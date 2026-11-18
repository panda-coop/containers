# ubi10-mailpit

[Mailpit](https://mailpit.axllent.org) on Red Hat UBI 10 micro: the upstream static release
binary `mailpit`, checksum-verified, rebuilt on UBI updates.

An SMTP mail catcher for development and testing: every message sent to it stays in Mailpit,
readable in its web UI and REST API. Nothing is delivered onwards unless a relay is configured.

Built from github.com/panda-coop/containers. Not affiliated with or supported by Red Hat or the
upstream project.

| Item | Value |
|---|---|
| Image | `quay.io/panda-coop/ubi10-mailpit` |
| Upstream | `axllent/mailpit`, version in `ARG VERSION` of the [Containerfile](Containerfile) |
| Download | `mailpit-linux-<arch>.tar.gz` from the GitHub release (statically linked) |
| Checksums | Upstream publishes no checksum file. The pinned sha256 values are GitHub's asset digests for the two archives; a download that differs fails the build |
| Base | `registry.access.redhat.com/ubi10/ubi-micro`, pinned by digest; the binary is static |
| Architectures | `amd64`, `arm64` (both checksums pinned; CI publishes `amd64`) |
| User | `1001:1001`, a fixed owner for the data volume (not `65534`: captured mail owned by `nobody` is readable by every other `nobody` process; upstream's image runs as root) |
| Licence | MIT; upstream `LICENSE` from the release archive in `/licenses/mailpit/` |
| Time zones | `/usr/share/zoneinfo` from UBI `tzdata` (ubi-micro has none), so `TZ` works, as in upstream's image |
| CA bundle | `/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem`, copied from UBI `ca-certificates` (ubi-micro has none), for a relay or forward target over TLS |

## Tags

| Tag | Example | Moves |
|---|---|---|
| `x.y.z-<epoch>` | `1.34.0-<epoch>` | never |
| `x.y.z` | `1.34.0` | on a UBI rebuild |
| `x.y` | `1.34` | on a patch release |
| `x` | `1` | on a minor release |
| `latest` | | on every release |

See [ADR 0001](../docs/decisions/0001-image-tags-version-release-timestamp.md).

## Runtime

| Item | Value |
|---|---|
| Entrypoint | `/usr/bin/mailpit`; arguments are its flags or a subcommand (`version`, `readyz`, `dump`, `reindex`) |
| Command | None; upstream's defaults |
| Ports | `1025/tcp` SMTP, `8025/tcp` web UI and API (`/api/v1/`), as upstream; POP3 (`1110`) is off unless `MP_POP3_AUTH_FILE` is set |
| Volume | `/var/lib/mailpit`, mode `0700`, owner `1001:1001` |
| Database | `MP_DATABASE=/var/lib/mailpit/mailpit.db`, the only default; upstream's default is a temporary file lost with the container. Upstream keeps the newest 500 messages (`MP_MAX_MESSAGES`) |
| Configuration | None in the image: `MP_*` environment (every flag has one) or flags |
| Health | `HEALTHCHECK` runs `mailpit readyz` every 15 s, as upstream; it follows `MP_UI_BIND_ADDR` and `MP_WEBROOT`. Docker format keeps it; a Quadlet takes it over unless `HealthCmd` overrides it |
| Bind mount | The host directory must be owned by `1001` inside the user namespace: `Volume=/srv/mailpit:/var/lib/mailpit:Z,U` |

Mailpit accepts any sender and recipient and, by default, needs no SMTP or UI login. On a shared
host set `MP_UI_AUTH_FILE` (an htpasswd file, mounted) and keep both ports off the internet;
Mailpit warns at start when the UI has no authentication.

## Example

```sh
podman volume create mailpit-data
podman run -d --name mailpit --network mail \
  -p 127.0.0.1:8025:8025 \
  -v mailpit-data:/var/lib/mailpit \
  quay.io/panda-coop/ubi10-mailpit:1
```

Clients send to `mailpit:1025` without TLS or authentication; the UI is on
`http://localhost:8025`. One message through SMTP, read back through the API:

```sh
printf 'From: app@example.org\r\nTo: user@example.net\r\nSubject: test\r\n\r\nhello\r\n' \
  | curl -sS --url smtp://127.0.0.1:1025 --mail-from app@example.org --mail-rcpt user@example.net -T -
curl -s localhost:8025/api/v1/messages | jq '.total, [.messages[].Subject]'
```

(The SMTP line needs `-p 127.0.0.1:1025:1025` as well, or run it from a container on `mail`.)

## Local build

```sh
task build IMAGE=mailpit     # localhost/ubi10-mailpit:dev
task run IMAGE=mailpit -- version
task inspect IMAGE=mailpit
```

A version bump changes `ARG VERSION` and both `ARG SHA256_*` values together; take them from the
`digest` of the `mailpit-linux-amd64.tar.gz` and `mailpit-linux-arm64.tar.gz` assets
(`gh release view v<version> -R axllent/mailpit --json assets -q '.assets[]|.name+" "+.digest'`),
or `sha256sum` the downloads. A stale checksum fails the build.
