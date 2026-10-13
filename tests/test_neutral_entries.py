"""Shared entry point logic reads neutral facts, not the entry point kinds of one adapter.

Before this change, two shared functions tested the Python kinds `main_function` and
`main_module`:

- `page_sequences.short_entry` gave `main() in <module>` only for `main_function`.
- `journey_coverage._same_script` found the console script that `main_function` and
  `main_module` run again. The test was a Python rule in shared code.

Now the short name uses a neutral property: if the name of the entry point is the name
of its target function, the name alone does not identify it, so the short name adds the
module. Each adapter writes the neutral `same_as` fact: the identity of the entry point
that starts the same code, or an empty string. The facts format is now 9.

Acceptance:

- In a Python fixture, `same_as` of the `main_function` and the `main_module` entry
  points is the identity of the console script. In a TypeScript fixture, `same_as` is
  an empty string for each entry point.
- Without a sequence, the Python fixture gives one entry point without a sequence (the
  console script), and the TypeScript fixture gives each of its entry points.
- If the facts do not have `same_as` (an older facts file), the alias is not known.
  Then the entry point stays in the list. It is not a pass.
- The short name is `main() in shop.cli` for the Python `main` function, `shop` for the
  Python console script, and `web` for the TypeScript console script.
- The shared modules do not contain the literal `main_function` or `main_module`. Only
  the label table of the adapters in `source_facts.py` has them.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from conftest import write_tree

from systemap import config, extract
from systemap.journey_coverage import ways_in_without_journey
from systemap.model import Meaning
from systemap.page_sequences import short_entry
from systemap.source_facts import entry_identity

PYTHON_TREE = {
    "systemap.toml": 'language = "python"\n',
    "pyproject.toml": (
        '[project]\nname = "shop"\nversion = "1"\n[project.scripts]\nshop = "shop.cli:main"\n'
    ),
    "src/shop/__init__.py": "",
    "src/shop/__main__.py": "from shop.cli import main\n\nmain()\n",
    "src/shop/cli.py": "def main() -> None:\n    pass\n",
}
TYPESCRIPT_TREE = {
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
    "package.json": '{"name":"web","bin":{"web":"src/cli.ts"}}',
    "tsconfig.json": '{"compilerOptions":{}}',
    "src/cli.ts": "export function main(): void {}\n",
    "src/index.ts": "export function start(): void {}\n",
}


def _facts(tmp_path: Path, tree: dict[str, str]) -> dict[str, Any]:
    write_tree(tmp_path, tree)
    return extract.build(config.load(tmp_path))


def _by_kind(facts: dict[str, Any]) -> dict[str, dict[str, str]]:
    return {p["kind"]: p for p in facts["entry_points"]}


def test_the_python_adapter_writes_the_same_code_fact(tmp_path: Path) -> None:
    points = _by_kind(_facts(tmp_path, PYTHON_TREE))
    script = entry_identity(points["console_script"])
    assert points["console_script"]["same_as"] == ""
    assert points["main_function"]["same_as"] == script
    assert points["main_module"]["same_as"] == script


def test_the_typescript_adapter_writes_an_empty_same_code_fact(tmp_path: Path) -> None:
    facts = _facts(tmp_path, TYPESCRIPT_TREE)
    assert facts["entry_points"]
    assert all(p["same_as"] == "" for p in facts["entry_points"])


def test_an_alias_gets_no_finding(tmp_path: Path) -> None:
    python = _facts(tmp_path / "py", PYTHON_TREE)
    missing = ways_in_without_journey(Meaning({}), python)
    assert [p["kind"] for p in missing] == ["console_script"]
    typescript = _facts(tmp_path / "ts", TYPESCRIPT_TREE)
    assert ways_in_without_journey(Meaning({}), typescript) == typescript["entry_points"]


def test_an_unknown_alias_is_not_a_pass(tmp_path: Path) -> None:
    facts = _facts(tmp_path, PYTHON_TREE)
    for point in facts["entry_points"]:
        del point["same_as"]
    missing = ways_in_without_journey(Meaning({}), facts)
    assert sorted(p["kind"] for p in missing) == ["console_script", "main_function", "main_module"]


def test_the_short_name_comes_from_neutral_fields(tmp_path: Path) -> None:
    python = _by_kind(_facts(tmp_path / "py", PYTHON_TREE))
    assert short_entry(python["main_function"]) == "main() in shop.cli"
    assert short_entry(python["console_script"]) == "shop"
    assert short_entry(python["main_module"]) == "python -m shop"
    typescript = _facts(tmp_path / "ts", TYPESCRIPT_TREE)
    names = {p["kind"]: short_entry(p) for p in typescript["entry_points"]}
    assert names["console_script"] == "web"
    assert names["public_function"] == "start"
    # A task has the name of its target function. The module identifies it.
    task = {"kind": "task", "name": "send", "module": "shop.jobs", "target": "send"}
    assert short_entry(task) == "send() in shop.jobs"


SRC = Path(__file__).resolve().parent.parent / "src" / "systemap"
ADAPTERS = {"extract.py", "source_facts.py"}
ONE_ADAPTER_KINDS = {"main_function", "main_module"}


def test_no_shared_module_names_a_python_entry_point_kind() -> None:
    found = [
        f"{path.name}:{node.lineno}"
        for path in sorted(SRC.glob("*.py"))
        if path.name not in ADAPTERS and not path.name.startswith(("python_", "typescript"))
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Constant) and node.value in ONE_ADAPTER_KINDS
    ]
    assert found == []
