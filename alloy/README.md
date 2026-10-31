# ubi10-alloy

[Grafana Alloy](https://github.com/grafana/alloy) on Red Hat UBI 10 minimal: the upstream
release binary `alloy`, checksum-verified against the release's `SHA256SUMS`, rebuilt on UBI
updates.

Built from github.com/panda-coop/containers. Not affiliated with or supported by Red Hat or the
upstream project.

| Item | Value |
|---|---|
| Image | `quay.io/panda-coop/ubi10-alloy` |
| Upstream | `grafana/alloy`, version in `ARG VERSION` of the [Containerfile](Containerfile) |
| Base | `registry.access.redhat.com/ubi10/ubi-minimal`, pinned by digest |
| Architectures | `amd64`, `arm64` (both checksums pinned; CI publishes `amd64`) |
| User | `473:473` (upstream creates this uid but runs as root) |
| Licence | Apache-2.0, one file MIT; upstream `LICENSE` and `LICENSING.md` in `/licenses/alloy/` |

## Why ubi-minimal

The release binary is built with `CGO_ENABLED=1` (tags `netgo embedalloyui
promtail_journal_enabled`): it links glibc dynamically and loads `libsystemd` for
`loki.source.journal`. Upstream's image is Ubuntu with `libsystemd0`, `tzdata` and
`ca-certificates` added. ubi-minimal already has `systemd-libs` and `ca-certificates`; the
image adds `tzdata`.

## Tags

| Tag | Example | Moves |
|---|---|---|
| `x.y.z-<epoch>` | `1.20.1-<epoch>` | never |
| `x.y.z` | `1.20.1` | on a UBI rebuild |
| `x.y` | `1.20` | on a patch release |
| `x` | `1` | on a minor release |
| `latest` | | on every release |

See [ADR 0001](../docs/decisions/0001-image-tags-version-release-timestamp.md).

## Runtime

| Item | Value |
|---|---|
| Entrypoint | `/bin/alloy` |
| Command | `run /etc/alloy/config.alloy --storage.path=/var/lib/alloy/data`, as upstream |
| Environment | `ALLOY_DEPLOY_MODE=docker`, as upstream |
| Port | None declared, as upstream; the UI and API listen on `127.0.0.1:12345` unless `--server.http.listen-addr` says otherwise |
| Volume | None declared, as upstream; `/var/lib/alloy/data` and `/var/lib/alloy/supervisor` exist, owned by `473`, mode `0770` |
| Configuration | None in the image: mount `/etc/alloy/config.alloy`. Upstream's image ships an example config; this one does not, so a bare `podman run` exits with "reading config path" |
| User | Non-root, unlike upstream. Tailing host logs or the journal needs `473` (or a supplementary group) to be able to read them |
| Not included | Upstream's `/bin/otelcol` and `/bin/otel-supervisor` wrapper scripts; they live in the source tree, not the release |

## Example

```sh
podman volume create alloy-data
podman run -d --name alloy -p 12345:12345 \
  -v ./config.alloy:/etc/alloy/config.alloy:ro,Z \
  -v alloy-data:/var/lib/alloy/data \
  quay.io/panda-coop/ubi10-alloy:1 \
  run /etc/alloy/config.alloy --storage.path=/var/lib/alloy/data \
  --server.http.listen-addr=0.0.0.0:12345
```

Extra flags replace the default command, so repeat `run <config>` and `--storage.path` when
adding one.

## Local build

```sh
task build IMAGE=alloy     # localhost/ubi10-alloy:dev
task run IMAGE=alloy -- --version
task inspect IMAGE=alloy
```

A version bump changes `ARG VERSION` and both `ARG SHA256_*` values together; a stale checksum
fails the build. The release zip holds only the binary, so `LICENSE` and `LICENSING.md` are
fetched from the release tag and are not checksum-pinned.
