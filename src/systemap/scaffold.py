"""Files that the init command writes for a new system map.

The initial model has one container, four regions, and no components.
The installed skill gives the source examination and the writing rules of each writing profile.
The agent writes components from source facts and calculates positions with the placement command.

The optional CI workflow uses the released package version that made it.
The project does not need systemap as a declared dependency."""

from __future__ import annotations

import argparse
from pathlib import Path

from systemap import __version__, model_load
from systemap import language as languages

CONFIG = """# systemap configuration. All keys are optional.
# The project name comes from pyproject.toml or the repository directory.
language = "{language}"
name = {name}
model = "map/model.py"
out_dir = "docs/map"
# Test directories can be one path or a list of paths.
# Without this key, the extractor finds directories with the name tests or test.
# tests_dir = ["tests"]
# spec_path = "docs/design.md"

# Keep these keys above the table lines. A key after a table header is part of that table.
{roots_note}
{roots}

# The writing profile selects the writing rules for the map text that a person reads.
# "plain" selects the common writing rules of the installed skill. A person or a program
# can examine these rules without a dictionary.
# "asd-ste100" also selects the full ASD-STE100 Issue 9 rules. These rules need the
# official ASD dictionary.
[writing]
profile = "plain"

# Each source module must have a component assignment or a recorded ignore.
# Each ignore must give an explanation.
# [coverage]
# ignore = [{{ module = "{package}.compat", reason = "Compatibility code outside the mapped system." }}]

# An exact answer identifies a complete judgement finding and its explanation.
# systemap judgement counts the answered findings and gives the stale answers.
# An exact answer must have the evidence digest from its pending answer line.
# [judgement]
# answered = [{{ item = "single module: Reader contains only {package}.reader", reason = "The reader is a separate component.", evidence = "<digest from the pending answer line>" }}]

# The URL of the map page that CI publishes for each pull request.
# The pull request number replaces {{number}}.
# With this value, CI posts one comment with a link to the Changes view of that page.
# [delta]
# page_url = "https://example.org/pr-{{number}}/"

# The refresh command renders these figures in the output directory.
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
# accent = "#D98E04"
"""

MODEL = '''# ruff: noqa: E501
"""The system map of {doc_name}.

All reader text must obey the writing profile in systemap.toml ([writing] profile).
Before you write names or sentences, read the language policy of the installed systemap skill.
The "plain" profile has no dictionary step. The "asd-ste100" profile needs the ASD dictionary.

The extractor supplies source facts. This file records component purposes and flow claims.
Each component identifies its source modules and an applicable public entry point.
Before a maintainer records support for a claim, the maintainer must examine the source.

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
        label={label},
        sub="one process",
        box=(16, 16, 876, 536),
        tone="server",
    ),
)

# fmt: off
# A region contains a group of components. The initial grid has 48-unit column corridors and 36-unit row corridors.
REGIONS = (
    Region(id="a", label="REGION A", box=(40, 60, 390, 216), container="system"),
    Region(id="b", label="REGION B", box=(478, 60, 390, 216), container="system"),
    Region(id="c", label="REGION C", box=(40, 312, 390, 216), container="system"),
    Region(id="d", label="REGION D", box=(478, 312, 390, 216), container="system"),
)
# fmt: on

# fmt: off
# Write one component for each task in the source.
# implemented_by gives source modules. entry gives a public source symbol.
# Do not set x and y. The placement command calculates them.
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


# Give short component descriptions, layer questions, and one sentence for each flow.
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

# The committed map must agree with the source facts and the renderer.
# This workflow uses the package version that made it.
# When you install a new systemap version, change the version in this file.
#
# SYSTEMAP_CI below controls what a map finding does. With advisory, a finding gives a
# warning and the job passes. With strict, a finding makes the job fail. When systemap
# cannot run, the job fails with both values. The delta log gives each action.
# Only the link job can write a pull request comment. It runs only if
# [delta] page_url in systemap.toml gives the map page of each pull request,
# and only for a pull request from a branch of this repository.


on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

env:
  # advisory: a map finding gives a warning. strict: a map finding makes the job fail.
  SYSTEMAP_CI: __CI_MODE__

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
          code=0
          uvx --from "systemap==__VERSION__" systemap extract --check || code=$?
          if [ "$code" = "1" ]; then
            level=warning
            if [ "$SYSTEMAP_CI" = "strict" ]; then level=error; fi
            echo "::$level title=Stale map::Source facts do not agree with the repository. Run systemap refresh. Then commit the output directory."
            if [ "$SYSTEMAP_CI" = "strict" ]; then exit 1; fi
          elif [ "$code" != "0" ]; then
            echo "::error title=Stale map::systemap could not run (exit $code). The lines above give the reason."
            exit "$code"
          fi

      - name: Map consistency checks
        run: |
          code=0
          uvx --from "systemap==__VERSION__" systemap check || code=$?
          if [ "$code" = "1" ]; then
            level=warning
            if [ "$SYSTEMAP_CI" = "strict" ]; then level=error; fi
            echo "::$level title=Map check::The model has fields that do not agree, or modules without a component. Examine the findings above."
            if [ "$SYSTEMAP_CI" = "strict" ]; then exit 1; fi
          elif [ "$code" != "0" ]; then
            echo "::error title=Map check::systemap could not run (exit $code). The lines above give the reason."
            exit "$code"
          fi

      - name: Judgement answers
        run: |
          code=0
          uvx --from "systemap==__VERSION__" systemap judgement --strict || code=$?
          if [ "$code" = "1" ]; then
            level=warning
            if [ "$SYSTEMAP_CI" = "strict" ]; then level=error; fi
            echo "::$level title=Judgement::A judgement finding has no answer. Change the map or record an answer under [judgement] answered in systemap.toml."
            if [ "$SYSTEMAP_CI" = "strict" ]; then exit 1; fi
          elif [ "$code" != "0" ]; then
            echo "::error title=Judgement::systemap could not run (exit $code). The lines above give the reason."
            exit "$code"
          fi

      - name: Rendered page matches
        run: |
          code=0
          uvx --from "systemap==__VERSION__" systemap render --check || code=$?
          if [ "$code" = "1" ]; then
            level=warning
            if [ "$SYSTEMAP_CI" = "strict" ]; then level=error; fi
            echo "::$level title=Stale map::index.html does not agree with the renderer output. Run systemap refresh. Then commit the output directory."
            if [ "$SYSTEMAP_CI" = "strict" ]; then exit 1; fi
          elif [ "$code" != "0" ]; then
            echo "::error title=Stale map::systemap could not run (exit $code). The lines above give the reason."
            exit "$code"
          fi

  delta:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    timeout-minutes: 10
    outputs:
      comment: ${{ steps.delta.outputs.comment }}
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
        id: delta
        env:
          BASE: ${{ github.event.pull_request.base.sha }}
          HEAD: ${{ github.event.pull_request.head.sha }}
          PR: ${{ github.event.pull_request.number }}
        run: |
          code=0
          uvx --from "systemap==__VERSION__" systemap delta --base "$BASE" --head "$HEAD" --pr "$PR" --comment comment.md || code=$?
          echo "$code" > delta.code
          if [ -s comment.md ]; then
            {
              echo "comment<<SYSTEMAP_COMMENT"
              cat comment.md
              echo "SYSTEMAP_COMMENT"
            } >> "$GITHUB_OUTPUT"
          fi

      - name: Map is current
        run: |
          code="$(cat delta.code)"
          if [ "$code" = "1" ]; then
            level=warning
            if [ "$SYSTEMAP_CI" = "strict" ]; then level=error; fi
            echo "::$level title=Map delta::A map update is necessary. Do the action in each line of the Map change results step. Then run the command in its last line."
            if [ "$SYSTEMAP_CI" = "strict" ]; then exit 1; fi
          elif [ "$code" != "0" ]; then
            echo "::error title=Map delta::systemap delta could not run (exit $code). The Map change results step gives the reason."
            exit "$code"
          fi

  # This job runs only if [delta] page_url in systemap.toml gives the map page of each pull request.
  # It runs only for a pull request from a branch of this repository. The code and the settings
  # of a pull request from a fork can change the comment text.
  link:
    needs: delta
    if: >-
      ${{ !cancelled() && needs.delta.outputs.comment != ''
      && github.event.pull_request.head.repo.full_name == github.repository }}
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions:
      pull-requests: write # this job posts or updates the link comment
    steps:
      - name: Link to the Changes view
        env:
          BODY: ${{ needs.delta.outputs.comment }}
          GH_TOKEN: ${{ github.token }}
          PR: ${{ github.event.pull_request.number }}
          REPO: ${{ github.repository }}
        run: |
          existing="$(gh api "repos/$REPO/issues/$PR/comments" --paginate --jq 'map(select(.body | startswith("<!-- systemap delta -->"))) | first | .id // empty' | head -n 1)"
          if [ -n "$existing" ]; then
            gh api -X PATCH "repos/$REPO/issues/comments/$existing" -f body="$BODY" > /dev/null
          else
            gh api -X POST "repos/$REPO/issues/$PR/comments" -f body="$BODY" > /dev/null
          fi || echo "::warning title=Map link::The job could not write the comment. A fork pull request has a read-only token."
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

# TOML basic strings and Python string literals use the same escapes for these characters.
_ESCAPES: dict[int, str] = {ord('"'): '\\"', ord("\\"): "\\\\"} | {
    code: f"\\u{code:04x}" for code in (*range(0x20), 0x7F)
}


def quoted(text: str) -> str:
    """Give a double-quoted string that TOML and Python both read as `text`."""
    return '"' + text.translate(_ESCAPES) + '"'


def tooling_note(root: Path, language: str) -> tuple[str, ...]:
    """Give the note about repository tool settings for the map files.

    The model file is Python. The repository tools read it if the source language uses
    the suffix of the model file, or if pyproject.toml is available. Otherwise the
    repository has no tool settings for the model file."""
    reads_model = model_load.MODEL_SUFFIX in languages.repository(language).source_suffixes
    if not reads_model and not (root / "pyproject.toml").is_file():
        return ()
    return TOOLING_NOTE


def _roots_block(roots: list[tuple[str, str]], language: str) -> str:
    """Give the [package_roots] table, or a commented example without roots."""
    if not roots:
        return languages.repository(language).roots_example
    lines = ["[package_roots]"] + [f"{quoted(path)} = {quoted(pkg)}" for path, pkg in roots]
    return "\n".join(lines)


# The value of SYSTEMAP_CI in the workflow. An empty value writes no workflow.
ADVISORY = "advisory"
STRICT = "strict"


def add_ci_options(parser: argparse.ArgumentParser) -> None:
    """Add the init options that select the CI workflow."""
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--no-ci", action="store_true", help="Do not write .github/workflows/systemap.yml."
    )
    group.add_argument(
        "--strict-ci",
        action="store_true",
        help=(
            "Write a workflow whose jobs fail on a map finding. Without this option, a "
            "finding gives a warning and the jobs pass."
        ),
    )


def ci_mode(args: argparse.Namespace) -> str:
    """Give the workflow mode that the init options select, or "" for no workflow."""
    if args.no_ci:
        return ""
    return STRICT if args.strict_ci else ADVISORY


def files(
    name: str,
    package: str,
    roots: list[tuple[str, str]],
    ci: str = ADVISORY,
    *,
    language: str,
) -> dict[str, str]:
    """Get initial file paths and contents.

    The init command installs the skill separately on each run.
    Existing configuration, model, and workflow files stay unchanged. `ci` is the
    workflow mode (ADVISORY or STRICT); an empty value writes no workflow."""
    out = {
        "systemap.toml": CONFIG.format(
            language=language,
            name=quoted(name),
            roots_note=languages.repository(language).roots_note,
            roots=_roots_block(roots, language),
            package=package,
        ),
        "map/model.py": MODEL.format(
            doc_name=quoted(name)[1:-1], label=quoted(name.upper()), package=package
        ),
        "docs/map/.gitkeep": "",
    }
    if ci:
        extra = languages.repository(language).install_extra
        requirement = f"systemap[{extra}]=={__version__}" if extra else f"systemap=={__version__}"
        out[".github/workflows/systemap.yml"] = WORKFLOW.replace(
            "systemap==__VERSION__", requirement
        ).replace("__CI_MODE__", ci)
    return out


def write(
    root: Path,
    name: str,
    package: str,
    roots: list[tuple[str, str]],
    ci: str = ADVISORY,
    *,
    language: str,
) -> list[str]:
    """Write missing files. Give one output line for each written or existing file."""
    out: list[str] = []
    for rel, content in files(name, package, roots, ci, language=language).items():
        path = root / rel
        if path.exists():
            out.append(f"kept {rel} (file exists)")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        out.append(f"wrote {rel}")
    return out
