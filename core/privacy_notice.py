"""Privacy Notice content and rendering."""

from __future__ import annotations

import html

from settings import (
    PRIVACY_CONTACT_EMAIL,
    PRIVACY_CONTACT_PHONE,
    PRIVACY_NOTICE_LAST_UPDATED,
    PRIVACY_NOTICE_URL,
    PRIVACY_RESPONSIBLE_ADDRESS,
    PRIVACY_RESPONSIBLE_NAME,
)


def privacy_notice_text() -> str:
    """Return the Privacy Notice as plain text."""
    return f"""Privacy Notice / Aviso de Privacidad

Last updated / Ultima actualizacion: {PRIVACY_NOTICE_LAST_UPDATED}

Responsible party / Responsable
{PRIVACY_RESPONSIBLE_NAME}
Address / Domicilio: {PRIVACY_RESPONSIBLE_ADDRESS}
Contact / Contacto: {PRIVACY_CONTACT_EMAIL} | {PRIVACY_CONTACT_PHONE}
Full notice URL / URL del aviso: {PRIVACY_NOTICE_URL}

Who we are / Quienes somos
Tulum Botox (Tulum BTX) provides aesthetic clinic services in Tulum and
Playa del Carmen, Mexico. This notice explains how personal data is processed
when you contact us through WhatsApp, our website, or related clinic channels.

Data we collect / Datos que recabamos
- WhatsApp sender identifier, phone number or business-scoped user ID.
- WhatsApp profile name, message text, message metadata, timestamps, and
  opt-in or opt-out evidence.
- Appointment, consultation, and service-interest information you choose to
  share with us.
- Information about aesthetic procedures, skin concerns, contraindications,
  allergies, pregnancy, medical history, or other health-related details if
  you voluntarily include them in your messages.

Sensitive personal data / Datos personales sensibles
Some messages about aesthetic procedures or health-related concerns may be
considered sensitive personal data under Mexican data protection law. We use
this information only to respond to your request, route you to the clinic team,
book consultations, and maintain legally necessary records. Please avoid
sending emergency medical information through WhatsApp. When the bot detects
medical safety details or a personal aesthetic consultation request, it avoids
AI processing and stores a redacted category marker instead of the full message
text in the admin inbox.

Purposes / Finalidades
- Respond to questions about Tulum Botox services, prices, booking, and
  locations.
- Route complex, medical, contraindication, or human-assistance requests to
  clinic staff.
- Send WhatsApp replies, booking links, and operational service messages.
- Maintain security, anti-spam, rate-limiting, audit, opt-in, opt-out, and
  deletion records.
- Comply with legal, regulatory, accounting, and dispute-resolution duties.

AI processing / Tratamiento con IA
The bot tries to answer from the local FAQ first. If the local FAQ does not
answer the question, the text of your WhatsApp message, your sanitized profile
name, and the minimum conversation context needed to answer may be sent to
Anthropic PBC for limited-scope AI processing. This third-party processing is
used only to support customer service for Tulum Botox, not to provide emergency
care or a medical diagnosis. Detected medical safety details and personal
aesthetic consultation requests are routed to the clinic team instead of
Anthropic, and you can reply HUMAN at any time.

Subprocessors and service providers / Subencargados y proveedores
Your data may be processed by these third-party subprocessors for the listed
purposes:
- Meta Platforms Inc. / WhatsApp: receives WhatsApp identifiers, profile names,
  message content, message metadata, and delivery data to provide WhatsApp
  messaging and the WhatsApp Business API.
- Railway Corporation: hosts the application, logs, PostgreSQL database, and
  operational infrastructure. Railway may process encrypted inbox records,
  masked or hashed identifiers, operational logs, and configuration metadata
  needed to run the service.
- Anthropic PBC: receives message text and the minimum context necessary for
  AI-assisted customer support only when local FAQ matching is insufficient and
  the message is not detected as medical or sensitive personal data.

Transfers / Transferencias
Data may be processed in Mexico, the United States, or other countries where
our providers operate infrastructure. We share only what is necessary for the
purposes described in this notice and for legally required disclosures.

Retention / Conservacion
Inbox messages and audit records are retained only as long as necessary for
customer service, security, opt-in/opt-out evidence, legal compliance, and
dispute handling. The bot is configured to delete expired inbox records using
the configured retention period. Opt-out proof may be retained to honor your
opposition request unless you ask us to delete that record too.

ARCO rights and deletion / Derechos ARCO y eliminacion
You may request access, rectification, cancellation/deletion, or opposition to
processing (ARCO), as well as withdrawal of consent where applicable. Contact
us at {PRIVACY_CONTACT_EMAIL} or {PRIVACY_CONTACT_PHONE}. Please include enough
information to identify your WhatsApp conversation, such as the phone number or
WhatsApp account used. We may request identity verification before completing
the request.

How to limit use / Como limitar el uso
Reply STOP, BAJA, UNSUBSCRIBE, or a similar opt-out instruction to stop
automated WhatsApp messages. You can also contact us using the details above.

Security / Seguridad
We use access controls, Railway environment variables for secrets, webhook
signature verification, rate limiting, audit logs, retention cleanup, and
encryption for configured inbox message storage. No internet system is risk
free, but we work to limit access to authorized personnel and providers.

Changes / Cambios al aviso
We may update this notice when our processing, providers, or legal duties
change. The latest version will be available at {PRIVACY_NOTICE_URL}.
"""


def privacy_notice_html() -> str:
    """Return a simple HTML version of the Privacy Notice."""
    escaped = html.escape(privacy_notice_text())
    body = escaped.replace("\n", "<br>\n")
    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Privacy Notice | Aviso de Privacidad</title>
    <style>
        body {{
            color: #18212f;
            font-family: Arial, sans-serif;
            line-height: 1.55;
            margin: 0;
            padding: 24px;
        }}
        main {{
            margin: 0 auto;
            max-width: 920px;
        }}
        h1 {{
            font-size: 28px;
            margin: 0 0 16px;
        }}
        .notice {{
            white-space: normal;
        }}
    </style>
</head>
<body>
    <main>
        <h1>Privacy Notice | Aviso de Privacidad</h1>
        <div class="notice">{body}</div>
    </main>
</body>
</html>"""
