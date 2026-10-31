# ubi10-keycloak

[Keycloak](https://github.com/keycloak/keycloak) on Red Hat UBI 10 OpenJDK 25 runtime: the
upstream release tarball, checked against the release's `.sha1` and its GPG signature, rebuilt on
UBI updates. A port of upstream's
[`quarkus/container/Dockerfile`](https://github.com/keycloak/keycloak/blob/main/quarkus/container/Dockerfile):
same layout (`/opt/keycloak`, UID 1000, GID 0, group-writable), same ports, same entrypoint.

Built from github.com/panda-coop/containers. Not affiliated with or supported by Red Hat or the
upstream project.

| Item | Value |
|---|---|
| Image | `quay.io/panda-coop/ubi10-keycloak` |
| Upstream | `keycloak/keycloak`, version in `ARG VERSION` of the [Containerfile](Containerfile) |
| Base | `registry.access.redhat.com/ubi10/openjdk-25-runtime`, pinned by digest |
| Architectures | `amd64`, `arm64` (one platform-independent tarball) |
| User | `1000:0` (`keycloak`, as upstream) |
| Licence | Apache-2.0; upstream `LICENSE.txt` in `/licenses/keycloak/` |

## Download check

| Arg | Value |
|---|---|
| `VERSION` | Keycloak release tag |
| `SHA1` | Contents of the release's `keycloak-<version>.tar.gz.sha1`; changes with `VERSION` |
| `GPG_FINGERPRINT` | `861AB50E8CC6611FB6BC01A6B8F12EA26FD6EEBA`, Keycloak Bot `<keycloak.bot@gmail.com>` |

Upstream publishes only `.md5`, `.sha1` and `.asc` next to the tarball, so the signature is the
real check. The key is [`keycloak-2.asc`](keycloak-2.asc) in the build context, a copy of
<https://www.keycloak.org/keys/keycloak-2.asc>; the fingerprint is the one listed on
<https://www.keycloak.org/keys> (source: `keycloak/keycloak-web`, `pages/keys.ftl`), and it is the
issuer of the 26.8.1 `.asc`. The same key is on `keyserver.ubuntu.com`; it is not on
`keys.openpgp.org`. The build fails unless gpg reports `VALIDSIG` for that fingerprint.

keycloak.org lists the key for "Maven artifacts after January 2024"; it also signs the release
tarballs. It expires on 2027-02-12: expect a new key or an extended copy of this one before then.

## Run

| Port | Use |
|---|---|
| 8080 | HTTP |
| 8443 | HTTPS |
| 9000 | Management: health (`KC_HEALTH_ENABLED=true`) and metrics |

```sh
podman run --rm -p 8080:8080 -p 9000:9000 \
  -e KC_BOOTSTRAP_ADMIN_USERNAME=admin -e KC_BOOTSTRAP_ADMIN_PASSWORD=change-me \
  -e KC_HEALTH_ENABLED=true \
  quay.io/panda-coop/ubi10-keycloak:latest start-dev
curl http://localhost:9000/health/ready
```

No `kc.sh build` is baked in. For production, build an optimised image on top of this one with your
database, features and providers, then run `start --optimized`.

## How it differs from upstream

| | `quay.io/keycloak/keycloak` | `ubi10-keycloak` |
|---|---|---|
| Base | `ubi9-micro` with a `java-21-openjdk-headless` rootfs copied in | `ubi10/openjdk-25-runtime` |
| JDK | 21 | 25. Keycloak supports OpenJDK 17, 21 and 25 and recommends the newest ([supported configurations](https://www.keycloak.org/server/supported-configurations)) |
| Locale | `en_US.UTF-8` (`glibc-langpack-en`) | the same; the runtime image ships only `C.utf8`, so `glibc-langpack-en` is installed from the UBI repos |
| User | `1000:0` | the same; the base image's user `185` (`default`) stays in `/etc/passwd`, unused |
| Download check | none (`ADD` of the tarball) | `.sha1` and GPG `.asc` |
| Image size | smaller (micro) | larger: the runtime image carries `microdnf` and the JBoss user setup |

The Red Hat build of Keycloak exists only as `registry.redhat.io/rhbk/keycloak-rhel9`, which needs a subscription.

## Local build

```sh
task build IMAGE=keycloak     # localhost/ubi10-keycloak:dev
task run IMAGE=keycloak -- --version
task inspect IMAGE=keycloak
```

## Open

| Question | Note |
|---|---|
| Base size | A micro-based rootfs build like upstream's would be smaller; start with the runtime image |
| Key rotation | The signing key expires 2027-02-12; a rotation changes `keycloak-2.asc` and `GPG_FINGERPRINT` together |
