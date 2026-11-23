"""The States view of the atlas page, in a browser (docs/design/atlas.md, stage 4).

The test drives real atlas pages in the Chromium of Playwright (tests/atlas_states.js): the
map of this repository, which has two state machines of Model ("Source review of a
component" with a transition in each direction between current and stale, and "Review of
a flow"), and the fixture of tests/canvas_sequenced.py (a top map and the nested map
Gateway). The test adds a machine to each map of the fixture in the page data
(`_fixture`). The machine of Gateway has a transition that goes through a different state,
two transitions in the same direction between the same two states, a loop, and a state with
no symbol and no sentence. The test skips when Node or the Playwright package is not there,
except when SYSTEMAP_BROWSER_TESTS is "required". Then it fails. The test of axe-core skips
when axe-core is not on NODE_PATH, with the same exception.

Acceptance values, written before the first run on 2026-11-18:

1. The header has the button States only when a map of the tree has a state machine. A
   click on it presses it. The canvas does not show, and the layer tabs, the key, the zoom
   control and the list of the sequences do not show. The headline gives "State machine",
   "of" and the component, the label of the first machine, and "N states · M
   transitions". The list has one button for each machine with its count of states, and
   the first is current.
2. The board has one state for each state of the machine and one transition for each
   transition. Each state has round ends: the radius of its corners is half of its height.
   Each state shows its ID and the last two parts of its source symbol. The first state
   has a dot and a short line before it, at its left and at its middle height. The other
   states have no dot.
3. Each transition starts 12 px or less from the box of its source state and its
   arrowhead is 12 px or less from the box of its target state. A straight transition
   (bend 0) has its label above its line: the bottom of the label is above the line at the
   middle of the label.
4. The two transitions between current and stale (one in each direction) bend: the middle
   of each line is 10 px or more from the straight line between the centres of the two
   states, the two middles are at the two sides of it, and each label is at the outer side
   of its line: at the same side as the middle of its line, and farther from the straight
   line than that middle.
5. No two labels of a machine cover each other, and no label covers a state, in each
   machine of the two pages.
6. A pointer on a transition lights it and its two states. The other states and
   transitions have an opacity of 0.5 or less. The reading line gives the source state,
   the target state, the label and the cause. A pointer on a state lights it, its
   transitions and their states, and the reading line gives the state, its sentence and,
   for the first state, "This is the first state.". With the pointer off the board, no
   item is lit and the reading line does not show.
7. A click on a transition keeps its light and its reading line after the pointer goes.
   A click on the ground removes them.
8. The keys. With the keyboard focus on the first button of the list, the right arrow key
   gives the focus to the first state. The right and down arrow keys go to the next item,
   the left arrow key to the previous item, End to the last transition (and the right
   arrow key stays there), Home to the first state, and Tab to the next item. Enter keeps
   the light, and Esc removes it. The camera does not move for the arrow keys and F.
9. A click on the second button of the list shows the second machine: its headline and
   its board, and that button is current. After a change of the screen size to
   1000 x 800, the board is in the new free part of the screen (at the right of the list).
10. A click on Map shows the Map view: the canvas and the tabs show, the board does not
    show, the reading line does not show, and the canvas draws flows again.
11. The nested fixture. The list has one group for each map with machines, with the path
    of the map. A click on the machine of Gateway shows it. The transition through a
    different state bends, and no point of its line is in the box of that state. The two
    transitions in the same direction bend to two different sides. The loop is fully above
    the top of its state. A pointer on the state with no sentence gives "The model gives no
    meaning for this state." and the finding of that state.
12. On a phone of 390 x 844 px, in the light and the dark scheme: the list is a row under
    the headline, the board starts under the row, the page has no horizontal scroll, and
    each text of the board is 7 px high or more. A tap on a transition keeps its light and
    its reading line.
13. The page has no script error in each run. axe-core finds no violation in the States
    view with a focused transition, in the light and the dark scheme, at 1440 x 900 and at
    390 x 844. A page with no state machine has no button States.

Acceptance value written on 2026-11-18 after the first runs, before its own first run:

14. No line of a transition goes through the label of a different transition, in each
    machine of the two pages: no point of the line (each of 16 parts of the line in 10
    steps) is in the label box with a margin of 1 px.

Acceptance values written on 2026-11-18 for the repair after the review, before their first
run. They use a third page (`probe_page`): the map of this repository with more machines.
"Life of a job" comes from `states.layout` (`canvas_states`) and has three states in one
column: idle, running and paused, with a transition in each direction between idle and
running and between idle and paused. "A row" has a transition in each direction between a
and c, with b between them. "Many lines" has three transitions between b and c, a
vertical transition and two diagonal transitions.

15. In each machine of the three pages, no line of a transition goes into the box of a
    state that is not one of its two states (the check of acceptance 14, with the box of
    the state). The two transitions between idle and paused go around running, at two
    sides of it.
16. Acceptance 3, 5 and 14 also hold for each machine of the probe page at 1440 x 900. The
    label of a straight transition is at the upper side of its line: for a line that is
    not vertical, the middle of the label is above the line at the x of that middle, and
    for a vertical line, the label is at its right side. No line goes through its own
    label.
17. On a phone of 390 x 844 px, the headline gives the counts of the machine. Each state of
    each machine is in the view of the board at the right, or the mark "More" at the right
    shows. The mark shows for at least one machine of the probe page. A tap
    on that mark scrolls the board to the right, and then no state goes out of the view at
    the right.
    "Review of a flow" of this repository fits on the phone: no mark shows.
18. A kept state or transition has aria-pressed "true", and each other item has
    aria-pressed "false".
"""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Any

import canvas_sequenced
import pytest
from conftest import write_tree
from test_canvas_access import no_axe
from test_canvas_browser import browser

from systemap import (
    atlas_data,
    atlas_page,
    canvas_page,
    canvas_states,
    config,
    facts_file,
    nest,
    states,
)
from systemap.cli import main

ROOT = Path(__file__).resolve().parent
DRIVER = ROOT / "atlas_states.js"
REPO = ROOT.parent

Box = dict[str, float]


def _drive(mode: str, page: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), mode, str(page)], capture_output=True, text=True, timeout=600
    )
    assert proc.returncode == 0, proc.stderr
    out = dict(json.loads(proc.stdout))
    assert out.get("errors", []) == [], out.get("errors")
    return out


def _write(out: Path, cfg: config.Config, tree: nest.Tree, data: dict[str, Any]) -> Path:
    out.write_text(atlas_page.build(canvas_page.tree_theme(cfg, tree), data), encoding="utf-8")
    return out


def _st(i: str, c: int, r: int, **more: Any) -> dict[str, Any]:
    return {"id": i, "c": c, "r": r, **more}


def _tr(a: int, b: int, label: str, cause: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {"a": a, "b": b, "l": label, "f": -1, "q": -1}
    if cause:
        out["c"] = cause
    return out


TOP_MACHINE = {
    "id": "token",
    "n": "Life of a token",
    "of": "Auth",
    "st": [
        _st("new", 0, 0, sym="auth.tokens.NEW", y="The auth made the token.", first=1),
        _st("used", 1, 0, sym="auth.tokens.USED", y="The gateway used the token."),
    ],
    "tr": [_tr(0, 1, "use", "The gateway sends the token.")],
    "fd": ['The state "used" has no transition out.'],
}

INNER_MACHINE = {
    "id": "request",
    "n": "Life of a request",
    "of": "Routes",
    "st": [
        _st("open", 0, 0, sym="gate.routes.OPEN", y="The routes have the request.", first=1),
        _st("busy", 1, 0, sym="gate.routes.BUSY", y="A view makes the answer."),
        _st("done", 2, 0),
    ],
    "tr": [
        _tr(0, 1, "start", "A route gives the request to a view."),
        _tr(0, 2, "refuse", "The route refuses the request."),
        _tr(1, 1, "retry", "The view starts again."),
        _tr(1, 2, "answer", "The view sends the answer."),
        _tr(1, 2, "fail", "The view sends an error."),
    ],
    "fd": ['The state "done" has no transition out.'],
}


@pytest.fixture(scope="module")
def self_page(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    cfg = config.load(REPO)
    tree = nest.load(cfg)
    data = atlas_data.build(cfg, tree, facts_file.read_facts(cfg.facts_path, cfg.root))
    return _write(tmp_path_factory.mktemp("sm") / "index.html", cfg, tree, data), data


@pytest.fixture(scope="module")
def nested_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("nsm")
    write_tree(root, canvas_sequenced.files())
    for command in ("place", "extract", "render"):
        assert main(["--root", str(root), command]) == 0
    cfg = config.load(root)
    tree = nest.load(cfg)
    data = atlas_data.build(cfg, tree, facts_file.read_facts(cfg.facts_path, cfg.root))
    data["maps"][0]["sm"] = [TOP_MACHINE]
    data["maps"][1]["sm"] = [INNER_MACHINE]
    return _write(root / "atlas.html", cfg, tree, data)


def _job() -> dict[str, Any]:
    """A machine from `states.layout`: idle, running and paused are in one column."""
    s, t = states.State, states.Transition
    machine = states.StateMachine(
        "job",
        "Life of a job",
        "Model",
        (s("new", say="The job is new."), s("idle"), s("running"), s("paused")),
        (
            t("new", "idle", "accept", "The queue takes the job."),
            t("idle", "running", "start"),
            t("running", "idle", "stop"),
            t("idle", "paused", "pause"),
            t("paused", "idle", "resume"),
        ),
        ("new",),
    )
    return dict(canvas_states._machine(machine, {}, {}))


ROW_MACHINE = {
    "id": "row",
    "n": "A row",
    "of": "Model",
    "st": [_st("a", 0, 0, first=1), _st("b", 1, 0), _st("c", 2, 0)],
    "tr": [_tr(0, 1, "go"), _tr(1, 2, "on"), _tr(0, 2, "skip there"), _tr(2, 0, "skip back")],
}

LINES_MACHINE = {
    "id": "lines",
    "n": "Many lines",
    "of": "Model",
    "st": [
        _st("a", 0, 0, first=1),
        _st("b", 1, 0),
        _st("c", 2, 0),
        _st("d", 0, 1),
        _st("e", 2, 1),
    ],
    "tr": [
        _tr(0, 1, "go"),
        _tr(0, 3, "down straight"),
        _tr(3, 1, "diagonal"),
        _tr(1, 4, "diag two"),
        _tr(1, 2, "one"),
        _tr(1, 2, "two"),
        _tr(2, 1, "three"),
    ],
}


@pytest.fixture(scope="module")
def probe_page(self_page: tuple[Path, dict[str, Any]]) -> Path:
    data = json.loads(json.dumps(self_page[1]))
    data["maps"][0]["sm"] = [_job(), ROW_MACHINE, LINES_MACHINE] + list(data["maps"][0]["sm"])
    cfg = config.load(REPO)
    return _write(self_page[0].parent / "probe.html", cfg, nest.load(cfg), data)


@pytest.fixture(scope="module")
def probe(probe_page: Path) -> dict[str, Any]:
    return _drive("--probe", probe_page)


@pytest.fixture(scope="module")
def wide(self_page: tuple[Path, dict[str, Any]]) -> dict[str, Any]:
    return _drive("--wide", self_page[0])


@pytest.fixture(scope="module")
def nested(nested_page: Path) -> dict[str, Any]:
    return _drive("--nested", nested_page)


def _machines(data: dict[str, Any]) -> list[dict[str, Any]]:
    return list(data["maps"][0]["sm"])


def _items(run: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [o for o in run["states"]["items"] if o["kind"] == kind]


def _gap(p: list[float], b: Box) -> float:
    """The distance of the point p to the box b (0 in the box)."""
    dx = max(b["left"] - p[0], 0.0, p[0] - b["right"])
    dy = max(b["top"] - p[1], 0.0, p[1] - b["bottom"])
    return math.hypot(dx, dy)


def _inside(p: list[float], b: Box) -> bool:
    return b["left"] < p[0] < b["right"] and b["top"] < p[1] < b["bottom"]


def _cover(a: Box, b: Box, pad: float = 0.0) -> bool:
    return (
        a["left"] < b["right"] - pad
        and b["left"] < a["right"] - pad
        and a["top"] < b["bottom"] - pad
        and b["top"] < a["bottom"] - pad
    )


def _crosses(points: list[list[float]], b: Box) -> bool:
    """True when the line of the points goes into the box b, with a margin of 1 px."""
    inner = {
        "left": b["left"] + 1,
        "right": b["right"] - 1,
        "top": b["top"] + 1,
        "bottom": b["bottom"] - 1,
    }
    for p, q in zip(points, points[1:], strict=False):
        for n in range(11):
            u = n / 10
            if _inside([p[0] + (q[0] - p[0]) * u, p[1] + (q[1] - p[1]) * u], inner):
                return True
    return False


def _centre(b: Box) -> list[float]:
    return [(b["left"] + b["right"]) / 2, (b["top"] + b["bottom"]) / 2]


def _side(a: list[float], b: list[float], p: list[float]) -> float:
    """The signed distance of p to the line from a to b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    return ((p[0] - a[0]) * dy - (p[1] - a[1]) * dx) / (math.hypot(dx, dy) or 1.0)


def _line_y(points: list[list[float]], x: float) -> float | None:
    """The y of the line at x, from the two points at the two sides of x (None out of the line)."""
    for p, q in zip(points, points[1:], strict=False):
        lo, hi = sorted((p[0], q[0]))
        if lo <= x <= hi and hi > lo:
            return p[1] + (q[1] - p[1]) * (x - p[0]) / (q[0] - p[0])
    return None


def test_the_view_shows_only_with_a_machine(self_page: tuple[Path, dict[str, Any]]) -> None:
    """Acceptance 1 and 13: the button."""
    cfg = config.load(REPO)
    tree = nest.load(cfg)
    t = canvas_page.tree_theme(cfg, tree)
    data = json.loads(json.dumps(self_page[1]))
    assert '<button type="button" data-mode="states"' in atlas_page.build(t, data)
    for m in data["maps"]:
        m.pop("sm", None)
    assert '<button type="button" data-mode="states"' not in atlas_page.build(t, data)


def test_the_headline_the_list_and_the_board(
    self_page: tuple[Path, dict[str, Any]], wide: dict[str, Any]
) -> None:
    """Acceptance 1 and 2."""
    first = _machines(self_page[1])[0]
    assert ["States", "false"] in wide["before"]["pressed"]
    s = wide["shown"]
    assert ["States", "true"] in s["pressed"] and ["Map", "false"] in s["pressed"]
    assert s["canvas"] == "hidden"
    assert s["tabs"] == s["key"] == s["zoom"] == s["seqRail"] == "none"
    assert s["view"]["kicker"] == "State machine · of " + first["of"]
    assert s["view"]["question"] == first["n"]
    assert s["view"]["counts"] == f"{len(first['st'])} states · {len(first['tr'])} transitions"
    rail = s["states"]["rail"]
    assert [r["on"] for r in rail] == [True] + [False] * (len(rail) - 1)
    for r, x in zip(rail, _machines(self_page[1]), strict=True):
        assert r["text"].startswith(x["n"] + str(len(x["st"])))
    assert s["states"]["on"] and s["states"]["id"] == first["id"]
    nodes = _items(s, "s")
    assert [n["id"] for n in nodes] == [x["id"] for x in first["st"]]
    assert len(_items(s, "t")) == len(first["tr"])
    for n, x in zip(nodes, first["st"], strict=True):
        assert n["rx"] == n["h"] / 2
        texts = [t["text"] for t in n["texts"]]
        assert texts == [x["id"], ".".join(x["sym"].split(".")[-2:])]
        if x.get("first"):
            dot, rect = n["dot"], n["rect"]
            assert dot["right"] < n["dotLine"]["right"] <= rect["left"]
            assert abs(_centre(dot)[1] - _centre(rect)[1]) < 1
        else:
            assert n["dot"] is None


def _straight_label(e: dict[str, Any]) -> None:
    """The label of a straight transition is at the upper side of its line."""
    box, pts = e["text"]["box"], e["points"]
    mid = _centre(box)
    if abs(pts[0][0] - pts[-1][0]) < 1:
        assert box["left"] > max(p[0] for p in pts), e
        return
    y = _line_y(pts, mid[0])
    if y is None:
        y = min(pts, key=lambda p: abs(p[0] - mid[0]))[1]
    assert mid[1] < y, e
    if abs(pts[0][1] - pts[-1][1]) < 1:
        assert box["bottom"] < y, e


def _geometry(run: dict[str, Any]) -> None:
    """Acceptance 3, 5, 14 and 15 for the machine on show."""
    nodes = {n["i"]: n for n in _items(run, "s")}
    edges = _items(run, "t")
    for e in edges:
        start, tip = e["points"][0], _centre(e["tip"])
        assert _gap(start, nodes[e["a"]]["rect"]) <= 12, e
        assert _gap(tip, nodes[e["b"]]["rect"]) <= 12, e
        if e["bend"] == 0 and e["a"] != e["b"]:
            _straight_label(e)
        for n in nodes.values():
            if n["i"] not in (e["a"], e["b"]):
                assert not _crosses(e["points"], n["rect"]), (e["l"], n["id"])
    for e in edges:
        box = e["text"]["box"]
        for o in edges:
            assert not _crosses(o["points"], box), (o["l"], e["l"])
    labels = [e["text"]["box"] for e in edges]
    for i, a in enumerate(labels):
        for b in labels[i + 1 :]:
            assert not _cover(a, b), (a, b)
        for n in nodes.values():
            assert not _cover(a, n["rect"]), (a, n["id"])


def test_the_transitions_and_their_labels(wide: dict[str, Any]) -> None:
    """Acceptance 3, 4 and 5 on the two machines of this repository."""
    for run in (wide["shown"], wide["second"]):
        _geometry(run)
    nodes = {n["id"]: n for n in _items(wide["shown"], "s")}
    a, b = _centre(nodes["current"]["rect"]), _centre(nodes["stale"]["rect"])
    pair = [e for e in _items(wide["shown"], "t") if {e["a"], e["b"]} == {1, 2}]
    assert len(pair) == 2 and all(e["bend"] != 0 for e in pair)
    sides = []
    for e in pair:
        mid = _side(a, b, e["points"][8])
        label = _side(a, b, _centre(e["text"]["box"]))
        assert abs(mid) >= 10, e
        assert mid * label > 0 and abs(label) > abs(mid), e
        sides.append(mid)
    assert sides[0] * sides[1] < 0


def test_pointing_lights_and_reads(
    self_page: tuple[Path, dict[str, Any]], wide: dict[str, Any]
) -> None:
    """Acceptance 6."""
    first = _machines(self_page[1])[0]
    t = first["tr"][1]
    edge = wide["edge"]
    assert edge["states"]["hot"] == "t1" and edge["states"]["cls"] == "sfocus"
    for o in edge["states"]["items"]:
        on = (o["kind"] == "t" and o["i"] == 1) or (o["kind"] == "s" and o["i"] in (t["a"], t["b"]))
        assert o["lit"] == on, o
        if not on:
            assert float(o["opacity"]) <= 0.5
    said = edge["say"]
    assert said["on"] and said["live"] == "polite"
    for word in (first["st"][t["a"]]["id"], first["st"][t["b"]]["id"], t["l"], t["c"]):
        assert word in said["text"]
    node = wide["node"]
    s0 = first["st"][0]
    assert node["states"]["hot"] == "s0"
    lit = {(o["kind"], o["i"]) for o in node["states"]["items"] if o["lit"]}
    want = {("s", 0)} | {("t", i) for i, x in enumerate(first["tr"]) if 0 in (x["a"], x["b"])}
    want |= {("s", x["b"]) for x in first["tr"] if x["a"] == 0}
    assert lit == want
    assert s0["id"] in node["say"]["text"] and s0["y"] in node["say"]["text"]
    assert "This is the first state." in node["say"]["text"]
    off = wide["off"]
    assert off["states"]["hot"] is None and off["states"]["cls"] == ""
    assert not off["say"]["on"]
    assert not any(o["lit"] for o in off["states"]["items"])


def test_a_click_keeps_the_light(wide: dict[str, Any]) -> None:
    """Acceptance 7."""
    p = wide["pinned"]
    assert p["states"]["pin"] == "t1" and p["states"]["hot"] is None
    assert p["say"]["on"] and p["states"]["cls"] == "sfocus"
    u = wide["unpinned"]
    assert u["states"]["pin"] is None and not u["say"]["on"]
    for o in p["states"]["items"]:
        assert o["pressed"] == ("true" if (o["kind"], o["i"]) == ("t", 1) else "false"), o
    assert all(o["pressed"] == "false" for o in u["states"]["items"])


def test_the_keys(self_page: tuple[Path, dict[str, Any]], wide: dict[str, Any]) -> None:
    """Acceptance 8."""
    first = _machines(self_page[1])[0]
    k = wide["keys"]
    last = "t" + str(len(first["tr"]) - 1)
    assert k["right"]["states"]["active"] == "s0"
    assert k["right"]["states"]["hot"] == "s0" and k["right"]["say"]["on"]
    assert k["right2"]["states"]["active"] == "s1"
    assert k["down"]["states"]["active"] == "s2"
    assert k["left"]["states"]["active"] == "s1"
    assert k["end"]["states"]["active"] == last
    assert k["endRight"]["states"]["active"] == last
    assert k["home"]["states"]["active"] == "s0"
    assert k["tab"]["states"]["active"] == "s1"
    assert k["enter"]["states"]["pin"] == "s1"
    assert k["esc"]["states"]["pin"] is None and k["esc"]["states"]["hot"] is None
    assert not k["esc"]["say"]["on"]
    for name in ("right", "down", "left", "end", "home", "f"):
        assert k[name]["camera"] == k["start"]["camera"], name


def test_the_second_machine_and_a_new_size(
    self_page: tuple[Path, dict[str, Any]], wide: dict[str, Any]
) -> None:
    """Acceptance 9."""
    second = _machines(self_page[1])[1]
    s = wide["second"]
    assert s["view"]["question"] == second["n"] and s["states"]["id"] == second["id"]
    assert [r["on"] for r in s["states"]["rail"]][:2] == [False, True]
    assert [n["id"] for n in _items(s, "s")] == [x["id"] for x in second["st"]]
    r = wide["resized"]["states"]
    assert r["view"]["left"] >= r["railBox"]["right"]
    assert r["view"]["right"] <= 1000
    for n in _items(wide["resized"], "s"):
        assert n["rect"]["left"] >= r["view"]["left"] and n["rect"]["right"] <= r["view"]["right"]


def test_the_map_view_comes_back(wide: dict[str, Any]) -> None:
    """Acceptance 10."""
    m = wide["map"]
    assert m["view"]["mode"] == "map" and ["Map", "true"] in m["pressed"]
    assert m["canvas"] == "visible" and m["tabs"] != "none"
    assert not m["states"]["on"] and not m["say"]["on"]
    assert wide["mapLines"]["flows"] > 0


def test_a_machine_in_a_nested_map(nested: dict[str, Any]) -> None:
    """Acceptance 11 and 5."""
    assert len(nested["groups"]) == 2 and nested["groups"][1].endswith("Gateway")
    assert nested["shown"]["states"]["id"] == "token"
    inner = nested["inner"]
    assert inner["states"]["id"] == "request" and inner["view"]["question"] == "Life of a request"
    _geometry(inner)
    nodes = {n["i"]: n for n in _items(inner, "s")}
    edges = {e["i"]: e for e in _items(inner, "t")}
    through = edges[1]
    assert through["bend"] != 0
    assert not any(_inside(p, nodes[1]["rect"]) for p in through["points"])
    a, b = _centre(nodes[1]["rect"]), _centre(nodes[2]["rect"])
    sides = [_side(a, b, edges[i]["points"][8]) for i in (3, 4)]
    assert sides[0] * sides[1] < 0 and min(abs(x) for x in sides) >= 10
    loop = edges[2]
    assert all(p[1] < nodes[1]["rect"]["top"] for p in loop["points"])
    text = nested["done"]["say"]["text"]
    assert "The model gives no meaning for this state." in text
    assert 'The state "done" has no transition out.' in text


def test_a_phone(self_page: tuple[Path, dict[str, Any]]) -> None:
    """Acceptance 12."""
    out = _drive("--phone", self_page[0])
    for scheme in ("light", "dark"):
        o = out[scheme]
        for run in (o["shown"], o["second"]):
            s = run["states"]
            assert s["on"]
            assert s["railBox"]["top"] >= run["ask"]["bottom"] - 1
            assert s["view"]["top"] >= s["railBox"]["bottom"]
            assert run["scroll"] <= run["width"]
            for n in _items(run, "s"):
                assert all(t["px"] >= 7 for t in n["texts"]), n
            for e in _items(run, "t"):
                assert e["text"]["px"] >= 7, e
        assert o["tapped"]["states"]["pin"] == "t1" and o["tapped"]["say"]["on"]
        for run in (o["shown"], o["second"]):
            assert run["countsShown"] != "none" and run["view"]["counts"].endswith("transitions")
        assert o["second"]["states"]["more"] == [None, None]
        _all_in_view(o["second"])


def _all_in_view(run: dict[str, Any]) -> None:
    view = run["states"]["view"]
    for n in _items(run, "s"):
        r = n["rect"]
        assert view["left"] - 1 <= r["left"] and r["right"] <= view["right"] + 1, n["id"]
        assert view["top"] - 1 <= r["top"] and r["bottom"] <= view["bottom"] + 1, n["id"]


def test_more_machines_on_a_wide_screen(probe: dict[str, Any]) -> None:
    """Acceptance 15 and 16."""
    names = [o["shown"]["view"]["question"] for o in probe["wide"]]
    assert names[:3] == ["Life of a job", "A row", "Many lines"]
    for o in probe["wide"]:
        _geometry(o["shown"])
    job = probe["wide"][0]["shown"]
    nodes = {n["id"]: n for n in _items(job, "s")}
    cols = {round(_centre(nodes[i]["rect"])[0]) for i in ("idle", "running", "paused")}
    assert len(cols) == 1
    mid = _centre(nodes["running"]["rect"])[0]
    around = [e for e in _items(job, "t") if e["l"] in ("pause", "resume")]
    sides = [e["points"][8][0] - mid for e in around]
    assert (
        sides[0] * sides[1] < 0
        and min(abs(x) for x in sides) > nodes["running"]["rect"]["width"] / 2
    )


def test_more_machines_on_a_phone(probe: dict[str, Any]) -> None:
    """Acceptance 17."""
    for o in probe["phone"]:
        run = o["shown"]
        assert run["countsShown"] != "none"
        view = run["states"]["view"]
        out = [n for n in _items(run, "s") if n["rect"]["right"] > view["right"] + 1]
        if out:
            assert run["states"]["more"][0] is not None, run["view"]["question"]
        if run["states"]["more"][0] is None:
            continue
        after = o["more"]
        assert after["states"]["scrollAt"][0] > 0
        for n in _items(after, "s"):
            assert n["rect"]["right"] <= after["states"]["view"]["right"] + 1, n["id"]
    assert any("more" in o for o in probe["phone"])


def test_axe_finds_no_violation(self_page: tuple[Path, dict[str, Any]]) -> None:
    """Acceptance 13."""
    out = _drive("--axe", self_page[0])
    if out["axe"] is None:
        no_axe("the test needs axe-core on NODE_PATH")
    assert len(out["axe"]) == 4
    for r in out["axe"]:
        assert r["violations"] == [], r
