#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Dump PostgreSQL schema to a SQL file.

Usage:
  ./dump_schema.sh [--output stephanos_schema.sql] [--db-name stephanos] [--host raksasa] [--port 5432] [--user stephanos] [--ssh-host raksasa]

Connection defaults (if flags omitted):
  DB_NAME/PGDATABASE (default: stephanos)
  DB_HOST/PGHOST
  DB_PORT/PGPORT (default: 5432)
  DB_USER/PGUSER (default: stephanos)

Notes:
  - Uses ~/.pgpass (or libpq env vars) for password auth.
  - Auto-discovers pg_dump in PATH and common macOS Postgres install locations.
  - If local pg_dump server-version mismatch is detected, it can fallback to `ssh <host> pg_dump ...`.
EOF
}

find_pg_dump() {
  if command -v pg_dump >/dev/null 2>&1; then
    command -v pg_dump
    return 0
  fi

  # Common macOS install locations when pg tools are not on PATH.
  local candidates=(
    "/Applications/Postgres.app/Contents/Versions/latest/bin/pg_dump"
    "/Applications/Postgres/Contents/Versions/latest/bin/pg_dump"
    "/Applications/Postgres/bin/pg_dump"
  )

  local path
  for path in "${candidates[@]}"; do
    if [[ -x "$path" ]]; then
      echo "$path"
      return 0
    fi
  done

  shopt -s nullglob
  for path in /Applications/Postgres.app/Contents/Versions/*/bin/pg_dump /Applications/Postgres/Contents/Versions/*/bin/pg_dump /Applications/Postgres/*/bin/pg_dump; do
    if [[ -x "$path" ]]; then
      echo "$path"
      return 0
    fi
  done
  shopt -u nullglob

  return 1
}

output_file="stephanos_schema.sql"
db_name="${DB_NAME:-${PGDATABASE:-stephanos}}"
db_host="${DB_HOST:-${PGHOST:-}}"
db_port="${DB_PORT:-${PGPORT:-5432}}"
db_user="${DB_USER:-${PGUSER:-stephanos}}"
ssh_host=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      output_file="$2"
      shift 2
      ;;
    --db-name)
      db_name="$2"
      shift 2
      ;;
    --host)
      db_host="$2"
      shift 2
      ;;
    --port)
      db_port="$2"
      shift 2
      ;;
    --user)
      db_user="$2"
      shift 2
      ;;
    --ssh-host)
      ssh_host="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

pg_dump_bin="$(find_pg_dump || true)"
if [[ -z "$pg_dump_bin" ]]; then
  echo "Could not find pg_dump in PATH or /Applications/Postgres*." >&2
  echo "Install PostgreSQL tools or add them to PATH." >&2
  exit 1
fi

cmd=("$pg_dump_bin" "--schema-only" "--no-owner" "--no-privileges")
if [[ -n "$db_host" ]]; then
  cmd+=("-h" "$db_host")
fi
if [[ -n "$db_port" ]]; then
  cmd+=("-p" "$db_port")
fi
if [[ -n "$db_user" ]]; then
  cmd+=("-U" "$db_user")
fi
cmd+=("$db_name")

err_file="$(mktemp)"
trap 'rm -f "$err_file"' EXIT

if "${cmd[@]}" > "$output_file" 2>"$err_file"; then
  echo "Schema dump written to: $output_file"
  echo "pg_dump binary: $pg_dump_bin"
  exit 0
fi

if rg -q "server version mismatch" "$err_file"; then
  fallback_host="$ssh_host"
  if [[ -z "$fallback_host" ]]; then
    fallback_host="$db_host"
  fi

  if [[ -n "$fallback_host" ]]; then
    remote_cmd=(pg_dump --schema-only --no-owner --no-privileges)
    if [[ -n "$db_user" ]]; then
      remote_cmd+=(-U "$db_user")
    fi
    remote_cmd+=("$db_name")

    remote_cmd_escaped="$(printf '%q ' "${remote_cmd[@]}")"
    ssh "$fallback_host" "$remote_cmd_escaped" > "$output_file"
    echo "Schema dump written to: $output_file"
    echo "pg_dump fallback: ssh $fallback_host (remote pg_dump)"
    exit 0
  fi
fi

cat "$err_file" >&2
exit 1
