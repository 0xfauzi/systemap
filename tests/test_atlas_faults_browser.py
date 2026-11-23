"""Faults of the atlas page that a test of the page on a different repository found.

The test drives the atlas page of a small fixture project in the Chromium of Playwright
(tests/atlas_faults.js). The fixture has the shape of the faults, not the names of that
repository: a top map with more cards than the part of a phone screen above the details
sheet can show. The test skips when Node or the Playwright package is not there, except
when SYSTEMAP_BROWSER_TESTS is "required". Then it fails.

Acceptance values, written on 2026-11-20 before the first run of these tests:

1. On a phone of 390 x 844 px, after the selection of each card of the top map that is
   not an actor (the details sheet is open), no card box on the screen is under the
   visible box of the headline, and the selected card is fully between the bottom of the
   bars at the top and the top of the sheet. No run has a script error.
2. At 1440 x 900, Tab from the canvas goes to no link of the list of the tree, and the
   focus comes back to a button that it had before. Tab still goes to each card of the top
   map on the canvas (the canvas keeps the focus for 9 Tab steps or more). The link of the
   list for the neighbour Auth of the nested map Orchestration has the address "#Auth".
   A click on it opens the top map with the card Auth selected, as a selection of that
   neighbour on the canvas does. No run has a script error.
3. At 1440 x 900 and at 390 x 844, in the All layer at the fit of the whole top map, the
   name of each card of the top map shows in full, with no "...". This includes the long
   name of the card Orchestration, which opens a map. The box of that name is in the box of
   its card, and it is not on the small picture of the map of the card.
4. In the States view at 1440 x 900, each end of each transition is on the outline of its
   state: 8 units or less from it (3 at the start, and 7 before the arrowhead at the end).
   No transition goes more than 2 units into a state that is not one of its two ends. Each
   state shows its full ID, with no "...". No run has a script error.
5. At 1440 x 900, after a selection of the card Cache on the Map view (the card with the
   most flows is Orchestration), the button Focus of the header opens the Focus view on
   Cache. No run has a script error.
"""

from __future__ import annotations

import functools
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree
from test_canvas_browser import browser

from systemap.cli import main

DRIVER = Path(__file__).resolve().parent / "atlas_faults.js"
NAMES = ("Auth", "Store", "Log", "Cache", "Queue", "Mail", "Search", "Billing")
HEAD = "from systemap import Component, Container, Flow, Meaning, Model, Region\n"
# A state machine with the shape of the session transaction of SQLAlchemy 2.1.9: a state ID
# wider than the default state, and two transitions whose straight lines go through other
# states, one of them on a diagonal.
MACHINES = (
    "from systemap import State, StateMachine, Transition\n"
    "MACHINES = (StateMachine(id='work', label='State of a work item', of='Cache', "
    "start=('OPEN',), states=(State('OPEN'), State('WAITING_FOR_A_CONNECTION'), "
    "State('READY'), State('DONE'), State('FAILED'), State('CLOSED')), transitions=("
    "Transition('OPEN', 'WAITING_FOR_A_CONNECTION', 'wait'), "
    "Transition('WAITING_FOR_A_CONNECTION', 'OPEN', 'connected'), "
    "Transition('OPEN', 'READY', 'prepare'), Transition('READY', 'DONE', 'finish'), "
    "Transition('OPEN', 'FAILED', 'error'), Transition('FAILED', 'CLOSED', 'reset'), "
    "Transition('DONE', 'CLOSED', 'close'), Transition('OPEN', 'CLOSED', 'cancel'))),)\n"
)


def _top() -> str:
    """Give the model file of the top map: the card Orchestration opens a map."""
    cards = "".join(
        f'    Component(id="{n}", does="Does the {n.lower()} work.", '
        f'implemented_by=("pkg.{n.lower()}",), entry="run", region="work"),\n'
        for n in NAMES
    )
    flows = "".join(
        f'    Flow("Orchestration", "{n}", "{n.lower()} call", "control"),\n' for n in NAMES
    )
    plain = ", ".join(f'"{n}": "the {n.lower()}"' for n in NAMES)
    said = "".join(
        f'("Orchestration", "{n}"): "The orchestration calls the {n.lower()}.", ' for n in NAMES
    )
    return (
        HEAD + 'CONTAINERS = (Container(id="system", label="SYSTEM", box=(0, 0, 0, 0), '
        'tone="server"),)\n'
        'REGIONS = (Region(id="work", label="WORK", box=(0, 0, 0, 0), container="system"),)\n'
        "COMPONENTS = (\n"
        '    Component(id="Orchestration", does="Calls the other parts.", '
        'implemented_by=("pkg.orchestration.*",), entry="route", region="work", '
        'map="orchestration.py"),\n' + cards + ")\nFLOWS = (\n" + flows + ")\n"
        "MODEL = Model(canvas=(0, 0), containers=CONTAINERS, regions=REGIONS, "
        "components=COMPONENTS, flows=FLOWS, flow_kinds=())\n"
        + MACHINES
        + 'MEANING = Meaning(plain={"Orchestration": "the orchestration", '
        + plain
        + "}, relations={"
        + said
        + "}, machines=MACHINES)\n"
    )


NESTED = (
    HEAD
    + """
CONTAINERS = (
    Container(id="around", label="AROUND", box=(0, 0, 0, 0), tone="host"),
    Container(id="system", label="ORCHESTRATION", box=(0, 0, 0, 0), tone="server"),
)
REGIONS = (Region(id="work", label="WORK", box=(0, 0, 0, 0), container="system"),)
COMPONENTS = (
    Component(id="Auth", does="An adjacent component.", kind="actor", container="around"),
    Component(id="Store", does="An adjacent component.", kind="actor", container="around"),
    Component(id="Routes", does="Takes the routes.", implemented_by=("pkg.orchestration.routes",), entry="route", region="work"),
    Component(id="Views", does="Shows the views.", implemented_by=("pkg.orchestration.views",), entry="view", region="work"),
)
FLOWS = (
    Flow("Routes", "Auth", "auth call", "control"),
    Flow("Views", "Store", "store call", "control"),
)
MODEL = Model(canvas=(0, 0), containers=CONTAINERS, regions=REGIONS, components=COMPONENTS, flows=FLOWS, flow_kinds=())
MEANING = Meaning(
    plain={"Auth": "the auth", "Store": "the store", "Routes": "the routes", "Views": "the views"},
    relations={
        ("Routes", "Auth"): "The routes call the auth.",
        ("Views", "Store"): "The views call the store.",
    },
)
"""
)


def _source() -> dict[str, str]:
    out = {f"pkg/{n.lower()}.py": "def run() -> None:\n    return None\n" for n in NAMES}
    out["pkg/__init__.py"] = ""
    out["pkg/orchestration/__init__.py"] = ""
    out["pkg/orchestration/routes.py"] = (
        "from pkg.auth import run\n\n\ndef route() -> None:\n    return run()\n"
    )
    out["pkg/orchestration/views.py"] = (
        "from pkg.store import run\n\n\ndef view() -> None:\n    return run()\n"
    )
    return out


@pytest.fixture(scope="module")
def shape_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("shape")
    files = {
        "systemap.toml": 'name = "shape"\n[package_roots]\n"pkg" = "pkg"\n'
        '[render]\npage = "atlas"\n',
        "map/model.py": _top(),
        "map/orchestration.py": NESTED,
        **_source(),
    }
    write_tree(root, files)
    for command in ("place", "extract", "render"):
        assert main(["--root", str(root), command]) == 0
    return root / "docs" / "map" / "index.html"


@functools.cache
def _run(page: str, mode: str) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), mode, page], capture_output=True, text=True, timeout=600
    )
    assert proc.returncode == 0, proc.stderr
    return dict(json.loads(proc.stdout))


def _over(a: list[float], b: list[float]) -> bool:
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def test_on_a_phone_the_headline_covers_no_card_while_the_sheet_is_open(
    shape_page: Path,
) -> None:
    """Acceptance 1."""
    out = _run(str(shape_page), "sheet")
    assert out["errors"] == []
    assert len(out["runs"]) == len(NAMES) + 1
    for run in out["runs"]:
        assert run["selected"] == run["id"]
        ask = run["ask"]
        for card in run["cards"]:
            box = [
                card["b"][0],
                card["b"][1],
                card["b"][0] + card["b"][2],
                card["b"][1] + card["b"][3],
            ]
            assert not (ask and _over(ask, box)), (run["id"], card["id"], ask, box)
        sel = run["box"]
        assert sel[1] >= run["bars"] - 0.5, run
        assert sel[1] + sel[3] <= run["sheet"] + 0.5, run


def test_tab_goes_to_no_link_of_the_list_and_a_neighbour_link_goes_out(
    shape_page: Path,
) -> None:
    """Acceptance 2."""
    out = _run(str(shape_page), "keys")
    assert out["errors"] == []
    seen = out["seen"]
    assert [x for x in seen if x["tree"]] == []
    assert seen[-1]["tag"] == "BUTTON"
    assert sum(1 for x in seen if x["id"] == "canvas") >= len(NAMES) + 1
    assert out["link"] == {"href": "#Auth", "tabindex": "-1"}
    assert out["after"]["current"] == ""
    assert out["after"]["sel"] == {"map": "", "id": "Auth"}


def test_the_name_of_a_card_that_opens_a_map_shows_in_full(shape_page: Path) -> None:
    """Acceptance 3."""
    out = _run(str(shape_page), "names")
    assert out["errors"] == []
    for run in out["runs"]:
        drawn = {t["s"]: t["box"] for t in run["texts"]}
        assert [s for s in drawn if s.endswith("...")] == [], run["width"]
        assert {"Orchestration", *NAMES} <= set(drawn), run["width"]
        name, c, p = drawn["Orchestration"], run["card"], run["picture"]
        assert c[0] <= name[0] and name[2] <= c[0] + c[2], run["width"]
        assert c[1] <= name[1] and name[3] <= c[1] + c[3], run["width"]
        assert not _over(name, [p[0], p[1], p[0] + p[2], p[1] + p[3]]), (run["width"], name, p)


def test_each_transition_starts_and_ends_on_its_states(shape_page: Path) -> None:
    """Acceptance 4."""
    out = _run(str(shape_page), "states")
    assert out["errors"] == []
    assert "WAITING_FOR_A_CONNECTION" in out["names"]
    assert [n for n in out["names"] if n.endswith("...")] == []
    assert len(out["edges"]) == 8
    for edge in out["edges"]:
        assert edge["start"] <= 8 and edge["end"] <= 8, edge
        assert edge["through"] == [], edge


def test_the_focus_view_opens_on_the_selected_card(shape_page: Path) -> None:
    """Acceptance 5."""
    out = _run(str(shape_page), "focus")
    assert out["errors"] == []
    assert out["selected"] == {"map": "", "id": "Cache", "focus": "Cache"}
