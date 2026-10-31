# ubi10-alertmanager

[Prometheus Alertmanager](https://github.com/prometheus/alertmanager) on Red Hat UBI 10 micro:
the upstream release binaries `alertmanager` and `amtool`, checksum-verified against the
release's `sha256sums.txt`, rebuilt on UBI updates.

Built from github.com/panda-coop/containers. Not affiliated with or supported by Red Hat or the
upstream project.

| Item | Value |
|---|---|
| Image | `quay.io/panda-coop/ubi10-alertmanager` |
| Upstream | `prometheus/alertmanager`, version in `ARG VERSION` of the [Containerfile](Containerfile) |
| Base | `registry.access.redhat.com/ubi10/ubi-micro`, pinned by digest |
| Architectures | `amd64`, `arm64` (both checksums pinned; CI publishes `amd64`) |
| User | `65534:65534` (`nobody`, as upstream) |
| Licence | Apache-2.0; upstream `LICENSE` and `NOTICE` in `/licenses/alertmanager/` |

## Tags

| Tag | Example | Moves |
|---|---|---|
| `x.y.z-<epoch>` | `0.34.1-<epoch>` | never |
| `x.y.z` | `0.34.1` | on a UBI rebuild |
| `x.y` | `0.34` | on a patch release; the floating major of a 0.x upstream |
| `latest` | | on every release |

No `0` tag while upstream is 0.x. See [ADR 0001](../docs/decisions/0001-image-tags-version-release-timestamp.md).

## Runtime

| Item | Value |
|---|---|
| Entrypoint | `/bin/alertmanager` |
| Command | `--config.file=/etc/alertmanager/alertmanager.yml --storage.path=/alertmanager`, as upstream |
| Port | `9093/tcp`; the cluster port `9094` is not exposed, as upstream |
| Volume | `/alertmanager` (silences, notification log), owned by `65534`, group-writable |
| Configuration | None in the image: mount `/etc/alertmanager/alertmanager.yml`. Upstream's image ships an example config; this one does not, so a bare `podman run` exits with "error loading configuration file" |
| Also included | `/bin/amtool`; the CA bundle at `/etc/pki/tls/certs/ca-bundle.crt` and `/usr/share/zoneinfo`, copied from the UBI minimal download stage (ubi-micro has neither; upstream's image has both) |

## Example

```sh
podman volume create alertmanager-data
podman run -d --name alertmanager -p 9093:9093 \
  -v ./alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro,Z \
  -v alertmanager-data:/alertmanager \
  quay.io/panda-coop/ubi10-alertmanager:0.34

podman run --rm --entrypoint /bin/amtool \
  -v ./alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro,Z \
  quay.io/panda-coop/ubi10-alertmanager:0.34 check-config /etc/alertmanager/alertmanager.yml
```

Extra flags replace the default command, so repeat `--config.file` and `--storage.path` when
adding one (for example `--cluster.listen-address=`).

## Local build

```sh
task build IMAGE=alertmanager     # localhost/ubi10-alertmanager:dev
task run IMAGE=alertmanager -- --version
task inspect IMAGE=alertmanager
```

A version bump changes `ARG VERSION` and both `ARG SHA256_*` values together; a stale checksum
fails the build. The CA bundle and time zones follow `ARG DOWNLOAD_IMAGE`, so they move when
Renovate bumps that digest, not on the scheduled base rebuild.
