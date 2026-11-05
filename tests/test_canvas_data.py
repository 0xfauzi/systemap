"""The canvas data: one JSON object for all maps of a map tree (`canvas_data`).

Acceptance values:

1. Each card and each flow of each map of the tree is in the data one time, in the map
   of its model. The cards are in reading order, and the flows are in model order.
2. The route points and the label box of each flow are the values of `route.routed`,
   and the page gives the same values in its detail data.
3. The ports of a nested map agree with `nest_join`: each flow between an internal
   component and an actor has one port, and each boundary line of the map is in one
   port. With the open lines of the judgement, a port gives only its open lines.
4. Two builds give the same bytes.
5. A map without nested maps gives one map with no ports.
6. A map with change data has its revision comparison. A map without it has none.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import three_levels
from conftest import write_tree
from test_nest_join import CONFIG, NESTED, SOURCE, TO_AUTH, TO_AUTH_SENTENCE, TOP

from systemap import (
    assurance,
    canvas_data,
    config,
    facts_file,
    judgement_json,
    nest,
    nest_join,
    route,
    schematic,
)
from systemap.cli import main


def _made(root: Path, files: dict[str, str]) -> tuple[config.Config, nest.Tree, dict[str, Any]]:
    write_tree(root, files)
    for command in ("place", "extract"):
        assert main(["--root", str(root), command]) == 0
    cfg = config.load(root)
    return cfg, nest.load(cfg), facts_file.read_facts(cfg.facts_path, cfg.root)


@pytest.fixture(scope="module")
def levels(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[config.Config, nest.Tree, dict[str, Any]]:
    return _made(tmp_path_factory.mktemp("levels"), three_levels.files())


def _join(root: Path, top: str = TOP, nested: str = NESTED) -> tuple[Any, ...]:
    files = {"systemap.toml": CONFIG, "map/model.py": top, "map/gateway.py": nested, **SOURCE}
    return _made(root, files)


def _has_each_card_and_flow(tree: nest.Tree, m: nest.Map, shown: dict[str, Any]) -> None:
    """Make sure that the data of one map has each card and each flow one time."""
    ids = [card["id"] for card in shown["cards"]]
    assert sorted(ids) == sorted(c.id for c in m.model.components)
    boxes = [tuple(card["b"][:2])[::-1] for card in shown["cards"]]
    assert boxes == sorted(boxes)
    flows = [(f["s"], f["t"], f["a"], f["k"]) for f in shown["flows"]]
    assert flows == [(f.src, f.dst, f.artifact, f.kind) for f in m.model.flows]
    opens = {card["id"]: card["o"] for card in shown["cards"] if "o" in card}
    assert opens == {child.card: child.id for child in tree.children(m)}


def test_each_card_and_flow_of_each_map_is_in_the_data_one_time(levels: Any) -> None:
    """Acceptance 1."""
    cfg, tree, facts = levels
    data = canvas_data.build(cfg, tree, facts)
    assert [m["id"] for m in data["maps"]] == three_levels.map_ids()
    for m, shown in zip(tree.maps, data["maps"], strict=True):
        _has_each_card_and_flow(tree, m, shown)


def test_the_routes_are_the_routes_of_the_router_and_the_page(levels: Any) -> None:
    """Acceptance 2."""
    cfg, tree, facts = levels
    route.clear_routed()
    data = canvas_data.build(cfg, tree, facts)
    for m, shown in zip(tree.maps, data["maps"], strict=True):
        routes, seats = schematic.flow_routes(m.model, schematic.geometry(m.model))
        _svg, text = schematic.render(
            m.model, m.meaning, m.theme, facts, observed_by=cfg.observed_by
        )
        page = json.loads(text)["_meta"]
        for i, flow in enumerate(shown["flows"]):
            points = [[round(x, 1), round(y, 1)] for x, y in routes[i].points]
            assert flow["p"] == points == page["paths"][str(i)]
            box = [round(v, 1) for v in seats[i].box]
            assert flow["lb"] == box == page["labels"][i]["box"]


def test_the_ports_agree_with_the_boundary_findings(tmp_path: Path) -> None:
    """Acceptance 3: a nested flow with no parent flow, a parent flow with no nested flow,
    and an import with no flow."""
    top = TOP.replace(
        '    Flow("Gateway", "Store", "record", "data"),\n',
        '    Flow("Gateway", "Store", "record", "data"),\n'
        '    Flow("Log", "Gateway", "entry", "data"),\n',
    ).replace(
        '        ("Gateway", "Store"): "The gateway sends the record to the store.",\n',
        '        ("Gateway", "Store"): "The gateway sends the record to the store.",\n'
        '        ("Log", "Gateway"): "The log sends the entry to the gateway.",\n',
    )
    nested = NESTED.replace(TO_AUTH, '    Flow("Auth", "Views", "key", "data"),\n').replace(
        TO_AUTH_SENTENCE, '        ("Auth", "Views"): "The auth sends the key to the views.",\n'
    )
    cfg, tree, facts = _join(tmp_path, top, nested)
    m = tree.get("Gateway")
    lines = nest_join.lines(tree, m, facts)
    assert len(lines) == 4
    shown = canvas_data.build(cfg, tree, facts)["maps"][1]
    ports = shown["ports"]
    listed = [line for port in ports for line in port.get("n", [])]
    assert sorted(listed) == sorted(lines)
    assert [port["f"] for port in ports if "f" in port] == _crossing(m) == [0, 1]
    into = next(port for port in ports if port.get("f") == 0)
    assert (into["x"], into["i"], into["d"], into["pf"]) == ("Auth", "Views", "in", [])
    assert into["at"] == shown["flows"][0]["p"][0]
    assert into["n"] == [line for line in lines if "actor Auth sends to Views" in line]
    out = next(port for port in ports if port.get("f") == 1)
    assert (out["x"], out["i"], out["d"], out["pf"]) == ("Store", "Views", "out", [1])
    assert "n" not in out
    _judged_ports(cfg, tree, facts, ports)


def _crossing(m: nest.Map) -> list[int]:
    """Give the indexes of the nested flows between an internal component and an actor."""
    ends = [(f.src, f.dst) for f in m.model.flows]
    return [
        i
        for i, (a, b) in enumerate(ends)
        if any(nest_join.crossing(m.model, m.card, *pair) for pair in ((a, b), (b, a)))
    ]


def _judged_ports(cfg: Any, tree: nest.Tree, facts: dict[str, Any], ports: list[Any]) -> None:
    """With the open lines of the judgement, the ports are the same, because no line has an
    answer. With no open line, only the ports of the flows stay, and they have no lines."""
    judged = judgement_json.evaluate(tree, facts, cfg).result.open
    assert {line for port in ports for line in port.get("n", [])} <= set(judged)
    assert canvas_data.build(cfg, tree, facts, judged)["maps"][1]["ports"] == ports
    closed = canvas_data.build(cfg, tree, facts, open_lines=())["maps"][1]["ports"]
    assert closed == [{k: v for k, v in port.items() if k != "n"} for port in ports if "f" in port]


def test_two_builds_give_the_same_bytes(levels: Any) -> None:
    """Acceptance 4. The caches of the router and the claims are empty before the second
    build, and the tree is loaded again."""
    cfg, tree, facts = levels
    first = canvas_data.text(canvas_data.build(cfg, tree, facts))
    route.clear_routed()
    assurance.clear_claims()
    again = canvas_data.text(canvas_data.build(cfg, nest.load(cfg), facts))
    assert first.encode("utf-8") == again.encode("utf-8")


def test_a_map_without_nested_maps(tmp_path: Path) -> None:
    """Acceptance 5."""
    top = TOP.replace(', map="gateway.py"', "")
    files = {"systemap.toml": CONFIG, "map/model.py": top, **SOURCE}
    cfg, tree, facts = _made(tmp_path, files)
    data = canvas_data.build(cfg, tree, facts)
    assert len(data["maps"]) == 1
    (shown,) = data["maps"]
    assert shown["id"] == ""
    assert not {"up", "card", "ports", "ch"} & set(shown)
    assert all("o" not in card for card in shown["cards"])
    assert len(shown["cards"]) == 4
    assert len(shown["flows"]) == 2


def test_only_a_map_with_change_data_has_a_comparison(tmp_path: Path) -> None:
    """Acceptance 6."""
    cfg, tree, facts = _join(tmp_path)
    change = {
        "has_change": True,
        "base": "main",
        "head": "HEAD",
        "direct": {"Routes"},
        "adjacent": set(),
        "per_component": {},
    }
    data = canvas_data.build(cfg, tree, facts, changes={"Gateway": change})
    top, nested = data["maps"]
    assert "ch" not in top
    assert nested["ch"]["direct"] == ["Routes"]
    json.loads(canvas_data.text(data))


def test_a_line_of_two_flows_is_in_one_port(tmp_path: Path) -> None:
    """Acceptance 3: two nested flows from the actor Auth to Views give one line, and the
    line is in the port of the first flow only."""
    nested = NESTED.replace(
        TO_AUTH,
        '    Flow("Auth", "Views", "key", "data", id="key"),\n'
        '    Flow("Auth", "Views", "code", "data", id="code"),\n',
    ).replace(
        TO_AUTH_SENTENCE,
        '        "key": "The auth sends the key to the views.",\n'
        '        "code": "The auth sends the code to the views.",\n',
    )
    cfg, tree, facts = _join(tmp_path, nested=nested)
    (line,) = [one for one in nest_join.lines(tree, tree.get("Gateway"), facts) if "Views" in one]
    ports = canvas_data.build(cfg, tree, facts)["maps"][1]["ports"]
    assert [(port.get("f"), port.get("n")) for port in ports if port.get("i") == "Views"] == [
        (0, [line]),
        (1, None),
        (2, None),
    ]
