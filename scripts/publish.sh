#!/usr/bin/env bash
# Make a release package and upload it to PyPI.
# Prefer the release workflow, which uses PyPI trusted publishing without a stored token.
# Use this script if that workflow cannot run.
#
# Supply UV_PUBLISH_TOKEN through the environment:
#   UV_PUBLISH_TOKEN=pypi-... scripts/publish.sh
#
# On macOS, the token can come from the login keychain.
# Write a token with this command. The -w option asks for its value:
#   security add-generic-password -U -a "$USER" -s pypi-token-systemap -w
# Use SYSTEMAP_KEYCHAIN_ITEM for a different item name.
#
# scripts/publish.sh makes the package and uploads it.
# scripts/publish.sh --dry-run makes the package without an upload.
set -euo pipefail

cd "$(dirname "$0")/.."

version="$(uv run python -c 'import systemap; print(systemap.__version__)')"
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "publish: The working tree has uncommitted changes. First commit or stash them." >&2
  exit 1
fi
if ! git tag --list "v${version}" | grep -q .; then
  echo "publish: No tag v${version} is available. First give the release commit its tag: git tag v${version} && git push origin v${version}" >&2
  exit 1
fi

rm -rf dist
uv build
# Not `ls dist`: parsing ls breaks on a name with a space or a newline in
# it, and shellcheck refuses it (SC2012). The glob is the shell's own list.
built="$(cd dist && printf '%s ' *)"
echo "publish: Made $built"

if [ "${1:-}" = "--dry-run" ]; then
  echo "publish: Dry run. No upload occurred."
  exit 0
fi

token="${UV_PUBLISH_TOKEN:-}"
if [ -z "$token" ] && command -v security >/dev/null 2>&1; then
  item="${SYSTEMAP_KEYCHAIN_ITEM:-pypi-token-systemap}"
  token="$(security find-generic-password -s "$item" -w 2>/dev/null || true)"
fi
if [ -z "$token" ]; then
  echo "publish: No token is available. Set UV_PUBLISH_TOKEN or store a token in the keychain. See the script header." >&2
  exit 1
fi
UV_PUBLISH_TOKEN="$token" uv publish
unset token
echo "publish: systemap ${version} uploaded. Examine https://pypi.org/project/systemap/${version}/"
