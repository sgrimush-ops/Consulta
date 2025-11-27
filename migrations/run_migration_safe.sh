#!/usr/bin/env bash
set -euo pipefail

# Runbook script for safe migration: migrations/001_safe_add_columns.sql
# Usage: export DATABASE_URL='postgresql://user:pass@host:port/db' && ./run_migration_safe.sh
# This script will:
#  - verify env / tools
#  - create a pg_dump backup file (timestamped)
#  - run the safe migration SQL
#  - run basic validations (column existence and non-empty counts)
#  - optionally create a CONCURRENTLY index (if you pass --concurrent)

MIGRATION_FILE="migrations/001_safe_add_columns.sql"
ROLLBACK_FILE="migrations/001_safe_add_columns_rollback.sql"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL environment variable not set. Export it and re-run."
  exit 1
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "ERROR: psql not found in PATH. Install the PostgreSQL client utilities."
  exit 1
fi

if ! command -v pg_dump >/dev/null 2>&1; then
  echo "ERROR: pg_dump not found in PATH. Install the PostgreSQL client utilities."
  exit 1
fi

echo "Using DATABASE_URL: ${DATABASE_URL}"

timestamp() { date +%Y%m%d_%H%M%S; }
BACKUP_FILE="backup_before_migration_$(timestamp).dump"

echo "Creating backup into ${BACKUP_FILE} (may take a while)..."
pg_dump --format=custom --file="${BACKUP_FILE}" "${DATABASE_URL}"
echo "Backup finished."

echo "Running safe migration: ${MIGRATION_FILE}"
psql "${DATABASE_URL}" -f "${MIGRATION_FILE}"
echo "Migration finished."

echo "Running validations..."
echo "Checking mix_produtos columns and non-null counts..."
psql "${DATABASE_URL}" -c "SELECT column_name FROM information_schema.columns WHERE table_name='mix_produtos' AND column_name IN ('codigo_interno','descricao','codigo_ean');"
psql "${DATABASE_URL}" -c "SELECT COUNT(*) AS total, COUNT(codigo_interno) AS codigo_interno_count FROM mix_produtos;"

echo "Checking ofertas columns and non-null counts..."
psql "${DATABASE_URL}" -c "SELECT column_name FROM information_schema.columns WHERE table_name='ofertas' AND column_name IN ('codigo_interno','descricao');"
psql "${DATABASE_URL}" -c "SELECT COUNT(*) AS total, COUNT(codigo_interno) AS codigo_interno_count FROM ofertas;"

echo "Checking pedidos_consolidados columns and non-null counts..."
psql "${DATABASE_URL}" -c "SELECT column_name FROM information_schema.columns WHERE table_name='pedidos_consolidados' AND column_name IN ('codigo_interno','descricao','codigo_ean');"
psql "${DATABASE_URL}" -c "SELECT COUNT(*) AS total, COUNT(codigo_interno) AS codigo_interno_count FROM pedidos_consolidados;"

if [[ "${1:-}" == "--concurrent" || "${2:-}" == "--concurrent" ]]; then
  echo "User requested CONCURRENT index creation — creating index concurrently (note: must be run outside long transactions)"
  echo "Creating unique index CONCURRENTLY on ofertas(codigo_interno, data_inicio, data_final)"
  # As per PostgreSQL behavior, CREATE INDEX CONCURRENTLY cannot run inside a transaction; this command will run standalone
  psql "${DATABASE_URL}" -c "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uniq_ofertas_cod_period ON ofertas (codigo_interno, data_inicio, data_final);"
  echo "CONCURRENT index creation requested finished."
else
  echo "Skipping CONCURRENT index creation. To create non-blocking index, re-run with --concurrent"
fi

echo "All done. If you need to rollback, run: psql \"$DATABASE_URL\" -f ${ROLLBACK_FILE}"
