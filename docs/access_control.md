# Access Control Procedure

Last reviewed: 2026-05-08

This procedure covers access to the Tulum Botox WhatsApp bot, Railway project,
Railway Variables, PostgreSQL, Redis, GitHub repository, Meta/WhatsApp Business
assets, Anthropic API, and the `/admin/messages` inbox.

## Access Principles

- Use named personal accounts only. No shared Railway, GitHub, Meta, or
  Anthropic accounts.
- Grant least privilege for the shortest practical time.
- Require MFA/2FA wherever the platform supports it.
- Never send secrets in chat, email, screenshots, tickets, or freelance
  delivery notes.
- Store production secrets only in Railway Variables. Seal every variable that
  contains a token, password, connection string, hash, or encryption key.
- Production access must have an owner, reason, approval date, and removal
  date.
- Contractor/freelancer access expires when the delivery is accepted unless a
  new written approval extends it.

## Role Matrix

| Surface | Normal Role | Who Should Have It | Notes |
| --- | --- | --- | --- |
| Railway project Owner | Owner | Clinic/business owner only | Full administration and billing impact. |
| Railway project Editor | Editor | Active technical maintainer only | Can deploy and change settings. Time-limit this for contractors. |
| Railway project Viewer | Viewer | Client stakeholder if needed | Read-only; Railway viewers cannot see environment variables. |
| Railway workspace admin | Admin | Business owner or trusted ops lead | Needed for workspace security and 2FA enforcement. |
| Railway production environment | Restricted access where available | Owner/admin only | Use Environment RBAC on Enterprise when available. |
| GitHub repository admin | Admin | Repo owner only | Can change branch protection and secrets. |
| GitHub repository maintainer/write | Maintainer/write | Active developer only | Remove after delivery. |
| Meta Business / WhatsApp app | Admin/developer as needed | Business owner and current maintainer | Remove stale app users and system users. |
| Anthropic Console/API | Owner/admin | Business owner or technical owner | Rotate API keys after maintainer changes if exposed. |
| Admin inbox `/admin/messages` | `admin` | Business owner or authorized clinic lead | Can view and soft-delete messages. |
| Admin inbox `/admin/messages` | `viewer` | Authorized client staff | View-only. Use separate username/hash. |
| PostgreSQL direct DB access | Break-glass only | Technical owner | Prefer app role and admin inbox over direct DB access. |

## Onboarding

1. Record the request:
   - person's name and email;
   - organization;
   - access purpose;
   - requested systems;
   - role requested;
   - approver;
   - planned removal date.
2. Confirm MFA/2FA is enabled before granting access.
3. Grant the minimum role:
   - Railway: prefer `Viewer` unless the person must deploy or configure;
   - GitHub: prefer read access unless the person must push code;
   - Admin inbox: prefer `viewer` unless deletion/audit actions are required.
4. For Railway, verify project visibility remains private.
5. For secrets, use Railway Variables and sealed variables. Do not reveal
   existing values to the new user.
6. For contractors, add a calendar reminder for removal on the delivery date.
7. Record the completed grant in the access review log template below.

## Monthly Access Review

Run this review monthly, and immediately after any contractor handoff,
employment change, or suspected incident.

### Railway

1. Open Railway project `Settings -> Members`.
2. Confirm every member is expected and has the minimum role.
3. Remove unknown, inactive, or completed-contractor accounts.
4. Confirm project visibility is private.
5. Open workspace `People` settings:
   - confirm only expected workspace members remain;
   - enable `Require 2FA` if the plan supports 2FA enforcement;
   - confirm admins are still appropriate.
6. Review the project Activity feed for unexpected variable, deployment,
   member, service, or domain changes.
7. Confirm production variables containing secrets are sealed.
8. Confirm service variables use private references where possible:
   - `DATABASE_URL=${{Postgres.DATABASE_URL}}`;
   - `REDIS_URL=${{Redis.REDIS_URL}}`;
   - `RATE_LIMIT_STORAGE_URL=${{Redis.REDIS_URL}}`.

### GitHub

1. Review repository collaborators, teams, deploy keys, GitHub Apps, and
   Actions secrets.
2. Remove stale contractors and unused integrations.
3. Confirm branch protection or required PR checks are still active.
4. Confirm no secrets were committed.

### Meta / WhatsApp

1. Review Business Manager users, partners, system users, app roles, and token
   owners.
2. Remove stale users and unused tokens.
3. Confirm WhatsApp Business 2FA/PIN remains enabled.
4. Confirm webhook URL and verify token are expected.

### Anthropic

1. Review API keys and users in the Anthropic Console.
2. Revoke unused keys.
3. Rotate `ANTHROPIC_API_KEY` if a maintainer with secret access leaves.

### Admin Inbox

1. Confirm `INBOX_ADMIN_USERNAME` belongs to the current authorized owner/admin.
2. Confirm `INBOX_VIEWER_USERNAME` belongs to the current client viewer, if
   used.
3. Rotate password hashes after role changes.
4. Confirm `INBOX_REQUIRE_ENCRYPTION=true`.
5. Confirm `INBOX_ENCRYPTION_KEY`, `INBOX_CSRF_SECRET`, and
   `INBOX_PROOF_SECRET` are sealed.

### PostgreSQL / Redis

1. Confirm app uses private service references where possible.
2. Confirm public TCP access is disabled unless explicitly needed.
3. Confirm restricted DB user is used when `INBOX_AUTO_MIGRATE=false`.
4. Rotate DB/Redis credentials if someone with secret access leaves.

## Freelancer Offboarding

When freelance delivery is accepted:

1. Remove the freelancer from Railway project members and workspace members.
2. Remove the freelancer from GitHub repo/team access.
3. Remove the freelancer from Meta Business, WhatsApp app, and any test phone
   access if granted.
4. Remove or downgrade admin inbox access.
5. Revoke any personal API keys or tokens created for the freelancer.
6. Rotate secrets if the freelancer could view or export them:
   - `WHATSAPP_TOKEN`;
   - `META_APP_SECRET`;
   - `VERIFY_TOKEN`;
   - `ANTHROPIC_API_KEY`;
   - `DATABASE_URL` / `DATABASE_PRIVATE_URL`;
   - `REDIS_URL`;
   - `INBOX_ADMIN_PASSWORD_HASH`;
   - `INBOX_VIEWER_PASSWORD_HASH`;
   - `INBOX_CSRF_SECRET`;
   - `INBOX_PROOF_SECRET`;
   - `FLASK_SECRET_KEY`;
   - `INBOX_ENCRYPTION_KEY` only if it was exposed or copied.
7. Redeploy after secret rotation.
8. Run smoke checks:
   - `/health`;
   - webhook verification;
   - one inbound test message;
   - admin inbox login with the remaining authorized user.
9. Record offboarding in the access review log.

## Emergency Access

Emergency access is allowed only to restore service or contain an incident.

1. Approver grants temporary access with a clear expiry time.
2. Use the minimum role that can fix the issue.
3. Record all actions in the incident log.
4. Remove access immediately after resolution.
5. Rotate exposed credentials and update `docs/breach_response.md` if personal
   data may have been affected.

## Access Review Log Template

Copy this block into an internal ticket, document, or issue for every review.

```text
Review date:
Reviewer:
Reason: monthly / contractor offboarding / incident / other

Railway members reviewed: yes/no
Railway 2FA enforcement checked: yes/no
Railway project visibility private: yes/no
Railway sealed variables checked: yes/no
Railway activity feed reviewed: yes/no

GitHub collaborators/integrations reviewed: yes/no
Meta/WhatsApp users and tokens reviewed: yes/no
Anthropic users and API keys reviewed: yes/no
Admin inbox users reviewed: yes/no
Postgres/Redis access reviewed: yes/no

Removed users:
Changed roles:
Rotated secrets:
Follow-up tasks:
Approver:
```

## Sources Used For This Procedure

- Railway Project Members docs: Owner, Editor, Viewer scopes.
- Railway Two-Factor Authentication Enforcement docs.
- Railway Environment RBAC docs for restricted production environments on
  Enterprise.
