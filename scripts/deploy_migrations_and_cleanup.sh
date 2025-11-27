#!/usr/bin/env bash
set -euo pipefail

# Deploy helper: backup + safe migration + optional concurrent index + cleanup ofertas antigas
# Usage:
#   export DATABASE_URL='postgresql://user:pass@host:5432/db'
#   ./scripts/deploy_migrations_and_cleanup.sh [--concurrent] [--cleanup-days 1] [--cleanup-pedidos-days 7]
#
# Notes:
# - Requires: psql, pg_dump, python3 (for cleanup script)
# - The migration runbook already creates a timestamped pg_dump backup

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
RUNBOOK="${ROOT_DIR}/migrations/run_migration_safe.sh"
CLEANUP_SCRIPT="${ROOT_DIR}/scripts/cleanup_old_ofertas.py"
CLEANUP_PEDIDOS_SCRIPT="${ROOT_DIR}/scripts/cleanup_old_pedidos_aprovados.py"

# Defaults
CONCURRENT_FLAG=""
CLEANUP_DAYS=1
PEDIDOS_DAYS=7

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --concurrent)
      CONCURRENT_FLAG="--concurrent"; shift ;;
    --cleanup-days)
      CLEANUP_DAYS="${2:-1}"; shift 2 ;;
    --cleanup-pedidos-days)
      PEDIDOS_DAYS="${2:-7}"; shift 2 ;;
    *) echo "Unknown argument: $1"; exit 2 ;;
  esac
done

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL environment variable not set." >&2
  exit 1
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "ERROR: psql not found in PATH." >&2
  exit 1
fi

if ! command -v pg_dump >/dev/null 2>&1; then
  echo "ERROR: pg_dump not found in PATH." >&2
  exit 1
fi

if [[ ! -x "${RUNBOOK}" ]]; then
  echo "INFO: making runbook executable" && chmod +x "${RUNBOOK}"
fi

echo "==> Running safe migration runbook (${CONCURRENT_FLAG:---no-concurrent})"
"${RUNBOOK}" ${CONCURRENT_FLAG}

echo "==> Running cleanup of old ofertas (older than ${CLEANUP_DAYS} day(s))"
CLEANUP_OLDER_THAN_DAYS="${CLEANUP_DAYS}" python3 "${CLEANUP_SCRIPT}"

echo "==> Running cleanup of approved pedidos (older than ${PEDIDOS_DAYS} day(s))"
CLEANUP_PEDIDOS_DAYS="${PEDIDOS_DAYS}" python3 "${CLEANUP_PEDIDOS_SCRIPT}"

echo "==> Deploy steps finished successfully."
