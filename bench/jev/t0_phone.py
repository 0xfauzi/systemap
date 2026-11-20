"""T0 C3: the opening view of a map on a phone of 390 x 844, today and with 3 other rules.

Today a phone opens a map at a zoom of 0.5 at its top left part (`mapFit` in `atlas_input`:
when the fit is below 0.5). This script measures the opening view of the top map of the
self map, of #Page, and of the top map of the workspace fixture, in the Chromium of
Playwright with a touch screen (bench/jev/t0_phone.js):

- the zoom (the map scale on the screen), and the smallest and largest size of a card name
  in CSS px (the texts of one frame, `systemapCanvas.drawn`);
- the empty band: the rows of the map area (from the bottom of the headline to the bottom of
  the screen) with no card and no line of the layer, as a share of the map area height, the
  longest run of such rows and the run at the bottom;
- the left column: the cards that share the x range of the leftmost column of cards, and how
  many of them are fully on the screen below the headline;
- the part of the width and of the height of the frame of the map on the screen.

It measures the same values for 3 other opening rules. Each rule replaces the zoom of the
phone branch of `mapFit`, with the same top left place (a script edit of the temporary page,
no change of the product code):

- `height`: the zoom that fills the height of the map area of the fit with the map;
- `name11`: the zoom that gives a card name of 11 px (13.5 map units at a zoom of 1);
- `cols2`: the zoom that shows the left two columns of cards (cards with overlapping x ranges
  are one column) in the width of the screen with 14 px at each side.

For each rule it gives the result of two tests, done as the tests do them:

- acceptance 9 of tests/test_atlas_point_browser.py on the top map of the self map: a tap on
  the card of the test (`_card`), then the card is selected, the details are a sheet at the
  bottom, the card box is between the headline and the top of the sheet, and the page has no
  horizontal scroll. A card that is not on the screen at the opening cannot get the tap.
- the 390 x 844 part of `test_the_line_of_a_neighbour_is_readable_at_the_fit`
  (tests/test_atlas_inside_browser.py, Z1 and Z4d) on Page and on the maps P0, P0/Q0 and
  P0/Q0/Deep of the M11 tree, in the light scheme: each neighbour card has its line "on ...",
  the line draws, its alpha is 1, and it is in the card box. The page logs the line of a
  neighbour only for a card that it draws, thus a neighbour that is not on the screen fails
  the test. The test does not use the top map.

This is a baseline measurement for the targets of stages 3 and 4 of the open faults. It has
no acceptance value.

Run from the repository root (Node and the Playwright package must be installed):
    uv run python bench/jev/t0_phone.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import t0_common as common  # noqa: E402

DRIVER = HERE / "t0_phone.js"
RULE = (
    "if (!wide && k * m.T.s < 0.5 && !whole) {k = 0.5 / m.T.s;",
    "if (!wide && (window.__T0RULE || k * m.T.s < 0.5) && !whole) {"
    "k = window.__T0RULE ? window.__T0RULE(m, b, Hs - top - bottom, W) : 0.5 / m.T.s;",
)
RULES = ("today", "height", "name11", "cols2")


def card(data: dict[str, Any]) -> str:
    """The card of acceptance 9 (`_card` of tests/test_atlas_point_browser.py)."""
    top = data["maps"][0]
    count: dict[str, int] = {}
    for i in top["layers"][0]["e"]:
        for end in ("s", "t"):
            count[top["flows"][i][end]] = count.get(top["flows"][i][end], 0) + 1
    cards = [c["id"] for c in top["cards"] if c["k"] != "actor"]
    return max(cards, key=lambda c: (count.get(c, 0), c))


def row(page: str, rule: str, r: dict[str, Any]) -> str:
    """Give one table row."""
    names = "-" if r["names"] is None else f"{r['names'][0]:.1f} to {r['names'][1]:.1f}"
    z1 = r["z1"]
    z1_text = (
        f"{'pass' if z1['pass'] else 'fail'} ({z1['drawn']} of {z1['actors']} lines draw, "
        f"sizes {z1['sizes']})"
        if r["id"] != "top"
        else "not in the test (top map)"
    )
    a9 = r.get("a9")
    a9_text = (
        "-"
        if a9 is None
        else ("pass" if a9["pass"] else "fail")
        + ("" if a9["tappable"] else " (card not on the screen)")
    )
    return (
        f"| {page} {r['id']} | {rule} | {r['zoom']:.3f} | {names} | {r['emptyShare']:.2f} "
        f"({r['empty']} of {r['area']} rows, longest {r['longest']}, bottom {r['bottomRun']}) | "
        f"{r['left']['seen']} of {r['left']['n']} | {r['frameSeen'][0]:.2f} / "
        f"{r['frameSeen'][1]:.2f} | {a9_text} | {z1_text} | {r['scroll']} |"
    )


def main() -> int:
    self_theme, self_data = common.self_data()
    pages = {
        "self": (self_theme, self_data, "top,Page", card(self_data)),
        "workspace": (*common.workspace_data(), "top", None),
        "M11": (*common.m11_data(), "P0,P0/Q0,P0/Q0/Deep", None),
    }
    print(
        "| Map | Rule | Zoom | Card name (px) | Empty band share | Left column on the screen "
        "| Frame on the screen, width / height | Acceptance 9 | Z1 at 390 | Scroll width |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|")
    with tempfile.TemporaryDirectory() as tmp:
        for page, (theme, data, maps, test_card) in pages.items():
            html = common.write(Path(tmp) / f"{page}.html", theme, data, (RULE,))
            for rule in RULES:
                args = [str(html), rule, maps] + ([test_card] if test_card else [])
                out = common.drive(DRIVER, *args)
                for r in out["maps"]:
                    print(row(page, rule, r), flush=True)
    print(f"\nThe card of acceptance 9 on the self map: {card(self_data)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
