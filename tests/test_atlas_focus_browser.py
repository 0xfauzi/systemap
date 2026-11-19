"""The Focus view of the atlas page, in a browser (docs/design/atlas.md, stage 5).

The test drives the atlas page of the map of this repository in the Chromium of Playwright
(tests/atlas_focus.js). The test skips when Node or the Playwright package is not there,
except when SYSTEMAP_BROWSER_TESTS is "required". Then it fails. The test of axe-core skips
when axe-core is not on NODE_PATH, with the same exception. The expected counts come from a
reach in Python on the flows of the page data (`_reach`), not from the page.

Acceptance values, written before the first run on 2026-11-19:

1. The header has the button Focus when a map has a flow between two of its cards, and not
   when no map has such a flow. A click on it presses it. The canvas does not show, and the
   layer tabs and the zoom control do not show. The view opens on the card with the most
   flows (Model). The headline gives "Focus", "What does Model use, and what uses Model?",
   and "receives from N · gives to M · a change here can reach R of T cards" with the
   counts of `_reach`.
2. At 1440 x 900 the board has four columns: "Two steps before", "Gives to Model", "Model
   gives to" and "Two steps after", in that order from left to right. Each column has the
   cards of its step, nine at most, and the text "+ N more" with the count of the other
   cards of the step when the step has more than nine cards. The cards at two steps have the
   class "far". The middle card is at the middle between the columns at one step.
3. Each line starts at a card of a column and ends at a card of the next column at its
   right, and it has a flow of the map from the first card to the second card.
4. A pointer on a card lights it, its lines and the cards at their other ends, and the
   other lines have an opacity of 0.5 or less. The reading line gives the card and its
   place. A pointer on a line lights the line and its two cards, and the reading line gives
   the two cards and the artifact. With the pointer off the board, nothing is lit and the
   reading line does not show. A click on a line keeps its light (aria-pressed "true"), and
   a click on the ground removes it.
5. A click on a button of the list and a click on a card of the board focus on that card:
   the middle card, the headline and the current button of the list change. The list has the
   cards with a flow, the largest count of flows first.
6. The keys. From the first button of the list, the right arrow key goes to the middle
   card. The right arrow key goes to the column at the right, the down arrow key to the card
   below, the left arrow key to the column at the left, and Home to the middle card. Enter
   on a card focuses on it, and the keyboard focus is then on the new middle card. Esc
   removes the light. The camera does not move for the keys and F.
7. At 1000 x 800 the board has the two columns at one step only. A click on Map shows the
   Map view: the canvas shows, the board does not show, and the canvas draws flows again.
8. The details of the card Check have the button "Focus on this card". A click on it shows
   the Focus view on Check, and the details close.
9. On a phone of 390 x 844 px, in the light and the dark scheme: the board has the two
   columns at one step only, the headline shows the counts, the list is above the board,
   the page has no horizontal scroll, the board does not scroll at the right, and each name
   of a card is 7 px high or more. A tap on a card focuses on it.
10. The page has no script error in each run. axe-core finds no violation in the Focus
    view with a focused card, in the light and the dark scheme, at 1440 x 900 and at
    390 x 844.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_canvas_access import no_axe
from test_canvas_browser import browser

from systemap import atlas_data, atlas_header, atlas_page, canvas_page, config, facts_file, nest

ROOT = Path(__file__).resolve().parent
DRIVER = ROOT / "atlas_focus.js"
REPO = ROOT.parent


def _drive(mode: str, page: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), mode, str(page)], capture_output=True, text=True, timeout=600
    )
    assert proc.returncode == 0, proc.stderr
    out = dict(json.loads(proc.stdout))
    assert out.get("errors", []) == [], out.get("errors")
    return out


@pytest.fixture(scope="module")
def self_page(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    cfg = config.load(REPO)
    tree = nest.load(cfg)
    data = atlas_data.build(cfg, tree, facts_file.read_facts(cfg.facts_path, cfg.root))
    out = tmp_path_factory.mktemp("focus") / "index.html"
    out.write_text(atlas_page.build(canvas_page.tree_theme(cfg, tree), data), encoding="utf-8")
    return out, data


@pytest.fixture(scope="module")
def wide(self_page: tuple[Path, dict[str, Any]]) -> dict[str, Any]:
    return _drive("--wide", self_page[0])


def _flows(data: dict[str, Any]) -> list[tuple[str, str]]:
    top = data["maps"][0]
    ids = {c["id"] for c in top["cards"]}
    return [
        (f["s"], f["t"])
        for f in top["flows"]
        if f["s"] != f["t"] and f["s"] in ids and f["t"] in ids
    ]


def _reach(data: dict[str, Any], card: str, back: bool) -> dict[str, int]:
    """The cards on a path of flows from `card` (against the flows when `back`), with the
    count of steps of the shortest path."""
    pairs = [(t, s) if back else (s, t) for s, t in _flows(data)]
    dist: dict[str, int] = {}
    edge, d = {card}, 0
    while edge:
        d += 1
        nxt = {t for s, t in pairs if s in edge and t != card and t not in dist}
        for t in nxt:
            dist[t] = d
        edge = nxt
    return dist


def _counts(data: dict[str, Any], card: str) -> str:
    up, dn = _reach(data, card, True), _reach(data, card, False)
    total = len(data["maps"][0]["cards"]) - 1
    one = sum(1 for v in up.values() if v == 1)
    two = sum(1 for v in dn.values() if v == 1)
    return (
        f"receives from {one} · gives to {two} · a change here can reach {len(dn)} of "
        f"{total} card{'' if total == 1 else 's'}"
    )


def _cards(st: dict[str, Any]) -> list[dict[str, Any]]:
    return [o for o in st["focus"]["items"] if o["kind"] == "n"]


def _lines(st: dict[str, Any]) -> list[dict[str, Any]]:
    return [o for o in st["focus"]["items"] if o["kind"] == "e"]


def test_the_header_has_focus_only_with_a_flow() -> None:
    assert 'data-mode="focus"' in atlas_header.header("x", focus=True)
    assert 'data-mode="focus"' not in atlas_header.header("x")
    flow = {"cards": [{"id": "a"}, {"id": "b"}], "flows": [{"s": "a", "t": "b"}]}
    loop = {"cards": [{"id": "a"}], "flows": [{"s": "a", "t": "a"}]}
    assert atlas_page._has_flow(flow)
    assert not atlas_page._has_flow(loop)
    assert not atlas_page._has_flow({"cards": [], "flows": []})


def test_the_view_opens_on_the_card_with_most_flows(
    wide: dict[str, Any], self_page: tuple[Path, dict[str, Any]]
) -> None:
    data = self_page[1]
    st = wide["shown"]
    assert ["Focus", "false"] in wide["before"]["pressed"]
    assert ["Focus", "true"] in st["pressed"]
    assert st["canvas"] == "hidden"
    assert st["tabs"] == "none" and st["zoom"] == "none"
    assert st["focus"]["on"] and st["focus"]["id"] == "Model"
    assert st["view"]["kicker"].endswith("Focus")
    assert st["view"]["question"] == "What does Model use, and what uses Model?"
    assert st["view"]["counts"] == _counts(data, "Model")


def test_the_board_has_four_columns_with_a_cap(
    wide: dict[str, Any], self_page: tuple[Path, dict[str, Any]]
) -> None:
    data = self_page[1]
    st = wide["shown"]
    names = [c["text"] for c in st["focus"]["cols"]]
    assert names == ["Two steps before", "Gives to Model", "Model gives to", "Two steps after"]
    xs = [c["box"]["x"] for c in st["focus"]["cols"]]
    assert xs == sorted(xs)
    up, dn = _reach(data, "Model", True), _reach(data, "Model", False)
    cards = _cards(st)
    more = [m["text"] for m in st["focus"]["more"]]
    expect_more = []
    for j, dist, step in ((-2, up, 2), (-1, up, 1), (1, dn, 1), (2, dn, 2)):
        want = {k for k, v in dist.items() if v == step}
        got = [c for c in cards if c["j"] == j]
        assert len(got) == min(9, len(want))
        assert {c["id"] for c in got} <= want
        assert all(("far" in c["cls"]) == (abs(j) == 2) for c in got)
        if len(want) > 9:
            expect_more.append(f"+ {len(want) - 9} more")
    assert more == expect_more and more
    mid = next(c for c in cards if c["j"] == 0)["rect"]
    left = next(c for c in cards if c["j"] == -1)["rect"]
    right = next(c for c in cards if c["j"] == 1)["rect"]
    centre = mid["x"] + mid["width"] / 2
    assert abs((left["x"] + left["width"] / 2 + right["x"] + right["width"] / 2) / 2 - centre) < 2


def test_each_line_has_a_flow_between_adjacent_columns(
    wide: dict[str, Any], self_page: tuple[Path, dict[str, Any]]
) -> None:
    flows = set(_flows(self_page[1]))
    by_key = {c["key"]: c for c in _cards(wide["shown"])}
    lines = _lines(wide["shown"])
    assert lines
    for e in lines:
        a, b = by_key[e["a"]], by_key[e["b"]]
        assert b["j"] == a["j"] + 1
        assert (a["id"], b["id"]) in flows
        assert e["box"]["x"] >= a["rect"]["x"] + a["rect"]["width"] - 1
        assert e["box"]["x"] + e["box"]["width"] <= b["rect"]["x"] + 1


def test_pointing_and_keeping_the_light(wide: dict[str, Any]) -> None:
    card = wide["card"]
    hot = next(c for c in _cards(card) if c["j"] == 1 and c["i"] == 0)
    assert hot["lit"]
    lit = [e for e in _lines(card) if e["lit"]]
    assert lit and all(hot["key"] in (e["a"], e["b"]) for e in lit)
    assert all(float(e["opacity"]) <= 0.5 for e in _lines(card) if not e["lit"])
    assert card["say"]["on"] and hot["id"] in card["say"]["text"]
    assert "Model gives to it" in card["say"]["text"]
    line = wide["line"]
    one = next(e for e in _lines(line) if e["i"] == wide["lineIndex"])
    assert one["lit"] and sum(e["lit"] for e in _lines(line)) == 1
    assert one["s"] in line["say"]["text"] and one["t"] in line["say"]["text"]
    assert not any(o["lit"] for o in wide["off"]["focus"]["items"])
    assert not wide["off"]["say"]["on"]
    pinned = next(e for e in _lines(wide["pinned"]) if e["i"] == wide["lineIndex"])
    assert pinned["lit"] and pinned["pressed"] == "true" and wide["pinned"]["say"]["on"]
    assert wide["unpinned"]["focus"]["pin"] is None
    assert not wide["unpinned"]["say"]["on"]


def test_selecting_a_card_focuses_on_it(
    wide: dict[str, Any], self_page: tuple[Path, dict[str, Any]]
) -> None:
    rail = wide["shown"]["focus"]["rail"]
    assert rail[0]["id"] == "Model" and rail[0]["on"]
    counts = [int("".join(ch for ch in r["text"].split(",")[0] if ch.isdigit())) for r in rail]
    assert counts == sorted(counts, reverse=True)
    st = wide["rail"]
    assert st["focus"]["id"] == "CLI"
    assert st["view"]["question"] == "What does CLI use, and what uses CLI?"
    assert st["view"]["counts"] == _counts(self_page[1], "CLI")
    assert [r["id"] for r in st["focus"]["rail"] if r["on"]] == ["CLI"]
    first = next(c for c in _cards(st) if c["j"] == 1 and c["i"] == 0)["id"]
    assert wide["board"]["focus"]["id"] == first
    assert [r["id"] for r in wide["board"]["focus"]["rail"] if r["on"]] == [first]


def test_the_keys(wide: dict[str, Any]) -> None:
    k = wide["keys"]
    cam = k["start"]["camera"]
    assert k["right"]["focus"]["active"] == "n0"
    assert k["right2"]["focus"]["active"].startswith("n1:")
    below = k["down"]["focus"]["active"]
    assert below.startswith("n1:") and below != k["right2"]["focus"]["active"]
    assert k["left"]["focus"]["active"] == "n0"
    assert k["left2"]["focus"]["active"].startswith("n-1:")
    assert k["home"]["focus"]["active"] == "n0"
    target = k["right3"]["focus"]["active"].split(":", 1)[1]
    assert k["entered"]["focus"]["id"] == target
    assert k["entered"]["focus"]["active"] == "n0"
    assert not any(o["lit"] for o in k["esc"]["focus"]["items"])
    for name in ("right", "down", "left", "home", "esc", "f"):
        assert k[name]["camera"] == cam


def test_a_middle_screen_and_the_map(wide: dict[str, Any]) -> None:
    js = sorted({c["j"] for c in _cards(wide["resized"])})
    assert js == [-1, 0, 1]
    m = wide["map"]
    assert m["canvas"] == "visible" and not m["focus"]["on"]
    assert wide["mapStats"]["flows"] > 0


def test_the_details_open_the_view(self_page: tuple[Path, dict[str, Any]]) -> None:
    out = _drive("--details", self_page[0])
    assert out["button"] == "Focus on this card"
    assert out["shown"]["focus"]["mode"] == "focus"
    assert out["shown"]["focus"]["id"] == "Check"
    assert not out["side"]["on"]


def test_the_phone(self_page: tuple[Path, dict[str, Any]]) -> None:
    out = _drive("--phone", self_page[0])
    for scheme in ("light", "dark"):
        st = out[scheme]["shown"]
        f = st["focus"]
        assert sorted({c["j"] for c in _cards(st)}) == [-1, 0, 1]
        assert st["counts"] == "block"
        assert f["railBox"]["bottom"] <= f["view"]["y"]
        assert st["scroll"] <= st["width"]
        assert f["scroll"][0] <= f["scroll"][2]
        assert min(c["text"]["px"] for c in _cards(st)) >= 7
        first = next(c for c in _cards(st) if c["j"] == 1 and c["i"] == 0)["id"]
        assert out[scheme]["tapped"]["focus"]["id"] == first


def test_axe_finds_no_violation(self_page: tuple[Path, dict[str, Any]]) -> None:
    out = _drive("--axe", self_page[0])
    if out["axe"] is None:
        no_axe()
    assert len(out["axe"]) == 4
    for run in out["axe"]:
        assert run["violations"] == [], run
