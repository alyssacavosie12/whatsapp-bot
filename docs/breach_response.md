# Personal Data Breach Response

Last reviewed: 2026-05-08

This playbook covers suspected or confirmed personal-data incidents involving
the Tulum Botox WhatsApp bot, Railway services, PostgreSQL inbox data, Redis
cache, Meta/WhatsApp delivery, and Anthropic AI processing.

This is an operational checklist, not legal advice. The responsible person must
confirm external notification duties with Mexican privacy counsel when a breach
is suspected or confirmed.

## Owners And Contacts

- Responsible party: Tulum Botox (Tulum BTX)
- Privacy contact: Ally@TulumBotox.com | +52 984 105 0808
- Internal incident owner: TBD
- Technical owner: TBD
- Legal/privacy counsel: TBD
- Railway: Central Station / Railway Support; for security or privacy reports,
  use the current contacts listed in Railway Support docs.
- Anthropic: support portal; governmental authorities may use Anthropic's
  designated regulator contact.
- Meta/WhatsApp: Meta Business Support / WhatsApp Business Manager support.
- INAI / CAS: atencion@inai.org.mx | 01-800-835-4324 | Insurgentes Sur 3211,
  Col. Insurgentes Cuicuilco, Coyoacan, C.P. 04530, Ciudad de Mexico.

## What Counts As A Breach

Treat any of the following as a suspected personal-data breach:

- unauthorized access to Railway, GitHub, Meta, Anthropic, Postgres, Redis, or
  admin inbox accounts;
- leaked Railway Variables, API keys, database URLs, Fernet keys, or admin
  password hashes;
- exposed WhatsApp message content, phone numbers, profile names, sender IDs,
  opt-in proof, opt-out records, audit logs, or backups;
- loss, alteration, deletion, unauthorized copy, or unauthorized use of inbox
  records;
- webhook spoofing, signature bypass, or unexpected outbound messages;
- vendor incident affecting Meta, Railway, Anthropic, or database backups.

## Severity

- SEV-1: confirmed unauthorized access to sensitive personal data, encryption
  keys, database credentials, or production admin access.
- SEV-2: suspected exposure of personal data or credentials without confirmed
  data access.
- SEV-3: limited security event with no personal-data exposure after review.

## First 0-2 Hours

1. Assign one incident owner and one note taker.
2. Start an incident log with UTC timestamps.
3. Preserve evidence before changing systems:
   - Railway deployment IDs, service IDs, environment, logs, metrics;
   - Git commit SHA and branch;
   - admin inbox audit rows;
   - Postgres backup/snapshot references;
   - suspicious IPs, user agents, message IDs, and request IDs.
4. Contain the issue:
   - rotate suspected Railway Variables;
   - revoke or rotate WhatsApp, Anthropic, Redis, Postgres, and Flask secrets;
   - disable compromised admin inbox credentials;
   - remove unnecessary Railway/GitHub members;
   - pause affected scheduled jobs if they may worsen the incident.
5. Keep the bot online only if it is safe to process new messages. If not,
   disable the public service or route users to human contact.

## First 24 Hours

Complete this assessment within 24 hours of detection:

- Was personal data accessed, copied, altered, lost, deleted, or used without
  authorization?
- What categories were involved:
  - WhatsApp sender ID / phone / BSUID;
  - profile name;
  - message text or redacted category marker;
  - sensitive aesthetic or health-related content;
  - opt-in or opt-out records;
  - admin audit logs;
  - API keys or encryption keys?
- Approximate number of affected people.
- Date/time of first access, detection, containment, and confirmation.
- Whether Fernet-encrypted data was exposed together with its key.
- Whether data was sent to a subprocesser or third party outside expected flow.
- Whether affected rights may be significantly impacted.
- Whether users need immediate protective steps.

Decision by 24 hours:

- SEV-1 or likely significant impact: prepare user notification and regulatory
  notification package.
- SEV-2: continue investigation, prepare draft notices, and reassess at least
  every 12 hours.
- SEV-3: document why notification is not required and close only after owner
  approval.

## Notification Within 72 Hours

Use 72 hours from breach confirmation as the internal maximum target for
external notification decisions. Notify sooner when enough facts are known.

Notify affected users without unjustified delay when the breach significantly
affects their patrimonial or moral rights. The notice should include:

- nature of the incident;
- personal data compromised;
- recommended protective steps;
- immediate corrective actions already taken;
- contact channel for more information.

Notify INAI or the competent authority when required by law, counsel, or the
confirmed impact assessment. The notification package should include:

- nature of the incident and compromised data;
- date/time detected and confirmed;
- systems affected;
- approximate number of affected people;
- corrective measures implemented;
- user-notification actions;
- preventive measures to avoid recurrence;
- contact person responsible for follow-up.

If legal counsel determines that INAI notification is not required for a
private-sector incident, record that decision, the legal basis, the approver,
and the evidence used.

## User Notification Template

Subject: Important notice about your WhatsApp data

We identified a security incident involving the Tulum Botox WhatsApp assistant
on [DATE]. The data potentially involved may include [DATA CATEGORIES].

What happened: [SHORT FACTUAL DESCRIPTION]

What we did: [CONTAINMENT AND CORRECTIVE ACTIONS]

What you can do: [RECOMMENDED STEPS]

For questions or ARCO/deletion requests, contact Ally@TulumBotox.com or
+52 984 105 0808.

## Technical Recovery Checklist

- Rotate Railway Variables:
  - WHATSAPP_TOKEN
  - META_APP_SECRET
  - VERIFY_TOKEN
  - ANTHROPIC_API_KEY
  - DATABASE_URL / DATABASE_PRIVATE_URL credentials
  - REDIS_URL credentials
  - INBOX_ENCRYPTION_KEY if exposed
  - INBOX_CSRF_SECRET
  - INBOX_PROOF_SECRET
  - FLASK_SECRET_KEY
- Rotate admin inbox password hashes.
- Revoke unused GitHub and Railway access.
- Review Railway project members and enforce MFA/2FA.
- Review Meta WhatsApp app users and tokens.
- Review Anthropic API key usage and revoke compromised keys.
- Pull a fresh Postgres backup after containment.
- If integrity is suspect, restore to staging from a pre-incident backup and
  compare before production restore.
- Confirm `/health` returns healthy after redeploy.
- Confirm webhook signature verification is active.
- Confirm `ALLOW_UNSIGNED_WEBHOOKS=false`.
- Confirm inbox encryption is required and configured.
- Confirm retention cleanup still runs after rotation.

## Evidence To Keep

Keep these records for counsel and regulator/user follow-up:

- incident timeline;
- screenshots or exports of Railway deployments, variables changed, and member
  access changes;
- list of rotated keys and rotation timestamps;
- affected database tables and row counts;
- affected message IDs or hashed sender IDs;
- user notification copy and send timestamps;
- INAI/regulator notification copy and submission receipt, if submitted;
- remediation PR/commit SHA;
- post-incident review notes.

## Post-Incident Review

Complete within 7 calendar days after containment:

- root cause;
- data categories and affected people;
- what controls worked;
- what controls failed;
- remediation owner and due dates;
- updates needed for Privacy Notice, Railway variables, tests, or monitoring;
- whether a tabletop drill is needed.

## Sources Used For This Playbook

- INAI guidance on personal-data security incidents and notifications.
- LFPDPPP breach-notification duties for affected data subjects.
- 2026 LFPDPPP compendium guidance on INAI communication for significant
  breaches.
- Railway Support docs for support channels.
- Anthropic Help Center for governmental/regulator contact routing.
