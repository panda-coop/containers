# ubi10-garage

[Garage](https://garagehq.deuxfleurs.fr/) on Red Hat UBI 10 micro: the upstream static (musl)
release binary `garage`, checksum-verified, rebuilt on UBI updates.

Built from github.com/panda-coop/containers. Not affiliated with or supported by Red Hat or the
upstream project.

| Item | Value |
|---|---|
| Image | `quay.io/panda-coop/ubi10-garage` |
| Upstream | `Deuxfleurs/garage` on [git.deuxfleurs.fr](https://git.deuxfleurs.fr/Deuxfleurs/garage), version in `ARG VERSION` of the [Containerfile](Containerfile) |
| Download | `https://garagehq.deuxfleurs.fr/_releases/v<version>/<target>/garage`, targets `x86_64-unknown-linux-musl` and `aarch64-unknown-linux-musl` (statically linked) |
| Checksums | Upstream publishes none. The pinned sha256 values were computed from the first download of each binary; a later download that differs fails the build |
| Base | `registry.access.redhat.com/ubi10/ubi-micro`, pinned by digest |
| Architectures | `amd64`, `arm64` (both checksums pinned; CI publishes `amd64`) |
| User | `65534:65534` (`nobody`; upstream's scratch image runs as root) |
| Licence | AGPL-3.0; upstream `LICENSE` from the release tag in `/licenses/garage/`. The `org.opencontainers.image.source` label points at that tag, `https://git.deuxfleurs.fr/Deuxfleurs/garage/src/tag/v<version>` |

Renovate tracks the version through the upstream git tags on git.deuxfleurs.fr (`gitea-tags`
datasource; the Forgejo server speaks the Gitea API).

## Tags

| Tag | Example | Moves |
|---|---|---|
| `x.y.z-<epoch>` | `2.5.0-<epoch>` | never |
| `x.y.z` | `2.5.0` | on a UBI rebuild |
| `x.y` | `2.5` | on a patch release |
| `x` | `2` | on a minor release |
| `latest` | | on every release |

See [ADR 0001](../docs/decisions/0001-image-tags-version-release-timestamp.md).

## Runtime

| Item | Value |
|---|---|
| Entrypoint | `/usr/bin/garage`; `/garage` is a symlink to it, so `podman exec <name> /garage status` works as with upstream's image |
| Command | `server`, as upstream |
| Ports | `3900/tcp` S3 API, `3901/tcp` RPC, `3902/tcp` S3 web, `3903/tcp` admin API |
| Volumes | `/var/lib/garage/meta`, `/var/lib/garage/data`, owned by `65534`, group-writable |
| Environment | `RUST_BACKTRACE=1`, `RUST_LOG=garage=info`, as upstream |
| Configuration | None in the image: mount `/etc/garage.toml` (Garage's default path), with `metadata_dir` and `data_dir` pointing at the volumes |

Upstream's image has `CMD ["/garage", "server"]` and no entrypoint; here the entrypoint is the
binary, so `podman run ... /garage status` becomes `podman run ... status`.

## Example

```sh
podman volume create garage-meta
podman volume create garage-data
podman run -d --name garage -p 3900:3900 -p 3901:3901 -p 3902:3902 -p 3903:3903 \
  -v ./garage.toml:/etc/garage.toml:ro,Z \
  -v garage-meta:/var/lib/garage/meta \
  -v garage-data:/var/lib/garage/data \
  quay.io/panda-coop/ubi10-garage:2

podman exec garage /garage status
```

## Local build

```sh
task build IMAGE=garage     # localhost/ubi10-garage:dev
task run IMAGE=garage -- --version
task inspect IMAGE=garage
```

A version bump changes `ARG VERSION` and both `ARG SHA256_*` values together. With no upstream
checksums, compute them from the new release's binaries (`curl -fsSL <url> | sha256sum`) and
record that in the commit. A stale checksum fails the build.
