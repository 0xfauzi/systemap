"""What `systemap init` writes: a configuration, a starter model, a workflow.

The starter model is empty on purpose: one container holding four regions
in a two-by-two grid, and no components, no flows, no positions. A
placeholder card would be a lie the first check had to catch; instead the
check says the model has no components yet and points at the skill, and
the agent following it (installed by the same command, see skill.py)
writes the real cards from the facts, without positions, and runs
`systemap place`, which lays the regions out on the grid the corridor
rule needs and puts every card on it. The four regions are there to be
renamed and to show the shape.

The workflow runs the check on every push and pull request with the
released package, pinned to the tag of the version that wrote it (`uvx
--from "git+https://github.com/0xfauzi/systemap@v<this version>"`), so
the project needs no dependency on systemap. The pin moves to PyPI at
1.0. It is written by default and skipped with `--no-ci`, since not every
repository runs on the one forge the workflow is written for.
"""

from __future__ import annotations

from pathlib import Path

from systemap import __version__

CONFIG = """# systemap configuration. Every key is optional; these are the defaults
# except name, which defaults to [project] name in pyproject.toml, then
# the git repository's directory, then this directory's name.
name = "{name}"
# Where the packages are: "path" = "import name". Leave it out to discover
# every top-level directory (or src/<dir>) that holds an __init__.py, in
# the root and in every [tool.uv.workspace] member.
{roots}
# Where test files live: one directory or a list. Leave it out to read every
# directory named tests or test under the root.
# tests_dir = ["tests"]
model = "map/model.py"
out_dir = "docs/map"
# spec_path = "docs/design.md"

# `systemap check` refuses a map that leaves a module unclaimed. A module
# that has no place on the map is ignored here, and every ignore needs a
# reason, so the hole is on record rather than hidden.
# [coverage]
# ignore = [{{ module = "{package}.compat", reason = "a shim with no place on the map" }}]

# `systemap judgement` lines the maintainer has answered, each with why; an
# answered line is suppressed and counted, a stale one is reported.
# [judgement]
# answered = [{{ item = "single module: Reader is only {package}.reader", reason = "a real part" }}]

# Figures `systemap refresh` regenerates beside the page. mode is "system"
# (nothing marked) or "reach" (the named components marked as a plan's reach);
# layer = "structure" (or "system", "data", "control", a layer of your own)
# draws one reading only, with every card and none of the other edges. An
# out ending in .svg is the bare drawing, for a README or a document.
[[figures]]
out = "figures/structure.svg"
mode = "system"
interactive = false
layer = "structure"

[[figures]]
out = "figures/system.svg"
mode = "system"
interactive = false

# [theme]
# accent = "#5DADE2"
"""

MODEL = '''# ruff: noqa: E501
# The map is prose held in strings: a sentence per flow, a step per journey,
# a rule per invariant. A sentence is not wrapped, so the line-length rule
# does not apply to this file. The schema is imported whole and every name
# is used below, so a card written later finds every name and the linter
# has nothing to say.
"""The system map of {name}: what the parts are and what they are to each other.

Everything in this file is written on purpose. The facts about the code
(which modules exist, what they export, which tests import them) are read
by `systemap extract`; this file says what the system is MEANT to be, and
the map draws the two together. The map draws what exists today: a
component names the modules that are it and one entry they define, and
`systemap check` refuses a name the code does not have.

Positions are fixed in this file because this is a topology, not a chart:
a card's place carries meaning. A card written without `x` and `y` is
placed by `systemap place`, which lays the regions out on a grid with
corridors between them and puts every such card on the grid; `systemap
place --all` lays every card out again after one is added or removed,
keeping the cards marked `pinned=True`. `systemap check` verifies every
card sits in its band, no two overlap, every flow has a layer and a
sentence, and every route and label is clean.

This file starts empty: one container holding four regions in a two-by-two
grid, and no components. The skill says how to write the cards from the
facts; references/layout.md says what is still yours to decide.
"""

from __future__ import annotations

# systemap is a tool this repository runs, not a dependency it declares,
# so a strict type checker cannot find the import and a dependency
# checker reports it. The ignore below answers mypy (and is not itself
# reported as unused where systemap happens to be installed); `systemap
# init` prints the pyproject lines that answer deptry (DEP001, DEP003).
from systemap import (  # type: ignore[import-not-found, unused-ignore]
    Component,
    Container,
    Flow,
    Invariant,
    Journey,
    Layer,
    Meaning,
    Model,
    Region,
    Step,
)

CONTAINERS = (
    Container(
        id="system",
        label="{upper}",
        sub="one process; say what the boundary means",
        box=(16, 16, 876, 536),
        tone="server",
    ),
)

# Four regions in a two-by-two grid. The 48 units between the region
# columns and the 36 between the region rows are corridors: an edge may not
# cross a region it neither starts nor ends in, and the corridors form a
# cross, so from any region there is a route to any other. Rename the
# regions after the phases, concerns or teams the parts fall into; drop one
# you do not need; add one you do. `systemap place` lays them out again on
# the same kind of grid, sized to the cards each holds, when no card is
# pinned, so the boxes here are a shape to start from, not a rule.
#
# The position tables stay one line per row: the formatter is turned off
# around them so the grid stays readable, and on again below.
# fmt: off
REGIONS = (
    Region(id="a", label="REGION A", box=(40, 60, 390, 216), container="system"),
    Region(id="b", label="REGION B", box=(478, 60, 390, 216), container="system"),
    Region(id="c", label="REGION C", box=(40, 312, 390, 216), container="system"),
    Region(id="d", label="REGION D", box=(478, 312, 390, 216), container="system"),
)
# fmt: on

# One card per thing a reader would point at and name. `implemented_by`
# names the modules that are it (from the facts file), `entry` one public
# name they define. Write no x or y: `systemap place` writes them, on the
# grid, and `systemap place --all` writes them again after a card is added
# or removed; `pinned=True` marks a card whose place you chose. For example:
#
#     Component(
#         id="Reader",
#         region="a",
#         does="Reads the input and turns it into a request.",
#         interface="read(source) -> Request",
#         implemented_by=("{package}.reader",),
#         entry="read",
#     ),
# fmt: off
COMPONENTS: tuple[Component, ...] = ()
# fmt: on

# (from, to, the artifact carried, the kind). Two kinds are standard and
# need no declaring: data (an artifact moves) and control (one part drives
# another). A kind of your own is declared in FLOW_KINDS and given a layer.
# The artifact is a noun phrase of one to three words, never a sentence.
FLOWS: tuple[Flow, ...] = ()

FLOW_KINDS: tuple[str, ...] = ()

# Rules the repository states about itself, each citing its source.
INVARIANTS: tuple[Invariant, ...] = ()

MODEL = Model(
    canvas=(910, 570),
    containers=CONTAINERS,
    regions=REGIONS,
    components=COMPONENTS,
    flows=FLOWS,
    flow_kinds=FLOW_KINDS,
    invariants=INVARIANTS,
)

# ---- meaning: the plain words, the layers, one sentence per flow ---------

# The plain words a newcomer would use for each card, by id.
PLAIN: dict[str, str] = {{}}

# The page derives Structure, System context, Data flow and Control flow
# from the model. A layer of your own goes here, as the question it
# answers, with its kind mapped to it in LAYER_OF_KIND.
LAYERS: tuple[Layer, ...] = ()

LAYER_OF_KIND: dict[str, str] = {{}}

# One sentence per flow, read from the source side.
RELATIONS: dict[tuple[str, str], str] = {{}}

VERBS: dict[str, tuple[str, str]] = {{"data": ("hands to", "receives from")}}

# One journey per entry point that matters, one Step per edge it traces;
# a journey's steps are a tuple of Step.
Steps = tuple[Step, ...]
JOURNEYS: tuple[Journey, ...] = ()

MEANING = Meaning(
    plain=PLAIN,
    layers=LAYERS,
    layer_of_kind=LAYER_OF_KIND,
    relations=RELATIONS,
    journeys=JOURNEYS,
    verbs=VERBS,
)
'''

WORKFLOW = """name: systemap

# The system map under docs/map is generated from the code and the model
# module. It is committed so the page can be served as-is and so the diff
# between two commits of the facts file records what changed about the
# system. This job fails when the committed map no longer matches the tree
# or the renderer; the fix is one command, named in the failure.
#
# systemap runs from the released package, pinned to the tag of the
# version that wrote this file, so the project needs no dependency on it;
# the pin moves to PyPI at 1.0. Bump the pin when you upgrade. Every
# action is pinned to a commit, with the version beside it; the jobs read
# the tree and nothing else, the checkout keeps no token, and the one job
# that writes (the delta comment on a pull request) says so beside its
# permission, so a workflow linter passes it as written.

on:
  push:
    branches: [main]
  pull_request:

# Read-only for every job; the delta job widens it for itself alone.
permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  systemap:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false

      - name: Install uv
        uses: astral-sh/setup-uv@37802adc94f370d6bfd71619e3f0bf239e1f3b78 # v7.6.0
        with:
          version: latest
          enable-cache: true

      - name: facts match the tree
        run: |
          uvx --from "git+https://github.com/0xfauzi/systemap@v__VERSION__" systemap extract --check || {
            echo "::error title=Map is stale::the facts no longer describe the tree. Run systemap refresh and commit the output directory."
            exit 1
          }

      - name: layout, meaning and coverage are consistent
        run: |
          uvx --from "git+https://github.com/0xfauzi/systemap@v__VERSION__" systemap check || {
            echo "::error title=Map check::the model contradicts itself or leaves a module unmapped; see the lines above."
            exit 1
          }

      - name: every judgement line is answered
        run: |
          uvx --from "git+https://github.com/0xfauzi/systemap@v__VERSION__" systemap judgement --strict || {
            echo "::error title=Judgement::a judgement line is unanswered. Act on it, or answer it under [judgement] answered in systemap.toml."
            exit 1
          }

      - name: page matches the renderer
        run: |
          uvx --from "git+https://github.com/0xfauzi/systemap@v__VERSION__" systemap render --check || {
            echo "::error title=Map is stale::index.html differs from what systemap renders. Run systemap refresh and commit the output directory."
            exit 1
          }

  delta:
    # What the pull request does to the map, as one comment: posted once,
    # then updated in place on every push. The base and head commits reach
    # the command through the environment, never through the template. A
    # pull request from a fork has a read-only token, so the comment step
    # warns instead of failing there; the delta is in the log either way.
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read
      pull-requests: write # this job posts or updates the delta comment
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
          fetch-depth: 0 # the base and the head commits, for the two extractions

      - name: Install uv
        uses: astral-sh/setup-uv@37802adc94f370d6bfd71619e3f0bf239e1f3b78 # v7.6.0
        with:
          version: latest
          enable-cache: true

      - name: what this change does to the map
        env:
          BASE: ${{ github.event.pull_request.base.sha }}
          HEAD: ${{ github.event.pull_request.head.sha }}
        run: |
          code=0
          uvx --from "git+https://github.com/0xfauzi/systemap@v__VERSION__" systemap delta --base "$BASE" --head "$HEAD" --format markdown > delta.md || code=$?
          echo "$code" > delta.code
          if [ ! -s delta.md ]; then
            printf '<!-- systemap delta -->\\n## What this change does to the map\\n\\nsystemap delta could not run (exit %s); see the workflow log.\\n' "$code" > delta.md
          fi
          cat delta.md

      - name: post or update the comment
        env:
          GH_TOKEN: ${{ github.token }}
          PR: ${{ github.event.pull_request.number }}
          REPO: ${{ github.repository }}
        run: |
          existing="$(gh api "repos/$REPO/issues/$PR/comments" --paginate --jq 'map(select(.body | startswith("<!-- systemap delta -->"))) | first | .id // empty' | head -n 1)"
          if [ -n "$existing" ]; then
            gh api -X PATCH "repos/$REPO/issues/comments/$existing" -F body=@delta.md > /dev/null
          else
            gh api -X POST "repos/$REPO/issues/$PR/comments" -F body=@delta.md > /dev/null
          fi || echo "::warning title=Map delta::could not post the comment (a pull request from a fork has a read-only token); the delta is in the step above."

      - name: every line is acted on
        run: |
          code="$(cat delta.code)"
          if [ "$code" != "0" ]; then
            echo "::error title=Map delta::the change needs the map's attention; see the comment on the pull request, act on each line, then run systemap refresh."
          fi
          exit "$code"
"""


# What `init` says about the repository's own gates: the model imports
# systemap, which the repository need not depend on, so a strict type
# checker and a dependency checker both need telling. mypy is answered in
# the file; deptry by these lines, printed so they can be pasted.
TOOLING_NOTE = (
    "note: map/model.py imports systemap, a tool this repository runs and need not depend on:",
    "  mypy --strict: the import line carries # type: ignore[import-not-found, "
    "unused-ignore], so it passes as written",
    "  deptry: add these lines to pyproject.toml",
    "    [tool.deptry.per_rule_ignores]",
    '    DEP001 = ["systemap"]',
    '    DEP003 = ["systemap"]',
    "  run every CI command the repository runs on the map's files, not only pre-commit",
)


def files(name: str, package: str, roots: list[tuple[str, str]], ci: bool = True) -> dict[str, str]:
    """path -> content for every file `systemap init` writes.

    The skill is not in this table: it is package text that is refreshed
    on every init, where everything here is written once and then kept.
    """
    if roots:
        lines = ["[package_roots]"] + [f'"{path}" = "{pkg}"' for path, pkg in roots]
        roots_block = "\n".join(lines)
    else:
        roots_block = '# [package_roots]\n# "src/mypackage" = "mypackage"'
    out = {
        "systemap.toml": CONFIG.format(name=name, roots=roots_block, package=package),
        "map/model.py": MODEL.format(name=name, upper=name.upper(), package=package),
        "docs/map/.gitkeep": "",
    }
    if ci:
        out[".github/workflows/systemap.yml"] = WORKFLOW.replace("__VERSION__", __version__)
    return out


def write(
    root: Path, name: str, package: str, roots: list[tuple[str, str]], ci: bool = True
) -> list[str]:
    """Write every file that does not exist yet; return one line per file."""
    out: list[str] = []
    for rel, content in files(name, package, roots, ci).items():
        path = root / rel
        if path.exists():
            out.append(f"kept {rel} (already exists)")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        out.append(f"wrote {rel}")
    return out
