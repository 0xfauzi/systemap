"""The width of a card name on the atlas page: one measure for the check and the page.

The atlas page draws a card name on one line in the embedded Inter font (`page_font`) at
weight 600, with no kerning. When a name is wider than its room, the page cuts the name and
adds three dots. The check uses the same font widths and the same room (`page_name_problems`).
Thus the check reports each name that the page cuts.

The page gets the size and the room of a name from `PAGE_NAME` (`atlas_draw`). At a map
scale `a` of 1.6 or less, the name is `size * a` high and its room is `a` times the room at
scale 1. At a larger scale, the room grows more than the name. On a small card, and on a
neighbour card of a nested map, the page can make the name larger. Then it makes the name
smaller again until the name fits, but not smaller than its base size. Thus a name that has
no problem here always shows in full.

`NAME_ADVANCES` gives the advance of each character from 32 to 126 at weight 600, in units
of 2048 to the em. scripts/inter_subset.py prints these values from the subset font.
"""

from __future__ import annotations

from systemap.model import CARD_W

NAME_ADVANCES = tuple(
    int(value)
    for value in """
    515 658 1071 1318 1332 2057 1357 667 764 764 1105 1378 653 953 653 776 1351 866 1276
    1303 1364 1254 1310 1180 1311 1310 653 674 1378 1378 1378 1113 2047 1490 1350 1509 1479
    1240 1204 1534 1527 567 1188 1441 1158 1889 1555 1574 1321 1583 1336 1332 1352 1507 1490
    2089 1474 1461 1336 764 776 764 986 961 719 1176 1279 1193 1279 1211 796 1281 1254 535
    535 1167 535 1844 1253 1247 1279 1279 813 1125 723 1254 1202 1719 1165 1206 1159 931 734
    931 1378
    """.split()
)
NAME_EM = 2048
NAME_WEIGHT = 600
# The name size at scale 1, the space at the left of the name (an actor has round ends), and
# the space at the right of the name, in map units.
PAGE_NAME = {"size": 13.5, "pad": 13.0, "actor": 20.0, "end": 8.0}


def name_width(name: str) -> float | None:
    """Give the width of a card name on the atlas page at scale 1, in map units.

    Give None when the name has a character that has no measured width."""
    advance = 0
    for char in name:
        code = ord(char) - 32
        if not 0 <= code < len(NAME_ADVANCES):
            return None
        advance += NAME_ADVANCES[code]
    return advance * PAGE_NAME["size"] / NAME_EM


def name_room(kind: str) -> float:
    """Give the width that the atlas page has for the name of a card of this kind at scale 1."""
    pad = PAGE_NAME["actor"] if kind == "actor" else PAGE_NAME["pad"]
    return CARD_W - pad - PAGE_NAME["end"]


def page_name_problems(kind: str, cid: str) -> list[str]:
    """Give the diagnostic for a card name that the atlas page cuts, or no diagnostic."""
    width, room = name_width(cid), name_room(kind)
    if width is None:
        return [f"card {cid}: name width on the atlas page is not measured for all characters"]
    if width <= room:
        return []
    return [
        f"card {cid}: name does not fit on the atlas page ({kind} cards on that page show a "
        f"name of {room:g} units or less on one line, and this one is {width:.0f} units)"
    ]
