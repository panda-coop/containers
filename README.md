# containers

Public container images on Red Hat Universal Base Image 10, built from upstream releases and
published to [quay.io/panda-coop](https://quay.io/organization/panda-coop). GitHub Actions
builds every image on pull requests and pushes it from `main`; a scheduled job rebuilds an image
when its UBI base changes.

Not affiliated with or supported by Red Hat or the upstream projects.

## Images

| Directory | Image | Base | Upstream licence | Status |
|---|---|---|---|---|
| `envoy/` | `quay.io/panda-coop/ubi10-envoy` | `ubi10/ubi-minimal` | Apache-2.0 | planned |
| `prometheus/` | `quay.io/panda-coop/ubi10-prometheus` | `ubi10/ubi-micro` | Apache-2.0 | planned |
| `alertmanager/` | `quay.io/panda-coop/ubi10-alertmanager` | `ubi10/ubi-micro` | Apache-2.0 | planned |
| `loki/` | `quay.io/panda-coop/ubi10-loki` | `ubi10/ubi-micro` | AGPL-3.0 | planned |
| `tempo/` | `quay.io/panda-coop/ubi10-tempo` | `ubi10/ubi-micro` | AGPL-3.0 | planned |
| `perses/` | `quay.io/panda-coop/ubi10-perses` | `ubi10/ubi-minimal` | Apache-2.0 | planned |
| `alloy/` | `quay.io/panda-coop/ubi10-alloy` | `ubi10/ubi-micro` | Apache-2.0 | planned |
| `kafka/` | `quay.io/panda-coop/ubi10-kafka` | `ubi10/openjdk-*-runtime` | Apache-2.0 | planned |
| `postgresql/` | `quay.io/panda-coop/ubi10-postgresql` | `ubi10/ubi-minimal` | PostgreSQL | planned |
| `valkey/` | `quay.io/panda-coop/ubi10-valkey` | `ubi10/ubi-minimal` | BSD-3-Clause | planned |
| `garage/` | `quay.io/panda-coop/ubi10-garage` | `ubi10/ubi-micro` | AGPL-3.0 | planned |
| `traefik/` | `quay.io/panda-coop/ubi10-traefik` | `ubi10/ubi-micro` | MIT | planned |
| `clickhouse/` | `quay.io/panda-coop/ubi10-clickhouse` | `ubi10/ubi-minimal` | Apache-2.0 | planned |

Upstream licences are verified at the pinned version before an image's first public push. A
directory is an image when it holds a `Containerfile`; each one also has a `.containerignore`
and a `README.md`.

## Tags

| Tag | Moves |
|---|---|
| `x.y.z-<epoch>` | never; `<epoch>` is the Unix build time |
| `x.y.z` | on a UBI rebuild |
| `x.y` | on a patch release |
| `x` | on a minor release; not published for a 0.x upstream, where `0.y` is the floating major |
| `latest` | on every release |

Pin `x.y.z-<epoch>` or a digest in production. Reasoning: [ADR 0001](docs/decisions/0001-image-tags-version-release-timestamp.md).

## How an image is built

| Rule | Detail |
|---|---|
| Upstream version | `ARG VERSION` in the image's `Containerfile` |
| Download | A stage on `ubi10/ubi-minimal` fetches the release and checks the sha256 pinned next to `ARG VERSION` |
| Base | Pinned by digest |
| Runtime | Non-root user; no configuration inside the image |
| Labels | `name`, `vendor`, `summary`, `description`, `url`, `maintainer` are ours; inherited `com.redhat.*` labels are blanked; `org.opencontainers.image.*` carry source, licence, version and revision |
| Licences | Upstream `LICENSE` and `NOTICE` in `/licenses/<software>/` |

## Local use

Requires [go-task](https://taskfile.dev), rootless Podman and [prek](https://github.com/j178/prek).

```sh
task lint    # the validation gate (prek)
```

## Licence

This repository's own files are licensed under the Apache License 2.0 (see `LICENSE`). Each
image carries its upstream licence in `/licenses/`.
