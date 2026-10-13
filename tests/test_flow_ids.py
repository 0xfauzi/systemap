"""Flow identifiers: two or more flows on one ordered pair.

Acceptance:
- Each existing test passes, and no existing model fixture changes (backward compatibility).
  A flow without an id keeps its review digest and its finding lines.
- A model with two flows `submit-order` and `cancel-order` from OrderService to OrderQueue
  loads, and `systemap check` gives no layout error for it. The figure has two labels.
  Each flow has its own review digest and its own judgement lines.
- `systemap review --flow submit-order` writes only the digest of that flow.
- A step that names `cancel-order` traces that flow. A step with the bare edge of that
  pair is refused with a message that tells the author to use the flow id.
- A step source record outside the components of the step is refused, in a model step and
  in an agent step, with the Python adapter and with the TypeScript adapter.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree

from systemap import (
    config,
    evidence,
    extract,
    flow_ids,
    journeys,
    judgement,
    nest,
    step_refs,
)
from systemap.cli import main
from systemap.model import (
    Component,
    Flow,
    Journey,
    Meaning,
    Model,
    Region,
    Step,
    meaning_problems,
    problems,
)
from systemap.schematic import render as render_schematic

TREES = {
    "python": {
        "systemap.toml": 'language = "python"\n',
        "pyproject.toml": '[project]\nname = "shop"\nversion = "1"\n',
        "src/shop/__init__.py": "",
        "src/shop/service.py": (
            "from shop.queue import push\n\n\ndef submit() -> None:\n    push()\n"
        ),
        "src/shop/queue.py": "def push() -> None:\n    pass\n",
        "src/shop/other.py": "def other() -> None:\n    pass\n",
    },
    "typescript": {
        "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "shop"\n',
        "package.json": '{"name":"shop"}',
        "tsconfig.json": '{"compilerOptions":{}}',
        "src/index.ts": "// The package marker.\n",
        "src/service.ts": (
            'import { push } from "./queue";\nexport function submit(): void { push(); }\n'
        ),
        "src/queue.ts": "export function push(): void {}\n",
        "src/other.ts": "export function other(): void {}\n",
    },
}

ORDER_MODEL = '''"""The map of the order system."""

from __future__ import annotations

from systemap import Component, Container, Flow, Journey, Meaning, Model, Region, Step

MODEL = Model(
    canvas=(600, 300),
    containers=(Container(id="system", label="SHOP", box=(16, 16, 568, 268), tone="server"),),
    regions=(Region(id="core", label="CORE", box=(40, 60, 520, 200), container="system"),),
    components=(
        Component(
            id="OrderService",
            region="core",
            does="Takes the orders.",
            implemented_by=("shop.service",),
            entry="submit",
            x=80,
            y=130,
        ),
        Component(
            id="OrderQueue",
            region="core",
            does="Keeps the orders in sequence.",
            implemented_by=("shop.queue",),
            entry="push",
            x=370,
            y=130,
        ),
        Component(
            id="Other",
            region="core",
            does="Does other work.",
            implemented_by=("shop.other",),
            entry="other",
            x=225,
            y=200,
        ),
    ),
    flows=(
        Flow("OrderService", "OrderQueue", "order", "data", source_refs=SUBMIT_REFS, id="submit-order"),
        Flow("OrderService", "OrderQueue", "cancel", "control", source_refs=CANCEL_REFS, id="cancel-order"),
    ),
    flow_kinds=(),
)

MEANING = Meaning(
    plain={"OrderService": "the order service", "OrderQueue": "the order queue", "Other": "other"},
    relations={
        "submit-order": "The service puts a new order in the queue.",
        "cancel-order": "The service tells the queue to remove an order.",
    },
    journeys=(
        Journey(
            id="cancel",
            label="An order is removed",
            steps=(
                Step(
                    acts=("OrderService",),
                    measures=(),
                    flow="cancel-order",
                    say="The service tells the queue to remove the order.",
                ),
            ),
        ),
    ),
)
'''


def _facts(root: Path) -> dict[str, Any]:
    return extract.build(config.load(root))


def _ref(facts: dict[str, Any], module: str) -> str:
    return f"{module}@{facts['components'][module]['source_sha256']}"


def _project(tmp_path: Path, language: str) -> Path:
    """Write the source tree and the order model. Give the model file."""
    write_tree(tmp_path, TREES[language])
    assert main(["--root", str(tmp_path), "init", "--no-ci"]) == 0
    facts = _facts(tmp_path)
    refs = repr((_ref(facts, "shop.service"),))
    text = ORDER_MODEL.replace("SUBMIT_REFS", refs).replace("CANCEL_REFS", refs)
    path = tmp_path / "map/model.py"
    path.write_text(text, encoding="utf-8")
    return path


def _top(root: Path) -> nest.Map:
    return nest.load(config.load(root)).top


@pytest.mark.parametrize("language", ["python", "typescript"])
def test_two_flows_on_one_pair_load_check_and_draw(
    tmp_path: Path, language: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: the model loads, the check gives no layout error, and two labels show."""
    _project(tmp_path, language)
    m = _top(tmp_path)
    assert [f.key for f in m.model.flows] == ["submit-order", "cancel-order"]
    assert problems(m.model, m.meaning) == []
    assert main(["--root", str(tmp_path), "refresh"]) == 0
    capsys.readouterr()
    assert main(["--root", str(tmp_path), "check"]) == 0
    out = capsys.readouterr().out
    assert "map layout: has no errors (3 components, 2 orthogonal flow paths" in out, out
    svg, detail = render_schematic(m.model, m.meaning, m.theme, _facts(tmp_path))
    labels = [
        part for part in svg.split('<g class="flowlbl')[1:] if 'data-from="OrderService"' in part
    ]
    assert len(labels) == 2
    assert ">order<" in labels[0] and ">cancel<" in labels[1]
    meta = json.loads(detail)["_meta"]
    # Two separate lines: the router gives each flow its own path.
    paths = meta["paths"]
    assert paths.get("0", paths.get(0)) != paths.get("1", paths.get(1))
    assert [e["id"] for e in meta["edges"]] == ["submit-order", "cancel-order"]
    assert [e["say"] for e in meta["edges"]] == [
        "The service puts a new order in the queue.",
        "The service tells the queue to remove an order.",
    ]
    # The step that names cancel-order traces that flow, on the page too.
    assert meta["journeys"][0]["steps"][0]["edge"] == 1
    assert m.meaning.journeys[0].steps[0].edge == ("OrderService", "OrderQueue")


def test_each_flow_has_its_own_judgement_lines_and_review_digest(tmp_path: Path) -> None:
    """Acceptance: two lines before the reviews. `review --flow submit-order` writes one value."""
    path = _project(tmp_path, "python")
    facts = _facts(tmp_path)
    m = _top(tmp_path)
    heads = [line.split(" has ")[0] for line in judgement.flow_review(m.model, m.meaning, facts)]
    assert heads == [
        "flow review: OrderService -> OrderQueue [submit-order] (order)",
        "flow review: OrderService -> OrderQueue [cancel-order] (cancel)",
    ]
    states = evidence.of_model(m.model, m.meaning, facts)
    assert [states.of(f).claim_changed for f in m.model.flows] == [True, True]
    before = path.read_text(encoding="utf-8")
    assert main(["--root", str(tmp_path), "review", "--flow", "submit-order"]) == 0
    after = path.read_text(encoding="utf-8")
    m = _top(tmp_path)
    submit, cancel = m.model.flows
    assert submit.review_digest == evidence.flow_claim_digest(submit, m.meaning)
    assert cancel.review_digest == ""
    heads = [line.split(" has ")[0] for line in judgement.flow_review(m.model, m.meaning, facts)]
    assert heads == ["flow review: OrderService -> OrderQueue [cancel-order] (cancel)"]
    old = 'id="submit-order")'
    new = f'id="submit-order", review_digest="{submit.review_digest}")'
    assert after == before.replace(old, new)
    assert main(["--root", str(tmp_path), "review", "--flow", "cancel-order"]) == 0
    m = _top(tmp_path)
    submit, cancel = m.model.flows
    assert cancel.review_digest == evidence.flow_claim_digest(cancel, m.meaning)
    assert submit.review_digest != cancel.review_digest
    states = evidence.of_model(m.model, m.meaning, facts)
    assert [states.of(f).state for f in m.model.flows] == ["observed", "observed"]


def test_the_judgement_lines_of_two_flows_on_one_pair_are_different() -> None:
    """Acceptance: each flow gives its own `no sentence` and `declared flow` lines."""
    model, meaning = _orders()
    bare = dataclasses.replace(meaning, relations={})
    assert judgement.no_sentence(model, bare) == [
        "no sentence: OrderService -> OrderQueue [submit-order] ('order')",
        "no sentence: OrderService -> OrderQueue [cancel-order] ('cancel')",
    ]
    facts: dict[str, Any] = {"components": {"shop.service": {}, "shop.queue": {}}}
    lines = judgement.declared_flows(model, meaning, facts)
    assert [line.split(" (")[0] for line in lines] == [
        "declared flow: OrderService -> OrderQueue [submit-order]",
        "declared flow: OrderService -> OrderQueue [cancel-order]",
    ]


def test_review_flow_with_the_pair_of_two_flows_is_refused(tmp_path: Path) -> None:
    """Acceptance: `--flow 'OrderService->OrderQueue'` names two flows. Exit 1, no change."""
    path = _project(tmp_path, "python")
    before = path.read_text(encoding="utf-8")
    assert main(["--root", str(tmp_path), "review", "--flow", "OrderService->OrderQueue"]) == 1
    assert main(["--root", str(tmp_path), "review", "--flow", "no-such-flow"]) == 2
    assert path.read_text(encoding="utf-8") == before


def _orders(step: Step | None = None) -> tuple[Model, Meaning]:
    cards = (
        Component("OrderService", "Takes the orders.", implemented_by=("shop.service",)),
        Component("OrderQueue", "Keeps the orders.", implemented_by=("shop.queue",)),
        Component("Other", "Does other work.", implemented_by=("shop.other",)),
    )
    placed = tuple(
        dataclasses.replace(c, region="core", x=20 + 200 * k, y=20) for k, c in enumerate(cards)
    )
    model = Model(
        canvas=(640, 200),
        containers=(),
        regions=(Region("core", "CORE", (0, 0, 640, 200)),),
        components=placed,
        flows=(
            Flow("OrderService", "OrderQueue", "order", "data", id="submit-order"),
            Flow("OrderService", "OrderQueue", "cancel", "control", id="cancel-order"),
        ),
        flow_kinds=(),
    )
    steps = (step,) if step is not None else ()
    meaning = Meaning(
        plain={"OrderService": "s", "OrderQueue": "q", "Other": "o"},
        relations={"submit-order": "It puts an order.", "cancel-order": "It removes an order."},
        journeys=(Journey("cancel", "Cancel", steps),),
    )
    return model, meaning


def test_a_step_names_its_flow_by_id_and_a_bare_pair_is_refused() -> None:
    """Acceptance: the id step traces cancel-order. The pair step gets a clear refusal."""
    by_id = Step(("OrderService",), (), flow="cancel-order", say="It removes the order.")
    model, meaning = _orders(by_id)
    assert meaning_problems(model, meaning) == []
    found, problem = flow_ids.step_flow(by_id, model.flows)
    assert found is model.flows[1] and problem == ""
    by_pair = Step(("OrderService",), (), ("OrderService", "OrderQueue"), "It removes the order.")
    model, meaning = _orders(by_pair)
    assert meaning_problems(model, meaning) == [
        "journey cancel step 1 names the pair OrderService -> OrderQueue, which has 2 flows "
        "(submit-order, cancel-order). Name one flow with flow=ID"
    ]
    wrong = Step(("OrderService",), (), flow="nothing", say="It removes the order.")
    model, meaning = _orders(wrong)
    assert meaning_problems(model, meaning) == [
        "journey cancel step 1 has an unknown flow id: nothing"
    ]


def test_flows_on_one_pair_without_ids_and_pair_keys_are_refused() -> None:
    """Acceptance: a pair of two flows needs ids. A pair key is refused for that pair."""
    model, meaning = _orders()
    plain = dataclasses.replace(model.flows[1], id="")
    mixed = dataclasses.replace(model, flows=(model.flows[0], plain))
    assert mixed.layout_problems() == [
        "flow OrderService -> OrderQueue appears twice ('order' and 'cancel'). Give each flow "
        "on this pair its own id. For an artifact that goes back, add a flow in the "
        "opposite direction"
    ]
    twice = dataclasses.replace(model, flows=(model.flows[0], model.flows[0]))
    assert "flow id submit-order identifies two flows. Give each flow its own id" in (
        twice.layout_problems()
    )
    spaced = dataclasses.replace(model.flows[1], id="cancel order")
    bad = dataclasses.replace(model, flows=(model.flows[0], spaced))
    assert any("has the id 'cancel order'" in p for p in bad.layout_problems())
    keyed = dataclasses.replace(
        meaning,
        relations={**meaning.relations, ("OrderService", "OrderQueue"): "Both."},
        layer_overrides={"no-flow": "data"},
    )
    found = meaning_problems(model, keyed)
    assert (
        "relations uses the pair OrderService -> OrderQueue as a key, but 2 flows connect "
        "this pair. Use the id of each flow as its key"
    ) in found
    assert "layer_overrides has an unknown flow: no-flow" in found


def test_a_flow_without_an_id_keeps_its_digest_and_its_old_keys() -> None:
    """Acceptance: the claim digest of a flow without an id is the digest before flow ids."""
    flow = Flow("A", "B", "thing", "data")
    meaning = Meaning(plain={}, relations={("A", "B"): "A gives B the thing."})
    claim = ("A", "B", "thing", "data", "A gives B the thing.")
    data = json.dumps(claim, ensure_ascii=False, separators=(",", ":"))
    assert evidence.flow_claim_digest(flow, meaning) == hashlib.sha256(data.encode()).hexdigest()
    assert flow.key == "A->B" and flow.name == "A -> B"
    assert meaning.relation(flow) == "A gives B the thing."
    # The id form of the key gives the same sentence.
    assert Meaning(plain={}, relations={"A->B": "Same."}).relation(flow) == "Same."
    step = Step(("A",), (), ("A", "B"), "A gives B the thing.")
    record = flow_ids.journey_record(Journey("j", "J", (step,)))
    # The sequence claim of a step without the new fields is the claim before them.
    assert list(record["steps"]) == [
        {"acts": ("A",), "measures": (), "edge": ("A", "B"), "say": "A gives B the thing."}
    ]


def _language_facts(tmp_path: Path, language: str) -> dict[str, Any]:
    write_tree(tmp_path, TREES[language])
    return _facts(tmp_path)


@pytest.mark.parametrize("language", ["python", "typescript"])
def test_a_step_source_record_outside_the_step_components_is_refused(
    tmp_path: Path, language: str
) -> None:
    """Acceptance: a judgement line for the outside and stale records. The step in the
    module of the acting component gives no line."""
    facts = _language_facts(tmp_path, language)
    inside, outside = _ref(facts, "shop.service"), _ref(facts, "shop.other")
    stale = "shop.service@" + "0" * 64
    step = Step(
        ("OrderService",),
        (),
        flow="cancel-order",
        say="It removes the order.",
        source_refs=(inside, outside, stale),
    )
    model, meaning = _orders(step)
    lines = step_refs.problems(model, meaning, facts)
    assert lines == [
        "step source: journey cancel step 1 cites shop.service, which does not resolve in the "
        "current source. Cite a current record in a module of an acting or measured "
        "component, or change the step.",
        "step source: journey cancel step 1 cites shop.other, which is in no module of "
        "OrderService. Cite a current record in a module of an acting or measured "
        "component, or change the step.",
    ]
    assert all(judgement.kind_of(line) == "step source" for line in lines)
    good = dataclasses.replace(step, source_refs=(inside,))
    model, meaning = _orders(good)
    assert step_refs.problems(model, meaning, facts) == []


@pytest.mark.parametrize("language", ["python", "typescript"])
def test_an_agent_step_with_an_outside_source_record_is_refused(
    tmp_path: Path, language: str
) -> None:
    """Acceptance: the draft has the refusal and no sequence. A good record is kept."""
    facts = _language_facts(tmp_path, language)
    model, _meaning = _orders()
    group = journeys.Group(
        ({"kind": "console_script", "name": "shop", "module": "shop.service", "target": "submit"},)
    )

    def answer(refs: list[str]) -> str:
        step = {
            "flow": "cancel-order",
            "acts": ["OrderService"],
            "measures": [],
            "say": "The service tells the queue to remove the order.",
            "source_refs": refs,
        }
        return json.dumps({"id": "cancel", "label": "Cancel", "steps": [step]})

    refused = journeys.read_answer(answer([_ref(facts, "shop.other")]), model, group, facts)
    assert refused.journey is None
    assert refused.problems[0] == "step 1 cites shop.other, which is in no module of OrderService"
    kept = journeys.read_answer(answer([_ref(facts, "shop.service")]), model, group, facts)
    assert kept.journey is not None and kept.problems == ()
    step = kept.journey.steps[0]
    assert step.flow == "cancel-order" and step.edge == ("OrderService", "OrderQueue")
    assert any('flow="cancel-order",' in line for line in journeys.as_source(kept.journey))
    no_facts = journeys.read_answer(answer([_ref(facts, "shop.service")]), model, group)
    assert no_facts.problems[0] == (
        "step 1 has source_refs, but no facts are available to examine them"
    )
