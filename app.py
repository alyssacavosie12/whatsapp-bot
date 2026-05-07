"""WhatsApp Bot for Tulum BTX.

Uses Meta WhatsApp Cloud API + Claude AI for smart client responses.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os

import requests
from flask import Flask, jsonify, redirect, request, url_for
from werkzeug.security import check_password_hash
from werkzeug.exceptions import RequestEntityTooLarge

from ai_responder import get_ai_response
from admin_security import admin_response, client_ip, inbox_auth_challenge
from admin_views import render_admin_messages_page
from auth_throttle import (
    clear_inbox_auth_failures,
    inbox_auth_keys,
    is_inbox_auth_limited,
    record_inbox_auth_failure,
)
from compliance import build_inbound_opt_in_evidence
from content_loader import detect_language, get_response
from dedup import seen_message
from faq import find_best_faq_match
from graph_api import summarize_graph_error
from http_hardening import build_webhook_rate_limit, configure_talisman
from message_store import (
    list_messages as list_inbox_messages,
    record_audit_event,
    record_incoming_message,
    record_opt_in_proof,
    soft_delete_message,
)
from phone_utils import is_valid_phone, mask_phone, normalize_phone
from rate_limit import allow_phone_message
from settings import (
    BOT_DISCLOSURE,
    FLASK_SECRET_KEY,
    FORCE_HTTPS,
    GRAPH_API_VERSION,
    INCOMING_MESSAGE_LOG_MAX_CHARS,
    INBOX_ADMIN_PASSWORD_HASH,
    INBOX_ADMIN_USERNAME,
    INBOX_CSRF_SECRET,
    INBOX_DATABASE_URL,
    INBOX_ENABLED,
    INBOX_ENCRYPTION_KEY,
    INBOX_PROOF_SECRET,
    INBOX_REQUIRE_ENCRYPTION,
    INBOX_RETENTION_DAYS,
    INBOX_VIEWER_PASSWORD_HASH,
    INBOX_VIEWER_USERNAME,
    LOG_INCOMING_MESSAGES,
    MAX_CONTENT_LENGTH,
    MAX_INCOMING_TEXT_CHARS,
    META_APP_SECRET,
    RATE_LIMIT_STORAGE_URL,
    TEAM_NOTIFY_PHONE,
    VERIFY_TOKEN,
    WEBHOOK_RATE_LIMIT,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_TOKEN,
)
from text_utils import sanitize_untrusted_text
from webhook_events import iter_webhook_messages
from webhook_schema import validate_webhook_payload


TEXT_MESSAGE_TYPE = "text"
HUMAN_HANDOFF_KEYWORD = "HUMAN"
MEDIA_MESSAGE_TYPES = {"image", "document", "audio", "video"}
MAX_SENDER_NAME_LENGTH = 64
INBOX_ADMIN_ROLE = "admin"
INBOX_VIEWER_ROLE = "viewer"
INBOX_ROLES = {INBOX_VIEWER_ROLE: 1, INBOX_ADMIN_ROLE: 2}
MESSAGE_TOO_LONG_FALLBACK = {
    "en": "Thanks - that message is too long. Please send a shorter version.",
    "es": "Gracias - ese mensaje es demasiado largo. Envia una version mas corta.",
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.update(
    MAX_CONTENT_LENGTH=MAX_CONTENT_LENGTH,
    SECRET_KEY=FLASK_SECRET_KEY or os.urandom(32),
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
app.debug = False


def rate_limit_key() -> str:
    """Return the client key used by Flask-Limiter."""
    return client_ip() or "unknown"


configure_talisman(app, force_https=FORCE_HTTPS)
webhook_rate_limit = build_webhook_rate_limit(
    app,
    key_func=rate_limit_key,
    rate_limit=WEBHOOK_RATE_LIMIT,
    storage_uri=RATE_LIMIT_STORAGE_URL,
)


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


def log_incoming_text_message(
    sender_name: str,
    sender_phone: str,
    message_type: str,
    incoming_text: str,
) -> None:
    """Log incoming message metadata, and text only when explicitly enabled."""
    if LOG_INCOMING_MESSAGES:
        logger.info(
            "Incoming message from %s (%s), type=%s, length=%s, text=%s",
            sender_name or "unknown",
            mask_phone(sender_phone),
            message_type,
            len(incoming_text),
            sanitize_untrusted_text(incoming_text, INCOMING_MESSAGE_LOG_MAX_CHARS)
            or "empty",
        )
        return

    logger.info(
        "Message from %s (%s), type=%s, length=%s",
        sender_name or "unknown",
        mask_phone(sender_phone),
        message_type,
        len(incoming_text),
    )


def inbox_configured() -> bool:
    """Return True when the admin inbox can use a database."""
    return bool(INBOX_ENABLED and INBOX_DATABASE_URL)


def inbox_auth_configured() -> bool:
    """Return True when at least one admin inbox user is configured."""
    return bool(
        (INBOX_ADMIN_USERNAME and INBOX_ADMIN_PASSWORD_HASH)
        or (INBOX_VIEWER_USERNAME and INBOX_VIEWER_PASSWORD_HASH)
    )


def inbox_encryption_configured() -> bool:
    """Return True when inbox storage satisfies encryption policy."""
    return bool(not INBOX_REQUIRE_ENCRYPTION or INBOX_ENCRYPTION_KEY)


def role_allows(user_role: str, required_role: str) -> bool:
    """Return True when a user's inbox role satisfies a required role."""
    return INBOX_ROLES.get(user_role, 0) >= INBOX_ROLES.get(required_role, 0)


def get_inbox_users() -> list[dict[str, str]]:
    """Build configured admin inbox users from environment variables."""
    users = []

    if INBOX_ADMIN_USERNAME and INBOX_ADMIN_PASSWORD_HASH:
        users.append(
            {
                "username": INBOX_ADMIN_USERNAME,
                "password_hash": INBOX_ADMIN_PASSWORD_HASH,
                "role": INBOX_ADMIN_ROLE,
            }
        )

    if INBOX_VIEWER_USERNAME and INBOX_VIEWER_PASSWORD_HASH:
        users.append(
            {
                "username": INBOX_VIEWER_USERNAME,
                "password_hash": INBOX_VIEWER_PASSWORD_HASH,
                "role": INBOX_VIEWER_ROLE,
            }
        )

    return users


def authenticate_inbox_user() -> dict[str, str] | None:
    """Authenticate the current request using HTTP Basic auth."""
    auth = request.authorization

    if not auth or not auth.username or auth.password is None:
        return None

    for user in get_inbox_users():
        if not hmac.compare_digest(auth.username, user["username"]):
            continue

        try:
            password_ok = check_password_hash(
                user["password_hash"],
                auth.password,
            )
        except ValueError:
            logger.error("Invalid inbox password hash for user role=%s", user["role"])
            return None

        if password_ok:
            return {"username": user["username"], "role": user["role"]}

    return None


def require_inbox_user(required_role: str = INBOX_VIEWER_ROLE):
    """Return the authenticated inbox user or a response to send back."""
    if not inbox_configured():
        return None, admin_response("Inbox is not configured", 503)

    if not inbox_encryption_configured():
        return None, admin_response("Inbox encryption is not configured", 503)

    if not inbox_auth_configured():
        return None, admin_response("Inbox authentication is not configured", 503)

    auth = request.authorization
    throttle_keys = inbox_auth_keys(client_ip(), auth.username if auth else "")

    if is_inbox_auth_limited(throttle_keys):
        return None, admin_response("Too many failed login attempts", 429)

    user = authenticate_inbox_user()
    if not user:
        if auth and auth.username:
            record_inbox_auth_failure(throttle_keys)
        return None, inbox_auth_challenge()

    clear_inbox_auth_failures(throttle_keys)

    if not role_allows(user["role"], required_role):
        return None, admin_response("Forbidden", 403)

    return user, None


def csrf_secret() -> str:
    """Return the secret used to protect state-changing admin forms."""
    return INBOX_CSRF_SECRET or META_APP_SECRET


def inbox_proof_secret() -> str:
    """Return the secret used to HMAC opt-in proof records."""
    return INBOX_PROOF_SECRET or INBOX_CSRF_SECRET or META_APP_SECRET


def inbox_csrf_token(username: str, action: str, target_id: int) -> str:
    """Build a stable HMAC token for an admin inbox form action."""
    secret = csrf_secret()
    if not secret:
        return ""

    payload = f"{username}:{action}:{target_id}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def valid_inbox_csrf(username: str, action: str, target_id: int) -> bool:
    """Validate a submitted admin inbox CSRF token."""
    expected = inbox_csrf_token(username, action, target_id)
    submitted = request.form.get("csrf_token", "")

    return bool(expected and hmac.compare_digest(expected, submitted))


def audit_inbox_action(
    user: dict[str, str],
    action: str,
    *,
    target_message_id: int | None = None,
    metadata: dict | None = None,
) -> None:
    """Write an inbox audit event without leaking message content to logs."""
    if not inbox_configured():
        return

    try:
        record_audit_event(
            INBOX_DATABASE_URL,
            actor=user["username"],
            actor_role=user["role"],
            action=action,
            target_message_id=target_message_id,
            ip_address=client_ip(),
            user_agent=request.headers.get("User-Agent", ""),
            metadata=metadata or {},
        )
    except Exception as exc:
        logger.error("Failed to record inbox audit event: %s", exc.__class__.__name__)


def store_incoming_message(
    message_id: str,
    sender_phone: str,
    sender_name: str,
    message_type: str,
    body: object,
) -> None:
    """Persist an inbound message for the admin inbox when configured."""
    if not inbox_configured():
        return

    if not inbox_encryption_configured():
        logger.error("Inbox encryption is required; incoming message was not stored")
        return

    try:
        record_incoming_message(
            INBOX_DATABASE_URL,
            whatsapp_message_id=message_id,
            sender_phone=sender_phone,
            sender_phone_masked=mask_phone(sender_phone),
            sender_name=sender_name,
            message_type=message_type,
            body=body,
            encryption_key=INBOX_ENCRYPTION_KEY,
            retention_days=INBOX_RETENTION_DAYS,
        )
        record_opt_in_proof(
            INBOX_DATABASE_URL,
            whatsapp_message_id=message_id,
            sender_phone=sender_phone,
            proof_type="inbound_customer_initiated",
            proof_source="whatsapp_webhook",
            evidence=build_inbound_opt_in_evidence(
                message_id,
                sender_phone,
                message_type,
                body,
            ),
            proof_secret=inbox_proof_secret(),
            encryption_key=INBOX_ENCRYPTION_KEY,
        )
    except Exception as exc:
        logger.error("Failed to store incoming message: %s", exc.__class__.__name__)


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


def process_webhook_message(value: dict, message: dict) -> str:
    """Process one WhatsApp message from a webhook payload."""
    message_id = message.get("id", "")

    if message_id and seen_message(message_id):
        logger.info(
            "Duplicate message ignored: %s",
            sanitize_untrusted_text(message_id, 80),
        )
        return "duplicate"

    sender_phone_raw = message.get("from", "")
    sender_phone = normalize_phone(sender_phone_raw)

    if not is_valid_phone(sender_phone):
        logger.warning(
            "Invalid sender phone ignored: %s",
            sanitize_untrusted_text(sender_phone_raw, 32) or "empty",
        )
        return "invalid sender"

    if not allow_phone_message(sender_phone):
        logger.warning("Rate limit exceeded for %s", mask_phone(sender_phone))
        return "rate limited"

    message_type = message.get("type", "")

    contacts = value.get("contacts", [{}])
    raw_sender_name = (
        contacts[0].get("profile", {}).get("name", "") if contacts else ""
    )
    sender_name = sanitize_sender_name(raw_sender_name)

    incoming_text = ""
    if message_type == TEXT_MESSAGE_TYPE:
        incoming_text = str(message.get("text", {}).get("body", "") or "").strip()

    store_incoming_message(
        message_id,
        sender_phone,
        sender_name,
        message_type,
        incoming_text,
    )

    if message_type == TEXT_MESSAGE_TYPE:
        lang = detect_language(incoming_text[:MAX_INCOMING_TEXT_CHARS])

        log_incoming_text_message(
            sender_name,
            sender_phone,
            message_type,
            incoming_text,
        )

        if not incoming_text:
            send_whatsapp_message(sender_phone, get_response("unknown_message", lang))
            return "ok"

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
            return "ok"

        if incoming_text.upper() == HUMAN_HANDOFF_KEYWORD:
            response_text = get_response("human_handoff", lang)
            send_whatsapp_message(sender_phone, response_text)
            notify_team(build_handoff_notification(sender_name, sender_phone))
            logger.info("Human handoff requested by %s", mask_phone(sender_phone))
            return "ok"

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

    return "ok"


@app.route("/", methods=["GET"])
def root():
    return jsonify({"status": "ok", "service": "tulum-btx-whatsapp-bot"}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200


@app.route("/admin/messages", methods=["GET"])
def admin_messages():
    """Show recent incoming WhatsApp messages to authorized users."""
    user, error_response = require_inbox_user(INBOX_VIEWER_ROLE)
    if error_response:
        return error_response

    query = request.args.get("q", "").strip()

    try:
        limit = int(request.args.get("limit", "100"))
    except ValueError:
        limit = 100

    limit = max(1, min(limit, 500))

    try:
        messages = list_inbox_messages(
            INBOX_DATABASE_URL,
            query=query,
            limit=limit,
            encryption_key=INBOX_ENCRYPTION_KEY,
        )
    except Exception as exc:
        logger.error("Failed to load inbox messages: %s", exc.__class__.__name__)
        return admin_response("Inbox is unavailable", 503)

    audit_inbox_action(
        user,
        "view_messages",
        metadata={"has_query": bool(query), "result_count": len(messages)},
    )

    return admin_response(
        render_admin_messages_page(
            user,
            messages,
            query=query,
            limit=limit,
            admin_role=INBOX_ADMIN_ROLE,
            csrf_token_builder=inbox_csrf_token,
        )
    )


@app.route("/admin/messages/<int:message_id>/delete", methods=["POST"])
def admin_delete_message(message_id: int):
    """Soft-delete one inbox message."""
    user, error_response = require_inbox_user(INBOX_ADMIN_ROLE)
    if error_response:
        return error_response

    if not valid_inbox_csrf(user["username"], "delete", message_id):
        return admin_response("Forbidden", 403)

    try:
        deleted = soft_delete_message(
            INBOX_DATABASE_URL,
            message_id=message_id,
            deleted_by=user["username"],
        )
    except Exception as exc:
        logger.error("Failed to delete inbox message: %s", exc.__class__.__name__)
        return admin_response("Inbox is unavailable", 503)

    audit_inbox_action(
        user,
        "delete_message",
        target_message_id=message_id,
        metadata={"deleted": deleted},
    )

    return redirect(url_for("admin_messages"), code=303)


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
@webhook_rate_limit
def handle_message():
    """Process incoming WhatsApp webhook events."""
    if not verify_meta_signature():
        return jsonify({"status": "invalid signature"}), 401

    if not request.is_json:
        return jsonify({"status": "unsupported content type"}), 415

    data = request.get_json(silent=True)

    if not data:
        return jsonify({"status": "no data"}), 400

    payload_ok, payload_error = validate_webhook_payload(data)
    if not payload_ok:
        logger.warning(
            "Invalid webhook payload rejected: %s",
            sanitize_untrusted_text(payload_error, 120),
        )
        return jsonify({"status": "invalid payload"}), 400

    try:
        events = list(iter_webhook_messages(data))

        if not events:
            return jsonify({"status": "no messages"}), 200

        statuses = []

        for value, message in events:
            try:
                statuses.append(process_webhook_message(value, message))
            except Exception as exc:
                logger.error("Error processing message: %s", exc.__class__.__name__)
                statuses.append("ok")

        if len(statuses) == 1 and statuses[0] != "ok":
            return jsonify({"status": statuses[0]}), 200

    except Exception as exc:
        logger.error("Error processing webhook: %s", exc.__class__.__name__)

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
