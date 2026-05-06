#!/usr/bin/env bash
# Daily Postgres backup — pipes pg_dump → gzip → optional S3/Backblaze.
#
# Add to crontab (VPS):
#   0 2 * * * /opt/pod-bot/scripts/backup.sh >> /var/log/podbot-backup.log 2>&1
#
# Required env (export from /etc/podbot/backup.env):
#   POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT,
#   POSTGRES_DB
# Optional env:
#   BACKUP_DIR        — local dir to keep backups (default /var/backups/podbot)
#   BACKUP_RETENTION  — days to keep locally (default 14)
#   S3_BUCKET         — bucket name (default empty = no upload)
#   S3_ENDPOINT       — for S3-compatible providers (Backblaze B2 etc.)
#   AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY — credentials for `aws s3`

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/podbot}"
BACKUP_RETENTION="${BACKUP_RETENTION:-14}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
DUMPFILE="$BACKUP_DIR/podbot-$TIMESTAMP.sql.gz"

mkdir -p "$BACKUP_DIR"

PGPASSWORD="${POSTGRES_PASSWORD:?missing POSTGRES_PASSWORD}" pg_dump \
  --host="${POSTGRES_HOST:-localhost}" \
  --port="${POSTGRES_PORT:-5432}" \
  --username="${POSTGRES_USER:?missing POSTGRES_USER}" \
  --no-owner --no-privileges --format=plain \
  "${POSTGRES_DB:?missing POSTGRES_DB}" \
  | gzip -9 > "$DUMPFILE"

echo "[$(date -Is)] Wrote local backup: $DUMPFILE ($(du -h "$DUMPFILE" | cut -f1))"

# --- Upload to S3-compatible store ------------------------------------------
if [[ -n "${S3_BUCKET:-}" ]]; then
  ARGS=()
  if [[ -n "${S3_ENDPOINT:-}" ]]; then
    ARGS+=("--endpoint-url" "$S3_ENDPOINT")
  fi
  aws s3 cp "$DUMPFILE" "s3://$S3_BUCKET/podbot/$(basename "$DUMPFILE")" "${ARGS[@]}"
  echo "[$(date -Is)] Uploaded to s3://$S3_BUCKET/podbot/"
fi

# --- Local retention --------------------------------------------------------
find "$BACKUP_DIR" -name 'podbot-*.sql.gz' -mtime "+$BACKUP_RETENTION" -delete
echo "[$(date -Is)] Trimmed backups older than $BACKUP_RETENTION days"
