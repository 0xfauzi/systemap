"""Shared logic gives the same result for a Python repository and a TypeScript repository.

Each test reads one Python fixture and one TypeScript fixture through the language
adapters. Acceptance for the work item: each test below passes, and each test failed on
the base commit 376c84e (before the adapters wrote the neutral facts). The last test
finds zero language tests in the shared modules.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree

from systemap import (
    check,
    config,
    explain,
    extract,
    history,
    judgement,
    page_data,
    source_facts,
    suggest,
    typescript_calls,
)
from systemap import language as languages
from systemap.model import Component, Model, Region
from systemap.schematic import lives_in

PYTHON_TREE = {
    "systemap.toml": 'language = "python"\n',
    "pyproject.toml": (
        '[project]\nname = "shop"\nversion = "1"\n[project.scripts]\nshop = "shop.cli:main"\n'
    ),
    "src/shop/__init__.py": "",
    "src/shop/cli.py": "def main() -> None:\n    pass\n",
    "src/shop/orders/__init__.py": "",
    "src/shop/orders/store.py": (
        "import ai\n\n\nclass Ledger:\n    def record(self) -> None:\n        pass\n"
    ),
    "src/shop/orders/audit.py": "import shop.orders.store as st\n\nVALUE = st.Ledger\n",
}
TYPESCRIPT_TREE = {
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
    "package.json": '{"name":"@acme/web","bin":{"web":"src/cli.ts"}}',
    "tsconfig.json": '{"compilerOptions":{}}',
    "src/cli.ts": "export function main(): void {}\n",
    "src/index.ts": "// The package marker.\n",
    "src/users/index.ts": 'export { UserService } from "./user.service";\n',
    "src/users/user.ts": "export interface User { name: string }\n",
    "src/users/user.service.ts": (
        'import { generateText } from "ai";\n'
        "export class $Store { public $get(): void {} }\n"
        "export class UserService { public save(): void { generateText() } }\n"
    ),
}


def _facts(tmp_path: Path, tree: dict[str, str]) -> tuple[config.Config, dict[str, Any]]:
    write_tree(tmp_path, tree)
    cfg = config.load(tmp_path)
    return cfg, extract.build(cfg)


@pytest.fixture
def python_facts(tmp_path: Path) -> tuple[config.Config, dict[str, Any]]:
    return _facts(tmp_path / "py", PYTHON_TREE)


@pytest.fixture
def typescript_facts(tmp_path: Path) -> tuple[config.Config, dict[str, Any]]:
    return _facts(tmp_path / "ts", TYPESCRIPT_TREE)


def _model(*modules: str, interface: str = "", entry: str = "") -> Model:
    return Model(
        canvas=(600, 200),
        containers=(),
        regions=(Region("all", "ALL", (0, 0, 600, 200)),),
        components=(
            Component(
                "Keeper",
                "Keeps every record ever written.",
                interface=interface,
                implemented_by=modules,
                entry=entry,
                region="all",
                x=20,
                y=20,
            ),
        ),
        flows=(),
        flow_kinds=(),
    )


def test_page_data_names_each_entry_point_of_each_language(
    python_facts: tuple[config.Config, dict[str, Any]],
    typescript_facts: tuple[config.Config, dict[str, Any]],
) -> None:
    """Acceptance (census item 1): the page gives a non-empty label for 100% of the entry
    points: `shop (console script)` for Python and `web (console script)` for TypeScript."""
    for (_cfg, facts), module, label in (
        (python_facts, "shop.cli", "shop (console script)"),
        (typescript_facts, "web.cli", "web (console script)"),
    ):
        points = page_data.sources(_model(module), facts)["Keeper"]["points"]
        assert label in points
        assert all(points)


def test_lives_in_reads_the_file_facts(
    python_facts: tuple[config.Config, dict[str, Any]],
    typescript_facts: tuple[config.Config, dict[str, Any]],
) -> None:
    """Acceptance (census item 2): the card gives the real source path, with the package
    root and the real suffix, for 2 of 2 languages."""
    _cfg, py = python_facts
    assert lives_in(["shop.orders.store"], py["components"]) == "src/shop/orders/store.py"
    _cfg, ts = typescript_facts
    components = ts["components"]
    assert lives_in(["web.users.user.service"], components) == "src/users/user.service.ts"
    assert lives_in(["web.users.*"], components) == "src/users/"


def test_the_package_fact_ignores_a_dot_in_a_file_name(
    python_facts: tuple[config.Config, dict[str, Any]],
    typescript_facts: tuple[config.Config, dict[str, Any]],
) -> None:
    """Acceptance (census item 5): the `package` fact is the folder package. A dot in a
    TypeScript file name adds no package. The mis-fold line and the suggested group name
    that package, and the Python results do not change."""
    _cfg, py = python_facts
    packages = {m: r["package"] for m, r in py["components"].items()}
    assert packages["shop.orders.store"] == "shop.orders"
    assert packages["shop.orders"] == "shop"
    assert packages["shop"] == "shop"
    _cfg, ts = typescript_facts
    assert ts["components"]["web.users.user.service"]["package"] == "web.users"
    assert ts["components"]["web.users.index"]["package"] == "web.users"
    for facts, modules, package in (
        (py, ("shop.orders.store", "shop.cli"), "shop.orders"),
        (ts, ("web.users.user.service", "web.cli"), "web.users"),
    ):
        lines = judgement.mis_folds(_model(*modules), _meaning(), facts)
        line = next(line for line in lines if f"module claim {modules[0]} " in line)
        assert line.endswith(f"no other component module in {package})")
    groups, _alone = suggest.proposals(ts)
    users = next(g for g in groups if g.package == "web.users")
    assert set(users.modules) == {"web.users.index", "web.users.user", "web.users.user.service"}


def _meaning() -> Any:
    from systemap.model import Meaning

    return Meaning(plain={})


def test_the_unknown_surface_text_names_no_language(
    tmp_path: Path,
) -> None:
    """Acceptance (census item 6): an unknown-surface line from Python source and from
    TypeScript source gets a fix line and an explanation without the word TypeScript."""
    py_tree = {**PYTHON_TREE, "src/shop/broken.py": "def broken(:\n"}
    ts_tree = {**TYPESCRIPT_TREE, "src/broken.ts": "export function (: {\n"}
    for name, tree in (("py", py_tree), ("ts", ts_tree)):
        _cfg, facts = _facts(tmp_path / name, tree)
        lines = source_facts.unknown_fact_lines(facts)
        assert lines, name
        report = check._unknown_surface_report(lines)
        assert "TypeScript" not in report[-1]
    lesson = explain.lesson("unknown surface")
    assert lesson is not None and "TypeScript" not in lesson.means


def test_the_history_cache_key_holds_the_parser_of_the_language(
    python_facts: tuple[config.Config, dict[str, Any]],
    typescript_facts: tuple[config.Config, dict[str, Any]],
) -> None:
    """Acceptance (census item 7): a different parser version gives a different cache
    scope for 2 of 2 languages. The TypeScript key holds the tree-sitter versions."""
    for cfg, _facts_of in (python_facts, typescript_facts):
        adapter = languages.repository(cfg.language)
        version = adapter.parser_version()
        assert history.cache_scope(cfg, version) != history.cache_scope(cfg, version + "x")
    assert "tree-sitter-typescript" in languages.repository("typescript").parser_version()


def test_an_interface_name_can_contain_a_dollar_sign(
    python_facts: tuple[config.Config, dict[str, Any]],
    typescript_facts: tuple[config.Config, dict[str, Any]],
) -> None:
    """Acceptance (census item 8): `$Store.$get` in TypeScript and `Ledger.record` in
    Python give no interface problem."""
    _cfg, py = python_facts
    card = _model("shop.orders.store", interface="Ledger.record").components[0]
    assert check.interface_problem(card, py["components"]) == ""
    _cfg, ts = typescript_facts
    card = _model("web.users.user.service", interface="$Store.$get").components[0]
    assert check.interface_problem(card, ts["components"]) == ""


def test_the_adapters_write_the_empty_marker_fact(
    python_facts: tuple[config.Config, dict[str, Any]],
    typescript_facts: tuple[config.Config, dict[str, Any]],
) -> None:
    """Acceptance (census item 9): a Python `__init__.py` file and a TypeScript `index.ts`
    file without code are empty markers. An index file with an export is not."""
    _cfg, py = python_facts
    assert source_facts.empty_markers(py) == ["shop", "shop.orders"]
    _cfg, ts = typescript_facts
    assert source_facts.empty_markers(ts) == ["web.index"]
    assert ts["components"]["web.users.index"]["empty_marker"] is False


def test_the_default_name_comes_from_the_package_metadata(
    python_facts: tuple[config.Config, dict[str, Any]],
    typescript_facts: tuple[config.Config, dict[str, Any]],
) -> None:
    """Acceptance (census item 10): without a name key, the map name is the package name
    of pyproject.toml or package.json."""
    assert python_facts[0].name == "shop"
    assert typescript_facts[0].name == "@acme/web"


def test_an_output_folder_is_a_package_only_for_its_adapter(tmp_path: Path) -> None:
    """Acceptance (census item 11): a `build` folder with `__init__.py` is a Python
    package, so its tests folder is found. The TypeScript adapter skips it."""
    write_tree(tmp_path, {"build/__init__.py": "", "build/tests/test_a.py": ""})
    python = languages.repository("python").package_dir
    typescript = languages.repository("typescript").package_dir
    assert config.discover_tests(tmp_path, python) == ["build/tests"]
    assert config.discover_tests(tmp_path, typescript) == []


def test_the_language_comes_from_the_source_when_the_key_is_absent(tmp_path: Path) -> None:
    """Acceptance (census item 12): without the language key, a Python tree gives python
    and a TypeScript tree gives typescript. Both trees together stop with a message that
    names the key. A tree without source stops when a command needs the adapter."""
    py_tree = {k: v for k, v in PYTHON_TREE.items() if k != "systemap.toml"}
    ts_tree = {k: v for k, v in TYPESCRIPT_TREE.items() if k != "systemap.toml"}
    write_tree(tmp_path / "py", py_tree)
    write_tree(tmp_path / "ts", ts_tree)
    assert config.load(tmp_path / "py").language == "python"
    assert config.load(tmp_path / "ts").language == "typescript"
    write_tree(tmp_path / "both", {**py_tree, **ts_tree})
    with pytest.raises(config.ConfigError, match="Set the language key"):
        config.load(tmp_path / "both")
    (tmp_path / "none").mkdir()
    empty = config.load(tmp_path / "none")
    assert empty.language == languages.UNKNOWN
    with pytest.raises(config.ConfigError, match="Set the language key"):
        extract.build(empty)


def test_each_adapter_has_its_own_model_sdk_names(
    python_facts: tuple[config.Config, dict[str, Any]],
    typescript_facts: tuple[config.Config, dict[str, Any]],
) -> None:
    """Acceptance (census item 13): the npm package `ai` is a model SDK for TypeScript
    only. A Python import `ai` gives 0 model sdk lines, a TypeScript import gives 1."""
    found = {}
    for cfg, facts in (python_facts, typescript_facts):
        module = "shop.orders.store" if cfg.language == "python" else "web.users.user.service"
        sdks = judgement.sdk_list(cfg.model_sdks, languages.repository(cfg.language).model_sdks)
        found[cfg.language] = judgement.model_sdk_imports(_model(module), facts, sdks)
    assert found["python"] == []
    assert len(found["typescript"]) == 1


def test_each_adapter_reads_the_local_names_of_an_import(
    python_facts: tuple[config.Config, dict[str, Any]],
) -> None:
    """Acceptance (census item 15): the call-site reader of each adapter gives the local
    name of a whole-module import and its use: `st` for Python and `svc` for TypeScript."""
    _cfg, facts = python_facts
    sites = {s["local"]: s for s in facts["components"]["shop.orders.audit"]["call_sites"]}
    assert (sites["st"]["target"], sites["st"]["name"]) == ("shop.orders.store", "*")
    assert sites["st"]["uses"] == [[3, 0, "Ledger"]]
    text = 'import * as svc from "./user.service";\nsvc.save();\n'
    target = "web.users.user.service"
    found = typescript_calls.call_sites(
        text, "src/users/view.ts", "web.users.view", {"./user.service": target}.get
    )
    assert found is not None
    assert [(s["local"], s["target"], s["name"], s["uses"]) for s in found] == [
        ("svc", target, "*", [[2, 0, "save"]])
    ]


# ---- the final acceptance test: no language test in a shared module --------------------

SRC = Path(__file__).resolve().parent.parent / "src" / "systemap"
# The language adapters. Language-specific work belongs here.
ADAPTERS = {
    "extract.py": "The Python adapter: Python syntax and the shared build steps.",
    "python_repo.py": "The Python repository adapter.",
    "python_entry.py": "The Python entry point reader.",
    "python_imports.py": "The Python import resolver.",
    "python_calls.py": "The Python call-site reader.",
    "python_syntax.py": "The Python package marker and decorator rules.",
    "python_tests.py": "The Python test reader.",
    "python_exports.py": "The Python rules for a star re-export.",
    "typescript.py": "The TypeScript adapter.",
    "typescript_repo.py": "The TypeScript repository adapter.",
    "typescript_config.py": "The tsconfig reader of the TypeScript adapter.",
    "typescript_config_files.py": "The TypeScript configuration files for the live watcher.",
    "typescript_entry.py": "The TypeScript entry point reader.",
    "typescript_imports.py": "The TypeScript import reader.",
    "typescript_calls.py": "The TypeScript call-site reader.",
    "typescript_projects.py": "The TypeScript project reader.",
    "typescript_surface.py": "The TypeScript public surface reader.",
    "typescript_syntax.py": "The TypeScript parser.",
    "typescript_tests.py": "The TypeScript test reader.",
}
# The model-file readers. A model file is Python for each source language, so these
# modules parse Python text. They do not read repository source.
MODEL_READERS = {
    "place_source.py": "It edits the positions in the Python model file.",
    "journeys.py": "It writes sequences into the Python model file.",
    "model_load.py": "It reads the Python model file without running it.",
    "model_convert.py": "It converts the Python model file to a new schema.",
    "model_edit.py": "It edits the Python model file in place.",
    "review.py": "It records source reviews in the Python model file.",
}
SUFFIXES = {".py", ".ts", ".tsx", ".mts", ".cts", "*.py", "*.ts", "__init__.py", "__init__"}
LANGUAGE_NAMES = {"python", "typescript"}


def _problems(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[str] = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Import | ast.ImportFrom) and _imports_ast(node):
            out.append(f"{path.name}:{line}: import ast")
        elif isinstance(node, ast.Compare) and _language_compare(node):
            out.append(f"{path.name}:{line}: language ==")
        elif isinstance(node, ast.Constant) and node.value in SUFFIXES | LANGUAGE_NAMES:
            out.append(f"{path.name}:{line}: {node.value!r}")
    return out


def _imports_ast(node: ast.Import | ast.ImportFrom) -> bool:
    if isinstance(node, ast.ImportFrom):
        return node.module == "ast"
    return any(alias.name == "ast" for alias in node.names)


def _language_compare(node: ast.Compare) -> bool:
    parts = [node.left, *node.comparators]
    named = any(
        (isinstance(p, ast.Name) and p.id == "language")
        or (isinstance(p, ast.Attribute) and p.attr == "language")
        for p in parts
    )
    return named and any(isinstance(op, ast.Eq | ast.NotEq) for op in node.ops)


def test_no_shared_module_tests_a_language() -> None:
    """Acceptance (work item step 8): 0 language tests in the shared modules. A language
    test is a `language ==` comparison, a source suffix or `__init__` literal, a language
    name literal, or an `ast` import. The registry in `language.py` maps each name of
    the language key to its adapter, so it holds the names."""
    allowed = set(ADAPTERS) | set(MODEL_READERS)
    problems = [
        problem
        for path in sorted(SRC.glob("*.py"))
        if path.name not in allowed
        for problem in _problems(path)
        if not (path.name == "language.py" and problem.endswith(("'python'", "'typescript'")))
    ]
    assert problems == []
    assert set(ADAPTERS) | set(MODEL_READERS) <= {p.name for p in SRC.glob("*.py")}
