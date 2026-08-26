"""What `systemap init` writes: a configuration, a starter model, a workflow.

The starter model is empty on purpose: one container holding four regions
in a two-by-two grid, with the corridors between them already there, and
no components, no flows. A placeholder card would be a lie the first
check had to catch; instead the check says the model has no components
yet and points at the skill, and the agent following it (installed by the
same command, see skill.py) writes the real cards from the facts. The
regions come laid out so the first draft inherits a drawable shape: with
more than two full-width bands stacked there is no corridor for an edge
between the outer two, and the check refuses the route.

The workflow runs the check on every push and pull request with the
released package (`uvx --from "systemap==<this version>"`), so the
project needs no dependency on systemap; it does need the package on
PyPI. It is written by default and skipped with `--no-ci`, since not
every repository runs on the one forge the workflow is written for.
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

MODEL = '''# ruff: noqa: E501, F401
# The map is prose held in strings: a sentence per flow, a step per journey,
# a rule per invariant. A sentence is not wrapped, so the line-length rule
# does not apply to this file; and the schema is imported whole, so a card
# written later finds every name.
"""The system map of {name}: what the parts are and what they are to each other.

Everything in this file is written on purpose. The facts about the code
(which modules exist, what they export, which tests import them) are read
by `systemap extract`; this file says what the system is MEANT to be, and
the map draws the two together. The map draws what exists today: a
component names the modules that are it and one entry they define, and
`systemap check` refuses a name the code does not have.

Positions are hand-placed on a grid because this is a topology, not a chart:
a card's place carries meaning. `systemap check` verifies every card sits in
its band, no two overlap, every flow has a layer and a sentence, and every
route and label is clean.

This file starts empty: one container holding four regions in a two-by-two
grid, and no components. The skill says how to write the cards from the
facts; references/layout.md says why the regions sit where they do.
"""

from __future__ import annotations

from systemap import (
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

# The grid: card columns 190 apart (150 card, 40 gutter), rows 92 apart
# (56 card, 36 gutter). Cards on the grid leave straight corridors for edges.
# Two card columns per region column (l1, l2 on the left; r1, r2 on the
# right) and two card rows per region row (t1, t2 at the top; b1, b2 at
# the bottom).
COL = {{"l1": 64, "l2": 254, "r1": 502, "r2": 692}}
ROW = {{"t1": 104, "t2": 196, "b1": 356, "b2": 448}}

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
# you do not need; keep the gaps.
REGIONS = (
    Region(id="a", label="REGION A", box=(40, 60, 390, 216), container="system"),
    Region(id="b", label="REGION B", box=(478, 60, 390, 216), container="system"),
    Region(id="c", label="REGION C", box=(40, 312, 390, 216), container="system"),
    Region(id="d", label="REGION D", box=(478, 312, 390, 216), container="system"),
)

# One card per thing a reader would point at and name. `implemented_by`
# names the modules that are it (from the facts file), `entry` one public
# name they define. For example:
#
#     Component(
#         id="Reader",
#         region="a",
#         does="Reads the input and turns it into a request.",
#         interface="read(source) -> Request",
#         implemented_by=("{package}.reader",),
#         entry="read",
#         x=COL["l1"],
#         y=ROW["t1"],
#     ),
COMPONENTS: tuple[Component, ...] = ()

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

# One journey per entry point that matters, one Step per edge it traces.
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
# systemap runs from the released package, pinned to the version that
# wrote this file, so the project needs no dependency on it. Bump the pin
# when you upgrade.

on:
  push:
    branches: [main]
  pull_request:

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  systemap:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v7

      - name: Install uv
        uses: astral-sh/setup-uv@v7
        with:
          version: latest
          enable-cache: true

      - name: facts match the tree
        run: |
          uvx --from "systemap==__VERSION__" systemap extract --check || {
            echo "::error title=Map is stale::the facts no longer describe the tree. Run systemap refresh and commit the output directory."
            exit 1
          }

      - name: layout, meaning and coverage are consistent
        run: |
          uvx --from "systemap==__VERSION__" systemap check || {
            echo "::error title=Map check::the model contradicts itself or leaves a module unmapped; see the lines above."
            exit 1
          }

      - name: page matches the renderer
        run: |
          uvx --from "systemap==__VERSION__" systemap render --check || {
            echo "::error title=Map is stale::index.html differs from what systemap renders. Run systemap refresh and commit the output directory."
            exit 1
          }
"""


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
