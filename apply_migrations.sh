#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Apply post-baseline schema migrations.

Usage:
  ./apply_migrations.sh [--bootstrap] [--host raksasa] [--port 5432] [--user stephanos] [--db-name stephanos]

Flags:
  --bootstrap   Apply schema/base_schema.sql before post-baseline migrations.

Connection defaults:
  DB_HOST/PGHOST
  DB_PORT/PGPORT (default: 5432)
  DB_USER/PGUSER (default: stephanos)
  DB_NAME/PGDATABASE (default: stephanos)
EOF
}

find_psql() {
  if command -v psql >/dev/null 2>&1; then
    command -v psql
    return 0
  fi

  local candidates=(
    "/Applications/Postgres.app/Contents/Versions/latest/bin/psql"
    "/Applications/Postgres/Contents/Versions/latest/bin/psql"
    "/Applications/Postgres/bin/psql"
  )
  local path
  for path in "${candidates[@]}"; do
    if [[ -x "$path" ]]; then
      echo "$path"
      return 0
    fi
  done

  shopt -s nullglob
  for path in /Applications/Postgres.app/Contents/Versions/*/bin/psql /Applications/Postgres/Contents/Versions/*/bin/psql /Applications/Postgres/*/bin/psql; do
    if [[ -x "$path" ]]; then
      echo "$path"
      return 0
    fi
  done
  shopt -u nullglob
  return 1
}

run_sql_file() {
  local sql_file="$1"
  local psql_bin="$2"
  shift 2
  local conn_args=("$@")

  echo "Applying: $sql_file"
  "$psql_bin" -v ON_ERROR_STOP=1 "${conn_args[@]}" -f "$sql_file"
}

bootstrap=0
db_host="${DB_HOST:-${PGHOST:-}}"
db_port="${DB_PORT:-${PGPORT:-5432}}"
db_user="${DB_USER:-${PGUSER:-stephanos}}"
db_name="${DB_NAME:-${PGDATABASE:-stephanos}}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bootstrap)
      bootstrap=1
      shift
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
    --db-name)
      db_name="$2"
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

psql_bin="$(find_psql || true)"
if [[ -z "$psql_bin" ]]; then
  echo "Could not find psql in PATH or /Applications/Postgres*." >&2
  exit 1
fi

conn_args=()
if [[ -n "$db_host" ]]; then
  conn_args+=("-h" "$db_host")
fi
if [[ -n "$db_port" ]]; then
  conn_args+=("-p" "$db_port")
fi
if [[ -n "$db_user" ]]; then
  conn_args+=("-U" "$db_user")
fi
conn_args+=("-d" "$db_name")

if [[ "$bootstrap" -eq 1 ]]; then
  run_sql_file "schema/base_schema.sql" "$psql_bin" "${conn_args[@]}"
fi

shopt -s nullglob
migration_files=(migrations/*.sql)
shopt -u nullglob

if [[ "${#migration_files[@]}" -eq 0 ]]; then
  echo "No post-baseline migrations found in migrations/."
  exit 0
fi

IFS=$'\n' migration_files_sorted=($(printf '%s\n' "${migration_files[@]}" | sort))
unset IFS

for migration_file in "${migration_files_sorted[@]}"; do
  run_sql_file "$migration_file" "$psql_bin" "${conn_args[@]}"
done

echo "Migration apply complete."
