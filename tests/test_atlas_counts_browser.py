"""The counts of the atlas page agree, and Focus gives the direct importers, in a browser.

The headline of each layer, the Structure layer and the Focus view must give the same number
with the same noun for the same thing. A card is an actor or a component. The Focus headline
gives the reach through flows and, as a separate count, the other cards that import the card
directly (`fcImports` in `atlas_focus`). The
test drives the atlas page in the Chromium of Playwright (tests/atlas_counts.js). The test
skips when Node or the Playwright package is not there, except when SYSTEMAP_BROWSER_TESTS
is "required". Then it fails.

Acceptance values, written on 2026-11-21 before the first run of this test:

R1. On the map of the card Core with flows to F1 and F2, the cards I1, I2 and I3 that import
    the module of Core and have no flow, and the actor User with a flow to Core: the Focus
    headline of Core ends with "a change here can reach 5 of 6 other cards: 2 through
    flows, 3 through imports with no flow". The live region gives the same reach in a
    sentence.
    Changed on 2026-11-21 by the decision of the maintainer after the first run: the import
    count is one step only, and it is not added to the reach. A path of imports with more
    steps gets to almost each card of a framework (on Django, Orm got 34 of 36), so it does
    not inform the reader, and the two counts have different meanings. The new value: the
    card J imports I1 and has no flow. The Focus headline of Core ends with "through flows,
    a change here can reach 2 of 7 other cards · 3 other cards import this card directly"
    (J is not an importer of Core), and the live region gives "Through flows, a change here
    can reach 2 of 7 other cards. 3 other cards import this card directly."
R2. On the same map, the headline of the layer All gives "1 actor · 6 components · 3 flows",
    and a layer with no flow gives "7 cards in 1 region: 1 actor and 6 components". Thus
    7 cards = 1 actor + 6 components, and the Focus total is 7 - 1 = 6 other cards.
    Changed after the first run: the value for All was wrong. The flows of All touch only
    Core, F1 and F2 of the 6 components, thus the rule "N of T" of the headline gives "1 actor
    · 3 of 6 components · 3 flows". The page was correct.
    Changed with R1 on 2026-11-21: the card J makes 7 components and 8 cards. Thus All gives
    "1 actor · 3 of 7 components · 3 flows" and a layer with no flow gives "8 cards in 1
    region: 1 actor and 7 components".
R3. On the map of this repository, the Focus total of Model is the count of the cards less
    one, and the headline of each layer with flows gives totals of actors and components
    whose sum is the count of the cards. The reach of Model is the reach in Python on the
    flows and the imports of the page data, with the same split.
    Changed with R1 on 2026-11-21: the reach of Model is the reach in Python on the flows,
    and the importers are the other cards with a module that imports a module of Model
    directly, from the page data.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_atlas_browser import self_page  # noqa: F401  (fixture)
from test_atlas_uses_browser import page
from test_canvas_browser import browser

DRIVER = Path(__file__).resolve().parent / "atlas_counts.js"


def drive(html: Path, card: str) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), str(html), card], capture_output=True, text=True, timeout=300
    )
    assert proc.returncode == 0, proc.stderr
    got = dict(json.loads(proc.stdout))
    assert got["errors"] == [], got["errors"]
    assert got["chosen"] is True
    return got


@pytest.fixture
def core(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    run = "def run() -> None:\n    pass\n"
    sources = {
        "pkg/core.py": run,
        **{f"pkg/f{n}.py": run for n in (1, 2)},
        **{f"pkg/i{n}.py": "from pkg import core\n\n" + run for n in (1, 2, 3)},
        "pkg/user.py": run,
        "pkg/j.py": "from pkg import i1\n\n" + run,
    }
    more = {"User": "kind='actor', implemented_by=('pkg.user',), entry='run'"}
    cards = ["Core", "F1", "F2", "I1", "I2", "I3", "J", "User"]
    flows = [("Core", "F1", "a"), ("Core", "F2", "b"), ("User", "Core", "c")]
    html = page(tmp_path, sources, cards, flows, more)
    capsys.readouterr()
    return drive(html, "Core")


def test_focus_gives_the_reach_and_the_direct_importers(core: dict[str, Any]) -> None:
    """R1."""
    reach = "flows, a change here can reach 2 of 7 other cards"
    importers = "3 other cards import this card directly"
    assert core["focus"]["counts"].endswith(f"through {reach} · {importers}")
    assert f"Through {reach}. {importers}." in core["focus"]["said"]


def test_the_headline_and_focus_give_the_same_cards(core: dict[str, Any]) -> None:
    """R2."""
    layers = core["layers"]
    assert layers["all"] == "1 actor · 3 of 7 components · 3 flows"
    flat = [t for t in layers.values() if "region" in t]
    assert flat and all(t == "8 cards in 1 region: 1 actor and 7 components" for t in flat)


def reach_set(edges: list[tuple[str, str]], card: str) -> set[str]:
    seen: set[str] = set()
    edge = [card]
    while edge:
        nxt = [t for s, t in edges if s in edge and t != card and t not in seen]
        seen.update(nxt)
        edge = list(dict.fromkeys(nxt))
    return seen


def focus_words(reach: int, others: int, importers: int) -> str:
    """The end of the Focus headline of a card of the top map."""
    verb = "card imports" if importers == 1 else "cards import"
    return (
        f"through flows, a change here can reach {reach} of {others} other "
        f"card{'' if others == 1 else 's'} · {importers} other {verb} this card directly"
    )


def import_links(top: dict[str, Any]) -> list[tuple[str, str]]:
    """The import links of the page data, as `fcImports` gives them: (A, B) when a module of
    B imports a module of A."""
    own = {k: cid for cid, r in top.get("sr", {}).items() for k in r.get("mo", [])}
    md = top.get("md", [])
    out: list[tuple[str, str]] = []
    for j, x in enumerate(md):
        if x.get("ia"):
            importers = [y for y in x.get("ib", []) if isinstance(y, int)]
        else:
            importers = [k for k, o in enumerate(md) if j in o.get("im", [])]
        for y in importers:
            a, b = own.get(j), own.get(y)
            if a and b and a != b and (a, b) not in out:
                out.append((a, b))
    return out


def test_the_counts_of_the_self_map_agree(self_page: tuple[Path, dict[str, Any]]) -> None:  # noqa: F811
    """R3."""
    html, data = self_page
    top = data["maps"][0]
    got = drive(html, "Model")
    ids = {c["id"] for c in top["cards"]}
    total = len(ids)
    flows = [(f["s"], f["t"]) for f in top["flows"] if f["s"] != f["t"] and {f["s"], f["t"]} <= ids]
    by_flow = reach_set(flows, "Model")
    importers = {b for a, b in import_links(top) if a == "Model"}
    assert importers
    assert got["focus"]["counts"].endswith(focus_words(len(by_flow), total - 1, len(importers)))
    both = 0
    for text in got["layers"].values():
        nums = re.findall(r"(\d+) (?:actors?|components?)\b", text)
        if len(nums) == 2:
            both += 1
            assert int(nums[0]) + int(nums[1]) == total, text
    assert both >= 2
