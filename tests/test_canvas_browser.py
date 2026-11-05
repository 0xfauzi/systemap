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

Acceptance 6 also applies on a screen of 390 x 844 pixels.
"""

from __future__ import annotations

import functools
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
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


def drive(page: Path, *flags: str) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), str(page), "Gateway", "Auth", *flags],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr
    return dict(json.loads(proc.stdout))


@pytest.fixture(scope="module")
def canvas(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = _made(tmp_path_factory.mktemp("browser"), "[render]\ncanvas = true\n")
    return root / "docs" / "map" / "index.html"


@pytest.fixture(scope="module")
def driven(canvas: Path) -> dict[str, Any]:
    return drive(canvas)


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
