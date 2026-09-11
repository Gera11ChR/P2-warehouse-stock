#!/usr/bin/env bash
set -euo pipefail

PGBIN="${PGBIN:-/usr/lib/postgresql/18/bin}"
DATA_DIR="${P2_PGDATA:-/tmp/opencode/p2-pg}"
PORT="${P2_PGPORT:-5432}"
SOCKET_DIR="/tmp/opencode"

if [ ! -d "$DATA_DIR" ]; then
  "$PGBIN/initdb" -D "$DATA_DIR" -U p2admin --auth=trust --encoding=UTF8 >/dev/null
fi

if ! "$PGBIN/pg_ctl" -D "$DATA_DIR" status >/dev/null 2>&1; then
  "$PGBIN/pg_ctl" -D "$DATA_DIR" -o "-p $PORT -k $SOCKET_DIR" -l "$SOCKET_DIR/p2-pg.log" start >/dev/null
fi

"$PGBIN/createdb" -h "$SOCKET_DIR" -p "$PORT" -U p2admin p2 >/dev/null 2>&1 || true
echo "PostgreSQL dev cluster ready on port $PORT (db: p2)"
