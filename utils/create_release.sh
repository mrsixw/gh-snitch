#!/usr/bin/env bash
set -euo pipefail

version="$1"
tag="v${version}"

gh release create "${tag}" ./dist/gh-snitch \
  man1/gh-snitch.1.gz \
  completions/gh-snitch.bash \
  completions/_gh-snitch \
  completions/gh-snitch.fish \
  --title "${tag}" \
  --generate-notes \
  --target "$(git rev-parse HEAD)"
