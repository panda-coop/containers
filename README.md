# containers

[![Build](https://github.com/panda-coop/containers/actions/workflows/build.yml/badge.svg)](https://github.com/panda-coop/containers/actions/workflows/build.yml)
[![Release](https://github.com/panda-coop/containers/actions/workflows/release.yml/badge.svg?branch=main)](https://github.com/panda-coop/containers/actions/workflows/release.yml)
[![Weekly rebuild](https://github.com/panda-coop/containers/actions/workflows/rebuild.yml/badge.svg)](https://github.com/panda-coop/containers/actions/workflows/rebuild.yml)
[![License](https://img.shields.io/github/license/panda-coop/containers)](LICENSE)
[![Renovate](https://img.shields.io/badge/renovate-enabled-brightgreen?logo=renovatebot)](https://github.com/renovatebot/renovate)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/panda-coop/containers/badge)](https://scorecard.dev/viewer/?uri=github.com/panda-coop/containers)
[![Signed with cosign](https://img.shields.io/badge/signed-cosign-2a9d8f?logo=sigstore&logoColor=white)](#verify-an-image)

Public container images on Red Hat Universal Base Image 10, built from upstream releases and
published to [quay.io/panda-coop](https://quay.io/organization/panda-coop). GitHub Actions
builds every image on pull requests and pushes it from `main`; a scheduled job rebuilds an image
when its UBI base changes.

Not affiliated with or supported by Red Hat or the upstream projects.

## Images

| Directory | Quay repository | Base | Upstream licence |
|---|---|---|---|
| [`prometheus/`](prometheus/) | [`quay.io/panda-coop/ubi10-prometheus`](https://quay.io/repository/panda-coop/ubi10-prometheus) | `ubi10/ubi-micro` | `Apache-2.0` |
| [`alertmanager/`](alertmanager/) | [`quay.io/panda-coop/ubi10-alertmanager`](https://quay.io/repository/panda-coop/ubi10-alertmanager) | `ubi10/ubi-micro` | `Apache-2.0` |
| [`loki/`](loki/) | [`quay.io/panda-coop/ubi10-loki`](https://quay.io/repository/panda-coop/ubi10-loki) | `ubi10/ubi-micro` | `AGPL-3.0-only` |
| [`tempo/`](tempo/) | [`quay.io/panda-coop/ubi10-tempo`](https://quay.io/repository/panda-coop/ubi10-tempo) | `ubi10/ubi-micro` | `AGPL-3.0-only` |
| [`alloy/`](alloy/) | [`quay.io/panda-coop/ubi10-alloy`](https://quay.io/repository/panda-coop/ubi10-alloy) | `ubi10/ubi-minimal` | `Apache-2.0` |
| [`perses/`](perses/) | [`quay.io/panda-coop/ubi10-perses`](https://quay.io/repository/panda-coop/ubi10-perses) | `ubi10/ubi-minimal` | `Apache-2.0` |
| [`envoy/`](envoy/) | [`quay.io/panda-coop/ubi10-envoy`](https://quay.io/repository/panda-coop/ubi10-envoy) | `ubi10/ubi-minimal` | `Apache-2.0` |
| [`traefik/`](traefik/) | [`quay.io/panda-coop/ubi10-traefik`](https://quay.io/repository/panda-coop/ubi10-traefik) | `ubi10/ubi-micro` | `MIT` |
| [`garage/`](garage/) | [`quay.io/panda-coop/ubi10-garage`](https://quay.io/repository/panda-coop/ubi10-garage) | `ubi10/ubi-micro` | `AGPL-3.0` |
| [`kafka/`](kafka/) | [`quay.io/panda-coop/ubi10-kafka`](https://quay.io/repository/panda-coop/ubi10-kafka) | `ubi10/openjdk-25-runtime` | `Apache-2.0` |
| [`kafka-exporter/`](kafka-exporter/) | [`quay.io/panda-coop/ubi10-kafka-exporter`](https://quay.io/repository/panda-coop/ubi10-kafka-exporter) | `ubi10/ubi-micro` | `Apache-2.0` |
| [`postgresql/`](postgresql/) | [`quay.io/panda-coop/ubi10-postgresql`](https://quay.io/repository/panda-coop/ubi10-postgresql) | `ubi10/ubi-minimal` | `PostgreSQL` |
| [`patroni/`](patroni/) | [`quay.io/panda-coop/ubi10-patroni`](https://quay.io/repository/panda-coop/ubi10-patroni) | `ubi10/ubi-minimal` | `MIT AND PostgreSQL` |
| [`valkey/`](valkey/) | [`quay.io/panda-coop/ubi10-valkey`](https://quay.io/repository/panda-coop/ubi10-valkey) | `ubi10/ubi-minimal` | `BSD-3-Clause` |
| [`redis-exporter/`](redis-exporter/) | [`quay.io/panda-coop/ubi10-redis-exporter`](https://quay.io/repository/panda-coop/ubi10-redis-exporter) | `ubi10/ubi-micro` | `MIT` |
| [`etcd/`](etcd/) | [`quay.io/panda-coop/ubi10-etcd`](https://quay.io/repository/panda-coop/ubi10-etcd) | `ubi10/ubi-micro` | `Apache-2.0` |
| [`clickhouse/`](clickhouse/) | [`quay.io/panda-coop/ubi10-clickhouse`](https://quay.io/repository/panda-coop/ubi10-clickhouse) | `ubi10/ubi-minimal` | `Apache-2.0` |
| [`keycloak/`](keycloak/) | [`quay.io/panda-coop/ubi10-keycloak`](https://quay.io/repository/panda-coop/ubi10-keycloak) | `ubi10/openjdk-25-runtime` | `Apache-2.0` |

The licence column is the SPDX expression in each image's `org.opencontainers.image.licenses`
label. Upstream licences are verified at the pinned version before an image's first
public push. A directory is an image when it holds a `Containerfile`; each one also has a `README.md`
with its runtime details. None is published yet: the first push of each image follows a merge
to `main`.

## Tags

The floating tags depend on how many parts the upstream version has:

| Upstream version | Tags | Example (not a pin) |
|---|---|---|
| `x.y.z` | `x.y.z-<epoch>`, `x.y.z`, `x.y`, `x`, `latest` | Prometheus `3.7.3` |
| `0.y.z` | `0.y.z-<epoch>`, `0.y.z`, `0.y`, `latest`; no `0`, since `0.y` is the floating major | Alertmanager `0.28.1` |
| `x.y` | `x.y-<epoch>`, `x.y`, `x`, `latest` | PostgreSQL `18.6` |
| `w.x.y.z` | `w.x.y.z-<epoch>`, `w.x.y.z`, `w.x`, `latest`; no `w`, a year is not a compatibility promise | ClickHouse `26.10.2.103` |

`<epoch>` is the Unix build time. The `-<epoch>` tag never moves; the full version moves on a
UBI rebuild, the shorter ones on upstream releases, `latest` on every release. Pin the
`-<epoch>` tag or a digest in production. Reasoning: [ADR 0001](docs/decisions/0001-image-tags-version-release-timestamp.md).

## How an image is built

| Rule | Detail |
|---|---|
| Upstream version | `ARG VERSION` in the image's `Containerfile` |
| Download | A stage on `ubi10/ubi-minimal` fetches the release and checks the sha256 pinned next to `ARG VERSION` |
| Base | Pinned by digest |
| Runtime | Non-root user; no configuration inside the image |
| Labels | `name`, `vendor`, `summary`, `description`, `url`, `maintainer` are ours; inherited `com.redhat.*` labels are blanked; `org.opencontainers.image.*` carry source, licence, version and revision |
| Licences | Upstream `LICENSE` and `NOTICE` in `/licenses/<software>/` |

## Verify an image

Every published image is signed keyless with [cosign](https://github.com/sigstore/cosign) by the
GitHub Actions workflows of this repository, and carries an SBOM attestation.

```sh
cosign verify quay.io/panda-coop/ubi10-prometheus:3.15.0 \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --certificate-identity-regexp '^https://github\.com/panda-coop/containers/\.github/workflows/(publish|release|rebuild)\.yml@refs/heads/main$'
```

## Updates

[Renovate](.github/renovate.json) opens the pull requests; a merge to `main` releases the image.

| What | How Renovate finds it |
|---|---|
| Upstream version | The `# renovate: datasource=<datasource> depName=<name>` comment directly above `ARG VERSION=`, with optional `registryUrl=` (a datasource off its default host, e.g. Garage's Forgejo) and `extractVersion=` |
| UBI bases | `ARG BASE_IMAGE=` and `ARG DOWNLOAD_IMAGE=`, pinned as `registry.access.redhat.com/ubi10/<image>:x.y@sha256:...`; digest moves and `x.y` bumps |

Renovate cannot update the `ARG SHA256_*` values next to `ARG VERSION`: a version bump PR fails
its build on the checksum mismatch until the new values from the release's checksum file are
pushed to the PR branch. That failure is intended; nothing unverified gets built.

## Local use

Requires [go-task](https://taskfile.dev), rootless Podman and [prek](https://github.com/j178/prek).

```sh
task lint                          # the validation gate (prek)
task version IMAGE=prometheus      # the upstream version, from ARG VERSION
task build IMAGE=prometheus        # podman build --format docker -t localhost/ubi10-prometheus:dev
task run IMAGE=prometheus -- --version
task inspect IMAGE=prometheus      # labels, user, entrypoint, ports, volumes
```

## Licence

This repository's own files are licensed under the Apache License 2.0 (see `LICENSE`). Each
image carries its upstream licence in `/licenses/`.
