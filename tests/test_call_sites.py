"""The call-site fact has the same meaning for a Python module and a TypeScript module.

Each adapter writes `call_sites` for each module. The flow context of `jev flow` reads
only this fact and the source lines that it names.

Acceptance (work item call-site-facts, written before the change):

- For the Python fixture and the TypeScript fixture, the call-site fact of the writer
  module lists the instance calls `ledger.record(parts)` of the imported class `Ledger`,
  and the plain calls `total(parts)` of the imported function `total`. Each use has the
  correct source line and the correct line of the function or method that contains it.
- The flow context of the two fixtures contains these lines.
- If the fact is not known, the flow gets no question, and the plan records the flow
  as not known. It is not an empty context.
- All existing tests pass.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree

from systemap import audit, config, extract, nest
from systemap.audit_code import code_between
from systemap.language import repository
from systemap.model import Component, Flow, Meaning, Model

PYTHON = {
    "systemap.toml": 'language = "python"\n[package_roots]\n"pkg" = "pkg"\n',
    "pkg/__init__.py": "",
    "pkg/ledger.py": (
        '"""The ledger keeps the parts."""\n'
        "\n"
        "\n"
        "class Ledger:\n"
        "    def record(self, parts: list[str]) -> None:\n"
        "        pass\n"
        "\n"
        "\n"
        "def total(parts: list[str]) -> int:\n"
        "    return len(parts)\n"
    ),
    "pkg/writer.py": (
        "from pkg.ledger import Ledger, total\n"  # 1
        "\n"  # 2
        "\n"  # 3
        "class Writer:\n"  # 4
        "    def __init__(self) -> None:\n"  # 5
        "        self.ledger = Ledger()\n"  # 6
        "\n"  # 7
        "    def write(self, parts: list[str]) -> int:\n"  # 8
        "        self.ledger.record(parts)\n"  # 9
        "        return total(parts)\n"  # 10
        "\n"  # 11
        "\n"  # 12
        "def keep(parts: list[str]) -> None:\n"  # 13
        "    ledger = Ledger()\n"  # 14
        "    ledger.record(parts)\n"  # 15
    ),
}
TYPESCRIPT = {
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "pkg"\n',
    "package.json": '{"name":"pkg"}',
    "tsconfig.json": '{"compilerOptions":{}}',
    "src/ledger.ts": (
        "/** The ledger keeps the parts. */\n"
        "export class Ledger {\n"
        "  record(parts: string[]): void {}\n"
        "}\n"
        "\n"
        "export function total(parts: string[]): number {\n"
        "  return parts.length;\n"
        "}\n"
    ),
    "src/writer.ts": (
        'import { Ledger, total } from "./ledger";\n'  # 1
        "\n"  # 2
        "\n"  # 3
        "export class Writer {\n"  # 4
        "  private ledger = new Ledger();\n"  # 5
        "\n"  # 6
        "\n"  # 7
        "  write(parts: string[]): number {\n"  # 8
        "    this.ledger.record(parts);\n"  # 9
        "    return total(parts);\n"  # 10
        "  }\n"  # 11
        "}\n"  # 12
        "export function keep(parts: string[]): void {\n"  # 13
        "  const ledger = new Ledger();\n"  # 14
        "  ledger.record(parts);\n"  # 15
        "}\n"
    ),
}
LANGUAGES = {"python": (PYTHON, "self"), "typescript": (TYPESCRIPT, "this")}
# The instance binding: in `__init__` for Python (line 6, function line 5), and in a
# class field for TypeScript (line 5, outside a function).
FIELD = {"python": (6, 5), "typescript": (5, 0)}


def _facts(tmp_path: Path, files: dict[str, str]) -> tuple[config.Config, dict[str, Any]]:
    write_tree(tmp_path, files)
    cfg = config.load(tmp_path)
    return cfg, extract.build(cfg)


def _site(sites: list[dict[str, Any]], local: str) -> dict[str, Any]:
    return next(s for s in sites if s["local"] == local)


@pytest.mark.parametrize("language", sorted(LANGUAGES))
def test_the_fact_lists_the_instance_calls_and_the_function_calls(
    tmp_path: Path, language: str
) -> None:
    """Acceptance: the two adapters write the same call sites for the writer module."""
    files, receiver = LANGUAGES[language]
    _cfg, facts = _facts(tmp_path, files)
    sites = facts["components"]["pkg.writer"]["call_sites"]
    assert {s["target"] for s in sites} == {"pkg.ledger"}
    ledger_class = _site(sites, "Ledger")
    assert (ledger_class["name"], ledger_class["bound"], ledger_class["line"]) == (
        "Ledger",
        "import",
        1,
    )
    field_line, field_function = FIELD[language]
    assert ledger_class["uses"] == [[field_line, field_function, ""], [14, 13, ""]]
    function = _site(sites, "total")
    assert (function["name"], function["bound"]) == ("total", "import")
    assert function["uses"] == [[10, 8, ""]]
    field = _site(sites, f"{receiver}.ledger")
    assert (field["name"], field["bound"], field["line"]) == ("Ledger", "value", field_line)
    assert field["uses"] == [[9, 8, "record"]]
    local = _site(sites, "ledger")
    assert (local["name"], local["bound"], local["line"]) == ("Ledger", "value", 14)
    assert local["uses"] == [[15, 13, "record"]]


def _flow_model() -> tuple[Model, Meaning]:
    model = Model(
        canvas=(400, 200),
        containers=(),
        regions=(),
        components=(
            Component(id="Ledger", does="Keeps.", implemented_by=("pkg.ledger",), x=40, y=40),
            Component(id="Writer", does="Writes.", implemented_by=("pkg.writer",), x=240, y=40),
        ),
        flows=(Flow("Writer", "Ledger", "parts", "data"),),
        flow_kinds=(),
    )
    return model, Meaning(plain={}, relations={("Writer", "Ledger"): "The writer records parts."})


@pytest.mark.parametrize("language", sorted(LANGUAGES))
def test_the_flow_context_contains_the_call_lines(tmp_path: Path, language: str) -> None:
    """Acceptance: the flow context gives the call lines, the function lines, and the
    target signatures."""
    files, receiver = LANGUAGES[language]
    cfg, facts = _facts(tmp_path, files)
    model, _meaning = _flow_model()
    by = audit.modules_by_card(model, facts)
    code = code_between(cfg.root, facts, by, ("Writer", "Ledger"), repository(cfg.language))
    assert code is not None
    text = "\n".join(code)
    for line, words in (
        (9, f"{receiver}.ledger.record(parts)"),
        (10, "total(parts)"),
        (15, "ledger.record(parts)"),
        (8, "write("),
        (13, "keep(parts"),
    ):
        assert f"pkg.writer:{line}: " in text and words in text, (line, code)
    assert any(x.startswith("pkg.ledger defines: ") and "record" in x for x in code), code
    assert any(x.startswith("pkg.ledger defines: ") and "total" in x for x in code), code
    assert "pkg.ledger docstring: The ledger keeps the parts" in text


@pytest.mark.parametrize("language", sorted(LANGUAGES))
def test_a_flow_without_the_fact_is_not_known(tmp_path: Path, language: str) -> None:
    """Acceptance: a module without the fact (older facts, or source that did not parse)
    gives no context. The plan records the flow as not known."""
    files, _receiver = LANGUAGES[language]
    cfg, facts = _facts(tmp_path, files)
    facts["components"]["pkg.writer"]["call_sites"] = None
    model, meaning = _flow_model()
    by = audit.modules_by_card(model, facts)
    assert code_between(cfg.root, facts, by, ("Writer", "Ledger"), repository(cfg.language)) is None
    tree = nest.Tree(
        (nest.Map(id="", path=cfg.model_path, rel="", model=model, meaning=meaning, theme={}),)
    )
    plan = audit.make_plan(tree, facts, cfg, ("decision flow",))
    assert plan.questions == []
    assert plan.unasked == []
    assert plan.unknown == ["Writer -> Ledger (parts)"]


def test_source_that_does_not_parse_has_no_known_call_sites(tmp_path: Path) -> None:
    """Acceptance: a module that did not parse has the value `null`, not an empty list."""
    files = {**PYTHON, "pkg/writer.py": PYTHON["pkg/writer.py"] + "def broken(:\n"}
    _cfg, facts = _facts(tmp_path, files)
    assert facts["components"]["pkg.writer"]["call_sites"] is None
    assert facts["components"]["pkg.ledger"]["call_sites"] == []
