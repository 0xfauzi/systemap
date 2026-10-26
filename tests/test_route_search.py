"""Tests for the route search (audit finding scale-5).

Acceptance:
- The new search gives the same routes as the earlier Dijkstra search of commit 65e5464.
  The test compares a SHA-256 digest of the routes with the digest of that commit. The
  maps have used lanes, used ports, a block, and flows that must cross an unrelated
  region.
- The search examines the regions of each grid segment one time for each router. The
  earlier search examined them for each step of each search.
"""

from __future__ import annotations

import hashlib

import pytest

from systemap import route
from systemap.route import Box, Router, route_all

Layout = tuple[
    list[tuple[str, str]],
    dict[str, Box],
    set[str],
    list[Box],
    dict[str, Box],
    dict[str, str],
    tuple[float, float],
]


def _regions_layout() -> Layout:
    """Give three region columns. The middle region fills the full canvas height.

    A flow from the left column to the right column must cross the middle region.
    """
    cards: dict[str, Box] = {}
    region_of: dict[str, str] = {}
    regions: dict[str, Box] = {}
    for col, rid in enumerate(("L", "M", "R")):
        x0 = 40.0 + col * 420.0
        regions[rid] = (
            x0 - 20.0,
            0.0 if rid == "M" else 40.0,
            380.0,
            700.0 if rid == "M" else 620.0,
        )
        for row in range(3):
            for k in range(2):
                cid = f"{rid}{row}{k}"
                cards[cid] = (x0 + k * 190.0, 80.0 + row * 200.0, 150.0, 56.0)
                region_of[cid] = rid
    ids = sorted(cards)
    edges = [(a, b) for n, a in enumerate(ids) for b in ids[n + 1 :] if (n + len(b)) % 3 == 0]
    edges += [(b, a) for a, b in edges[:12]]
    blocks: list[Box] = [(500.0, 40.0, 60.0, 20.0)]
    return edges, cards, {"L00"}, blocks, regions, region_of, (1300.0, 700.0)


def _cards_layout() -> Layout:
    """Give a grid of cards without regions and with many flows for each card."""
    cards = {
        f"C{r}{c}": (60.0 + c * 230.0, 60.0 + r * 140.0, 150.0, 56.0)
        for r in range(4)
        for c in range(4)
    }
    ids = sorted(cards)
    edges = [(a, b) for n, a in enumerate(ids) for b in ids[n + 1 :] if (n + ord(b[-1])) % 3 == 0]
    return edges, cards, set(), [], {}, {}, (1000.0, 640.0)


# The SHA-256 digests of the repr of the routes from the earlier search (commit 65e5464).
EARLIER = {
    "regions": "bc0ddeac3e05bb52fc8182656720bd371c7237607cf358d82656203158bbb44c",
    "cards": "a7b10caa326708b13f9d4318c3d73f35ac427be60353980882dd624f12fdee63",
}


def _digest(layout: Layout) -> str:
    routes = route_all(*layout)
    text = "".join(f"{k} {routes[k]!r}\n" for k in sorted(routes))
    return hashlib.sha256(text.encode()).hexdigest()


@pytest.mark.parametrize(("name", "make"), [("regions", _regions_layout), ("cards", _cards_layout)])
def test_the_search_gives_the_routes_of_the_earlier_search(name: str, make: object) -> None:
    layout = make()  # type: ignore[operator]
    routes = route_all(*layout)
    assert len(routes) == len(layout[0]) > 30
    # The layout must have flows that cross an unrelated region, or the test does not
    # examine the second search.
    assert any(r.fallback for r in routes.values()) == bool(layout[4])
    assert _digest(layout) == EARLIER[name]


def test_the_search_examines_the_regions_of_a_segment_one_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = [0]
    segment = Router._segment

    def counted(self: Router, orient: int, key: tuple[int, int]) -> set[str]:
        calls[0] += 1
        return segment(self, orient, key)

    monkeypatch.setattr(Router, "_segment", counted)
    routers: list[Router] = []
    monkeypatch.setattr(route, "Router", lambda *a: routers.append(Router(*a)) or routers[-1])
    layout = _regions_layout()
    route_all(*layout)
    # The earlier search called _segment 428362 times on this layout: one call for
    # each open step of each search. The new search calls it one time for each segment.
    # The grid has fewer than 2 * nx * ny segments.
    assert calls[0] <= 2 * routers[0]._nx * routers[0]._ny
