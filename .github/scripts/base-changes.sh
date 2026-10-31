#!/usr/bin/env bash
# Print, as a JSON array, the published images whose UBI base moved:
#   [{"image": "prometheus", "base_image": "registry.access.redhat.com/ubi10/ubi-micro:10.2@sha256:..."}]
# For each image directory, the tag of ARG BASE_IMAGE is resolved to its current digest and
# compared with the digest in the org.opencontainers.image.base.name label of the published
# :latest. base_image is the tag pinned to the current digest, for the rebuild to use.
#   FORCE=true base-changes.sh   lists every published image regardless
set -euo pipefail

registry="${REGISTRY:-quay.io/panda-coop}"
force="${FORCE:-false}"
cd "$(git rev-parse --show-toplevel)"

for image in $(git ls-files -- '*/Containerfile' | awk -F/ 'NF == 2 { print $1 }' | sort -u); do
  pin="$(sed -n 's/^ARG BASE_IMAGE=//p' "$image/Containerfile")"
  if [ -z "$pin" ]; then
    echo "$image: no ARG BASE_IMAGE, skipped" >&2
    continue
  fi
  base="${pin%@*}"
  current="$(skopeo inspect --no-creds --no-tags --format '{{.Digest}}' "docker://$base")"
  if ! published="$(skopeo inspect --no-creds --no-tags "docker://$registry/ubi10-$image:latest" 2>/dev/null \
      | jq -r '.Labels["org.opencontainers.image.base.name"] // ""')"; then
    echo "$image: not published yet, skipped (release.yml publishes it)" >&2
    continue
  fi
  if [ "$force" = true ] || [ "${published##*@}" != "$current" ]; then
    echo "$image: base ${published##*@} -> $current" >&2
    jq -cn --arg image "$image" --arg base_image "$base@$current" '{image: $image, base_image: $base_image}'
  else
    echo "$image: base $current unchanged" >&2
  fi
done | jq -cs .
