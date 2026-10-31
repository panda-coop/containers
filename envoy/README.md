# ubi10-envoy

[Envoy](https://github.com/envoyproxy/envoy) on Red Hat UBI 10 minimal: the upstream release
binary `envoy`, checksum-verified against the release's PGP-signed `checksums.txt.asc`,
rebuilt on UBI updates.

Built from github.com/panda-coop/containers. Not affiliated with or supported by Red Hat or the
upstream project.

| Item | Value |
|---|---|
| Image | `quay.io/panda-coop/ubi10-envoy` |
| Upstream | `envoyproxy/envoy`, version in `ARG VERSION` of the [Containerfile](Containerfile) |
| Base | `registry.access.redhat.com/ubi10/ubi-minimal`, pinned by digest; the binary links glibc and libstdc++ dynamically, so not `ubi-micro` |
| Architectures | `amd64`, `arm64` (both checksums pinned; CI publishes `amd64`) |
| User | `65534:65534` (`nobody`; upstream's distroless image uses `65532`) |
| Licence | Apache-2.0; upstream `LICENSE` and `NOTICE` from the release tag in `/licenses/envoy/` |

The release also ships `envoy-contrib-*` binaries with the contrib extensions; this image
packages the core `envoy` binary only.

## Tags

| Tag | Example | Moves |
|---|---|---|
| `x.y.z-<epoch>` | `1.40.2-<epoch>` | never |
| `x.y.z` | `1.40.2` | on a UBI rebuild |
| `x.y` | `1.40` | on a patch release |
| `x` | `1` | on a minor release |
| `latest` | | on every release |

See [ADR 0001](../docs/decisions/0001-image-tags-version-release-timestamp.md).

## Runtime

| Item | Value |
|---|---|
| Entrypoint | `/usr/local/bin/envoy`, as upstream |
| Command | `-c /etc/envoy/envoy.yaml`, as upstream |
| Port | `10000/tcp`, as upstream; the listeners are whatever the configuration declares |
| Configuration | None in the image: mount `/etc/envoy/envoy.yaml`. Upstream's image ships an example config; this one does not, so a bare `podman run` exits with an error loading the config |

Listening below port 1024 as the non-root user needs
`--sysctl net.ipv4.ip_unprivileged_port_start=0` (or ports at or above 1024 published to 80/443).

## Example

```sh
podman run -d --name envoy -p 10000:10000 -p 9901:9901 \
  -v ./envoy.yaml:/etc/envoy/envoy.yaml:ro,Z \
  quay.io/panda-coop/ubi10-envoy:1

podman run --rm -v ./envoy.yaml:/etc/envoy/envoy.yaml:ro,Z \
  quay.io/panda-coop/ubi10-envoy:1 --mode validate -c /etc/envoy/envoy.yaml
```

Extra flags replace the default command, so repeat `-c /etc/envoy/envoy.yaml` when adding one
(for example `--log-level debug`).

## Local build

```sh
task build IMAGE=envoy     # localhost/ubi10-envoy:dev
task run IMAGE=envoy -- --version
task inspect IMAGE=envoy
```

A version bump changes `ARG VERSION` and both `ARG SHA256_*` values together; take them from
the release's `checksums.txt.asc` (`envoy-<version>-linux-x86_64`, `envoy-<version>-linux-aarch_64`).
A stale checksum fails the build.
