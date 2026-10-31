# ubi10-postgresql

[PostgreSQL](https://www.postgresql.org/) on Red Hat UBI 10 minimal: `postgresql18-server` and
`postgresql18-contrib` from the [PGDG](https://yum.postgresql.org/) EL 10 repository,
signature-verified, with an entrypoint whose environment contract is compatible with the Red Hat /
sclorg PostgreSQL images ([sclorg/postgresql-container](https://github.com/sclorg/postgresql-container)).
Rebuilt on UBI updates.

Built from github.com/panda-coop/containers. Not affiliated with or supported by Red Hat, the
sclorg project or the upstream project. The entrypoint is our own, written from the sclorg
documentation; no sclorg code is used.

| Item | Value |
|---|---|
| Image | `quay.io/panda-coop/ubi10-postgresql` |
| Upstream | PGDG `postgresql18-*` RPMs, PostgreSQL version in `ARG VERSION` of the [Containerfile](Containerfile); the RPM release follows the repository |
| Base | `registry.access.redhat.com/ubi10/ubi-minimal`, pinned by digest |
| Repositories | UBI BaseOS and AppStream, and `pgdg18` ([pgdg.repo](pgdg.repo)); every other repository is disabled for the install, so a subscribed build host's RHEL repositories cannot satisfy a dependency |
| Signatures | `gpgcheck=1` and `repo_gpgcheck=1` against [PGDG-RPM-GPG-KEY-RHEL](PGDG-RPM-GPG-KEY-RHEL), fingerprint `D4BF 08AE 67A0 B4C7 A1DB CCD2 40BC A2B4 08B4 0D20`, from `pgdg-redhat-repo-latest.noarch.rpm` |
| Not included | `llvmjit`, PostGIS, pgvector |
| Architectures | `amd64`, `arm64` (PGDG publishes both; CI publishes `amd64`) |
| User | `26:26` (`postgres`, as the PGDG RPM and RHEL create it) |
| Licence | PostgreSQL; PGDG's `COPYRIGHT` in `/licenses/postgresql/` |

## Tags

| Tag | Example | Moves |
|---|---|---|
| `x.y-<epoch>` | `18.6-<epoch>` | never |
| `x.y` | `18.6` | on a UBI or PGDG rebuild |
| `x` | `18` | on a minor release |
| `latest` | | on every release |

PostgreSQL versions are `major.minor`, one level shorter than the `x.y.z` of
[ADR 0001](../docs/decisions/0001-image-tags-version-release-timestamp.md). The image stays on
major 18: a major upgrade (`pg_upgrade`) is not this image's job.

## Runtime

| Item | Value |
|---|---|
| Entrypoint | `postgresql-entrypoint.sh` |
| Command | `postgres`; a first argument starting with `-` is passed to `postgres`; any other command runs as given |
| Port | `5432/tcp` |
| Volume | `/var/lib/pgsql/data`, owned by `26`, mode `0700` |
| `PGDATA` | `/var/lib/pgsql/data/userdata`, the cluster inside the volume, as RHEL |
| Stop signal | `SIGINT` (fast shutdown) |
| Binaries | `/usr/pgsql-18/bin`, on `PATH` |
| Locale | `LANG=C.UTF-8` |
| Configuration | initdb's defaults from the PGDG sample with `listen_addresses = '*'` and `logging_collector = off` (logs go to stderr); `postgresql.conf` includes `postgresql.container.conf`, rewritten from the tuning variables on every start |
| Authentication | socket and loopback `trust` (initdb's default); every other host the configured `password_encryption` (`scram-sha-256`) |

### Environment

Set either the application trio, or `POSTGRESQL_ADMIN_PASSWORD`, or both; any other combination,
including no variables, exits with a usage message. Checked on every start.

| Variable | Meaning |
|---|---|
| `POSTGRESQL_USER` | Application user. Not a superuser, cannot be `postgres`. Set together with the next two |
| `POSTGRESQL_PASSWORD` | Its password |
| `POSTGRESQL_DATABASE` | Database it owns |
| `POSTGRESQL_ADMIN_PASSWORD` | Optional password of the `postgres` superuser. Unset, `postgres` has no password and only connects locally |

On every start, before the server listens, the entrypoint creates the user and the database if
they are missing and sets both passwords from the environment, as the sclorg images do: the
environment is the source of truth, and a password changed with SQL is reset at the next start.
Removing `POSTGRESQL_ADMIN_PASSWORD` later leaves the stored `postgres` password as it was.

### Tuning

Written to `postgresql.container.conf` on every start; a changed value applies after a restart.

| Variable | Default |
|---|---|
| `POSTGRESQL_MAX_CONNECTIONS` | `100` |
| `POSTGRESQL_MAX_PREPARED_TRANSACTIONS` | `0` |
| `POSTGRESQL_SHARED_BUFFERS` | 1/4 of the container memory limit, or `32MB` without one |
| `POSTGRESQL_EFFECTIVE_CACHE_SIZE` | 1/2 of the container memory limit, or `128MB` without one |

The memory limit is read from cgroup v2 (`/sys/fs/cgroup/memory.max`), set with `--memory`.

### Init scripts

Our one deviation from the sclorg contract: on the first start only, after initdb and the user
and database, `/docker-entrypoint-initdb.d/*` runs in name order against a socket-only temporary
server, as `postgres` in `POSTGRESQL_DATABASE` (`postgres` when only the admin password is set).
Objects a script creates belong to `postgres`; grant to the application user in the script.

| File | Handling |
|---|---|
| `*.sh`, executable | Run |
| `*.sh`, not executable | Sourced; `"${psql[@]}"` is the psql command |
| `*.sql`, `*.sql.gz`, `*.sql.xz`, `*.sql.zst` | Fed to `psql -v ON_ERROR_STOP=1` |
| anything else | Ignored |

A failing script stops the container with a half-initialised `PGDATA`; remove the volume before
the next attempt.

### User

The image runs as `postgres` (`26`). Started with `--user 0`, the entrypoint chowns the volume
and `/run/postgresql` to `postgres` and re-executes itself as `postgres` with `setpriv`. An
arbitrary UID without a `/etc/passwd` entry (OpenShift `restricted`) is not supported.

## Differences from the sclorg images

| Item | sclorg `postgresql-18` | This image |
|---|---|---|
| `/docker-entrypoint-initdb.d` | not documented | `*.sh`, `*.sql` on first init |
| Logging | files under `userdata/log` (`POSTGRESQL_LOG_DESTINATION`) | stderr; `POSTGRESQL_LOG_DESTINATION` is ignored |
| `POSTGRESQL_LIBRARIES`, `POSTGRESQL_EXTENSIONS` | supported | not supported |
| Migration (`POSTGRESQL_MIGRATION_*`), upgrade (`POSTGRESQL_UPGRADE`) | supported | not supported |
| s2i hooks (`postgresql-cfg/`, `-init/`, `-start/`, `-pre-start/`) | supported | not supported |

## Volume and upgrades

The volume layout is RHEL's: mount at `/var/lib/pgsql/data`, cluster in `userdata/`. The tuning
include is added to `postgresql.conf` at initdb, so a cluster initialised elsewhere (an sclorg
volume, for example) does not pick up the tuning variables; reusing one is untested. A cluster
from another major does not start on 18: dump and restore, or run `pg_upgrade` outside this
image. This image's earlier docker-library-style builds used `/var/lib/postgresql/data` and the
`POSTGRES_*` variables; their volumes are not carried over.

## Example

```sh
podman volume create pg-data
podman run -d --name postgres -p 5432:5432 \
  -e POSTGRESQL_USER=app -e POSTGRESQL_PASSWORD=change-me -e POSTGRESQL_DATABASE=app \
  -e POSTGRESQL_ADMIN_PASSWORD=change-me-too \
  -v pg-data:/var/lib/pgsql/data \
  -v ./initdb.d:/docker-entrypoint-initdb.d:ro,Z \
  quay.io/panda-coop/ubi10-postgresql:18

podman exec -it postgres psql -d app -c 'select version()'
```

A bind-mounted volume must be owned by `26` inside the container; with rootless Podman, `:U` on
the mount does that.

## Local build

```sh
task build IMAGE=postgresql     # localhost/ubi10-postgresql:dev
task run IMAGE=postgresql -- postgres --version
task inspect IMAGE=postgresql
```

Renovate follows the `postgres` image's `18.y` tags. Docker Hub can publish a minor before PGDG
has its RPMs; until PGDG catches up the build fails at `microdnf install`.
