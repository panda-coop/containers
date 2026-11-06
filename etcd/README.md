# ubi10-etcd

[etcd](https://etcd.io) on Red Hat UBI 10 micro: the upstream release binaries `etcd`, `etcdctl`
and `etcdutl`, checksum-verified against the sha256 values upstream publishes in the release's
`SHA256SUMS`, rebuilt on UBI updates.

The distributed configuration store (DCS) for Patroni: a 3-member cluster, one member per
worker, holds the PostgreSQL leader key and cluster state. Three members tolerate one failure.

Built from github.com/panda-coop/containers. Not affiliated with or supported by Red Hat or the
upstream project.

| Item | Value |
|---|---|
| Image | `quay.io/panda-coop/ubi10-etcd` |
| Upstream | `etcd-io/etcd`, 3.6 line, version in `ARG VERSION` of the [Containerfile](Containerfile) |
| Base | `registry.access.redhat.com/ubi10/ubi-micro`, pinned by digest; the binaries are static |
| Architectures | `amd64`, `arm64` (both checksums pinned; CI publishes `amd64`) |
| User | `1001:1001`, a fixed owner for the data volume (not `65534`: data owned by `nobody` is readable by every other `nobody` process) |
| Licence | Apache-2.0; upstream `LICENSE` from the release tag, sha256-pinned, in `/licenses/etcd/` (the release archive has none) |
| CA bundle | `/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem`, copied from UBI `ca-certificates` (ubi-micro has none) |

## Tags

| Tag | Example | Moves |
|---|---|---|
| `x.y.z-<epoch>` | `3.6.16-<epoch>` | never |
| `x.y.z` | `3.6.16` | on a UBI rebuild |
| `x.y` | `3.6` | on a patch release |
| `x` | `3` | on a minor release |
| `latest` | | on every release |

See [ADR 0001](../docs/decisions/0001-image-tags-version-release-timestamp.md). Renovate follows
3.6 patch releases only (`extractVersion` in the Containerfile); a move to 3.7 is a deliberate
edit, since etcd upgrades one minor at a time across a running cluster.

## Runtime

| Item | Value |
|---|---|
| Entrypoint | `/usr/bin/etcd`; arguments are its flags. `etcdctl` and `etcdutl` are on `PATH` for `podman exec` |
| Command | None |
| Ports | `2379/tcp` clients (Patroni, `etcdctl`), `2380/tcp` peers |
| Volume | `/var/lib/etcd`, mode `0700`, owner `1001:1001`; `ETCD_DATA_DIR=/var/lib/etcd` is the only default |
| Configuration | None in the image: `ETCD_*` environment (every flag has one, `--initial-cluster` is `ETCD_INITIAL_CLUSTER`) or flags |
| Flag and variable | etcd exits when a flag and its `ETCD_*` variable are both set: change the data directory with `ETCD_DATA_DIR`, never `--data-dir` |
| Bind mount | The host directory must be owned by `1001` inside the user namespace: `Volume=/srv/etcd:/var/lib/etcd:Z,U` |

Defaults left upstream's: etcd listens on `localhost` only until `ETCD_LISTEN_CLIENT_URLS` and
`ETCD_LISTEN_PEER_URLS` say otherwise, and a listener on `0.0.0.0` needs the matching
`ETCD_ADVERTISE_CLIENT_URLS` / `ETCD_INITIAL_ADVERTISE_PEER_URLS`.

## Example: 3 members with Quadlet

One unit per worker; only `ETCD_NAME` and the advertised URLs change. The `ETCD_INITIAL_*`
values are read only when the data directory is empty, on the first start.

```ini
# /etc/containers/systemd/etcd.container, on worker-1
[Unit]
Description=etcd member worker-1

[Container]
Image=quay.io/panda-coop/ubi10-etcd:3.6.16-<epoch>
ContainerName=etcd
Volume=etcd-data:/var/lib/etcd:Z
PublishPort=2379:2379
PublishPort=2380:2380
Environment=ETCD_NAME=worker-1
Environment=ETCD_INITIAL_CLUSTER=worker-1=https://worker-1:2380,worker-2=https://worker-2:2380,worker-3=https://worker-3:2380
Environment=ETCD_INITIAL_CLUSTER_STATE=new
Environment=ETCD_INITIAL_CLUSTER_TOKEN=patroni-etcd
Environment=ETCD_LISTEN_PEER_URLS=https://0.0.0.0:2380
Environment=ETCD_INITIAL_ADVERTISE_PEER_URLS=https://worker-1:2380
Environment=ETCD_LISTEN_CLIENT_URLS=https://0.0.0.0:2379
Environment=ETCD_ADVERTISE_CLIENT_URLS=https://worker-1:2379
Environment=ETCD_LISTEN_METRICS_URLS=http://0.0.0.0:2381
PublishPort=127.0.0.1:2381:2381
# TLS on both ports, certificates from the host (see TLS below)
Volume=/etc/etcd/pki:/etc/etcd/pki:ro,Z
Environment=ETCD_CERT_FILE=/etc/etcd/pki/server.crt
Environment=ETCD_KEY_FILE=/etc/etcd/pki/server.key
Environment=ETCD_TRUSTED_CA_FILE=/etc/etcd/pki/ca.crt
Environment=ETCD_CLIENT_CERT_AUTH=true
Environment=ETCD_PEER_CERT_FILE=/etc/etcd/pki/peer.crt
Environment=ETCD_PEER_KEY_FILE=/etc/etcd/pki/peer.key
Environment=ETCD_PEER_TRUSTED_CA_FILE=/etc/etcd/pki/ca.crt
Environment=ETCD_PEER_CLIENT_CERT_AUTH=true

[Service]
Restart=always
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

The same cluster with plain `podman run` on one host, as the image's smoke test runs it:

```sh
podman network create etcd
CLUSTER=e1=http://e1:2380,e2=http://e2:2380,e3=http://e3:2380
for n in e1 e2 e3; do
  podman run -d --name "$n" --network etcd -v "etcd-$n:/var/lib/etcd" \
    -e ETCD_NAME="$n" -e ETCD_INITIAL_CLUSTER="$CLUSTER" -e ETCD_INITIAL_CLUSTER_STATE=new \
    -e ETCD_LISTEN_PEER_URLS=http://0.0.0.0:2380 -e ETCD_INITIAL_ADVERTISE_PEER_URLS="http://$n:2380" \
    -e ETCD_LISTEN_CLIENT_URLS=http://0.0.0.0:2379 -e ETCD_ADVERTISE_CLIENT_URLS="http://$n:2379" \
    quay.io/panda-coop/ubi10-etcd:3
done
podman exec e1 etcdctl --endpoints=http://e1:2379 endpoint status --cluster -w table
```

Patroni points at all three client URLs (`etcd3:` with `hosts: worker-1:2379,worker-2:2379,worker-3:2379`,
`protocol: https` and its client certificate).

## TLS

Production members use TLS on both ports: peer traffic carries every write, client traffic the
Patroni leader lock. Certificates are mounted, never baked in. `ETCD_CLIENT_CERT_AUTH=true` and
`ETCD_PEER_CLIENT_CERT_AUTH=true` make etcd require a certificate signed by the trusted CA, which
is the access control for the DCS. The server certificate's SANs must cover every name in the
advertised URLs, and the key files must be readable by UID `1001`. The image's CA bundle only
serves outbound connections to publicly trusted endpoints; the cluster CA is
`ETCD_TRUSTED_CA_FILE` / `ETCD_PEER_TRUSTED_CA_FILE`.

## Health and metrics

| Check | How |
|---|---|
| Member health | `podman exec etcd etcdctl endpoint health` (with TLS: `--cacert`, `--cert`, `--key`, or `ETCDCTL_CACERT` / `ETCDCTL_CERT` / `ETCDCTL_KEY`) |
| Cluster view | `etcdctl endpoint status --cluster -w table`: leader, Raft term and index, DB size per member |
| HTTP | `GET /health` on the client port, or on `ETCD_LISTEN_METRICS_URLS` without client certificates |
| Metrics | `GET /metrics` on the same listeners; watch `etcd_server_has_leader`, `etcd_server_leader_changes_seen_total`, `etcd_disk_wal_fsync_duration_seconds`, `etcd_disk_backend_commit_duration_seconds` |

A separate plain-HTTP `ETCD_LISTEN_METRICS_URLS` (bound to localhost or the monitoring network)
lets Prometheus scrape without a client certificate.

## Backup

```sh
podman exec etcd etcdctl snapshot save /var/lib/etcd/snapshot.db
podman exec etcd etcdutl snapshot status /var/lib/etcd/snapshot.db -w table
podman cp etcd:/var/lib/etcd/snapshot.db ./etcd-$(date -u +%Y%m%dT%H%M%SZ).db
```

One member's snapshot is the whole keyspace. Restore is `etcdutl snapshot restore` into an empty
data directory on every member, then a new cluster. For Patroni the DCS holds no data that
PostgreSQL cannot rebuild, so losing quorum is an outage until a new cluster is created, not data
loss.

## Disk

etcd fsyncs its write-ahead log on every commit; a slow disk shows up as leader elections and
Patroni failovers, not as slowness. Put `/var/lib/etcd` on SSD or NVMe local storage, never on
network storage, and check `etcd_disk_wal_fsync_duration_seconds` p99 (upstream's guidance:
under 10 ms). The default backend quota is 2 GiB; Patroni writes a few keys, so the quota only
matters if compaction stops.

## Local build

```sh
task build IMAGE=etcd     # localhost/ubi10-etcd:dev
task run IMAGE=etcd -- --version
task inspect IMAGE=etcd
```

A version bump changes `ARG VERSION` and both `ARG SHA256_*` architecture values together; take
them from the `linux-amd64.tar.gz` and `linux-arm64.tar.gz` lines of the release's `SHA256SUMS`
(`gh release download v<version> -R etcd-io/etcd -p SHA256SUMS -O -`). `SHA256_LICENSE` changes
only if upstream changes the licence text. A stale checksum fails the build.
