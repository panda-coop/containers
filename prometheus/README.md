# ubi10-prometheus

[Prometheus](https://github.com/prometheus/prometheus) on Red Hat UBI 10 micro: the upstream
release binaries `prometheus` and `promtool`, checksum-verified against the release's
`sha256sums.txt`, rebuilt on UBI updates.

Built from github.com/panda-coop/containers. Not affiliated with or supported by Red Hat or the
upstream project.

| Item | Value |
|---|---|
| Image | `quay.io/panda-coop/ubi10-prometheus` |
| Upstream | `prometheus/prometheus`, version in `ARG VERSION` of the [Containerfile](Containerfile) |
| Base | `registry.access.redhat.com/ubi10/ubi-micro`, pinned by digest |
| Architectures | `amd64`, `arm64` (both checksums pinned; CI publishes `amd64`) |
| User | `65534:65534` (`nobody`, as upstream) |
| Licence | Apache-2.0; upstream `LICENSE` and `NOTICE` in `/licenses/prometheus/` |

## Tags

| Tag | Example | Moves |
|---|---|---|
| `x.y.z-<epoch>` | `3.15.0-<epoch>` | never |
| `x.y.z` | `3.15.0` | on a UBI rebuild |
| `x.y` | `3.15` | on a patch release |
| `x` | `3` | on a minor release |
| `latest` | | on every release |

See [ADR 0001](../docs/decisions/0001-image-tags-version-release-timestamp.md).

## Runtime

| Item | Value |
|---|---|
| Entrypoint | `/bin/prometheus` |
| Command | `--config.file=/etc/prometheus/prometheus.yml --storage.tsdb.path=/prometheus`, as upstream |
| Port | `9090/tcp` |
| Volume | `/prometheus` (TSDB), owned by `65534`, group-writable |
| Configuration | None in the image: mount `/etc/prometheus/prometheus.yml`. Upstream's image ships an example config; this one does not, so a bare `podman run` exits with "Error loading config" |
| Also included | `/bin/promtool` |

## Example

```sh
podman volume create prometheus-data
podman run -d --name prometheus -p 9090:9090 \
  -v ./prometheus.yml:/etc/prometheus/prometheus.yml:ro,Z \
  -v prometheus-data:/prometheus \
  quay.io/panda-coop/ubi10-prometheus:3

podman run --rm --entrypoint /bin/promtool \
  -v ./prometheus.yml:/etc/prometheus/prometheus.yml:ro,Z \
  quay.io/panda-coop/ubi10-prometheus:3 check config /etc/prometheus/prometheus.yml
```

Extra flags replace the default command, so repeat `--config.file` and `--storage.tsdb.path`
when adding one (for example `--storage.tsdb.retention.time=30d`).

## Local build

```sh
task build IMAGE=prometheus     # localhost/ubi10-prometheus:dev
task run IMAGE=prometheus -- --version
task inspect IMAGE=prometheus
```

A version bump changes `ARG VERSION` and both `ARG SHA256_*` values together; a stale checksum
fails the build.
