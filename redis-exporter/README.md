# ubi10-redis-exporter

[redis_exporter](https://github.com/oliver006/redis_exporter) on Red Hat UBI 10 micro: the
upstream release binary `redis_exporter`, checksum-verified against the sha256 values upstream
publishes in the release's `sha256sums.txt`, rebuilt on UBI updates.

Prometheus metrics for Redis and Valkey: memory, clients, keyspace, hits and misses, evictions,
slowlog and latency, read through `INFO` and a few read-only commands.

Built from github.com/panda-coop/containers. Not affiliated with or supported by Red Hat or the
upstream project.

| Item | Value |
|---|---|
| Image | `quay.io/panda-coop/ubi10-redis-exporter` |
| Upstream | `oliver006/redis_exporter`, version in `ARG VERSION` of the [Containerfile](Containerfile) |
| Base | `registry.access.redhat.com/ubi10/ubi-micro`, pinned by digest; the binary is static |
| Architectures | `amd64`, `arm64` (both checksums pinned; CI publishes `amd64`) |
| User | `65534:65534` (`nobody`; upstream's image uses `59000`) |
| Licence | MIT; upstream `LICENSE` from the release archive in `/licenses/redis_exporter/` |
| CA bundle | `/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem`, copied from UBI `ca-certificates` (ubi-micro has none), for `rediss://` without `--tls-ca-cert-file` |

## Tags

| Tag | Example | Moves |
|---|---|---|
| `x.y.z-<epoch>` | `1.97.0-<epoch>` | never |
| `x.y.z` | `1.97.0` | on a UBI rebuild |
| `x.y` | `1.97` | on a patch release |
| `x` | `1` | on a minor release |
| `latest` | | on every release |

See [ADR 0001](../docs/decisions/0001-image-tags-version-release-timestamp.md).

## Runtime

| Item | Value |
|---|---|
| Entrypoint | `/usr/bin/redis_exporter`; arguments are its flags |
| Command | None; the default target is `--redis.addr=redis://localhost:6379`, as upstream |
| Port | `9121/tcp`, `/metrics`, as upstream |
| Configuration | None in the image: flags only, and every flag also reads its upper-case environment variable (`REDIS_ADDR`, `REDIS_USER`, `REDIS_PASSWORD`) |
| Credentials | `REDIS_PASSWORD` from a Podman secret (`--secret <name>,type=env,target=REDIS_PASSWORD`), not a flag: flags show up in `ps` and `podman inspect` |

A read-only ACL user is enough:

```text
ACL SETUSER exporter on >… -@all +info +ping +config|get +client|list +slowlog|get +latency
```

With that user, pass `--set-client-name=false`: the exporter otherwise runs `CLIENT SETNAME`
on every scrape and logs `NOPERM` for it (metrics are unaffected). The exporter keeps running
when Redis is down and reports `redis_up 0`.

## Example

```sh
printf '%s' "$EXPORTER_PASSWORD" | podman secret create redis-exporter-password -

podman run -d --name redis-exporter --network site -p 127.0.0.1:9121:9121 \
  --secret redis-exporter-password,type=env,target=REDIS_PASSWORD \
  quay.io/panda-coop/ubi10-redis-exporter:1 \
  --redis.addr=redis://redis:6379 --redis.user=exporter --set-client-name=false

curl -s localhost:9121/metrics | grep -E '^redis_(up|memory_used_bytes|evicted_keys_total) '
```

## Local build

```sh
task build IMAGE=redis-exporter     # localhost/ubi10-redis-exporter:dev
task run IMAGE=redis-exporter -- --version
task inspect IMAGE=redis-exporter
```

A version bump changes `ARG VERSION` and both `ARG SHA256_*` values together; take them from
the `linux-amd64` and `linux-arm64` lines of the release's `sha256sums.txt`
(`gh release download v<version> -R oliver006/redis_exporter -p sha256sums.txt -O -`). A stale
checksum fails the build.
