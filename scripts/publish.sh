#!/usr/bin/env bash
# Build and upload a release to PyPI from a working copy.
#
# Prefer the release workflow: pushing a v<version> tag publishes through
# PyPI's trusted publishing, where GitHub proves the build's identity and
# no long-lived token exists anywhere. This script is the manual path, for
# a release made from a laptop when that workflow cannot run.
#
# The token comes from the environment:
#
#   UV_PUBLISH_TOKEN=pypi-... scripts/publish.sh
#
# On macOS it can come from the login keychain instead, which keeps it out
# of your shell history and your environment. Store one with:
#
#   security add-generic-password -U -a "$USER" -s pypi-token-systemap -w
#
# (the -w with no value prompts for it), and name the item with
# SYSTEMAP_KEYCHAIN_ITEM if you use a different one.
#
# Usage: scripts/publish.sh            build dist/ and upload
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

token="${UV_PUBLISH_TOKEN:-}"
if [ -z "$token" ] && command -v security >/dev/null 2>&1; then
  item="${SYSTEMAP_KEYCHAIN_ITEM:-pypi-token-systemap}"
  token="$(security find-generic-password -s "$item" -w 2>/dev/null || true)"
fi
if [ -z "$token" ]; then
  echo "publish: no token. Set UV_PUBLISH_TOKEN, or store one in the keychain; see the header of this script." >&2
  exit 1
fi
UV_PUBLISH_TOKEN="$token" uv publish
unset token
echo "publish: systemap ${version} uploaded; check https://pypi.org/project/systemap/${version}/"
