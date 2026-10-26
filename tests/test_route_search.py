"""Tests for the route search (audit finding scale-5).

Acceptance:
- The search gives the same routes as the earlier Dijkstra search of commit 65e5464.
  The test compares a SHA-256 digest of the routes with the digest of that commit. The
  maps have used lanes, used ports, a block, and flows that must cross an unrelated
  region.
- The router finds the regions of each grid segment one time, with the comparisons of
  Router._segment.
- The A* search of a strict search gives the same routes as the Dijkstra search on
  random layouts. Some of these layouts have two paths whose float costs are different
  only in the last bit.
- The A* search takes fewer states from the heap than the Dijkstra search.
"""

from __future__ import annotations

import hashlib
import heapq
import random
from collections.abc import Callable
from typing import Any

import pytest

from systemap import route, route_search
from systemap.route import Box, Router, route_all
from systemap.route_astar import Cuts
from systemap.route_search import Found, Port

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
def test_the_search_gives_the_routes_of_the_earlier_search(
    name: str, make: Callable[[], Layout]
) -> None:
    layout = make()
    routes = route_all(*layout)
    assert len(routes) == len(layout[0]) > 30
    # The layout must have flows that cross an unrelated region, or the test does not
    # examine the second search.
    assert any(r.fallback for r in routes.values()) == bool(layout[4])
    assert _digest(layout) == EARLIER[name]


def test_the_router_finds_the_regions_of_each_segment_one_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = [0]
    segment = Router._segment

    def counted(self: Router, orient: int, key: tuple[int, int]) -> set[str]:
        calls[0] += 1
        return segment(self, orient, key)

    monkeypatch.setattr(Router, "_segment", counted)
    layout = _regions_layout()
    router = Router(*layout[1:])
    route_all(*layout)
    # The earlier search called _segment 428362 times on this layout: one call for
    # each open step of each search. The router now finds all regions at the start.
    assert calls[0] == 0
    grid = router.grid
    found = [frozenset(segment(router, orient, key)) for orient, key in grid.segments]
    assert [grid.regions[kind] for kind in grid.kind] == found
    assert sum(1 for regions in found if regions) > 100


def _random_cards(rng: random.Random) -> tuple[dict[str, Box], tuple[float, float]]:
    """Give cards in a grid with random gaps, and the canvas."""
    cols, rows = rng.randint(2, 6), rng.randint(2, 6)
    gx, gy = rng.choice([40.0, 60.0, 80.0, 120.0]), rng.choice([36.0, 50.0, 80.0, 140.0])
    cards: dict[str, Box] = {}
    for c in range(cols):
        for r in range(rows):
            if rng.random() < 0.15:
                continue
            x = 40.0 + c * (150.0 + gx) + rng.choice([0.0, 3.5, 7.25])
            cards[f"c{c}_{r}"] = (x, 60.0 + r * (56.0 + gy), 150.0, 56.0)
    return cards, (80.0 + cols * (150.0 + gx), 120.0 + rows * (56.0 + gy))


def _random_regions(
    rng: random.Random, cards: dict[str, Box]
) -> tuple[dict[str, Box], dict[str, str]]:
    """Give regions around random groups of cards. The regions can overlap."""
    regions: dict[str, Box] = {}
    region_of: dict[str, str] = {}
    for k in range(rng.randint(0, 4)):
        members = rng.sample(sorted(cards), min(len(cards), rng.randint(1, 4)))
        x0 = min(cards[m][0] for m in members)
        y0 = min(cards[m][1] for m in members)
        x1 = max(cards[m][0] for m in members) + 150.0
        y1 = max(cards[m][1] for m in members) + 56.0
        pad = rng.choice([10.0, 20.0, 25.5])
        regions[f"r{k}"] = (x0 - pad, y0 - pad, x1 - x0 + 2 * pad, y1 - y0 + 2 * pad)
        region_of.update((m, f"r{k}") for m in members)
    return regions, region_of


def _random_layout(seed: int) -> Layout:
    """Give a random layout with cards in a grid, regions, a block, and flows."""
    rng = random.Random(seed)
    cards, canvas = _random_cards(rng)
    ids = sorted(cards)
    regions, region_of = _random_regions(rng, cards)
    pairs = [(rng.choice(ids), rng.choice(ids)) for _ in range(rng.randint(5, 40))]
    edges = [(a, b) for a, b in pairs if a != b]
    blocks: list[Box] = []
    if rng.random() < 0.3:
        blocks.append((rng.uniform(0, 300), rng.uniform(0, 300), 60.0, 20.0))
    actors = set(rng.sample(ids, min(len(ids), rng.randint(0, 2))))
    return edges, cards, actors, blocks, regions, region_of, canvas


def _dijkstra(cuts: Cuts, allowed: set[str], ports: tuple[list[Port], list[Port]]) -> Found | None:
    return route_search.search(cuts.grid, lambda orient, key: set(), allowed, True, ports)


# Seeds 27, 56 and 93 have paths whose float costs are different only in the last bit.
# A search that does not keep the exact float sums gives a different route for them.
@pytest.mark.parametrize("seed", [27, 56, 93, 97, 168, *range(12)])
def test_the_astar_search_gives_the_routes_of_the_dijkstra_search(
    seed: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = _random_layout(seed)
    found = repr(route_all(*layout))
    monkeypatch.setattr(route, "astar", _dijkstra)
    assert found == repr(route_all(*layout))


def test_the_astar_search_takes_fewer_states_from_the_heap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pops = [0]
    pop = heapq.heappop

    def counted(heap: list[Any]) -> Any:
        pops[0] += 1
        return pop(heap)

    monkeypatch.setattr(heapq, "heappop", counted)
    layout = _cards_layout()
    route_all(*layout)
    astar = pops[0]
    pops[0] = 0
    monkeypatch.setattr(route, "astar", _dijkstra)
    route_all(*layout)
    assert astar * 2 < pops[0]
