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
    screen of 390 x 844 pixels.

11. A boundary flow fades in and out with the camera. It does not appear or go at one
    time. The M11 tree, on a screen of 1440 x 900 pixels without reduced motion, has four
    slow camera moves of 200 frames each: from the top fit into the map P0/A0, from P0/A0
    out to the top fit, from the map P0 into P0/A0, and a zoom from 0.5 to 3 times the fit
    of P0/A0. The alpha of each drawn path of a boundary flow changes by 0.25 or less
    between two frames. A path that is not drawn has the alpha 0. No drawn path goes into
    a card that is not open. The moves draw boundary flows in 30 frames or more.
12. The camera fit of a map zooms to that map. After the fit, the frame of the map covers
    at least 80 percent of the free width: the screen width less a band at each side as
    wide as the widest portal at that side. The frame is in the free width. The test uses
    two maps of the generated M11 tree, on a screen of 390 x 844 pixels and on a screen of
    1440 x 900 pixels.

Acceptance 6 also applies on a screen of 390 x 844 pixels.
"""

from __future__ import annotations

import functools
import itertools
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_canvas_frames import _bench
from test_canvas_page import _made

ROOT = Path(__file__).resolve().parent
DRIVER = ROOT / "canvas_driver.js"


@functools.cache
def _started() -> str | None:
    """Give the Node command if Playwright can start Chromium. The probe runs one time."""
    node = shutil.which("node")
    if node is None:
        return None
    probe = subprocess.run([node, str(DRIVER), "--probe"], capture_output=True, timeout=120)
    return node if probe.returncode == 0 else None


def browser() -> str:
    """Give the Node command, or skip the test when Playwright cannot start Chromium."""
    node = _started()
    if node is None:
        if os.environ.get("SYSTEMAP_BROWSER_TESTS") == "required":
            pytest.fail("Node with the Playwright package and Chromium is necessary.")
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
    bench = _bench()
    return Path(
        bench.write_page(bench.nested_tree(), tmp_path_factory.mktemp("tree") / "tree.html")
    )


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


def test_a_boundary_flow_fades_with_the_camera(tree: Path) -> None:
    """Acceptance 11."""
    dives = drive(tree, "--fade", ids=("P0/A0", "P0"))["dives"]
    assert [d["frames"] for d in dives] == [200, 200, 200, 200]
    assert sum(d["drawn"] for d in dives) >= 30
    for dive in dives:
        assert dive["problems"] == [], dive
        assert dive["worst"] <= 0.25, dive


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


@pytest.mark.parametrize("flags", [("--fits", "--phone"), ("--fits",)])
def test_the_fit_zooms_to_the_open_map(tree: Path, flags: tuple[str, ...]) -> None:
    """Acceptance 12."""
    fitted = _fitted(tree, flags)
    for fit in (fitted["P0"], fitted["P0/A0"]):
        x, _, w, _ = fit["frame"]
        assert w >= 0.8 * fit["free"], fit
        assert fit["band"] - 1 <= x and x + w <= fit["band"] + fit["free"] + 1, fit
