#!/usr/bin/env bash
# Publish systemap to PyPI with the token held in the macOS login Keychain.
#
# The token never appears on the command line or in a file: it is read from
# the Keychain item "pypi-token-systemap" into the environment of the one
# process that needs it. Store or replace it with:
#
#   security add-generic-password -U -a "$USER" -s pypi-token-systemap -w
#
# (the -w with no value prompts for it, so it never enters shell history).
#
# Usage: scripts/publish.sh            build dist/ for the current version and publish
#        scripts/publish.sh --dry-run  build and check only
set -euo pipefail

cd "$(dirname "$0")/.."

version="$(uv run python -c 'import systemap; print(systemap.__version__)')"
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "publish: the working tree has uncommitted changes; commit or stash first" >&2
  exit 1
fi
if ! git tag --list "v${version}" | grep -q .; then
  echo "publish: no tag v${version}; tag the release commit first: git tag v${version} && git push origin v${version}" >&2
  exit 1
fi

rm -rf dist
uv build
echo "publish: built $(ls dist | tr '\n' ' ')"

if [ "${1:-}" = "--dry-run" ]; then
  echo "publish: dry run, nothing uploaded"
  exit 0
fi

if ! token="$(security find-generic-password -s pypi-token-systemap -w 2>/dev/null)"; then
  echo "publish: no Keychain item pypi-token-systemap; see the header of this script" >&2
  exit 1
fi
UV_PUBLISH_TOKEN="$token" uv publish
unset token
echo "publish: systemap ${version} uploaded; check https://pypi.org/project/systemap/${version}/"
