# Railway Admin Inbox Setup

This project can store incoming WhatsApp webhook messages in Railway
PostgreSQL and expose them at `/admin/messages`.

## 1. Add PostgreSQL

In Railway, add a PostgreSQL database to the same project and environment as
the bot. Railway exposes database variables such as `DATABASE_URL`.

Set the bot service variable:

```text
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

If the Postgres service has a different name, use that service name instead of
`Postgres`.

## 2. Configure admin access

Generate password hashes locally:

```bash
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('replace-this-password'))"
```

Set these variables on the bot service:

```text
INBOX_ADMIN_USERNAME=owner
INBOX_ADMIN_PASSWORD_HASH=<generated hash>
INBOX_VIEWER_USERNAME=client
INBOX_VIEWER_PASSWORD_HASH=<generated hash>
INBOX_CSRF_SECRET=<long random secret>
INBOX_PROOF_SECRET=<different long random secret>
INBOX_RETENTION_DAYS=30
INBOX_AUTH_MAX_FAILED_ATTEMPTS=5
INBOX_AUTH_WINDOW_SECONDS=900
INBOX_REQUIRE_ENCRYPTION=true
INBOX_AUTO_MIGRATE=true
BOT_DISCLOSURE=true
ALLOW_UNSIGNED_WEBHOOKS=false
LOG_INCOMING_MESSAGES=false
FLASK_SECRET_KEY=<long random secret>
WEBHOOK_RATE_LIMIT=300 per minute
FORCE_HTTPS=false
```

The `admin` user can view and soft-delete messages. The `viewer` user can only
view messages.

## 3. Required app-level encryption

Generate a Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set:

```text
INBOX_ENCRYPTION_KEY=<generated key>
```

Keep this key sealed/secret. Existing encrypted messages cannot be read if the
key is lost or changed. The inbox refuses to store or display messages when
`INBOX_REQUIRE_ENCRYPTION=true` and this key is missing. Message text, sender
phone, sender name, and inbound opt-in evidence are encrypted before storage.

## 4. Redis for production rate limits

Add a Railway Redis service for shared rate limiting and deduplication across
multiple app instances. Set the bot service variable to the Redis private URL:

```text
REDIS_URL=${{Redis.REDIS_URL}}
RATE_LIMIT_STORAGE_URL=${{Redis.REDIS_URL}}
```

If your Redis service has a different name, use that service name instead of
`Redis`.

## 5. Deploy

Redeploy the bot after adding variables. The app creates the inbox tables at
runtime on the first message or admin page load.

Visit:

```text
https://<your-railway-domain>/admin/messages
```

## 6. Strict database role option

By default, `INBOX_AUTO_MIGRATE=true` lets the app create and update inbox
tables at runtime. For stricter production least privilege:

1. Run `migrations/001_inbox.sql` once using the Postgres owner credentials.
2. Create a restricted DB user with only `SELECT`, `INSERT`, `UPDATE`, and
   `DELETE` on the inbox tables.
3. Change the bot's `DATABASE_URL` to that restricted user.
4. Set `INBOX_AUTO_MIGRATE=false`.

Keep `INBOX_AUTO_MIGRATE=true` until the migration has been run.

## 7. Security checklist

- Keep `LOG_INCOMING_MESSAGES=false` for production.
- Keep `ALLOW_UNSIGNED_WEBHOOKS=false` for production.
- Keep `BOT_DISCLOSURE=true` so AI fallback replies disclose automation.
- Keep `FORCE_HTTPS=false` until the Railway domain is confirmed to pass the
  correct `X-Forwarded-Proto` header, then switch it to `true`.
- Seal Railway variables that contain passwords, hashes, CSRF secrets, and
  encryption keys.
- Limit Railway project access to people who need operational access.
- Disable external TCP access to Postgres if the project does not need it.
- Prefer Railway private service references for Postgres and Redis.
- Keep a documented retention value in `INBOX_RETENTION_DAYS`.
- Configure database backups and monitoring for production use.
