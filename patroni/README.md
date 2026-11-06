# ubi10-patroni

[Patroni](https://github.com/patroni/patroni) with [PostgreSQL](https://www.postgresql.org/) 18
on Red Hat UBI 10 minimal: `patroni`, `patroni-etcd`, `postgresql18-server` and
`postgresql18-contrib` from the [PGDG](https://yum.postgresql.org/) EL 10 repositories,
signature-verified, rebuilt on UBI updates.

A highly available PostgreSQL cluster with etcd as the DCS: Patroni elects the leader, runs
initdb on the first node, bootstraps the others with `pg_basebackup` and manages replication and
failover. The volume layout is [ubi10-postgresql](../postgresql/)'s.

Built from github.com/panda-coop/containers. Not affiliated with or supported by Red Hat, PGDG or
the upstream projects.

| Item | Value |
|---|---|
| Image | `quay.io/panda-coop/ubi10-patroni` |
| Upstream | PGDG `patroni` and `patroni-etcd` RPMs, Patroni version in `ARG VERSION`, PostgreSQL version in `ARG PG_VERSION` of the [Containerfile](Containerfile); the RPM releases follow the repositories |
| Base | `registry.access.redhat.com/ubi10/ubi-minimal`, pinned by digest |
| Repositories | UBI BaseOS and AppStream, `pgdg18` and `pgdg-common` ([pgdg.repo](pgdg.repo)); every other repository is disabled for the install, so a subscribed build host's RHEL repositories cannot satisfy a dependency |
| Signatures | `gpgcheck=1` and `repo_gpgcheck=1` against [PGDG-RPM-GPG-KEY-RHEL](PGDG-RPM-GPG-KEY-RHEL), fingerprint `D4BF 08AE 67A0 B4C7 A1DB CCD2 40BC A2B4 08B4 0D20`, the same key as ubi10-postgresql |
| Python | UBI's `python3` 3.12 and UBI Python libraries; PGDG builds `psycopg2`, `python-etcd`, `click`, `ydiff` and `py-consul` (a requirement of PGDG's `patroni` package, unused here) |
| DCS | etcd v3 API (`etcd3`); the etcd v2 `etcd` section also works. Consul, ZooKeeper, Kubernetes and Raft are not configured or tested |
| Not included | `llvmjit`, PostGIS, pgvector, pgBackRest, WAL-G |
| Architectures | `amd64`, `arm64` (PGDG publishes both; CI publishes `amd64`) |
| User | `26:26` (`postgres`, as the PGDG RPM and RHEL create it) |
| Licence | Patroni MIT, `LICENSE` in `/licenses/patroni/`; PostgreSQL, PGDG's `COPYRIGHT` in `/licenses/postgresql/` |

## Tags

| Tag | Example | Moves |
|---|---|---|
| `x.y.z-<epoch>` | `4.1.5-<epoch>` | never |
| `x.y.z` | `4.1.5` | on a UBI, PGDG or PostgreSQL minor rebuild |
| `x.y` | `4.1` | on a Patroni patch release |
| `x` | `4` | on a Patroni minor release |
| `latest` | | on every release |

The tags are Patroni's version ([ADR 0001](../docs/decisions/0001-image-tags-version-release-timestamp.md)).
PostgreSQL stays on major 18 and its minor is in the `io.k8s.description` and
`org.opencontainers.image.description` labels; a PostgreSQL minor update is a rebuild under the
same Patroni tags. A major upgrade is not this image's job.

## Runtime

| Item | Value |
|---|---|
| Entrypoint | `patroni` |
| Command | `/etc/patroni/patroni.yml`, the configuration path; arguments are Patroni's (`--version`, `--validate-config`). Other tools run with `podman exec` or `--entrypoint patronictl` |
| Ports | `5432/tcp` PostgreSQL, `8008/tcp` Patroni REST API |
| Volume | `/var/lib/pgsql/data`, owned by `26`, mode `0700`, as ubi10-postgresql |
| `PGDATA` | `/var/lib/pgsql/data/userdata`; set `postgresql.data_dir` to it, Patroni does not read `PGDATA` |
| Binaries | `/usr/pgsql-18/bin`, on `PATH`; `postgresql.bin_dir` can stay unset |
| Stop signal | `SIGTERM`: Patroni stops PostgreSQL in fast mode and releases the leader key, so a replica takes over at once. Give it time: `--stop-timeout 30` |
| PID 1 | Patroni itself: started as PID 1 it forks the daemon, forwards signals to it and reaps children. It exits `0` even when the daemon fails on a bad configuration; read the log |
| Locale | `LANG=C.UTF-8` |
| Configuration | None in the image. Patroni reads the file given as its argument if it exists, else the YAML in `PATRONI_CONFIGURATION`, else `PATRONI_*` variables alone; `PATRONI_*` variables override the file |
| PostgreSQL configuration | Patroni writes `postgresql.conf` and `pg_hba.conf`; initdb's file, from the PGDG sample with `logging_collector = off` (logs go to stderr), becomes `postgresql.base.conf` |
| `pgpass` | `~/pgpass` (`/var/lib/pgsql/pgpass`) unless `postgresql.pgpass` says otherwise; written by Patroni |

Patroni owns initdb, the superuser, replication and rewind users, `pg_hba.conf` and replication.
There is no `POSTGRESQL_*` sclorg contract and no `/docker-entrypoint-initdb.d` here: create
application roles and databases with `bootstrap.post_bootstrap`, or with SQL against the leader
after the cluster is up. A volume from ubi10-postgresql mounts at the same path with the cluster
in the same `userdata/`; adopting an existing cluster into Patroni is untested.

### REST API health checks

| Endpoint | `200` when |
|---|---|
| `GET /primary` (also `/leader`, `/read-write`) | the node is the running leader |
| `GET /replica` | the node is a running replica that may serve reads |
| `GET /read-only` | leader or replica, either can serve reads |
| `GET /quorum` | the node is a quorum standby (`synchronous_mode: quorum`) |
| `GET /sync` | the node is the synchronous standby (`synchronous_mode: on`) |
| `GET /health` | PostgreSQL is running, any role |
| `GET /liveness` | Patroni's main loop is alive; the container liveness probe |
| `GET /readiness` | leader, or replica streaming within lag |

Any other state returns `503`. An Envoy or HAProxy in front sends read-write traffic to the one
node that answers `/primary`, and reads to the nodes that answer `/replica`. Envoy, in the
read-write cluster (each endpoint sets `health_check_config.port_value: 8008`, so the check goes
to the REST API and the traffic to `5432`):

```yaml
health_checks:
  - timeout: 2s
    interval: 3s
    unhealthy_threshold: 1
    healthy_threshold: 2
    http_health_check:
      path: /primary
common_lb_config:
  healthy_panic_threshold:
    value: 0
```

`healthy_panic_threshold: 0` keeps Envoy from spreading writes across every node when only one
is healthy. HAProxy: `option httpchk GET /primary`, `http-check expect status 200`,
`server pg1 pg1:5432 check port 8008`.

## Three-node cluster

One node per host. One file for every node, mounted read-only; the node's name and addresses as
`PATRONI_*` variables, the passwords as Podman secrets. Three etcd members run beside it; this
image does not contain etcd. `etcd1`..`etcd3` must resolve from every host (DNS or
`/etc/hosts`); a container on Podman's default network uses the host's resolver, a Podman
bridge network's names do not leave its host.

```yaml
# patroni.yml
scope: pg
namespace: /service/
restapi:
  listen: 0.0.0.0:8008
  # Basic auth on the unsafe endpoints (POST /switchover, /failover, /restart, /reinitialize,
  # PATCH /config); the password is PATRONI_RESTAPI_PASSWORD.
  authentication:
    username: patroni
etcd3:
  hosts: etcd1:2379,etcd2:2379,etcd3:2379
bootstrap:
  # Written to etcd once, by the node that initialises the cluster; change it later with
  # patronictl edit-config.
  dcs:
    ttl: 30
    loop_wait: 10
    retry_timeout: 10
    maximum_lag_on_failover: 1048576
    # quorum: synchronous_standby_names = 'ANY 1 (pg2,pg3)', a commit waits for either standby.
    # on: 'pg2', one named synchronous standby (FIRST 1).
    synchronous_mode: quorum
    synchronous_node_count: 1
    postgresql:
      use_pg_rewind: true
      parameters:
        wal_level: replica
        hot_standby: "on"
        max_wal_senders: 10
        max_replication_slots: 10
        wal_log_hints: "on"
  initdb:
    - encoding: UTF8
    - data-checksums
postgresql:
  listen: 0.0.0.0:5432
  data_dir: /var/lib/pgsql/data/userdata
  pg_hba:
    - local all all trust
    - host replication replicator 0.0.0.0/0 scram-sha-256
    - host all all 0.0.0.0/0 scram-sha-256
  authentication:
    superuser:
      username: postgres
    replication:
      username: replicator
    rewind:
      username: rewind
```

```sh
printf '%s' "$SUPERUSER_PASSWORD" | podman secret create pg-superuser -
printf '%s' "$REPLICATION_PASSWORD" | podman secret create pg-replication -
printf '%s' "$REWIND_PASSWORD" | podman secret create pg-rewind -
printf '%s' "$RESTAPI_PASSWORD" | podman secret create pg-restapi -

# Per host: pg1 on 10.0.0.11, pg2 on 10.0.0.12, pg3 on 10.0.0.13. The connect addresses are
# the host's routable address or DNS name, which the other nodes and the load balancer dial;
# the published ports match them.
HOST_ADDR=10.0.0.11
podman volume create pg-data
podman run -d --name pg1 -p 5432:5432 -p 8008:8008 --stop-timeout 30 \
  -e PATRONI_NAME=pg1 \
  -e PATRONI_RESTAPI_CONNECT_ADDRESS="$HOST_ADDR:8008" \
  -e PATRONI_POSTGRESQL_CONNECT_ADDRESS="$HOST_ADDR:5432" \
  --secret pg-superuser,type=env,target=PATRONI_SUPERUSER_PASSWORD \
  --secret pg-replication,type=env,target=PATRONI_REPLICATION_PASSWORD \
  --secret pg-rewind,type=env,target=PATRONI_REWIND_PASSWORD \
  --secret pg-restapi,type=env,target=PATRONI_RESTAPI_PASSWORD \
  -v ./patroni.yml:/etc/patroni/patroni.yml:ro,z \
  -v pg-data:/var/lib/pgsql/data \
  quay.io/panda-coop/ubi10-patroni:4

podman exec pg1 patronictl -c /etc/patroni/patroni.yml list
```

The first node to take the initialise key in etcd runs initdb and becomes the leader. The
others find an empty `PGDATA`, run `pg_basebackup` from the leader as `replicator` (the default
`create_replica_methods: [basebackup]`) and stream from it; Patroni creates their replication
slots. A failed or wiped replica re-bootstraps the same way on its next start; with
`use_pg_rewind`, a former leader rewinds and rejoins as a replica. `patronictl list` then shows
one `Leader` and two `Quorum Standby` members (`Sync Standby` with `synchronous_mode: on`).

`restapi.authentication` covers only the unsafe endpoints: the `GET` health endpoints stay
unauthenticated, so the Envoy and HAProxy checks need no credentials. `patronictl` in the
container takes the same username and `PATRONI_RESTAPI_PASSWORD` for `switchover`, `failover`
and `restart`.

`:z`, not `:Z`, when the file is shared by more than one container on a host: `:Z` gives each
container a private SELinux label and the others cannot read it. Without the file, the same
settings go in `PATRONI_*` variables (`PATRONI_SCOPE`, `PATRONI_ETCD3_HOSTS`,
`PATRONI_POSTGRESQL_DATA_DIR`, `PATRONI_SUPERUSER_USERNAME`, ...) or as a whole YAML in
`PATRONI_CONFIGURATION`; `bootstrap.dcs` and `pg_hba` have no individual variables.

## Local build

```sh
task build IMAGE=patroni     # localhost/ubi10-patroni:dev
task run IMAGE=patroni -- --version
task inspect IMAGE=patroni
```

Renovate follows Patroni's GitHub releases on `ARG VERSION`. PGDG can lag a Patroni release;
until PGDG has the RPMs the build fails at `microdnf install`. `ARG PG_VERSION` is not tracked
by Renovate: bump it with ubi10-postgresql's `ARG VERSION`.
