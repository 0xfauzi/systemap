"""What `systemap init` writes: a configuration, a starter model, a workflow.

The starter model is the smallest map that passes every check: one
container, one region inside it, two components and one flow between them,
one layer, one journey of one step and one invariant. An agent following
the skill (installed by the same command, see skill.py) replaces the words
and adds cards from there; a person may do the same by hand.

The workflow runs the check on every push and pull request. It is written
by default and skipped with `--no-ci`, since not every repository runs on
the one forge the workflow is written for.
"""

from __future__ import annotations

from pathlib import Path

CONFIG = """# systemap configuration. Every key is optional; these are the defaults
# except name, which defaults to the directory's name.
name = "{name}"
# Where the packages are: "path" = "import name". Leave it out to discover
# every top-level directory (or src/<dir>) that holds an __init__.py.
{roots}
tests_dir = "tests"
model = "map/model.py"
out_dir = "docs/map"
# issue_url = "https://example.invalid/issues/{{n}}"
# spec_path = "docs/design.md"

# `systemap check` refuses a map that leaves a module unclaimed. A module
# that has no place on the map is ignored here, and every ignore needs a
# reason, so the hole is on record rather than hidden.
[coverage]
ignore = [
    {{ module = "{package}", reason = "the package root only marks the directory as a package" }},
]

# Figures `systemap refresh` regenerates beside the page. mode is "system"
# (nothing marked) or "reach" (the named components marked as a plan's reach).
[[figures]]
out = "system.html"
mode = "system"
interactive = true

# [theme]
# accent = "#5DADE2"
"""

MODEL = '''"""The system map of {name}: what the parts are and what they are to each other.

Everything in this file is written by a person on purpose. The facts about
the code (which modules exist, what they export, which tests import them)
are read by `systemap extract`; this file says what the system is MEANT to
be, and the map draws the two together. Build state is derived: a component
is built when the entry named in `entry` exists in the modules named in
`implemented_by`.

Positions are hand-placed on a grid because this is a topology, not a chart:
a card's place carries meaning. `systemap check` verifies every card sits in
its band, no two overlap, every flow has a layer and a sentence, and every
route and label is clean.
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
COL = {{"c1": 80, "c2": 370}}
ROW = {{"r1": 130}}

CONTAINERS = (
    Container(
        id="system",
        label="{upper}",
        sub="one process; replace this line with what the boundary means",
        box=(16, 16, 568, 268),
        tone="server",
    ),
)

REGIONS = (Region(id="core", label="CORE", box=(40, 60, 520, 200), container="system"),)

COMPONENTS = (
    Component(
        id="Reader",
        region="core",
        does="Reads the input and turns it into a request.",
        interface="read(source) -> Request",
        implemented_by=("{package}.reader",),
        entry="read",
        x=COL["c1"],
        y=ROW["r1"],
    ),
    Component(
        id="Writer",
        region="core",
        does="Takes a request and writes the result.",
        interface="write(request) -> Result",
        implemented_by=("{package}.writer",),
        entry="write",
        x=COL["c2"],
        y=ROW["r1"],
    ),
)

# (from, to, the artifact carried, the dataflow kind)
FLOWS = (Flow("Reader", "Writer", "request", "work"),)

FLOW_KINDS = ("work",)

INVARIANTS = (
    Invariant(1, "The writer never reads the input itself.", governs=("Writer",)),
)

MODEL = Model(
    canvas=(600, 300),
    containers=CONTAINERS,
    regions=REGIONS,
    components=COMPONENTS,
    flows=FLOWS,
    flow_kinds=FLOW_KINDS,
    invariants=INVARIANTS,
)

# ---- meaning: the plain words, the layers, one sentence per flow ---------

PLAIN = {{
    "Reader": "the part that reads",
    "Writer": "the part that writes",
}}

LAYERS = (
    Layer(
        id="work",
        label="Work",
        question="How does an input become an output?",
        sub="the forward path",
    ),
)

LAYER_OF_KIND = {{"work": "work"}}

RELATIONS = {{
    ("Reader", "Writer"): "The reader hands the writer one request at a time; the writer never goes back to the source.",
}}

VERBS = {{"work": ("hands to", "receives from")}}

JOURNEYS = (
    Journey(
        id="input-to-output",
        label="An input becomes an output",
        steps=(
            Step(
                acts=("Reader",),
                measures=(),
                edge=("Reader", "Writer"),
                say="The reader parses the input and hands the writer a request; nothing measures this step yet.",
            ),
        ),
    ),
)

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

      - name: Install project
        run: uv sync --frozen --all-extras --dev

      - name: facts match the tree
        run: |
          uv run systemap extract --check || {
            echo "::error title=Map is stale::the facts no longer describe the tree. Run systemap refresh and commit the output directory."
            exit 1
          }

      - name: layout, meaning and coverage are consistent
        run: |
          uv run systemap check || {
            echo "::error title=Map check::the model contradicts itself or leaves a module unmapped; see the lines above."
            exit 1
          }

      - name: page matches the renderer
        run: |
          uv run systemap render --check || {
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
        out[".github/workflows/systemap.yml"] = WORKFLOW
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
