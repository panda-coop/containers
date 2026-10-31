#!/usr/bin/env bash
# Print the image directories changed since BASE as a JSON array, e.g. ["prometheus"].
# An image directory is a top-level directory holding a tracked Containerfile. With no BASE, an
# all-zero BASE (a new branch) or a BASE not in the history, every image counts as changed.
set -euo pipefail

base="${1:-}"
cd "$(git rev-parse --show-toplevel)"

all_images() {
  git ls-files -- '*/Containerfile' | awk -F/ 'NF == 2 { print $1 }' | sort -u
}

if [ -z "$base" ] || [ -z "${base//0/}" ] || ! git cat-file -e "${base}^{commit}" 2>/dev/null; then
  images="$(all_images)"
else
  images="$(git diff --name-only "$base" HEAD | awk -F/ 'NF > 1 { print $1 }' | sort -u \
    | while read -r dir; do git ls-files --error-unmatch -- "$dir/Containerfile" >/dev/null 2>&1 && echo "$dir"; done || true)"
fi

printf '%s\n' "$images" | jq -R . | jq -cs 'map(select(length > 0))'
