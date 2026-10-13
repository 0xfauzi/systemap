"""Entry point coverage uses only language-neutral facts and the scope of each map.

Codex result change-7. An import from the module of a console script does not show that
an entry point starts the same operation. Acceptance values:

- Python fixture: `pkg.__main__` imports a constant from `pkg.tools`, which supplies the
  console script `tool`. The coverage list has `python -m pkg` and `tool`. Before the
  repair, the list did not have `python -m pkg`.
- Python fixture: `pkg.__main__` calls `run`, the target of the script. The adapter
  writes `same_as` with the identity of the script, and the list has only `tool`.
- TypeScript fixture: the package root imports a constant from the module of a `bin`
  script. The list has the two entry points, and each `same_as` is empty.

Codex result change-17. Two nested maps each cover their own entry point. Acceptance
value: `systemap describe` gives `1 of 1 have sequence coverage` for each map and no
entry point without a sequence, as `systemap judgement` does. The test uses a Python
fixture and a TypeScript fixture. Before the repair, each map gave `1 of 2` and the
entry point of the other map.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree

from systemap import config, extract, facts_file, source_facts
from systemap.cli import main
from systemap.journey_coverage import ways_in_without_journey
from systemap.model import Meaning

PYPROJECT = '[project]\nname = "pkg"\nversion = "0"\n[project.scripts]\ntool = "pkg.tools:run"\n'
TOOLS = 'NAME = "tools"\n\n\ndef run() -> None:\n    print(NAME)\n'


def python_points(root: Path, main_module: str) -> tuple[list[str], dict[str, Any]]:
    write_tree(
        root,
        {
            "pyproject.toml": PYPROJECT,
            "systemap.toml": '[package_roots]\n"pkg" = "pkg"\n',
            "pkg/__init__.py": "",
            "pkg/tools.py": TOOLS,
            "pkg/__main__.py": main_module,
        },
    )
    facts = extract.build(config.load(root))
    return [p["name"] for p in ways_in_without_journey(Meaning(plain={}), facts)], facts


def test_an_import_of_a_constant_does_not_join_two_python_entry_points(tmp_path: Path) -> None:
    names, facts = python_points(tmp_path, "from pkg.tools import NAME\n\nprint(NAME)\n")
    assert names == ["tool", "python -m pkg"]
    assert not any(p["same_as"] for p in facts["entry_points"])


def test_a_main_module_that_calls_the_script_target_is_the_same_operation(
    tmp_path: Path,
) -> None:
    names, facts = python_points(tmp_path, "from pkg.tools import run\n\nrun()\n")
    assert names == ["tool"]
    script = next(p for p in facts["entry_points"] if p["kind"] == "console_script")
    module = next(p for p in facts["entry_points"] if p["kind"] == "main_module")
    assert module["same_as"] == source_facts.entry_identity(script)


def test_an_import_of_a_constant_does_not_join_two_typescript_entry_points(
    tmp_path: Path,
) -> None:
    write_tree(
        tmp_path,
        {
            "package.json": '{"name":"web","bin":{"web":"src/cli.ts"},"exports":"./src/index.ts"}',
            "tsconfig.json": '{"compilerOptions":{}}',
            "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
            "src/cli.ts": "export const LIMIT = 3;\nexport function main(): void {}\n",
            "src/index.ts": (
                'import { LIMIT } from "./cli";\nexport function serve(): number { return LIMIT }\n'
            ),
        },
    )
    facts = extract.build(config.load(tmp_path))
    names = [p["name"] for p in ways_in_without_journey(Meaning(plain={}), facts)]
    assert names == ["web", "serve"]
    assert not any(p["same_as"] for p in facts["entry_points"])


# ---- change-17: describe uses the scope of each map ---------------------------------

TOP = """
from systemap import Component, Container, Flow, Journey, Meaning, Model, Region, Step

CONTAINERS = (Container(id="system", label="SYSTEM", box=(0, 0, 0, 0), tone="server"),)
REGIONS = (Region(id="core", label="CORE", box=(0, 0, 0, 0), container="system"),)
COMPONENTS = (
    Component(id="Cli", does="Starts a run.", implemented_by=("{cli}",), region="core"),
    Component(id="Inner", does="Does the work.", implemented_by=("{inner}.*",), region="core",
              map="inner.py"),
)
FLOWS = (Flow("Cli", "Inner", "request", "data"),)
MODEL = Model(canvas=(0, 0), containers=CONTAINERS, regions=REGIONS, components=COMPONENTS,
              flows=FLOWS, flow_kinds=())
MEANING = Meaning(
    plain={{"Cli": "the start", "Inner": "the work"}},
    relations={{("Cli", "Inner"): "The start gives the work one request."}},
    journeys=(
        Journey(id="start", label="A run starts", covers=({start!r},), steps=(
            Step(acts=("Cli",), measures=(), edge=("Cli", "Inner"), say="The start sends a request."),
        )),
    ),
)
"""

INNER = """
from systemap import Component, Container, Flow, Journey, Meaning, Model, Region, Step

CONTAINERS = (
    Container(id="around", label="AROUND", box=(0, 0, 0, 0), tone="host"),
    Container(id="inner", label="INNER", box=(0, 0, 0, 0), tone="server"),
)
REGIONS = (Region(id="work", label="WORK", box=(0, 0, 0, 0), container="inner"),)
COMPONENTS = (
    Component(id="Cli", does="The component that calls in.", kind="actor", container="around"),
    Component(id="Tool", does="Does one task.", implemented_by=("{tool}",), region="work"),
)
FLOWS = (Flow("Cli", "Tool", "request", "data"),)
MODEL = Model(canvas=(0, 0), containers=CONTAINERS, regions=REGIONS, components=COMPONENTS,
              flows=FLOWS, flow_kinds=())
MEANING = Meaning(
    plain={{"Cli": "the start", "Tool": "the task"}},
    relations={{("Cli", "Tool"): "The start gives the task one request."}},
    journeys=(
        Journey(id="task", label="A task starts", covers=({start!r},), steps=(
            Step(acts=("Cli",), measures=(), edge=("Cli", "Tool"), say="The start sends a request."),
        )),
    ),
)
"""

PYTHON_TREE = {
    "systemap.toml": '[package_roots]\n"pkg" = "pkg"\n',
    "pkg/__init__.py": "",
    "pkg/cli.py": "def main() -> None:\n    return None\n",
    "pkg/inner/__init__.py": "",
    "pkg/inner/tool.py": "def main() -> None:\n    return None\n",
}
PYTHON_NAMES = {
    "cli": "pkg.cli",
    "inner": "pkg.inner",
    "tool": "pkg.inner.tool",
    "top": '["main_function","pkg.cli","main","main"]',
    "nested": '["main_function","pkg.inner.tool","main","main"]',
}

TYPESCRIPT_TREE = {
    "package.json": '{"name":"web","bin":{"web":"src/cli.ts","tool":"src/inner/tool.ts"}}',
    "tsconfig.json": '{"compilerOptions":{}}',
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
    "src/cli.ts": "export function main(): void {}\n",
    "src/inner/tool.ts": "export function main(): void {}\n",
}
TYPESCRIPT_NAMES = {
    "cli": "web.cli",
    "inner": "web.inner",
    "tool": "web.inner.tool",
    "top": '["console_script","web.cli","","web"]',
    "nested": '["console_script","web.inner.tool","","tool"]',
}


@pytest.mark.parametrize(
    ("tree", "names"),
    [(PYTHON_TREE, PYTHON_NAMES), (TYPESCRIPT_TREE, TYPESCRIPT_NAMES)],
    ids=["python", "typescript"],
)
def test_describe_gives_the_coverage_of_each_nested_map(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    tree: dict[str, str],
    names: dict[str, str],
) -> None:
    top = TOP.format(cli=names["cli"], inner=names["inner"], start=names["top"])
    inner = INNER.format(tool=names["tool"], start=names["nested"])
    write_tree(tmp_path, {**tree, "map/model.py": top, "map/inner.py": inner})
    assert main(["--root", str(tmp_path), "extract"]) == 0
    facts = facts_file.read_facts(config.load(tmp_path).facts_path)
    identities = {source_facts.entry_identity(p) for p in facts["entry_points"]}
    assert identities == {names["top"], names["nested"]}
    capsys.readouterr()
    assert main(["--root", str(tmp_path), "describe"]) == 0
    out = capsys.readouterr().out
    assert out.count("entry points: 1 of 1 have sequence coverage") == 2, out
    assert "without a sequence" not in out
    main(["--root", str(tmp_path), "judgement"])
    assert "has no sequence" not in capsys.readouterr().out


@pytest.mark.parametrize(
    ("tree", "names", "extra"),
    [
        (PYTHON_TREE, PYTHON_NAMES, {"pkg/extra.py": "def main() -> None:\n    return None\n"}),
        (
            TYPESCRIPT_TREE,
            TYPESCRIPT_NAMES,
            {
                "package.json": (
                    '{"name":"web","bin":{"web":"src/cli.ts","tool":"src/inner/tool.ts",'
                    '"extra":"src/extra.ts"}}'
                ),
                "src/extra.ts": "export function main(): void {}\n",
            },
        ),
    ],
    ids=["python", "typescript"],
)
def test_journeys_uses_the_scope_of_judgement(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    tree: dict[str, str],
    names: dict[str, str],
    extra: dict[str, str],
) -> None:
    """Acceptance: an entry point in a module that no component claims has no sequence.
    `systemap judgement` gives one line for it, and `systemap journeys --dry-run` lists
    one entry point. Before the repair, `journeys` used its own scope and listed none.
    """
    top = TOP.format(cli=names["cli"], inner=names["inner"], start=names["top"])
    inner = INNER.format(tool=names["tool"], start=names["nested"])
    write_tree(tmp_path, {**tree, **extra, "map/model.py": top, "map/inner.py": inner})
    assert main(["--root", str(tmp_path), "extract"]) == 0
    capsys.readouterr()
    main(["--root", str(tmp_path), "judgement"])
    assert capsys.readouterr().out.count("has no sequence") == 1
    assert main(["--root", str(tmp_path), "journeys", "--dry-run"]) == 0
    assert "journeys: 1 entry point without a sequence" in capsys.readouterr().out
