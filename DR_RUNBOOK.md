# Disaster Recovery Runbook

Owner: TBD
Last tested: TBD

## 1. Targets (define first)

- RTO target: TBD minutes
- RPO target: TBD minutes

These targets drive backup frequency and the restore path below.

## 2. Critical data sources

- PostgreSQL (inbox messages, opt-out, audit)
- Redis (rate limit, dedup) is cache only; loss is acceptable
- Code and config live in GitHub + Railway Variables

## 3. PostgreSQL backups

1) Railway managed backups
- Paid plans: enable backups in the Postgres service and verify they exist.
- Hobby plan: no backups, use external dumps.

2) External pg_dump to S3/GCS
- Use Railway Cron or a dedicated service.
- Example script: scripts/backup_postgres.sh

## 4. Restore testing (staging)

- Create a staging Postgres database.
- Restore from the latest dump:
  pg_restore --clean --no-owner --no-privileges --dbname "$DATABASE_PRIVATE_URL" /path/to/dump
- Run migrations:
  alembic upgrade head
- Smoke test:
  curl --fail https://<staging-domain>/health
  Send one test webhook payload and confirm a reply.

## 5. Redis policy

- Treat Redis as cache; no backup required for this bot.
- If you need higher durability, enable RDB + AOF and export snapshots to S3/GCS.

## 6. What not to back up

- Container filesystem (Railway deploys from GitHub)
- Railway logs

## 7. DR scenarios

A) Railway or region outage
- Update status page and reply template.
- If outage is long, deploy the same app to another region/cloud.

B) Data corruption or accidental drop
- Stop deploys.
- Pick a restore point based on RPO.
- Restore Postgres from backup and run migrations.
- Run smoke tests.

C) Credential compromise
- Rotate API keys in Railway Variables (WhatsApp, Anthropic).
- Consider restoring from a pre-incident backup.
- Notify the owner if required.
- If personal data may be affected, follow docs/breach_response.md.

## 8. Regular DR tests

- Every 1-3 months:
  - Restore latest backup into staging.
  - Run migrations and smoke tests.
  - Record date, duration (RTO), and any issues.
