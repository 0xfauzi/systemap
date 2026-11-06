"""The canvas page in a browser: the camera, the hash and a portal (`page_canvas`).

The test drives the real canvas page of the fixture of tests/test_nest_join.py in the
Chromium of Playwright (tests/canvas_driver.js). The card Gateway opens a map, and the
card Auth of the top map is a neighbour of that map. The test skips when Node or the
Playwright package is not there, except when SYSTEMAP_BROWSER_TESTS is "required" (the
CI job canvas-browser).

Acceptance values:

1. The script runs under the CSP of the page: the page has no script error.
2. A double-click on Gateway goes into its map: the path of the canvas and the URL
   hash name the map Gateway.
3. The portal of Auth is at the screen edge in the map Gateway. A click on it moves the
   camera to Auth: the card Auth is then in the middle of the screen.
4. Esc goes out one level: the path is the top map and the hash is empty.
5. + zooms in, - zooms out, and F fits the current map.
6. A link with the hash #Gateway opens the canvas in the map Gateway.
7. A drag moves the camera with the pointer. The wheel zooms at the pointer: the point
   under the pointer stays in its place.
8. The page uses the theme tokens: the light scheme gives a light background.
9. The boundary flow from the portal of Auth has right angles and crosses no card: no
   segment goes into the box of a card of the map Gateway or of the top map. In two maps of
   the generated M11 tree (bench/jev/canvas_frames.py), at the fit and at 17 other camera
   positions near it, each boundary flow has right angles, stays on the screen, goes into
   no card that is not open, and ends at the edge of its portal. At the fit of each map,
   there is a boundary flow.
10. A portal does not cover a card of the open map. After the camera fit of a map, no card
    of that map is in the band of a portal at its screen edge. The test uses the map Gateway
    and two maps of the generated M11 tree, on a screen of 1440 x 900 pixels and on a
    screen of 390 x 844 pixels. Also, at the camera fit of each map, no portal covers a box
    of the maps on the screen (a card, a flow label plate or a text) by more than 0.5
    pixels. A box with an opacity below 0.05 and a box of the neighbour of the portal do not
    count. The test uses the 50 maps of the generated M11 tree with 14 columns of cards and
    with 4 columns of cards, on screens of 1440 x 900, 390 x 844 and 844 x 390 pixels. With 4
    columns, the bottom and the right rows of the portals are on cards and flow labels of
    the map above, when a portal does not move off them.

11. A boundary flow fades in and out with the camera. It does not appear or go at one
    time. The M11 tree, on a screen of 1440 x 900 pixels without reduced motion, has four
    slow camera moves of 200 frames each: from the top fit into the map P0/A0, from P0/A0
    out to the top fit, from the map P0 into P0/A0, and a zoom from 0.5 to 3 times the fit
    of P0/A0. On that screen and on a screen of 390 x 844 pixels, five more moves zoom
    out: from the fit of P0, of P0/A0 and of P0/A0/B0 to the fit of the map above, and a
    zoom from 3 to 0.5 times the fit of P0 and of P0/A0. The alpha of each drawn path of a
    boundary flow changes by 0.25 or less between two frames. A path that is not drawn has
    the alpha 0. A boundary flow is under the cards: in each frame, no pixel of the layer
    of the lines is in a card that is not open, 2 pixels or more in from the edge of its
    box. The moves on each screen draw boundary flows in 30 frames or more.
12. The camera fit of a map zooms to that map. After the fit, the frame of the map covers
    at least 80 percent of the free width: the screen width less a band at each side as
    wide as the widest portal at that side. The frame is in the free width. The test uses
    two maps of the generated M11 tree, on a screen of 390 x 844 pixels and on a screen of
    1440 x 900 pixels.
13. The two speed changes of a moving frame fade in time. They do not appear or go at one
    time. The generated map of 400 cards, on a screen of 1440 x 900 pixels without reduced
    motion, has three camera moves, and a stop of 700 ms after each move: a dive into the
    middle card, a pan, and the dive back out. In each frame, the page gives the alpha of
    each layer: the text that MOVE_TEXT hides, the image layer of the map, and the part of
    each image in the result. Each alpha changes by 0.25 or less between two frames. A layer
    that a frame does not have has the alpha 0. The dive in and the pan show the images at
    the full alpha, and in 3 or more frames an image layer between 0 and 1. After each
    stop, 3 or more frames still fade, and the last frame has the full resolution, the
    full text and no image.
14. A portal fades in and out by time. It does not appear or go at one time, also when
    the chain changes. The M11 tree, on a screen of 1440 x 900 pixels and on a screen of
    390 x 844 pixels without reduced motion, has two slow camera moves of 300 frames
    each: a dive into the map P0/A0 at the middle of its fit, from the scale of the top
    fit to the scale of the fit of P0/A0, and the zoom out back. In each move, the chain
    changes, and the alpha of each portal changes by 0.25 or less between two frames. A
    portal that is not drawn has the alpha 0. The middle of a portal moves by 16 pixels
    or less between two frames.
15. The camera fit of each map uses the screen. The test uses the fit of the top map and of
    one map on each level below it, to level 3, of the generated M11 tree, on screens of
    390 x 844, 844 x 390 and 1440 x 900 pixels, and after the screen of 390 x 844 pixels
    turns to 844 x 390 pixels. At each fit, the frame of the open map is in the free box:
    the screen less the bands of the portals, the path and the help line. The frame fills
    at least 90 percent of the free width or of the free height. The screen edge cuts no
    card of the open map. The plates of the path and the help line, and the portals, do not
    cover each other. The help line has one line in the screen width.
16. At rest, each portal is fully shown or fully gone, and no portal covers a different
    portal. The generated M11 tree, on screens of 390 x 844, 844 x 390 and 1440 x 900
    pixels without reduced motion, opens with the hash #P0/A0. Then the camera goes to the
    fit of the top map and of one map on each level below it, to level 3. 2.5 s after the
    load, and 1 s after each fit, the alpha of each portal is 0 or 1, and no two portal
    boxes with an alpha above 0 overlap.
17. At the fit of each map, the names of the cards are clear. The generated M11 tree, on a
    screen of 1440 x 900 pixels without reduced motion, opens at the top map. Then the
    camera goes to the fit of each of the 50 maps. 1 s after each fit, the page draws the
    frame again. Each card of the open map has its name in its box, at 8.5 px or more and
    with the alpha 1. The name can be cut with three dots. The box of a name does not
    overlap the box of a different text by more than 0.5 pixels.
18. An input in a flight stops the flight or changes its end. On a screen of 1440 x 900
    pixels without reduced motion, F starts a flight to the fit of the top map. An arrow key
    in that flight stops the flight: 1 s later, the camera is not at the fit. A change of
    the screen size to 900 x 1440 pixels in that flight changes its end: 2 s later, the
    camera is at the fit of the top map on the new screen.
19. A gesture with two fingers is not a tap. A tap with two fingers on the card Gateway,
    with no move, does not go into the map Gateway. After a pinch, the finger that stays
    down moves the map: a move of 100 pixels moves the camera by 100 pixels.
20. A card does not open a map that has no area. When the map Gateway has the size 0 x 0,
    the hash #Gateway and a double-click on the card Gateway give a camera with finite
    values. The page has no script error.
21. The fade of the count of text columns of a card starts again when the frame before did
    not draw the card. The test runs the function `colFade` of the page script in Node.

Acceptance 6 also applies on a screen of 390 x 844 pixels.
"""

from __future__ import annotations

import functools
import itertools
import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_canvas_frames import _bench
from test_canvas_page import _made

from systemap import page_canvas_text

ROOT = Path(__file__).resolve().parent
DRIVER = ROOT / "canvas_driver.js"


@functools.cache
def _started() -> tuple[str | None, str]:
    """Give the Node command if Playwright can start Chromium. The probe runs one time.

    When the probe fails, give None and the error text of the probe."""
    node = shutil.which("node")
    if node is None:
        return None, "The node command is not on the PATH."
    probe = subprocess.run(
        [node, str(DRIVER), "--probe"], capture_output=True, text=True, timeout=120
    )
    if probe.returncode != 0:
        return None, (probe.stderr or probe.stdout).strip()
    return node, ""


def browser() -> str:
    """Give the Node command, or skip the test when Playwright cannot start Chromium."""
    node, why = _started()
    if node is None:
        if os.environ.get("SYSTEMAP_BROWSER_TESTS") == "required":
            pytest.fail("Node with the Playwright package and Chromium is necessary. " + why)
        pytest.skip("the canvas tests need Node with the Playwright package and Chromium")
    return node


def drive(page: Path, *flags: str, ids: tuple[str, str] = ("Gateway", "Auth")) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), str(page), *ids, *flags],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr
    return dict(json.loads(proc.stdout))


@functools.cache
def _fitted(tree: Path, flags: tuple[str, ...]) -> dict[str, Any]:
    """The `--fits` result for the maps P0 and P0/A0. Each set of flags runs one time."""
    return drive(tree, *flags, ids=("P0", "P0/A0"))


@pytest.fixture(scope="module")
def canvas(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = _made(tmp_path_factory.mktemp("browser"), "[render]\ncanvas = true\n")
    return root / "docs" / "map" / "index.html"


@pytest.fixture(scope="module")
def driven(canvas: Path) -> dict[str, Any]:
    return drive(canvas)


@pytest.fixture(scope="module")
def tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The canvas page of the generated M11 tree."""
    return _tree_page(tmp_path_factory, "tree")


def _tree_page(factory: pytest.TempPathFactory, name: str, cols: int = 14) -> Path:
    """Write the canvas page of the generated M11 tree with `cols` columns of cards."""
    bench = _bench()
    return Path(bench.write_page(bench.nested_tree(cols), factory.mktemp(name) / "tree.html"))


def test_the_script_runs_under_the_policy(driven: dict[str, Any]) -> None:
    """Acceptance 1."""
    assert driven["errors"] == []
    assert driven["start"]["chain"] == []
    assert driven["start"]["label"] == "System map: join. Level 0."


def test_a_double_click_goes_into_the_map(driven: dict[str, Any]) -> None:
    """Acceptance 2."""
    assert driven["inside"]["chain"] == ["Gateway"]
    assert driven["inside"]["hash"] == "#Gateway"
    assert driven["inside"]["label"] == "System map: join / Gateway. Level 1."


def _into(segment: tuple[list[float], list[float]], box: list[float]) -> bool:
    """Tell if a segment with a right angle goes into a box, by more than 1 pixel."""
    (x0, y0), (x1, y1) = segment
    bx, by, bw, bh = box
    return (
        min(x0, x1) < bx + bw - 1
        and max(x0, x1) > bx + 1
        and min(y0, y1) < by + bh - 1
        and max(y0, y1) > by + 1
    )


def test_a_boundary_flow_crosses_no_card(driven: dict[str, Any]) -> None:
    """Acceptance 9."""
    links = [link for link in driven["inside"]["links"] if link["id"] == "Auth"]
    assert links
    for link in links:
        points = link["points"]
        segments = list(itertools.pairwise(points))
        assert len(segments) >= 2
        for (x0, y0), (x1, y1) in segments:
            assert abs(x0 - x1) < 0.5 or abs(y0 - y1) < 0.5, (x0, y0, x1, y1)
        for card in driven["inside"]["boxes"]:
            crossed = [s for s in segments if _into(s, card["b"])]
            assert not crossed, (card["id"], crossed)


def test_the_boundary_flows_near_the_fit(tree: Path) -> None:
    """Acceptance 9 in the M11 tree."""
    links = drive(tree, "--links", ids=("P0", "P0/A0"))
    assert links["frames"] == 36
    assert links["problems"] == []
    assert links["atFit"]["P0"] >= 1 and links["atFit"]["P0/A0"] >= 1


def test_a_portal_click_moves_the_camera_to_the_neighbour(driven: dict[str, Any]) -> None:
    """Acceptance 3."""
    assert any(h["kind"] == "portal" and h["id"] == "Auth" for h in driven["inside"]["hits"])
    x, y, w, h = driven["portalCard"]
    assert abs(x + w / 2 - 640) < 2 and abs(y + h / 2 - 400 - 20) < 2
    assert driven["portal"]["chain"] == []


def test_escape_goes_out_one_level(driven: dict[str, Any]) -> None:
    """Acceptance 4."""
    assert driven["escaped"]["chain"] == []
    assert driven["escaped"]["hash"] == ""


def test_the_zoom_keys_and_the_fit_key(driven: dict[str, Any]) -> None:
    """Acceptance 5."""
    assert driven["zoomIn"] == pytest.approx(1.6)
    assert driven["zoomOut"] == pytest.approx(1 / 1.6)
    assert driven["fitted"] == pytest.approx(1)


def test_a_link_with_the_hash_opens_the_map(driven: dict[str, Any]) -> None:
    """Acceptance 6."""
    assert driven["linked"]["chain"] == ["Gateway"]
    assert driven["linked"]["hash"] == "#Gateway"


def test_the_drag_and_the_wheel(driven: dict[str, Any]) -> None:
    """Acceptance 7."""
    assert driven["dragged"] == pytest.approx([100, 20], abs=0.01)
    assert driven["wheel"]["zoom"] > 1.3
    assert driven["wheel"]["moved"] < 0.5


def test_a_link_with_the_hash_opens_the_map_on_a_phone(canvas: Path) -> None:
    """Acceptance 6 on a screen of 390 x 844 pixels: the map is open at its fit."""
    linked = drive(canvas, "--phone")["linked"]
    assert linked["chain"] == ["Gateway"]
    assert linked["hash"] == "#Gateway"


def test_the_light_scheme(canvas: Path, driven: dict[str, Any]) -> None:
    """Acceptance 8."""
    light = drive(canvas, "--light")
    assert light["errors"] == []
    dark, paper = (_luma(d["theme"]) for d in (driven, light))
    assert dark < 60 < paper


def _luma(css: str) -> float:
    r, g, b = (float(v) for v in css[css.index("(") + 1 : css.index(")")].split(",")[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


@pytest.mark.parametrize(("flags", "moves"), [(("--fade",), 9), (("--fade", "--phone"), 5)])
def test_a_boundary_flow_fades_with_the_camera(
    tree: Path, flags: tuple[str, ...], moves: int
) -> None:
    """Acceptance 11."""
    dives = drive(tree, *flags, ids=("P0/A0", "P0"))["dives"]
    assert [d["frames"] for d in dives] == [200] * moves
    assert sum(d["drawn"] for d in dives) >= 30
    assert sum(d["checked"] for d in dives) > 0
    for dive in dives:
        assert dive["problems"] == [], dive
        assert dive["worst"] <= 0.25, dive


@pytest.fixture(scope="module")
def narrow(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The canvas page of the generated M11 tree with 4 columns of cards in each map."""
    return _tree_page(tmp_path_factory, "narrow", 4)


@pytest.mark.parametrize("flags", [("--fits",), ("--fits", "--phone")])
def test_a_portal_does_not_cover_a_card_of_the_open_map(
    driven: dict[str, Any], tree: Path, flags: tuple[str, ...]
) -> None:
    """Acceptance 10."""
    assert driven["inside"]["covered"] == []
    fitted = _fitted(tree, flags)
    assert fitted["P0"]["chain"] == ["P0"] and fitted["P0"]["portals"] == 2
    assert fitted["P0/A0"]["chain"] == ["P0", "P0/A0"] and fitted["P0/A0"]["portals"] == 4
    assert fitted["P0"]["covered"] == []
    assert fitted["P0/A0"]["covered"] == []


def test_a_portal_keeps_off_the_boxes_of_the_maps(tree: Path, narrow: Path) -> None:
    """Acceptance 10."""
    for page in (tree, narrow):
        clear = drive(page, "--clear", ids=("", ""))
        assert clear["fits"] == 150 and clear["portals"] >= 300, clear["portals"]
        assert clear["problems"] == []


@pytest.mark.parametrize("flags", [("--fits", "--phone"), ("--fits",)])
def test_the_fit_zooms_to_the_open_map(tree: Path, flags: tuple[str, ...]) -> None:
    """Acceptance 12."""
    fitted = _fitted(tree, flags)
    for fit in (fitted["P0"], fitted["P0/A0"]):
        x, _, w, _ = fit["frame"]
        assert w >= 0.8 * fit["free"], fit
        assert fit["band"] - 1 <= x and x + w <= fit["band"] + fit["free"] + 1, fit


def test_the_speed_changes_fade_in_time(tmp_path: Path) -> None:
    """Acceptance 13."""
    bench = _bench()
    page = bench.write_page(bench.grid_map(400), tmp_path / "g400.html")
    moves = {m["kind"]: m for m in drive(page, "--layers")["moves"]}
    assert list(moves) == ["dive in", "pan", "dive out"]
    for move in moves.values():
        assert move["worst"] <= 0.25, move
        assert move["hideMax"] == 1, move
        assert move["stillFading"] >= 3, move
        assert move["end"] == {"sharp": True, "fine": True, "hide": 0, "images": 0}, move
    for kind in ("dive in", "pan"):
        assert moves[kind]["full"] >= 1, moves[kind]
        assert moves[kind]["fading"] >= 3, moves[kind]


@pytest.mark.parametrize("flags", [("--portals",), ("--portals", "--phone")])
def test_a_portal_fades_with_the_camera(tree: Path, flags: tuple[str, ...]) -> None:
    """Acceptance 14."""
    moves = drive(tree, *flags, ids=("P0/A0", "P0"))["moves"]
    assert [m["frames"] for m in moves] == [300, 300]
    for move in moves:
        assert move["changes"] >= 1 and move["most"] >= 2, move
        assert move["worst"] <= 0.25, move
        assert move["jump"] <= 16, move


def test_the_fit_uses_the_screen(tree: Path) -> None:
    """Acceptance 15."""
    fits = drive(tree, "--layout", ids=("", ""))["fits"]
    assert [(f["W"], f["H"], f["id"]) for f in fits][:5] == [
        (390, 844, ""),
        (390, 844, "P0"),
        (390, 844, "P0/A0"),
        (390, 844, "P0/A0/B0"),
        (844, 390, "P0/A0/B0"),
    ]
    assert len(fits) == 13
    for fit in fits:
        width, height, g = fit["W"], fit["H"], fit["gutters"]
        x, y, w, h = fit["frame"]
        free_w, free_h = width - 2 * g["x"], height - g["top"] - g["bottom"]
        assert g["x"] - 1 <= x and x + w <= width - g["x"] + 1, fit
        assert g["top"] - 1 <= y and y + h <= height - g["bottom"] + 1, fit
        assert w >= 0.9 * free_w or h >= 0.9 * free_h, fit
        assert fit["cut"] == [], fit
        assert fit["covers"] == [], fit
        assert fit["help"][0] + fit["help"][2] <= width, fit


def test_a_portal_at_rest_is_fully_shown_or_gone(tree: Path) -> None:
    """Acceptance 16."""
    fits = drive(tree, "--rest", ids=("P0/A0", ""))["fits"]
    assert [(f["W"], f["H"], f["at"]) for f in fits][:5] == [
        (390, 844, "#P0/A0"),
        (390, 844, ""),
        (390, 844, "P0"),
        (390, 844, "P0/A0"),
        (390, 844, "P0/A0/B0"),
    ]
    assert len(fits) == 15
    assert sum(f["portals"] for f in fits) > 0
    for fit in fits:
        assert fit["problems"] == [], fit


def test_the_names_are_clear_at_the_fit(tree: Path) -> None:
    """Acceptance 17."""
    maps = drive(tree, "--names", ids=("", ""))["maps"]
    assert len(maps) == 50
    assert sum(m["cards"] for m in maps) == 2000
    for fit in maps:
        assert fit["problems"] == [], fit


def test_an_input_in_a_flight(canvas: Path) -> None:
    """Acceptance 18 and 19."""
    found = drive(canvas, "--input")
    arrow, resize = found["arrow"], found["resize"]
    assert abs(arrow["camera"]["k"] / arrow["fit"]["k"] - 1) > 0.01, arrow
    for key in ("x", "y", "k"):
        assert resize["camera"][key] == pytest.approx(resize["fit"][key], rel=1e-3, abs=0.5)
    assert found["tap"]["chain"] == [], found["tap"]
    before, after = found["pinch"]["before"], found["pinch"]["after"]
    assert (after["x"] - before["x"]) * before["k"] == pytest.approx(100, abs=1), found["pinch"]


def test_a_card_does_not_open_a_map_with_no_area(canvas: Path, tmp_path: Path) -> None:
    """Acceptance 20."""
    html = canvas.read_text(encoding="utf-8")
    found = re.search(r'id="canvas-data">(.*?)</script>', html, re.S)
    assert found is not None
    data = json.loads(found.group(1))
    for m in data["maps"]:
        if m["id"] == "Gateway":
            m["size"] = [0, 0]
    page = _bench().write_page(data, tmp_path / "empty.html")
    out = drive(page, "--empty")
    assert out["errors"] == []
    for camera in (out["linked"]["camera"], out["entered"]["camera"]):
        assert all(isinstance(v, float | int) and math.isfinite(v) for v in camera.values())


COL_FADE = """
var PAGE_CTX = {}, STILL_CTX = {}, ctx = PAGE_CTX, drawn = 0, SPEED_STEP = 0.2;
function toward(v, to, step) { return Math.min(to, v + step); }
%s
var c = {}, out = [];
for (drawn = 0; drawn < 10; drawn++) colFade(c, 'd', 6);
drawn = 50;
out.push(Object.assign({}, colFade(c, 'd', 14)));
drawn = 51;
out.push(Object.assign({}, colFade(c, 'd', 20)));
process.stdout.write(JSON.stringify(out));
"""


def test_the_column_fade_starts_again_after_a_gap() -> None:
    """Acceptance 21."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("the test needs Node")
    found = re.search(r"function colFade\(.*?\n\}\n", page_canvas_text.TEXT, re.S)
    assert found is not None
    proc = subprocess.run(
        [node, "-e", COL_FADE % found.group(0)], capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, proc.stderr
    back, changed = json.loads(proc.stdout)
    assert (back["k"], back["from"], back["f"]) == (14, 14, 1)
    assert (changed["k"], changed["from"], changed["f"]) == (20, 14, 0.2)
