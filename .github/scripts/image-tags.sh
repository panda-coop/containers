#!/usr/bin/env bash
# Print the tags of one release, one per line, immutable tag first:
#   image-tags.sh VERSION EPOCH   e.g. 3.7.3 1761900000
#   image-tags.sh --self-test
# VERSION is the upstream version, two to four numeric parts; EPOCH the Unix build time.
# The floating tags depend on the part count (ADR 0001):
#   x.y.z    x.y.z-EPOCH, x.y.z, x.y, x, latest   (a 0.y.z gets no `0`: 0.y is its major)
#   x.y      x.y-EPOCH, x.y, x, latest            (a 0.y gets no `0`)
#   w.x.y.z  w.x.y.z-EPOCH, w.x.y.z, w.x, latest  (no `w`: a year, not a compatibility promise)
set -euo pipefail

tags() {
  local version="$1" epoch="$2" part='(0|[1-9][0-9]*)'
  if ! [[ "$version" =~ ^${part}(\.${part}){1,3}$ ]]; then
    echo "image-tags: version '$version' is not x.y, x.y.z or w.x.y.z" >&2
    return 1
  fi
  local -a v
  IFS=. read -ra v <<< "$version"
  if ! [[ "$epoch" =~ ^[1-9][0-9]{9,}$ ]]; then
    echo "image-tags: epoch '$epoch' is not a Unix timestamp" >&2
    return 1
  fi
  printf '%s\n' "${version}-${epoch}" "$version"
  case "${#v[@]}" in
    2) [ "${v[0]}" = 0 ] || echo "${v[0]}" ;;
    3) echo "${v[0]}.${v[1]}"; [ "${v[0]}" = 0 ] || echo "${v[0]}" ;;
    4) echo "${v[0]}.${v[1]}" ;;
  esac
  echo latest
}

self_test() {
  local failed=0 got
  check() {
    got="$(tags "$1" "$2" 2>/dev/null | paste -sd, -)" || got="error"
    [ -n "$got" ] || got="error"
    if [ "$got" = "$3" ]; then
      echo "ok   $1 $2 -> $got"
    else
      echo "FAIL $1 $2 -> $got, want $3"
      failed=1
    fi
  }
  check 3.7.3 1761900000 3.7.3-1761900000,3.7.3,3.7,3,latest
  check 10.0.12 1761900000 10.0.12-1761900000,10.0.12,10.0,10,latest
  check 0.28.1 1761900000 0.28.1-1761900000,0.28.1,0.28,latest
  check 0.0.1 1761900000 0.0.1-1761900000,0.0.1,0.0,latest
  check 18.6 1761900000 18.6-1761900000,18.6,18,latest
  check 0.9 1761900000 0.9-1761900000,0.9,latest
  check 26.10.2.103 1761900000 26.10.2.103-1761900000,26.10.2.103,26.10,latest
  check 0.1.2.3 1761900000 0.1.2.3-1761900000,0.1.2.3,0.1,latest
  check v3.7.3 1761900000 error
  check 3 1761900000 error
  check 3.7.3.1.2 1761900000 error
  check 3.7.3-rc.1 1761900000 error
  check 26.10.2.103-stable 1761900000 error
  check 03.7.3 1761900000 error
  check 3.7. 1761900000 error
  check 3.7.3 dev error
  check 3.7.3 "" error
  return "$failed"
}

if [ "${1:-}" = --self-test ]; then
  self_test
elif [ "$#" -eq 2 ]; then
  tags "$1" "$2"
else
  echo "usage: $0 VERSION EPOCH | --self-test" >&2
  exit 2
fi
