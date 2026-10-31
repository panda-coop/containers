# ubi10-perses

[Perses](https://github.com/perses/perses) on Red Hat UBI 10 minimal: the upstream release
archive (the `perses` server with its web UI embedded, `percli`, and the bundled plugins),
checksum-verified against the release's `perses_<version>_checksums.txt`, rebuilt on UBI updates.

Built from github.com/panda-coop/containers. Not affiliated with or supported by Red Hat or the
upstream project.

| Item | Value |
|---|---|
| Image | `quay.io/panda-coop/ubi10-perses` |
| Upstream | `perses/perses`, version in `ARG VERSION` of the [Containerfile](Containerfile) |
| Base | `registry.access.redhat.com/ubi10/ubi-minimal`, pinned by digest |
| Architectures | `amd64`, `arm64` (both checksums pinned; CI publishes `amd64`) |
| User | `65532:65532` (distroless `nonroot`, as upstream) |
| Licence | Apache-2.0; upstream `LICENSE` in `/licenses/perses/` (upstream has no `NOTICE`). The bundled plugins are Apache-2.0 and carry their own `LICENSE` inside each archive |

## Tags

| Tag | Example | Moves |
|---|---|---|
| `x.y.z-<epoch>` | `0.54.0-<epoch>` | never |
| `x.y.z` | `0.54.0` | on a UBI rebuild |
| `x.y` | `0.54` | on a patch release; the floating major of a 0.x upstream |
| `latest` | | on every release |

No `0` tag while upstream is 0.x. See [ADR 0001](../docs/decisions/0001-image-tags-version-release-timestamp.md).

## Runtime

| Item | Value |
|---|---|
| Entrypoint | `/bin/perses` |
| Command | `--config=/etc/perses/config.yaml --log.level=error`, as upstream |
| Port | `8080/tcp` |
| Volume | `/perses` (file database), owned by `65532` |
| Plugins | `/etc/perses/plugins-archive/` holds the release's plugin archives (read-only); Perses unpacks them at startup into `/etc/perses/plugins/`, owned by `65532`. Both are the in-container defaults Perses picks when the config names no plugin paths |
| Configuration | None in the image: mount `/etc/perses/config.yaml`. Upstream's image ships one pointing the file database at `/perses`; this one does not, so a bare `podman run` exits on the missing config |
| Also included | `/bin/percli`; `/etc/mime.types` from `mailcap`, as upstream adds it |

The server has no `--version` flag; `percli version` prints the client version, and
`GET /api/v1/health` the server's.

## Example

Upstream's `config.docker.yaml`, the minimum for a file database:

```yaml
database:
  file:
    folder: "/perses"
    extension: "json"
```

```sh
podman volume create perses-data
podman run -d --name perses -p 8080:8080 \
  -v ./perses.yaml:/etc/perses/config.yaml:ro,Z \
  -v perses-data:/perses \
  quay.io/panda-coop/ubi10-perses:0.54

curl -s localhost:8080/api/v1/health
```

## Local build

```sh
task build IMAGE=perses     # localhost/ubi10-perses:dev
podman run --rm --entrypoint /bin/percli localhost/ubi10-perses:dev version
task inspect IMAGE=perses
```

A version bump changes `ARG VERSION` and both `ARG SHA256_*` values together; a stale checksum
fails the build.
