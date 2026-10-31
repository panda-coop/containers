#!/usr/bin/env bash
# Entrypoint with the environment contract of the Red Hat / sclorg PostgreSQL images, written from
# their documentation:
#   POSTGRESQL_USER, POSTGRESQL_PASSWORD, POSTGRESQL_DATABASE   all three, or none
#   POSTGRESQL_ADMIN_PASSWORD                                   optional password for postgres
#   at least the trio or POSTGRESQL_ADMIN_PASSWORD must be set
#   POSTGRESQL_MAX_CONNECTIONS, POSTGRESQL_MAX_PREPARED_TRANSACTIONS, POSTGRESQL_SHARED_BUFFERS,
#   POSTGRESQL_EFFECTIVE_CACHE_SIZE                             written to an included file on every start
# An empty PGDATA is initialised; one holding PG_VERSION is kept. On every start the app user and
# database are created if missing and the passwords set from the environment, as sclorg resets
# them. Our addition: /docker-entrypoint-initdb.d/* runs on the first init only. Started as root
# (--user 0), it fixes ownership and re-executes itself as postgres.
# -u is left off: sourced init scripts run in this shell.
set -Eeo pipefail

INITDB_D=/docker-entrypoint-initdb.d
CONTAINER_CONF=postgresql.container.conf

usage() {
  cat >&2 <<EOE
error: $1

You must specify either all of
  POSTGRESQL_USER       name of the application user (not a superuser; owns the database)
  POSTGRESQL_PASSWORD   password of the application user
  POSTGRESQL_DATABASE   name of the database the application user owns
or
  POSTGRESQL_ADMIN_PASSWORD   password of the postgres superuser
or both.

Optional tuning: POSTGRESQL_MAX_CONNECTIONS (100), POSTGRESQL_MAX_PREPARED_TRANSACTIONS (0),
POSTGRESQL_SHARED_BUFFERS (1/4 of the memory limit, or 32MB),
POSTGRESQL_EFFECTIVE_CACHE_SIZE (1/2 of the memory limit, or 128MB).
EOE
  exit 1
}

check_env() {
  local set=0 v
  for v in POSTGRESQL_USER POSTGRESQL_PASSWORD POSTGRESQL_DATABASE; do
    [ -n "${!v:-}" ] && set=$((set + 1))
  done
  if [ "$set" -ne 0 ] && [ "$set" -ne 3 ]; then
    usage "POSTGRESQL_USER, POSTGRESQL_PASSWORD and POSTGRESQL_DATABASE are set together or not at all."
  fi
  if [ "$set" -eq 0 ] && [ -z "${POSTGRESQL_ADMIN_PASSWORD:-}" ]; then
    usage "no application user and no POSTGRESQL_ADMIN_PASSWORD."
  fi
  if [ "${POSTGRESQL_USER:-}" = postgres ]; then
    usage "POSTGRESQL_USER cannot be postgres; set POSTGRESQL_ADMIN_PASSWORD for the superuser."
  fi
}

# True when an argument makes postgres print something and exit.
want_help() {
  local arg
  for arg; do
    case "$arg" in
      -'?' | --help | --describe-config | -V | --version) return 0 ;;
    esac
  done
  return 1
}

# Memory limit of the container in bytes (cgroup v2), or nothing when unlimited.
memory_limit() {
  local max
  max="$(cat /sys/fs/cgroup/memory.max 2>/dev/null || :)"
  case "$max" in
    '' | max | *[!0-9]*) ;;
    *) echo "$max" ;;
  esac
}

# The tuning file, rewritten on every start and included from postgresql.conf.
write_container_conf() {
  local limit shared=32MB cache=128MB
  limit="$(memory_limit)"
  if [ -n "$limit" ]; then
    shared="$((limit / 4 / 1024))kB"
    cache="$((limit / 2 / 1024))kB"
  fi
  {
    echo "# Written by $(basename "$0") on every start, from POSTGRESQL_* variables. Do not edit."
    printf "max_connections = '%s'\n" "${POSTGRESQL_MAX_CONNECTIONS:-100}"
    printf "max_prepared_transactions = '%s'\n" "${POSTGRESQL_MAX_PREPARED_TRANSACTIONS:-0}"
    printf "shared_buffers = '%s'\n" "${POSTGRESQL_SHARED_BUFFERS:-$shared}"
    printf "effective_cache_size = '%s'\n" "${POSTGRESQL_EFFECTIVE_CACHE_SIZE:-$cache}"
  } >"$PGDATA/$CONTAINER_CONF"
}

# psql over the socket as postgres, in DB (default postgres), stopping at the first error.
process_sql() {
  psql -v ON_ERROR_STOP=1 --username postgres --no-password --no-psqlrc --quiet \
    --dbname "${DB:-postgres}" "$@"
}

process_init_files() {
  # Sourced scripts call "${psql[@]}", as with the docker-library image.
  # shellcheck disable=SC2034
  psql=(process_sql)
  local f
  for f; do
    case "$f" in
      *.sh)
        if [ -x "$f" ]; then
          echo "$0: running $f"
          "$f"
        else
          echo "$0: sourcing $f"
          # shellcheck disable=SC1090
          . "$f"
        fi
        ;;
      *.sql) echo "$0: running $f"; process_sql -f "$f" ;;
      *.sql.gz) echo "$0: running $f"; gunzip -c "$f" | process_sql ;;
      *.sql.xz) echo "$0: running $f"; xzcat "$f" | process_sql ;;
      *.sql.zst) echo "$0: running $f"; zstd -dc "$f" | process_sql ;;
      *) echo "$0: ignoring $f" ;;
    esac
  done
}

init_cluster() {
  # Reading the directory now fails early, before a half-initialised PGDATA, if it is unreadable.
  ls "$INITDB_D/" >/dev/null
  initdb --username=postgres
  # Socket and loopback stay trust (initdb's default); every other host uses a password.
  printf '\nhost all all all %s\n' "$(postgres -C password_encryption -D "$PGDATA")" >>"$PGDATA/pg_hba.conf"
  printf "\ninclude '%s'\n" "$CONTAINER_CONF" >>"$PGDATA/postgresql.conf"
}

# Role, database and passwords from the environment; idempotent, run on every start. Values reach
# psql through \getenv, never the command line.
apply_env() {
  if [ -n "${POSTGRESQL_USER:-}" ]; then
    process_sql <<'EOSQL'
\getenv app_user POSTGRESQL_USER
\getenv app_password POSTGRESQL_PASSWORD
\getenv app_db POSTGRESQL_DATABASE
SELECT format('CREATE ROLE %I LOGIN', :'app_user')
  WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_user') \gexec
ALTER ROLE :"app_user" PASSWORD :'app_password';
SELECT format('CREATE DATABASE %I OWNER %I', :'app_db', :'app_user')
  WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'app_db') \gexec
EOSQL
  fi
  if [ -n "${POSTGRESQL_ADMIN_PASSWORD:-}" ]; then
    process_sql <<'EOSQL'
\getenv admin_password POSTGRESQL_ADMIN_PASSWORD
ALTER ROLE postgres PASSWORD :'admin_password';
EOSQL
  fi
}

main() {
  if [ "${1:0:1}" = - ]; then
    set -- postgres "$@"
  fi
  if [ "$1" != postgres ] || want_help "$@"; then
    exec "$@"
  fi

  check_env

  if [ "$(id -u)" = 0 ]; then
    mkdir -p "$PGDATA"
    find "$(dirname "$PGDATA")" /run/postgresql \! -user postgres -exec chown postgres:postgres '{}' +
    exec setpriv --reuid=postgres --regid=postgres --init-groups "$0" "$@"
  fi
  mkdir -p "$PGDATA"
  chmod 0700 "$PGDATA"

  local fresh=
  if [ -s "$PGDATA/PG_VERSION" ]; then
    echo "PostgreSQL database directory appears to contain a database; skipping initialization."
  else
    init_cluster
    fresh=1
  fi
  write_container_conf

  # Socket-only temporary server for the role, database, passwords and init scripts.
  NOTIFY_SOCKET='' pg_ctl -D "$PGDATA" -w start -o "$(printf '%q ' "${@:2}" -c listen_addresses= -p "${PGPORT:-5432}")"
  apply_env
  if [ -n "$fresh" ]; then
    DB="${POSTGRESQL_DATABASE:-postgres}" process_init_files "$INITDB_D"/*
  fi
  pg_ctl -D "$PGDATA" -m fast -w stop
  if [ -n "$fresh" ]; then
    echo "PostgreSQL init process complete; ready for start up."
  fi

  unset "${!POSTGRESQL_@}"
  exec "$@"
}

main "$@"
