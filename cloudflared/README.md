# ubi10-cloudflared

[cloudflared](https://github.com/cloudflare/cloudflared) on Red Hat UBI 10 micro: the
Cloudflare Tunnel connector, upstream's static release binary checksum-verified against the
sha256 Cloudflare publishes with the release, rebuilt on UBI updates.

The connector for a remotely-managed tunnel: several hosts may run a connector of the same tunnel
as active/active replicas. The tunnel's routes live in the Cloudflare dashboard, not in the
container.

Built from github.com/panda-coop/containers. Not affiliated with or supported by Red Hat or the
upstream project.

| Item | Value |
|---|---|
| Image | `quay.io/panda-coop/ubi10-cloudflared` |
| Upstream | `cloudflare/cloudflared`, version in `ARG VERSION` of the [Containerfile](Containerfile) |
| Binary | `cloudflared-linux-<arch>` from the GitHub release, a static Go binary (the same file Cloudflare's RPM packages), at `/usr/bin/cloudflared` with the RPM's `/usr/local/bin/cloudflared` link |
| Binary check | `ARG SHA256_AMD64` / `ARG SHA256_ARM64`, the sha256 values in the release notes, which match GitHub's asset digests |
| Base | `registry.access.redhat.com/ubi10/ubi-micro`, pinned by digest; the download stage is `ubi10/ubi-minimal` |
| Architectures | `amd64`, `arm64` (both checksums pinned; CI publishes `amd64`) |
| User | `65532:65532`, as upstream's image (distroless `nonroot`) |
| Licence | Apache-2.0; the release has no licence file, so upstream `LICENSE` from the release tag (sha256-pinned) in `/licenses/cloudflared/` |
| CA bundle | `/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem` (and the `/etc/pki/tls/certs/ca-bundle.crt` link), the download stage's UBI `ca-certificates`, for the TLS to Cloudflare's edge |

Every GitHub release keeps its binaries, so a pinned `VERSION` keeps building after Cloudflare
publishes the next one. Earlier images installed the RPM from `pkg.cloudflare.com`, which serves
only the latest release.

### Changes from the RPM-based image

| Item | RPM-based (`ubi-minimal`) | Now (`ubi-micro`) |
|---|---|---|
| Entrypoint, command, user, `NO_AUTOUPDATE` | `cloudflared`, `version`, `65532:65532`, `true` | unchanged |
| Binary | `/usr/bin/cloudflared`, `/usr/local/bin/cloudflared` link | unchanged, byte-identical for `2026.10.7` |
| CA bundle path | `/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem` | unchanged |
| Package manager | `microdnf`, `rpm` | none: `rpm -q cloudflared` no longer works; `cloudflared version` does |
| Other tools | ubi-minimal's userland, `curl` | ubi-micro's: `bash` and coreutils, no `curl` |
| Man page | `/usr/share/man/man1/cloudflared.1` | none |

## Tags

| Tag | Example | Moves |
|---|---|---|
| `x.y.z-<epoch>` | `2026.10.7-<epoch>` | never |
| `x.y.z` | `2026.10.7` | on a UBI rebuild |
| `x.y` | `2026.10` | on a patch release |
| `x` | `2026` | on a minor release |
| `latest` | | on every release |

See [ADR 0001](../docs/decisions/0001-image-tags-version-release-timestamp.md).

## Runtime

| Item | Value |
|---|---|
| Entrypoint | `cloudflared`; arguments are its command and flags |
| Command | `version`, as upstream |
| Auto-update | Off: `NO_AUTOUPDATE=true` in the image, as upstream. A new version is a new image |
| Configuration | None in the image. A remotely-managed tunnel needs only its token |
| Credentials | `TUNNEL_TOKEN` from a Podman secret (`--secret <name>,type=env,target=TUNNEL_TOKEN`), not `--token`: flags show up in `ps` and `podman inspect` |
| Port | None exposed: the tunnel is outbound only. Metrics are opt-in, below |

### Metrics and readiness

The release binary is a host build: without `--metrics` it binds `localhost:20241` (the first free of
`20241`–`20245`), inside the container's network namespace. Upstream's image is built with
`CONTAINER_BUILD=1` and binds `0.0.0.0` instead; this one does not. To scrape it, pass the address
explicitly, `--metrics 0.0.0.0:2000` (or `TUNNEL_METRICS=0.0.0.0:2000`), and publish the port.

| Path | Use |
|---|---|
| `/metrics` | Prometheus metrics |
| `/ready` | `200` once the connector has at least one connection to the edge, `503` before; the Quadlet health check |

`cloudflared tunnel --metrics 127.0.0.1:2000 ready` calls `/ready` and exits non-zero unless it
returns `200`, so the health check needs no `curl`.

### Updates

Cloudflare supports a `cloudflared` release for one year after it is published; older connectors
are deprecated and can stop connecting. Merge the Renovate PR and roll both connectors, one at a
time, so the tunnel keeps a replica up.

## Example

```sh
printf '%s' "$TUNNEL_TOKEN" | podman secret create cloudflared-token -

podman run -d --name cloudflared --network host \
  --secret cloudflared-token,type=env,target=TUNNEL_TOKEN \
  quay.io/panda-coop/ubi10-cloudflared:2026.10.7 \
  tunnel --no-autoupdate --metrics 127.0.0.1:2000 run
```

As a Quadlet, `/etc/containers/systemd/cloudflared.container`:

```ini
[Container]
Image=quay.io/panda-coop/ubi10-cloudflared:2026.10.7
Network=host
Secret=cloudflared-token,type=env,target=TUNNEL_TOKEN
Exec=tunnel --no-autoupdate --metrics 127.0.0.1:2000 run
HealthCmd=cloudflared tunnel --metrics 127.0.0.1:2000 ready
HealthInterval=30s
HealthStartPeriod=30s

[Service]
Restart=always
```

With `Network=host` the tunnel reaches origins on the host as configured in the dashboard, and
the metrics stay on the loopback; use `--metrics 0.0.0.0:2000` with a published port for a
bridge network or a remote scrape.

## Local build

```sh
task build IMAGE=cloudflared     # localhost/ubi10-cloudflared:dev
task run IMAGE=cloudflared -- version
task inspect IMAGE=cloudflared
```

A version bump changes `ARG VERSION` and both `ARG SHA256_*` values, from the release notes'
checksum list (or `gh api repos/cloudflare/cloudflared/releases/tags/<version>`, each asset's
`digest`); `ARG SHA256_LICENSE` only when upstream's `LICENSE` changes. A stale value fails the
build.
