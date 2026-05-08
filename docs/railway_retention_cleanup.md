# Railway Retention Cleanup

The inbox retention policy is enforced by a dedicated Railway scheduled
service. This keeps cleanup out of the webhook hot path and creates an audit
record every time the cleanup runs.

## Service

Create a second Railway service from the same GitHub repository:

```text
Service name: inbox-retention-cleanup
Config file path: /railway.cleanup.toml
```

The config file sets:

```toml
[deploy]
startCommand = "python -m scripts.cleanup_inbox"
cronSchedule = "0 9 * * *"
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

Railway evaluates cron schedules in UTC. `0 9 * * *` runs once per day at
09:00 UTC. The cleanup command exits after one run, which is required for
Railway cron services.

## Variables

Set these variables on the `inbox-retention-cleanup` service:

```text
DATABASE_URL=${{Postgres.DATABASE_URL}}
INBOX_RETENTION_DAYS=30
INBOX_AUTO_MIGRATE=true
```

Use the same Postgres service reference and retention value as the web service.
If production uses a restricted DB user and migrations have already run, set
`INBOX_AUTO_MIGRATE=false`.

## Evidence

Each successful run:

- deletes expired `inbox_messages`;
- deletes older `inbox_audit_events` and `inbox_opt_in_proofs`;
- writes a new `inbox_audit_events` record with:
  - `actor = system:retention-cleanup`;
  - `actor_role = system`;
  - `action = retention_cleanup`;
  - `metadata.deleted_messages`;
  - `metadata.retention_days`.

This audit row is the operational proof that retention cleanup actually ran.
