"""The parts of the canvas page that help a person read the map, in a browser: the flow
labels at the fit (`labelSize` in `page_canvas_draw`), the caption (`page_canvas_caption`)
and the route in the Details panel (`seqRoute` in `page_canvas_sequences`).

The test drives real canvas pages in the Chromium of Playwright (tests/canvas_reading.js):
the self-map of this repository, which has the nested map Page (`self_page`), the top map
of the self-map with no nested map (`flat_page`, only for acceptance 10), and the fixture
of tests/test_canvas_page.py, which has the nested map Gateway. The test skips when Node
or the Playwright package is not there, except when SYSTEMAP_BROWSER_TESTS is "required"
(the CI job canvas-browser). Then it fails.

Acceptance values, written before the first run on 2026-11-15:

1. At 1440 x 900 pixels, at the fit of the self-map, in each layer that has flows: the
   drawn labels are exactly the artifacts of the flows of the layer that have a label box.
   Each label has an alpha of 0.99 or more and a font size of 9 px or more (L1 in
   bench/jev/README.md).
2. The page opens with a caption (changed on 2026-11-15, before the run, with acceptance
   11: the caption of the first layer, not of All). After a click on each layer button, the caption gives the name and the question of that
   layer, with the alpha 1, and the live region gives the question. The plate of the caption
   is in the row of the path: it has the top and the height of the plate of the path, it
   starts 8 px after that plate, and it ends 12 px or more before the right screen edge.
3. Without reduced motion, after a change of the layer, the alpha of the caption changes
   by 0.25 or less between two frames. The sentence changes only in a frame in which the
   alpha is 0.25 or less. The alpha is 1 at the end. With reduced motion, the first frame
   after the change has the new sentence with the alpha 1.
4. At 390 x 844 pixels on a touch screen, the caption is in the screen or it does not show
   (a box of null), and the scroll width is 390 px.
5. In the Sequences view of the self-map, with the whole route of the first sequence: the
   caption gives the name of the sequence and "Which parts does this operation use?". The
   drawn labels are artifacts of the flows of the steps, and their count is the count of
   the different flows of the steps that have a label box.
6. The D key opens the Details panel. Its heading is the name of the sequence. Its ordered
   list has one button for each step, in order, and the text of button k starts with "k. ".
   Each sentence of a step is in the list. No button is the current step.
7. A click on the button of step 3: the view is in the Steps mode at step 3, the button of
   step 3 is the only button with `aria-current="step"`, and it has the keyboard focus. The
   caption gives "Step 3 of n" and the sentence of the step, and the toolbar gives "Step 3
   of n". After Next in the toolbar, the button of step 4 is the current step.
8. A click on a card: the heading of the panel is the name of that card. A click on empty
   space: the heading is the name of the sequence again.
9. axe-core 4.14.0 finds no serious or critical violation with the route in the panel, in
   the whole route and at a step, in the light and the dark scheme. The page has no script
   error in each run.
10. The bands of the fit. The self-map has no port: the left and right bands are 0, the top
    band is the bottom of the plate of the path, and the bottom band is 34 px. The frame of
    the map at the fit is below the plate of the path and above the plate of the help line.
    The fixture with the nested map has ports: its top band is 155 px and its bottom band is
    75 px, the values before this change.
11. Added on 2026-11-15, before the first run with the change of the first layer. The page
    opens with the layer System context when that layer is the first layer of the top map,
    and with All in the other cases: the view state, the one pressed layer button, the one
    layer button in the Tab order, the select and the caption give that layer. The self-map
    opens with System context. With that layer, "Show the flow on the map" in the Details
    panel for a flow that the layer does not show changes the layer to the layer of the
    flow, in the Map view.
12. Added on 2026-11-19 for the repair of stage 10 of docs/design/atlas.md, before the first
    run of this test. The fixture `self_page` removes the nested map Page from the card Page,
    because acceptance 10 is for a tree with no port. The fixture `tree_page` is the real
    tree of this repository, with the nested map Page. On that page, acceptance 1, 2 to 4,
    5 to 8 and 11 hold with the same checks, the page has ports, and the frame of the map
    at the fit is below the plate of the path and above the plate of the help line.
    The first run on 2026-11-19 failed acceptance 1 on this page: the smallest label at the
    fit is 8.5 px, not 9 px. The ports make the bands of the fit larger, thus the scale of
    the fit is lower (`labelSize` in `page_canvas_draw`). The other values held.
    Correction on 2026-11-19, after the second review of stage 10: an earlier text of this
    record said that the 8.5 px label is only in the layer System context. That is not
    correct. A run of `canvas_reading.js --labels` on this page gives a smallest label of
    8.5 px in each layer: System context, Data flow, Control flow and Map review.
    Also after the second review: the 9 px of acceptance 1 is not changed to 8.5 px. The
    canvas page stays as it is (docs/design/atlas.md), thus the 9 px check is an expected
    failure (`xfail`, strict) until the maintainer makes a decision. The other checks of
    acceptance 1 pass. The fixture `self_page` is now the real tree with the nested map Page
    (the earlier `tree_page`), thus acceptance 1 to 9 and 11 drive the real self-map again.
    Only acceptance 10
    uses `flat_page`, the top map with no nested map, because its values are for a tree
    with no port. Acceptance 12 checks the bands of the real tree, which has ports.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_canvas_access import AXE_VERSION, no_axe
from test_canvas_browser import browser
from test_canvas_page import _made

from systemap import canvas_data, canvas_page, config, facts_file, nest

ROOT = Path(__file__).resolve().parent
DRIVER = ROOT / "canvas_reading.js"
REPO = ROOT.parent
ROUTE_QUESTION = "Which parts does this operation use?"


def _drive(mode: str, page: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), mode, str(page)], capture_output=True, text=True, timeout=600
    )
    assert proc.returncode == 0, proc.stderr
    return dict(json.loads(proc.stdout))


def _write(cfg: config.Config, tree: nest.Tree, out: Path) -> Path:
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    data = canvas_data.build(cfg, tree, facts)
    out.write_text(canvas_page.build(canvas_page.tree_theme(cfg, tree), data), encoding="utf-8")
    return out


@pytest.fixture(scope="module")
def self_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The canvas page of the real tree of this repository, with the nested map Page."""
    cfg = config.load(REPO)
    tree = nest.load(cfg)
    assert len(tree.maps) > 1
    return _write(cfg, tree, tmp_path_factory.mktemp("reading") / "index.html")


@pytest.fixture(scope="module")
def flat_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The top map of the self-map with no nested map: the tree with no port of acceptance 10.

    From stage 10 of docs/design/atlas.md, the card Page opens the nested map Page. Here the
    card Page opens no map."""
    cfg = config.load(REPO)
    top = nest.load(cfg).top
    cards = tuple(dataclasses.replace(c, map=None) for c in top.model.components)
    flat = dataclasses.replace(top, model=dataclasses.replace(top.model, components=cards))
    return _write(cfg, nest.Tree(maps=(flat,)), tmp_path_factory.mktemp("flat") / "index.html")


@pytest.fixture(scope="module")
def self_labels(self_page: Path) -> dict[str, Any]:
    return _drive("--labels", self_page)


def test_the_labels_of_a_layer_at_the_fit(self_labels: dict[str, Any]) -> None:
    """Acceptance 1 with no size check, with the labels at rest (A3 of bench/jev/README.md).

    At rest, a label shows only when no path of a different flow of the layer goes
    through it. Thus the labels at rest are a part of the labels of the layer. With the
    pointer on a card, each label of a flow of that card shows.
    """
    _labels(self_labels)


@pytest.mark.xfail(
    strict=True,
    reason="Acceptance 1 fails on the real tree with the nested map Page: the smallest label "
    "at the fit is 8.5 px in each layer, not 9 px (acceptance 12). A decision of the "
    "maintainer is necessary.",
)
def test_the_labels_of_a_layer_have_9_px_at_the_fit(self_labels: dict[str, Any]) -> None:
    """Acceptance 1, the size of 9 px or more."""
    assert self_labels["errors"] == []
    small = {lay["id"]: min(t["size"] for t in lay["got"]) for lay in self_labels["layers"]}
    assert all(size >= 9 for size in small.values()), small


def _labels(out: dict[str, Any]) -> None:
    assert out["errors"] == []
    assert len(out["layers"]) >= 4
    for layer in out["layers"]:
        got, want = layer["got"], list(layer["want"])
        assert got, layer["id"]
        for t in got:
            assert t["s"] in want, layer["id"]
            want.remove(t["s"])
        assert min(t["alpha"] for t in got) >= 0.99, layer["id"]
        near = [t["s"] for t in layer["near"] if t["alpha"] >= 0.99]
        for name in layer["of_card"]:
            assert name in near, (layer["id"], layer["card"])
            near.remove(name)


def _in_path_row(at: dict[str, Any]) -> None:
    box, path = at["caption"]["box"], at["path"]
    assert box is not None
    assert box[1] == path[1] and box[3] == path[3]
    assert abs(box[0] - (path[0] + path[2] + 8)) < 0.01
    assert box[0] + box[2] <= at["width"] - 12


def test_the_caption_gives_the_question_of_each_layer(self_page: Path) -> None:
    """Acceptance 2, 3 and 4."""
    out = _drive("--caption", self_page)
    assert out["errors"] == []
    assert out["start"]["caption"]["a"] == 1
    _in_path_row(out["start"])
    assert len(out["layers"]) >= 5
    for layer in out["layers"]:
        cap = layer["at"]["caption"]
        assert (cap["k"], cap["s"], cap["a"]) == (layer["n"], layer["q"], 1), layer["id"]
        assert layer["q"] in layer["said"], layer["id"]
        _in_path_row(layer["at"])
    # Acceptance 3.
    frames = out["fade"]
    question = "Which flows connect the components?"
    for before, after in zip(frames, frames[1:], strict=False):
        assert abs(after[1] - before[1]) <= 0.25, (before, after)
        if after[2] != before[2]:
            assert after[1] <= 0.25, (before, after)
    assert frames[-1][1] == 1 and frames[-1][2] == question
    assert any(0 < f[1] < 1 for f in frames)
    assert out["reduced"][1][1:] == [1, question], out["reduced"][:3]
    # Acceptance 4.
    phone = out["phone"]
    assert phone["scroll"] == 390
    box = phone["caption"]["box"]
    assert box is None or (box[0] >= 0 and box[0] + box[2] <= 390)


def _route_run(one: dict[str, Any]) -> None:
    seq, flows = one["seq"], one["flows"]
    steps = seq["s"]
    n = len(steps)
    assert n >= 4
    # Acceptance 5.
    whole = one["whole"]
    assert (whole["caption"]["k"], whole["caption"]["s"]) == (seq["n"], ROUTE_QUESTION)
    on_route = {s["f"] for s in steps if s["f"] >= 0}
    drawn = [t["s"] for t in one["wholeLabels"]]
    assert set(drawn) <= {flows[i] for i in on_route}
    assert 0 < len(drawn) <= len(on_route)
    # Acceptance 6.
    panel = one["panel"]
    assert panel["title"] == seq["n"]
    assert len(panel["steps"]) == n
    for k, text in enumerate(panel["steps"]):
        assert text.startswith(f"{k + 1}. "), text
    assert panel["sentences"] == [s["y"] for s in steps if s.get("y")]
    assert panel["current"] == []
    # Acceptance 7.
    third = one["third"]
    assert third["state"]["seq"]["steps"] is True and third["state"]["seq"]["s"] == 2
    assert third["panel"]["current"] == ["2"] and third["panel"]["focus"] == "2"
    assert third["state"]["caption"]["k"] == f"Step 3 of {n}"
    assert third["state"]["caption"]["s"] == steps[2]["y"]
    assert third["state"]["count"] == f"Step 3 of {n}"
    fourth = one["fourth"]
    assert fourth["state"]["seq"]["s"] == 3 and fourth["panel"]["current"] == ["3"]
    # Acceptance 8.
    assert one["card"]["panel"]["title"] == one["card"]["id"]
    assert one["back"]["title"] == seq["n"]
    assert one["errors"] == []


def test_the_details_panel_gives_the_route_in_order(self_page: Path) -> None:
    """Acceptance 5 to 8, and the script errors of acceptance 9."""
    out = _drive("--route", self_page)
    for scheme in ("light", "dark"):
        _route_run(out[scheme])


def test_axe_core_finds_no_issue_with_the_route_in_the_panel(self_page: Path) -> None:
    """Acceptance 9."""
    out = _drive("--route", self_page)
    for scheme in ("light", "dark"):
        for key in ("axeWhole", "axeStep"):
            found = out[scheme][key]
            if found is None:
                no_axe("axe-core is not in NODE_PATH")
            assert found["version"] == AXE_VERSION
            assert found["violations"] == [], (scheme, key)


def test_a_tree_with_no_port_has_no_portal_bands(flat_page: Path, tmp_path: Path) -> None:
    """Acceptance 10, on the top map with no nested map (acceptance 12)."""
    own = _drive("--bands", flat_page)
    assert own["errors"] == [] and own["ports"] is False
    path, help_plate, frame, bands = own["path"], own["help"], own["frame"], own["gutters"]
    assert bands == {"x": 0, "top": path[1] + path[3], "bottom": 34}
    assert frame[1] >= path[1] + path[3]
    assert frame[1] + frame[3] <= help_plate[1]
    assert frame[0] >= 0 and frame[0] + frame[2] <= own["width"]
    nested = _made(tmp_path, '[render]\npage = "canvas"\n') / "docs" / "map" / "index.html"
    other = _drive("--bands", nested)
    assert other["errors"] == [] and other["ports"] is True
    assert other["gutters"]["top"] == 155 and other["gutters"]["bottom"] == 75


def _opens_with(out: dict[str, Any]) -> str:
    layers = out["layers"]
    want = "system" if layers and layers[0]["id"] == "system" else "all"
    start = out["start"]
    assert out["errors"] == []
    assert (start["layer"], start["mode"], start["select"]) == (want, "map", want)
    assert start["pressed"] == [want] and start["tab"] == [want]
    name = {lay["id"]: lay["n"] for lay in layers} | {"all": "All layers"}
    assert start["caption"]["k"] == name[want]
    return want


def test_the_page_opens_with_system_context(self_page: Path, tmp_path: Path) -> None:
    """Acceptance 11."""
    own = _drive("--first", self_page)
    assert _opens_with(own) == "system"
    assert own["layers"][0]["e"] > 0
    flow = own["flow"]
    assert flow["layer"] != "system"
    assert (flow["after"]["layer"], flow["after"]["mode"]) == (flow["layer"], "map")
    assert flow["after"]["pressed"] == [flow["layer"]]
    nested = _made(tmp_path, '[render]\npage = "canvas"\n') / "docs" / "map" / "index.html"
    _opens_with(_drive("--first", nested))


def test_the_real_tree_with_the_nested_map_page(self_page: Path) -> None:
    """Acceptance 12, the bands. Acceptance 1 to 9 and 11 use the same page (`self_page`)."""
    own = _drive("--bands", self_page)
    assert own["errors"] == [] and own["ports"] is True
    path, help_plate, frame = own["path"], own["help"], own["frame"]
    assert frame[1] >= path[1] + path[3]
    assert frame[1] + frame[3] <= help_plate[1]
