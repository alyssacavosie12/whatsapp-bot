"""WhatsApp Bot for Tulum BTX.

Uses Meta WhatsApp Cloud API + Claude AI for smart client responses.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re

import requests
from flask import Flask, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from ai_responder import get_ai_response
from content_loader import detect_language, get_response
from dedup import seen_message
from faq import find_best_faq_match
from rate_limit import allow_phone_message
from settings import (
    BOT_DISCLOSURE,
    GRAPH_API_VERSION,
    MAX_CONTENT_LENGTH,
    MAX_INCOMING_TEXT_CHARS,
    META_APP_SECRET,
    TEAM_NOTIFY_PHONE,
    VERIFY_TOKEN,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_TOKEN,
)
from text_utils import sanitize_untrusted_text


TEXT_MESSAGE_TYPE = "text"
HUMAN_HANDOFF_KEYWORD = "HUMAN"
MEDIA_MESSAGE_TYPES = {"image", "document", "audio", "video"}
VALID_PHONE_RE = re.compile(r"\d{10,15}")
MAX_SENDER_NAME_LENGTH = 64
GRAPH_ERROR_FIELDS = ("code", "error_subcode", "type", "fbtrace_id")
MESSAGE_TOO_LONG_FALLBACK = {
    "en": "Thanks - that message is too long. Please send a shorter version.",
    "es": "Gracias - ese mensaje es demasiado largo. Envia una version mas corta.",
}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def normalize_phone(phone: str) -> str:
    """Normalize Mexican WhatsApp numbers from 521XXXXXXXXXX to 52XXXXXXXXXX."""
    phone = str(phone or "").strip()

    if phone and phone.startswith("521") and len(phone) == 13:
        return "52" + phone[3:]

    return phone


def is_valid_phone(phone: str) -> bool:
    """Return True for E.164-like WhatsApp recipient numbers without a plus sign."""
    return bool(VALID_PHONE_RE.fullmatch(str(phone or "")))


def mask_phone(phone: str) -> str:
    """Mask a phone number for logs."""
    digits = "".join(char for char in str(phone or "") if char.isdigit())

    if len(digits) < 4:
        return "***"

    return f"***{digits[-4:]}"


def sanitize_sender_name(sender_name: str) -> str:
    """Return a safe customer name for logs, prompts, and team notifications."""
    return sanitize_untrusted_text(sender_name, MAX_SENDER_NAME_LENGTH)


def get_message_too_long_response(lang: str) -> str:
    """Return configured or built-in response for overlong customer messages."""
    return get_response("message_too_long", lang) or MESSAGE_TOO_LONG_FALLBACK[lang]


def build_handoff_notification(sender_name: str, sender_phone: str) -> str:
    """Build a safe team alert for human handoff requests."""
    safe_name = sanitize_sender_name(sender_name) or "unknown"
    safe_phone = sender_phone if is_valid_phone(sender_phone) else "invalid"

    return (
        "HUMAN REQUESTED\n"
        f"Customer name: {safe_name}\n"
        f"Customer phone: +{safe_phone}\n"
        "Please respond to them directly."
    )


def summarize_graph_error(response: requests.Response) -> str:
    """Summarize Graph API errors without persisting response bodies or PII."""
    try:
        body = response.json()
    except (AttributeError, ValueError):
        return "body omitted"

    if not isinstance(body, dict) or not isinstance(body.get("error"), dict):
        return "body omitted"

    error = body["error"]
    fields = [
        f"{field}={sanitize_untrusted_text(error[field], 80)}"
        for field in GRAPH_ERROR_FIELDS
        if error.get(field)
    ]

    return ", ".join(fields) or "body omitted"


def verify_meta_signature() -> bool:
    """Verify Meta X-Hub-Signature-256 for POST webhooks. Always required."""
    if not META_APP_SECRET:
        logger.error("META_APP_SECRET is not set; refusing webhook")
        return False

    signature = request.headers.get("X-Hub-Signature-256", "")

    if not signature.startswith("sha256="):
        logger.warning("Missing or invalid X-Hub-Signature-256 header")
        return False

    raw_body = request.get_data(cache=True)
    expected = "sha256=" + hmac.new(
        META_APP_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


@app.route("/", methods=["GET"])
def root():
    return jsonify({"status": "ok", "service": "tulum-btx-whatsapp-bot"}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200


@app.errorhandler(RequestEntityTooLarge)
def handle_request_too_large(_exc):
    return jsonify({"status": "payload too large"}), 413


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    """Meta sends a GET request to verify the webhook URL."""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token", "")
    challenge = request.args.get("hub.challenge")

    if not VERIFY_TOKEN:
        logger.error("VERIFY_TOKEN is not set; refusing webhook verification")
        return "Forbidden", 403

    if mode == "subscribe" and hmac.compare_digest(
        token.encode("utf-8"), VERIFY_TOKEN.encode("utf-8")
    ):
        logger.info("Webhook verified successfully")
        return challenge, 200

    logger.warning("Webhook verification failed")
    return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def handle_message():
    """Process incoming WhatsApp webhook events."""
    if not verify_meta_signature():
        return jsonify({"status": "invalid signature"}), 401

    if not request.is_json:
        return jsonify({"status": "unsupported content type"}), 415

    data = request.get_json(silent=True)

    if not data:
        return jsonify({"status": "no data"}), 400

    try:
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return jsonify({"status": "no messages"}), 200

        message = messages[0]
        message_id = message.get("id", "")

        if message_id and seen_message(message_id):
            logger.info(
                "Duplicate message ignored: %s",
                sanitize_untrusted_text(message_id, 80),
            )
            return jsonify({"status": "duplicate"}), 200

        sender_phone_raw = message.get("from", "")
        sender_phone = normalize_phone(sender_phone_raw)

        if not is_valid_phone(sender_phone):
            logger.warning(
                "Invalid sender phone ignored: %s",
                sanitize_untrusted_text(sender_phone_raw, 32) or "empty",
            )
            return jsonify({"status": "invalid sender"}), 200

        if not allow_phone_message(sender_phone):
            logger.warning("Rate limit exceeded for %s", mask_phone(sender_phone))
            return jsonify({"status": "rate limited"}), 200

        message_type = message.get("type", "")

        contacts = value.get("contacts", [{}])
        raw_sender_name = (
            contacts[0].get("profile", {}).get("name", "") if contacts else ""
        )
        sender_name = sanitize_sender_name(raw_sender_name)

        if message_type == TEXT_MESSAGE_TYPE:
            incoming_text = str(message.get("text", {}).get("body", "") or "").strip()
            lang = detect_language(incoming_text[:MAX_INCOMING_TEXT_CHARS])

            logger.info(
                "Message from %s (%s), type=%s, length=%s",
                sender_name or "unknown",
                mask_phone(sender_phone),
                message_type,
                len(incoming_text),
            )

            if not incoming_text:
                send_whatsapp_message(sender_phone, get_response("unknown_message", lang))
                return jsonify({"status": "ok"}), 200

            if len(incoming_text) > MAX_INCOMING_TEXT_CHARS:
                logger.warning(
                    "Incoming text too long from %s: length=%s",
                    mask_phone(sender_phone),
                    len(incoming_text),
                )
                send_whatsapp_message(
                    sender_phone,
                    get_message_too_long_response(lang),
                )
                return jsonify({"status": "ok"}), 200

            if incoming_text.upper() == HUMAN_HANDOFF_KEYWORD:
                response_text = get_response("human_handoff", lang)
                send_whatsapp_message(sender_phone, response_text)
                notify_team(build_handoff_notification(sender_name, sender_phone))
                logger.info("Human handoff requested by %s", mask_phone(sender_phone))
                return jsonify({"status": "ok"}), 200

            faq_answer = find_best_faq_match(incoming_text)

            if faq_answer:
                response_text = faq_answer
                logger.info("Responded via FAQ match")
            else:
                response_text = get_ai_response(incoming_text, sender_name)
                logger.info("Responded via AI")

            if BOT_DISCLOSURE and not faq_answer:
                response_text += (
                    "\n\n_This is an automated assistant. "
                    "Reply HUMAN to speak with our team._"
                )

            send_whatsapp_message(sender_phone, response_text)

        elif message_type in MEDIA_MESSAGE_TYPES:
            send_whatsapp_message(sender_phone, get_response("media_response", "en"))
        else:
            send_whatsapp_message(sender_phone, get_response("unknown_message", "en"))

    except Exception as exc:
        logger.error("Error processing message: %s", exc.__class__.__name__)

    return jsonify({"status": "ok"}), 200


def notify_team(message: str) -> None:
    """Send an alert to the team WhatsApp number."""
    if TEAM_NOTIFY_PHONE:
        send_whatsapp_message(TEAM_NOTIFY_PHONE, message)
        logger.info("Team notified")
    else:
        logger.info("TEAM_NOTIFY_PHONE not set; team notification skipped")


def send_whatsapp_message(to_phone: str, text: str) -> requests.Response | None:
    """Send a text message through the WhatsApp Cloud API."""
    if not WHATSAPP_TOKEN:
        logger.error("WHATSAPP_TOKEN is not set")
        return None

    if not WHATSAPP_PHONE_NUMBER_ID:
        logger.error("WHATSAPP_PHONE_NUMBER_ID is not set")
        return None

    to_phone = normalize_phone(to_phone)

    if not to_phone:
        logger.error("Cannot send message: recipient phone is empty")
        return None

    if not is_valid_phone(to_phone):
        logger.error("Cannot send message: recipient phone is invalid")
        return None

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": text},
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
    except requests.RequestException as exc:
        logger.error("Failed to send message request: %s", exc.__class__.__name__)
        return None

    if response.status_code == 200:
        logger.info("Message sent to %s", mask_phone(to_phone))
    else:
        logger.error(
            "Failed to send message: status=%s, graph_error=%s",
            response.status_code,
            summarize_graph_error(response),
        )

    return response


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    host = os.getenv("HOST", "127.0.0.1")
    app.run(host=host, port=port)
