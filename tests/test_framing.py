"""The framing on click, driven under Node with a stub viewport.

A selection frames what it lights, and only that: the card, the edges of
it the reading shows (every edge on All and on Structure, which has no
edges of its own), and their other ends; the framed rectangle is centred
in the part of the map the reader can see, the map's box clipped to the
window less the drawer's column; a lit set larger than that area at the
minimum zoom is fitted whole, never cropped; and a resize with the focus
held frames it again for the new window.

`tests/page_driver.js --scenario framing` selects several cards on every
reading and reports what was lit, what was framed, and where the view
landed; the geometry is done again here from the stub's numbers (the
viewBox, the window, the drawer's box), so the script's own account of
the visible area is checked, not trusted.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import Sample
from test_keyboard import DRIVER, SELF_MAP, needs_node, sample_page

# The script's constants: the daylight left beside the drawer, the padding
# round a framed set, the zoom cap and floor.
GAP = 12
FRAME_PAD = 28
ZCAP = 1.4
ZMIN = 0.4


def drive(html: Path, viewport: str) -> dict[str, Any]:
    args = [
        shutil.which("node") or "node",
        str(DRIVER),
        str(html),
        "--scenario",
        "framing",
        "--viewport",
        viewport,
    ]
    proc = subprocess.run(args, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    report: dict[str, Any] = json.loads(proc.stdout)
    return report


def expected_area(report: dict[str, Any], case: dict[str, Any]) -> tuple[float, ...]:
    """The visible area from the stub's numbers alone: the figure's box
    clipped to the window, less the drawer's column and the gap beside it."""
    vb = report["viewBox"]
    vw, vh = case["viewport"]["w"], case["viewport"]["h"]
    x0, y0 = max(vb["x"], 0), max(vb["y"], 0)
    x1, y1 = min(vb["x"] + vb["w"], vw), min(vb["y"] + vb["h"], vh)
    if not case["drawerHidden"]:
        d = case["drawer"]
        if case["dock"] == "left":
            x0 = max(x0, d["right"] + GAP)
        else:
            x1 = min(x1, d["left"] - GAP)
    return x0, y0, x1 - x0, y1 - y0


def expected_lit(report: dict[str, Any], case: dict[str, Any]) -> tuple[set[str], set[int]]:
    """What the readings table says a focus lights on this reading."""
    cid, reading = case["id"], case["reading"]
    edges: list[int] = report["detailEdges"][cid]
    shown = [] if reading == "all" else report["readings"][reading]["edges"]
    lit_edges = [i for i in edges if i in shown] if shown else edges
    ids = {cid}
    for i in lit_edges:
        ids.add(report["edges"][i]["from"])
        ids.add(report["edges"][i]["to"])
    return ids, set(lit_edges)


def inside(box: dict[str, float], rect: dict[str, float], slack: float = 0.05) -> bool:
    return (
        box["x"] >= rect["x"] - slack
        and box["y"] >= rect["y"] - slack
        and box["x"] + box["w"] <= rect["x"] + rect["w"] + slack
        and box["y"] + box["h"] <= rect["y"] + rect["h"] + slack
    )


def check_case(report: dict[str, Any], case: dict[str, Any]) -> None:
    where = f"{case['reading']}: {case['id']}"
    frame = case["frame"]
    assert frame is not None, where
    rect, area, view = frame["rect"], frame["area"], case["view"]
    assert case["drawerHidden"] is False, where
    # The visible area the script framed in is the one the stub describes.
    x, y, w, h = expected_area(report, case)
    assert (area["x"], area["y"], area["w"], area["h"]) == pytest.approx((x, y, w, h)), where
    assert case["drawer"]["width"] == report["drawerWidth"], where
    # The framed rectangle's centre lands on the visible area's centre.
    cx = view["k"] * (rect["x"] + rect["w"] / 2) + view["tx"]
    cy = view["k"] * (rect["y"] + rect["h"] / 2) + view["ty"]
    assert abs(cx - (area["x"] + area["w"] / 2)) <= 1, where
    assert abs(cy - (area["y"] + area["h"] / 2)) <= 1, where
    # What is lit is what the readings table says, and it is all inside the rect.
    ids, edges = expected_lit(report, case)
    assert {n["id"] for n in case["lit"]} == ids, where
    assert {e["edge"] for e in case["litEdges"]} == edges, where
    for n in case["lit"]:
        assert inside(n["box"], rect), f"{where}: card {n['id']} outside the frame"
    for e in case["litEdges"]:
        b = e["box"]
        assert inside({"x": b["x"], "y": b["y"], "w": b["width"], "h": b["height"]}, rect), (
            f"{where}: edge {e['edge']} outside the frame"
        )
    # Fitted whole, never cropped, and never past the zoom cap.
    assert view["k"] <= ZCAP + 1e-6, where
    assert view["k"] * rect["w"] <= area["w"] + 0.05, where
    assert view["k"] * rect["h"] <= area["h"] + 0.05, where


def check(report: dict[str, Any]) -> None:
    cases = report["cases"]
    assert len(cases) == (len(report["readings"]) + 1) * len(report["cards"])
    assert len(report["cards"]) >= 3
    assert {c["reading"] for c in cases} == set(report["readings"]) | {"all"}
    for case in cases:
        check_case(report, case)
    # Some reading lights fewer edges than All does for the same card, so
    # the filter is exercised, not merely computed.
    assert any(len(expected_lit(report, c)[1]) < len(report["detailEdges"][c["id"]]) for c in cases)
    before, after = report["beforeResize"], report["afterResize"]
    assert after["viewport"] != before["viewport"]
    check_case(report, after)
    assert after["frame"]["area"] != before["frame"]["area"], "the resize framed again"


@needs_node
def test_sample_page_frames_the_lit_set_beside_the_drawer(sample: Sample, tmp_path: Path) -> None:
    check(drive(sample_page(sample, tmp_path), "1600x900"))


@needs_node
def test_self_map_page_frames_in_the_part_on_screen() -> None:
    assert SELF_MAP.is_file(), "the committed page; run systemap refresh"
    # A window shorter than the map: the visible area is clipped at the bottom.
    report = drive(SELF_MAP, "1600x700")
    check(report)
    vb = report["viewBox"]
    assert vb["y"] + vb["h"] > 700, "the map runs below the window"
    assert all(c["frame"]["area"]["h"] == 700 - max(vb["y"], 0) for c in report["cases"])


@needs_node
def test_a_lit_set_larger_than_the_area_is_fitted_whole() -> None:
    assert SELF_MAP.is_file(), "the committed page; run systemap refresh"
    # A window under half the map: a card with many neighbours lights a
    # set the area cannot hold at ZMIN, and it is fitted whole.
    report = drive(SELF_MAP, "700x300")
    check(report)
    assert any(c["view"]["k"] < ZMIN for c in report["cases"]), "some frame went under ZMIN"
