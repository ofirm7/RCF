#!/bin/bash
set -e

export PATH="/usr/lib/postgresql/17/bin:$PATH"

echo "=== RCF — Refund Claim Finder ==="
echo ""

# ---------------------------------------------------------------
# 1. Start PostgreSQL
# ---------------------------------------------------------------
echo "[1/5] Starting PostgreSQL ..."

# Ensure PGDATA directory exists with correct ownership
mkdir -p "$PGDATA"
chown postgres:postgres "$PGDATA"
touch /var/log/postgresql.log
chown postgres:postgres /var/log/postgresql.log

# Init DB if not already done
if [ ! -f "$PGDATA/PG_VERSION" ]; then
    su postgres -c "PATH=$PATH initdb -D $PGDATA --locale=C --encoding=UTF8"
fi

# Start postgres in background
su postgres -c "PATH=$PATH pg_ctl -D $PGDATA -l /var/log/postgresql.log start -w"

# Create user and database (ignore errors if they already exist)
su postgres -c "PATH=$PATH psql -c \"CREATE USER rcf WITH PASSWORD 'rcf';\"" 2>/dev/null || true
su postgres -c "PATH=$PATH psql -c \"CREATE DATABASE rcf OWNER rcf;\"" 2>/dev/null || true
su postgres -c "PATH=$PATH psql -c \"GRANT ALL PRIVILEGES ON DATABASE rcf TO rcf;\"" 2>/dev/null || true

echo "    PostgreSQL ready."

# ---------------------------------------------------------------
# 2. Run migrations
# ---------------------------------------------------------------
echo "[2/5] Running database migrations ..."
PGPASSWORD=rcf psql -h localhost -U rcf -d rcf -f /app/supabase/migrations/001_initial_schema.sql 2>/dev/null || true
echo "    Schema ready."

# ---------------------------------------------------------------
# 3. Seed sample addresses
# ---------------------------------------------------------------
echo "[3/5] Seeding sample addresses ..."
python /app/scripts/seed_addresses.py
echo ""

# ---------------------------------------------------------------
# 4. Run scanner (if ANTHROPIC_API_KEY is set)
# ---------------------------------------------------------------
if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "[4/5] Running scanner ..."
    SCAN_CITY="${SCAN_CITY:-}"
    SCAN_LIMIT="${SCAN_LIMIT:-10}"

    CMD="python /app/scripts/run_scanner.py --limit $SCAN_LIMIT"
    if [ -n "$SCAN_CITY" ]; then
        CMD="$CMD --city \"$SCAN_CITY\""
    fi
    eval $CMD || echo "    Scanner finished (some errors may have occurred — check logs)."
    echo ""
else
    echo "[4/5] Skipping scanner (ANTHROPIC_API_KEY not set)"
    echo "    Set ANTHROPIC_API_KEY to enable scanning."
    echo ""
fi

# ---------------------------------------------------------------
# 5. Start API server
# ---------------------------------------------------------------
echo "[5/5] Starting API server on port 8000 ..."
echo ""
echo "  API:     http://localhost:8000"
echo "  Health:  http://localhost:8000/health"
echo "  Docs:    http://localhost:8000/docs"
echo ""

exec uvicorn rcf.api.app:app --host 0.0.0.0 --port 8000
