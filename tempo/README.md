# ubi10-tempo

[Grafana Tempo](https://github.com/grafana/tempo) on Red Hat UBI 10 micro: the upstream release
binary `tempo`, checksum-verified against the release's `SHA256SUMS`, rebuilt on UBI updates.

Built from github.com/panda-coop/containers. Not affiliated with or supported by Red Hat or the
upstream project.

| Item | Value |
|---|---|
| Image | `quay.io/panda-coop/ubi10-tempo` |
| Upstream | `grafana/tempo`, version in `ARG VERSION` of the [Containerfile](Containerfile) |
| Base | `registry.access.redhat.com/ubi10/ubi-micro`, pinned by digest |
| Architectures | `amd64`, `arm64` (both checksums pinned; CI publishes `amd64`) |
| User | `10001:10001`, as upstream (numeric; no `/etc/passwd` entry) |
| Licence | AGPL-3.0-only, some directories Apache-2.0; upstream `LICENSE` and `LICENSING.md` in `/licenses/tempo/` |

## Source

Tempo is AGPL-3.0. The binary is upstream's, unmodified; its corresponding source is the
upstream release tag, which the image's `org.opencontainers.image.source` label names:

```sh
podman image inspect quay.io/panda-coop/ubi10-tempo:3 \
  --format '{{ index .Labels "org.opencontainers.image.source" }}'
# https://github.com/grafana/tempo/tree/v3.1.0
```

This repository's build files are at the `url` and `vcs-ref` labels.

## Tags

| Tag | Example | Moves |
|---|---|---|
| `x.y.z-<epoch>` | `3.1.0-<epoch>` | never |
| `x.y.z` | `3.1.0` | on a UBI rebuild |
| `x.y` | `3.1` | on a patch release |
| `x` | `3` | on a minor release |
| `latest` | | on every release |

See [ADR 0001](../docs/decisions/0001-image-tags-version-release-timestamp.md).

## Runtime

| Item | Value |
|---|---|
| Entrypoint | `/tempo`, as upstream (a symlink to `/usr/bin/tempo`) |
| Command | None, as upstream: pass `-config.file=...` |
| Ports | None declared, as upstream; the defaults are `3200/tcp` (HTTP), `9095/tcp` (gRPC), and OTLP `4317`/`4318` when the receiver is configured |
| Volume | None declared, as upstream; `/var/tempo` exists, owned by `10001`, mode `0700` |
| Configuration | None in the image: mount one and pass `-config.file`. Without it Tempo exits with "unknown backend" |
| Not included | `tempo-cli` and `tempo-query` from the same tarball; upstream's image leaves them out too |
| Also included | The CA bundle at `/etc/pki/tls/certs/ca-bundle.crt` and `/usr/share/zoneinfo`, copied from the UBI minimal download stage (ubi-micro has neither; upstream's image has both) |

## Example

```sh
podman volume create tempo-data
podman run -d --name tempo -p 3200:3200 -p 4317:4317 -p 4318:4318 \
  -v ./tempo.yaml:/etc/tempo/tempo.yaml:ro,Z \
  -v tempo-data:/var/tempo \
  quay.io/panda-coop/ubi10-tempo:3 -config.file=/etc/tempo/tempo.yaml
```

## Local build

```sh
task build IMAGE=tempo     # localhost/ubi10-tempo:dev
task run IMAGE=tempo -- --version
task inspect IMAGE=tempo
```

A version bump changes `ARG VERSION` and both `ARG SHA256_*` values together; a stale checksum
fails the build. `LICENSING.md` is fetched from the release tag and is not checksum-pinned. The
CA bundle and time zones follow `ARG DOWNLOAD_IMAGE`, so they move when Renovate bumps that
digest, not on the scheduled base rebuild.
