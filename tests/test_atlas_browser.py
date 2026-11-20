"""The Map view of the atlas page at rest, in a browser (docs/design/atlas.md, stage 1).

The test drives real atlas pages in the Chromium of Playwright (tests/atlas_map.js): the
map of this repository, the model of tests/fixture_workspace.py with the positions of the
placer, and the fixture of tests/test_canvas_page.py, which has the nested map Gateway. The
test skips when Node or the Playwright package is not there, except when
SYSTEMAP_BROWSER_TESTS is "required". Then it fails. The test of axe-core skips when
axe-core is not on NODE_PATH, with the same exception.

Acceptance values, written before the first run on 2026-11-18:

1. The page has no script error. It opens with the layer System context, and the headline
   gives the name and the question of that layer and the counts of its actors, components
   and flows. Each tab gives a layer of the top map that has flows, Structure, or All.
2. For each tab: the selected tab, the name and the question of the headline are of that
   layer. The lines are the flows of the layer. The layer is busy when it has more than 48
   flows: then no label shows at rest. The alpha of a line at rest is 1.25 - n / 56, from
   0.3 to 1. A quiet card is a card that no flow of the layer touches, in a layer with
   flows.
3. Lanes: no two lines of a layer have segments on the same line with an overlap of more
   than 2 units. Thus N flows show as N lines.
4. Labels at rest: each drawn label is the label of a line of the layer, with the alpha 1
   and a size of 9 px or more. No label covers a card or a different label.
5. The headline does not cover the frame of the map: the map is beside the headline or
   below it. On the wide screen of the self-map, the headline is beside the map.
6. The dot grid has a cell of 17 px to 34 px on the screen.
7. The short name of a card shows at a scale of 1.2, and it does not show at the fit of the
   self-map (a scale below 0.95). The zoom readout gives 120%.
8. The arrow key moves the keyboard focus to the next tab and does not change the layer.
   Enter selects the layer.
9. On a phone of 390 x 844 px, the map opens at a scale of 0.5 or more with the frame of the
   map at its top left, and the page has no horizontal scroll. After a click on Fit, the
   whole width of the map is on the screen.
10. A double-click on the card Gateway goes into its nested map: the chain is Gateway, the
    headline gives the path with a button for the top map, and the hash is #Gateway. Esc
    goes out to the top map. A load with #Gateway opens the nested map, and a click on the
    first part of the path goes to the top map.
11. axe-core finds no serious or critical violation in the light and the dark scheme, at
    1440 x 900 and at 390 x 844.

Acceptance values 12 to 20, written on 2026-11-18 for the repair of stage 1, before the
first run of these tests:

12. After the double-click of acceptance 10, the live region gives the open map and not a
    selection, and the canvas is the same picture as after a load with #Gateway: 1 % of its
    blocks of 4 x 4 pixels or less differ.
13. Each line of each layer has its wire, a casing that is wider than the wire, a dot at its
    first point and an arrowhead at its last point. The canvas at each arrowhead does not
    have the color of the ground.
14. A card that is not a component and not an actor has the tag of its kind inside its box.
    An actor has round ends: its corner radius is half of its height. A container that holds
    only actors is a label with no surface. The tints of two regions do not touch.
15. No other line goes through a label at rest, and a label at rest is on no name of a
    region or a container. The labels at rest have the same size at three zooms.
16. The dot grid as the canvas draws it, at the zooms 0.45, 1, 1.6 and 3.3: each dot has a
    size of 1.5 px to 3.5 px, the sizes at all zooms differ by 1 px or less, and the
    distance between two adjacent dots is from 17 px to 34 px.
17. The wheel zooms at the pointer: the world point under the pointer stays in 0.5 units,
    and the zoom increases. A drag moves the camera by the drag divided by the zoom. A pinch
    that doubles the distance of two fingers doubles the zoom, and the world point between
    the fingers stays.
18. With reduced motion, the camera is at the nested map 60 ms after the double-click, and
    no line fades after a change of the layer. Without it, the camera is not yet there
    after 60 ms, and the lines fade.
19. The position of the headline gives the larger fit: the scale of the fit is the larger of
    the two fits. The self-map is beside the headline, and the wide workspace map is below
    it.
20. A card that opens a map has a second edge and the small picture of its map in its box.
    While the camera goes into the nested map, the alpha of the map above goes down, and it
    is 0 when the nested map has the screen. On a phone, at the open and after Fit, each
    card of the top map has its shape and its name. At the open, the names of the regions
    and the containers and the kind tags show.

Acceptance value 21, written on 2026-11-19 for the repair of stage 7, before the first run
of this test:

21. Before the reader selects a layer, a nested map shows its first layer System context
    with the name Neighbours, as in the study: after the double-click and after a load
    with #Gateway, the shown layer is "system", the selected tab is Neighbours, and the
    question is "Which neighbours connect to Gateway?". The top map of the fixture, which
    has no System context, shows All before the dive and after Esc.

Acceptance value 22, written on 2026-11-19 for the repair of stage 10, before the first run
of this test:

22. A label at rest stays in the box of its map. For each layer tab of the top map of the
    self-map and of its nested map Page (opened with #Page): at 1440 x 900 at the fit, and
    at 390 x 844 at the open and after a click on Fit, the screen box of each label at rest
    of that map (`systemapCanvas.lines`) is inside the frame of the map, with 0.5 px of
    tolerance. After Fit on the phone, each such box is also inside the width of the
    screen. Each of the two maps shows at least one label at rest.

Acceptance value 23, written on 2026-11-19 for the second repair of stage 10, from the rules
"Nested maps" and "Neighbours of a nested map" of docs/design/atlas.md and from the model
files. A run of the driver before this text only found the names of the page API, and the
values below do not come from it:

23. The nested map Page of the self-map, opened with #Page at 1440 x 900: the page has no
    script error and the chain is Page. The parts of Page in the page are the components
    of map/page.py that are not actors, and there are 11. The frame draws each part with
    its name. The neighbours are the actors of map/page.py, and they are the cards of the
    top map that have a flow with Page. For each layer tab, the counts of the headline are
    the counts of the model (`model.reading`): the neighbours and the parts that the flows
    of the layer touch, and the flows; for a layer with no flow, the cards and the
    regions. A mouse click on each neighbour goes out to the top map and selects the card
    of the top map with the same name.

Acceptance values 24 to 26, written on 2026-11-19 for the third repair of stage 10, before
the first run of these tests. A run of the driver before this text gave the names of the
values only:

24. The counts of the headline of Page are the counts from the text of map/page.py, found
    with no systemap code (`_text_counts`): the flows of the layer by their kind (each
    flow with a neighbour for Neighbours), the neighbours and the parts that these flows
    touch, and for Structure the components and the regions.
    Changed on 2026-11-20 by the decision of the maintainer "a total is always the total"
    (Z2 in tests/test_atlas_inside_browser.py), before the run: when a layer touches fewer
    neighbours or parts than the map has, the count is "N of T", and else "T".
25. With the keyboard, on #Page: Tab on the canvas to each neighbour gives the keyboard
    focus to that card of Page, and Enter goes out to the top map and selects the card of
    the top map with the same name.
26. The rule "Neighbours of a nested map": on #Page, at 1440 x 900 at the fit and at
    390 x 844 after a click on Fit, in the light and the dark scheme, the neighbours are at
    three sides or more of the box of the parts, and no side has all of them. A neighbour
    is at a side when its screen box is fully outside the box of the parts at that side.
    The chain is Page, the dark scheme has a dark ground, and the page has no horizontal
    scroll.

Acceptance value 27, written on 2026-11-20 from Z2 of the coordinator, before the first run:

27. On the top map, in each layer tab with flows, the counts of the headline give the totals
    of the map: "N of T components" when the layer touches N of the T components, and "T
    components" when it touches all. The same rule for the actors.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest
from test_canvas_access import no_axe
from test_canvas_browser import browser
from test_canvas_page import _made

from systemap import atlas_data, atlas_page, canvas_page, config, facts_file, nest, place

ROOT = Path(__file__).resolve().parent
DRIVER = ROOT / "atlas_map.js"
REPO = ROOT.parent


def _drive(mode: str, page: Path, *rest: str) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), mode, str(page), *rest],
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, proc.stderr
    return dict(json.loads(proc.stdout))


@pytest.fixture(scope="module")
def self_page(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    cfg = config.load(REPO)
    tree = nest.load(cfg)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    data = atlas_data.build(cfg, tree, facts)
    out = tmp_path_factory.mktemp("atlas") / "index.html"
    out.write_text(atlas_page.build(canvas_page.tree_theme(cfg, tree), data), encoding="utf-8")
    return out, data


@pytest.fixture(scope="module")
def workspace_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    sys.path.insert(0, str(ROOT))
    import fixture_workspace as fw  # noqa: PLC0415

    laid = place.apply(fw.MODEL, place.compute(fw.MODEL, all_cards=True))
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "systemap.toml").write_text('name = "workspace"\n', encoding="utf-8")
        cfg = config.load(Path(tmp))
    theme = nest.load(config.load(REPO)).top.theme
    one = nest.Map(
        id="", path=Path("m.py"), rel="m.py", model=laid, meaning=fw.MEANING, theme=theme
    )
    tree = nest.Tree(maps=(one,))
    data = atlas_data.build(cfg, tree, fw.facts())
    out = tmp_path_factory.mktemp("workspace") / "index.html"
    out.write_text(atlas_page.build(canvas_page.tree_theme(cfg, tree), data), encoding="utf-8")
    return out


@pytest.fixture(scope="module")
def nested_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = _made(tmp_path_factory.mktemp("nested"), '[render]\npage = "atlas"\n')
    return root / "docs" / "map" / "index.html"


@pytest.fixture(scope="module")
def self_rest(self_page: tuple[Path, dict[str, Any]]) -> dict[str, Any]:
    return _drive("--rest", self_page[0])


def _over(a: list[float], b: list[float]) -> bool:
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def test_the_page_opens_with_the_first_layer(
    self_page: tuple[Path, dict[str, Any]], self_rest: dict[str, Any]
) -> None:
    """Acceptance 1."""
    top = self_page[1]["maps"][0]
    first = self_rest["first"]
    assert self_rest["errors"] == []
    assert first["layer"] == "system" == top["layers"][0]["id"]
    assert first["kicker"] == top["layers"][0]["n"]
    assert first["question"] == top["layers"][0]["q"]
    assert first["counts"].endswith(f"{len(top['layers'][0]['e'])} flows")
    assert " actors · " in first["counts"]
    want = [lay["id"] for lay in top["layers"] if lay["e"] or lay["id"] == "structure"]
    assert [t["id"] for t in first["tabs"]] == [*want, "all"]


def _check_layer(top: dict[str, Any], one: dict[str, Any]) -> None:
    layers = {lay["id"]: lay for lay in top["layers"]}
    view, lines = one["view"], one["lines"]
    lid = view["layer"]
    assert [t["id"] for t in view["tabs"] if t["on"]] == [lid]
    edges = list(range(len(top["flows"]))) if lid == "all" else layers[lid]["e"]
    assert sorted(e["f"] for e in lines["lanes"]) == sorted(edges)
    question = "Which flows connect the components?" if lid == "all" else layers[lid]["q"]
    assert view["question"] == question
    n = len(edges)
    assert lines["dense"] is (n > 48)
    assert lines["rest"] == pytest.approx(min(1, max(0.3, 1.25 - n / 56)))
    assert not (lines["dense"] and lines["labels"])
    used = {top["flows"][i][k] for i in edges for k in ("s", "t")}
    quiet = {q["id"] for q in one["quiet"] if q["q"]}
    assert quiet == ({c["id"] for c in top["cards"]} - used if n else set())


def test_each_layer_shows_its_flows(
    self_page: tuple[Path, dict[str, Any]], self_rest: dict[str, Any]
) -> None:
    """Acceptance 2."""
    for one in self_rest["layers"]:
        _check_layer(self_page[1]["maps"][0], one)


def _segments(lanes: list[dict[str, Any]]) -> list[tuple[int, int, float, float, float]]:
    out = []
    for e in lanes:
        q = e["q"]
        for a, b in zip(q, q[1:], strict=False):
            for ax in (0, 1):
                if abs(a[ax] - b[ax]) < 0.01 and abs(a[1 - ax] - b[1 - ax]) > 1:
                    lo, hi = sorted((a[1 - ax], b[1 - ax]))
                    out.append((e["f"], ax, round(a[ax] * 2) / 2, lo, hi))
    return out


def test_flows_that_share_a_gap_have_their_own_lanes(self_rest: dict[str, Any]) -> None:
    """Acceptance 3."""
    for one in self_rest["layers"]:
        segs = _segments(one["lines"]["lanes"])
        for i, a in enumerate(segs):
            for b in segs[i + 1 :]:
                if a[0] != b[0] and a[1:3] == b[1:3]:
                    assert min(a[4], b[4]) - max(a[3], b[3]) <= 2, (one["view"]["layer"], a, b)


def test_the_labels_at_rest_cover_no_card_and_no_label(self_rest: dict[str, Any]) -> None:
    """Acceptance 4."""
    shown = 0
    for one in self_rest["layers"]:
        names = [x["s"] for x in one["lines"]["labels"]]
        drawn = [
            t for t in one["texts"] if t["weight"] == 500 and t["s"] in names and t["size"] >= 9
        ]
        assert len(drawn) == len(names), one["view"]["layer"]
        cards = [
            [c["b"][0], c["b"][1], c["b"][0] + c["b"][2], c["b"][1] + c["b"][3]]
            for c in one["cards"]
        ]
        for i, t in enumerate(drawn):
            assert t["alpha"] >= 0.99
            assert not any(_over(t["box"], c) for c in cards), t
            assert not any(_over(t["box"], o["box"]) for o in drawn[i + 1 :]), t
        shown += len(drawn)
    assert shown > 10


def test_the_headline_does_not_cover_the_map(self_rest: dict[str, Any]) -> None:
    """Acceptance 5 and 6."""
    for one in self_rest["layers"]:
        f, h = one["frame"], one["head"]
        assert f[0] >= h["qRight"] or f[1] >= h["qBottom"], (f, h)
        assert 17 <= one["grid"]["pitch"] < 34
    assert self_rest["first"]["beside"] is True


def test_the_short_name_shows_near(
    self_page: tuple[Path, dict[str, Any]], self_rest: dict[str, Any]
) -> None:
    """Acceptance 7."""
    plain = {c["p"] for c in self_page[1]["maps"][0]["cards"] if c["p"]}
    assert not plain & {t["s"] for t in self_rest["layers"][0]["texts"]}
    assert plain & {t["s"] for t in self_rest["near"]["texts"]}
    assert self_rest["near"]["view"]["zoom"] == "120%"


def test_the_tabs_have_the_keys_of_a_tablist(self_rest: dict[str, Any]) -> None:
    """Acceptance 8."""
    tabs = [t["id"] for t in self_rest["first"]["tabs"]]
    keys = self_rest["keys"]
    assert keys["moved"] == {"focus": tabs[1], "layer": tabs[0]}
    assert keys["after"]["layer"] == tabs[1]


@pytest.mark.parametrize("which", ["self", "workspace"])
def test_a_phone_opens_near_the_top_left(
    which: str, self_page: tuple[Path, dict[str, Any]], workspace_page: Path
) -> None:
    """Acceptance 9."""
    out = _drive("--phone", self_page[0] if which == "self" else workspace_page)
    at, fitted = out["at"], out["fitted"]
    assert out["errors"] == []
    assert int(at["view"]["zoom"].rstrip("%")) >= 50
    assert at["frame"][0] == pytest.approx(14, abs=1)
    assert at["scroll"] == 390
    assert fitted["frame"][0] >= 0 and fitted["frame"][0] + fitted["frame"][2] <= 390


def test_the_workspace_has_no_error_at_rest(workspace_page: Path) -> None:
    out = _drive("--rest", workspace_page)
    assert out["errors"] == []
    assert out["first"]["question"] == "Which actors connect to the system?"


def test_a_nested_map_opens_and_closes(nested_run: dict[str, Any]) -> None:
    """Acceptance 10."""
    out = nested_run
    assert out["errors"] == []
    assert out["inside"]["chain"] == ["Gateway"]
    assert out["inside"]["path"] == ["join"]
    assert out["inside"]["hash"] == "#Gateway"
    assert "Gateway" in out["inside"]["view"]["kicker"]
    assert out["out"]["chain"] == []
    assert out["hashed"]["chain"] == ["Gateway"]
    assert out["back"] == []


def test_a_nested_map_opens_with_its_neighbours(nested_run: dict[str, Any]) -> None:
    """Acceptance 21."""
    for view in (nested_run["inside"]["view"], nested_run["hashed"]["view"]):
        assert view["shown"] == "system"
        assert [t["id"] for t in view["tabs"] if t["on"]] == ["system"]
        assert view["question"] == "Which neighbours connect to Gateway?"
    assert nested_run["out"]["view"]["shown"] == "all"


def test_axe_finds_no_serious_violation(
    self_page: tuple[Path, dict[str, Any]], nested_page: Path
) -> None:
    """Acceptance 11."""
    for page in (self_page[0], nested_page):
        runs = _drive("--axe", page)["runs"]
        if any(r["axe"] is None for r in runs):
            no_axe("the test needs axe-core on NODE_PATH")
        for r in runs:
            assert r["errors"] == [], r
            assert r["axe"]["violations"] == [], r


@pytest.fixture(scope="module")
def nested_run(nested_page: Path) -> dict[str, Any]:
    return _drive("--nested", nested_page, "Gateway")


def test_a_dive_leaves_no_selection(nested_run: dict[str, Any]) -> None:
    """Acceptance 12."""
    assert nested_run["inside"]["said"].startswith("Open map: join / Gateway.")
    assert "Selected" not in nested_run["inside"]["said"]
    assert nested_run["hashed"]["camera"] == pytest.approx(nested_run["inside"]["camera"])
    assert nested_run["hashed"]["differ"] <= 0.01


@pytest.fixture(scope="module", params=["self", "workspace"])
def marks_run(
    request: pytest.FixtureRequest,
    self_page: tuple[Path, dict[str, Any]],
    workspace_page: Path,
) -> dict[str, Any]:
    out = _drive("--marks", self_page[0] if request.param == "self" else workspace_page)
    assert out["errors"] == []
    return out


def _kind(one: dict[str, Any], t: str) -> list[dict[str, Any]]:
    return [m for m in one["drawn"]["marks"] if m["t"] == t]


def _box(b: list[float]) -> list[float]:
    return [b[0], b[1], b[0] + b[2], b[1] + b[3]]


def test_each_line_has_a_dot_an_arrowhead_and_a_casing(marks_run: dict[str, Any]) -> None:
    """Acceptance 13."""
    for one in marks_run["layers"]:
        lanes = sorted(e["f"] for e in one["lines"]["lanes"])
        lines, ends = _kind(one, "line"), _kind(one, "ends")
        assert sorted(e["f"] for e in lines) == lanes == sorted(e["f"] for e in ends)
        assert all(e["casing"] > e["wire"] > 0 for e in lines)
        first = {e["f"]: e["p"][0] for e in lines}
        for e in ends:
            assert e["dot"][2] > 0 and e["s"] > 0 and e["w"] > 0
            assert e["dot"][:2] == pytest.approx(first[e["f"]])
        ground = one["ground"]
        for color in one["heads"]:
            assert sum(abs(a - b) for a, b in zip(color, ground, strict=True)) > 20


def test_cards_containers_and_regions_have_the_rules(marks_run: dict[str, Any]) -> None:
    """Acceptance 14."""
    for one in marks_run["layers"]:
        texts = one["drawn"]["texts"]
        for c in _kind(one, "card"):
            b = _box(c["b"])
            if c["k"] == "actor":
                assert c["r"] == pytest.approx(c["b"][3] / 2)
            elif c["k"] != "component":
                tags = [t for t in texts if t["s"] == c["k"].upper()]
                assert any(
                    b[0] <= t["box"][0] and t["box"][2] <= b[2] and _over(t["box"], b) for t in tags
                ), c
        # The name of a container of actors draws only on the top map. A nested map that
        # shows as a small picture in its card, or that is open, draws no such name.
        actors = {m["n"] for m in _kind(one, "actors") if m["map"] == ""}
        assert actors and not actors & {m["n"] for m in _kind(one, "box")}
        assert all(any(t["s"] == n.upper() for t in texts) for n in actors)
        # Adjacent regions of one map do not touch. The regions of a small picture of a
        # nested map are inside a region of the map above.
        for mid in {m["map"] for m in _kind(one, "region")}:
            regions = [_box(m["b"]) for m in _kind(one, "region") if m["map"] == mid]
            for i, a in enumerate(regions):
                for b in regions[i + 1 :]:
                    assert not _over([a[0] - 0.5, a[1] - 0.5, a[2] + 0.5, a[3] + 0.5], b), (a, b)


def _crosses(p: list[float], q: list[float], box: list[float]) -> bool:
    steps = 40
    for i in range(steps + 1):
        x, y = p[0] + (q[0] - p[0]) * i / steps, p[1] + (q[1] - p[1]) * i / steps
        if box[0] < x < box[2] and box[1] < y < box[3]:
            return True
    return False


def _label_box(texts: list[dict[str, Any]], label: dict[str, Any]) -> list[float]:
    def far(t: dict[str, Any]) -> float:
        b = t["box"]
        return float(abs((b[0] + b[2]) / 2 - label["x"]) + abs((b[1] + b[3]) / 2 - label["y"]))

    mine = [t for t in texts if t["s"] == label["s"] and t["weight"] == 500]
    return list(min(mine, key=far)["box"])


def test_a_label_at_rest_has_its_line_alone(marks_run: dict[str, Any]) -> None:
    """Acceptance 15."""
    shown = 0
    for one in marks_run["layers"]:
        texts, lines = one["drawn"]["texts"], _kind(one, "line")
        names = {
            m["n"].upper() for m in one["drawn"]["marks"] if m["t"] in ("region", "box", "actors")
        }
        titles = [t["box"] for t in texts if t["s"] in names]
        for label in one["lines"]["labels"]:
            box = _label_box(texts, label)
            for e in lines:
                if e["f"] != label["f"]:
                    assert not any(
                        _crosses(p, q, box) for p, q in zip(e["p"], e["p"][1:], strict=False)
                    ), (label, e["f"])
            assert not any(_over(box, t) for t in titles), label
            shown += 1
    assert shown > 0
    sizes = set()
    for z in marks_run["zooms"]:
        names = {x["s"] for x in z["labels"]}
        sizes |= {t["size"] for t in z["texts"] if t["s"] in names and t["weight"] == 500}
    assert len(sizes) == 1 and min(sizes) >= 9, sizes
    assert marks_run["zooms"][-1]["k"] > 1.6 * marks_run["zooms"][0]["k"] * 0.99


def test_the_dot_grid_has_a_constant_size_on_the_screen(marks_run: dict[str, Any]) -> None:
    """Acceptance 16."""
    sizes = []
    for g in marks_run["grid"]:
        dots = g["dots"]
        assert len(dots) > 20, g["k"]
        sizes += [max(d["w"], d["h"]) for d in dots]
        rows: dict[int, list[float]] = {}
        for d in dots:
            rows.setdefault(round(d["y"]), []).append(d["x"])
        gaps = sorted(
            b - a for xs in rows.values() for a, b in zip(sorted(xs), sorted(xs)[1:], strict=False)
        )
        assert gaps and 17 <= gaps[len(gaps) // 2] <= 34, (g["k"], gaps)
    assert 1.5 <= min(sizes) and max(sizes) <= 3.5 and max(sizes) - min(sizes) <= 1


def test_the_wheel_the_drag_and_the_pinch_move_the_camera(
    self_page: tuple[Path, dict[str, Any]],
) -> None:
    """Acceptance 17."""
    out = _drive("--input", self_page[0])
    assert out["errors"] == []
    wheel, drag, pinch = out["wheel"], out["drag"], out["pinch"]
    assert wheel["k1"] > wheel["k0"] * 1.2
    assert wheel["after"] == pytest.approx(wheel["before"], abs=0.5)
    k = drag["from"]["k"]
    assert drag["to"]["k"] == k
    assert drag["from"]["x"] - drag["to"]["x"] == pytest.approx(drag["move"][0] / k, abs=0.5)
    assert drag["from"]["y"] - drag["to"]["y"] == pytest.approx(drag["move"][1] / k, abs=0.5)
    assert pinch["k1"] / pinch["k0"] == pytest.approx(pinch["ratio"], rel=0.02)
    assert pinch["after"] == pytest.approx(pinch["before"], abs=0.5)


def test_reduced_motion_moves_and_fades_nothing(nested_page: Path) -> None:
    """Acceptance 18."""
    out = _drive("--motion", nested_page, "Gateway")
    calm, moving = out["reduce"], out["no-preference"]
    assert calm["errors"] == [] and moving["errors"] == []
    assert calm["soon"] == pytest.approx(calm["late"])
    assert calm["swap"] == 1
    assert moving["soon"]["k"] < moving["late"]["k"] * 0.9
    assert moving["swap"] < 0.5


def test_the_headline_takes_the_position_of_the_larger_map(
    self_rest: dict[str, Any], workspace_page: Path
) -> None:
    """Acceptance 19."""
    wide = _drive("--rest", workspace_page)
    for run, beside in ((self_rest, True), (wide, False)):
        fit = run["fit"]
        assert fit["beside"] is beside
        assert run["first"]["beside"] is beside
        assert (fit["kBeside"] >= fit["kAbove"]) is beside
        assert fit["k"] == pytest.approx(min(max(fit["kBeside"], fit["kAbove"]), fit["k"]))
    for one in wide["layers"]:
        f, h = one["frame"], one["head"]
        assert f[1] >= h["qBottom"], (f, h)


def test_a_nested_map_has_its_picture_and_fades_the_map_above(nested_run: dict[str, Any]) -> None:
    """Acceptance 20, the nested map."""
    marks = nested_run["top"]["marks"]
    card = next(m for m in marks if m["t"] == "card" and m["id"] == "Gateway")
    picture = next(m for m in marks if m["t"] == "map" and m["id"] == "Gateway")
    assert card["under"] is True
    b, p = _box(card["b"]), _box(picture["b"])
    # The small picture is in the right half of the card.
    assert (b[0] + b[2]) / 2 <= p[0] and p[2] <= b[2] and b[1] <= p[1] and p[3] <= b[3]
    tops = [f["top"] for f in nested_run["fade"]]
    assert tops[0] == 1 and tops[-1] == 0
    assert all(a >= b for a, b in zip(tops, tops[1:], strict=False))
    assert any(0 < t < 1 for t in tops)


@pytest.mark.parametrize("which", ["self", "workspace"])
def test_a_phone_shows_the_cards_and_their_names(
    which: str, self_page: tuple[Path, dict[str, Any]], workspace_page: Path
) -> None:
    """Acceptance 20, the phone."""
    out = _drive("--phone", self_page[0] if which == "self" else workspace_page)
    for state in ("atDrawn", "fitDrawn"):
        texts = {t["s"] for t in out[state]["texts"]}
        cards = [m for m in out[state]["marks"] if m["t"] == "card" and m["map"] == ""]
        assert cards and all(c["shape"] == 1 for c in cards), state
        assert all(c["r"] == pytest.approx(c["b"][3] / 2) for c in cards if c["k"] == "actor")
        assert all(any(t.startswith(c["id"][:5]) for t in texts) for c in cards), state
    opened = out["atDrawn"]
    texts = {t["s"] for t in opened["texts"]}
    names = {m["n"].upper() for m in opened["marks"] if m["t"] in ("region", "box", "actors")}
    kinds = {
        m["k"].upper()
        for m in opened["marks"]
        if m["t"] == "card" and m["k"] not in ("actor", "component")
    }
    assert names and names <= texts
    assert kinds and kinds <= texts


@pytest.mark.parametrize("which", ["", "Page"])
def test_a_label_at_rest_stays_in_the_box_of_its_map(
    which: str, self_page: tuple[Path, dict[str, Any]]
) -> None:
    """Acceptance 22."""
    out = _drive("--inside", self_page[0], which)
    assert out["errors"] == []
    assert out["chain"] == ([which] if which else [])
    shown = 0
    for run in out["runs"]:
        f = run["frame"]
        frame = [f[0] - 0.5, f[1] - 0.5, f[0] + f[2] + 0.5, f[1] + f[3] + 0.5]
        for label in run["labels"]:
            if label["hide"]:
                continue
            b = label["box"]
            where = (run["state"], run["layer"], label["s"], b, f)
            assert frame[0] <= b[0] and frame[1] <= b[1], where
            assert b[2] <= frame[2] and b[3] <= frame[3], where
            if run["state"] == "phoneFit":
                assert -0.5 <= b[0] and b[2] <= run["size"][0] + 0.5, where
            shown += 1
    assert shown > 0


def _text_counts(layer: str) -> str:
    """The counts of the headline of Page for a layer, from the text of map/page.py."""
    import re  # noqa: PLC0415

    text = (REPO / "map/page.py").read_text(encoding="utf-8")
    actors = set(re.findall(r"id='(\w+)',\s*does='[^']*',\s*kind='actor'", text))
    flows = re.findall(r"Flow\('(\w+)', '(\w+)', '[^']*', '(\w+)'", text)
    if layer == "structure":
        cards, regions = text.count("Component("), text.count("Region(")
        return f"{cards} cards in {regions} regions"
    if layer == "system":
        chosen = [f for f in flows if f[0] in actors or f[1] in actors]
    else:
        chosen = [f for f in flows if layer == "all" or f[2] == layer]
    ends = {e for f in chosen for e in f[:2]}
    parts = text.count("Component(") - len(actors)
    return (
        f"{_of_all(len(ends & actors), len(actors), 'neighbour')} · "
        f"{_of_all(len(ends - actors), parts, 'part')} · {len(chosen)} flows"
    )


def _of_all(n: int, total: int, word: str) -> str:
    """The count rule of the headline (Z2): "N of T words", or "T words" when N is T."""
    words = f"{total} {word}" + ("" if total == 1 else "s")
    return words if n == total else f"{n} of {words}"


def test_the_counts_of_the_top_map_give_the_totals(
    self_page: tuple[Path, dict[str, Any]], self_rest: dict[str, Any]
) -> None:
    """Acceptance 27."""
    top = self_page[1]["maps"][0]
    kinds = {c["id"]: c["k"] for c in top["cards"]}
    actors = {i for i, k in kinds.items() if k == "actor"}
    checked = 0
    for one in self_rest["layers"]:
        view = one["view"]
        lid = view["layer"]
        edges = (
            list(range(len(top["flows"])))
            if lid == "all"
            else next(lay["e"] for lay in top["layers"] if lay["id"] == lid)
        )
        if not edges:
            continue
        ends = {top["flows"][i][k] for i in edges for k in ("s", "t")}
        want = f"{_of_all(len(ends - actors), len(kinds) - len(actors), 'component')} · "
        want += f"{len(edges)} flow" + ("" if len(edges) == 1 else "s")
        if ends & actors:
            want = f"{_of_all(len(ends & actors), len(actors), 'actor')} · {want}"
        assert view["counts"].startswith(want), (lid, view["counts"], want)
        checked += 1
    assert checked >= 2


def test_the_nested_map_page_has_its_parts_and_neighbours(page_run: dict[str, Any]) -> None:
    """Acceptance 23 and 24."""
    tree = nest.load(config.load(REPO))
    page = next(m for m in tree.maps if m.id == "Page")
    parts = {c.id for c in page.model.components if c.kind != "actor"}
    actors = {c.id for c in page.model.components if c.kind == "actor"}
    top = tree.top.model
    near = {f.src for f in top.flows if f.dst == "Page"} | {
        f.dst for f in top.flows if f.src == "Page"
    }
    assert len(parts) == 11 and actors == near - {"Page"}
    out = page_run
    assert out["errors"] == [] and out["chain"] == ["Page"]
    shown = {c["id"]: c["k"] for c in out["cards"]}
    assert {i for i, k in shown.items() if k != "actor"} == parts
    assert {i for i, k in shown.items() if k == "actor"} == actors
    assert actors <= {c["id"] for c in out["top"]}
    marks = out["drawn"]["marks"]
    drawn = {m["id"] for m in marks if m["t"] == "card" and m["map"] == "Page"}
    assert parts <= drawn
    assert parts <= {t["s"] for t in out["drawn"]["texts"]}
    tabs = [h["layer"] for h in out["heads"]]
    assert set(tabs) >= {"system", "structure", "all"}
    for head in out["heads"]:
        assert head["counts"] == _text_counts(head["layer"]), head["layer"]
    assert sorted(g["id"] for g in out["goes"]) == sorted(actors)
    for go in out["goes"]:
        assert go["chain"] == [] and go["current"] == "", go
        assert go["sel"] == {"map": "", "id": go["id"]}, go


@pytest.fixture(scope="module")
def page_run(self_page: tuple[Path, dict[str, Any]]) -> dict[str, Any]:
    return _drive("--page", self_page[0], "Page")


def test_a_neighbour_goes_out_with_the_keyboard(page_run: dict[str, Any]) -> None:
    """Acceptance 25."""
    assert page_run["errors"] == []
    actors = sorted(c["id"] for c in page_run["cards"] if c["k"] == "actor")
    assert sorted(k["id"] for k in page_run["keyed"]) == actors and actors
    for one in page_run["keyed"]:
        assert one["focus"] == {"map": "Page", "id": one["id"]}, one
        assert one["chain"] == [] and one["current"] == "", one
        assert one["sel"] == {"map": "", "id": one["id"]}, one


def _sides_of(cards: list[dict[str, Any]]) -> list[str]:
    parts = [_box(c["b"]) for c in cards if c["k"] != "actor"]
    x0, y0 = min(b[0] for b in parts), min(b[1] for b in parts)
    x1, y1 = max(b[2] for b in parts), max(b[3] for b in parts)
    out = []
    for c in cards:
        if c["k"] != "actor":
            continue
        b = _box(c["b"])
        at = [
            s
            for s, yes in (
                ("left", b[2] <= x0),
                ("right", b[0] >= x1),
                ("top", b[3] <= y0),
                ("bottom", b[1] >= y1),
            )
            if yes
        ]
        assert at, (c["id"], b, (x0, y0, x1, y1))
        out.append(at[0])
    return out


def test_the_neighbours_of_page_are_around_its_parts(page_run: dict[str, Any]) -> None:
    """Acceptance 26."""
    assert len(page_run["looks"]) == 4
    grounds = {}
    for look in page_run["looks"]:
        assert look["chain"] == ["Page"], look["size"]
        assert look["width"] <= (1440 if look["size"] == "wide" else 390)
        sides = _sides_of(look["cards"])
        assert len(set(sides)) >= 3, (look["size"], look["scheme"], sides)
        assert max(sides.count(s) for s in set(sides)) < len(sides)
        grounds[(look["size"], look["scheme"])] = look["dark"]
    for size in ("wide", "phone"):
        light = [int(v) for v in grounds[(size, "light")][4:-1].split(",")]
        dark = [int(v) for v in grounds[(size, "dark")][4:-1].split(",")]
        assert sum(dark) < 150 < sum(light), (size, light, dark)
