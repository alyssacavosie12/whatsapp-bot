# Online Checks

These tests verify that the deployed Railway service and live provider
credentials work together. They are opt-in and are skipped during normal CI.

## Setup

```bash
cp .env.online.example .env.online
```

Fill `.env.online` with real Railway/Meta/Anthropic values. The file is
git-ignored; do not commit it.

Required for the core online checks:

```text
RUN_ONLINE_CHECKS=true
PUBLIC_BASE_URL=https://<your-railway-domain>
WHATSAPP_TOKEN=...
WHATSAPP_PHONE_NUMBER_ID=...
GRAPH_API_VERSION=v23.0
VERIFY_TOKEN=...
META_APP_SECRET=...
ANTHROPIC_API_KEY=...
DATABASE_URL=...
FLASK_SECRET_KEY=...
INBOX_ENCRYPTION_KEY=...
INBOX_CSRF_SECRET=...
INBOX_PROOF_SECRET=...
ALLOW_UNSIGNED_WEBHOOKS=false
LOG_INCOMING_MESSAGES=false
INBOX_REQUIRE_ENCRYPTION=true
```

## Run

```bash
ONLINE_CHECKS_ENV_FILE=.env.online .venv/bin/python -m pytest -m online
```

Or run only the online file:

```bash
ONLINE_CHECKS_ENV_FILE=.env.online .venv/bin/python -m pytest tests/test_online_checks.py
```

## What The Core Checks Do

- GET `/health` on the public Railway domain.
- GET `/privacy`.
- GET `/webhook` with `VERIFY_TOKEN`.
- POST `/webhook` without a signature and expect `401`.
- POST `/webhook` with a signed status-only payload and expect `200`.
- Read WhatsApp phone-number metadata from Meta Graph API.
- List Anthropic models to verify the API key.

The signed webhook payload contains only a fake status event. It does not send
a customer message and should not trigger an outbound WhatsApp reply.

## Optional Checks

Enable only when the network path is reachable from the test runner:

```text
ONLINE_CHECK_DATABASE=true
ONLINE_DATABASE_SSLMODE=require
ONLINE_CHECK_REDIS=true
ONLINE_CHECK_ADMIN=true
ONLINE_INBOX_USERNAME=<real admin or viewer username>
ONLINE_INBOX_PASSWORD=<real password, not the hash>
```

Railway private Postgres/Redis URLs usually work only from inside Railway's
private network. If running these tests locally, use a safe temporary public
connection or run the tests from a Railway job/service attached to the same
project environment.

## Safety Rules

- Never commit `.env.online`.
- Never paste real tokens into GitHub issues, PRs, screenshots, or chat.
- Keep `ALLOW_UNSIGNED_WEBHOOKS=false`.
- Keep `LOG_INCOMING_MESSAGES=false`.
- Rotate credentials after sharing temporary access with a contractor.
