# Getting started

Every image is public on [quay.io/panda-coop](https://quay.io/organization/panda-coop) as
`quay.io/panda-coop/ubi10-<image>`, built from upstream's release on Red Hat Universal Base
Image 10. No login is needed to pull.

## Pull an image

```sh
podman pull quay.io/panda-coop/ubi10-prometheus:3.15.0
```

`docker pull` works the same. The image list is in the navigation on the left; each image's page
has its tags, its packages and its Containerfile.

## Pick a tag

| Tag | Example | Moves |
|---|---|---|
| `<version>-<epoch>` | `3.15.0-1794229146` | Never: one build, for good |
| `<version>` | `3.15.0` | On a rebuild of the same version on a newer UBI base |
| `<major>.<minor>`, `<major>` | `3.15`, `3` | On an upstream release of that line |
| `latest` | | On every release |

For anything that must not change under you, pin the `<version>-<epoch>` tag or the digest:

```sh
podman pull quay.io/panda-coop/ubi10-prometheus@sha256:<digest>
```

A 0.x version has no `0` tag, and a four-part version such as ClickHouse's has no first-part
tag; the [tag rules](https://github.com/panda-coop/containers#tags) list every case.

## Verify the signature

Every image is signed keyless with [cosign](https://github.com/sigstore/cosign) by this
repository's GitHub Actions workflows:

```sh
cosign verify quay.io/panda-coop/ubi10-prometheus:3.15.0 \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --certificate-identity-regexp '^https://github\.com/panda-coop/containers/\.github/workflows/(publish|release|rebuild)\.yml@refs/heads/main$'
```

## Read the SBOM

Each image carries an SPDX SBOM as a signed attestation:

```sh
cosign verify-attestation --type spdxjson quay.io/panda-coop/ubi10-prometheus:3.15.0 \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --certificate-identity-regexp '^https://github\.com/panda-coop/containers/\.github/workflows/(publish|release|rebuild)\.yml@refs/heads/main$' \
  | jq -r .payload | base64 -d | jq '.predicate.packages[] | {name, versionInfo}'
```

## Run it

The images run as a non-root user and hold no configuration: mount yours, and keep data on a
volume. Each image's README, linked from its page as **Source**, has its user, ports, volumes
and an example.

## Stay current

The images are rebuilt when Red Hat updates their UBI base, checked hourly, and on every upstream
version bump. The floating tags follow; a pinned `<version>-<epoch>` tag does not, so move the
pin when a newer release appears on the image's page. [Image health](health.md) grades
every image's `:latest` daily.
