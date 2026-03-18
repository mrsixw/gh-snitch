#!/usr/bin/env bash
set -euo pipefail

version="$1"
tag="v${version}"

gh release create "${tag}" ./dist/gh-snitch \
  --title "${tag}" \
  --generate-notes \
  --target "$(git rev-parse HEAD)"
