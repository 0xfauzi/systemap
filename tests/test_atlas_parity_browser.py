"""The parity parts of the atlas page in a browser (docs/design/atlas.md, stage 8).

The test drives real atlas pages in the Chromium of Playwright (tests/atlas_parity.js): the
map of this repository, the nested fixture of tests/test_canvas_page.py (the map Gateway with
the card Routes), the nested fixture of tests/test_canvas_ports.py with two open boundary
lines, and the three-level tree of tests/test_canvas_changes.py with a revision comparison.
The test skips when Node or the Playwright package is not there, except when
SYSTEMAP_BROWSER_TESTS is "required". Then it fails. The test of axe-core skips when
axe-core is not on NODE_PATH, with the same exception.

Acceptance values, written on 2026-11-19 before the first run of these tests:

1. The theme control. With the light scheme of the device and no stored key, the theme is
   Device, its button is pressed, and `data-theme` is light. A click on Dark sets
   `data-theme` to dark, stores "dark" with the key systemap-theme, presses only Dark, the
   ground of the page has the dark color, and the live region gives "Theme: Dark.". After a
   reload, the theme is still Dark. A click on Device removes the key, and `data-theme`
   follows the scheme of the device, also after a change of that scheme.
2. Reduce motion. A click sets `data-reduce-motion` to true, stores "true" with the key
   systemap-reduce-motion and presses the button. After a reload, the setting stays.
3. The keyboard sheet. The ? key on the canvas opens it with the keyboard focus on its
   Close button and one row for each key of `atlas_tools.KEYS`. Tab keeps the focus in the
   sheet, an arrow key does not move the camera, and Esc closes it and gives the focus back to
   the canvas. The Keyboard keys button opens it, and Close gives the focus back to that
   button.
4. On a phone of 390 x 844 with a touch screen, the tools are in the Tools menu: the menu
   button is 44 x 44 px or more, each tool of the open menu is 44 px high or more, the page
   has no horizontal scroll, the keyboard focus goes to the first tool, and Esc closes the
   menu and gives the focus back to the menu button.
5. Find. Ctrl K and / open the dialog with the focus in its field, and Esc closes it and
   gives the focus back. With no text, the groups are Views, Layers, Sequences and Actions.
   The text of a card name gives that card as the first row of Components, and the status
   gives the count of the rows. Enter closes the dialog, selects the card, opens its details
   and writes the hash of the card. The result of a flow keeps the line of that flow lit.
   The result of a sequence shows the Sequences view at that sequence, and the result of a
   step shows that step. "Go to the top map" shows the Map view. On a phone, Find in the
   Tools menu opens the dialog. The page has no script error.
6. The URL hash. A load with #Gateway opens the nested map Gateway. A load with
   #Gateway/Routes opens Gateway, keeps the hash and has the card Routes on the screen. A
   hash that names nothing opens the top map, and the live region tells it. A change of the
   hash in the loaded page moves the camera to that map, and Esc goes out to the top map
   and clears the hash.
7. The boundary finding marks. At the fit of Gateway, the actor card Style has a mark with
   the tag "2 open lines", a dotted ring in --ink-2 and a tag of 7 px or more with the alpha
   1, in the light and the dark scheme. The headline gives "2 open boundary lines", and the
   live region gives "Open boundary lines: 2.". The list of the tree and the reading line of
   Style give "Open boundary lines: No flow inside, Import with no flow.". With the answers
   of the policy kind, no card has a mark.
8. The changes with `--base`. At the top map, P0 has the tag "changed · changed inside" and
   a solid ring of 2 px in --change. In P0/Q0/Deep, D1 has the tag "changed" and D0 the tag
   "imports" with a dashed ring, each in --change, and each lost flow has a dashed line in
   --change. The headline gives the count of the changed cards and the base. The list of the
   tree gives "Change: changed source." and "Changed inside:". A page without a comparison
   has no change mark.
9. The text list of the map tree. The list is a navigation landmark with the name "Map
   tree". It has one link for each map, each card of each map, and each flow of each map,
   with the lists "Cards of ..." and "Flows of ...". Enter on the link of a card of Gateway
   moves the camera into Gateway and writes the hash of the card.
10. axe-core finds no violation (of any impact) in the light and the dark scheme, at
    1440 x 900 and 390 x 844: at rest, with Find open, with the keyboard sheet open, with
    the Tools menu open on the phone, and in the nested map Gateway.

Notes after the first run, with no change to a value: a nested map opens on its Neighbours
layer, which can hide a lost flow. Thus the test of acceptance 8 examines the lost lines in
the layer All. The axe-core runs bypass the page policy, because the policy refuses the
script of axe-core.
11. `systemap live` with `[render] page = "atlas"`: each load opens 1 event connection to
    `/events`. A new version loads the page 1 time, the hash stays #Gateway/Routes and the
    map Gateway is open. A version that the command cannot render shows the notice "The map
    is not updated:" with the first line of the error. 0 policy violations, 0 script errors
    and 0 requests outside the origin of the server.

Acceptance 11 is after the notes of the first run, in the order of the first commit of stage
8. That commit is the only record, and it does not show when acceptance 11 was written. Thus
acceptance 11 can have been written after the first run of the tests, and it is not a value
that was fixed before a run. The repair after the first review moved it up, and the repair
after the second review put it back in this order.

Acceptance values written on 2026-11-19 after the review of stage 8, before the first run of
their tests:

12. Find with the keyboard. The rows of a flow, a sequence, a step and the action "Go to
    the top map" are chosen with the down arrow key and Enter in the dialog, and each gives
    the result of acceptance 5. The / key in a text field of the page types "/" and does
    not open Find. In the field of Find, "a/b" is the text of the field and the dialog stays
    open.
13. Find for a different map. At the top map of the nested fixture, the text "Routes" gives
    the card Routes in the group "Other maps" with the hint "in Gateway". Enter on that row
    moves the camera into Gateway, selects Routes and writes the hash #Gateway/Routes. The
    first row of "Other maps" for the artifact of a flow of Gateway keeps that flow lit in
    Gateway.
14. The tags of the marks. At the top map and in P0/Q0/Deep (its first layer and the layer
    All), in the light and the dark scheme, no tag covers a label, a different tag, a
    different card of its map or a line. At the top map, each drawn mark is a mark of the top
    map: a map that shows as a small picture has no marks.
15. The tag TESTS. When the change data gives only changed tests for D1 in P0/Q0/Deep, D1 has
    the tag "tests" and a solid ring of 1.2 px in --change, and the list of the tree gives
    "Change: only tests changed.".

Acceptance values written on 2026-11-19 after the second review of stage 8, before the first
run of their tests:

16. The URL hash of a card. At 1440 x 900 and at 390 x 844, in the light and the dark scheme,
    a load with #Gateway/Routes selects Routes and opens its details with the heading
    Routes. At 1440 x 900 the camera is the fit of Gateway with the space of the details: its
    zoom is within 1 percent of the zoom after the result of Find for Routes from the top
    map, its position is within 2 screen px of that camera, and the frame of Gateway is on the
    screen below the headline and at the left of the details. In the map of this repository,
    Find for Judgement and then a reload with the hash that Find wrote give the same
    selection and a camera within 1 percent of zoom and 2 screen px, at both sizes. A change
    of the hash to #Gateway/Routes in a page at the top map, and Enter on the link of Routes
    in the list of the tree, each select Routes.
17. The marks on a phone. At 390 x 844, in Gateway of the fixture with two open boundary
    lines, the headline shows the text "2 open boundary lines" in a box of 1 px or more
    high, and the count of the parts does not show. At the top map of the tree with a
    revision comparison, the headline shows the count of the changed cards.
    Changed on 2026-11-20 in the final repair, before the run: the count of the parts shows
    on a phone, because docs/design/atlas.md says that the headline gives the counts.

Acceptance value written on 2026-11-19 after the third review of stage 8, before the first
run of its test:

18. The hint of the field of Find is "Find a card, flow, sequence or action". On a phone of
    390 x 844, after the fonts load, its width in the font of the hint is 8 px or more less
    than the width of the field between its padding.

Acceptance value written on 2026-11-19 in stage 9 (the atlas page is the default), before
the first run of its test:

19. The view link of a pull request comment. A load of the nested fixture with #changes
    opens the top map, and a load with #Gateway/changes opens Gateway. Neither load writes
    "No map and no card has the link" in the live region, and neither has a script error.

Acceptance value written on 2026-11-19 after the review of stage 9, before the first run of
its test:

20. A card with the ID `changes` keeps its link. In the nested fixture with the card Log of
    the top map and the card Routes of Gateway renamed to `changes`, #changes selects the
    card `changes` of the top map, and #Gateway/changes selects the card `changes` of
    Gateway. #Auth/changes opens the top map and writes "No map and no card has the link
    #Auth/changes" in the live region, because Auth is a card and not a map. No load has a
    script error.
Acceptance value written on 2026-11-19 after the second review of stage 9, before the first
run of its test:

21. axe-core on the committed self-map. docs/map/index.html is the atlas page from stage 9,
    and the website publishes it. axe-core finds no violation (of any impact) on that file in
    the light and the dark scheme, at 1440 x 900 and 390 x 844: at rest, with Find open, with
    the keyboard sheet open, with the Tools menu open on the phone, and with #CLI (the card CLI
    selected, with its details open). That is 18 runs. No run has a script error.
"""

from __future__ import annotations

import copy
import functools
import json
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any

import pytest
import test_canvas_changes as changes_fixture
import test_canvas_ports as ports_fixture
from conftest import write_tree
from test_canvas_access import no_axe
from test_canvas_browser import browser
from test_canvas_page import _made
from test_nest_join import CONFIG as NEST_CONFIG
from test_nest_join import NESTED, TOP
from test_nest_join import SOURCE as NEST_SOURCE

from systemap import (
    atlas_data,
    atlas_page,
    atlas_tools,
    canvas_page,
    config,
    facts_file,
    nest,
    page_csp,
    serve,
)
from systemap.cli import main
from systemap.config import ConfigError

ROOT = Path(__file__).resolve().parent
DRIVER = ROOT / "atlas_parity.js"
REPO = ROOT.parent
ATLAS = '[render]\npage = "atlas"\n'
BOTH = "Open boundary lines: No flow inside, Import with no flow."


def _drive(*args: str) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), *args], capture_output=True, text=True, timeout=900
    )
    assert proc.returncode == 0, proc.stderr
    return dict(json.loads(proc.stdout))


@functools.cache
def _self_page() -> Path:
    cfg = config.load(REPO)
    tree = nest.load(cfg)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    out = Path(tempfile.mkdtemp(prefix="atlas-parity-")) / "index.html"
    data = atlas_data.build(cfg, tree, facts)
    out.write_text(atlas_page.build(canvas_page.tree_theme(cfg, tree), data), encoding="utf-8")
    return out


@functools.cache
def _nested_page() -> Path:
    root = _made(Path(tempfile.mkdtemp(prefix="atlas-nested-")), ATLAS)
    return root / "docs" / "map" / "index.html"


@functools.cache
def _ports_pages() -> tuple[Path, Path]:
    out = Path(tempfile.mkdtemp(prefix="atlas-ports-"))
    opened = ports_fixture.made(out / "open", page="atlas") / "docs/map/index.html"
    closed = (
        ports_fixture.made(out / "closed", extra=ports_fixture.POLICY, page="atlas")
        / "docs/map/index.html"
    )
    return opened, closed


@functools.cache
def _changes_pages() -> tuple[Path, Path]:
    out = Path(tempfile.mkdtemp(prefix="atlas-changes-"))
    root = out / "repo"
    rev = changes_fixture.committed(root)
    changes_fixture.model_change(root)
    changes_fixture.source_change(root)
    cfg, tree, facts, changes = changes_fixture.changed(root, rev)
    theme = canvas_page.tree_theme(cfg, tree)
    compared, plain = out / "changed.html", out / "plain.html"
    compared.write_text(
        atlas_page.build(theme, atlas_data.build(cfg, tree, facts, changes=changes)),
        encoding="utf-8",
    )
    plain.write_text(atlas_page.build(theme, atlas_data.build(cfg, tree, facts)), encoding="utf-8")
    return compared, plain


@functools.cache
def _tests_page() -> Path:
    """The page of the changes fixture, with only changed tests for D1 in P0/Q0/Deep.

    The fixture has no test files. Thus the change data of the map is changed as the change
    detector gives it for a component with changed tests and no changed source module."""
    out = Path(tempfile.mkdtemp(prefix="atlas-tests-"))
    root = out / "repo"
    rev = changes_fixture.committed(root)
    changes_fixture.source_change(root)
    cfg, tree, facts, changes = changes_fixture.changed(root, rev)
    deep = copy.deepcopy(changes)
    record = deep[changes_fixture.DEEP]["per_component"]["D1"]
    record["modules"] = []
    record["surface"]["tests_added"] = ["test_more"]
    page_file = out / "tests.html"
    page_file.write_text(
        atlas_page.build(
            canvas_page.tree_theme(cfg, tree), atlas_data.build(cfg, tree, facts, changes=deep)
        ),
        encoding="utf-8",
    )
    return page_file


def test_the_theme_control_reduce_motion_and_the_keyboard_sheet() -> None:
    """Acceptance 1 to 4."""
    out = _drive("--tools", str(_self_page()))
    assert out["errors"] == [] and out["phone"]["errors"] == [], out
    start = out["start"]
    assert start["tools"]["theme"] == "device" and start["tools"]["scheme"] == "light"
    assert start["stored"]["theme"] is None and start["pressed"] == "true"
    dark = out["dark"]
    assert dark["tools"]["scheme"] == "dark" and dark["stored"]["theme"] == "dark"
    assert dark["pressed"] == ["false", "false", "true"] and dark["say"] == "Theme: Dark."
    assert dark["ground"] == "rgb(18, 17, 15)"
    assert (
        out["motion"]["tools"]["motion"] == "true" and out["motion"]["stored"]["motion"] == "true"
    )
    assert out["motion"]["pressed"] == "true"
    reload = out["reload"]
    assert reload["tools"]["theme"] == "dark" and reload["tools"]["scheme"] == "dark"
    assert reload["tools"]["motion"] == "true" and reload["pressed"] == "true"
    assert reload["themePressed"] == "true"
    assert out["device"]["stored"]["theme"] is None and out["device"]["tools"]["scheme"] == "light"
    assert out["deviceDark"]["tools"]["scheme"] == "dark"
    _check_sheet_and_phone(out)


def _check_sheet_and_phone(out: dict[str, Any]) -> None:
    """Acceptance 3 and 4."""
    sheet = out["sheet"]
    assert sheet["tools"]["keys"] and sheet["rows"] == len(atlas_tools.KEYS)
    assert sheet["active"] == "BUTTON" and sheet["tab"] == "BUTTON" and not sheet["moved"]
    assert not sheet["closed"]["keys"] and sheet["back"] == "canvas"
    assert out["button"]["tools"]["keys"] and out["button"]["back"] == "atlas-keys"
    phone = out["phone"]
    assert phone["wideTools"] == [] and all(w >= 44 and h >= 44 for w, h in phone["open"])
    assert phone["menu"]["menu"] and all(h >= 44 for _w, h in phone["targets"])
    assert len(phone["targets"]) == 6 and phone["scroll"] <= 0
    assert phone["active"] == "atlas-find-menu"
    assert phone["light"]["scheme"] == "light"
    assert not phone["closed"]["menu"] and phone["back"] == "atlas-tools-open"
    assert phone["keys"]["keys"] and not phone["keys"]["menu"]


def test_find_goes_to_a_card_a_flow_a_sequence_and_a_step() -> None:
    """Acceptance 5, 12 and 18."""
    out = _drive("--find", str(_self_page()), "Judgement", "verdict")
    assert out["errors"] == [] and out["phone"]["errors"] == [], out
    assert out["ctrl"]["find"] and out["ctrl"]["active"] == "pal-input"
    assert not out["ctrl"]["closed"] and out["ctrl"]["back"] == "canvas"
    assert out["slash"] and out["button"]["find"] and out["button"]["expanded"] == "true"
    assert [g["g"] for g in out["empty"]] == ["Views", "Layers", "Sequences", "Actions"]
    components = [g for g in out["rows"] if g["g"] == "Components"][0]
    assert components["rows"][0]["t"] == "Judgement" and out["listed"][0] == "Judgement"
    assert out["status"] == f"{len(out['listed'])} results"
    card = out["card"]
    assert not card["find"] and card["side"]["sel"] == {"map": "", "id": "Judgement"}
    assert card["side"]["on"] and card["hash"] == "#Judgement"
    flows = [g for g in out["flowRows"] if g["g"] == "Flows"][0]
    assert flows["rows"][0]["t"] == "verdict"
    assert out["flow"]["lit"]["pin"] is not None and out["flow"]["side"]["sel"] is None
    assert "verdict" in out["flow"]["say"]
    assert out["sequences"], out
    assert out["sequence"]["mode"] == "seq" and out["sequence"]["seq"]["step"] == -1
    assert out["step"]["seq"]["step"] == 1
    assert out["top"]["mode"] == "map" and out["top"]["current"] == ""
    # Acceptance 12: the rows above are chosen with the keyboard.
    assert out["flowKey"] == {"g": "Flows", "n": 0, "t": "verdict"}
    assert out["sequenceKey"]["g"] == "Sequences" and out["stepKey"]["g"] == "Steps"
    assert out["topKey"]["t"] == "Go to the top map"
    typed = out["typed"]
    assert not typed["find"] and typed["value"] == "/"
    assert typed["open"] and typed["field"] == "a/b"
    assert out["phone"]["tools"]["find"] and out["phone"]["active"] == "pal-input"
    assert out["phone"]["back"] == "atlas-tools-open"
    # The hint names the four kinds of row, and a phone of 390 px shows all of it.
    hint = out["phone"]["hint"]
    assert hint["text"] == "Find a card, flow, sequence or action", hint
    assert hint["width"] + 8 <= hint["room"], hint


def _gateway_flow(page_file: Path) -> str:
    data = json.loads(
        page_file.read_text(encoding="utf-8")
        .split('<script type="application/json" id="atlas-data">')[1]
        .split("</script>")[0]
    )
    gateway = [m for m in data["maps"] if m["id"] == "Gateway"][0]
    return str(gateway["flows"][0]["a"])


def test_find_goes_to_a_card_and_a_flow_of_a_different_map() -> None:
    """Acceptance 13."""
    page_file = _nested_page()
    flow = _gateway_flow(page_file)
    out = _drive("--other", str(page_file), "Routes", flow)
    assert out["errors"] == [], out
    other = [g for g in out["cardRows"] if g["g"] == "Other maps"][0]["rows"][0]
    assert other["t"] == "Routes" and other["hint"] == "in Gateway"
    assert out["cardKey"]["t"] == "Routes"
    card = out["card"]
    assert card["current"] == "Gateway" and card["hash"] == "#Gateway/Routes"
    assert card["side"]["sel"] == {"map": "Gateway", "id": "Routes"}
    assert out["before"] == ""
    rows = [g for g in out["flowRows"] if g["g"] == "Other maps"][0]["rows"]
    assert rows[0]["t"] == flow and rows[0]["hint"] == "in Gateway"
    assert out["flow"]["current"] == "Gateway" and out["flow"]["lit"]["pin"] is not None
    assert out["flow"]["lit"]["map"] == "Gateway"


def test_the_url_hash_of_a_map_and_of_a_card() -> None:
    """Acceptance 6."""
    out = _drive("--hash", str(_nested_page()), "Gateway", "Routes")
    assert out["errors"] == [], out
    assert out["map"]["current"] == "Gateway" and out["map"]["hash"] == "#Gateway"
    card = out["card"]
    assert card["current"] == "Gateway" and card["hash"] == "#Gateway/Routes"
    x, y, w, h = card["box"]
    assert x >= 0 and y >= 48 and x + w <= 1440 and y + h <= 900
    assert out["none"]["current"] == "" and "No map and no card has the link" in out["none"]["say"]
    assert out["changed"]["current"] == "Gateway"
    assert out["out"]["current"] == "" and out["out"]["hash"] == ""


def test_the_view_link_of_a_pull_request_comment() -> None:
    """Acceptance 19."""
    out = _drive("--hash", str(_nested_page()), "Gateway", "Routes")
    assert out["errors"] == [], out
    assert out["view"]["current"] == "", out["view"]
    assert out["mapView"]["current"] == "Gateway", out["mapView"]
    for run in (out["view"], out["mapView"]):
        assert "No map and no card has the link" not in run["say"], run


@functools.cache
def _ids_page() -> Path:
    """The nested fixture with a card `changes` in the top map and in Gateway."""
    root = Path(tempfile.mkdtemp(prefix="atlas-ids-")) / "repo"
    files = {
        "systemap.toml": NEST_CONFIG + ATLAS,
        "map/model.py": TOP.replace('"Log"', '"changes"').replace('id="Log"', 'id="changes"'),
        "map/gateway.py": NESTED.replace('"Routes"', '"changes"').replace(
            'id="Routes"', 'id="changes"'
        ),
        **NEST_SOURCE,
    }
    write_tree(root, files)
    for command in ("place", "extract", "render"):
        assert main(["--root", str(root), command]) == 0
    return root / "docs" / "map" / "index.html"


def test_a_card_with_the_id_changes_keeps_its_link() -> None:
    """Acceptance 20."""
    out = _drive("--ids", str(_ids_page()), "#changes,#Gateway/changes,#Auth/changes")
    assert out["errors"] == [], out
    top, inner, card = (out["runs"][h] for h in ("#changes", "#Gateway/changes", "#Auth/changes"))
    _selected(top, "", "changes")
    _selected(inner, "Gateway", "changes")
    assert card["current"] == "", card
    assert "No map and no card has the link #Auth/changes" in card["say"], card


def _same_camera(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """True when the cameras `a` and `b` have a zoom within 1 percent and the same screen
    position within 2 px."""
    k = float(a["k"])
    return (
        abs(k / float(b["k"]) - 1) <= 0.01
        and abs(a["x"] - b["x"]) * k <= 2
        and abs(a["y"] - b["y"]) * k <= 2
    )


def _selected(state: dict[str, Any], map_id: str, card: str) -> None:
    side = state["side"]
    assert side["on"] and not side["hidden"], state
    assert side["sel"] == {"map": map_id, "id": card}, state
    assert state["heading"] == card, state


def test_the_url_hash_of_a_card_selects_the_card_at_the_fit_of_its_map() -> None:
    """Acceptance 16."""
    out = _drive("--cardhash", str(_nested_page()), str(_self_page()))
    assert len(out["runs"]) == 4
    for run in out["runs"]:
        assert run["errors"] == [], run
        for key in ("load", "find", "changed", "tree"):
            _selected(run[key], "Gateway", "Routes")
            assert run[key]["hash"] == "#Gateway/Routes", (key, run[key])
        _selected(run["selfFind"], "", "Judgement")
        _selected(run["selfLoad"], "", "Judgement")
        assert run["selfLoad"]["hash"] == run["selfFind"]["hash"] == "#Judgement"
        assert _same_camera(run["selfLoad"]["cam"], run["selfFind"]["cam"]), run
        if run["size"] != "wide":
            continue
        assert _same_camera(run["load"]["cam"], run["find"]["cam"]), run
        x, y, w, h = run["load"]["frame"]
        ask = run["load"]["ask"]
        assert x >= 0 and x + w <= run["load"]["side"]["box"][0], run["load"]
        assert y >= ask[1] + ask[3] and y + h <= 900, run["load"]


def test_the_counts_of_the_marks_show_on_a_phone() -> None:
    """Acceptance 17."""
    opened, _closed = _ports_pages()
    compared, _plain = _changes_pages()
    out = _drive("--phonemarks", str(opened), str(compared))
    assert out["errors"] == [], out
    ports = {p["cls"]: p for p in out["ports"]}
    assert "2 open boundary lines" in ports["ask__m"]["text"]
    assert ports["ask__m"]["shown"] and ports["ask__m"]["h"] >= 1
    assert "part" in ports["ask__c"]["text"] and ports["ask__c"]["shown"]
    changes = {p["cls"]: p for p in out["changes"]}
    assert "changed card" in changes["ask__m"]["text"]
    assert changes["ask__m"]["shown"] and changes["ask__m"]["h"] >= 1


def _mark(run: dict[str, Any], where: str, cid: str) -> dict[str, Any]:
    found = [m for m in run[where]["drawn"] if m["t"] == "mark" and m["id"] == cid]
    assert found, (where, cid, run[where]["drawn"])
    return dict(found[0])


def test_the_marks_of_the_open_boundary_lines() -> None:
    """Acceptance 7."""
    opened, closed = _ports_pages()
    out = _drive("--marks", str(opened), "Gateway")
    for run in out["runs"]:
        assert run["errors"] == [], run
        style = _mark(run, "nested", "Style")
        assert style["tag"] == "2 open lines" and style["port"] and style["alpha"] == 1
        assert style["size"] >= 7 and style["ring"]["dash"]
        assert style["ring"]["color"] == run["tokens"]["ink2"]
        assert "2 open boundary lines" in run["nested"]["head"]
        assert "Open boundary lines: 2." in run["nested"]["say"]
        assert BOTH in run["tree"] and BOTH in run["reading"]
    out = _drive("--marks", str(closed), "Gateway")
    for run in out["runs"]:
        assert run["errors"] == [] and run["state"]["cards"] == [], run
        assert not [m for m in run["nested"]["drawn"] if m["t"] == "mark"]


def test_the_marks_of_the_changes_of_a_revision_comparison() -> None:
    """Acceptance 8 and 14."""
    compared, plain = _changes_pages()
    nested = "P0/Q0/Deep"
    out = _drive("--marks", str(compared), nested)
    for run in out["runs"]:
        assert run["errors"] == [], run
        change = run["tokens"]["change"]
        p0 = _mark(run, "top", "P0")
        assert p0["tag"] == "changed · changed inside" and p0["ring"]["w"] == 2
        assert p0["ring"]["color"] == change and not p0["ring"]["dash"]
        d1, d0 = _mark(run, "nested", "D1"), _mark(run, "nested", "D0")
        assert d1["tag"] == "changed" and d1["ring"]["color"] == change
        assert d0["tag"] == "imports" and d0["ring"]["dash"]
        lost = [m for m in run["nestedAll"]["drawn"] if m["t"] == "changed line"]
        assert sorted(m["f"] for m in lost) == sorted(run["state"]["lost"]), run["state"]
        assert run["state"]["lost"] and all(m["color"] == change for m in lost)
        assert "changed card" in run["top"]["head"] and " since " in run["top"]["head"]
        assert "Change: changed source." in run["tree"] and "Changed inside:" in run["tree"]
        # Acceptance 14.
        for where in ("top", "nested", "nestedAll"):
            assert run[where]["over"] == [], (run["scheme"], where, run[where]["over"])
        assert all(m["map"] == "" for m in run["top"]["drawn"] if m["t"] == "mark")
    out = _drive("--marks", str(plain), nested)
    for run in out["runs"]:
        assert run["errors"] == [], run
        assert not [m for m in run["top"]["drawn"] + run["nested"]["drawn"] if m["t"] == "mark"]
        assert "since" not in run["top"]["head"]


def test_the_tag_of_a_card_with_only_changed_tests() -> None:
    """Acceptance 15."""
    out = _drive("--marks", str(_tests_page()), changes_fixture.DEEP)
    for run in out["runs"]:
        assert run["errors"] == [], run
        d1 = _mark(run, "nested", "D1")
        assert d1["tag"] == "tests" and d1["ring"]["w"] == 1.2 and not d1["ring"]["dash"]
        assert d1["ring"]["color"] == run["tokens"]["change"]
        assert "Change: only tests changed." in run["tree"]
        assert run["nested"]["over"] == [], run["nested"]["over"]


def test_the_text_list_of_the_map_tree() -> None:
    """Acceptance 9."""
    page = _nested_page()
    out = _drive("--tree", str(page))
    assert out["errors"] == [], out
    assert out["label"] == "Map tree"
    data = json.loads(
        page.read_text(encoding="utf-8")
        .split('<script type="application/json" id="atlas-data">')[1]
        .split("</script>")[0]
    )
    maps = data["maps"]
    links = out["links"]
    assert len([x for x in links if x["c"] is None and x["f"] is None]) == 1
    assert len([x for x in links if x["c"] is not None]) == sum(len(m["cards"]) for m in maps)
    assert len([x for x in links if x["f"] is not None]) == sum(len(m["flows"]) for m in maps)
    assert any(x.startswith("Cards of ") for x in out["lists"])
    assert any(x.startswith("Flows of ") for x in out["lists"])
    went = out["went"]
    assert went["current"] == "Gateway" and went["hash"] == went["card"]["href"]


def test_axe_finds_no_violation_with_the_parity_parts() -> None:
    """Acceptance 10."""
    out = _drive("--axe", str(_nested_page()), "Gateway")
    if out["runs"] is None:
        no_axe("the axe-core test needs axe-core on NODE_PATH")
    assert len(out["runs"]) == 2 * (4 + 5)
    for run in out["runs"]:
        assert run["errors"] == [], run
        assert run["axe"]["violations"] == [], run


def test_axe_finds_no_violation_on_the_committed_self_map() -> None:
    """Acceptance 21."""
    out = _drive("--axe", str(REPO / "docs" / "map" / "index.html"), "CLI")
    if out["runs"] is None:
        no_axe("the axe-core test needs axe-core on NODE_PATH")
    assert len(out["runs"]) == 2 * (4 + 5)
    for run in out["runs"]:
        assert run["errors"] == [], run
        assert run["axe"]["violations"] == [], run


FAILED = "The model cannot load: a test error."


def test_live_reloads_the_atlas_page_and_keeps_the_hash(tmp_path: Path) -> None:
    """Acceptance 11."""
    root = _made(tmp_path / "repo", ATLAS)
    flag = tmp_path / "fail"

    def render() -> serve.Rendered:
        if flag.exists():
            raise ConfigError(FAILED + "\nThe second line.")
        return serve.render_tree(root, "")

    live = serve.LiveMap(tmp_path / "out", render, lambda _event: None)
    httpd = serve.make_live_server(live, 0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        live.request()
        live.wait(120)
        top = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
        assert 'id="atlas-data"' in top
        policy = page_csp.of_page(top).split("; ")
        assert "frame-src 'none'" in policy and "connect-src 'self'" in policy
        out = _drive("--live", live.url + "index.html", "#Gateway/Routes", str(flag))
    finally:
        httpd.shutdown()
        httpd.server_close()
        live.close()
    assert out["violations"] == [] and out["errors"] == [] and out["outside"] == [], out
    assert out["sources"] == ["/events", "/events"], out
    assert out["navigations"] == 2, out
    assert [load["hash"] for load in out["loads"]] == ["#Gateway/Routes", "#Gateway/Routes"]
    assert all(load["current"] == "Gateway" and load["atlas"] for load in out["loads"]), out
    assert out["notice"] == "The map is not updated: " + FAILED


@pytest.fixture(autouse=True)
def _needs_browser() -> None:
    browser()
