"""Privacy Notice content and rendering."""

from __future__ import annotations

import html
from dataclasses import dataclass

from settings import (
    PRIVACY_CONTACT_EMAIL,
    PRIVACY_CONTACT_PHONE,
    PRIVACY_NOTICE_LAST_UPDATED,
    PRIVACY_NOTICE_URL,
    PRIVACY_RESPONSIBLE_ADDRESS,
    PRIVACY_RESPONSIBLE_NAME,
)

__all__ = [
    "PrivacyNoticeSection",
    "privacy_notice_html",
    "privacy_notice_text",
]


@dataclass(frozen=True)
class PrivacyNoticeSection:
    """One bilingual Privacy Notice section."""

    title: str
    paragraphs: tuple[str, ...] = ()
    bullets: tuple[str, ...] = ()


def _notice_sections() -> tuple[PrivacyNoticeSection, ...]:
    """Return structured Privacy Notice sections.

    Legal/privacy content should be reviewed periodically, especially when
    LFPDPPP/ARCO guidance, clinic workflows, subprocessors, transfers, AI use,
    or sensitive-data handling changes.
    """
    return (
        PrivacyNoticeSection(
            title="Responsible party / Responsable",
            paragraphs=(
                PRIVACY_RESPONSIBLE_NAME,
                f"Address / Domicilio: {PRIVACY_RESPONSIBLE_ADDRESS}",
                f"Contact / Contacto: {PRIVACY_CONTACT_EMAIL} | {PRIVACY_CONTACT_PHONE}",
                f"Full notice URL / URL del aviso: {PRIVACY_NOTICE_URL}",
            ),
        ),
        PrivacyNoticeSection(
            title="Who we are / Quienes somos",
            paragraphs=(
                "Tulum Botox (Tulum BTX) provides aesthetic clinic services in Tulum and "
                "Playa del Carmen, Mexico. This notice explains how personal data is processed "
                "when you contact us through WhatsApp, our website, or related clinic channels.",
            ),
        ),
        PrivacyNoticeSection(
            title="Data we collect / Datos que recabamos",
            bullets=(
                "WhatsApp sender identifier, phone number or business-scoped user ID.",
                "WhatsApp profile name, message text, message metadata, timestamps, and "
                "opt-in or opt-out evidence.",
                "Appointment, consultation, and service-interest information you choose to "
                "share with us.",
                "Information about aesthetic procedures, skin concerns, contraindications, "
                "allergies, pregnancy, medical history, or other health-related details if "
                "you voluntarily include them in your messages.",
            ),
        ),
        PrivacyNoticeSection(
            title="Sensitive personal data / Datos personales sensibles",
            paragraphs=(
                "Some messages about aesthetic procedures or health-related concerns may be "
                "considered sensitive personal data under Mexican data protection law. We use "
                "this information only to respond to your request, route you to the clinic team, "
                "book consultations, and maintain legally necessary records.",
                "Please avoid sending emergency medical information through WhatsApp. When the "
                "bot detects medical safety details or a personal aesthetic consultation request, "
                "it avoids AI processing and stores a redacted category marker instead of the full "
                "message text in the admin inbox.",
            ),
        ),
        PrivacyNoticeSection(
            title="Purposes / Finalidades",
            bullets=(
                "Respond to questions about Tulum Botox services, prices, booking, and locations.",
                "Route complex, medical, contraindication, or human-assistance requests "
                "to clinic staff.",
                "Send WhatsApp replies, booking links, and operational service messages.",
                "Maintain security, anti-spam, rate-limiting, audit, opt-in, opt-out, "
                "and deletion records.",
                "Comply with legal, regulatory, accounting, and dispute-resolution duties.",
            ),
        ),
        PrivacyNoticeSection(
            title="AI processing / Tratamiento con IA",
            paragraphs=(
                "The bot tries to answer from the local FAQ first. If the local FAQ does not "
                "answer the question, the text of your WhatsApp message, your sanitized profile "
                "name, and the minimum conversation context needed to answer may be sent to "
                "Anthropic PBC for limited-scope AI processing.",
                "This third-party processing is used only to support customer service for Tulum "
                "Botox, not to provide emergency care or a medical diagnosis. Detected medical "
                "safety details and personal aesthetic consultation requests are routed to the "
                "clinic team instead of Anthropic, and you can reply HUMAN at any time.",
            ),
        ),
        PrivacyNoticeSection(
            title="Subprocessors and service providers / Subencargados y proveedores",
            paragraphs=(
                "Your data may be processed by these third-party subprocessors for the "
                "listed purposes:",
            ),
            bullets=(
                "Meta Platforms Inc. / WhatsApp: receives WhatsApp identifiers, profile names, "
                "message content, message metadata, and delivery data to provide WhatsApp "
                "messaging "
                "and the WhatsApp Business API.",
                "Railway Corporation: hosts the application, logs, PostgreSQL database, and "
                "operational infrastructure. Railway may process encrypted inbox records, masked "
                "or hashed identifiers, operational logs, and configuration metadata needed to run "
                "the service.",
                "Anthropic PBC: receives message text and the minimum context necessary for "
                "AI-assisted customer support only when local FAQ matching is insufficient and "
                "the message is not detected as medical or sensitive personal data.",
            ),
        ),
        PrivacyNoticeSection(
            title="Transfers / Transferencias",
            paragraphs=(
                "Data may be processed in Mexico, the United States, or other countries where "
                "our providers operate infrastructure. We share only what is necessary for the "
                "purposes described in this notice and for legally required disclosures.",
            ),
        ),
        PrivacyNoticeSection(
            title="Retention / Conservacion",
            paragraphs=(
                "Inbox messages and audit records are retained only as long as necessary for "
                "customer service, security, opt-in/opt-out evidence, legal compliance, and "
                "dispute handling. The bot is configured to delete expired inbox records using "
                "the configured retention period.",
                "Opt-out proof may be retained to honor your opposition request unless you ask "
                "us to delete that record too.",
            ),
        ),
        PrivacyNoticeSection(
            title="ARCO rights and deletion / Derechos ARCO y eliminacion",
            paragraphs=(
                "You may request access, rectification, cancellation/deletion, or opposition to "
                "processing (ARCO), as well as withdrawal of consent where applicable. Contact us "
                f"at {PRIVACY_CONTACT_EMAIL} or {PRIVACY_CONTACT_PHONE}.",
                "Please include enough information to identify your WhatsApp conversation, such as "
                "the phone number or WhatsApp account used. We may request identity verification "
                "before completing the request.",
            ),
        ),
        PrivacyNoticeSection(
            title="How to limit use / Como limitar el uso",
            paragraphs=(
                "Reply STOP, BAJA, UNSUBSCRIBE, or a similar opt-out instruction to stop automated "
                "WhatsApp messages. You can also contact us using the details above.",
            ),
        ),
        PrivacyNoticeSection(
            title="Security / Seguridad",
            paragraphs=(
                "We use access controls, Railway environment variables for secrets, webhook "
                "signature verification, rate limiting, audit logs, retention cleanup, and "
                "encryption for configured inbox message storage. No internet system is risk free, "
                "but we work to limit access to authorized personnel and providers.",
            ),
        ),
        PrivacyNoticeSection(
            title="Changes / Cambios al aviso",
            paragraphs=(
                "We may update this notice when our processing, providers, or legal duties "
                "change. "
                f"The latest version will be available at {PRIVACY_NOTICE_URL}.",
            ),
        ),
    )


def _render_section_text(section: PrivacyNoticeSection) -> str:
    """Render one section as plain text."""
    lines = [section.title]

    for paragraph in section.paragraphs:
        lines.append(paragraph)

    for bullet in section.bullets:
        lines.append(f"- {bullet}")

    return "\n".join(lines)


def privacy_notice_text() -> str:
    """Return the Privacy Notice as plain text."""
    header = (
        "Privacy Notice / Aviso de Privacidad\n\n"
        f"Last updated / Ultima actualizacion: {PRIVACY_NOTICE_LAST_UPDATED}"
    )
    sections = "\n\n".join(_render_section_text(section) for section in _notice_sections())
    return f"{header}\n\n{sections}\n"


def _paragraph_html(text: str) -> str:
    """Render escaped paragraph HTML."""
    return f"<p>{html.escape(text)}</p>"


def _section_html(section: PrivacyNoticeSection) -> str:
    """Render one escaped section as HTML."""
    parts = ["<section>", f"<h2>{html.escape(section.title)}</h2>"]

    parts.extend(_paragraph_html(paragraph) for paragraph in section.paragraphs)

    if section.bullets:
        parts.append("<ul>")
        parts.extend(f"<li>{html.escape(bullet)}</li>" for bullet in section.bullets)
        parts.append("</ul>")

    parts.append("</section>")
    return "\n".join(parts)


def privacy_notice_html() -> str:
    """Return an escaped, readable HTML version of the Privacy Notice."""
    sections_html = "\n".join(_section_html(section) for section in _notice_sections())
    last_updated = html.escape(PRIVACY_NOTICE_LAST_UPDATED)

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
            margin: 0 0 8px;
        }}
        .updated {{
            color: #526071;
            margin: 0 0 24px;
        }}
        section {{
            margin: 28px 0;
        }}
        h2 {{
            font-size: 20px;
            margin: 0 0 10px;
        }}
        p {{
            margin: 0 0 12px;
        }}
        ul {{
            margin: 0 0 12px 22px;
            padding: 0;
        }}
        li {{
            margin: 0 0 8px;
        }}
    </style>
</head>
<body>
    <main>
        <h1>Privacy Notice | Aviso de Privacidad</h1>
        <p class="updated">Last updated / Ultima actualizacion: {last_updated}</p>
        {sections_html}
    </main>
</body>
</html>"""
