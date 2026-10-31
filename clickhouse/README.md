# ubi10-clickhouse

[ClickHouse](https://github.com/ClickHouse/ClickHouse) on Red Hat UBI 10 minimal:
`clickhouse-server` and `clickhouse-client` from ClickHouse's official RPM repository, stable
channel, with an entrypoint that keeps the environment contract of upstream's
`clickhouse/clickhouse-server` image. Rebuilt on UBI updates.

Built from github.com/panda-coop/containers. Not affiliated with or supported by Red Hat or the
upstream project.

| Item | Value |
|---|---|
| Image | `quay.io/panda-coop/ubi10-clickhouse` |
| Upstream | `ClickHouse/ClickHouse`, version in `ARG VERSION` of the [Containerfile](Containerfile) |
| Packages | `clickhouse-server`, `clickhouse-client`, `clickhouse-common-static`, all pinned to `VERSION`, from `https://packages.clickhouse.com/rpm/stable/` |
| Package check | Signed repository metadata (`repo_gpgcheck=1`) against [`RPM-GPG-KEY-clickhouse`](RPM-GPG-KEY-clickhouse), fingerprint `3A9EA1193A97B548BE1457D48919F6BD2B48D754`. The packages themselves are unsigned (`gpgcheck=0`), as upstream publishes them |
| Base | `registry.access.redhat.com/ubi10/ubi-minimal`, pinned by digest; every other package comes from the UBI repos |
| Architectures | `amd64`, `arm64` (the repository has both; CI publishes `amd64`) |
| User | `101:101` (`clickhouse`, as upstream) |
| Licence | Apache-2.0; upstream `LICENSE` in `/licenses/clickhouse/` |

Stable, not LTS: ClickHouse [recommends stable by default](https://clickhouse.com/docs/faq/operations/production)
and LTS only for policies that forbid frequent upgrades.

## Tags

| Tag | Example | Moves |
|---|---|---|
| `x.y.z.w-<epoch>` | `26.10.2.103-<epoch>` | never |
| `x.y.z.w` | `26.10.2.103` | on a UBI rebuild |

ClickHouse versions have four parts; the floating tags of
[ADR 0001](../docs/decisions/0001-image-tags-version-release-timestamp.md) are not settled for them yet.

## Runtime

| Item | Value |
|---|---|
| Entrypoint | `/entrypoint.sh`; with no arguments, or arguments starting with `--`, it starts `clickhouse-server`; anything else runs as given (`bash`, `clickhouse-client`) |
| Ports | `8123/tcp` HTTP, `9000/tcp` native, `9009/tcp` interserver |
| Volume | `/var/lib/clickhouse`, owned by `101` |
| Configuration | The package's `config.xml` and `users.xml`, plus `config.d/docker_related_config.xml` (listen on all addresses, as upstream). Mount more under `/etc/clickhouse-server/config.d/` and `users.d/` |
| Logs | `/var/log/clickhouse-server/`, as upstream; the container log carries only the entrypoint and startup lines |
| Locale, time zone | `LANG=C.UTF-8`, `TZ=UTC` |

### Environment

| Variable | Default | Effect |
|---|---|---|
| `CLICKHOUSE_USER` | `default` | User created in place of `default` |
| `CLICKHOUSE_PASSWORD` | empty | Its password. With neither user nor password set, `default` is reachable from localhost only |
| `CLICKHOUSE_PASSWORD_FILE` | empty | Read the password from this file (a secret mount) |
| `CLICKHOUSE_DB` | empty | Database created on first start |
| `CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT` | `0` | `1` lets the user manage users and grants with SQL |
| `CLICKHOUSE_SKIP_USER_SETUP` | `0` | `1` leaves the users as the mounted configuration defines them |
| `CLICKHOUSE_ALWAYS_RUN_INITDB_SCRIPTS` | empty | Non-empty runs the init scripts on every start |
| `CLICKHOUSE_INIT_TIMEOUT` | `1000` | Seconds to wait for the init server |

The user file (`users.d/default-user.xml`) is written on every start, so a changed variable takes
effect on the next restart.

### Init scripts

On first start, when `/var/lib/clickhouse/data` does not exist yet, the entrypoint starts the
server on `127.0.0.1` only, creates `CLICKHOUSE_DB`, runs `/docker-entrypoint-initdb.d/*` in
name order (`*.sh` executed if executable, sourced otherwise; `*.sql` and `*.sql.gz` through
`clickhouse-client` as `CLICKHOUSE_USER`), stops it, and then starts the server for real.

## Example

```sh
podman volume create clickhouse-data
podman run -d --name clickhouse -p 8123:8123 -p 9000:9000 \
  -e CLICKHOUSE_USER=app -e CLICKHOUSE_PASSWORD=change-me -e CLICKHOUSE_DB=app \
  -v clickhouse-data:/var/lib/clickhouse \
  -v ./initdb:/docker-entrypoint-initdb.d:ro,Z \
  quay.io/panda-coop/ubi10-clickhouse:26.10.2.103

podman exec clickhouse clickhouse-client --user app --password change-me --query 'select version()'
```

## How it differs from upstream

| | `clickhouse/clickhouse-server` | `ubi10-clickhouse` |
|---|---|---|
| Base | Ubuntu | UBI 10 minimal |
| Process user | starts as root, chowns, then `clickhouse su` to `101` | runs as `101` from the start; no chown, so `CLICKHOUSE_UID`, `CLICKHOUSE_GID`, `CLICKHOUSE_RUN_AS_ROOT` and `CLICKHOUSE_DO_NOT_CHOWN` do not apply. A volume must be writable by `101` |
| Mounted `users.xml` overrides | detected by comparing `users.default` before and after processing | not detected; set `CLICKHOUSE_SKIP_USER_SETUP=1` |
| Extra directories | log, tmp, user files and disk paths from the config are created and chowned | not created; everything under `/var/lib/clickhouse` is created by the server itself |
| Locale | `en_US.UTF-8` | `C.UTF-8` (no langpack needed) |

## Local build

```sh
task build IMAGE=clickhouse     # localhost/ubi10-clickhouse:dev
task run IMAGE=clickhouse -- clickhouse-client --version
task inspect IMAGE=clickhouse
```

A version bump changes `ARG VERSION` only; the version must exist in the stable repository.
