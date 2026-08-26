#!/usr/bin/env bash
# bench/run.sh: the headless recipe as a script, so a cost is measured the
# same way every time and lands in bench/results.jsonl as one line.
#
#   bench/run.sh <repo-url-or-path> first-map   [--ref REF] [options]
#   bench/run.sh <repo-url-or-path> maintenance --base REF [--ref REF] [options]
#
# What it does, in order: puts a checkout of the repository under a scratch
# directory (a git worktree for a local path, a clone for a URL: shallow for
# a first map, history without old blobs for maintenance, which needs the
# base commit); installs systemap into a tool directory of its own, pinned
# to this checkout's version tag by default; runs `systemap init` there;
# runs the coding agent headless with the documented sentence, the
# acceptEdits permission mode and the tool list below, streaming the
# session as JSON to a log; then runs `systemap check` and `systemap
# judgement --strict`, reads the module count back, and writes the summary
# line with bench/summary.py. The line records the model the session
# names, its turns, minutes and dollars from the result event, whether it
# finished or was cut off, and whether its first tool call was the
# systemap skill, which the recipe requires.
#
# Nothing here is estimated; a value the log does not carry is null.
set -euo pipefail

here="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
  cat <<'USAGE'
Usage: bench/run.sh <repo-url-or-path> <first-map|maintenance> [options]

  --ref REF          the commit, branch or tag to check out (default: HEAD of
                     the source; a shallow clone takes a branch or a tag)
  --base REF         maintenance only, required: the ref the map is compared
                     against (the base branch of the pull request replayed)
  --from SPEC        where to install systemap from (default: the git tag of
                     this checkout's version, git+https://github.com/0xfauzi/systemap@vX.Y.Z;
                     a local path or a PyPI requirement work too)
  --model NAME       the model to run the session with (default: the agent's)
  --max-turns N      cut the session off after N turns (default: none)
  --scratch DIR      where the checkouts go (default: bench/scratch, ignored by git)
  --help             this text

The summary line is appended to bench/results.jsonl; render the table with
python3 bench/table.py. The checkout is kept under the scratch directory for
inspection, with the session log beside it (session.jsonl).
USAGE
}

repo="" mode="" ref="" base="" from="" model="" max_turns="" scratch="$here/bench/scratch"
while [ $# -gt 0 ]; do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --ref) ref="${2:-}"; shift 2 ;;
    --base) base="${2:-}"; shift 2 ;;
    --from) from="${2:-}"; shift 2 ;;
    --model) model="${2:-}"; shift 2 ;;
    --max-turns) max_turns="${2:-}"; shift 2 ;;
    --scratch) scratch="${2:-}"; shift 2 ;;
    --*) echo "bench: unknown option $1" >&2; usage >&2; exit 2 ;;
    *)
      if [ -z "$repo" ]; then repo="$1"
      elif [ -z "$mode" ]; then mode="$1"
      else echo "bench: unexpected argument $1" >&2; usage >&2; exit 2
      fi
      shift ;;
  esac
done
if [ -z "$repo" ] || [ -z "$mode" ]; then usage >&2; exit 2; fi
case "$mode" in
  first-map|maintenance) ;;
  *) echo "bench: mode must be first-map or maintenance, not $mode" >&2; exit 2 ;;
esac
if [ "$mode" = "maintenance" ] && [ -z "$base" ]; then
  echo "bench: maintenance needs --base REF" >&2; exit 2
fi
for tool in git uv claude python3; do
  command -v "$tool" >/dev/null 2>&1 || { echo "bench: $tool is not on PATH" >&2; exit 2; }
done

version="$(sed -n 's/^version = "\(.*\)"$/\1/p' "$here/pyproject.toml" | head -n 1)"
from="${from:-git+https://github.com/0xfauzi/systemap@v$version}"

# The source: a URL is cloned, a path is added as a worktree. The table
# names a URL as given and a path by its directory alone.
case "$repo" in
  *://*|git@*:*) kind=clone; name="${repo##*/}"; name="${name%.git}"; label="${repo%.git}" ;;
  *)
    [ -d "$repo" ] || { echo "bench: $repo is not a directory or a URL" >&2; exit 2; }
    kind=worktree; name="$(basename "$(cd "$repo" && pwd)")"; label="$name" ;;
esac
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
run="$scratch/$name-$mode-$stamp"
tree="$run/repo"
log="$run/session.jsonl"
mkdir -p "$run"
echo "bench: $label, $mode, systemap from $from"
echo "bench: checkout at $tree"

if [ "$kind" = worktree ]; then
  git -C "$repo" worktree add --quiet --detach "$tree" "${ref:-HEAD}"
elif [ "$mode" = first-map ]; then
  if [ -n "$ref" ]; then git clone --quiet --depth 1 --branch "$ref" "$repo" "$tree"
  else git clone --quiet --depth 1 "$repo" "$tree"; fi
else
  git clone --quiet --filter=blob:none "$repo" "$tree"
  if [ -n "$ref" ]; then git -C "$tree" checkout --quiet "$ref"; fi
fi
sha="$(git -C "$tree" rev-parse HEAD)"

# systemap in a tool directory of this run's own, so the machine's install
# is neither used nor touched.
export UV_TOOL_DIR="$run/tools" UV_TOOL_BIN_DIR="$run/bin"
uv tool install --quiet --force --from "$from" systemap
export PATH="$run/bin:$PATH"
installed="$(systemap --version | awk '{print $2}')"
echo "bench: systemap $installed installed"

cd "$tree"
systemap init | sed 's/^/bench: init: /'

if [ "$mode" = first-map ]; then
  sentence="Map this repository with systemap. Follow the systemap skill."
else
  sentence="The code changed. Update the map with systemap: follow the systemap skill's maintenance path, with base $base."
fi
allowed="Skill,Read,Edit,Write,Glob,Grep,TodoWrite"
for cmd in systemap uv uvx python3 git ls cat grep rg find head tail sed wc mkdir; do
  allowed="$allowed,Bash($cmd:*)"
done

echo "bench: session starts ($(date -u +%H:%M:%SZ)); log at $log"
start="$(date +%s)"
set +e
claude -p "$sentence" \
  --permission-mode acceptEdits \
  --allowedTools "$allowed" \
  --output-format stream-json --verbose \
  ${model:+--model "$model"} \
  ${max_turns:+--max-turns "$max_turns"} \
  > "$log" 2> "$run/claude.stderr"
claude_exit=$?
set -e
end="$(date +%s)"
echo "bench: session ended with exit $claude_exit after $(( (end - start) / 60 )) minutes"

check=clean; systemap check > "$run/check.txt" 2>&1 || check=failed
judgement=clean; systemap judgement --strict > "$run/judgement.txt" 2>&1 || judgement=open
modules="$(systemap facts 2>/dev/null | sed -n 's/^ *modules: *\([0-9][0-9]*\).*$/\1/p' | head -n 1)"
echo "bench: check $check, judgement $judgement, modules ${modules:-unknown}"

python3 "$here/bench/summary.py" "$log" \
  --repository "$label" --mode "$mode" --systemap "$installed" --ref "$sha" \
  ${base:+--base "$base"} ${modules:+--modules "$modules"} \
  --check "$check" --judgement "$judgement" --wall-seconds "$((end - start))" \
  --append "$here/bench/results.jsonl" | tee "$run/summary.json"
if grep -q '"first_tool_ok": true' "$run/summary.json"; then
  echo "bench: first tool call was Skill systemap, as the recipe requires"
else
  echo "bench: WARNING: the first tool call was not Skill systemap; the row says so"
fi
echo "bench: line appended to bench/results.jsonl; render with: python3 bench/table.py"
