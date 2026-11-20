"""The History view of the atlas page, in a browser (docs/design/atlas.md, stage 6).

The test drives the atlas page of the map of this repository with a history that the test
makes from a small log (`_history`, with `history_data.build`), in the Chromium of
Playwright (tests/atlas_history.js). Thus the expected values do not depend on the commits
of the clone. The test skips when Node or the Playwright package is not there, except when
SYSTEMAP_BROWSER_TESTS is "required". Then it fails. The test of axe-core skips when
axe-core is not on NODE_PATH, with the same exception.

Acceptance values, written before the first run on 2026-11-19:

1. The header has the button History only when the page has history data. A click on it
   presses it. The canvas, the layer tabs and the zoom control do not show. The headline
   gives "History", "Where did the system change, and when?" and "4 commits · 1 Jan to
   13 Jan · changed source files, by component · the clone is shallow, earlier commits are
   not in it".
2. The board has one row for each component with a change, in the order of the cards of
   the page data, with a name and 12 cells. The opacity of a cell with a change is
   sqrt(lines / largest lines), to 0.01, as docs/design/atlas.md gives it (changed from the
   rule of the study in the repair of the stage, before its run). A cell with no change has the class
   "none". A cell with a new module has a dot. The bars have heights in the ratio of the
   changed lines of each column, and the highest bar is 46 map units high. The count at the
   right of a row is its count of file changes.
3. At 1440 x 900 the board is at the right of the headline, in the screen, and above the
   reading line. At 1000 x 800 the board is under the headline.
4. A pointer on a cell lights it and the name of its row, and the reading line gives the
   component, the dates of the part, "6 file changes, 15 lines" and "new: a, b, c, d and 1
   more". With the pointer off the board the reading line does not show. A click keeps the
   reading line (aria-pressed "true"). A second click removes it. A click on the ground
   removes it.
5. The keys. The board has one stop of Tab. From the first name: the right arrow key goes to
   the first cell of the row, the down arrow key to the row below, End to the last cell,
   Home to the name, the up arrow key to the row above. Enter on a cell keeps the reading
   line, and Esc removes it. The camera does not move for the keys and F.
6. Enter on the name of a row shows the Map view, with that card selected.
7. On a phone of 390 x 844 px, in the light and the dark scheme: the headline shows the
   counts, the page has no horizontal scroll, the board does not scroll at the right, the
   board is under the headline, and each name of a row is 7 px high or more. A tap on a cell
   gives the reading line.
8. A page with no history data has no button History, and the view History does not open.
9. The page has no script error in each run. axe-core finds no violation in the History
   view with a focused cell, in the light and the dark scheme, at 1440 x 900 and at
   390 x 844.
10. With reduced motion, a cell has no transition (Reduce motion button). The live region of
   a screen reader gives the count of commits and, for a shallow clone, "The clone is
   shallow. Earlier commits are not in it."
11. On a phone of 390 x 844 px, the Map view shows the layer tabs in a strip under the
   header: each of the first two tabs is 40 px wide or more and in the screen, the strip
   does not cover the views, and the headline is under the strip.

Acceptance value, written on 2026-11-20 for the final repair, before the first run of its
test:

12. For a shallow clone, the board marks where the clone starts: it has the two texts
   "Clone starts" and "no earlier commits", at the left of the first column (the right
   edge of each text is at the left of the left edge of the first cell).
"""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_canvas_access import no_axe
from test_canvas_browser import browser

from systemap import atlas_data, atlas_page, canvas_page, config, facts_file, history_data, nest

ROOT = Path(__file__).resolve().parent
DRIVER = ROOT / "atlas_history.js"
REPO = ROOT.parent
NO_AXE = "the test needs axe-core on NODE_PATH"
DAY = 86_400
ROW = "CLI"


def _history() -> dict[str, Any]:
    new = tuple(f"{x}.py" for x in "abcde")
    commits = (
        history_data.Commit("r", 0, True, (("cli.py", 99),), ()),
        history_data.Commit(
            "1", 0, False, (("cli.py", 10), ("config.py", 3), *((n, 1) for n in new)), new
        ),
        history_data.Commit("2", 6 * DAY, False, (("page.py", 40),), ()),
        history_data.Commit("3", 9 * DAY, False, (("README.md", 5),), ()),
        history_data.Commit("4", 12 * DAY, False, (("config.py", 1),), ()),
    )
    own = {"cli.py": ("CLI", "cli"), "config.py": ("Config", "config"), "page.py": ("Page", "page")}
    own.update({n: ("CLI", n[:-3]) for n in new})
    data = history_data.build(history_data.Log("h", True, commits), own)
    assert data is not None
    return data


def _drive(*args: str) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), *args], capture_output=True, text=True, timeout=600
    )
    assert proc.returncode == 0, proc.stderr
    out = dict(json.loads(proc.stdout))
    assert out.get("errors", []) == [], out.get("errors")
    return out


@pytest.fixture(scope="module")
def pages(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    cfg = config.load(REPO)
    tree = nest.load(cfg)
    data = atlas_data.build(cfg, tree, facts_file.read_facts(cfg.facts_path, cfg.root))
    theme = canvas_page.tree_theme(cfg, tree)
    folder = tmp_path_factory.mktemp("history")
    hist = _history()
    (folder / "with.html").write_text(atlas_page.build(theme, data, hist), encoding="utf-8")
    (folder / "none.html").write_text(atlas_page.build(theme, data), encoding="utf-8")
    return {"with": folder / "with.html", "none": folder / "none.html", "data": data, "h": hist}


@pytest.fixture(scope="module")
def wide(pages: dict[str, Any]) -> dict[str, Any]:
    return _drive("--wide", str(pages["with"]), ROW)


def _rows(pages: dict[str, Any]) -> list[str]:
    return [c["id"] for c in pages["data"]["maps"][0]["cards"] if c["id"] in pages["h"]["cells"]]


def test_the_header_and_the_headline(wide: dict[str, Any]) -> None:
    """Acceptance 1."""
    assert ["History", "false"] in wide["before"]["pressed"]
    st = wide["shown"]
    assert ["History", "true"] in st["pressed"]
    assert st["canvas"] == "hidden"
    assert st["tabs"] == "none" and st["zoom"] == "none"
    assert st["history"]["on"]
    assert st["view"]["kicker"] == "History"
    assert st["view"]["question"] == "Where did the system change, and when?"
    assert st["view"]["counts"] == (
        "4 commits · 1 Jan to 13 Jan · changed source files, by component"
        " · the clone is shallow, earlier commits are not in it"
    )


def _cell_ok(o: dict[str, Any], x: list[Any], top: int) -> None:
    """A drawn cell `o` agrees with its data `x`."""
    assert o["dot"] == bool(x[2])
    if not x[0]:
        assert "none" in o["cls"]
        return
    assert "none" not in o["cls"]
    want = math.sqrt(x[1] / top)
    assert float(o["opacity"]) == pytest.approx(want, abs=0.006)


def test_reduced_motion_and_the_words_for_a_screen_reader(wide: dict[str, Any]) -> None:
    """Acceptance 10."""
    assert wide["motion"]["normal"] == "0.12s"
    assert wide["motion"]["reduced"] == "0s"
    assert wide["motion"]["back"] == "0.12s"
    said = wide["shown"]["said"]
    assert said.startswith("History. 4 commits from 1 Jan to 13 Jan.")
    assert said.endswith(" The clone is shallow. Earlier commits are not in it.")


def test_the_rows_and_the_cells(wide: dict[str, Any], pages: dict[str, Any]) -> None:
    """Acceptance 2: the rows and the cells."""
    h = wide["shown"]["history"]
    cells = pages["h"]["cells"]
    names = [o["id"] for o in h["items"] if o["kind"] == "r"]
    assert names == _rows(pages)
    assert sorted(names) == ["CLI", "Config", "Page"]
    top = max(x[1] for row in cells.values() for x in row)
    for name in names:
        got = [o for o in h["items"] if o["kind"] == "c" and o["id"] == name]
        got.sort(key=lambda o: o["j"])
        assert len(got) == 12
        for o, x in zip(got, cells[name], strict=True):
            _cell_ok(o, x, top)


def test_the_bars_and_the_sums(wide: dict[str, Any], pages: dict[str, Any]) -> None:
    """Acceptance 2: the bars and the counts at the right."""
    h = wide["shown"]["history"]
    cells = pages["h"]["cells"]
    names = [o["id"] for o in h["items"] if o["kind"] == "r"]
    totals = [sum(cells[n][i][1] for n in names) for i in range(12)]
    bars = [b["h"] for b in h["bars"]]
    assert max(bars) == pytest.approx(46)
    for b, t in zip(bars, totals, strict=True):
        assert b == pytest.approx(max(1, t / max(totals) * 46))
    assert h["sums"][0] == "files"
    assert h["sums"][1:] == [str(sum(x[0] for x in cells[n])) for n in names]


def test_the_place_of_the_board(wide: dict[str, Any]) -> None:
    """Acceptance 3."""
    st = wide["shown"]
    view, ask = st["history"]["view"], st["ask"]
    assert view["x"] >= ask["x"] + ask["width"]
    assert view["x"] + view["width"] <= 1440 and view["y"] + view["height"] <= 900
    cells = [o["rect"] for o in st["history"]["items"]]
    say = wide["pointed"]["sayBox"]
    assert max(r["y"] + r["height"] for r in cells) <= say["y"]
    narrow = wide["narrow"]
    assert narrow["history"]["view"]["y"] >= narrow["ask"]["y"] + narrow["ask"]["height"]


def test_pointing_and_keeping_a_cell(wide: dict[str, Any], pages: dict[str, Any]) -> None:
    """Acceptance 4."""
    key = wide["cell"]
    st = wide["pointed"]
    lit = {o["key"] for o in st["history"]["items"] if o["lit"]}
    row = next(o for o in st["history"]["items"] if o["key"] == key)
    name = next(o for o in st["history"]["items"] if o["kind"] == "r" and o["i"] == row["i"])
    assert lit == {key, name["key"]}
    part = pages["h"]["parts"][row["j"]]
    text = st["say"]["text"]
    assert st["say"]["on"]
    assert ROW in text and f"{part[0]} to {part[1]}" in text
    assert "6 file changes, 15 lines" in text
    assert "new: a, b, c, d and 1 more" in text
    assert not wide["off"]["say"]["on"]
    assert wide["pinned"]["say"]["on"] and wide["pinned"]["history"]["pin"] == key
    pressed = next(o for o in wide["pinned"]["history"]["items"] if o["key"] == key)
    assert pressed["label"].startswith(f"{ROW}, {part[0]} to {part[1]}, 6 file changes, 15 lines")
    assert wide["second"]["history"]["pin"] is None
    assert wide["ground"]["history"]["pin"] is None and not wide["ground"]["say"]["on"]


def test_the_keys(wide: dict[str, Any]) -> None:
    """Acceptance 5."""
    k = wide["keys"]
    tabs = [o for o in k["start"]["history"]["items"] if o["tab"] == 0]
    assert len(tabs) == 1
    assert k["start"]["history"]["active"] == "r0"
    assert k["right"]["history"]["active"] == "c0:0"
    assert k["down"]["history"]["active"] == "c1:0"
    assert k["end"]["history"]["active"] == "c1:11"
    assert k["home"]["history"]["active"] == "r1"
    assert k["up"]["history"]["active"] == "r0"
    assert k["right2"]["history"]["active"] == "c0:0"
    assert k["enter"]["history"]["pin"] == "c0:0" and k["enter"]["say"]["on"]
    assert k["esc"]["history"]["pin"] is None and not k["esc"]["say"]["on"]
    cams = [k[x]["camera"] for x in ("start", "right", "down", "end", "home", "esc", "f")]
    assert all(c == cams[0] for c in cams)
    assert all(len([o for o in k[x]["history"]["items"] if o["tab"] == 0]) == 1 for x in k)


def test_a_name_shows_the_card_on_the_map(wide: dict[str, Any]) -> None:
    """Acceptance 6."""
    st = wide["map"]
    assert ["Map", "true"] in st["pressed"]
    assert st["canvas"] == "visible"
    assert st["side"]["sel"] == {"map": "", "id": ROW}


def test_the_phone(pages: dict[str, Any]) -> None:
    """Acceptance 7."""
    out = _drive("--phone", str(pages["with"]), ROW)
    for scheme in ("light", "dark"):
        st = out[scheme]["shown"]
        assert st["counts"] == "block"
        assert st["scroll"] == st["width"] == 390
        sw, _sh, cw, _ch = st["history"]["scroll"]
        assert sw <= cw
        assert st["history"]["view"]["y"] >= st["ask"]["y"] + st["ask"]["height"]
        names = [o["text"]["px"] for o in st["history"]["items"] if o["kind"] == "r"]
        assert min(names) >= 7
        tap = out[scheme]["tapped"]
        assert tap["say"]["on"] and ROW in tap["say"]["text"]
        # Acceptance 11: the layer tabs of the Map view.
        m = out[scheme]["mapView"]
        assert m["scroll"] == 390
        assert len(m["tabs"]) >= 2
        for tab in m["tabs"][:2]:
            assert tab["width"] >= 40 and tab["x"] >= 0 and tab["x"] + tab["width"] <= 390
        assert (
            m["strip"]["width"] == 390 and m["strip"]["y"] >= m["views"]["y"] + m["views"]["height"]
        )
        assert m["ask"]["y"] >= m["strip"]["y"] + m["strip"]["height"]


def test_no_history_gives_no_view(pages: dict[str, Any]) -> None:
    """Acceptance 8."""
    out = _drive("--none", str(pages["none"]))
    assert all(name != "History" for name, _ in out["shown"]["pressed"])
    assert out["mode"] is False
    assert out["after"]["view"]["mode"] == "map"
    assert out["after"]["history"]["has"] is False


def test_axe_finds_no_violation(pages: dict[str, Any]) -> None:
    """Acceptance 9."""
    out = _drive("--axe", str(pages["with"]))
    if out["axe"] is None:
        no_axe(NO_AXE)
    assert len(out["axe"]) == 4
    for run in out["axe"]:
        assert run["violations"] == [], run


def test_the_board_marks_where_a_shallow_clone_starts(wide: dict[str, Any]) -> None:
    """Acceptance 12."""
    h = wide["shown"]["history"]
    assert h["data"]["shallow"] is True
    assert [e["text"] for e in h["edge"]] == ["Clone starts", "no earlier commits"]
    first = min(o["rect"]["left"] for o in h["items"] if o["kind"] == "c")
    assert all(e["box"]["right"] <= first for e in h["edge"])
