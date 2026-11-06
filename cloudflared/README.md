# ubi10-cloudflared

[cloudflared](https://github.com/cloudflare/cloudflared) on Red Hat UBI 10 minimal: the
Cloudflare Tunnel connector from Cloudflare's signed RPM repository, `pkg.cloudflare.com`,
rebuilt on UBI updates.

The connector for a remotely-managed tunnel on `lb-01` and `lb-02`: both run a connector of the
same tunnel, so they are active/active replicas, and each forwards to the Envoy on its own host.
The tunnel's routes live in the Cloudflare dashboard, not in the container.

Built from github.com/panda-coop/containers. Not affiliated with or supported by Red Hat or the
upstream project.

| Item | Value |
|---|---|
| Image | `quay.io/panda-coop/ubi10-cloudflared` |
| Upstream | `cloudflare/cloudflared`, version in `ARG VERSION` of the [Containerfile](Containerfile) |
| Package | `cloudflared`, pinned to `VERSION`, from `https://pkg.cloudflare.com/cloudflared/rpm` (upstream's [`cloudflared.repo`](https://pkg.cloudflare.com/cloudflared.repo)) |
| Package check | Signed packages (`gpgcheck=1`) against [`RPM-GPG-KEY-cloudflare`](RPM-GPG-KEY-cloudflare), `CloudFlare Software Packaging 2025`, fingerprint `CC94B39C77AE7342A68B89628A682D308D4E5E73`, the key Cloudflare rolled to on 2025-10-30. The repository metadata is signed with the deprecated 2015 key, which upstream's `.repo` does not distribute, so no `repo_gpgcheck` |
| Base | `registry.access.redhat.com/ubi10/ubi-minimal`, pinned by digest; nothing else is installed |
| Architectures | `amd64`, `arm64` (the repository has both; CI publishes `amd64`) |
| User | `65532:65532`, as upstream's image (distroless `nonroot`) |
| Licence | Apache-2.0; the RPM has no licence file, so upstream `LICENSE` from the release tag (sha256-pinned) in `/licenses/cloudflared/` |
| CA bundle | `/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem`, UBI `ca-certificates`, for the TLS to Cloudflare's edge |

The repository serves only the latest release. A pinned `VERSION` stops building once Cloudflare
publishes the next one, until the Renovate PR for it is merged.

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

The RPM binary is a host build: without `--metrics` it binds `localhost:20241` (the first free of
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

With `Network=host` the tunnel's origin is the host's Envoy as configured in the dashboard, and
the metrics stay on the loopback; use `--metrics 0.0.0.0:2000` with a published port for a
bridge network or a remote scrape.

## Local build

```sh
task build IMAGE=cloudflared     # localhost/ubi10-cloudflared:dev
task run IMAGE=cloudflared -- version
task inspect IMAGE=cloudflared
```

A version bump changes `ARG VERSION`; `ARG LICENSE_SHA256` only when upstream's `LICENSE`
changes, and a stale value fails the build. A Cloudflare key rotation fails the install with
`SIGNATURE: NOT OK`: replace `RPM-GPG-KEY-cloudflare` from `https://pkg.cloudflare.com/cloudflare-main.gpg`
and update the fingerprint here and in [`cloudflared.repo`](cloudflared.repo).
