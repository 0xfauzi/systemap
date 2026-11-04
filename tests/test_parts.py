"""The part plan, the stubs, and the result files of `systemap parts`.

Acceptance values:

1. `systemap parts` writes `map/parts/plan.json` with the fields of the design for each
   nested part of the top map: the files, the modules, the groups, the actors, the
   boundary flows and imports, the import rules, the entry points, the state, and
   `level_2`. `order` puts the largest part first.
2. Each entry point goes to the deepest map that claims its module.
3. `level_2` is true only for a part with more modules than `LEVEL_2_ABOVE`.
4. `--map ID` gives the record of the part from the plan of its parent map, and writes
   the plan of the nested parts of the map ID.
5. The stub has one component for each group, `<Card>Other` for the modules alone in
   their package, the symbol claims of the card unchanged, the actors, and positions.
   After `map=`, `refresh` and `check` exit 0.
6. `--stub` refuses a file that exists, a group ID that is the same as an actor ID, and
   a level-2 stub that needs an actor that the level-1 map does not have.
7. The plan refuses the stems `model`, `contract`, `plan`, `*_contract`, and `*_plan`, a
   stem that is the same as a different stem in a different case, and a file prefix
   that is the start of a different stem.
8. A different facts file or a different contract makes the plan stale. Then
   `parts --map ID` stops with "The plan is stale. Do systemap parts again."
9. `check --map ID` warns about a stale plan, with the same exit code. If no plan
   exists, `check --map ID` says nothing about a plan.
10. `suggest` and `parts --stub` give the same file name.
11. The result file examination refuses an answer form other than `item` and `items`,
    a digest that is not the digest of the plan, and a file outside the write set.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest
import three_levels
from conftest import write_tree

from systemap import (
    config,
    model_load,
    nest,
    parts,
    parts_plan,
    parts_result,
    parts_stub,
    suggest,
)
from systemap.cli import main

STALE = "The plan is stale. Do systemap parts again."


def run(root: Path, *argv: str) -> int:
    return main(["--root", str(root), *argv])


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("parts")
    write_tree(root, three_levels.files())
    assert run(root, "place") == 0
    assert run(root, "extract") == 0
    assert run(root, "refresh", "--quiet") == 0
    return root


@pytest.fixture
def tree_root(built: Path, tmp_path: Path) -> Path:
    root = tmp_path / "copy"
    shutil.copytree(built, root)
    return root


def _plan(root: Path, capsys: pytest.CaptureFixture[str], *argv: str) -> dict[str, Any]:
    capsys.readouterr()
    assert run(root, "parts", *argv, "--json") == 0
    found: dict[str, Any] = json.loads(capsys.readouterr().out)
    return found


def test_the_plan_gives_the_facts_of_each_part(
    tree_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 1."""
    plan = _plan(tree_root, capsys)
    stored = json.loads((tree_root / "map/parts/plan.json").read_text(encoding="utf-8"))
    assert stored == plan
    assert plan["map"] == ""
    assert plan["order"] == ["P0", "P1"]
    assert plan["vocabulary"]["regions"] == ["work"]
    assert plan["vocabulary"]["flow_artifacts"] == ["value lookup"]
    assert "map/model.py" in plan["shared_files"] and "map/parts/plan.json" in plan["shared_files"]
    p0 = plan["parts"][0]
    assert {key: p0[key] for key in ("map", "card", "stem", "model_file", "contract_file")} == {
        "map": "P0",
        "card": "P0",
        "stem": "p0",
        "model_file": "map/p0.py",
        "contract_file": "map/p0_contract.py",
    }
    assert p0["file_prefix"] == "map/p0_" and p0["result_file"] == "map/parts/p0.json"
    assert p0["module_count"] == len(p0["modules"]) == 7
    assert p0["source_bytes"] > 0
    assert p0["actors"] == [{"id": "Base", "because": ["flow value lookup", "crossing import"]}]
    assert p0["boundary_flows"] == [{"src": "P0", "dst": "Base", "artifact": "value lookup"}]
    assert {"module": "pkg.p0.q0.r0", "imports": "pkg.base.util", "card": "Base"} in p0[
        "boundary_imports"
    ]
    assert p0["state"] == "mapped" and p0["level_2"] is False
    assert p0["import_rules"] == []


def test_each_entry_point_goes_to_the_deepest_map(tree_root: Path) -> None:
    """Acceptance 2."""
    cfg = config.load(tree_root)
    tree = nest.load(cfg)
    facts = json.loads(cfg.facts_path.read_text(encoding="utf-8"))
    point = {"kind": "function", "name": "x", "label": "x", "target": "", "same_as": ""}
    facts["entry_points"] = [
        {**point, "module": "pkg.p0.glue", "symbol": "start_0"},
        {**point, "module": "pkg.p0.q0.r0", "symbol": "run_0_0"},
        {**point, "module": "pkg.p0.q0.deep.d1", "symbol": "detail_0_0"},
    ]
    top = parts_plan.build(cfg, tree, tree.top, facts)["parts"][0]
    level_1 = parts_plan.build(cfg, tree, tree.get("P0"), facts)["parts"][0]
    level_2 = parts_plan.build(cfg, tree, tree.get("P0/Q0"), facts)["parts"][0]
    modules = [[json.loads(e)[1] for e in r["entry_points"]] for r in (top, level_1, level_2)]
    assert modules == [["pkg.p0.glue"], ["pkg.p0.q0.r0"], ["pkg.p0.q0.deep.d1"]]


def test_level_2_is_for_a_part_above_the_limit(
    tree_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 3."""
    assert parts_plan.LEVEL_2_ABOVE == 400
    monkeypatch.setattr(parts_plan, "LEVEL_2_ABOVE", 6)
    assert [r["level_2"] for r in _plan(tree_root, capsys)["parts"]] == [True, True]
    monkeypatch.setattr(parts_plan, "LEVEL_2_ABOVE", 7)
    assert [r["level_2"] for r in _plan(tree_root, capsys)["parts"]] == [False, False]


def test_the_map_option_gives_the_record_and_the_nested_plan(
    tree_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 4."""
    top = _plan(tree_root, capsys)
    found = _plan(tree_root, capsys, "--map", "P0")
    assert found["part"] == top["parts"][0]
    assert found["facts_digest"] == top["facts_digest"]
    assert found["contract_digest"] == top["contract_digest"]
    nested = found["nested_plan"]
    assert nested["map"] == "P0" and nested["order"] == ["P0/Q0", "P0/Q1"]
    assert (tree_root / "map/parts/p0_plan.json").is_file()
    q0 = nested["parts"][0]
    assert {a["id"] for a in q0["actors"]} == {"Base", "Glue"}
    assert q0["result_file"] == "map/parts/p0_q0.json"
    assert _plan(tree_root, capsys, "--map", "P0/Q0")["nested_plan"]["order"] == ["P0/Q0/Deep"]
    deep = _plan(tree_root, capsys, "--map", "P0/Q0/Deep")
    assert deep["nested_plan"] is None
    assert not (tree_root / "map/parts/p0_q0_deep_plan.json").exists()


GATE_CONFIG = """
name = "gate"
[package_roots]
"pkg" = "pkg"
"""
GATE_MODEL = """
from systemap import Component, Container, Flow, Meaning, Model, Region

CONTAINERS = (Container(id="system", label="SYSTEM", box=(0, 0, 0, 0), tone="server"),)
REGIONS = (Region(id="work", label="WORK", box=(0, 0, 0, 0), container="system"),)
COMPONENTS = (
    Component(id="App", does="Starts the work.", implemented_by=("pkg.app",), entry="start", region="work"),
    Component(id="Gate", does="Gives the values.", implemented_by=("pkg.gate.*", "pkg.gate.api:handler"), entry="handler", region="work"),
)
FLOWS = (Flow("App", "Gate", "request", "control"),)
MODEL = Model(canvas=(0, 0), containers=CONTAINERS, regions=REGIONS, components=COMPONENTS, flows=FLOWS, flow_kinds=())
MEANING = Meaning(
    plain={"App": "the app", "Gate": "the gate"},
    relations={("App", "Gate"): "The app sends the request to the gate."},
)
"""
GATE_SOURCE = {
    "pkg/__init__.py": "",
    "pkg/app.py": "from pkg.gate.api import handler\n\n\ndef start() -> str:\n    return handler()\n",
    "pkg/gate/__init__.py": "",
    "pkg/gate/api.py": "from pkg.gate.store.a import a\n\n\ndef handler() -> str:\n    return a()\n",
    "pkg/gate/store/__init__.py": "",
    "pkg/gate/store/a.py": "from pkg.gate.store.b import b\n\n\ndef a() -> str:\n    return b()\n",
    "pkg/gate/store/b.py": "def b() -> str:\n    return 'b'\n",
}


def _gate(root: Path, model: str = GATE_MODEL) -> Path:
    write_tree(root, {"systemap.toml": GATE_CONFIG, "map/model.py": model, **GATE_SOURCE})
    assert run(root, "place") == 0
    assert run(root, "extract") == 0
    return root


def _set_map(path: Path, card: str, name: str) -> None:
    text = path.read_text(encoding="utf-8")
    marker = f'id="{card}",'
    assert marker in text
    path.write_text(text.replace(marker, f'{marker} map="{name}",', 1), encoding="utf-8")


def test_the_stub_passes_check(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Acceptance 5."""
    root = _gate(tmp_path)
    capsys.readouterr()
    assert run(root, "parts", "--stub", "Gate") == 0
    assert 'Set map="gate.py" on Gate in map/model.py.' in capsys.readouterr().out
    cfg = config.load(root)
    names = model_load.read(root / "map/gate.py", "map/gate.py", root)
    model = names["MODEL"]
    by_id = {c.id: c for c in model.components}
    assert set(by_id) == {"App", "GateStore", "GateOther"}
    assert by_id["App"].kind == "actor"
    assert by_id["GateStore"].implemented_by == ("pkg.gate.store.a", "pkg.gate.store.b")
    assert by_id["GateOther"].implemented_by == ("pkg.gate.api", "pkg.gate.api:handler")
    assert by_id["GateOther"].entry == "handler"
    assert all(c.positioned for c in model.components)
    assert model.flows == ()
    _set_map(root / "map/model.py", "Gate", parts.file_name("Gate"))
    assert run(root, "refresh", "--quiet") == 0
    capsys.readouterr()
    assert run(root, "check") == 0
    assert nest.load(cfg).get("Gate").path == root / "map/gate.py"


def test_the_stub_refuses_a_file_that_exists_and_an_actor_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 6: a file that exists, and a group ID that is an actor ID."""
    root = _gate(tmp_path / "one")
    (root / "map/gate.py").write_text("# a file of the maintainer\n", encoding="utf-8")
    capsys.readouterr()
    assert run(root, "parts", "--stub", "Gate") == 2
    assert "map/gate.py exists" in capsys.readouterr().err
    assert (root / "map/gate.py").read_text(encoding="utf-8") == "# a file of the maintainer\n"
    other = _gate(tmp_path / "two", GATE_MODEL.replace('"App"', '"GateStore"'))
    capsys.readouterr()
    assert run(other, "parts", "--stub", "Gate") == 2
    assert "has the ID of the actor GateStore" in capsys.readouterr().err
    assert not (other / "map/gate.py").exists()


def test_a_level_2_stub_needs_the_actor_in_the_level_1_map(
    tree_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 6: the level-1 map P0 has no actor P1."""
    glue = tree_root / "pkg/p0/glue.py"
    glue.write_text("from pkg.p1.glue import start_1\n" + glue.read_text(encoding="utf-8"))
    assert run(tree_root, "extract") == 0
    capsys.readouterr()
    assert run(tree_root, "parts", "--map", "P0", "--stub", "Glue") == 2
    err = capsys.readouterr().err
    assert "needs the actor P1, but the map P0 has no component P1" in err
    assert not (tree_root / "map/p0_glue.py").exists()


@pytest.mark.parametrize(
    ("ids", "words"),
    [
        (["Model"], "the stem model is reserved"),
        (["Contract"], "the stem contract is reserved"),
        (["Plan"], "the stem plan is reserved"),
        (["Gate_Contract"], "ends in _contract"),
        (["Gate/Contract"], "ends in _contract"),
        (["Gate/Plan"], "ends in _plan"),
        (["Gate", "gate"], "is also the stem of"),
        (["Gate", "Gate_Routes"], "the file prefix gate_ is the start of the stem gate_routes"),
    ],
)
def test_the_plan_refuses_reserved_and_overlapping_stems(ids: list[str], words: str) -> None:
    """Acceptance 7."""
    assert any(words in line for line in parts.stem_problems(ids))


def test_correct_stems_give_no_line() -> None:
    assert parts.stem_problems(["P0", "P1", "Gateway/Routes", "Gateway/Store"]) == []


def test_the_command_refuses_a_plan_with_a_reserved_stem(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 7, at the command."""
    root = _gate(tmp_path, GATE_MODEL.replace('"Gate"', '"Plan"'))
    assert run(root, "parts", "--stub", "Plan") == 2
    assert "the stem plan is reserved" in capsys.readouterr().err


def test_a_stale_plan_stops_the_record(tree_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Acceptance 8: the facts digest, then the contract digest."""
    _plan(tree_root, capsys)
    facts = tree_root / "docs/map/map.json"
    original = facts.read_text(encoding="utf-8")
    facts.write_text(original.replace('"loc"', '"loc" ', 1), encoding="utf-8")
    capsys.readouterr()
    assert run(tree_root, "parts", "--map", "P0") == 1
    assert STALE in capsys.readouterr().err
    facts.write_text(original, encoding="utf-8")
    assert run(tree_root, "parts", "--map", "P0") == 0
    model = tree_root / "map/model.py"
    model.write_text(model.read_text(encoding="utf-8").replace("value lookup", "value query"))
    capsys.readouterr()
    assert run(tree_root, "parts", "--map", "P0") == 1
    assert STALE in capsys.readouterr().err


def test_a_position_does_not_make_the_plan_stale(tree_root: Path) -> None:
    """Acceptance 8: the contract digest does not contain the positions."""
    cfg = config.load(tree_root)
    tree = nest.load(cfg)
    before = parts_plan.contract_digest(tree.top)
    model = tree_root / "map/model.py"
    text = model.read_text(encoding="utf-8")
    assert re.search(r"x=\d+", text)
    model.write_text(re.sub(r"x=(\d+)", lambda m: f"x={int(m[1]) + 4}", text, count=1))
    after = parts_plan.contract_digest(nest.load(cfg).top)
    assert before == after


def test_check_with_map_warns_about_a_stale_plan(
    tree_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 9."""
    capsys.readouterr()
    assert run(tree_root, "check", "--map", "P0") == 0
    assert "plan" not in capsys.readouterr().out
    _plan(tree_root, capsys)
    assert run(tree_root, "check", "--map", "P0") == 0
    assert "plan" not in capsys.readouterr().out
    model = tree_root / "map/model.py"
    model.write_text(model.read_text(encoding="utf-8").replace("value lookup", "value query"))
    assert run(tree_root, "check", "--map", "P0") == 0
    out = capsys.readouterr().out
    assert f"warning: {STALE} The plan file is map/parts/plan.json." in out


def test_suggest_and_the_stub_give_the_same_file_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 10."""
    root = _gate(tmp_path)
    cfg = config.load(root)
    facts = json.loads(cfg.facts_path.read_text(encoding="utf-8"))
    monkeypatch.setattr(nest, "CARDS_PER_MAP", 1)
    lines = suggest.nesting_lines(nest.load(cfg), facts)
    named = [line for line in lines if line.strip().startswith("Gate:")]
    assert named == ['  Gate: 5 modules, map="gate.py"']
    capsys.readouterr()
    assert run(root, "parts", "--stub", "Gate") == 0
    assert (root / "map/gate.py").is_file()
    assert 'map="gate.py"' in capsys.readouterr().out


def _result(plan: dict[str, Any], part: dict[str, Any], **changed: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "map": part["map"],
        "base_commit": plan["base_commit"],
        "facts_digest": plan["facts_digest"],
        "contract_digest": plan["contract_digest"],
        "files": [part["model_file"], part["contract_file"], part["file_prefix"] + "extra.py"],
        "check_exit": 0,
        "open_lines": [],
        "verdicts": [],
        "answers": [{"line": "P0: single module: Glue", "form": "item", "reason": "r"}],
        "proposed_answers": [{"form": "kind", "value": "single module", "reason": "r"}],
        "boundary_requests": [{"kind": "add_flow", "subject": "Glue", "reason": "r"}],
        "questions": [],
    }
    return {**data, **changed}


def test_the_result_examination(tree_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Acceptance 11."""
    plan = _plan(tree_root, capsys)
    part = plan["parts"][0]
    assert parts_result.problems(_result(plan, part), plan, part) == []
    crossing = [{"line": "x", "form": "crossing", "reason": "r"}]
    found = parts_result.problems(_result(plan, part, answers=crossing), plan, part)
    assert found == [
        "the answer for x has the form crossing. A part agent records answers only in the "
        "forms item and items. Put the answer under proposed_answers."
    ]
    found = parts_result.problems(_result(plan, part, facts_digest="0"), plan, part)
    assert found == ["the facts_digest is not the facts_digest of the plan. Send the part back."]
    found = parts_result.problems(_result(plan, part, files=["map/model.py"]), plan, part)
    assert found == ["the file map/model.py is not in the write set of the part"]
    found = parts_result.problems({"map": "P0"}, plan, part)
    assert "the key facts_digest is missing" in found
    request = [{"kind": "move", "subject": "x"}]
    found = parts_result.problems(_result(plan, part, boundary_requests=request), plan, part)
    assert found == [
        "a boundary request has the kind move. The request kinds are move_module, "
        "add_flow, remove_flow, artifact."
    ]


def test_the_results_option_examines_each_result_file(
    tree_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plan = _plan(tree_root, capsys)
    part = plan["parts"][0]
    (tree_root / part["result_file"]).write_text(json.dumps(_result(plan, part)))
    capsys.readouterr()
    assert run(tree_root, "parts", "--results") == 1
    out = capsys.readouterr().out
    assert "result P0: correct" in out
    assert "result P1: 1 problems" in out and "map/parts/p1.json is missing" in out
    cfg = config.load(tree_root)
    stored = parts_plan.read(cfg, "")
    assert stored is not None
    assert parts_result.examine(cfg, stored)["P0"] == []


def test_the_stub_module_gives_the_stub_without_a_write(tree_root: Path) -> None:
    """The level-2 stub uses the actors of the direct parent map."""
    cfg = config.load(tree_root)
    tree = nest.load(cfg)
    facts = json.loads(cfg.facts_path.read_text(encoding="utf-8"))
    parent = tree.get("P0")
    model, meaning = parts_stub.build(tree, parent, parent.model.component("Glue"), facts)
    actors = sorted(c.id for c in model.components if c.kind == "actor")
    assert actors == ["Q0", "Q1"]
    glue = parent.model.component("Glue")
    assert parts_stub.problems(parent, glue, model, meaning, facts, "x") == []
