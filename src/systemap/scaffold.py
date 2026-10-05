"""Files that the init command writes for a new system map.

The initial model has one container, four regions, and no components.
The installed skill gives the source examination and ASD-STE100 language requirements.
The agent writes components from source facts and calculates positions with the placement command.

The optional CI workflow uses the released package version that made it.
The project does not need systemap as a declared dependency."""

from __future__ import annotations

from pathlib import Path

from systemap import __version__

CONFIG = """# systemap configuration. All keys are optional.
# The project name comes from pyproject.toml or the repository directory.
language = "{language}"
name = "{name}"
# Package roots use "path" = "import name".
# Without explicit roots, the extractor finds top-level Python packages
# in the repository and its uv workspace members.
{roots}
# Test directories can be one path or a list of paths.
# Without this key, the extractor finds directories called tests or test.
# tests_dir = ["tests"]
model = "map/model.py"
out_dir = "docs/map"
# spec_path = "docs/design.md"

# Each source module must have a component assignment or a recorded ignore.
# Each ignore must give an explanation.
# [coverage]
# ignore = [{{ module = "{package}.compat", reason = "Compatibility code outside the mapped system." }}]

# An exact answer identifies a complete judgement finding and its explanation.
# The command counts answered findings and gives stale-answer findings.
# [judgement]
# answered = [{{ item = "single module: Reader is only {package}.reader", reason = "The reader is a separate component." }}]

# The refresh command renders these figures beside the page.
# mode is "system" for all components or "reach" for a plan selection.
# layer selects the flow view. A .svg path gives an SVG figure.
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
"""The system map of {name}.

All reader text must use ASD-STE100 Issue 9.
Before you write names or sentences, read the installed systemap skill language policy.
Use the official writing rules and dictionary, including approved word meanings.

The extractor supplies source facts. This file records component purposes and flow claims.
Each component identifies its source modules and an applicable public entry point.
A maintainer must examine the source before recording support for a claim.

The initial model has one container and four regions, without components.
Write components from source facts. Then run systemap place to calculate positions.
With --all, the placement command calculates positions again but keeps pinned cards.
Read references/layout.md for the applicable geometry rules.
"""

from __future__ import annotations

# The generated model uses the systemap tool package.
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

# Containers give system boundaries.
CONTAINERS = (
    Container(
        id="system",
        label="{upper}",
        sub="one process",
        box=(16, 16, 876, 536),
        tone="server",
    ),
)

# fmt: off
# Regions group components. The initial grid has 48-unit column corridors and 36-unit row corridors.
REGIONS = (
    Region(id="a", label="REGION A", box=(40, 60, 390, 216), container="system"),
    Region(id="b", label="REGION B", box=(478, 60, 390, 216), container="system"),
    Region(id="c", label="REGION C", box=(40, 312, 390, 216), container="system"),
    Region(id="d", label="REGION D", box=(478, 312, 390, 216), container="system"),
)
# fmt: on

# fmt: off
# Write one component per source responsibility.
# implemented_by gives source modules. entry gives a public source symbol.
# Omit x and y until the placement command runs.
COMPONENTS: tuple[Component, ...] = ()
# fmt: on

# Each flow gives source, target, artifact, and kind.
# Use at most three words for a new artifact noun.
FLOWS: tuple[Flow, ...] = ()

FLOW_KINDS: tuple[str, ...] = ()

# Record source-supported rules with source references and applicable component identifiers.
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


# Give short component descriptions, layer questions, and one sentence per flow.
PLAIN: dict[str, str] = {{}}

LAYERS: tuple[Layer, ...] = ()

LAYER_OF_KIND: dict[str, str] = {{}}

RELATIONS: dict[tuple[str, str], str] = {{}}

VERBS: dict[str, tuple[str, str]] = {{"data": ("sends to", "receives from")}}

# Each sequence starts at an entry point. Each step identifies its components and flow.
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

# The committed map must match the source facts and renderer.
# This workflow uses the package version that made it.
# Change the package pin when you install a new systemap version.
# Only the delta job has permission to write a pull request comment.


on:
  push:
    branches: [main]
  pull_request:

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

      - name: Source facts match
        run: |
          uvx --from "systemap==__VERSION__" systemap extract --check || {
            echo "::error title=Stale map::Source facts do not match the repository. Run systemap refresh and commit the output directory."
            exit 1
          }

      - name: Map consistency checks
        run: |
          uvx --from "systemap==__VERSION__" systemap check || {
            echo "::error title=Map check::The model has inconsistent fields or unmapped modules. Examine the findings above."
            exit 1
          }

      - name: Judgement answers
        run: |
          uvx --from "systemap==__VERSION__" systemap judgement --strict || {
            echo "::error title=Judgement::A judgement finding has no answer. Change the map or record an answer under [judgement] answered in systemap.toml."
            exit 1
          }

      - name: Rendered page matches
        run: |
          uvx --from "systemap==__VERSION__" systemap render --check || {
            echo "::error title=Stale map::index.html does not match the renderer output. Run systemap refresh and commit the output directory."
            exit 1
          }

  delta:
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

      - name: Map change results
        env:
          BASE: ${{ github.event.pull_request.base.sha }}
          HEAD: ${{ github.event.pull_request.head.sha }}
        run: |
          code=0
          uvx --from "systemap==__VERSION__" systemap delta --base "$BASE" --head "$HEAD" --format markdown > delta.md || code=$?
          echo "$code" > delta.code
          if [ ! -s delta.md ]; then
            printf '<!-- systemap delta -->\\n## Map change results\\n\\nsystemap delta could not run (exit %s). Examine the workflow log.\\n' "$code" > delta.md
          fi
          cat delta.md

      - name: Write the delta comment
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
          fi || echo "::warning title=Map delta::The command could not write the comment. A fork pull request has a read-only token. The preceding step contains the delta."

      - name: Delta findings answered
        run: |
          code="$(cat delta.code)"
          if [ "$code" != "0" ]; then
            echo "::error title=Map delta::The change has unanswered map findings. Examine the pull request comment, answer each finding, then run systemap refresh."
          fi
          exit "$code"
"""


# What `init` says about the repository's own gates: the model imports
# systemap, which the repository need not depend on, so a strict type
# checker and a dependency checker both need telling. mypy is answered in
# the file; deptry by these lines, printed so they can be pasted.
TOOLING_NOTE = (
    "note: map/model.py imports the systemap tool package:",
    "  mypy --strict: the import has # type: ignore[import-not-found, unused-ignore]",
    "  deptry: add these lines to pyproject.toml",
    "    [tool.deptry.per_rule_ignores]",
    '    DEP001 = ["systemap"]',
    '    DEP003 = ["systemap"]',
    "  run all repository CI commands on the map files",
)


def files(
    name: str,
    package: str,
    roots: list[tuple[str, str]],
    ci: bool = True,
    language: str = "python",
) -> dict[str, str]:
    """Get initial file paths and contents.

    The init command installs the skill separately on each run.
    Existing configuration, model, and workflow files stay unchanged."""
    if roots:
        lines = ["[package_roots]"] + [f'"{path}" = "{pkg}"' for path, pkg in roots]
        roots_block = "\n".join(lines)
    else:
        roots_block = '# [package_roots]\n# "src/mypackage" = "mypackage"'
    out = {
        "systemap.toml": CONFIG.format(
            language=language, name=name, roots=roots_block, package=package
        ),
        "map/model.py": MODEL.format(name=name, upper=name.upper(), package=package),
        "docs/map/.gitkeep": "",
    }
    if ci:
        requirement = (
            f"systemap[typescript]=={__version__}"
            if language == "typescript"
            else f"systemap=={__version__}"
        )
        out[".github/workflows/systemap.yml"] = WORKFLOW.replace(
            "systemap==__VERSION__", requirement
        )
    return out


def write(
    root: Path,
    name: str,
    package: str,
    roots: list[tuple[str, str]],
    ci: bool = True,
    language: str = "python",
) -> list[str]:
    """Write missing files. Give one output line for each written or existing file."""
    out: list[str] = []
    for rel, content in files(name, package, roots, ci, language).items():
        path = root / rel
        if path.exists():
            out.append(f"kept {rel} (file exists)")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        out.append(f"wrote {rel}")
    return out
