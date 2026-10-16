"""Import rules: checks that a program makes over the import facts.

Each rule gets one result: `pass`, `fail`, or `unknown`.

Acceptance:
- A Python fixture and a TypeScript fixture, each with three components (Api, Core, Store):
  a forbidden import gives `fail` and lists the import (source module, target module).
  A rule with no import against it gives `pass`.
  A module with a syntax error gives `unknown`. A module with an unresolved import gives `unknown`.
- A cycle between two components gives `fail` for `forbid_cycle`. No cycle gives `pass`.
- `allow_imports` gives `fail` for an import of a component that the rule does not name.
  It gives `pass` when the only other imports are external packages.
- A rule with an unknown component makes `systemap check` exit 1. The message gives the
  rule id and the component id.
- `systemap check` exits 1 for a `fail` and prints the import. It prints an `unknown` result
  as a warning and exits 0. It exits 1 for `unknown` under `[rules] unknown = "fail"`.
- `systemap rules --json` writes one JSON object with the result of each rule.
- All tests that were in the suite before this change pass.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import STARTER_MODULES, init_two_cards, write_tree
from test_check_rules import run

from systemap import config, explain, extract, import_rules, model_load
from systemap.import_rules import FAIL, NO_COMPONENT, NOT_PARSED, PASS, UNKNOWN, UNRESOLVED
from systemap.model import Component, ImportRule, Invariant, Model, problems
from systemap.model import Meaning as _Meaning

# ---- the two fixtures: the same three components in each language -------------------

PYTHON = {
    "pkg/__init__.py": "",
    "pkg/api.py": "import requests\n\nfrom pkg.core import run\n\n\ndef serve():\n    return run()\n",
    "pkg/core.py": "from pkg.store import save\n\n\ndef run():\n    return save()\n",
    "pkg/store.py": "def save():\n    return 1\n",
}
PYTHON_CYCLE = {"pkg/store.py": "from pkg import core\n\n\ndef save():\n    return core\n"}
PYTHON_BROKEN = {"pkg/store.py": "def save(:\n    return 1\n"}
PYTHON_UNRESOLVED = {
    "pkg/store.py": "from pkg.missing import gone\n\n\ndef save():\n    return gone\n"
}

TYPESCRIPT = {
    "tsconfig.json": '{"compilerOptions":{}}',
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
    "src/api.ts": (
        'import { z } from "zod";\nimport { run } from "./core";\n'
        "export function serve(): unknown {\n  return [z, run()];\n}\n"
    ),
    "src/core.ts": (
        'import { save } from "./store";\nexport function run(): number {\n  return save();\n}\n'
    ),
    "src/store.ts": "export function save(): number {\n  return 1;\n}\n",
}
TYPESCRIPT_CYCLE = {
    "src/store.ts": (
        'import { run } from "./core";\nexport function save(): number {\n  return 1;\n}\n'
        "export const again = run;\n"
    )
}
TYPESCRIPT_BROKEN = {"src/store.ts": "export function save( {\n"}
TYPESCRIPT_UNRESOLVED = {
    "src/store.ts": (
        'import { gone } from "./missing";\nexport function save(): number {\n  return gone;\n}\n'
    )
}

LANGUAGES = {
    "python": ("pkg", PYTHON, PYTHON_CYCLE, PYTHON_BROKEN, PYTHON_UNRESOLVED),
    "typescript": ("web", TYPESCRIPT, TYPESCRIPT_CYCLE, TYPESCRIPT_BROKEN, TYPESCRIPT_UNRESOLVED),
}


def _facts(root: Path, *trees: dict[str, str]) -> dict[str, Any]:
    for tree in trees:
        write_tree(root, tree)
    return extract.build(config.load(root))


def _model(prefix: str, *rules: ImportRule) -> Model:
    cards = tuple(
        Component(name.title(), f"The {name} part.", implemented_by=(f"{prefix}.{name}",))
        for name in ("api", "core", "store")
    )
    return Model((800, 600), (), (), cards, (), (), import_rules=rules)


def _results(model: Model, facts: dict[str, Any]) -> dict[str, import_rules.Outcome]:
    return {o.rule.id: o for o in import_rules.evaluate(model, facts)}


@pytest.fixture(params=sorted(LANGUAGES))
def language(request: pytest.FixtureRequest) -> str:
    return str(request.param)


# ---- fail, pass, and unknown for each language ---------------------------------------


def test_a_forbidden_import_fails_and_no_import_passes(tmp_path: Path, language: str) -> None:
    prefix, tree, *_ = LANGUAGES[language]
    facts = _facts(tmp_path, tree)
    model = _model(
        prefix,
        ImportRule("core-no-store", "forbid_import", ("Core",), ("Store",)),
        ImportRule("api-no-store", "forbid_import", ("Api",), ("Store",)),
    )
    found = _results(model, facts)
    assert found["core-no-store"].result == FAIL
    assert found["core-no-store"].imports == ((f"{prefix}.core", f"{prefix}.store"),)
    assert found["api-no-store"].result == PASS
    assert found["api-no-store"].imports == () and found["api-no-store"].gaps == ()


def test_a_module_that_does_not_parse_gives_unknown(tmp_path: Path, language: str) -> None:
    prefix, tree, _cycle, broken, _unresolved = LANGUAGES[language]
    facts = _facts(tmp_path, tree, broken)
    model = _model(prefix, ImportRule("store-alone", "forbid_import", ("Store",), ("Api",)))
    outcome = _results(model, facts)["store-alone"]
    assert outcome.result == UNKNOWN
    assert [(g.module, g.cause) for g in outcome.gaps] == [(f"{prefix}.store", NOT_PARSED)]
    assert "could not parse" in outcome.gaps[0].detail


def test_an_unresolved_import_gives_unknown(tmp_path: Path, language: str) -> None:
    prefix, tree, _cycle, _broken, unresolved = LANGUAGES[language]
    facts = _facts(tmp_path, tree, unresolved)
    model = _model(prefix, ImportRule("store-alone", "forbid_import", ("Store",), ("Api",)))
    outcome = _results(model, facts)["store-alone"]
    assert outcome.result == UNKNOWN
    assert [(g.module, g.cause) for g in outcome.gaps] == [(f"{prefix}.store", UNRESOLVED)]
    assert "missing" in outcome.gaps[0].detail


def test_a_cycle_between_two_components_fails(tmp_path: Path, language: str) -> None:
    prefix, tree, cycle, *_ = LANGUAGES[language]
    rules = (
        ImportRule("no-cycle", "forbid_cycle"),
        ImportRule("api-core", "forbid_cycle", ("Api", "Core")),
    )
    before = _results(_model(prefix, *rules), _facts(tmp_path, tree))
    assert before["no-cycle"].result == PASS
    after = _results(_model(prefix, *rules), _facts(tmp_path, cycle))
    assert after["no-cycle"].result == FAIL
    assert after["no-cycle"].imports == (
        (f"{prefix}.core", f"{prefix}.store"),
        (f"{prefix}.store", f"{prefix}.core"),
    )
    # The cycle is not between Api and Core.
    assert after["api-core"].result == PASS


def test_allow_imports_fails_for_another_component_and_passes_for_packages(
    tmp_path: Path, language: str
) -> None:
    prefix, tree, *_ = LANGUAGES[language]
    facts = _facts(tmp_path, tree)
    model = _model(
        prefix,
        ImportRule("api-uses-core", "allow_imports", ("Api",), ("Core",)),
        ImportRule("api-alone", "allow_imports", ("Api",)),
    )
    found = _results(model, facts)
    # Api imports an external package and Core. External packages are not in the rule.
    assert found["api-uses-core"].result == PASS
    assert found["api-alone"].result == FAIL
    assert found["api-alone"].imports == ((f"{prefix}.api", f"{prefix}.core"),)


def test_allow_imports_is_unknown_for_a_module_with_no_component(tmp_path: Path) -> None:
    facts = _facts(tmp_path, PYTHON)
    cards = (
        Component("Api", "The api part.", implemented_by=("pkg.api",)),
        Component("Store", "The store part.", implemented_by=("pkg.store",)),
    )
    rule = ImportRule("api-alone", "allow_imports", ("Api",))
    model = Model((800, 600), (), (), cards, (), (), import_rules=(rule,))
    outcome = _results(model, facts)["api-alone"]
    assert outcome.result == UNKNOWN
    assert [(g.module, g.cause) for g in outcome.gaps] == [("pkg.api", NO_COMPONENT)]


def test_facts_without_modules_give_unknown() -> None:
    model = _model("pkg", ImportRule("core-no-store", "forbid_import", ("Core",), ("Store",)))
    assert _results(model, {})["core-no-store"].result == UNKNOWN


# ---- the model check refuses incorrect rules -----------------------------------------


def test_the_model_check_refuses_incorrect_rules() -> None:
    model = _model(
        "pkg",
        ImportRule("a", "forbid_import", ("Core",), ("Cache",)),
        ImportRule("a", "forbid_import", ("Core",), ("Store",)),
        ImportRule("b", "forbid_imports", ("Core",), ("Store",)),
        ImportRule("c", "forbid_import", ("Core",)),
        ImportRule("d", "forbid_cycle", ("Core",), ("Store",)),
        ImportRule("e", "allow_imports", ("Core",), ("Core",)),
        ImportRule("f", "allow_imports", ("Core",), invariant=4),
    )
    model = Model(
        model.canvas,
        (),
        (),
        model.components,
        (),
        (),
        (Invariant(1, "A rule."),),
        model.import_rules,
    )
    found = [p for p in problems(model, _Meaning({})) if p.startswith("import rule:")]
    assert found == [
        "import rule: a has unknown component Cache in dst",
        "import rule: a is the id of two rules. Give each rule its own id",
        "import rule: b has unknown kind forbid_imports. Use forbid_import, allow_imports, "
        "forbid_cycle",
        "import rule: c has no dst component. A rule of kind forbid_import must have one",
        "import rule: d has a dst. A rule of kind forbid_cycle uses only src",
        "import rule: e has component Core in src and in dst",
        "import rule: f has unknown invariant 4",
    ]
    assert import_rules.evaluate(model, {"components": {"pkg.core": {}}}) == []


def test_the_model_reader_reads_an_import_rule(tmp_path: Path) -> None:
    path = tmp_path / "model.py"
    path.write_text(
        "from systemap import ImportRule\n"
        'RULES = (ImportRule("core-no-store", "forbid_import", ("Core",), dst=("Store",), '
        'reason="Core keeps no state.", invariant=1),)\n',
        encoding="utf-8",
    )
    values = model_load.read(path, "model.py")
    assert values["RULES"] == (
        ImportRule(
            "core-no-store", "forbid_import", ("Core",), ("Store",), "Core keeps no state.", 1
        ),
    )


def test_each_result_kind_has_a_lesson() -> None:
    for kind in ("rule fail", "rule unknown"):
        found = explain.lesson(kind)
        assert found is not None and found.means and found.why and found.do


# ---- systemap check and systemap rules -----------------------------------------------

# The two-card map: Writer (pkg.writer) imports Reader (pkg.reader).
FORBID = 'ImportRule("writer-alone", "forbid_import", ("Writer",), ("Reader",))'
NO_CYCLE = 'ImportRule("no-cycle", "forbid_cycle")'


def current(root: Path) -> None:
    """Write the two-card map with its import, and make it current."""
    write_tree(root, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(root, "--no-ci")
    assert run("--root", str(root), "refresh") == 0
    assert run("--root", str(root), "check") == 0


def _with_rules(root: Path, *rules: str) -> None:
    """Write the import rules in the contract file of the two-card map."""
    path = root / "map/contract.py"
    old = "IMPORT_RULES: tuple[ImportRule, ...] = ()"
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, f"IMPORT_RULES = ({', '.join(rules)},)"), encoding="utf-8")


def test_check_fails_for_a_rule_with_an_unknown_component(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current(tmp_path)
    capsys.readouterr()
    _with_rules(tmp_path, 'ImportRule("writer-alone", "forbid_import", ("Writer",), ("Cache",))')
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "import rule fields: 1 problem" in out
    assert "\n  writer-alone has unknown component Cache in dst\n" in out


def test_check_fails_for_a_forbidden_import(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current(tmp_path)
    capsys.readouterr()
    _with_rules(tmp_path, FORBID, NO_CYCLE)
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "import rules: 2 rules, 1 fail, 0 unknown, 1 pass" in out
    assert "rule fail: 1 rule" in out
    assert "  writer-alone (forbid_import): pkg.writer imports pkg.reader" in out
    assert explain.LESSONS["rule fail"].why in out
    assert run("--root", str(tmp_path), "check", "--brief") == 1
    assert explain.LESSONS["rule fail"].why not in capsys.readouterr().out


def test_check_warns_for_unknown_unless_the_configuration_makes_it_fail(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current(tmp_path)
    _with_rules(tmp_path, NO_CYCLE)
    # The reader has an unresolved import: the facts do not give all its imports.
    write_tree(
        tmp_path, {"pkg/reader.py": "from pkg.gone import x\n\n\ndef read(source):\n    return x\n"}
    )
    assert run("--root", str(tmp_path), "refresh") == 0
    capsys.readouterr()
    assert run("--root", str(tmp_path), "check") == 0
    out = capsys.readouterr().out
    assert 'rule unknown: 1 rule. This result is a warning with [rules] unknown = "warn".' in out
    assert "  no-cycle (forbid_cycle): pkg.reader: The module has unresolved imports: " in out
    toml = tmp_path / "systemap.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8").replace(
            "[package_roots]", '[rules]\nunknown = "fail"\n\n[package_roots]', 1
        ),
        encoding="utf-8",
    )
    assert run("--root", str(tmp_path), "check") == 1
    assert "This result causes exit 1" in capsys.readouterr().out


def test_rules_json_gives_each_result(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    current(tmp_path)
    _with_rules(tmp_path, FORBID, NO_CYCLE)
    capsys.readouterr()
    assert run("--root", str(tmp_path), "rules", "--json") == 1
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is False and data["unknown_policy"] == "warn" and data["problems"] == []
    assert data["counts"] == {"fail": 1, "unknown": 0, "pass": 1}
    first, second = data["rules"]
    assert first["id"] == "writer-alone" and first["result"] == "fail"
    assert first["imports"] == [{"source": "pkg.writer", "target": "pkg.reader"}]
    assert second["id"] == "no-cycle" and second["result"] == "pass"
    assert run("--root", str(tmp_path), "rules") == 1
    assert "writer-alone (forbid_import): pkg.writer imports pkg.reader" in capsys.readouterr().out


def test_rules_without_rules_passes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    current(tmp_path)
    capsys.readouterr()
    assert run("--root", str(tmp_path), "rules") == 0
    assert "import rules: The model has no import rules." in capsys.readouterr().out


def test_an_unknown_rules_key_is_a_configuration_error(tmp_path: Path) -> None:
    write_tree(tmp_path, {"systemap.toml": '[rules]\nunknown = "stop"\n'})
    with pytest.raises(config.ConfigError, match='rules.unknown must be "warn" or "fail"'):
        config.load(tmp_path)
