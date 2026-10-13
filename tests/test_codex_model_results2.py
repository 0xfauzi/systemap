"""Regression tests for the second Codex review of the model: model-1 to model-9.

Each test shows the failure on `origin/main` at 13a7f45 before the repair.

Acceptance values:

1. model-1: A model file that gives a list for a tuple field (`layers=[]`, a list of
   steps) loads with tuples. `systemap refresh` and `systemap check` give exit code 0
   and no TypeError.
2. model-2: An interface `Service.read` of a re-export from a module that did not parse
   gives no finding: the method is not known. A known re-export without the method still
   gives the finding. This holds for a Python fixture and a TypeScript fixture.
3. model-3: A component with an empty entry and a claimed module that did not parse
   gives no `has no entry` line. A module that parsed and has public names still gives
   the line. This holds for a Python fixture and a TypeScript fixture.
4. model-4: A symbol claim in a module that did not parse and that no component owns
   gives the module-owner line. This holds for a Python fixture and a TypeScript fixture.
5. model-5: A step whose components have no module claim and that cites a current
   record gives one `step source` line. The agent sequence reader refuses the step.
   This holds for a Python fixture and a TypeScript fixture.
6. model-6: A change to the `say` text or to the acting components of a step changes
   the evidence digest of a `step source` line that names no component.
7. model-7: Two flows without ids on the pairs ("A->B", "C") and ("A", "B->C") give a
   placement finding. `flow_ids.find` refuses the text `A->B->C` as two flows. With an
   explicit id on each flow, the finding does not occur.
8. model-8: Without systemap.toml, a pyproject.toml with `tool = 1`, or with
   `[tool] systemap = 1`, gives a ConfigError. The command gives exit code 2 and no
   traceback.
9. model-9: An output page that is not UTF-8 text gives the stale line "differs from
   the rendered output" and exit code 1 in `systemap check` and in `render --check`.
   It gives no traceback.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree
from test_check_rules import current, edit_model
from test_flow_ids import TREES, _project, _ref

from systemap import (
    check,
    config,
    extract,
    flow_ids,
    journeys,
    judgement,
    nest,
    step_refs,
)
from systemap.cli import main
from systemap.config import ConfigError
from systemap.model import (
    Component,
    Flow,
    Journey,
    Meaning,
    Model,
    Region,
    Step,
    problems,
)

# ---- model-1: a list in a tuple field --------------------------------------------


def test_model_1_a_list_in_a_tuple_field_loads_as_a_tuple(tmp_path: Path) -> None:
    current(tmp_path)
    edit_model(tmp_path, "LAYERS = ()", "LAYERS = []")
    edit_model(
        tmp_path, "            ),\n        ),\n    ),\n)", "            ),\n        ],\n    ),\n)"
    )
    edit_model(tmp_path, "        steps=(\n", "        steps=[\n")
    model, meaning = config.load_model(tmp_path / "map/model.py")
    assert meaning.layers == ()
    assert isinstance(meaning.journeys[0].steps, tuple)
    assert model.components and isinstance(model.components, tuple)
    assert main(["--root", str(tmp_path), "refresh"]) == 0
    assert main(["--root", str(tmp_path), "check"]) == 0


# ---- model-2, model-3, model-4: an unknown result is not a failure ----------------

SOURCES: dict[str, dict[str, str]] = {
    "python": {
        "pyproject.toml": '[project]\nname = "web"\nversion = "1"\n',
        "systemap.toml": 'language = "python"\n',
        "src/web/__init__.py": "from web.good import Good\nfrom web.service import Service\n",
        "src/web/service.py": (
            "class Service:\n    def read(self) -> int:\n        return 1\n\n\ndef broken(:\n"
        ),
        "src/web/good.py": "class Good:\n    def write(self) -> int:\n        return 1\n",
        "src/web/script.py": "x = (\n",
        "src/web/named.py": "def run() -> None:\n    pass\n",
    },
    "typescript": {
        "package.json": '{"name":"web"}',
        "tsconfig.json": '{"compilerOptions":{}}',
        "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
        "src/index.ts": "// The package marker.\n",
        "src/service.ts": (
            "export class Service {\n  read(): number { return 1; }\n}\nconst broken = (;\n"
        ),
        "src/good.ts": "export class Good {\n  write(): number { return 1; }\n}\n",
        "src/api.ts": 'export { Good } from "./good";\nexport { Service } from "./service";\n',
        "src/script.ts": "const x = (;\n",
        "src/named.ts": "export function run(): void {}\n",
    },
}
# The module that re-exports Good and Service. A Python re-export is in a package `__init__`.
API = {"python": "web", "typescript": "web.api"}


def _source_facts(tmp_path: Path, language: str) -> dict[str, Any]:
    write_tree(tmp_path, SOURCES[language])
    facts = extract.build(config.load(tmp_path))
    components = facts["components"]
    assert components["web.service"]["completeness"]["parsed"] is False
    assert components["web.script"]["completeness"]["parsed"] is False
    assert components[API[language]]["completeness"]["parsed"] is True
    return facts


def _model(*cards: Component) -> Model:
    return Model((800, 600), (), (), cards, (), ())


@pytest.mark.parametrize("language", ["python", "typescript"])
def test_model_2_a_method_of_a_reexport_that_did_not_parse_is_not_known(
    tmp_path: Path, language: str
) -> None:
    facts = _source_facts(tmp_path, language)
    components = facts["components"]
    api = Component(
        "Api", "Gives the API.", interface="Service.read()", implemented_by=(API[language],)
    )
    assert check.interface_problem(api, components) == ""
    known = dataclasses.replace(api, interface="Good.read()")
    assert "Good has no public method read" in check.interface_problem(known, components)
    good = dataclasses.replace(api, interface="Good.write()")
    assert check.interface_problem(good, components) == ""


@pytest.mark.parametrize("language", ["python", "typescript"])
def test_model_3_an_empty_entry_of_a_module_that_did_not_parse_is_not_known(
    tmp_path: Path, language: str
) -> None:
    facts = _source_facts(tmp_path, language)
    script = Component("Script", "Does the work.", implemented_by=("web.script",))
    named = Component("Named", "Runs.", implemented_by=("web.named",))
    lines = check.check_entry(_model(script, named), facts)
    assert not any(line.startswith("Script has no entry") for line in lines), lines
    assert any(line.startswith("Named has no entry") for line in lines), lines


@pytest.mark.parametrize("language", ["python", "typescript"])
def test_model_4_an_unknown_symbol_name_keeps_the_owner_check(
    tmp_path: Path, language: str
) -> None:
    facts = _source_facts(tmp_path, language)
    reader = Component(
        "Reader", "Reads.", implemented_by=("web.script:read",), entry="read", kind="store"
    )
    lines = check.check_entry(_model(reader), facts)
    assert lines == [
        "Reader has a symbol claim for web.script:read in a module with no owner. A symbol "
        "claim must have a module owner on the map."
    ]
    owner = Component("Script", "Owns the script.", implemented_by=("web.script",), kind="store")
    lines = check.check_entry(_model(reader, owner), facts)
    assert not any("web.script:read" in line for line in lines), lines


# ---- model-5: a step without module claims cites no source -----------------------


def _actor_step(refs: tuple[str, ...]) -> tuple[Model, Meaning]:
    cards = (
        Component("User", "Uses the shop.", kind="actor", region="core", x=20, y=20),
        Component("OrderService", "Takes orders.", implemented_by=("shop.service",), region="core"),
        Component("Other", "Does other work.", implemented_by=("shop.other",), region="core"),
    )
    cards = cards[:1] + tuple(
        dataclasses.replace(c, x=220 + 200 * k, y=20) for k, c in enumerate(cards[1:])
    )
    model = Model(
        canvas=(640, 200),
        containers=(),
        regions=(Region("core", "CORE", (0, 0, 640, 200)),),
        components=cards,
        flows=(Flow("User", "OrderService", "order", "data"),),
        flow_kinds=(),
    )
    step = Step(("User",), (), ("User", "OrderService"), "The user sends an order.", "", refs)
    meaning = Meaning(
        plain={"User": "u", "OrderService": "s", "Other": "o"},
        relations={("User", "OrderService"): "The user sends an order."},
        journeys=(Journey("send", "Send", (step,)),),
    )
    return model, meaning


@pytest.mark.parametrize("language", ["python", "typescript"])
def test_model_5_a_step_without_module_claims_refuses_each_record(
    tmp_path: Path, language: str
) -> None:
    write_tree(tmp_path, TREES[language])
    facts = extract.build(config.load(tmp_path))
    model, meaning = _actor_step((_ref(facts, "shop.other"),))
    assert step_refs.problems(model, meaning, facts) == [
        "step source: journey send step 1 cites shop.other, but no acting or measured "
        "component has a module claim. Cite a current record in a module of an acting or "
        "measured component, or change the step."
    ]
    answer = (
        '{"id": "send", "label": "Send", "steps": [{"edge": ["User", "OrderService"], '
        '"acts": ["User"], "measures": [], "say": "The user sends an order.", '
        f'"source_refs": ["{_ref(facts, "shop.other")}"]}}]}}'
    )
    group = journeys.Group(
        ({"kind": "console_script", "name": "shop", "module": "shop.service", "target": "x"},)
    )
    refused = journeys.read_answer(answer, model, group, facts)
    assert refused.journey is None
    assert "no acting or measured component has a module claim" in refused.problems[0]


# ---- model-6: the step claim is evidence of a step source line ---------------------


@pytest.mark.parametrize("language", ["python", "typescript"])
def test_model_6_the_step_claim_is_evidence_of_a_step_source_line(
    tmp_path: Path, language: str
) -> None:
    path = _project(tmp_path, language)
    stale = '"shop.service@' + "0" * 64 + '"'
    text = path.read_text(encoding="utf-8")
    old = 'say="The service tells the queue to remove the order.",'
    path.write_text(text.replace(old, f"{old}\n                    source_refs=({stale},),"))
    facts = extract.build(config.load(tmp_path))

    def digest() -> tuple[str, str]:
        tree = nest.load(config.load(tmp_path))
        lines = step_refs.problems(tree.top.model, tree.top.meaning, facts)
        assert len(lines) == 1 and "OrderService" not in lines[0], lines
        return lines[0], judgement.evidence_for_tree(tree, facts, tmp_path, lines)[lines[0]]

    line, before = digest()
    edit = path.read_text(encoding="utf-8")
    path.write_text(edit.replace(old, 'say="The service removes the order.",'))
    after_say = digest()
    assert after_say[0] == line and after_say[1] != before
    path.write_text(edit.replace('acts=("OrderService",)', 'acts=("OrderService", "Other")'))
    after_acts = digest()
    assert after_acts[0] == line and after_acts[1] != before


# ---- model-7: two pairs never share a default flow identifier --------------------


def _arrow_model(ids: tuple[str, str]) -> tuple[Model, Meaning]:
    names = ("A->B", "C", "A", "B->C")
    cards = tuple(
        Component(n, "Does work.", kind="actor", region="core", x=20 + 150 * k, y=20)
        for k, n in enumerate(names)
    )
    model = Model(
        canvas=(640, 200),
        containers=(),
        regions=(Region("core", "CORE", (0, 0, 640, 200)),),
        components=cards,
        flows=(
            Flow("A->B", "C", "one", "data", id=ids[0]),
            Flow("A", "B->C", "two", "data", id=ids[1]),
        ),
        flow_kinds=(),
    )
    return model, Meaning(plain={n: n for n in names})


def test_model_7_two_pairs_with_one_default_identifier_are_refused() -> None:
    model, meaning = _arrow_model(("", ""))
    assert model.flows[0].key == model.flows[1].key == "A->B->C"
    expected = (
        "placement: flows A->B -> C and A -> B->C have the same identifier A->B->C. "
        "Give each of these flows its own id"
    )
    assert expected in problems(model, meaning)
    found, problem = flow_ids.find(model.flows, "A->B->C")
    assert found is None and problem.startswith("2 flows connect A->B->C"), problem
    model, meaning = _arrow_model(("one", "two"))
    assert not any("same identifier" in p for p in problems(model, meaning))


# ---- model-8: the tool table of pyproject.toml ------------------------------------


@pytest.mark.parametrize("text", ["tool = 1\n", "[tool]\nsystemap = 1\n"])
def test_model_8_a_tool_value_that_is_not_a_table_is_a_configuration_error(
    tmp_path: Path, text: str, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(tmp_path, {"pyproject.toml": text, "pkg/__init__.py": ""})
    with pytest.raises(ConfigError, match="must be a table"):
        config.load(tmp_path)
    assert main(["--root", str(tmp_path), "check"]) == 2
    assert "must be a table" in capsys.readouterr().err


# ---- model-9: an output that is not UTF-8 text is stale ---------------------------


def test_model_9_an_output_that_is_not_text_is_stale(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current(tmp_path)
    capsys.readouterr()
    (tmp_path / "docs/map/index.html").write_bytes(b"\xff")
    assert main(["--root", str(tmp_path), "check"]) == 1
    assert "docs/map/index.html differs from the rendered output." in capsys.readouterr().out
    assert main(["--root", str(tmp_path), "render", "--check"]) == 1
    assert "docs/map/index.html is stale" in capsys.readouterr().out
    assert main(["--root", str(tmp_path), "refresh"]) == 0
    assert main(["--root", str(tmp_path), "check"]) == 0
