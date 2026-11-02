# ubi10-kafka-exporter

[kafka_exporter](https://github.com/danielqsj/kafka_exporter) on Red Hat UBI 10 micro: the
upstream release binary `kafka_exporter`, checksum-verified against GitHub's sha256 digests of
the release archives (upstream publishes no checksum file), rebuilt on UBI updates.

Prometheus metrics for Kafka brokers, topic offsets and consumer group lag, read through the
Kafka protocol; no JMX.

Built from github.com/panda-coop/containers. Not affiliated with or supported by Red Hat or the
upstream project.

| Item | Value |
|---|---|
| Image | `quay.io/panda-coop/ubi10-kafka-exporter` |
| Upstream | `danielqsj/kafka_exporter`, version in `ARG VERSION` of the [Containerfile](Containerfile) |
| Base | `registry.access.redhat.com/ubi10/ubi-micro`, pinned by digest; the binary is static (`netgo`, CGO off) |
| Architectures | `amd64`, `arm64` (both checksums pinned; CI publishes `amd64`) |
| User | `65534:65534` (`nobody`, as upstream) |
| Licence | Apache-2.0; upstream `LICENSE` from the release archive in `/licenses/kafka_exporter/` |
| CA bundle | `/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem`, copied from UBI `ca-certificates` (ubi-micro has none), for TLS to brokers without `--tls.ca-file` |

## Tags

| Tag | Example | Moves |
|---|---|---|
| `x.y.z-<epoch>` | `1.11.0-<epoch>` | never |
| `x.y.z` | `1.11.0` | on a UBI rebuild |
| `x.y` | `1.11` | on a patch release |
| `x` | `1` | on a minor release |
| `latest` | | on every release |

See [ADR 0001](../docs/decisions/0001-image-tags-version-release-timestamp.md).

## Runtime

| Item | Value |
|---|---|
| Entrypoint | `/usr/bin/kafka_exporter`; arguments are its flags |
| Command | None; the default broker is `--kafka.server=kafka:9092`, as upstream |
| Port | `9308/tcp`, `/metrics`, as upstream |
| Configuration | None in the image: flags only. SASL, TLS and the topic / group filters are flags; mount certificates or keytabs and point the `--tls.*` / `--sasl.*` flags at them |

The exporter exits at start when no broker answers (`Error Init Kafka Client: ... run out of
available brokers`), so start it after Kafka or let the restart policy retry.

## Example

```sh
podman run -d --name kafka-exporter --network site -p 127.0.0.1:9308:9308 \
  quay.io/panda-coop/ubi10-kafka-exporter:1 \
  --kafka.server=kafka:9092

curl -s localhost:9308/metrics | grep kafka_consumergroup_lag
```

## Local build

```sh
task build IMAGE=kafka-exporter     # localhost/ubi10-kafka-exporter:dev
task run IMAGE=kafka-exporter -- --version
task inspect IMAGE=kafka-exporter
```

A version bump changes `ARG VERSION` and both `ARG SHA256_*` values together; take them from
the `digest` of the `linux-amd64` and `linux-arm64` assets of the GitHub release
(`gh release view v<version> -R danielqsj/kafka_exporter --json assets`). A stale checksum
fails the build.
