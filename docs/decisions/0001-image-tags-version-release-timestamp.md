# 0001 — Tag images VERSION-RELEASE, RELEASE is the build timestamp

- Status: accepted
- Date: 2026-10-31 (amended 2026-10-31: two- and four-part versions)
- Decision makers: Mykola Kharchenko

## Context

The images in this repo are public, wrap an upstream release, and are rebuilt when the UBI 10
base changes. Consumers look for the upstream version in the tag. Red Hat tags its images
`VERSION-RELEASE` with floating `VERSION` and `latest`; current UBI images use the Unix build
timestamp as RELEASE, e.g. `ubi10/ubi-minimal:10.0-1758185635` (registry.access.redhat.com, checked
2026-10-31). A rebuild after a UBI CVE fix must produce a new immutable tag without anyone
editing the repo.

## Options considered

| Option | Rejected because |
|--------|------------------|
| Counter RELEASE, `x.y.z-N` | Needs state (the last N) and a manual bump; scheduled rebuilds cannot run unattended |
| Date-based git tags, `<name>-YY.MM.DD-N` | Hides the upstream version from consumers; needs a git tag per release. Kept for the private `infra-*` images only, which are released by hand |
| **Timestamp RELEASE, `x.y.z-<epoch>`** | — chosen |

## Decision

Every image publishes these tags:

| Tag | Example (not a pin) | Moves |
|---|---|---|
| `x.y.z-<epoch>` | `3.7.3-1761900000` | never |
| `x.y.z` | `3.7.3` | on a UBI rebuild |
| `x.y` | `3.7` | on a patch release |
| `x` | `3` | on a minor release |
| `latest` | | on everything, including a major release |

An upstream still at 0.x gets no `0` tag: there the minor bump is the breaking one, so `0.y` is
its floating major. Example (not a pin): Alertmanager `0.28.1` publishes `0.28.1-<epoch>`,
`0.28.1`, `0.28` and `latest`.

Not every upstream versions in three parts. The floating tags follow the part count:

| Upstream version | Tags | Example (not a pin) |
|---|---|---|
| `x.y.z` | `x.y.z-<epoch>`, `x.y.z`, `x.y`, `x`, `latest` | Prometheus `3.7.3` |
| `0.y.z` | `0.y.z-<epoch>`, `0.y.z`, `0.y`, `latest` | Alertmanager `0.28.1` |
| `x.y` | `x.y-<epoch>`, `x.y`, `x`, `latest` (no `0` for a `0.y`) | PostgreSQL `18.6`: `18.6-<epoch>`, `18.6`, `18`, `latest` |
| `w.x.y.z` | `w.x.y.z-<epoch>`, `w.x.y.z`, `w.x`, `latest` | ClickHouse `26.10.2.103`: `26.10.2.103-<epoch>`, `26.10.2.103`, `26.10`, `latest` |

A four-part version is read as ClickHouse's year.month.patch.build: `w.x` is the release line,
and there is no `w` tag, since a year is not a compatibility promise (the same reasoning as the
0.x rule). The rule is decided by the part count alone, not by recognising the software.

The `x` tag lets a consumer stay on a major (`ubi10-prometheus:3`) without a major version in
the image name: Red Hat puts the major in an image name only for streams maintained in parallel,
this repo runs one stream per software, so staying on a major is the floating `x` tag.

The labels `version` (the upstream version), `release` (`<epoch>`) and `name` (`panda-coop/ubi10-<software>`)
match the tags. The upstream version lives in each `Containerfile` as `ARG VERSION`; CI supplies
the epoch at build time. No per-release git tags.

| Trigger | Result |
|---|---|
| A merged Renovate bump of `ARG VERSION` | New `x.y.z-<epoch>`; floating tags move |
| Scheduled rebuild, UBI base digest changed | New `x.y.z-<epoch>` on the same upstream version; floating tags move |
| Pull request | Build only, no push |

## Consequences

- Rebuilds on UBI updates need no human step; the release history is the tag list on Quay.
- Release order is the timestamp order. The release workflow runs one build per image at a time
  (a concurrency group), so two releases of one image never share an epoch.
- The release workflow computes the epoch once and uses it for both tags and labels.
- The git history no longer marks releases; "what is in `3.7.3-1761900000`" is answered by the
  `vcs-ref` label, which the workflow must set.
