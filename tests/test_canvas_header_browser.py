"""The header, the views and the layers of the canvas page in a browser (`canvas_header`,
`page_canvas_view`).

The test drives real canvas pages in the Chromium of Playwright (tests/canvas_header.js):
the fixture of tests/test_nest_join.py, the self-map of this repository, and generated
data of bench/jev/canvas_frames.py with two layers (`_layered`). The test skips when Node
or the Playwright package is not there, except when SYSTEMAP_BROWSER_TESTS is "required"
(the CI job canvas-browser).

Acceptance values:

1. The layer filter. For each map of the self-map tree and of the fixture, and for each
   layer of the union and All, at the fit of the map, the flows that the frame draws with
   an alpha above 0 are exactly the flows of the layer (`model.reading`), and the cards
   that it draws with an alpha below 1 are exactly the quiet cards of `paint` in
   `schematic_relations.py`: no flow of the layer touches the card, and the card is not a
   subject of the layer. A quiet card has the alpha 0.32. A map that does not have the
   layer shows no flow, and each of its cards is quiet.
   Added on 2026-11-07 (U4 in bench/jev/README.md): a boundary flow from a portal shows only
   when the layer has its nested flow (`f` of its port) or a flow of the map above that the
   port continues (`pf`).
2. A layer change and a view change fade. On the generated M11 shape and the generated map
   of 1,500 cards (its marks image), without reduced motion, at rest and during a pan, each
   alpha of a card, a flow, a mark of a view and the marks image of the old view changes
   by 0.25 or less between two frames, and a change by 1 takes 160 ms or more. With reduced
   motion (the system setting or the page setting), each change occurs in one frame.
3. The seam calls of a frame are not more than the count of the cards and the flows that
   the frame draws (STATS), in each frame of a pan with two layer changes on the generated
   maps of 400 and 1,500 cards.
4. A letter, +, -, =, an arrow key or Escape in a control of the header, in the select of
   the layers and in a text field does not change the camera. In the layer toolbar, the
   arrow keys, Home and End move the keyboard focus and the pressed layer. On the canvas,
   an arrow key still moves the camera.
5. Access (C4): each control of the header has a name. The keyboard focus on each control is
   visible: an outline 2 px wide or more with a contrast ratio of 3 or more against the
   header. Tab goes through the header, then to the canvas, then to the list of the tree,
   and then out of the page. With the focus on each control of the header, axe-core 4.14.0
   finds no violation, at 1440 x 900 and 390 x 844 pixels, in the light and the dark
   scheme. The page has no script error.
6. C5: on a phone screen of 390 x 844 pixels with a touch screen, the scroll width is 390
   pixels, the scroll position is 0, the header is 56 pixels high, and each target of the
   header is 44 x 44 pixels or more. The top band of the fit includes the header.
"""

from __future__ import annotations

import functools
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_canvas_access import AXE_VERSION
from test_canvas_browser import _bench, browser
from test_canvas_page import _loaded, _made
from test_theme import contrast

from systemap import canvas_data, canvas_page, config, facts_file, nest
from systemap.model import all_layers, reading, subject_of_layer

ROOT = Path(__file__).resolve().parent
DRIVER = ROOT / "canvas_header.js"
REPO = ROOT.parent


def _drive(*args: str) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), *args], capture_output=True, text=True, timeout=600
    )
    assert proc.returncode == 0, proc.stderr
    return dict(json.loads(proc.stdout))


def _layered(data: dict[str, Any]) -> dict[str, Any]:
    """Give the generated data with two layers: the even flows are data, the odd flows control."""
    for m in data["maps"]:
        for i, f in enumerate(m["flows"]):
            f["l"] = "data" if i % 2 == 0 else "control"
        m["layers"] = [
            {"id": lay, "n": lay.title(), "q": f"Which flows are {lay} flows?", "e": e}
            for lay, e in (
                ("data", list(range(0, len(m["flows"]), 2))),
                ("control", list(range(1, len(m["flows"]), 2))),
            )
        ]
    return data


@pytest.fixture(scope="module")
def fixture_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = _made(tmp_path_factory.mktemp("head"), "[render]\ncanvas = true\n")
    return root / "docs" / "map" / "index.html"


@functools.cache
def _self_tree() -> tuple[config.Config, nest.Tree, dict[str, Any]]:
    cfg = config.load(REPO)
    return cfg, nest.load(cfg), facts_file.read_facts(cfg.facts_path, cfg.root)


@pytest.fixture(scope="module")
def self_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    cfg, tree, facts = _self_tree()
    out = tmp_path_factory.mktemp("self") / "index.html"
    data = canvas_data.build(cfg, tree, facts)
    out.write_text(canvas_page.build(canvas_page.tree_theme(cfg, tree), data), encoding="utf-8")
    return out


def _generated(factory: pytest.TempPathFactory, name: str, data: dict[str, Any]) -> Path:
    return Path(_bench().write_page(_layered(data), factory.mktemp(name) / "page.html"))


@pytest.fixture(scope="module")
def shape_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _generated(tmp_path_factory, "shape", _bench().nested_tree())


@pytest.fixture(scope="module")
def grid_pages(tmp_path_factory: pytest.TempPathFactory) -> dict[int, Path]:
    return {n: _generated(tmp_path_factory, f"g{n}", _bench().grid_map(n)) for n in (400, 1500)}


def _layer_of(m: nest.Map, lay: str) -> tuple[list[int], list[str]]:
    """Give the flows and the quiet cards of layer `lay` in map m."""
    if lay not in {x.id for x in all_layers(m.model, m.meaning)}:
        return [], sorted(c.id for c in m.model.components)
    edges, _subjects = reading(m.model, m.meaning, lay)
    touched = {e for i in edges for e in m.model.flows[i].edge}
    quiet = sorted(
        c.id
        for c in m.model.components
        if c.id not in touched and not subject_of_layer(m.model, lay, c.id)
    )
    return sorted(edges), quiet


def _expected(tree: nest.Tree) -> dict[str, dict[str, tuple[list[int], list[str]]]]:
    """Give, for each map and each layer of the union, the flows and the quiet cards."""
    union = {lay.id for m in tree.maps for lay in all_layers(m.model, m.meaning)}
    out: dict[str, dict[str, tuple[list[int], list[str]]]] = {}
    for m in tree.maps:
        out[m.id] = {"all": (list(range(len(m.model.flows))), [])}
        out[m.id] |= {lay: _layer_of(m, lay) for lay in sorted(union)}
    return out


def _ports_in_layer(data: dict[str, Any], chain: list[str], lay: str) -> set[tuple[str, str]]:
    """Give the neighbour and the direction of each port of the open maps that layer `lay`
    shows: its nested flow or a flow of the map above that it continues is in the layer."""
    maps = {m["id"]: m for m in data["maps"]}

    def edges(map_id: str) -> set[int]:
        m = maps[map_id]
        if lay == "all":
            return set(range(len(m["flows"])))
        return {i for one in m.get("layers") or [] if one["id"] == lay for i in one["e"]}

    out = set()
    for map_id in chain:
        up = map_id.rsplit("/", 1)[0] if "/" in map_id else ""
        for p in maps[map_id].get("ports") or []:
            if p.get("f") in edges(map_id) or set(p.get("pf") or ()) & edges(up):
                out.add((p["x"], p["d"]))
    return out


def _check_sets(found: dict[str, Any], tree: nest.Tree, page: Path) -> None:
    assert found["errors"] == []
    text = page.read_text(encoding="utf-8")
    start = text.index('id="canvas-data">') + len('id="canvas-data">')
    data = json.loads(text[start : text.index("</script>", start)])
    want = _expected(tree)
    assert set(found["maps"]) == set(want)
    for map_id, layers in want.items():
        for lay, (edges, quiet) in layers.items():
            got = found["maps"][map_id][lay]
            assert got["flows"] == edges, (map_id, lay)
            assert got["quiet"] == quiet, (map_id, lay)
            assert got["alphas"] in ([], [0.32]), (map_id, lay, got["alphas"])
            assert got["drawnFlows"] == len(tree.get(map_id).model.flows), (map_id, lay)
            assert got["state"]["layer"] == lay and got["state"]["mode"] == "map"
            shown = {(x, d) for x, d in got["links"]}
            assert shown <= _ports_in_layer(data, got["chain"], lay), (map_id, lay, shown)


def test_the_layer_filter_of_the_self_map(self_page: Path) -> None:
    """Acceptance 1."""
    _check_sets(_drive("--sets", str(self_page)), _self_tree()[1], self_page)


def test_the_layer_filter_of_the_fixture(fixture_page: Path) -> None:
    """Acceptance 1."""
    _cfg, tree, _facts = _loaded(fixture_page.parent.parent.parent)
    found = _drive("--sets", str(fixture_page))
    _check_sets(found, tree, fixture_page)
    gateway = found["maps"]["Gateway"]
    assert gateway["all"]["links"]
    assert any(not got["links"] for got in gateway.values())


def _check_fade(found: dict[str, Any], marks: bool) -> None:
    """Check the values of each change. With `marks`, the map is drawn from its marks
    image: the cards have no values of their own, and the blend of the two marks images
    (`marks`, the count of frames with a blend) is the value of the change."""
    for motion, runs in found.items():
        assert runs["errors"] == [], motion
        for name in ("layer", "view", "viewBack", "back", "pan"):
            _check_run(motion, name, runs[name], marks)


def _check_run(motion: str, name: str, run: dict[str, Any], marks: bool) -> None:
    shown = run["marks"] if marks else run["frames"]
    if motion == "none":
        assert run["most"] <= 0.25 + 1e-9, (name, run)
        assert name == "pan" or (shown >= 5 and run["ms"] >= 160), (name, run)
    elif name != "pan":
        assert shown == 1 and run["frames"] <= 1, (motion, name, run)


def test_a_layer_change_and_a_view_change_fade(shape_page: Path) -> None:
    """Acceptance 2."""
    _check_fade(_drive("--fade", str(shape_page), "P0"), marks=False)


def test_the_marks_image_fades_to_the_new_view(grid_pages: dict[int, Path]) -> None:
    """Acceptance 2, with the marks image of a large map."""
    _check_fade(_drive("--fade", str(grid_pages[1500]), ""), marks=True)


@pytest.mark.parametrize("cards", [400, 1500])
def test_the_seam_calls_do_not_grow_with_the_cards(grid_pages: dict[int, Path], cards: int) -> None:
    """Acceptance 3."""
    found = _drive("--hooks", str(grid_pages[cards]))
    assert found["errors"] == []
    assert len(found["frames"]) >= 100
    for frame in found["frames"]:
        assert frame["hooks"] <= frame["cards"] + frame["flows"], frame


def test_the_camera_keys_do_not_operate_in_the_header(fixture_page: Path) -> None:
    """Acceptance 4."""
    found = _drive("--keys", str(fixture_page))
    assert found["errors"] == []
    assert len(found["controls"]) >= 4
    for control in found["controls"]:
        assert control["after"] == control["before"], control
    moves = found["moves"]
    assert all(m["layer"] == m["focus"] for m in moves), moves
    assert moves[0] == moves[2] == moves[3] != moves[1] and moves[4]["layer"] == "all", moves
    assert found["canvas"]["after"]["x"] != found["canvas"]["before"]["x"]


def test_the_header_is_accessible(fixture_page: Path) -> None:
    """Acceptance 5 (C4)."""
    found = _drive("--access", str(fixture_page))
    assert len(found["runs"]) == 4
    for run in found["runs"]:
        assert run["errors"] == [], run["errors"]
        assert len(run["controls"]) >= 2, run
        for c in run["controls"]:
            _check_control(c)
        runs_of = [o.split(":")[0] for o in run["order"]]
        compressed = [k for i, k in enumerate(runs_of) if i == 0 or runs_of[i - 1] != k]
        assert compressed == ["head", "canvas", "tree", "out"], run["order"]


def _check_control(c: dict[str, Any]) -> None:
    """A header control has a name, a visible focus outline and no axe-core violation."""
    assert c["name"], c
    focus = c["focus"]
    assert focus["visible"] and focus["style"] == "solid" and focus["width"] >= 2, c
    assert contrast(_hex(focus["color"]), _hex(focus["back"])) >= 3, c
    axe = c.get("axe")
    if axe is None:
        if os.environ.get("SYSTEMAP_BROWSER_TESTS") == "required":
            pytest.fail(f"axe-core {AXE_VERSION} for Node is necessary")
        return
    assert axe["version"] == AXE_VERSION and axe["violations"] == [], c


def _hex(rgb: str) -> str:
    """Give the hex color of a CSS color "rgb(r, g, b)"."""
    parts = rgb[rgb.index("(") + 1 : rgb.index(")")].split(",")
    return "#" + "".join(f"{round(float(p)):02x}" for p in parts[:3])


def test_the_header_on_a_phone(fixture_page: Path) -> None:
    """Acceptance 6 (C5)."""
    found = _drive("--phone", str(fixture_page))
    assert found["errors"] == []
    assert found["scrollWidth"] == 390 and found["scrollX"] == 0 and found["width"] == 390
    assert found["head"] == 56 and found["state"]["head"] == 56
    assert found["targets"], found
    for t in found["targets"]:
        assert t["w"] >= 44 and t["h"] >= 44, t
        assert t["x"] >= 0 and t["x"] + t["w"] <= 390, t
    path = found["layout"]["path"]
    assert path[1] >= 56 + 10
