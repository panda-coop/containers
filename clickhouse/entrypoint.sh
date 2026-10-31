#!/bin/bash
# A lean equivalent of upstream's docker/server/entrypoint.sh, for an image that already runs as
# the clickhouse user: no chown, no `clickhouse su`. Same environment contract:
#   CLICKHOUSE_USER, CLICKHOUSE_PASSWORD (or CLICKHOUSE_PASSWORD_FILE), CLICKHOUSE_DB,
#   CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT, CLICKHOUSE_SKIP_USER_SETUP,
#   CLICKHOUSE_ALWAYS_RUN_INITDB_SCRIPTS, CLICKHOUSE_INIT_TIMEOUT,
# and /docker-entrypoint-initdb.d (*.sh, *.sql, *.sql.gz) on first start only.
set -euo pipefail
shopt -s nullglob

# Anything but server flags runs as given, e.g. `bash` or `clickhouse-client`.
if [[ $# -gt 0 && "$1" != --* ]]; then
  exec "$@"
fi

config="${CLICKHOUSE_CONFIG:-/etc/clickhouse-server/config.xml}"
data_dir="$(clickhouse extract-from-config --config-file "$config" --key=path)"

user="${CLICKHOUSE_USER:-default}"
password="${CLICKHOUSE_PASSWORD:-}"
if [[ -n "${CLICKHOUSE_PASSWORD_FILE:-}" && -f "$CLICKHOUSE_PASSWORD_FILE" ]]; then
  password="$(<"$CLICKHOUSE_PASSWORD_FILE")"
fi
db="${CLICKHOUSE_DB:-}"
access_management="${CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT:-0}"
users_file=/etc/clickhouse-server/users.d/default-user.xml

# Rewritten on every start, so changing the environment and restarting takes effect. Upstream
# also leaves `default` alone when a mounted users file already changes it; here that is
# CLICKHOUSE_SKIP_USER_SETUP=1.
if [[ "${CLICKHOUSE_SKIP_USER_SETUP:-0}" == 1 ]]; then
  echo "$0: CLICKHOUSE_SKIP_USER_SETUP=1, users left as configured"
elif [[ "$user" != default || -n "$password" || "$access_management" != 0 ]]; then
  echo "$0: user '$user' replaces 'default'"
  cat > "$users_file" <<EOT
<clickhouse>
  <users>
    <default remove="remove"></default>
    <${user}>
      <profile>default</profile>
      <networks><ip>::/0</ip></networks>
      <password><![CDATA[${password//]]>/]]]]><![CDATA[>}]]></password>
      <quota>default</quota>
      <access_management>${access_management}</access_management>
    </${user}>
  </users>
</clickhouse>
EOT
else
  echo "$0: no CLICKHOUSE_USER or CLICKHOUSE_PASSWORD, user 'default' is local-only"
  cat > "$users_file" <<EOT
<clickhouse>
  <users>
    <default>
      <networks><ip>::1</ip><ip>127.0.0.1</ip></networks>
    </default>
  </users>
</clickhouse>
EOT
fi

# First start: no ${data_dir}/data yet. The server listens on localhost only until the init is done.
initdb=(/docker-entrypoint-initdb.d/*)
if [[ ( ! -d "${data_dir%/}/data" || -n "${CLICKHOUSE_ALWAYS_RUN_INITDB_SCRIPTS:-}" ) \
      && ( ${#initdb[@]} -gt 0 || -n "$db" ) ]]; then
  http_port="$(clickhouse extract-from-config --config-file "$config" --key=http_port)"
  tcp_port="$(clickhouse extract-from-config --config-file "$config" --key=tcp_port)"

  clickhouse-server --config-file="$config" -- --listen_host=127.0.0.1 &
  pid="$!"

  tries="${CLICKHOUSE_INIT_TIMEOUT:-1000}"
  until curl -fsS -m 1 -o /dev/null "http://127.0.0.1:${http_port}/ping" 2>/dev/null; do
    if (( tries-- <= 0 )); then
      echo "$0: ClickHouse did not start for the init" >&2
      exit 1
    fi
    sleep 1
  done

  client=(clickhouse-client --multiquery --host 127.0.0.1 --port "$tcp_port" --user "$user" --password "$password")

  if [[ -n "$db" ]]; then
    echo "$0: create database '$db'"
    "${client[@]}" --query "CREATE DATABASE IF NOT EXISTS \`${db}\`"
  fi

  for f in "${initdb[@]}"; do
    case "$f" in
      *.sh)
        if [[ -x "$f" ]]; then
          echo "$0: running $f"
          "$f"
        else
          echo "$0: sourcing $f"
          # shellcheck source=/dev/null
          . "$f"
        fi
        ;;
      *.sql) echo "$0: running $f"; "${client[@]}" < "$f" ;;
      *.sql.gz) echo "$0: running $f"; gunzip -c "$f" | "${client[@]}" ;;
      *) echo "$0: ignoring $f" ;;
    esac
  done

  kill -TERM "$pid"
  wait "$pid"
fi

# The watchdog does not forward SIGINT; without it the container stops on SIGTERM directly.
export CLICKHOUSE_WATCHDOG_ENABLE="${CLICKHOUSE_WATCHDOG_ENABLE:-0}"
cd "$data_dir"
exec clickhouse-server --config-file="$config" "$@"
