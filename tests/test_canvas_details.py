"""The data of the Details panel and the reader tools of the canvas page (`canvas_details`,
`page_canvas_details` and the tools of `canvas_header`).

Acceptance values, written before the first run on 2026-11-08 (step 5 of
docs/design/nested-canvas.md). The values 6, 7, 8 and 9 are measurements of
`bench/jev/canvas_details.py` and `tests/test_canvas_details_browser.py`.

1. The data adds no facts. For each card of the self-map that is not an actor, the
   modules of `sr` are the modules of `page_data.sources`, in the same order. For each
   module, the file (from `f` or the file rule `fr`), the imports, the importers (from
   `im` of the other modules and `ib`), the external imports, the counts of the public
   names and of the tests, the entry points and the public name claims are the values of
   `page_data.sources`.
2. The rules of a map are the invariants and the import rules of the model, with the
   assurance of `assurance.of_model`. A map with no invariants and no import rules has no
   `iv` and no `ir` key.
3. The keys sheet gives only the keys that operate on the canvas page. It has no key of the
   linked page that the canvas does not have (1 to 6, W, B, full screen). F fits the map.
4. The source button gives the 7-character commit, or "commit not recorded" when the facts
   have no commit. Its source records give each line of `unknown`, the full commit, the
   facts file and the model file.
10. The page of the self-map grows by at most 40,000 bytes raw (the parts of this step:
    the data keys, the script part, the CSS, the panel, the keys sheet and the tools). The
    script part has the bytes that the page gets (`page.compact`).
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any

from systemap import (
    assurance,
    canvas_data,
    canvas_details,
    canvas_header,
    canvas_page,
    config,
    facts_file,
    nest,
    page,
    page_canvas_details,
    page_data,
)

REPO = Path(__file__).resolve().parent.parent
B_KEYS = ("mf", "ff", "iv", "ir", "md", "fr", "sr")


@functools.cache
def _self() -> tuple[config.Config, nest.Tree, dict[str, Any], dict[str, Any]]:
    cfg = config.load(REPO)
    tree = nest.load(cfg)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    return cfg, tree, facts, canvas_data.build(cfg, tree, facts)


def _file(m: dict[str, Any], mod: dict[str, Any]) -> str:
    if "f" in mod:
        return str(mod["f"])
    prefix, suffix = m["fr"]
    return prefix + mod["i"].replace(".", "/") + suffix


def _name(m: dict[str, Any], ref: int | str) -> str:
    return str(m["md"][ref]["i"]) if isinstance(ref, int) else ref


def _importers(m: dict[str, Any], j: int) -> list[str]:
    mod = m["md"][j]
    found = [] if mod.get("ia") else [k for k, o in enumerate(m["md"]) if j in o.get("im", [])]
    return sorted(_name(m, x) for x in found + list(mod.get("ib", [])))


def _same_module(m: dict[str, Any], j: int, w: dict[str, Any]) -> None:
    x = m["md"][j]
    assert _file(m, x) == w["file"]
    assert [_name(m, y) for y in x.get("im", [])] == w["imports"]
    assert _importers(m, j) == sorted(w["imported_by"])
    assert x.get("ex", []) == w["external"]
    assert x.get("n", [0, 0]) == [len(w["public_names"]), len(w["tests"])]


def _same_card(m: dict[str, Any], got: dict[str, Any], want: dict[str, Any]) -> int:
    """Compare the records of one card with `page_data.sources`. Give the module count."""
    mo = got.get("mo", [])
    assert [m["md"][j]["i"] for j in mo] == [x["id"] for x in want["modules"]]
    for j, w in zip(mo, want["modules"], strict=True):
        _same_module(m, j, w)
    assert got.get("pt", []) == want["points"]
    assert got.get("sc", []) == [f"{s['module']}:{s['name']}" for s in want["symbol_claims"]]
    return len(mo)


def test_the_source_records_are_the_records_of_the_linked_page() -> None:
    """Acceptance 1."""
    _cfg, tree, facts, data = _self()
    checked = 0
    for nm, m in zip(tree.maps, data["maps"], strict=True):
        actors = {c.id for c in nm.model.components if c.kind == "actor"}
        for cid, want in page_data.sources(nm.model, facts).items():
            got = m.get("sr", {}).get(cid, {})
            if cid in actors:
                assert not got
            else:
                checked += _same_card(m, got, want)
    assert checked >= 100


def test_a_module_that_no_rule_gives_keeps_its_file() -> None:
    """Acceptance 1: the file rule, an empty file, and importers that the page cannot find."""
    table = [
        {
            "id": "a.b",
            "file": "src/a/b.py",
            "imports": ["a.c"],
            "imported_by": ["x.y"],
            "external": [],
            "unknown": [],
            "public_names": [],
            "tests": [],
        },
        {
            "id": "a.c",
            "file": "src/a/c.py",
            "imports": [],
            "imported_by": ["a.b", "a.d"],
            "external": [],
            "unknown": [{"line": 3, "column": 1, "reason": "no parse"}],
            "public_names": [{"name": "n", "kind": "function"}],
            "tests": ["t"],
        },
        {
            "id": "a.d",
            "file": "",
            "imports": [],
            "imported_by": [],
            "external": [],
            "unknown": [],
            "public_names": [],
            "tests": [],
        },
    ]
    sources = {"A": {"modules": table, "points": [], "symbol_claims": []}}
    keys, sr = canvas_details._modules(sources)
    md = keys["md"]
    assert keys["fr"] == ["src/", ".py"]
    assert "f" not in md[0] and "f" not in md[1] and md[2]["f"] == ""
    assert md[0]["ib"] == ["x.y"] and "ia" not in md[0]
    # a.d imports nothing, but the facts give it as an importer of a.c: `ib` gives all.
    assert md[1]["ia"] == 1 and md[1]["ib"] == [0, 2]
    assert md[1]["uk"] == ["Line 3, column 1: no parse"] and md[1]["n"] == [1, 1]
    assert sr == {"A": {"mo": [0, 1, 2]}}


def _same_rules(nm: nest.Map, m: dict[str, Any], facts: dict[str, Any]) -> None:
    model = nm.model
    claims = assurance.by_type(
        assurance.of_model(model, nm.meaning, facts, nm.id), assurance.INVARIANT
    )
    want = [(i.n, i.text, list(i.governs)) for i in sorted(model.invariants, key=lambda i: i.n)]
    assert [(r["n"], r["t"], r.get("g", [])) for r in m.get("iv", [])] == want
    for r in m.get("iv", []):
        claim = claims.get(str(r["n"]))
        assert r.get("as") == ([claim.level, claim.freshness] if claim else None)
    assert [r["id"] for r in m.get("ir", [])] == [r.id for r in model.import_rules]
    assert bool(model.invariants) == ("iv" in m)
    assert bool(model.import_rules) == ("ir" in m)


def test_the_rules_of_a_map_have_their_assurance() -> None:
    """Acceptance 2."""
    _cfg, tree, facts, data = _self()
    for nm, m in zip(tree.maps, data["maps"], strict=True):
        _same_rules(nm, m, facts)
    assert data["maps"][0]["iv"]


def test_the_keys_sheet_has_only_the_keys_of_the_canvas() -> None:
    """Acceptance 3."""
    sheet = page_canvas_details.KEYS_HTML
    for key in ("<kbd>F</kbd>", "<kbd>D</kbd>", "<kbd>?</kbd>", "<kbd>Esc</kbd>", "<kbd>Tab</kbd>"):
        assert key in sheet
    assert "Fit the current map" in sheet
    for gone in ("1 to 6", "<kbd>W</kbd>", "<kbd>B</kbd>", "Full screen", "Whole route"):
        assert gone not in sheet


def _data(rev: str, unknown: list[str]) -> dict[str, Any]:
    return {
        "rev": rev,
        "unknown": unknown,
        "maps": [{"ff": "docs/map/map.json", "mf": "map/model.py"}],
    }


def test_the_source_button_gives_the_commit_and_the_records() -> None:
    """Acceptance 4."""
    rev = "0254afb" + "1" * 33
    tools = canvas_header._tools(_data(rev, ["module pkg.a: no parse", "x < y"]))
    assert "at <code>0254afb</code></button>" in tools
    assert rev in tools and "docs/map/map.json" in tools and "map/model.py" in tools
    assert "Unknown source information" in tools
    assert "<code>module pkg.a: no parse</code>" in tools and "<code>x &lt; y</code>" in tools
    none = canvas_header._tools(_data("", []))
    assert ">commit not recorded</button>" in none and "Unknown source information" not in none


def test_the_page_grows_by_at_most_40000_bytes() -> None:
    """Acceptance 10: the bytes of the parts of this step on the self-map page."""
    cfg, tree, _facts, data = _self()
    added = sum(
        len(json.dumps(m.get(k), ensure_ascii=False, separators=(",", ":")).encode()) + len(k) + 4
        for m in data["maps"]
        for k in B_KEYS
        if k in m
    )
    parts = (
        page.compact(page_canvas_details.DETAILS),
        page_canvas_details.CSS,
        page_canvas_details.HTML,
        canvas_header._tools(data),
    )
    added += sum(len(p.encode()) for p in parts)
    assert added <= 40_000, added
    built = canvas_page.build(canvas_page.tree_theme(cfg, tree), data)
    assert page_canvas_details.HTML in built and canvas_header._tools(data) in built
