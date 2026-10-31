# ubi10-valkey

[Valkey](https://github.com/valkey-io/valkey) on Red Hat UBI 10 minimal: compiled from the
upstream release tarball, checksum-verified against
[valkey-io/valkey-hashes](https://github.com/valkey-io/valkey-hashes), rebuilt on UBI updates.

Built from github.com/panda-coop/containers. Not affiliated with or supported by Red Hat or the
upstream project.

| Item | Value |
|---|---|
| Image | `quay.io/panda-coop/ubi10-valkey` |
| Upstream | `valkey-io/valkey`, version in `ARG VERSION` of the [Containerfile](Containerfile) |
| Base | `registry.access.redhat.com/ubi10/ubi-minimal`, pinned by digest, for the build stage and the image |
| Build | `gcc`, `make`, `openssl-devel` from UBI BaseOS and AppStream only; `BUILD_TLS=yes`, bundled jemalloc |
| Source changes | Protected mode off by default, as the upstream `valkey/valkey` image |
| Architectures | `amd64`, `arm64` (one source checksum; CI publishes `amd64`) |
| User | `999:999`, as upstream; no `/etc/passwd` entry |
| Licence | BSD-3-Clause; upstream `COPYING` in `/licenses/valkey/` |

## Tags

| Tag | Example | Moves |
|---|---|---|
| `x.y.z-<epoch>` | `9.1.3-<epoch>` | never |
| `x.y.z` | `9.1.3` | on a UBI rebuild |
| `x.y` | `9.1` | on a patch release |
| `x` | `9` | on a minor release |
| `latest` | | on every release |

See [ADR 0001](../docs/decisions/0001-image-tags-version-release-timestamp.md).

## Runtime

| Item | Value |
|---|---|
| Entrypoint | `/usr/bin/valkey-server` |
| Command | None: the built-in defaults, with protected mode off |
| Port | `6379/tcp` |
| Volume | `/data` (working directory, RDB and AOF), owned by `999`, group-writable |
| Configuration | None in the image: pass flags, or mount a config file and pass its path as the first argument |
| Also included | `valkey-cli`, `valkey-benchmark`, `valkey-check-aof`, `valkey-check-rdb`, `valkey-sentinel`, and the `redis-*` symlinks |

### Differences from `valkey/valkey`

| Item | `valkey/valkey` | This image |
|---|---|---|
| Entrypoint | `tini` + `docker-entrypoint.sh`, command `valkey-server` | `valkey-server` directly |
| Arguments | `valkey-server --flag` or `--flag` | `--flag` only; a leading `valkey-server` is read as a config file path |
| Other commands | `podman run valkey/valkey valkey-cli` | `--entrypoint valkey-cli`, or `podman exec` |
| `--user 0` | chowns `/data`, drops to `999` | runs as root |
| `VALKEY_EXTRA_FLAGS` | appended to the command | not supported |
| umask | `0077` | `0022` |
| systemd notify | `USE_SYSTEMD=yes` | not built |

## Example

```sh
podman volume create valkey-data
podman run -d --name valkey -p 6379:6379 \
  -v valkey-data:/data \
  quay.io/panda-coop/ubi10-valkey:9 --appendonly yes --requirepass change-me

podman exec valkey valkey-cli -a change-me ping

podman run -d --name valkey -p 6379:6379 \
  -v ./valkey.conf:/etc/valkey/valkey.conf:ro,Z -v valkey-data:/data \
  quay.io/panda-coop/ubi10-valkey:9 /etc/valkey/valkey.conf
```

## Local build

```sh
task build IMAGE=valkey     # localhost/ubi10-valkey:dev
task run IMAGE=valkey -- --version
task inspect IMAGE=valkey
```

A version bump changes `ARG VERSION` and `ARG SHA256` together; take the sha256 from
`valkey-io/valkey-hashes` (the same value the upstream image pins). A stale checksum fails the
build.
