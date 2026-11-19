"""The contrast of the texts and marks of a nested map on the atlas page (stage 11).

In a nested map, the ground of the canvas and of the headline has the token `--inside`, and
the token `--ink-3` has the tone `--ink-3-in` (`atlas_inside`). This test gives each row of
tests/test_atlas_contrast.py that has the ground `--map` again with the ground `--inside`,
and it adds the rows of the new texts and marks of a nested map. The ratio comes from the
tokens, as in that test.

Acceptance values, written on 2026-11-19 before the first run:

1. Each row of `MARKS` and of `FAINT` of tests/test_atlas_contrast.py with the ground `map`
   has a ratio of its floor or more with the ground `inside`, in the light and the dark
   scheme. `--ink-3` is `--ink-3-in` for these rows.
2. Each row of `INSIDE` (the bar, the title of the frame, the line of a neighbour, the mark
   of the locator) has a ratio of its floor or more in the two schemes, and its code is in
   the page.
3. The ground `--inside` is a different color from `--map` in each scheme.
"""

from __future__ import annotations

import pytest
from test_atlas_contrast import FAINT, MARK, MARKS, SCHEMES, TEXT, Faint, _ratio

from systemap import atlas_css, atlas_draw, atlas_inside

CODE = atlas_css.CSS + atlas_inside.CSS + atlas_inside.INSIDE + atlas_draw.DRAW


def _inside(scheme: str) -> dict[str, str]:
    table = dict(SCHEMES[scheme])
    table["ink-3"] = table["ink-3-in"]
    return table


INSIDE = (
    (
        "text of the bar",
        "ink-2",
        "surface",
        TEXT,
        "font:500 14px/20px var(--fs);color:var(--ink-2)",
    ),
    ("name in the bar", "ink", "surface", TEXT, ".inside__at b{color:var(--ink)"),
    ("Back button", "ink", "map", TEXT, "color:var(--ink);font-weight:600;background:var(--map)"),
    (
        "Esc key of the Back button",
        "ink-2",
        "surface",
        TEXT,
        "color:var(--ink-2);background:var(--surface)",
    ),
    (
        "name of a map in the path",
        "ink-2",
        "surface",
        TEXT,
        ".inside__path button{color:var(--ink-2)",
    ),
    ("title of the frame", "ink", "surface", TEXT, "ts, C['--ink'], alpha, 600"),
    ("line of a neighbour", "ink-3", "inside", TEXT, "s, C['--ink-3'], alpha, 0.06"),
    ("marked card of the locator", "focus", "map", MARK, "g.fillStyle = C['--focus']"),
)


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("row", [r for r in MARKS if r[2] == "map"], ids=lambda r: r[0])
def test_each_row_on_the_ground_clears_its_floor_inside(
    scheme: str, row: tuple[str, str, str, float, str]
) -> None:
    """Acceptance 1."""
    what, token, _ground, floor, _code = row
    ratio = _ratio(_inside(scheme), token, "inside")
    assert ratio >= floor, (what, scheme, round(ratio, 2))


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize(
    "row", [r for r in FAINT if r[2] == "map" or r[6] == "map"], ids=lambda r: r[0]
)
def test_each_faint_row_on_the_ground_clears_its_floor_inside(scheme: str, row: Faint) -> None:
    """Acceptance 1."""
    what, token, ground, floor, _code, alpha, under = row
    swap = {"map": "inside"}
    ratio = _ratio(_inside(scheme), token, swap.get(ground, ground), alpha, swap.get(under, under))
    assert ratio >= floor, (what, scheme, round(ratio, 2))


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("row", INSIDE, ids=[r[0] for r in INSIDE])
def test_each_sign_of_a_nested_map_clears_its_floor(
    scheme: str, row: tuple[str, str, str, float, str]
) -> None:
    """Acceptance 2."""
    what, token, ground, floor, code = row
    ratio = _ratio(_inside(scheme), token, ground)
    assert ratio >= floor, (what, scheme, round(ratio, 2))
    assert code in CODE, (what, code)


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_inside_ground_differs(scheme: str) -> None:
    """Acceptance 3."""
    assert SCHEMES[scheme]["inside"] != SCHEMES[scheme]["map"]
