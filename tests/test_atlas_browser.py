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


def test_a_nested_map_opens_and_closes(nested_page: Path) -> None:
    """Acceptance 10."""
    out = _drive("--nested", nested_page, "Gateway")
    assert out["errors"] == []
    assert out["inside"]["chain"] == ["Gateway"]
    assert out["inside"]["path"] == ["join"]
    assert out["inside"]["hash"] == "#Gateway"
    assert "Gateway" in out["inside"]["view"]["kicker"]
    assert out["out"]["chain"] == []
    assert out["hashed"]["chain"] == ["Gateway"]
    assert out["back"] == []


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
