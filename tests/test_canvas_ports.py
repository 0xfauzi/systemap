"""The open boundary lines on the canvas page, with no browser (`page_canvas_ports`).

These tests come from the held branches 6 to 8 of docs/design/nested-parts.md
(tests/test_nested_boundaries.py, tests/test_page_nav.py and tests/test_theme.py of
origin/claude/nested-step-8). Step 5 of docs/design/nested-canvas.md moves the tests that
apply to the canvas. The fixture is the `nested` tree of tests/test_nested.py: Gateway and
Style open a map. Without the flow Routes -> Style, the map inside Gateway has one
`boundary flow` line and one `boundary import` line.

Acceptance values, written before the first run on 2026-11-08:

1. `canvas_page.pages` gives the open lines of the judgement to the canvas data
   (`judgement_json.open_boundary`). Thus `judged` is true. The set of the lines `n` of
   the ports of the page is the set of the "Gateway: boundary" lines of
   `judgement_json.evaluate(...).result.open`. With the two answers of the policy kind
   (`boundary flow` and `boundary import`), no port has a line. An exact answer with its
   evidence digest closes only its line. `open_boundary` gives the boundary lines of
   `evaluate` also for an exact answer that names a boundary line and a different line.
2. The words of the part (`page_canvas_ports.WORDS`) for the form `w` of each line of a
   port: a `boundary flow` line about a parent flow with no nested flow has the form "n"
   and gives "No flow inside", a `boundary import` line has the form "i" and gives
   "Import with no flow", and a `boundary flow` line about a nested flow with no parent
   flow has the form "p" and gives "No flow in the parent map". The script has the same
   texts.
3. Only a flow between an internal component and an actor of the map inside Gateway has
   a port with a nested flow: the flows Reader -> App and Routes -> Style.
4. The layer colours of the tree (`canvas_page.tree_theme`): in each scheme, a layer of
   the top map has the colour of the top page, and a layer that only a nested map has
   gets a colour that no layer of the top map has.
The test of step 6 for the frame policy is acceptance 8 of tests/test_canvas_page.py.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

from conftest import write_tree
from test_canvas_page import DATA
from test_nested import GATEWAY, MODELS, TREE

from systemap import (
    canvas_data,
    canvas_page,
    config,
    extraction,
    judgement_json,
    nest,
    nest_join,
    page_canvas_ports,
)
from systemap.cli import main
from systemap.config import Answer
from systemap.model import all_layers

CONFIG = """
name = "demo"
[package_roots]
"pkg" = "pkg"
[render]
canvas = true
"""
POLICY = (
    "[judgement]\nanswered = [\n"
    '    { kind = "boundary flow", policy = true, reason = "A test." },\n'
    '    { kind = "boundary import", policy = true, reason = "A test." },\n'
    "]\n"
)
ROUTE = '    Flow("Routes", "Style", "guide lookup", "data"),\n'
ROUTE_SENTENCE = '        ("Routes", "Style"): "A route looks a guide up in the cache.",\n'
WITHOUT = GATEWAY.replace(ROUTE, "").replace(ROUTE_SENTENCE, "")


def run(*argv: str) -> int:
    return main(list(argv))


def made(root: Path, gateway: str = WITHOUT, extra: str = "") -> Path:
    """The nested tree with the canvas page, placed, extracted and rendered."""
    files = {**TREE, **MODELS, "systemap.toml": CONFIG + extra, "map/gateway.py": gateway}
    write_tree(root, files)
    for command in ("place", "extract", "render"):
        assert run("--root", str(root), command) == 0
    return root


def page_data(root: Path) -> dict[str, Any]:
    html = (root / "docs/map/index.html").read_text(encoding="utf-8")
    found = DATA.search(html)
    assert found is not None
    return dict(json.loads(found.group(1)))


def port_lines(data: dict[str, Any]) -> set[str]:
    return {line for m in data["maps"] for port in m.get("ports", []) for line in port.get("n", [])}


def loaded(root: Path) -> tuple[config.Config, nest.Tree, dict[str, Any]]:
    cfg = config.load(root)
    tree = nest.load(cfg)
    return cfg, tree, extraction.build(cfg, None)


def test_the_page_and_judgement_agree_on_the_open_boundary_lines(tmp_path: Path) -> None:
    """Acceptance 1 (step 7: test_the_page_and_judgement_agree_on_the_open_boundary_lines)."""
    root = made(tmp_path)
    data = page_data(root)
    assert data["judged"] is True
    cfg, tree, facts = loaded(root)
    judged = judgement_json.evaluate(tree, facts, cfg).result.open
    expected = {line for line in judged if line.startswith("Gateway: boundary")}
    assert len(expected) == 2
    assert port_lines(data) == expected
    assert judgement_json.open_boundary(tree, facts, cfg) == frozenset(
        line for line in judged if nest_join.is_line(tree, line)
    )


def test_the_policy_answers_close_each_port(tmp_path: Path) -> None:
    """Acceptance 1: a recorded answer closes the open ports."""
    root = made(tmp_path, extra=POLICY)
    data = page_data(root)
    assert data["judged"] is True
    assert port_lines(data) == set()
    gateway = next(m for m in data["maps"] if m["id"] == "Gateway")
    assert gateway["ports"] and all("f" in port for port in gateway["ports"])


def test_an_exact_answer_closes_only_its_line(tmp_path: Path) -> None:
    """Acceptance 1: an exact answer with its digest, and an answer for two lines."""
    cfg, tree, facts = loaded(made(tmp_path))
    full = judgement_json.evaluate(tree, facts, cfg)
    flow_line = next(line for line in full.result.open if "boundary flow" in line)
    digest = judgement_json.digest(flow_line, full.evidence)
    assert digest is not None
    exact = Answer(items=(flow_line,), reason="A test.", evidence=digest)
    one = dataclasses.replace(cfg, judgement_answered=(exact,))
    still = judgement_json.open_boundary(tree, facts, one)
    assert flow_line not in still and len(still) == 1
    assert still == _boundary_open(tree, facts, one)
    # An answer that names the boundary line and a line that is not a boundary line.
    other = next(line for line in full.result.open if not nest_join.is_line(tree, line))
    group = Answer(items=(flow_line, other), reason="A test.", evidence="no digest")
    two = dataclasses.replace(cfg, judgement_answered=(group,))
    assert judgement_json.open_boundary(tree, facts, two) == _boundary_open(tree, facts, two)


def _boundary_open(tree: nest.Tree, facts: dict[str, Any], cfg: config.Config) -> frozenset[str]:
    judged = judgement_json.evaluate(tree, facts, cfg).result.open
    return frozenset(line for line in judged if nest_join.is_line(tree, line))


def test_each_open_line_has_its_short_text(tmp_path: Path) -> None:
    """Acceptance 2."""
    data = page_data(made(tmp_path))
    gateway = next(m for m in data["maps"] if m["id"] == "Gateway")
    pairs = [
        pair
        for port in gateway["ports"]
        for pair in zip(port.get("n", []), port.get("w", []), strict=True)
    ]
    words = page_canvas_ports.WORDS
    assert sorted(words[form] for _, form in pairs) == ["Import with no flow", "No flow inside"]
    for line, form in pairs:
        assert (form == "i") == (f": {nest_join.IMPORT_KIND}: " in line), (line, form)
        assert (form == "n") == (" has no nested flow " in line), (line, form)
    # A nested flow with no parent flow names its internal component.
    inside = nest_join.Finding("x", "A", "A", "Y", "", ("A", "Y"))
    assert canvas_data._form(inside) == "n"
    assert canvas_data._form(dataclasses.replace(inside, inner="B")) == "p"
    assert canvas_data._form(dataclasses.replace(inside, imports=(("m", "t"),))) == "i"
    for text in words.values():
        assert json.dumps(text) in page_canvas_ports.PORTS


def test_only_a_flow_between_an_internal_component_and_an_actor_has_a_port(
    tmp_path: Path,
) -> None:
    """Acceptance 3 (step 7: the same test on the linked page)."""
    data = page_data(made(tmp_path, GATEWAY))
    gateway = next(m for m in data["maps"] if m["id"] == "Gateway")
    flows = gateway["flows"]
    ends = {(flows[p["f"]]["s"], flows[p["f"]]["t"]) for p in gateway["ports"] if "f" in p}
    assert ends == {("Reader", "App"), ("Routes", "Style")}


def test_a_new_layer_of_a_nested_map_gets_a_colour_that_no_top_layer_has(
    tmp_path: Path,
) -> None:
    """Acceptance 4 (step 7: test_a_nested_map_gets_the_parent_colour_of_each_layer and
    test_a_new_layer_gets_a_colour_after_the_parent_colours)."""
    record = 'Flow("App", "Store", "record", "data")'
    gateway = (
        GATEWAY.replace(record, record.replace("data", "audit"))
        .replace("flow_kinds=()", 'flow_kinds=("audit",)')
        .replace("Model, Region", "Layer, Model, Region")
        .replace(
            "MEANING = Meaning(",
            'MEANING = Meaning(\n    layers=(Layer("audit", "Audit", question="What is recorded?"),),'
            '\n    layer_of_kind={"audit": "audit"},',
        )
    )
    cfg, tree, _facts = loaded(made(tmp_path, gateway))
    top_layers = {layer.id for layer in all_layers(tree.top.model, tree.top.meaning)}
    inner = {layer.id for m in tree.maps[1:] for layer in all_layers(m.model, m.meaning)}
    nested_only = inner - top_layers
    assert nested_only == {"audit"}
    theme = canvas_page.tree_theme(cfg, tree)
    alone = nest.theme_of(cfg, all_layers(tree.top.model, tree.top.meaning))
    for scheme, table in theme["schemes"].items():
        top = alone["schemes"][scheme]["layers"]
        for lid in top_layers:
            assert table["layers"][lid] == top[lid], (scheme, lid)
        for lid in nested_only:
            assert table["layers"][lid] not in {table["layers"][t] for t in top_layers}
