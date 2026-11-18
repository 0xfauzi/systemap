"""The Sequences view of the atlas page, in a browser (docs/design/atlas.md, stage 3).

The test drives real atlas pages in the Chromium of Playwright (tests/atlas_seq.js): the
map of this repository, and the fixture of tests/canvas_sequenced.py (a top map and the
nested map Gateway, each with sequences) with a second step in `serve` that names no flow
and an entry point list with no sequence (`_fixture`). A model check refuses a step that
names no flow, so the step goes into the page data. The test skips when Node or the
Playwright package is not there, except when SYSTEMAP_BROWSER_TESTS is "required". Then it
fails. The test of axe-core skips when axe-core is not on NODE_PATH, with the same exception.

Acceptance values, written before the first run on 2026-11-18:

1. The header has the button Sequences only when a map of the tree has a sequence. A click
   on it presses it, and the Map button is not pressed. The list at the left has one
   button for each sequence of the top map, with its count of steps, and the first is
   current. The headline gives "Sequence", the name of the sequence, its count of steps,
   and "starts at" and the entry point when the sequence has one. The layer tabs, the key
   and the note do not show. The bar gives "Whole route" and the button Start.
2. On the map, the drawn lines of the top map are the flows of the steps of the sequence,
   and no other flow. Each such line has a label that starts with the numbers of its
   steps. The other cards are quiet, and the cards of the steps are not.
3. The fit keeps the list and the bar free: on a screen of 1440 x 900 the frame of the map
   is at the right of the list and above the bar.
4. The step state. At step 2: the light is the flow of step 2 with the color of its kind,
   and its cards are lit. A line of an earlier step has the color --ink-2 and the alpha of
   a line at rest. A line of a later step has 0.4 times that alpha or less, and its label
   too. A card that is not lit keeps its alpha at rest: no card goes back. The bar gives
   "Step 2 of N" and the sentence of the step. The live region gives the step.
5. The arrow keys. With the keyboard focus on the Next button, the right arrow key goes to
   the next step and the left arrow key goes back, and the camera does not move. After the
   last step the step stays the last step. Done goes back to the whole route.
6. The diagram form: one column for each card of the steps, and one row for each step. At
   step 2, the row of step 2 is lit with the color of its kind, the earlier rows are done,
   and the later rows have an opacity of less than 0.5. The canvas does not show. A click
   on the row of step 3 goes to step 3. Enter on the focused row of step 1 goes to step 1.
   The map form shows the canvas again.
7. A click on Map shows the Map view again: the tabs show, the list does not show, and the
   lines of the layer of the Map view draw.
8. A nested map. The list has one group for each map with sequences, with the path of the
   map. A click on a sequence of Gateway moves the camera into Gateway. A step with no flow
   gives "This step has no flow" and its acting card in the bar, lights that card and no
   flow, and has the row "No flow" in the diagram.
9. The entry points with no sequence. The list gives the heading, the count, the short
   names, and "and N more". The page data of this repository gives the count of its entry
   points and the count with a sequence.
10. On a phone of 390 x 844 px, in the light and the dark scheme: the list is a row under
    the headline, the frame of the map starts under the row, the bar is fully on the
    screen, and the page has no horizontal scroll. At step 2, the cards of the step are
    fully in the free part of the screen.
11. With reduced motion, the line of the first step is fully drawn 50 ms after Start, and
    DIM is 1. Without it, the line is not fully drawn after 50 ms.
12. The page has no script error in each run. axe-core finds no serious or critical
    violation at step 2 on the map and in the diagram, in the light and the dark scheme, at
    1440 x 900 and at 390 x 844.

Acceptance values of the repair after the review, written before the first run on
2026-11-18:

13. The step labels (tests/atlas_seq.js --labels). For each sequence of the map of this
    repository, at the whole route and at each step, at 1440 x 900, 1000 x 800 and
    390 x 844 with reduced motion: each label on the screen whose line draws is on its own
    line (its box is 4 px or less from the line), or beside it: 64 px or less from its own
    line, and no other line is nearer to the box than half the height of the box less 1 px.
14. The line of the current step shows: of its length on the screen, the part that no label
    covers is 20 px or more, or half of the length or more.
15. The bar with the details open (tests/atlas_seq.js --open). At 1440 x 900 and at
    1000 x 800, a click on a card of step 2 opens the details. The bar is fully at the left
    of the details, the point at the right end of the button Next gives that button, and a
    click on it goes to step 3.
16. At 1000 x 800 (the middle media rule): the list and the entry points with no sequence
    are fully on the screen and above the bar, the entry points are below the list and not
    in its scroll, and the frame of the map is at the right of the list and above the bar.
    At 1440 x 900 the same for the list and the entry points.
17. The step state of a flow with two steps. In the nested fixture the top sequence gets a
    third step with the flow of step 1. At step 1 that flow is "now" and the flow of step 2
    is "later". At step 2 the first flow is "was" and the second is "now". At step 3 the
    first flow is "now" and the second is "was".
18. The arrow keys also change the step with the keyboard focus on the canvas and on a
    button of the list. The list of the map of this repository gives "All N entry points of
    this map have a sequence." when each entry point has a sequence. On a phone the
    headline gives the count of steps and "starts at" and the entry point.

Acceptance values of the second repair after the review, written before the first run on
2026-11-18. Acceptance 13 changes: a label beside its line touches it, so 64 px becomes
6 px.

13. (changed) Each label on the screen whose line draws is 6 px or less from its own line,
    and a label more than 4 px from its line has no other line nearer than half the height
    of its box less 1 px. The same on the nested fixture at 1440 x 900.
19. The bar with the details open (1440 x 900 and 1000 x 800, at step 3 and at the last
    step): the bar does not cover the list, the entry points with no sequence or the zoom
    control. The same at the whole route with no details.
20. At 1440 x 900 the bar of the whole route is 808 px wide outside.
21. At 1440 x 900, in each sequence of the map of this repository, at the whole route and
    at each step: the frame of the map is fully above the bar.
22. In the sequence "Make the initial map", at 1440 x 900 at the whole route, the label of
    step 1 is on a horizontal part of its line.
23. A label that shows only at its step (`hide`) does not show at the whole route, and at a
    step it shows only when its step is the current step or an earlier step.
24. On a phone in the diagram form, each card name and each flow label is 9 px high or
    more, and the row of the current step is fully in the part of the screen of the
    diagram. The current name of the list has an opaque background.
25. A pointer on a card of a later step at step 2 gives the usual light of that card (not
    the light of the step), and the light of step 2 comes back when the pointer goes.
26. The Reduce motion control of the header: the line of the first step is fully drawn
    50 ms after Start. The diagram draws again at a change of the screen size, in the new
    width. A sequence with `dr` gives "agent draft, source review necessary" in the
    headline.
27. The tags of the cards at step 2 of the first sequence: "acts" on each acting card of
    the step, "measures" on each measurement card that does not act, and "start" on the
    first card of the sequence when it has no other tag. The first card is the recorded
    start when it is a card, else the first acting card or the source of the first flow.

Acceptance values of the third repair after the review, written before the first run on
2026-11-18:

28. The diagram fits (tests/atlas_seq.js --fit). For each sequence of the map of this
    repository at the whole route, at 1440 x 900, 1280 x 720 and 390 x 844: when the scale
    of the diagram is more than BOARD_MIN (0.75), each card of the diagram is fully in the
    part of the screen of the diagram, and that part does not scroll (the scroll width and
    height are equal to the client width and height). At 1440 x 900 the scale of each
    diagram is more than BOARD_MIN.
29. On a phone of 390 x 844, at each step of each sequence of the map of this repository,
    the zoom of the map is 0.5 or more, and the target card of the step (the last card of
    the step) is fully in the free part of the screen.
30. On a phone of 390 x 844, in each sequence of the map of this repository, the dots of
    the bar are on the row of the step count (their vertical centres are 4 px apart or
    less), and the step controls have the same top in each sequence.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import canvas_sequenced
import pytest
from conftest import write_tree
from test_canvas_access import no_axe
from test_canvas_browser import browser

from systemap import atlas_data, atlas_page, canvas_page, config, facts_file, nest
from systemap.cli import main

ROOT = Path(__file__).resolve().parent
DRIVER = ROOT / "atlas_seq.js"
REPO = ROOT.parent
MISSING = ["tool one", "tool two", "tool three"]


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


@pytest.fixture(scope="module")
def self_page(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    cfg = config.load(REPO)
    tree = nest.load(cfg)
    data = atlas_data.build(cfg, tree, facts_file.read_facts(cfg.facts_path, cfg.root))
    return _write(tmp_path_factory.mktemp("seq") / "index.html", cfg, tree, data), data


@pytest.fixture(scope="module")
def nested_page(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    root = tmp_path_factory.mktemp("nseq")
    write_tree(root, canvas_sequenced.files())
    for command in ("place", "extract", "render"):
        assert main(["--root", str(root), command]) == 0
    cfg = config.load(root)
    tree = nest.load(cfg)
    data = atlas_data.build(cfg, tree, facts_file.read_facts(cfg.facts_path, cfg.root))
    data["maps"][1]["sq"][0]["s"].insert(
        1, {"f": -1, "a": ["Views"], "y": "The views make the page."}
    )
    data["maps"][0]["ne"] = {"t": 9, "c": 4, "x": MISSING, "mo": 2}
    data["maps"][1]["sq"][0]["dr"] = 1
    top = data["maps"][0]["sq"][0]["s"]
    top.append({**top[0], "y": "The first flow again."})
    return _write(root / "atlas.html", cfg, tree, data), data


@pytest.fixture(scope="module")
def wide(self_page: tuple[Path, dict[str, Any]]) -> dict[str, Any]:
    return _drive("--wide", self_page[0])


def _top_sq(data: dict[str, Any]) -> list[dict[str, Any]]:
    return list(data["maps"][0]["sq"])


def _drawn(run: dict[str, Any], kind: str, map_id: str = "") -> list[dict[str, Any]]:
    """The marks of `kind` of map `map_id` in the frame of a state."""
    out, current = [], None
    for m in run["drawn"]["marks"]:
        if m["t"] == "map":
            current = m["id"]
        elif m["t"] == kind and current == map_id:
            out.append(m)
    return out


def test_the_view_shows_only_with_a_sequence(tmp_path: Path) -> None:
    """Acceptance 1: the button."""
    cfg = config.load(REPO)
    tree = nest.load(cfg)
    data = atlas_data.build(cfg, tree, facts_file.read_facts(cfg.facts_path, cfg.root))
    t = canvas_page.tree_theme(cfg, tree)
    assert '<button type="button" data-mode="seq"' in atlas_page.build(t, data)
    for m in data["maps"]:
        m.pop("sq", None)
    assert '<button type="button" data-mode="seq"' not in atlas_page.build(t, data)


def test_the_list_the_headline_and_the_bar(
    self_page: tuple[Path, dict[str, Any]], wide: dict[str, Any]
) -> None:
    """Acceptance 1."""
    sq = _top_sq(self_page[1])
    whole = wide["whole"]
    assert whole["pressed"] == [["Map", "false"], ["Sequences", "true"], ["States", "false"]]
    rail = whole["seq"]["view"]["rail"]
    assert len(rail) == len(sq)
    for item, q in zip(rail, sq, strict=True):
        assert item["text"].startswith(q["n"] + str(len(q["s"])))
    assert [r["on"] for r in rail] == [True] + [False] * (len(sq) - 1)
    view = whole["view"]
    assert view["kicker"] == "Sequence" and view["question"] == sq[0]["n"]
    want = f"{len(sq[0]['s'])} steps"
    assert view["counts"].startswith(want)
    if sq[0].get("en"):
        assert f"starts at {sq[0]['en']}" in view["counts"]
    assert whole["tabs"] == whole["key"] == whole["note"] == "none"
    bar = whole["seq"]["view"]["bar"]
    assert bar["n"] == "Whole route" and bar["next"].startswith("Start") and bar["prev"] is False


def test_the_map_shows_only_the_flows_of_the_sequence(
    self_page: tuple[Path, dict[str, Any]], wide: dict[str, Any]
) -> None:
    """Acceptance 2."""
    top = self_page[1]["maps"][0]
    q = _top_sq(self_page[1])[0]
    flows = {s["f"] for s in q["s"] if s["f"] >= 0}
    lines = _drawn(wide["whole"], "line")
    assert {m["f"] for m in lines} == flows
    labels = {m["f"]: m["s"] for m in _drawn(wide["whole"], "label")}
    assert set(labels) == flows
    for f, text in labels.items():
        nums = [str(k + 1) for k, s in enumerate(q["s"]) if s["f"] == f]
        assert text.startswith(", ".join(nums) + " "), (f, text)
    used = {top["flows"][f][e] for f in flows for e in ("s", "t")}
    used |= {c for s in q["s"] for c in s.get("a", []) + s.get("me", [])}
    quiet = {c["id"] for c in wide["whole"]["quiet"] if c["q"]}
    assert quiet == {c["id"] for c in top["cards"]} - used


def test_the_fit_keeps_the_list_and_the_bar_free(wide: dict[str, Any]) -> None:
    """Acceptance 3."""
    whole = wide["whole"]
    frame, rail, bar = whole["frame"], whole["seq"]["view"]["railBox"], whole["seq"]["view"]["bar"]
    assert frame[0] >= rail["right"]
    assert frame[1] + frame[3] <= bar["box"]["top"]


def _tok(run: dict[str, Any], name: str) -> str:
    return str(run["tokens"][name]).lower()


KIND = {"data": "--data", "control": "--control", "judge": "--judge", "context": "--context"}


def test_the_step_state(self_page: tuple[Path, dict[str, Any]], wide: dict[str, Any]) -> None:
    """Acceptance 4."""
    top = self_page[1]["maps"][0]
    q = _top_sq(self_page[1])[0]
    second = wide["second"]
    st = q["s"][1]
    assert second["seq"]["view"]["step"] == 1
    assert second["lit"]["flows"] == ([st["f"]] if st["f"] >= 0 else [])
    lit = _drawn(second, "lit")
    if st["f"] >= 0:
        f = top["flows"][st["f"]]
        assert [m["f"] for m in lit] == [st["f"]]
        assert lit[0]["color"].lower() == _tok(second, KIND.get(f["k"], "--ink-2"))
        assert {f["s"], f["t"]} <= set(second["lit"]["cards"])
    first = {}
    for k, s in enumerate(q["s"]):
        if s["f"] >= 0:
            first.setdefault(s["f"], k)
    rest = {m["f"]: m["alpha"] for m in _drawn(wide["whole"], "line")}
    for m in _drawn(second, "line"):
        f = m["f"]
        if f == st["f"]:
            continue
        if first[f] < 1:
            assert m["step"] == "was" and m["color"].lower() == _tok(second, "--ink-2")
            assert abs(m["alpha"] - rest[f]) < 1e-6
        else:
            assert m["step"] == "later" and m["alpha"] <= 0.4 * rest[f] + 1e-6
    for m in _drawn(second, "label"):
        if m["f"] != st["f"] and first[m["f"]] > 1:
            assert m["alpha"] <= 0.4 + 1e-6
    before = {m["id"]: m["alpha"] for m in _drawn(wide["whole"], "card")}
    for m in _drawn(second, "card"):
        assert abs(m["alpha"] - before[m["id"]]) < 1e-6, m
    bar = second["seq"]["view"]["bar"]
    assert bar["n"] == f"Step 2 of {len(q['s'])}"
    assert bar["p"].startswith(st.get("y", "This step has no sentence."))
    assert second["said"].startswith(f"Step 2 of {len(q['s'])}: ")


def test_the_arrow_keys_change_the_step(wide: dict[str, Any]) -> None:
    """Acceptance 5."""
    n = wide["whole"]["seq"]["view"]["n"]
    assert wide["right"]["active"] == "atlas-step-next"
    assert wide["right"]["seq"]["view"]["step"] == 2
    assert wide["left"]["seq"]["view"]["step"] == 1
    assert wide["right"]["camera"] == wide["second"]["camera"] == wide["left"]["camera"]
    assert wide["last"]["seq"]["view"]["step"] == n - 1
    assert wide["last"]["seq"]["view"]["bar"]["next"] == "Done"
    assert wide["done"]["seq"]["view"]["step"] == -1
    assert wide["done"]["seq"]["view"]["bar"]["n"] == "Whole route"


def test_the_diagram_form(self_page: tuple[Path, dict[str, Any]], wide: dict[str, Any]) -> None:
    """Acceptance 6."""
    top = self_page[1]["maps"][0]
    q = _top_sq(self_page[1])[0]
    diagram = wide["diagram"]
    assert diagram["seq"]["view"]["form"] == "diagram" and diagram["seq"]["view"]["step"] == 1
    board = diagram["seq"]["board"]
    assert board["on"] is True and diagram["canvas"] == "hidden"
    cards: list[str] = []
    for s in q["s"]:
        f = top["flows"][s["f"]] if s["f"] >= 0 else None
        for c in [f["s"], f["t"]] if f else s.get("a", []) + s.get("me", []):
            if c not in cards:
                cards.append(c)
    assert len(board["nodes"]) == len(cards)
    rows = board["rows"]
    assert len(rows) == len(q["s"])
    assert rows[1]["current"] == "step" and "lit" in rows[1]["cls"]
    if q["s"][1]["f"] >= 0:
        assert rows[1]["k"] == f"var({KIND.get(top['flows'][q['s'][1]['f']]['k'], '--ink-2')})"
    assert "done" in rows[0]["cls"]
    for r in rows[2:]:
        assert float(r["opacity"]) < 0.5, r
    assert wide["rowClick"]["seq"]["view"]["step"] == 2
    assert wide["rowKey"]["seq"]["view"]["step"] == 0
    assert wide["onMap"]["canvas"] == "visible" and wide["onMap"]["seq"]["view"]["form"] == "map"


def test_the_map_view_comes_back(
    self_page: tuple[Path, dict[str, Any]], wide: dict[str, Any]
) -> None:
    """Acceptance 7."""
    back = wide["map"]
    assert back["pressed"] == [["Map", "true"], ["Sequences", "false"], ["States", "false"]]
    assert back["view"]["mode"] == "map" and back["tabs"] != "none"
    assert back["seq"]["view"]["railBox"]["width"] == 0
    assert {m["f"] for m in _drawn(back, "line")} == {
        m["f"] for m in _drawn(wide["before"], "line")
    }


@pytest.fixture(scope="module")
def nested(nested_page: tuple[Path, dict[str, Any]]) -> dict[str, Any]:
    return _drive("--nested", nested_page[0])


def test_a_sequence_of_a_nested_map_and_a_step_with_no_flow(nested: dict[str, Any]) -> None:
    """Acceptance 8."""
    assert nested["groups"] == ["join", "join / Gateway"]
    assert nested["top"]["current"] == ""
    assert nested["chosen"]["current"] == "Gateway"
    assert nested["chosen"]["seq"]["view"]["id"] == "serve"
    noflow = nested["noflow"]
    assert noflow["seq"]["view"]["step"] == 1
    assert "This step has no flow. Its cards: Views." in noflow["seq"]["view"]["bar"]["p"]
    assert noflow["lit"]["flows"] == [] and noflow["lit"]["cards"] == ["Views"]
    assert _drawn(noflow, "lit", "Gateway") == []
    texts = [r["text"] for r in nested["diagram"]["seq"]["board"]["rows"]]
    assert texts[1].startswith("No flow")


def test_the_entry_points_with_no_sequence(nested: dict[str, Any]) -> None:
    """Acceptance 9: the list."""
    ne = nested["top"]["seq"]["view"]["ne"]
    assert ne.startswith("Entry points with no sequence5 of 9")
    for name in MISSING:
        assert name in ne
    assert ne.endswith("and 2 more")


def test_the_page_data_counts_the_entry_points(self_page: tuple[Path, dict[str, Any]]) -> None:
    """Acceptance 9: the data."""
    cfg = config.load(REPO)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    ne = self_page[1]["maps"][0]["ne"]
    assert (
        0 < ne["t"] <= len(facts["entry_points"]) and ne["c"] == ne["t"] - len(ne["x"]) - ne["mo"]
    )
    tree = nest.load(cfg)
    extra = {
        "kind": "subcommand",
        "name": "zzz-none",
        "module": "systemap.cli",
        "target": "systemap",
        "function": "main",
    }
    more = dict(facts, entry_points=[*facts["entry_points"], extra])
    data = atlas_data.build(cfg, tree, more)
    assert "systemap zzz-none" in data["maps"][0]["ne"]["x"]


def _inside(b: list[float], free: dict[str, float]) -> bool:
    return (
        b[0] >= free["x0"] - 1
        and b[1] >= free["y0"] - 1
        and b[0] + b[2] <= free["x1"] + 1
        and b[1] + b[3] <= free["y1"] + 1
    )


def test_the_phone(self_page: tuple[Path, dict[str, Any]]) -> None:
    """Acceptance 10."""
    run = _drive("--phone", self_page[0])
    for scheme in ("light", "dark"):
        r = run[scheme]
        assert r["errors"] == []
        whole = r["whole"]
        rail, ask = whole["seq"]["view"]["railBox"], whole["ask"]
        assert rail["top"] >= ask["bottom"] and rail["height"] < 70 and rail["width"] > 300
        assert whole["frame"][1] >= rail["bottom"]
        bar = whole["seq"]["view"]["bar"]["box"]
        assert bar["top"] >= 0 and bar["bottom"] <= 844 and bar["left"] >= 0 and bar["right"] <= 390
        assert whole["scroll"] <= 390
        first = self_page[1]["maps"][0]["sq"][0]
        n = whole["askN"]
        assert n["display"] != "none" and n["box"]["height"] > 0, n
        assert n["box"]["bottom"] <= rail["top"]
        if first.get("en"):
            assert f"starts at {first['en']}" in n["text"]
        step = r["step"]
        assert step["seq"]["view"]["step"] == 1
        for b in step["cards"]:
            assert _inside(b, step["seq"]["view"]["free"]), (b, step["seq"]["view"]["free"])


def test_reduced_motion(self_page: tuple[Path, dict[str, Any]]) -> None:
    """Acceptance 11."""
    run = _drive("--motion", self_page[0])
    assert run["reduce"]["dim"] == 1 and run["reduce"]["parts"] == [1]
    assert run["no-preference"]["parts"] and run["no-preference"]["parts"][0] < 1


def test_axe_finds_no_violation(self_page: tuple[Path, dict[str, Any]]) -> None:
    """Acceptance 12."""
    runs = _drive("--axe", self_page[0])["runs"]
    if any(r["axe"] is None for r in runs):
        no_axe("the test needs axe-core on NODE_PATH")
    assert len(runs) == 8
    for r in runs:
        assert r["errors"] == [], r
        assert r["axe"]["violations"] == [], r


LABEL_SIZES = [(1440, 900), (1000, 800), (390, 844)]


@pytest.fixture(scope="module", params=LABEL_SIZES, ids=lambda v: f"{v[0]}x{v[1]}")
def labelled(
    request: pytest.FixtureRequest, self_page: tuple[Path, dict[str, Any]]
) -> dict[str, Any]:
    w, h = request.param
    return {"w": w, **_drive_size("--labels", self_page[0], w, h)}


def _drive_size(mode: str, page: Path, w: int, h: int) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), mode, str(page), str(w), str(h)],
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert proc.returncode == 0, proc.stderr
    out = dict(json.loads(proc.stdout))
    assert out.get("errors", []) == [], out.get("errors")
    return out


def test_each_step_label_is_at_its_own_line(
    self_page: tuple[Path, dict[str, Any]], labelled: dict[str, Any]
) -> None:
    """Acceptance 13."""
    count = sum(len(q["s"]) + 1 for m in self_page[1]["maps"] for q in m.get("sq") or [])
    assert len(labelled["runs"]) == count
    seen = 0
    for run in labelled["runs"]:
        for lab in run["labels"]:
            seen += 1
            where = (run["k"], run["step"], lab)
            assert lab["own"] <= 6, where
            if lab["own"] <= 4:
                continue
            assert lab["other"] >= lab["h"] / 2 - 1, where
    assert seen > 0


def test_the_line_of_the_current_step_shows(labelled: dict[str, Any]) -> None:
    """Acceptance 14."""
    lit = 0
    for run in labelled["runs"]:
        for line in run["lit"]:
            lit += 1
            assert line["free"] >= min(20, line["all"] / 2), (run["k"], run["step"], line)
    assert lit > 0


@pytest.fixture(scope="module", params=[(1440, 900), (1000, 800)], ids=["1440", "1000"])
def opened(
    request: pytest.FixtureRequest, self_page: tuple[Path, dict[str, Any]]
) -> dict[str, Any]:
    w, h = request.param
    return {"w": w, "h": h, **_drive_size("--open", self_page[0], w, h)}


def test_the_bar_with_the_details_open(opened: dict[str, Any]) -> None:
    """Acceptance 15."""
    side, bar = opened["side"], opened["bar"]
    assert side["width"] > 0 and side["right"] <= opened["w"] + 1
    assert bar["left"] >= 0 and bar["right"] <= side["left"]
    assert opened["next"]["right"] <= side["left"] and opened["nextHit"] is True
    assert opened["after"] == 2


def test_the_list_and_the_entry_points_fit(opened: dict[str, Any]) -> None:
    """Acceptance 16."""
    lst, ne = opened["list"]["box"], opened["ne"]
    bar = opened["bar"]
    assert lst["height"] > 0 and lst["top"] >= 0
    assert ne["height"] > 0 and ne["top"] >= lst["bottom"] and ne["bottom"] <= opened["h"]
    assert ne["bottom"] <= bar["top"] or ne["right"] <= bar["left"]
    if opened["w"] < 1181:
        bar = opened["whole"]["seq"]["view"]["bar"]["box"]
        assert ne["bottom"] <= bar["top"]
        frame, rail = opened["whole"]["frame"], opened["whole"]["seq"]["view"]["railBox"]
        assert frame[0] >= rail["right"] and frame[1] + frame[3] <= bar["top"]


def test_a_flow_with_two_steps(
    nested_page: tuple[Path, dict[str, Any]], nested: dict[str, Any]
) -> None:
    """Acceptance 17."""
    steps = nested_page[1]["maps"][0]["sq"][0]["s"]
    a, b = steps[0]["f"], steps[1]["f"]
    assert a >= 0 and b >= 0 and a != b and steps[2]["f"] == a
    got = [(v["step"], v["states"][a], v["states"][b]) for v in nested["steps"]]
    assert got == [(0, "now", "later"), (1, "was", "now"), (2, "now", "was")]


def test_more_keys_and_texts(self_page: tuple[Path, dict[str, Any]], wide: dict[str, Any]) -> None:
    """Acceptance 18."""
    assert wide["canvasRight"]["active"] == "canvas"
    assert wide["canvasRight"]["seq"]["view"]["step"] == wide["left"]["seq"]["view"]["step"] + 1
    assert wide["railLeft"]["seq"]["view"]["step"] == wide["canvasRight"]["seq"]["view"]["step"] - 1
    ne = self_page[1]["maps"][0]["ne"]
    if ne["t"] == ne["c"]:
        assert wide["whole"]["seq"]["view"]["ne"] == (
            f"All {ne['t']} entry points of this map have a sequence."
        )


def _apart(a: dict[str, float], b: dict[str, float]) -> bool:
    return (
        a["right"] <= b["left"] + 0.5
        or b["right"] <= a["left"] + 0.5
        or a["bottom"] <= b["top"] + 0.5
        or b["bottom"] <= a["top"] + 0.5
    )


def test_the_bar_covers_no_list(opened: dict[str, Any]) -> None:
    """Acceptance 19."""
    whole = opened["whole"]["seq"]["view"]
    states = [
        (opened["bar"], opened["openNe"], opened["openList"], opened["zoom"]),
        (
            opened["late"]["bar"],
            opened["late"]["ne"],
            opened["late"]["list"],
            opened["late"]["zoom"],
        ),
        (whole["bar"]["box"], opened["ne"], opened["list"]["box"], opened["zoom"]),
    ]
    assert opened["late"]["step"] == whole["n"] - 1 and opened["late"]["side"]["width"] > 0
    for bar, ne, lst, zoom in states:
        for other in (ne, lst, zoom):
            if other["width"] > 0:
                assert _apart(bar, other), (bar, other)


def test_the_bar_width(wide: dict[str, Any]) -> None:
    """Acceptance 20."""
    assert abs(wide["whole"]["seq"]["view"]["bar"]["box"]["width"] - 808) < 1


def test_the_frame_stays_above_the_bar(labelled: dict[str, Any]) -> None:
    """Acceptance 21."""
    if labelled["w"] != 1440:
        pytest.skip("acceptance 21 is for 1440 x 900")
    for run in labelled["runs"]:
        frame = run["frame"]
        assert frame[1] + frame[3] <= run["barTop"] + 1, (run["k"], run["step"], frame, run["bar"])


def test_the_first_label_is_on_a_horizontal_part(
    self_page: tuple[Path, dict[str, Any]], labelled: dict[str, Any]
) -> None:
    """Acceptance 22."""
    if labelled["w"] != 1440:
        pytest.skip("acceptance 22 is for 1440 x 900")
    ids = [q["id"] for q in _top_sq(self_page[1]) if q["n"] == "Make the initial map"]
    if not ids:
        pytest.skip("the map has no sequence Make the initial map")
    runs = [r for r in labelled["runs"] if r["name"] == ids[0] and r["step"] == -1]
    assert len(runs) == 1
    first = [lab for lab in runs[0]["labels"] if lab["s"].startswith("1 ")]
    assert first and first[0]["flat"], first


def test_hidden_labels_show_at_their_step(labelled: dict[str, Any]) -> None:
    """Acceptance 23."""
    for run in labelled["runs"]:
        hidden = set(run["hidden"])
        for lab in run["labels"]:
            if lab["f"] not in hidden or lab["t"] != "label":
                continue
            assert run["step"] >= 0 and lab["step"] in ("now", "was"), (run["k"], run["step"], lab)


def test_the_labels_of_a_nested_map(nested_page: tuple[Path, dict[str, Any]]) -> None:
    """Acceptance 13 on the nested fixture."""
    run = _drive_size("--labels", nested_page[0], 1440, 900)
    seen = 0
    for r in run["runs"]:
        for lab in r["labels"]:
            seen += 1
            assert lab["own"] <= 6, (r["map"], r["k"], r["step"], lab)
            if lab["own"] > 4:
                assert lab["other"] >= lab["h"] / 2 - 1, (r["map"], r["k"], r["step"], lab)
        for line in r["lit"]:
            assert line["free"] >= min(20, line["all"] / 2), (r["map"], r["step"], line)
    assert seen > 0


def test_the_phone_diagram(self_page: tuple[Path, dict[str, Any]]) -> None:
    """Acceptance 24."""
    run = _drive("--phone", self_page[0])
    for scheme in ("light", "dark"):
        r = run[scheme]
        assert "rgba" not in r["step"]["railBg"] or r["step"]["railBg"].endswith(", 1)")
        board = r["diagram"]["seq"]["board"]
        assert board["on"] is True and board["texts"]
        assert min(board["texts"]) >= 9, board["texts"]
        view = board["view"]
        cur = [row for row in board["rows"] if row["current"] == "step"]
        assert len(cur) == 1
        box = cur[0]["box"]
        assert box["top"] >= view["top"] - 1 and box["bottom"] <= view["bottom"] + 1, (box, view)


def test_a_pointer_during_a_step(wide: dict[str, Any]) -> None:
    """Acceptance 25."""
    p = wide["pointed"]
    if p is None:
        pytest.skip("the first sequence has no flow after step 2")
    assert p["on"]["step"] is False and p["card"] in p["on"]["cards"]
    assert p["off"]["step"] is True
    assert p["off"]["flows"] == wide["second"]["lit"]["flows"]


def test_the_motion_control_the_resize_and_a_draft(
    self_page: tuple[Path, dict[str, Any]], wide: dict[str, Any], nested: dict[str, Any]
) -> None:
    """Acceptance 26."""
    run = _drive("--motion", self_page[0])
    assert run["button"]["errors"] == [] and run["button"]["pressed"] == "true"
    assert run["button"]["parts"] == [1]
    before, after = wide["diagram"]["seq"]["board"], wide["resized"]["seq"]["board"]
    assert after["on"] is True and after["nodes"] and before["nodes"]
    assert after["view"]["right"] <= 1000 and after["view"]["width"] < before["view"]["width"]
    assert after["nodes"][0]["box"] != before["nodes"][0]["box"]
    assert "agent draft, source review necessary" in nested["chosen"]["view"]["counts"]


def test_the_tags_of_the_cards(
    self_page: tuple[Path, dict[str, Any]], wide: dict[str, Any]
) -> None:
    """Acceptance 27."""
    top = self_page[1]["maps"][0]
    q = _top_sq(self_page[1])[0]
    st = q["s"][1]
    want = {c: "measures" for c in st.get("me", [])}
    want.update({c: "acts" for c in st.get("a", [])})
    first = q["s"][0]
    cards = {c["id"] for c in top["cards"]}
    start = q.get("st") if q.get("st") in cards else (first.get("a") or [None])[0]
    if not start and first["f"] >= 0:
        start = top["flows"][first["f"]]["s"]
    if start and start not in want:
        want[start] = "start"
    got = {m["id"]: m["s"] for m in _drawn(wide["second"], "tag")}
    assert got == want


FIT_SIZES = [(1440, 900), (1280, 720), (390, 844)]
BOARD_MIN = 0.75


@pytest.fixture(scope="module", params=FIT_SIZES, ids=lambda v: f"{v[0]}x{v[1]}")
def fitted(
    request: pytest.FixtureRequest, self_page: tuple[Path, dict[str, Any]]
) -> dict[str, Any]:
    w, h = request.param
    return {"w": w, **_drive_size("--fit", self_page[0], w, h)}


def test_the_diagram_fits(self_page: tuple[Path, dict[str, Any]], fitted: dict[str, Any]) -> None:
    """Acceptance 28."""
    count = sum(len(m.get("sq") or []) for m in self_page[1]["maps"])
    assert len(fitted["runs"]) == count
    for run in fitted["runs"]:
        board = run["board"]
        if fitted["w"] == 1440:
            assert board["k"] > BOARD_MIN + 1e-6, run["k"]
        if board["k"] <= BOARD_MIN + 1e-6:
            continue
        view, (sw, sh, cw, ch) = board["view"], board["scroll"]
        assert (sw, sh) == (cw, ch), (run["k"], board["scroll"])
        for node in board["nodes"]:
            b = node["box"]
            assert b["left"] >= view["left"] - 0.5 and b["right"] <= view["right"] + 0.5, (
                run["k"],
                node,
                view,
            )
            assert b["top"] >= view["top"] - 0.5 and b["bottom"] <= view["bottom"] + 0.5


def test_the_phone_step_zoom(labelled: dict[str, Any]) -> None:
    """Acceptance 29."""
    if labelled["w"] != 390:
        pytest.skip("acceptance 29 is for 390 x 844")
    steps = [run for run in labelled["runs"] if run["step"] >= 0]
    assert steps
    for run in steps:
        assert run["zoom"] >= 0.5 - 1e-6, (run["k"], run["step"], run["zoom"])
        assert run["cards"], (run["k"], run["step"])
        assert _inside(run["cards"][-1], run["free"]), (run["k"], run["step"], run["cards"])


def test_the_phone_bar_rows(fitted: dict[str, Any]) -> None:
    """Acceptance 30."""
    if fitted["w"] != 390:
        pytest.skip("acceptance 30 is for 390 x 844")
    tops = set()
    for run in fitted["runs"]:
        dots, n = run["dots"], run["count"]
        mid = abs((dots["top"] + dots["bottom"]) / 2 - (n["top"] + n["bottom"]) / 2)
        assert mid <= 4, (run["k"], dots, n)
        tops.add(round(run["nav"]["top"], 1))
    assert len(tops) == 1, tops
