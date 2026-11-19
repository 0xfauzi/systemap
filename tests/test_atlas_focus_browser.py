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

Acceptance values added for the repair of stage 5, written before the first run on
2026-11-19:

11. The cap: the cards of a column are the first nine cards of the step, in the order of
    the reach (the order of the flows of the map), from the top down. The text "+ N more"
    is below the ninth card, and its middle is 2 px or less from the middle of that card.
12. At 1181 x 800 the board has the four columns, and at 1180 x 800 the two columns at one
    step only.
13. Space on a card focuses on it, and the keyboard focus is then on the new middle card.
    Enter on a line keeps its light (aria-pressed "true"), and Esc removes it. A second
    click on a kept line removes its light.
14. The reading line of a line gives the two cards, each artifact of the line, and the
    relation sentence of the model when the line has one flow.
15. The names for a screen reader: the middle card has the name "X. The card in focus."
    and aria-current "true". A card at one step has the name "Y. X gives to it. Select to
    focus on it." or "Y. Gives to X. Select to focus on it.", and a card at two steps
    "Y. Two steps after X. Select to focus on it." or "Y. Two steps before X. Select to
    focus on it.". A line has the name "Flow from S to T: A." with the artifacts of the
    line. The board has the name "Focus on X". The live region starts with "Focus on X.
    It receives from".
16. After the button "Focus on this card" of the details, with a click and with Enter, the
    keyboard focus is on the middle card.
17. After a focus on the last card of the list, with the list at its start, the current
    button of the list is in the box of the list: at 1440 x 900 and at 390 x 844.
18. With reduced motion, the headline has the new card at once after a click on a button
    of the list, the lines of the board have no transition, and the current button of the
    list is in the box of the list at once.
19. On a phone, after a tap on a line, the reading line shows the line and the box of the
    board ends above the reading line.
20. A nested map (the fixture of tests/test_nest_join.py with a flow from Routes to Views):
    with the map Gateway current, Focus shows the map Gateway. The list has only the parts
    Routes and Views, not the neighbours Auth and Store. The view opens on Routes, and the
    counts are "receives from 0 · gives to 1 · a change here can reach 1 of 1 part". The
    path of the headline has the button "join". A click on it shows the top map, on the card
    Gateway, with the keyboard focus on the middle card. The details of Routes have the
    button "Focus on this card". Changed after the first run: the value also said that the
    details of the neighbour Auth do not have the button. A selection of a neighbour goes
    out to its card in the map above, so the details of a neighbour do not open. The
    test does not examine them.
21. A map whose flows go only to its neighbours has no Focus view (`atlas_page._has_focus`).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree
from test_canvas_access import no_axe
from test_canvas_browser import browser
from test_nest_join import CONFIG, NESTED, SOURCE, TOP

from systemap import atlas_data, atlas_header, atlas_page, canvas_page, config, facts_file, nest
from systemap.cli import main

ROOT = Path(__file__).resolve().parent
DRIVER = ROOT / "atlas_focus.js"
REPO = ROOT.parent


NO_AXE = "the test needs axe-core on NODE_PATH"


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
    count of steps of the shortest path, in the order of the reach: one step after the
    other, and in a step in the order of the flows."""
    pairs = [(t, s) if back else (s, t) for s, t in _flows(data)]
    dist: dict[str, int] = {}
    edge, d = [card], 0
    while edge:
        d += 1
        nxt = []
        for s, t in pairs:
            if s in edge and t != card and t not in dist:
                dist[t] = d
                nxt.append(t)
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
    boxes = {m["text"]: m["box"] for m in st["focus"]["more"]}
    for j, dist, step in ((-2, up, 2), (-1, up, 1), (1, dn, 1), (2, dn, 2)):
        want = [k for k, v in dist.items() if v == step]
        got = sorted((c for c in cards if c["j"] == j), key=lambda c: c["i"])
        assert [c["id"] for c in got] == want[:9]
        ys = [c["rect"]["y"] for c in got]
        assert ys == sorted(ys)
        assert all(("far" in c["cls"]) == (abs(j) == 2) for c in got)
        if len(want) > 9:
            text = f"+ {len(want) - 9} more"
            expect_more.append(text)
            ninth, box = got[8]["rect"], boxes[text]
            assert box["y"] >= ninth["y"] + ninth["height"]
            assert abs(box["x"] + box["width"] / 2 - ninth["x"] - ninth["width"] / 2) <= 2
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


@pytest.fixture(scope="module")
def phone(self_page: tuple[Path, dict[str, Any]]) -> dict[str, Any]:
    return _drive("--phone", self_page[0])


def test_the_phone(phone: dict[str, Any]) -> None:
    out = phone
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
        no_axe(NO_AXE)
    assert len(out["axe"]) == 4
    for run in out["axe"]:
        assert run["violations"] == [], run


def _between(data: dict[str, Any], s: str, t: str) -> list[dict[str, Any]]:
    return [f for f in data["maps"][0]["flows"] if f["s"] == s and f["t"] == t]


def test_the_limit_of_1180_px(wide: dict[str, Any]) -> None:
    """Acceptance 12."""
    assert wide["w1181"]["focus"]["id"] == "Model"
    assert sorted({c["j"] for c in _cards(wide["w1181"])}) == [-2, -1, 0, 1, 2]
    assert sorted({c["j"] for c in _cards(wide["w1180"])}) == [-1, 0, 1]


def test_space_enter_on_a_line_and_a_second_click(wide: dict[str, Any]) -> None:
    """Acceptance 13."""
    k = wide["keys"]
    target = k["right5"]["focus"]["active"]
    assert target.startswith("n1:")
    assert k["space"]["focus"]["id"] == target.split(":", 1)[1]
    assert k["space"]["focus"]["active"] == "n0"
    line = next(e for e in _lines(k["line"]) if e["i"] == 0)
    assert k["line"]["focus"]["pin"] == "e0"
    assert line["pressed"] == "true" and line["lit"] and k["line"]["say"]["on"]
    assert k["lineEsc"]["focus"]["pin"] is None
    assert not any(o["lit"] for o in k["lineEsc"]["focus"]["items"])
    assert not k["lineEsc"]["say"]["on"]
    again = wide["again"]
    assert again["focus"]["pin"] is None
    assert not any(e["lit"] for e in _lines(again))


def test_the_reading_line_of_a_line(
    wide: dict[str, Any], self_page: tuple[Path, dict[str, Any]]
) -> None:
    """Acceptance 14."""
    line = wide["line"]
    one = next(e for e in _lines(line) if e["i"] == wide["lineIndex"])
    flows = _between(self_page[1], one["s"], one["t"])
    assert len(flows) == one["n"]
    text = line["say"]["text"]
    for f in flows:
        assert f["a"] in text
    if len(flows) == 1 and flows[0].get("y"):
        assert flows[0]["y"] in text


def test_the_names_for_a_screen_reader(
    wide: dict[str, Any], self_page: tuple[Path, dict[str, Any]]
) -> None:
    """Acceptance 15."""
    st = wide["shown"]
    places = {
        -2: "Two steps before Model",
        -1: "Gives to Model",
        1: "Model gives to it",
        2: "Two steps after Model",
    }
    for c in _cards(st):
        if c["j"] == 0:
            assert c["label"] == "Model. The card in focus." and c["current"] == "true"
        else:
            assert c["label"] == f"{c['id']}. {places[c['j']]}. Select to focus on it."
            assert c["current"] is None
    for e in _lines(st):
        names = ", ".join(f["a"] for f in _between(self_page[1], e["s"], e["t"]))
        assert e["label"] == f"Flow from {e['s']} to {e['t']}: {names}."
    assert st["focus"]["label"] == "Focus on Model"
    assert st["said"].startswith("Focus on Model. It receives from")


def test_the_details_give_the_keyboard_focus(self_page: tuple[Path, dict[str, Any]]) -> None:
    """Acceptance 16."""
    out = _drive("--details", self_page[0])
    assert out["shown"]["focus"]["active"] == "n0"
    assert out["keyed"]["focus"]["id"] == "Check"
    assert out["keyed"]["focus"]["active"] == "n0"


def _inside(inner: dict[str, float], outer: dict[str, float], axis: str = "y") -> bool:
    """True when the box `inner` is in the box `outer` along `axis` ("x" or "y"). A button
    of the list on a wide screen starts 10 px at the left of the list (`.rail button`)."""
    size = "height" if axis == "y" else "width"
    return (
        inner[axis] >= outer[axis] - 1
        and inner[axis] + inner[size] <= outer[axis] + outer[size] + 1
    )


def test_the_current_button_of_the_list_is_in_view(
    wide: dict[str, Any], phone: dict[str, Any]
) -> None:
    """Acceptance 17."""
    last = wide["last"]["focus"]
    assert last["id"] == last["rail"][-1]["id"] and last["rail"][-1]["on"]
    assert _inside(last["cur"], last["listBox"])
    for scheme in ("light", "dark"):
        f = phone[scheme]["last"]["focus"]
        assert f["id"] == f["rail"][-1]["id"]
        assert _inside(f["cur"], f["railBox"], "x")
        assert f["cur"]["x"] >= 0 and f["cur"]["x"] + f["cur"]["width"] <= 390


def test_reduced_motion(self_page: tuple[Path, dict[str, Any]]) -> None:
    """Acceptance 18."""
    out = _drive("--reduced", self_page[0])
    last = out["after"]["focus"]["rail"][-1]["id"]
    assert out["at"]["swap"] is False
    assert out["at"]["question"] == f"What does {last} use, and what uses {last}?"
    assert out["at"]["transition"] == "0s"
    assert _inside(out["after"]["focus"]["cur"], out["after"]["focus"]["listBox"])


def test_the_reading_line_does_not_cover_the_board(phone: dict[str, Any]) -> None:
    """Acceptance 19."""
    for scheme in ("light", "dark"):
        st = phone[scheme]["line"]
        f = st["focus"]
        assert f["pin"] == f"e{phone[scheme]['lineIndex']}"
        assert st["say"]["on"]
        assert f["view"]["y"] + f["view"]["height"] <= f["sayBox"]["y"] + 1


@pytest.fixture(scope="module")
def nested_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("focus-nested")
    flow = '    Flow("Routes", "Views", "view", "data"),\n'
    sentence = '        ("Routes", "Views"): "The routes send the view to the views.",\n'
    nested = NESTED.replace("FLOWS = (\n", "FLOWS = (\n" + flow, 1)
    nested = nested.replace("relations={\n", "relations={\n" + sentence, 1)
    assert flow in nested and sentence in nested
    files = {
        "systemap.toml": CONFIG + '[render]\npage = "atlas"\n',
        "map/model.py": TOP,
        "map/gateway.py": nested,
        **SOURCE,
    }
    write_tree(root, files)
    for command in ("place", "extract", "render"):
        assert main(["--root", str(root), command]) == 0
    return root / "docs" / "map" / "index.html"


def test_a_nested_map(nested_page: Path) -> None:
    """Acceptance 20."""
    out = _drive("--nested", nested_page)
    assert out["current"] == "Gateway"
    f = out["shown"]["focus"]
    assert f["map"] == "Gateway" and f["id"] == "Routes"
    assert [r["id"] for r in f["rail"]] == ["Routes", "Views"]
    assert {c["id"] for c in _cards(out["shown"])} == {"Routes", "Views"}
    assert out["shown"]["view"]["counts"] == (
        "receives from 0 · gives to 1 · a change here can reach 1 of 1 part"
    )
    assert out["path"][0] == ["BUTTON", "join"]
    assert ["B", "Gateway"] in out["path"]
    up = out["up"]["focus"]
    assert up["map"] == "" and up["id"] == "Gateway" and up["active"] == "n0"
    assert out["up"]["view"]["question"] == "What does Gateway use, and what uses Gateway?"
    assert out["button"] == "Focus on this card"


def test_a_map_with_flows_only_to_neighbours_has_no_focus() -> None:
    """Acceptance 21."""
    top = {"cards": [{"id": "G", "o": 1}, {"id": "A"}], "flows": []}
    inner = {
        "cards": [{"id": "A", "k": "actor"}, {"id": "R"}, {"id": "V"}],
        "flows": [{"s": "R", "t": "A"}],
    }
    assert not atlas_page._has_focus([top, inner])
    inner["flows"].append({"s": "R", "t": "V"})
    assert atlas_page._has_focus([top, inner])
    alone = {"cards": [{"id": "A", "k": "actor"}, {"id": "R"}], "flows": [{"s": "R", "t": "A"}]}
    assert atlas_page._has_focus([alone])
