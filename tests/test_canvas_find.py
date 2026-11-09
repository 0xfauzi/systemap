"""The Find dialog of the canvas page, with no browser (`page_canvas_find`).

Acceptance values, written before the first run on 2026-11-07:

1. The map page does not change: `page_palette.SCRIPT`, `page_palette.html()` and
   `page_palette.CSS` have the SHA-256 digests of commit d8ac070. The canvas part has the
   match code and the code of the list and of the dialog of the map page as the same text
   (`page_palette.MATCH` and `page_palette.LIST`).
   Change on 2026-11-07, after the C4 check U2 in bench/jev/README.md: in the canvas part,
   the text for no result in the list code has the role option and `aria-disabled`. The
   map page does not change.
   Change on 2026-11-09, after the CodeQL alert js/xss-through-dom: in the canvas part, the
   functions `name`, `row` and `render` of the list code and the glyph helpers make
   elements with DOM functions (`el`). The canvas part has no `innerHTML` and no HTML tag.
   The other list code (from `move`) is the same text as on the map page. The map page
   does not change.
2. The canvas data does not change: the data element of the canvas page is the text of
   `canvas_data.text`. The page has the dialog one time. The Find part (script, CSS and
   dialog) adds 32,000 bytes or less to the canvas page.
3. The ranking (Node, no browser). For the same results and the groups of the map page,
   the ranking of the canvas page (`RANK`) gives the same groups and rows as the ranking of
   `page_palette.SCRIPT`. With the cases of step 8: the group "Other maps" comes after the
   groups of the current map also when its best score is higher; it shows 8 rows or fewer;
   in its shown rows the actors and the flows come after the internal components; the text
   "other" does not show all its rows, but the text "comp" shows all components.
4. The results of the canvas data (Node, stubs of the other parts). The cards and the
   flows of the current map are in Components and Flows, and those of the other maps in
   "Other maps" with the hint "in <map ID>", or "in <system name>" for the top map. A card
   text has 60 characters or fewer. Without the view part, there is no Views, Layers,
   Sequences or Steps group. With it, Views gives Map and the views that the page has,
   Layers gives All and each layer, and the result of a layer calls `setView('map', id)`.
   With sequences in the data (`sq`), Sequences gives the sequences of the current map
   first, and the result of a step calls `setView('sequences')`, `seqChoose` and `seqMode`.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_canvas_page import DATA, _made

from systemap import canvas_data, page_canvas, page_canvas_find, page_palette

DRIVER = Path(__file__).resolve().parent / "canvas_find.js"
LIMIT_BYTES = 32_000

# The digests at commit d8ac070.
DIGESTS = {
    "SCRIPT": "9138677d175f6134447f139f59897e0241615a0a3f2d34a67e0cd2cd8be5cfb2",
    "html": "875b42c71cf73e65bf86e4886fe1668401520dea9efb46bd953736bd7fd074aa",
    "CSS": "639756b60477b7d554e7f5b2f2738d708f7dbbfe49b809eca309ccd4d3a3e7b7",
}


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_the_map_page_does_not_change() -> None:
    """Acceptance 1."""
    found = {
        "SCRIPT": _digest(page_palette.SCRIPT),
        "html": _digest(page_palette.html()),
        "CSS": _digest(page_palette.CSS),
    }
    assert found == DIGESTS
    for shared in (page_palette.MATCH, page_palette.LIST):
        assert shared in page_palette.SCRIPT
    assert page_palette.MATCH.replace("</", "<\\/") in page_canvas_find.FIND
    assert page_canvas_find.LIST in page_canvas_find.FIND
    # The change of the list code: the rows are elements, not HTML text. The text for no
    # result is an option that is not available, because a listbox has only options and
    # groups.
    move = "  function move(k, pointer){"
    assert page_canvas_find.LIST.split(move)[1] == page_palette.LIST.split(move)[1]
    assert "innerHTML" in page_palette.LIST
    assert "innerHTML" not in page_canvas_find.FIND
    assert re.search(r"<[a-z/]", page_canvas_find.FIND) is None
    assert "list.replaceChildren" in page_canvas_find.LIST
    assert "'class':'pal__none', role:'option', 'aria-disabled':'true'" in page_canvas_find.LIST
    assert page_canvas_find.FIND in page_canvas.SCRIPT


@pytest.fixture(scope="module")
def canvas(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = _made(tmp_path_factory.mktemp("find"), "[render]\ncanvas = true\n")
    return root / "docs" / "map" / "index.html"


def test_the_canvas_data_does_not_change(canvas: Path) -> None:
    """Acceptance 2."""
    html = canvas.read_text(encoding="utf-8")
    found = DATA.search(html)
    assert found is not None
    data = json.loads(found.group(1))
    assert found.group(1) == canvas_data.text(data).replace("<", "\\u003c")
    assert html.count('id="palette"') == 1 and html.count(page_canvas_find.HTML) == 1
    assert html.count(page_canvas_find.CSS) == 1
    added = page_canvas_find.FIND + page_canvas_find.CSS + page_canvas_find.HTML
    assert len(added.encode("utf-8")) <= LIMIT_BYTES
    print(
        f"Find part: {len(added.encode('utf-8')):,} bytes raw, "
        f"{len(gzip.compress(added.encode('utf-8'), 6)):,} bytes gzip -6"
    )


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        if os.environ.get("SYSTEMAP_BROWSER_TESTS") == "required":
            pytest.fail("The node command is necessary.")
        pytest.skip("the ranking test needs Node")
    return node


def _run(mode: str, payload: dict[str, Any]) -> dict[str, Any]:
    proc = subprocess.run(
        [_node(), str(DRIVER), mode],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return dict(json.loads(proc.stdout))


def _page_rank() -> str:
    """Give the function `rank` of the map page script."""
    found = re.search(r"  function rank\(text\)\{.*?\n  \}\n", page_palette.SCRIPT, re.S)
    assert found is not None
    return found.group(0)


PAGE_ORDER = ["Views", "Layers", "Components", "Flows", "Sequences", "Steps", "Rules", "Actions"]
PAGE_LIMIT = {"Components": 8, "Flows": 8, "Steps": 6, "Rules": 6}
STEP8_ORDER = [*PAGE_ORDER, "Other maps"]
STEP8_LIMIT = {**PAGE_LIMIT, "Other maps": 8}


def _page_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = [
        {"g": "Views", "t": "Map", "s": "What are the components and their connections?"},
        {"g": "Views", "t": "Changes", "s": "What did this change touch?"},
        {"g": "Layers", "t": "Data", "s": "Which data moves?"},
        {"g": "Actions", "t": "Reduce motion", "words": "motion animation"},
        {"g": "Rules", "t": "Only the store writes the records", "quiet": True},
    ]
    for n in range(12):
        items.append(
            {
                "g": "Components",
                "t": f"Store{n}" if n % 3 else f"Gateway{n}",
                "s": f"keeps the records {n}",
                "quiet": True,
                "more": [f"pkg.store{n}"],
            }
        )
        items.append({"g": "Flows", "t": f"record{n}", "s": f"Store{n} → Log", "quiet": True})
    return items


TEXTS = ["", "store", "st", "record", "comp", "rule", "map", "gw", "pkg.store1", "keeps 4", "zz"]


def test_the_ranking_is_the_ranking_of_the_map_page() -> None:
    """Acceptance 3: the same results and groups as the map page."""
    case = {"order": PAGE_ORDER, "limit": PAGE_LIMIT, "items": _page_items(), "texts": TEXTS}
    out = _run(
        "--rank",
        {
            "match": page_palette.MATCH,
            "ranks": {"page": _page_rank(), "canvas": page_canvas_find.RANK},
            "cases": [case],
        },
    )
    assert out["canvas"] == out["page"]
    assert [g["g"] for g in out["page"][0][1]] == ["Components", "Rules", "Flows"]


def _step8_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = [
        {"g": "Components", "t": "Store", "s": "keeps the records", "quiet": True},
        {"g": "Flows", "t": "record", "s": "Gateway → Store", "quiet": True},
    ]
    # In each other map: an actor, a flow and internal components, in that order of the
    # results. Thus the order of the results is not the order of the rows.
    for m in ("A", "B", "C", "D"):
        hint = f"in {m}"
        items.append({"g": "Other maps", "t": "Store", "late": True, "hint": hint, "quiet": True})
        items.append({"g": "Other maps", "t": "record", "late": True, "hint": hint, "quiet": True})
        items.extend(
            {"g": "Other maps", "t": f"Store{k}", "hint": hint, "quiet": True} for k in range(3)
        )
    return items


def test_the_ranking_has_the_rules_of_step_8() -> None:
    """Acceptance 3: the cases of step 8."""
    case = {
        "order": STEP8_ORDER,
        "limit": STEP8_LIMIT,
        "items": _step8_items(),
        "texts": ["store", "other", "comp", "record"],
    }
    out = _run(
        "--rank",
        {"match": page_palette.MATCH, "ranks": {"canvas": page_canvas_find.RANK}, "cases": [case]},
    )
    store, other, comp, record = out["canvas"][0]
    # "Store" in the other maps has the best score (100) but its group comes last. The group
    # shows 8 rows, and the actors (late) come after the internal components.
    assert [g["g"] for g in store] == ["Components", "Flows", "Other maps"]
    rows = store[2]["rows"]
    assert len(rows) == 8
    assert rows[:4] == ["Store0 in A", "Store1 in A", "Store2 in A", "Store0 in B"]
    assert rows[4:] == ["Store in A", "Store in B", "Store in C", "Store in D"]
    # The group word "other" does not show all rows of the other maps.
    assert [g["g"] for g in other] == ["Other maps"] and len(other[0]["rows"]) == 8
    # The group word "comp" shows all rows of the components.
    assert comp == [{"g": "Components", "rows": ["Store"]}]
    assert [g["g"] for g in record] == ["Flows", "Components", "Other maps"]
    assert record[2]["rows"] == ["record in A", "record in B", "record in C", "record in D"]


def _sample() -> dict[str, Any]:
    def card(cid: str, kind: str = "component", p: str = "", d: str = "") -> dict[str, Any]:
        return {"id": cid, "k": kind, "p": p, "d": d, "b": [0, 0, 10, 10]}

    def flow(s: str, t: str, a: str) -> dict[str, Any]:
        return {"s": s, "t": t, "a": a, "l": "data", "ev": "structural", "p": []}

    long = "keeps " + "the records " * 10
    top = {
        "id": "",
        "cards": [card("User", "actor"), card("Gateway", p=long), card("Store", d="Keeps.")],
        "flows": [flow("Gateway", "Store", "record")],
        "layers": [{"id": "data", "n": "Data", "q": "Which data moves?", "e": [0]}],
        "sq": [
            {
                "id": "get",
                "n": "Get a record",
                "s": [{"f": 0, "a": ["Gateway"], "y": "The gateway asks the store."}],
            }
        ],
    }
    inner = {
        "id": "Gateway",
        "cards": [card("Store", "actor"), card("Routes", p="the routes")],
        "flows": [flow("Routes", "Store", "record")],
        "layers": [],
        "sq": [{"id": "route", "n": "Route a request", "s": [{"f": 0, "y": "The routes ask."}]}],
    }
    return {"name": "shop", "maps": [top, inner]}


def test_the_results_of_the_canvas_data() -> None:
    """Acceptance 4."""
    texts = ["", "store", "gateway", "route"]
    plain = _run(
        "--stub",
        {"script": page_canvas_find.FIND, "data": _sample(), "view": False, "texts": texts},
    )["texts"]
    assert [g["g"] for g in plain[""]] == ["Actions"]
    store = {g["g"]: g["rows"] for g in plain["store"]}
    assert [r["t"] for r in store["Components"]] == ["Store"]
    assert [(r["t"], r["hint"], r["late"]) for r in store["Other maps"]] == [
        ("Store", "in Gateway", True),
        ("record", "in Gateway", True),
    ]
    gateway = {g["g"]: g["rows"] for g in plain["gateway"]}
    assert len(gateway["Components"][0]["s"]) <= 60
    assert gateway["Components"][0]["s"] == ("keeps " + "the records " * 10)[:60]
    assert "Sequences" not in store and "Views" not in store

    inner = _run(
        "--stub",
        {
            "script": page_canvas_find.FIND,
            "data": _sample(),
            "view": True,
            "current": 1,
            "texts": texts,
            "runs": [["data", "Layers", 0], ["routes ask", "Steps", 0], ["route", "Sequences", 0]],
        },
    )
    groups = {g["g"]: g["rows"] for g in inner["texts"][""]}
    assert [r["t"] for r in groups["Views"]] == ["Map", "Sequences"]
    assert groups["Views"][0]["hint"] == "Current"
    assert [r["t"] for r in groups["Layers"]] == ["All", "Data", "Control"]
    assert [(r["t"], r["hint"]) for r in groups["Sequences"]] == [
        ("Route a request", ""),
        ("Get a record", "in shop"),
    ]
    store = {g["g"]: g["rows"] for g in inner["texts"]["store"]}
    assert [(r["t"], r["hint"]) for r in store["Other maps"]][:1] == [("Store", "in shop")]
    layer, step, sequence = inner["runs"]["0"], inner["runs"]["1"], inner["runs"]["2"]
    assert layer == {"done": True, "calls": [["view", "map", "data"]]}
    assert step["done"] and step["calls"][:3] == [
        ["view", "sequences", None],
        ["seq", "Gateway", 0, False],
        ["step", True, 0, True],
    ]
    assert sequence["calls"][:2] == [["view", "sequences", None], ["seq", "Gateway", 0, True]]
