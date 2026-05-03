"""
WhatsApp Bot for Tulum BTX
Uses Meta WhatsApp Cloud API + Claude AI for client intake and FAQ responses.
"""

import os
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from faq import find_best_faq_match
from ai_responder import get_ai_response

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Configuration ───────────────────────────────────────────────
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "tulum-btx-webhook-token")
BOT_DISCLOSURE = os.getenv("BOT_DISCLOSURE", "false").lower() == "true"
TEAM_NOTIFY_PHONE = os.getenv("TEAM_NOTIFY_PHONE", "")  # Team WhatsApp number for alerts
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v21.0")

APPOINTMENT_KEYWORDS = [
    "appointment", "book", "booking", "schedule", "available", "availability",
    "consultation", "reserve", "price", "pricing", "cost", "quote",
    "cita", "agendar", "reservar", "disponible", "disponibilidad",
    "consulta", "precio", "cuanto", "cuánto", "cotizacion", "cotización",
]

SAFETY_KEYWORDS = [
    "trouble breathing", "difficulty breathing", "can't breathe", "shortness of breath",
    "difficulty swallowing", "can't swallow", "double vision", "blurred vision",
    "drooping eyelid", "muscle weakness", "severe swelling", "allergic reaction",
    "dificultad para respirar", "no puedo respirar", "falta de aire",
    "dificultad para tragar", "no puedo tragar", "vision doble", "visión doble",
    "vision borrosa", "visión borrosa", "parpado caido", "párpado caído",
    "debilidad muscular", "hinchazon severa", "hinchazón severa", "alergia",
]

HUMAN_HANDOFF_TEXT = (
    "No problem! A team member will get back to you shortly. "
    "If this is urgent or you are having severe symptoms, please seek emergency care now."
)

SAFETY_RESPONSE_TEXT = (
    "If you are having trouble breathing, trouble swallowing, vision changes, "
    "severe swelling, or muscle weakness, please seek emergency medical care immediately. "
    "I have also flagged this for our team so someone can follow up as soon as possible."
)

# ─── Phone Number Normalization ────────────────────────────────
def normalize_phone(phone: str) -> str:
    """
    Normalize Mexican phone numbers from 521XXXXXXXXXX to 52XXXXXXXXXX.
    WhatsApp API sometimes delivers Mexican numbers with an extra '1'
    after the country code (521...), but messages must be sent to (52...).
    """
    if phone and phone.startswith("521") and len(phone) == 13:
        return "52" + phone[3:]
    return phone

# ─── Webhook Verification (Meta requires this) ──────────────────
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    """Meta sends a GET request to verify your webhook URL."""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("Webhook verified successfully")
        return challenge, 200
    else:
        logger.warning("Webhook verification failed")
        return "Forbidden", 403


# ─── Incoming Messages ──────────────────────────────────────────
@app.route("/webhook", methods=["POST"])
def handle_message():
    """Process incoming WhatsApp messages."""
    data = request.get_json()

    if not data:
        return jsonify({"status": "no data"}), 400

    try:
        # Extract message details from the webhook payload
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            # This might be a status update, not a message
            return jsonify({"status": "no messages"}), 200

        message = messages[0]
        sender_phone = normalize_phone(message.get("from"))
        message_type = message.get("type")

        # Get sender name if available
        contacts = value.get("contacts", [{}])
        sender_name = contacts[0].get("profile", {}).get("name", "") if contacts else ""

        if message_type == "text":
            incoming_text = message["text"]["body"].strip()
            logger.info(f"Message from {sender_name} ({sender_phone}): {incoming_text}")

            # Handle "HUMAN" before FAQ/AI to avoid duplicate replies
            if incoming_text.upper() == "HUMAN":
                send_whatsapp_message(sender_phone, HUMAN_HANDOFF_TEXT)
                notify_team(
                    f"HUMAN REQUESTED\n"
                    f"Customer: {sender_name} ({sender_phone})\n"
                    f"Please respond to them directly."
                )
                logger.info(f"Human handoff requested by {sender_phone}")
                return jsonify({"status": "ok"}), 200

            msg_lower = incoming_text.lower()

            if any(kw in msg_lower for kw in SAFETY_KEYWORDS):
                send_whatsapp_message(sender_phone, SAFETY_RESPONSE_TEXT)
                notify_team(
                    f"SAFETY FOLLOW-UP\n"
                    f"Customer: {sender_name} ({sender_phone})\n"
                    f"Message: {incoming_text}\n\n"
                    f"Potential urgent post-treatment or medical concern. Follow up ASAP."
                )
                logger.info(f"Safety concern flagged by {sender_phone}")
                return jsonify({"status": "ok"}), 200

            # Step 1: Try FAQ match first (fast, no API cost)
            faq_answer = find_best_faq_match(incoming_text)

            if faq_answer:
                response_text = faq_answer
                logger.info("Responded via FAQ match")
            else:
                # Step 2: Fall back to AI for a natural response
                response_text = get_ai_response(incoming_text, sender_name)
                logger.info("Responded via AI")

            # Optional: Add bot disclosure
            if BOT_DISCLOSURE and not faq_answer:
                response_text += "\n\n_This is an automated assistant. Reply HUMAN to speak with our team._"

            send_whatsapp_message(sender_phone, response_text)

            if any(kw in msg_lower for kw in APPOINTMENT_KEYWORDS):
                notify_team(
                    f"APPOINTMENT / PRICING LEAD\n"
                    f"Customer: {sender_name} ({sender_phone})\n"
                    f"Message: {incoming_text}\n\n"
                    f"Please follow up with availability, consultation details, and pricing."
                )

        elif message_type in ["image", "document", "audio", "video"]:
            send_whatsapp_message(
                sender_phone,
                "Thanks for sending that. A team member will review it and reply shortly. "
                "If this is urgent or you are having severe symptoms, please seek emergency care now."
            )
        else:
            send_whatsapp_message(
                sender_phone,
                "Hi! Please send us a text message and we'll help you with Tulum BTX services."
            )

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)

    return jsonify({"status": "ok"}), 200


# ─── Notify Team (for extension requests, human handoffs, etc.) ──
def notify_team(message):
    """Send an alert to your team's WhatsApp number."""
    if TEAM_NOTIFY_PHONE:
        send_whatsapp_message(TEAM_NOTIFY_PHONE, message)
        logger.info(f"Team notified: {message[:50]}...")
    else:
        logger.warning("TEAM_NOTIFY_PHONE not set — team notification skipped")


# ─── Send Message via WhatsApp Cloud API ────────────────────────
def send_whatsapp_message(to_phone, text):
    """Send a text message through the WhatsApp Cloud API."""
    import requests

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
        response = requests.post(url, headers=headers, json=payload, timeout=15)
    except requests.RequestException as e:
        logger.error(f"WhatsApp API request failed: {e}", exc_info=True)
        return None

    if response.status_code == 200:
        logger.info(f"Message sent to {to_phone}")
    else:
        logger.error(f"Failed to send message: {response.status_code} - {response.text}")

    return response


# ─── Run ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
