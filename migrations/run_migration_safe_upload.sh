#!/usr/bin/env bash
set -euo pipefail

# Wrapper: runs safe migration and uploads the created backup to S3
# Usage:
#   export DATABASE_URL='postgresql://user:pass@host:port/db'
#   export S3_BUCKET='my-bucket/backups'
#   export AWS_PROFILE=... (or AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY/AWS_DEFAULT_REGION)
#   ./migrations/run_migration_safe_upload.sh [--keep-local]

KEEP_LOCAL=false
if [[ "${1:-}" == "--keep-local" ]]; then
  KEEP_LOCAL=true
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL not set. Export it first." >&2
  exit 1
fi

if [[ -z "${S3_BUCKET:-}" ]]; then
  echo "ERROR: S3_BUCKET not set. Export e.g. S3_BUCKET='my-bucket/path'" >&2
  exit 1
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "ERROR: aws cli not found in PATH. Install and configure AWS CLI to upload backups." >&2
  exit 1
fi

REPO_DIR="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$REPO_DIR"

echo "[run_migration_safe_upload] Starting — repo: $REPO_DIR"

echo "[run_migration_safe_upload] Running migration script (this will create a local backup)..."
./migrations/run_migration_safe.sh

echo "[run_migration_safe_upload] Searching latest backup file..."
LATEST_BACKUP=$(ls -1t backup_before_migration_*.dump 2>/dev/null | head -n 1 || true)

if [[ -z "$LATEST_BACKUP" ]]; then
  echo "ERROR: couldn't find a generated backup file (pattern: backup_before_migration_*.dump)" >&2
  exit 1
fi

DEST_KEY="${S3_BUCKET%/}/$(basename "$LATEST_BACKUP")"
S3_URI="s3://$DEST_KEY"

echo "[run_migration_safe_upload] Uploading $LATEST_BACKUP -> s3://$DEST_KEY"
aws s3 cp "$LATEST_BACKUP" "$S3_URI"

if [[ $? -ne 0 ]]; then
  echo "ERROR: AWS upload failed." >&2
  exit 1
fi

echo "[run_migration_safe_upload] Upload successful: $S3_URI"

if [[ "$KEEP_LOCAL" == "false" ]]; then
  echo "[run_migration_safe_upload] Removing local backup $LATEST_BACKUP"
  rm -f "$LATEST_BACKUP"
fi

echo "[run_migration_safe_upload] Done. If you want to keep local copy, re-run with --keep-local"
