# ubi10-traefik

[Traefik](https://github.com/traefik/traefik) on Red Hat UBI 10 micro: the upstream release
binary `traefik`, checksum-verified against the release's `traefik_v<version>_checksums.txt`,
rebuilt on UBI updates.

The development and local-stack reverse proxy; Envoy ([`ubi10-envoy`](../envoy/)) is the
production edge.

Built from github.com/panda-coop/containers. Not affiliated with or supported by Red Hat or the
upstream project.

| Item | Value |
|---|---|
| Image | `quay.io/panda-coop/ubi10-traefik` |
| Upstream | `traefik/traefik`, version in `ARG VERSION` of the [Containerfile](Containerfile) |
| Base | `registry.access.redhat.com/ubi10/ubi-micro`, pinned by digest; the binary is static (`CGO_ENABLED=0`) |
| Architectures | `amd64`, `arm64` (both checksums pinned; CI publishes `amd64`) |
| User | `65534:65534` (`nobody`; upstream's image runs as root) |
| Licence | MIT; upstream `LICENSE.md` from the release archive in `/licenses/traefik/` |
| CA bundle | `/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem`, copied from UBI `ca-certificates` (ubi-micro has none), for ACME and HTTPS backends |

## Tags

| Tag | Example | Moves |
|---|---|---|
| `x.y.z-<epoch>` | `3.7.17-<epoch>` | never |
| `x.y.z` | `3.7.17` | on a UBI rebuild |
| `x.y` | `3.7` | on a patch release |
| `x` | `3` | on a minor release |
| `latest` | | on every release |

See [ADR 0001](../docs/decisions/0001-image-tags-version-release-timestamp.md).

## Runtime

| Item | Value |
|---|---|
| Entrypoint | `/usr/bin/traefik`; arguments are Traefik flags. Upstream's `/entrypoint.sh` wrapper is not included |
| Command | None |
| Port | `80/tcp`, Traefik's default `http` entry point, as upstream |
| Configuration | None in the image: pass flags, or mount `/etc/traefik/traefik.yml` (one of Traefik's default static-config paths) |

The default `:80` entry point needs `--sysctl net.ipv4.ip_unprivileged_port_start=0` as the
non-root user; without it Traefik exits with `bind: permission denied`. Alternatively declare
entry points at or above 1024 and publish them to 80/443.

## Example

```sh
podman run -d --name traefik -p 80:80 -p 8080:8080 \
  --sysctl net.ipv4.ip_unprivileged_port_start=0 \
  -v ./traefik.yml:/etc/traefik/traefik.yml:ro,Z \
  -v ./dynamic:/etc/traefik/dynamic:ro,Z \
  quay.io/panda-coop/ubi10-traefik:3

podman run -d --name traefik -p 80:8000 \
  quay.io/panda-coop/ubi10-traefik:3 \
  --entryPoints.web.address=:8000 --providers.file.directory=/etc/traefik/dynamic
```

The Podman provider (`--providers.docker` against the Podman socket) needs the socket mounted
and readable by UID 65534.

## Local build

```sh
task build IMAGE=traefik     # localhost/ubi10-traefik:dev
task run IMAGE=traefik -- version
task inspect IMAGE=traefik
```

A version bump changes `ARG VERSION` and both `ARG SHA256_*` values together; take them from
the release's `traefik_v<version>_checksums.txt` (sha256). A stale checksum fails the build.
