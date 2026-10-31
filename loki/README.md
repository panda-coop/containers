# ubi10-loki

[Grafana Loki](https://github.com/grafana/loki) on Red Hat UBI 10 micro: the upstream release
binary `loki`, checksum-verified against the release's `SHA256SUMS`, rebuilt on UBI updates.

Built from github.com/panda-coop/containers. Not affiliated with or supported by Red Hat or the
upstream project.

| Item | Value |
|---|---|
| Image | `quay.io/panda-coop/ubi10-loki` |
| Upstream | `grafana/loki`, version in `ARG VERSION` of the [Containerfile](Containerfile) |
| Base | `registry.access.redhat.com/ubi10/ubi-micro`, pinned by digest |
| Architectures | `amd64`, `arm64` (both checksums pinned; CI publishes `amd64`) |
| User | `10001:10001`, as upstream (numeric; no `/etc/passwd` entry) |
| Licence | AGPL-3.0-only, some directories Apache-2.0; upstream `LICENSE` and `LICENSING.md` in `/licenses/loki/` |

## Source

Loki is AGPL-3.0. The binary is upstream's, unmodified; its corresponding source is the
upstream release tag, which the image's `org.opencontainers.image.source` label names:

```sh
podman image inspect quay.io/panda-coop/ubi10-loki:3 \
  --format '{{ index .Labels "org.opencontainers.image.source" }}'
# https://github.com/grafana/loki/tree/v3.7.8
```

This repository's build files are at the `url` and `vcs-ref` labels.

## Tags

| Tag | Example | Moves |
|---|---|---|
| `x.y.z-<epoch>` | `3.7.8-<epoch>` | never |
| `x.y.z` | `3.7.8` | on a UBI rebuild |
| `x.y` | `3.7` | on a patch release |
| `x` | `3` | on a minor release |
| `latest` | | on every release |

See [ADR 0001](../docs/decisions/0001-image-tags-version-release-timestamp.md).

## Runtime

| Item | Value |
|---|---|
| Entrypoint | `/usr/bin/loki` |
| Command | `-config.file=/etc/loki/local-config.yaml`, as upstream |
| Port | `3100/tcp` (HTTP); gRPC `9095` is not exposed, as upstream |
| Volume | None declared, as upstream; `/loki`, `/loki/rules` and `/loki/rules-temp` exist, owned by `10001` |
| Configuration | None in the image: mount `/etc/loki/local-config.yaml`. Upstream's image ships a single-binary filesystem config; this one does not, so a bare `podman run` exits with "does not exist, set config.file" |
| Also included | The CA bundle at `/etc/pki/tls/certs/ca-bundle.crt` and `/usr/share/zoneinfo`, copied from the UBI minimal download stage (ubi-micro has neither; upstream's distroless image has both) |

## Example

```sh
podman volume create loki-data
podman run -d --name loki -p 3100:3100 \
  -v ./loki.yaml:/etc/loki/local-config.yaml:ro,Z \
  -v loki-data:/loki \
  quay.io/panda-coop/ubi10-loki:3
```

## Local build

```sh
task build IMAGE=loki     # localhost/ubi10-loki:dev
task run IMAGE=loki -- -version
task inspect IMAGE=loki
```

A version bump changes `ARG VERSION` and both `ARG SHA256_*` values together; a stale checksum
fails the build. The release zip holds only the binary, so `LICENSE` and `LICENSING.md` are
fetched from the release tag and are not checksum-pinned. The CA bundle and time zones follow
`ARG DOWNLOAD_IMAGE`, so they move when Renovate bumps that digest, not on the scheduled base
rebuild.
