"""The Uses and Used by lists of the atlas page, in a browser.

The details of a card that is not an actor give two lists. "Uses" has one row for each other
card that a module of the card imports. "Used by" has one row for each other card with a
module that imports a module of the card. The page calculates the lists from the page data
of the Details panel and the flows of the map (`atlas_details`). The test drives the atlas
page of two small maps in the Chromium of Playwright (tests/atlas_uses.js). The test skips
when Node or the Playwright package is not there, except when SYSTEMAP_BROWSER_TESTS is
"required". Then it fails.

Acceptance values, written on 2026-11-21 before the first run of this test:

U1. On the map of three cards A, B and C, where A imports B and C, C imports B, and two flows
    connect A and C: the Uses list of A is B ("no flow"), then C ("flow: request and 1
    more"). A row gives the counts of the importing and the imported modules.
U2. The Uses list of A tells the module outside the map. The Used by list of A is empty and
    gives its empty text. Each list gives the sentence about imports for type checks.
U3. The Used by list of B is A, then C: the two rows have no flow and one importing module,
    thus the card ID gives the order.
U4. A click on the row of B in the Uses list of A selects B.
U5. On a map where the card Hub imports ten cards, the Uses list shows eight rows and the
    button "Show all 10". A click on the button shows all ten rows and removes the button.

Acceptance values, written on 2026-11-21 before the first run of the order test:

U6. On the map of the cards A (modules a and a2), B, C, D and the actor User, where a imports
    b, c, d and user, a2 imports d, and one flow connects A and B: the Uses list of A is D (no
    flow, 2 importing modules), then C (no flow, 1 importing module), then B (flow). Thus the
    rows with no flow come first although B has the first card ID, and the importing-module
    count comes before the card ID.
U7. On the same map, no list of A or D has a row for the actor User, although User claims the
    module user that a imports.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree
from test_canvas_browser import browser

from systemap.cli import main

DRIVER = Path(__file__).resolve().parent / "atlas_uses.js"
TYPE_NOTE = "These lists include imports for type checks."


def model_text(
    cards: list[str], flows: list[tuple[str, str, str]], more: dict[str, str] | None = None
) -> str:
    """Give a model file with one card for each module `pkg.<card in lower case>`.

    `more` gives the extra arguments of some cards, for example a kind or other modules."""
    rows = []
    for n, card in enumerate(cards):
        x, y = 40 + (n % 5) * 160, 60 + (n // 5) * 130
        extra = (more or {}).get(card, f"implemented_by=('pkg.{card.lower()}',), entry='run'")
        rows.append(
            f"    Component(id={card!r}, region='core', does='Does the work of {card}.', "
            f"interface='run() -> None', {extra}, x={x}, y={y}),"
        )
    width, height = 900, 140 + 130 * ((len(cards) + 4) // 5)
    flow_rows = [f"    Flow({s!r}, {t!r}, {a!r}, 'data')," for s, t, a in flows]
    relations = [f"    ({s!r}, {t!r}): 'The card {s} gives {a} to {t}.'," for s, t, a in flows]
    return "\n".join(
        [
            '"""The system map of pkg."""',
            "from __future__ import annotations",
            "from systemap import Component, Container, Flow, Meaning, Model, Region",
            "CONTAINERS = (Container(id='system', label='PKG', sub='one process', "
            f"box=(16, 16, {width - 32}, {height - 32}), tone='server'),)",
            f"REGIONS = (Region(id='core', label='CORE', box=(30, 40, {width - 60}, "
            f"{height - 80}), container='system'),)",
            "COMPONENTS = (",
            *rows,
            ")",
            "FLOWS = (",
            *flow_rows,
            ")",
            f"MODEL = Model(canvas=({width}, {height}), containers=CONTAINERS, regions=REGIONS, "
            "components=COMPONENTS, flows=FLOWS, flow_kinds=())",
            f"MEANING = Meaning(plain={ {c: 'the part ' + c for c in cards}!r}, relations={{",
            *relations,
            "}, verbs={'data': ('gives to', 'gets from')})",
            "",
        ]
    )


def page(
    root: Path,
    sources: dict[str, str],
    cards: list[str],
    flows: Any,
    more: dict[str, str] | None = None,
) -> Path:
    write_tree(root, {"pkg/__init__.py": "", **sources})
    assert main(["--root", str(root), "init", "--no-ci"]) == 0
    (root / "map/model.py").write_text(model_text(cards, flows, more), encoding="utf-8")
    assert main(["--root", str(root), "extract"]) == 0
    assert main(["--root", str(root), "render"]) == 0
    return root / "docs/map/index.html"


def drive(html: Path, card: str, click: str = "") -> dict[str, Any]:
    argv = [browser(), str(DRIVER), str(html), card, *([click] if click else [])]
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr
    got = dict(json.loads(proc.stdout))
    assert got["errors"] == [], got["errors"]
    return got


@pytest.fixture
def three(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    sources = {
        "pkg/a.py": "from pkg import b, extra\nfrom pkg.c import thing\n\n\ndef run() -> None:\n"
        "    b.run()\n    extra.run()\n    print(thing)\n",
        "pkg/b.py": "def run() -> None:\n    pass\n",
        "pkg/c.py": "from pkg.b import run\n\nthing = run\n",
        "pkg/extra.py": "def run() -> None:\n    pass\n",
    }
    flows = [("A", "C", "request"), ("C", "A", "reply")]
    html = page(tmp_path, sources, ["A", "B", "C"], flows)
    capsys.readouterr()
    return html


def test_the_lists_give_the_cards_in_order(three: Path) -> None:
    """U1, U2 and U3."""
    a = drive(three, "A")["before"]["sections"]
    uses = a["Uses"]
    assert [(r["id"], r["head"]) for r in uses["rows"]] == [
        ("B", "B no flow"),
        ("C", "C flow: request and 1 more"),
    ]
    assert uses["rows"][0]["text"] == "1 module of this card imports 1 module of B."
    assert "Modules of this card also import 1 module outside this map." in uses["notes"]
    assert uses["notes"][-1] == TYPE_NOTE and uses["more"] is None
    assert a["Used by"]["rows"] == []
    assert a["Used by"]["notes"] == ["No module of another card imports this card.", TYPE_NOTE]
    b = drive(three, "B")["before"]["sections"]
    assert [r["id"] for r in b["Used by"]["rows"]] == ["A", "C"]
    assert b["Used by"]["rows"][1]["text"] == "1 module of C imports 1 module of this card."
    assert b["Uses"]["notes"] == ["This card imports no module of another card.", TYPE_NOTE]


def test_a_click_on_a_row_selects_its_card(three: Path) -> None:
    """U4."""
    got = drive(three, "A", "row:B")
    assert got["before"]["sel"] == {"map": "", "id": "A"}
    assert got["after"]["sel"] == {"map": "", "id": "B"}


def test_show_all_gives_each_row(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """U5."""
    leaves = [f"L{n}" for n in range(10)]
    sources = {f"pkg/{leaf.lower()}.py": "def run() -> None:\n    pass\n" for leaf in leaves}
    sources["pkg/hub.py"] = "".join(f"from pkg.{leaf.lower()} import run\n" for leaf in leaves)
    html = page(tmp_path, sources, ["Hub", *leaves], [])
    capsys.readouterr()
    got = drive(html, "Hub", "all")
    before, after = got["before"]["sections"]["Uses"], got["after"]["sections"]["Uses"]
    assert len(before["rows"]) == 10 and sum(r["shown"] for r in before["rows"]) == 8
    assert before["more"] == "Show all 10"
    assert all(r["shown"] for r in after["rows"]) and after["more"] is None
    assert [r["id"] for r in after["rows"]] == sorted(leaves)


def test_the_order_and_the_actor_rule(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """U6 and U7."""
    run = "def run() -> None:\n    pass\n"
    sources = {
        "pkg/a.py": "from pkg import b, c, d, user\n\n\ndef run() -> None:\n    d.run()\n",
        "pkg/a2.py": "from pkg.d import run\n",
        **{f"pkg/{n}.py": run for n in ("b", "c", "d", "user")},
    }
    more = {
        "A": "implemented_by=('pkg.a', 'pkg.a2'), entry='run'",
        "User": "kind='actor', implemented_by=('pkg.user',), entry='run'",
    }
    html = page(tmp_path, sources, ["A", "B", "C", "D", "User"], [("A", "B", "request")], more)
    capsys.readouterr()
    a = drive(html, "A")["before"]["sections"]
    uses = a["Uses"]["rows"]
    assert [(r["id"], r["head"]) for r in uses] == [
        ("D", "D no flow"),
        ("C", "C no flow"),
        ("B", "B flow: request"),
    ]
    assert uses[0]["text"] == "2 modules of this card import 1 module of D."
    assert a["Used by"]["rows"] == []
    d = drive(html, "D")["before"]["sections"]
    assert [r["id"] for r in d["Used by"]["rows"]] == ["A"]
