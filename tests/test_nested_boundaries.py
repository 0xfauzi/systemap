"""The boundary of a nested map on its page: neighbours, the frame, the ports, and the badge.

The `nested` fixture has the top map with the cards Reader, Gateway, Style and Writer.
Gateway opens a map with the actors Reader and Style, and Style opens a map with the
actors Gateway and Writer. In the top layout, Reader is above Gateway and Style is at
its right. Thus `systemap place` puts the actor Reader above the frame of the map
inside Gateway, and the actor Style at the right of it.
"""

from __future__ import annotations

import json
from pathlib import Path

from conftest import write_tree
from test_nested import (
    CONFIG,
    GATEWAY,
    _detail_json,
    nested,  # noqa: F401 - a fixture
)

from systemap import (
    config,
    extraction,
    judgement_json,
    nest,
    page_context,
    place_nested,
    schematic_nested,
)
from systemap import theme as theme_mod
from systemap.cli import main
from systemap.model import Layer


def run(*argv: str) -> int:
    return main(list(argv))


def _tree(root: Path) -> nest.Tree:
    return nest.load(config.load(root))


def _page(root: Path, map_id: str = "") -> tuple[str, dict[str, object]]:
    path = root / "docs/map" / map_id / "index.html" if map_id else root / "docs/map/index.html"
    html = path.read_text(encoding="utf-8")
    return html, json.loads(_detail_json(html))


# ---- the placement ---------------------------------------------------------------------


def test_place_puts_each_neighbour_in_the_band_of_its_parent_direction(
    nested: Path,  # noqa: F811
) -> None:
    tree = _tree(nested)
    found = {}
    for m in tree.maps[1:]:
        parent = tree.parent_of(m)
        assert parent is not None
        actors = [c.id for c in m.model.components if c.kind == "actor"]
        sides = place_nested.parent_sides(parent.model, m.card, actors)
        assert sides is not None
        for cid in actors:
            found[(m.id, cid)] = (place_nested.band_of(m.model, cid), sides[cid])
    assert found == {
        ("Gateway", "Reader"): ("top", "top"),
        ("Gateway", "Style"): ("right", "right"),
        ("Style", "Gateway"): ("left", "left"),
        ("Style", "Writer"): ("bottom", "bottom"),
    }


def test_a_placement_that_keeps_positions_and_the_top_map_move_no_card(
    nested: Path,  # noqa: F811
) -> None:
    tree = _tree(nested)
    gateway = tree.get("Gateway")
    kept = place_nested.compute(gateway.model, tree.top.model, "Gateway")
    assert kept.arranged is False and kept.placement.positions == {}
    top = place_nested.compute(tree.top.model, None, "", all_cards=True)
    assert top.arranged is False


def test_the_band_of_a_direction() -> None:
    assert place_nested.side(10, 2) == "right"
    assert place_nested.side(-10, 2) == "left"
    assert place_nested.side(1, 20) == "bottom"
    assert place_nested.side(1, -20) == "top"
    # A tie gives a side band.
    assert place_nested.side(-5, 5) == "left"


# ---- the layer colors --------------------------------------------------------------------


def test_a_nested_map_gets_the_parent_colour_of_each_layer(nested: Path) -> None:  # noqa: F811
    tree = _tree(nested)
    top = tree.top.theme["schemes"]
    for m in tree.maps[1:]:
        for scheme, table in m.theme["schemes"].items():
            for lid, colour in table["layers"].items():
                if lid in top[scheme]["layers"]:
                    assert colour == top[scheme]["layers"][lid], (m.id, scheme, lid)


def test_a_new_layer_gets_a_colour_after_the_parent_colours() -> None:
    parent = theme_mod.resolve({}, [Layer("a", "A"), Layer("b", "B")])
    child = theme_mod.resolve({}, [Layer("b", "B"), Layer("c", "C")], parent)
    for scheme, table in child["schemes"].items():
        above = parent["schemes"][scheme]["layers"]
        assert table["layers"]["b"] == above["b"]
        assert table["layers"]["c"] not in above.values()
    alone = theme_mod.resolve({}, [Layer("b", "B"), Layer("c", "C")])
    assert alone["layers"]["b"] == parent["layers"]["a"]


# ---- the pages ----------------------------------------------------------------------------


def test_a_nested_page_labels_its_neighbours_and_draws_the_frame(
    nested: Path,  # noqa: F811
) -> None:
    assert run("--root", str(nested), "refresh") == 0
    html, detail = _page(nested, "Gateway")
    style = detail["Style"]
    assert isinstance(style, dict)
    assert style["state_label"] == "in the parent map"
    assert style["neighbour"] == {
        "where": "parent",
        "card": "Gateway",
        "parent_href": "../index.html#Style",
        "map_href": "../Style/index.html",
        "flows": [{"from": "Gateway", "to": "Style", "art": "guide lookup"}],
    }
    assert style["boundary"] == []
    assert html.count('class="node__mark node__parent"') == 2
    meta = detail["_meta"]
    assert isinstance(meta, dict)
    frame = meta["frame"]
    assert frame["label"] == "Inside Gateway" and "Inside Gateway" in html
    # Two flows cross the frame. No boundary line is open, so no port shows a join state.
    assert [p["text"] for p in frame["ports"]] == ["", ""]
    assert "frame__port--open" not in html and "verified" not in html.lower()
    # The parent context mark: one link to the opening card in the parent page.
    assert html.count('<a class="ctx" href="../index.html#Gateway"') == 1
    assert html.count('class="ctx__open"') == 1 and html.count('class="ctx__near"') == 2
    assert html.count('class="ctx__card"') == 2


def test_the_top_page_has_badges_and_the_nested_flows_of_each_parent_flow(
    nested: Path,  # noqa: F811
) -> None:
    assert run("--root", str(nested), "refresh") == 0
    html, detail = _page(nested)
    assert ">3 inside</text>" in html and ">2 inside</text>" in html
    assert 'class="frame"' not in html and 'class="ctx"' not in html
    meta = detail["_meta"]
    assert isinstance(meta, dict)
    edges = {f"{e['from']}->{e['to']}": e for e in meta["edges"]}
    # The flow between two cards that open a map has a nested flow in each map.
    assert edges["Gateway->Style"]["inside"] == [
        {
            "from": "Routes",
            "to": "Style",
            "art": "guide lookup",
            "inner": "Routes",
            "href": "Gateway/index.html#Routes",
        },
        {
            "from": "Gateway",
            "to": "Cache",
            "art": "lookup",
            "inner": "Cache",
            "href": "Style/index.html#Cache",
        },
    ]
    assert "inside" not in edges["User->Reader"]
    reader = detail["Reader"]
    assert isinstance(reader, dict) and "neighbour" not in reader


def test_an_open_boundary_line_gives_a_dotted_port_with_its_text(
    nested: Path,  # noqa: F811
) -> None:
    """Without the flow Routes -> Style, the map inside Gateway has a `boundary flow` line
    and a `boundary import` line. Each gives an open port and an inspector row. A recorded
    answer closes them."""
    without = GATEWAY.replace('    Flow("Routes", "Style", "guide lookup", "data"),\n', "")
    without = without.replace(
        '        ("Routes", "Style"): "A route looks a guide up in the cache.",\n', ""
    )
    write_tree(nested, {"map/gateway.py": without})
    assert run("--root", str(nested), "place", "--map", "Gateway") == 0
    assert run("--root", str(nested), "refresh") == 0
    html, detail = _page(nested, "Gateway")
    meta = detail["_meta"]
    assert isinstance(meta, dict)
    texts = sorted(p["text"] for p in meta["frame"]["ports"] if p["text"])
    assert texts == ["Import with no flow", "No flow inside"]
    assert html.count("frame__port--open") == 2
    style = detail["Style"]
    assert isinstance(style, dict)
    assert sorted(style["boundary"]) == [
        "Gateway: boundary flow: the parent flow from Gateway to Style has no nested flow to "
        "actor Style",
        "Gateway: boundary import: Routes imports Style, and no flow connects Routes and "
        "actor Style",
    ]
    write_tree(
        nested,
        {
            "systemap.toml": CONFIG
            + "[judgement]\nanswered = [\n"
            + '    { kind = "boundary flow", policy = true, reason = "A test." },\n'
            + '    { kind = "boundary import", policy = true, reason = "A test." },\n'
            + "]\n"
        },
    )
    assert run("--root", str(nested), "refresh") == 0
    html, detail = _page(nested, "Gateway")
    assert "frame__port--open" not in html
    style = detail["Style"]
    assert isinstance(style, dict) and style["boundary"] == []


def test_an_actor_of_the_parent_map_stays_outside(tmp_path: Path) -> None:
    """The map tree on three levels: on level 2, Glue is a component of the parent map, and
    Base is an actor of the parent map."""
    import three_levels

    write_tree(tmp_path, three_levels.files(1, 1))
    assert run("--root", str(tmp_path), "place") == 0
    tree = _tree(tmp_path)
    m = tree.get("P0/Q0")
    parent = tree.parent_of(m)
    assert parent is not None
    found = page_context.neighbours(tree, m, parent)
    assert found["Glue"]["where"] == "parent" and found["Base"]["where"] == "outside"
    assert found["Glue"]["map_href"] == "" and found["Base"]["flows"] == [
        {"from": "Q0", "to": "Base", "art": "value lookup"}
    ]


def test_two_parent_flows_in_one_direction_list_each_nested_flow_one_time(
    nested: Path,  # noqa: F811
) -> None:
    from test_nested import TOP

    first = '    Flow("Gateway", "Style", "guide lookup", "data"),\n'
    second = first.replace("guide lookup", "second lookup")
    write_tree(nested, {"map/model.py": TOP.replace(first, first + second)})
    tree = _tree(nested)
    found = page_context.inside_flows(tree, tree.top)
    assert [row["art"] for row in found["Gateway->Style"]] == ["guide lookup", "lookup"]


def test_the_page_and_judgement_agree_on_the_open_boundary_lines(
    nested: Path,  # noqa: F811
) -> None:
    without = GATEWAY.replace('    Flow("Routes", "Style", "guide lookup", "data"),\n', "")
    write_tree(nested, {"map/gateway.py": without})
    cfg = config.load(nested)
    tree = nest.load(cfg)
    facts = extraction.build(cfg, None)
    still = page_context.open_boundary(cfg, tree, facts)
    judged = judgement_json.evaluate(tree, facts, cfg)
    assert still == frozenset(judged.result.open)
    boundary = page_context.open_lines(tree, tree.get("Gateway"), facts, still)
    assert boundary
    assert {row["line"] for row in boundary} == {
        line for line in judged.result.open if line.startswith("Gateway: boundary")
    }


def test_only_a_flow_between_an_internal_component_and_an_actor_has_a_port(
    nested: Path,  # noqa: F811
) -> None:
    assert run("--root", str(nested), "place") == 0
    model = _tree(nested).get("Gateway").model
    frame = schematic_nested.frame_box(model)
    assert frame is not None
    x, y, w, h = frame
    # Each path goes from the middle of the frame to a point far outside it.
    out = [[x + w / 2, y + h / 2], [x + w / 2, y - 500]]
    paths = dict.fromkeys(range(len(model.flows)), out)
    found = schematic_nested.ports(model, {"label": "Inside Gateway"}, paths, frame)
    ends = {(model.flows[p["edge"]].src, model.flows[p["edge"]].dst) for p in found}
    assert ends == {("Reader", "App"), ("Routes", "Style")}
