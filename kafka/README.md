# ubi10-kafka

[Apache Kafka](https://kafka.apache.org/) in KRaft mode on Red Hat UBI 10 OpenJDK 25 runtime:
the upstream binary tarball `kafka_2.13-<version>.tgz`, checked against the release's `.sha512`
and its GPG signature against the Apache Kafka `KEYS`, rebuilt on UBI updates.

Built from github.com/panda-coop/containers. Not affiliated with or supported by Red Hat or the
upstream project.

| Item | Value |
|---|---|
| Image | `quay.io/panda-coop/ubi10-kafka` |
| Upstream | Apache Kafka, Scala 2.13 build, version in `ARG VERSION` of the [Containerfile](Containerfile) |
| Base | `registry.access.redhat.com/ubi10/openjdk-25-runtime`, pinned by digest |
| Java | 25: Kafka 4.4 fully supports 17, 21 and 25 and recommends the latest LTS |
| Architectures | Any the base has; the tarball is architecture independent (CI publishes `amd64`) |
| User | `185:0` (the base's `default` user); writable paths are group 0 writable, for arbitrary UIDs |
| Licence | Apache-2.0; upstream `LICENSE`, `NOTICE` and `licenses/` in `/licenses/kafka/` |

## Tags

| Tag | Example | Moves |
|---|---|---|
| `x.y.z-<epoch>` | `4.4.0-<epoch>` | never |
| `x.y.z` | `4.4.0` | on a UBI rebuild |
| `x.y` | `4.4` | on a patch release |
| `x` | `4` | on a minor release |
| `latest` | | on every release |

See [ADR 0001](../docs/decisions/0001-image-tags-version-release-timestamp.md).

## Runtime

| Item | Value |
|---|---|
| Entrypoint | `/usr/local/bin/kafka-entrypoint`, then `exec kafka-server-start.sh /etc/kafka/server.properties`; the JVM is PID 1 |
| Arguments | Options pass through to `kafka-server-start.sh` (`--override key=value`); a first argument that is not an option runs as a command, e.g. `kafka-topics.sh --version` |
| Ports | `9092/tcp` client (`PLAINTEXT`), `9093/tcp` controller (`CONTROLLER`) |
| Volume | `/var/lib/kafka/data` (the log directory), owned by `185:0`, group-writable |
| Configuration | None in the image: `/etc/kafka/server.properties` is rendered from the environment on every start. `/opt/kafka/config/` is the tarball's, untouched, and supplies `log4j2.yaml` |
| Application logs | stdout, and `/opt/kafka/logs` inside the container |
| `PATH` | Includes `/opt/kafka/bin`, so `podman exec` runs the Kafka tools by name |

## Environment

Every `KAFKA_*` variable becomes a server property, as in the `apache/kafka` image: drop
`KAFKA_`, lowercase, then `_` becomes `.`, `__` becomes `_` and `___` becomes `-`. For example
`KAFKA_LOG_RETENTION_HOURS=24` is `log.retention.hours=24`.

Not properties, read by the Kafka scripts or the JVM: `KAFKA_HEAP_OPTS` (default
`-Xmx1G -Xms1G`), `KAFKA_OPTS`, `KAFKA_JVM_PERFORMANCE_OPTS`, `KAFKA_GC_LOG_OPTS`,
`KAFKA_JMX_OPTS`, `KAFKA_LOG4J_OPTS`, `KAFKA_DEBUG`, and upstream's `KAFKA_VERSION`,
`KAFKA_LOG4J_ROOT_LOGLEVEL`, `KAFKA_LOG4J_LOGGERS`, `KAFKA_TOOLS_LOG4J_LOGLEVEL`,
`KAFKA_JMX_HOSTNAME` (excluded for compatibility; this entrypoint does not act on them).

Without `KAFKA_PROCESS_ROLES` the node is a single combined broker and controller, and each of
these defaults applies unless its variable is set:

| Variable | Default |
|---|---|
| `KAFKA_PROCESS_ROLES` | `broker,controller` |
| `KAFKA_NODE_ID` | `1` |
| `KAFKA_LISTENERS` | `PLAINTEXT://:9092,CONTROLLER://:9093` |
| `KAFKA_ADVERTISED_LISTENERS` | `PLAINTEXT://localhost:9092` |
| `KAFKA_LISTENER_SECURITY_PROTOCOL_MAP` | `CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT` |
| `KAFKA_CONTROLLER_LISTENER_NAMES` | `CONTROLLER` |
| `KAFKA_INTER_BROKER_LISTENER_NAME` | `PLAINTEXT` |
| `KAFKA_CONTROLLER_QUORUM_VOTERS` | `<KAFKA_NODE_ID>@localhost:9093` |
| `KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR` | `1` |
| `KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR`, `..._MIN_ISR` | `1` |
| `KAFKA_SHARE_COORDINATOR_STATE_TOPIC_REPLICATION_FACTOR`, `..._MIN_ISR` | `1` |
| `KAFKA_LOG_DIRS` | `/var/lib/kafka/data` (defaulted in every mode) |

With `KAFKA_PROCESS_ROLES` set, the environment describes the node and only `KAFKA_LOG_DIRS` is
defaulted. Format uses static voters (`KAFKA_CONTROLLER_QUORUM_VOTERS`), as `apache/kafka`
does; a dynamic quorum (`controller.quorum.bootstrap.servers`) needs format options this
entrypoint does not pass.

| Variable | Use |
|---|---|
| `CLUSTER_ID` | First start only. Unset: generated with `kafka-storage.sh random-uuid` and logged. Afterwards the cluster ID is the one in `meta.properties` in the log directories, and a different `CLUSTER_ID` stops the container. Set it for every node of a multi-node cluster |

`kafka-storage.sh format` runs only when a log directory (`KAFKA_LOG_DIRS`, and
`KAFKA_METADATA_LOG_DIR` if set) has no `meta.properties`, so restarts never reformat.

## Example

```sh
podman volume create kafka-data
podman run -d --name kafka -p 9092:9092 \
  -v kafka-data:/var/lib/kafka/data \
  quay.io/panda-coop/ubi10-kafka:4

podman exec kafka kafka-topics.sh --bootstrap-server localhost:9092 --create --topic smoke
echo hello | podman exec -i kafka kafka-console-producer.sh --bootstrap-server localhost:9092 --topic smoke
podman exec kafka kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic smoke \
  --from-beginning --max-messages 1
```

For clients outside the host, set `KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://<host>:9092`.

## Upgrades

- A new image on the same volume keeps the data and the cluster ID; nothing is reformatted.
- After every broker runs the new version, raise the metadata version, e.g.
  `podman exec kafka kafka-features.sh --bootstrap-server localhost:9092 upgrade --release-version 4.4`.
  Until then a downgrade to the previous image still works; after it, it may not.
- Kafka 4 is KRaft only: data from a ZooKeeper-mode 3.x cluster must be migrated to KRaft on 3.9
  first, upstream's documented path.
- From the `apache/kafka` image: its user is UID 1000, this one runs as 185, so give the volume
  to `185:0` first (`podman unshare chown -R 185:0 <volume path>`) and point `KAFKA_LOG_DIRS` at
  `/var/lib/kafka/data` if it was elsewhere.

## Local build

```sh
task build IMAGE=kafka     # localhost/ubi10-kafka:dev
task run IMAGE=kafka -- kafka-topics.sh --version
task inspect IMAGE=kafka
```

A version bump changes `ARG VERSION` and `ARG SHA512` together (the hex from the release's
`kafka_2.13-<version>.tgz.sha512`); a stale checksum fails the build.
