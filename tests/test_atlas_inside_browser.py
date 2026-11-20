"""The signs of a nested map on the atlas page, in a browser (docs/design/atlas.md, stage 11).

The test drives the atlas page of the map of this repository (the nested map Page) and of the
generated M11 tree (bench/jev/canvas_frames.py, three depths: P0, P0/Q0 and P0/Q0/Deep) in the
Chromium of Playwright (tests/atlas_inside.js). The test skips when Node or the Playwright
package is not there, except when SYSTEMAP_BROWSER_TESTS is "required". Then it fails. The
test of axe-core skips when axe-core is not on NODE_PATH, with the same exception.

Acceptance values, written by the coordinator before the work on 2026-11-19, with no change:

A1. In each nested map, at 1440 x 900 and 390 x 844, light and dark: the bar is fully in the
    viewport at the fit, its text is 14 px or more on the screen, and its text contrast is
    4.5:1 or more.
A2. The back button works with a mouse click, with Enter when it has the focus, and with Esc.
    Each goes to the parent map with the card of the nested map selected.
A3. The top map has no bar, no locator and no inside background.
A4. The enter movement and the leave movement each take 250 ms to 450 ms, measured in the
    browser, and the first frame of the enter movement shows the nested map at the box of its
    card (within 8 px). With prefers-reduced-motion: reduce, each takes 0 ms (one frame).
A5. At the fit, at 1440 x 900 and 390 x 844, the locator covers no card and no label box of
    the nested map.
A6. The background outside the frame of a nested map differs from the top map background in
    each scheme (a different color value, and a measurable difference in a screenshot).
A7. The title of the frame is 18 px or more on the screen at the fit at 1440 x 900.
A8. axe-core gives no violation on a nested map, light and dark.

How the test reads these values (written before the first run of this test):

- "At the fit" is the camera after a load with the hash of the map (`fitBox` of its frame).
- A1: each element of the bar with its own text gives its computed font size and the contrast
  of its color on the first ground under it that is not transparent.
- A2: also a click on the locator (sign 3: a click on it goes out).
- A4: a movement is the time from the call of the movement to its last frame (`moves` of
  `systemapCanvas.inside`). The nested map has the shape of its own frame, and the box of its
  card has the shape of the card. Thus "at the box of its card" is: in the first frame of the
  enter movement, the frame of the nested map is in the box of the card with a margin of 8 px,
  its middle is 8 px or less from the middle of the card, and its width or its height is the
  width or the height of the card, within 8 px.
- A5: the locator also shows (it is not absent) in each nested map at 1440 x 900.
- A6: "a measurable difference in a screenshot" is the mean color of a box of 16 x 16 px of the
  canvas at the bottom middle of the screen: the mean of one channel differs by 3 or more
  between the top map and the nested map.
- A7: the title text of the frame of the current map in the frame log (`drawn`).

Acceptance values of the repair of the zoomed-in view, written by the coordinator before the
work on 2026-11-20, with no change. Probes of the drivers ran before this text, but the values
below do not come from them:

Z1. The "on <map>" line of a neighbour card: on #Page at the fit at 1440 x 900, the text of the
    line is 10 CSS px or more, its contrast against the card ground is 4.5:1 or more in light
    and dark, and it stays inside its card box. At each zoom where the card name draws, the
    line is 0.7 times the size of the card name or more. The same holds at the three depths
    of the M11 tree.
Z2. When the layer uses fewer components (parts) than the map has, the headline says "N of T
    components" ("N of T parts" in a nested map). When it uses all, it says "T components".
    T in the headline of a nested map is the same number as in the "See its T parts" button
    and in the reading-line hint of its card. The same rule for actors and neighbours. Tested
    on Page and on the top map (tests/test_atlas_browser.py, acceptance 24 and 27).
Z3. Three Esc presses 80 ms apart from #P0/Q0/Deep end at the top map with P0 selected. Two
    presses end in P0 with Q0 selected. The same for clicks on the Back button. No frame
    jumps: between two frames, the camera moves less than the largest step of a normal leave
    movement plus 8 px.
Z4. a. Reduced motion: the camera of each frame changes exactly one time for an enter and for
       a leave.
    b. Each name in the path at depth 2 or more goes to that map: from #P0/Q0/Deep, a click on
       "P0" gives the current map P0 with Q0 selected, and a click on the top name gives the
       top map with P0 selected, no bar and no locator.
    c. The last frame of the leave movement shows the frame of the nested map at the box of
       its card within 8 px.
    d. Sign 5 ("on <map>") at the M11 depths and at 390 x 844.
Z5. In each view that shows a nested map, the bar (with Back and Esc) shows, and the ground is
    the inside ground. In each view of the top map, neither shows. Each view is tested.

How the test reads these values (written before the first run of these tests):

- Z1: the mark `up` of the frame log gives the size of the line and of the name, the box of
  the line, the color of the line, the ground of the card and the alpha. The contrast is
  that of the color on the ground. "Each zoom" is the camera at the fit times 0.35, 0.5, 0.7,
  1, 1.4, 2 and 3 (`--zooms`): where the name draws, the line draws, in its card box.
- Z3: the camera step between two frames is the largest distance on the screen that a corner
  of the viewport moves. The normal leave movements are one Esc in P0/Q0/Deep, in P0/Q0 and in
  P0, in the same run of the driver.
- Z4d: at 390 x 844 the size of 10 px does not apply (Z1 gives it at 1440 x 900). The line
  shows for each neighbour, in its card box, with a contrast of 4.5:1 or more.
- Z5: a view shows a nested map when its map (`viewMap`) is a nested map: the camera map in
  the Map view, the map of the sequence, of the machine or of the card in the middle, and the
  top map in the History view. The views come from the fixture of tests/canvas_sequenced.py
  with a state machine in each map (the Map view, the Sequences view in its two forms and the
  States view on the nested map Gateway), and from the map of this repository (the Focus view
  on Page, and the History view). The bar has "Back to" and "Esc", and it does not cover the
  headline, a list or a board. The ground of the canvas is `--inside`, and so is the
  background of the page where the canvas does not show. A click on Back opens the Map view
  of the map above with the card of the nested map selected.
- H1 (written before the repair on 2026-11-20): after a change of location.hash to #Page in
  each view of the top map, the page shows the Map view of Page with the bar.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from test_canvas_access import no_axe
from test_canvas_browser import browser

from systemap import atlas_data, atlas_page, canvas_page, config, facts_file, nest
from systemap.cli import main

ROOT = Path(__file__).resolve().parent
DRIVER = ROOT / "atlas_inside.js"
REPO = ROOT.parent
BENCH = REPO / "bench" / "jev"
M11_PATH = "P0,P0/Q0,P0/Q0/Deep"


def _drive(*args: str) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), *args], capture_output=True, text=True, timeout=900
    )
    assert proc.returncode == 0, proc.stderr
    out = dict(json.loads(proc.stdout))
    assert out.get("errors", []) == [], out.get("errors")
    return out


@pytest.fixture(scope="module")
def self_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    cfg = config.load(REPO)
    tree = nest.load(cfg)
    data = atlas_data.build(cfg, tree, facts_file.read_facts(cfg.facts_path, cfg.root))
    out = tmp_path_factory.mktemp("inside") / "self.html"
    out.write_text(atlas_page.build(canvas_page.tree_theme(cfg, tree), data), encoding="utf-8")
    return out


@pytest.fixture(scope="module")
def m11_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    browser()
    sys.path.insert(0, str(BENCH))
    import canvas_frames  # noqa: PLC0415  (a script in bench/jev)

    data = canvas_frames.m11_tree()
    out = tmp_path_factory.mktemp("inside") / "m11.html"
    out.write_text(atlas_page.build(nest.load(config.load(REPO)).top.theme, data), encoding="utf-8")
    return out


@pytest.fixture(scope="module")
def signs(self_page: Path, m11_page: Path) -> list[dict[str, Any]]:
    out = []
    for name, page, maps in (("self", self_page, "Page"), ("m11", m11_page, M11_PATH)):
        out += [{**r, "page": name} for r in _drive("--signs", str(page), maps)["runs"]]
    return out


def _nested(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in runs if r["id"]]


def _over(a: list[float], b: list[float]) -> bool:
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def test_the_bar_is_in_view_and_readable(signs: list[dict[str, Any]]) -> None:
    """A1."""
    assert len(_nested(signs)) == 16
    for r in _nested(signs):
        where = (r["scheme"], r["width"], r["id"])
        assert r["current"] == r["id"], where
        x, y, w, h = r["inside"]["bar"]["box"]
        assert x >= 0 and y >= 0 and x + w <= r["width"] and y + h <= r["height"], where
        name = r["id"].split("/")[-1]
        assert f"Inside {name}" in r["inside"]["bar"]["text"], where
        assert "Back to " in r["inside"]["bar"]["text"] and "Esc" in r["inside"]["bar"]["text"]
        assert r["bar"], where
        for t in r["bar"]:
            assert t["size"] >= 14, (where, t)
            assert t["ratio"] >= 4.5, (where, t)
        if "/" in r["id"]:
            for part in ["fifty maps", *r["id"].split("/")]:
                assert part in [t["text"] for t in r["bar"]], (where, part)


def test_the_top_map_has_no_sign(signs: list[dict[str, Any]]) -> None:
    """A3."""
    tops = [r for r in signs if not r["id"]]
    assert len(tops) == 8
    for r in tops:
        assert r["inside"]["bar"] is None and r["inside"]["loc"] is None
        assert r["inside"]["ground"] == r["inside"]["top"]


def test_the_locator_covers_no_card_and_no_label(signs: list[dict[str, Any]]) -> None:
    """A5."""
    for r in _nested(signs):
        where = (r["scheme"], r["width"], r["id"])
        loc = r["inside"]["loc"]
        if r["width"] == 1440:
            assert loc is not None, where
        if loc is None:
            continue
        box = [loc["x"], loc["y"], loc["x"] + loc["w"], loc["y"] + loc["h"]]
        for c in r["cards"]:
            b = c["b"]
            assert not _over(box, [b[0], b[1], b[0] + b[2], b[1] + b[3]]), (where, c["id"])
        for lab in r["labels"]:
            assert not _over(box, lab), (where, lab)


def test_the_ground_of_a_nested_map_differs(signs: list[dict[str, Any]]) -> None:
    """A6."""
    tops = {(r["page"], r["scheme"], r["width"]): r for r in signs if not r["id"]}
    for r in _nested(signs):
        top = tops[(r["page"], r["scheme"], r["width"])]
        assert r["inside"]["ground"] != top["inside"]["ground"], r["id"]
        diff = max(abs(a - b) for a, b in zip(r["ground"], top["ground"], strict=True))
        assert diff >= 3, (r["scheme"], r["width"], r["id"], r["ground"], top["ground"])


def test_the_frame_has_a_large_title(signs: list[dict[str, Any]]) -> None:
    """A7."""
    for r in [r for r in _nested(signs) if r["width"] == 1440]:
        own = [t for t in r["titles"] if t["map"] == r["id"]]
        assert own and own[0]["s"] == r["id"].split("/")[-1], r["id"]
        drawn = [t for t in r["titleTexts"] if t["s"] == own[0]["s"]]
        assert drawn and max(t["size"] for t in drawn) >= 18, (r["id"], drawn)


def test_a_neighbour_names_the_map_above(signs: list[dict[str, Any]]) -> None:
    """Sign 5: a neighbour card has the line "on" and the name of the map above."""
    page = [r for r in _nested(signs) if r["id"] == "Page" and r["width"] == 1440]
    assert page and {u["s"] for u in page[0]["ups"]} == {"on systemap"}
    assert len(page[0]["ups"]) == 10


def _check_moves(steps: list[dict[str, Any]], card: str, parent: str, reduced: bool) -> None:
    for st in steps:
        move = st["moves"][-1]
        ms = move["t1"] - move["t0"]
        if reduced:
            assert ms == 0, st
            changes = sum(a != b for a, b in zip(st["cams"], st["cams"][1:], strict=False))
            assert changes == 1, (st["step"], changes)
        else:
            assert 250 <= ms <= 450, (st["step"], ms)
        if st["step"].startswith("leave"):
            assert move["kind"] == "leave"
            assert st["current"] == parent, st
            assert st["sel"] == {"map": parent, "id": card}, st
            assert st["bar"] == bool(parent), st
            if not reduced:
                _at_card_box(move["last"])
        else:
            assert move["kind"] == "enter"
            if not reduced:
                _at_card_box(move["first"])


def _at_card_box(first: dict[str, list[float]]) -> None:
    f, c = first["frame"], first["card"]
    assert f[0] >= c[0] - 8 and f[1] >= c[1] - 8, first
    assert f[0] + f[2] <= c[0] + c[2] + 8 and f[1] + f[3] <= c[1] + c[3] + 8, first
    assert abs(f[0] + f[2] / 2 - c[0] - c[2] / 2) <= 8, first
    assert abs(f[1] + f[3] / 2 - c[1] - c[3] / 2) <= 8, first
    assert abs(f[2] - c[2]) <= 8 or abs(f[3] - c[3]) <= 8, first


@pytest.mark.parametrize("mode", ["--move", "--reduced"])
def test_back_esc_and_the_movements_on_page(self_page: Path, mode: str) -> None:
    """A2 and A4 on the nested map Page."""
    out = _drive(mode, str(self_page), "Page")
    assert [s["step"] for s in out["steps"]] == [
        "enter Page",
        "leave esc",
        "leave click",
        "leave enter",
        "leave locator",
    ]
    _check_moves(out["steps"], "Page", "", mode == "--reduced")


@pytest.mark.parametrize("mode", ["--move", "--reduced"])
def test_back_esc_and_the_movements_at_depth_two(m11_page: Path, mode: str) -> None:
    """A2 and A4 at depth 2 of the M11 tree: out of P0/Q0 to P0, with Q0 selected."""
    out = _drive(mode, str(m11_page), "P0,P0/Q0")
    _check_moves(out["steps"], "Q0", "P0", mode == "--reduced")
    assert out["steps"][1]["current"] == "P0/Q0"


def test_axe_finds_no_violation_in_a_nested_map(self_page: Path, m11_page: Path) -> None:
    """A8."""
    for page, map_id in ((self_page, "Page"), (m11_page, "P0/Q0/Deep")):
        out = _drive("--axe", str(page), map_id)
        if out["runs"] is None:
            no_axe("the test needs axe-core on NODE_PATH")
        assert len(out["runs"]) == 4
        for r in out["runs"]:
            assert r["current"] == map_id and r["violations"] == [] and r["errors"] == [], r


# ---- the repair of the zoomed-in view (Z1 to Z5) ---------------------------------------


def _lum(color: str) -> float:
    c = [int(color.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    f = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2]


def _contrast(fg: str, bg: str) -> float:
    a, b = _lum(fg), _lum(bg)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def _in_box(inner: list[float], b: list[float]) -> bool:
    return (
        inner[0] >= b[0]
        and inner[1] >= b[1]
        and inner[2] <= b[0] + b[2]
        and inner[3] <= b[1] + b[3]
    )


@pytest.fixture(scope="module")
def zooms(self_page: Path, m11_page: Path) -> list[dict[str, Any]]:
    out = []
    for name, page, maps in (("self", self_page, "Page"), ("m11", m11_page, M11_PATH)):
        out += [{**r, "page": name} for r in _drive("--zooms", str(page), maps)["runs"]]
    return out


def test_the_line_of_a_neighbour_is_readable_at_the_fit(zooms: list[dict[str, Any]]) -> None:
    """Z1 and Z4d."""
    fits = [r for r in zooms if r["f"] == 1]
    assert {(r["id"], r["width"]) for r in fits} == {
        (m, w) for m in ["Page", *M11_PATH.split(",")] for w in (1440, 390)
    }
    for r in fits:
        where = (r["scheme"], r["width"], r["id"])
        assert r["current"] == r["id"] and r["ups"], where
        cards = {c["id"]: c["b"] for c in r["cards"]}
        assert {u["id"] for u in r["ups"]} == set(cards), where
        for u in r["ups"]:
            assert u["box"] is not None and u["s"] == "on " + (
                "systemap" if r["page"] == "self" else _up_name(r["id"])
            ), (where, u)
            if r["width"] == 1440:
                assert u["size"] >= 10, (where, u)
            assert u["alpha"] == 1, (where, u)
            assert _contrast(u["color"], u["ground"]) >= 4.5, (where, u)
            assert _in_box(u["box"], cards[u["id"]]), (where, u, cards[u["id"]])


def _up_name(map_id: str) -> str:
    parts = map_id.split("/")
    return parts[-2] if len(parts) > 1 else "fifty maps"


def test_the_line_of_a_neighbour_keeps_its_size_at_each_zoom(zooms: list[dict[str, Any]]) -> None:
    """Z1: at each zoom where the name of a neighbour draws, the line draws in the card box."""
    named = 0
    for r in zooms:
        cards = {c["id"]: c["b"] for c in r["cards"]}
        for u in r["ups"]:
            if not u["named"]:
                continue
            named += 1
            where = (r["scheme"], r["width"], r["id"], r["f"], u["id"])
            assert u["box"] is not None, where
            assert u["size"] >= 0.7 * u["name"], (where, u["size"], u["name"])
            assert _in_box(u["box"], cards[u["id"]]), (where, u["box"], cards[u["id"]])
    assert named >= 200


def _step(a: dict[str, float], b: dict[str, float], size: list[int]) -> float:
    """The largest distance on the screen that a corner of the viewport moves."""
    out = 0.0
    for px, py in ((0, 0), (size[0], 0), (0, size[1]), (size[0], size[1])):
        qx = (a["x"] + px / a["k"] - b["x"]) * b["k"]
        qy = (a["y"] + py / a["k"] - b["y"]) * b["k"]
        out = max(out, ((qx - px) ** 2 + (qy - py) ** 2) ** 0.5)
    return out


def _largest(run: dict[str, Any]) -> float:
    cams = run["cams"]
    return max(_step(a, b, run["size"]) for a, b in zip(cams, cams[1:], strict=False))


def test_esc_during_a_move_out_goes_out_one_more_level(m11_page: Path) -> None:
    """Z3."""
    out = _drive("--queue", str(m11_page), M11_PATH)
    normal = [r for r in out["runs"] if r["n"] == 1]
    assert [r["from"] for r in normal] == ["P0/Q0/Deep", "P0/Q0", "P0"]
    for r in normal:
        assert r["sel"]["id"] == r["from"].split("/")[-1], r["sel"]
    limit = max(_largest(r) for r in normal) + 8
    want = {2: ("P0", {"map": "P0", "id": "Q0"}), 3: ("", {"map": "", "id": "P0"})}
    runs = [r for r in out["runs"] if r["n"] > 1]
    assert sorted((r["how"], r["n"]) for r in runs) == [
        ("click", 2),
        ("click", 3),
        ("esc", 2),
        ("esc", 3),
    ]
    for r in runs:
        where = (r["how"], r["n"])
        assert (r["current"], r["sel"]) == want[r["n"]], where
        assert r["bar"] == (r["n"] == 2) and r["loc"] == (r["n"] == 2), where
        assert [m["kind"] for m in r["moves"]] == ["leave"] * r["n"], where
        assert _largest(r) < limit, (where, _largest(r), limit)


def test_each_name_in_the_path_goes_to_its_map(m11_page: Path) -> None:
    """Z4b."""
    out = _drive("--path", str(m11_page), M11_PATH)
    assert out["names"] == ["fifty maps", "P0", "Q0", "Deep"]
    by = {s["name"]: s for s in out["steps"]}
    assert set(by) == {"fifty maps", "P0", "Q0"}
    top = by["fifty maps"]
    assert top["current"] == "" and top["sel"] == {"map": "", "id": "P0"}, top
    assert not top["bar"] and not top["loc"], top
    assert by["P0"]["current"] == "P0" and by["P0"]["sel"] == {"map": "P0", "id": "Q0"}
    assert by["Q0"]["current"] == "P0/Q0" and by["Q0"]["sel"] == {"map": "P0/Q0", "id": "Deep"}


@pytest.fixture(scope="module")
def views_pages(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """The nested fixture with a state machine in each map, and the self-map with history."""
    import canvas_sequenced  # noqa: PLC0415
    from conftest import write_tree  # noqa: PLC0415
    from test_atlas_history_browser import _history  # noqa: PLC0415
    from test_atlas_states_browser import INNER_MACHINE, TOP_MACHINE  # noqa: PLC0415

    root = tmp_path_factory.mktemp("views")
    write_tree(root, canvas_sequenced.files())
    for command in ("place", "extract", "render"):
        assert main(["--root", str(root), command]) == 0
    cfg = config.load(root)
    tree = nest.load(cfg)
    data = atlas_data.build(cfg, tree, facts_file.read_facts(cfg.facts_path, cfg.root))
    data["maps"][0]["sm"] = [TOP_MACHINE]
    data["maps"][1]["sm"] = [INNER_MACHINE]
    nested = root / "atlas.html"
    nested.write_text(atlas_page.build(canvas_page.tree_theme(cfg, tree), data), encoding="utf-8")
    cfg = config.load(REPO)
    tree = nest.load(cfg)
    data = atlas_data.build(cfg, tree, facts_file.read_facts(cfg.facts_path, cfg.root))
    own = root / "self.html"
    own.write_text(
        atlas_page.build(canvas_page.tree_theme(cfg, tree), data, _history()), encoding="utf-8"
    )
    return {"nested": nested, "self": own}


def _clear(bar: list[float], boxes: dict[str, list[float]]) -> bool:
    return all(b[1] >= bar[3] for b in boxes.values())


def test_each_view_of_a_nested_map_shows_the_bar_and_the_ground(
    views_pages: dict[str, Path],
) -> None:
    """Z5."""
    runs = _drive("--views", str(views_pages["nested"]), "Gateway")["runs"]
    runs += _drive("--views", str(views_pages["self"]), "Page")["runs"]
    shown = {(r["view"], r["shows"], r["width"]) for r in runs if r["has"]}
    for view in ("map", "seq-map", "seq-diagram", "states"):
        assert {(view, "Gateway", w) for w in (1440, 390)} <= shown, view
    for view in ("map", "seq-map", "seq-diagram", "states", "focus", "history"):
        assert {(view, "", w) for w in (1440, 390)} <= shown, view
    assert {("focus", "Page", w) for w in (1440, 390)} <= shown
    for r in [r for r in runs if r["has"]]:
        where = (r["view"], r["id"], r["width"], r["shows"])
        if r["shows"]:
            assert r["bar"] is not None, where
            assert "Back to " in r["bar"]["text"] and "Esc" in r["bar"]["text"], where
            assert f"Inside {r['shows']}" in r["bar"]["text"], where
            assert r["ground"] == r["inside"] != r["top"] and r["attr"], where
            assert _clear(r["barBox"], r["boxes"]), (where, r["barBox"], r["boxes"])
            assert r["back"] == {
                "mode": "map",
                "current": "",
                "sel": {"map": "", "id": r["shows"]},
                "bar": False,
            }, where
        else:
            assert r["bar"] is None and r["barBox"] is None, where
            assert r["ground"] == r["top"] and not r["attr"], where
    history = [r for r in runs if r["view"] == "history" and r["has"]]
    assert {r["id"] for r in history} == {"Page", ""}
    assert all(r["shows"] == "" for r in history)
    for r in [r for r in runs if r["has"]]:
        assert r["body"] == _rgb(r["inside"] if r["shows"] else r["top"]), (r["view"], r["id"])


def test_a_hash_change_in_each_view_opens_the_map_view_with_the_bar(
    views_pages: dict[str, Path],
) -> None:
    """H1: a hash change in a view other than the Map view gave a hidden bar."""
    runs = _drive("--hash", str(views_pages["self"]), "Page")["runs"]
    assert [r["view"] for r in runs if r["has"]] == [
        "map",
        "seq-map",
        "seq-diagram",
        "states",
        "focus",
        "history",
    ]
    for r in runs:
        where = r["view"]
        assert (r["mode"], r["current"], r["shows"]) == ("map", "Page", "Page"), (where, r)
        assert r["bar"] and not r["hidden"], (where, r)
        assert "Back to " in r["back"] and "Inside Page" in r["back"], (where, r)


def _rgb(color: str) -> str:
    c = [int(color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
    return f"rgb({c[0]}, {c[1]}, {c[2]})"


def test_a_total_is_the_total_of_the_map(self_page: Path) -> None:
    """Z2 on Page: the total of the parts agrees with the button and the reading line."""
    import re  # noqa: PLC0415

    out = _drive("--totals", str(self_page), "Page")
    parts = int(re.search(r"its (\d+) parts", out["button"]).group(1))
    assert parts == 11
    assert f"double-click to see its {parts} parts" in out["say"], out["say"]
    shown = [h for h in out["heads"] if "flow" in h["counts"]]
    assert shown
    for h in shown:
        found = re.search(r"(?:(\d+) of )?(\d+) parts", h["counts"])
        assert found and int(found.group(2)) == parts, h
        assert re.search(r"(?:\d+ of )?10 neighbours", h["counts"]), h
