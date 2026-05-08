#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DATABASE_PRIVATE_URL:-}" ]]; then
  echo "DATABASE_PRIVATE_URL is not set" >&2
  exit 1
fi

mkdir -p /backups

timestamp=$(date -u +%Y%m%d-%H%M)
backup_path="/backups/tulum-btx-${timestamp}.dump"

pg_dump "$DATABASE_PRIVATE_URL" --format=custom --file="$backup_path"

echo "Backup written to $backup_path"
# Optional: upload to S3/GCS using your preferred CLI.
