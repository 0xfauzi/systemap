"""Tests for the seat grid of the label-placement algorithm (audit finding scale-1).

Acceptance:
- SeatGrid.near gives each key whose box overlaps the query box, in dict insertion
  order, after random put, replace, and drop operations.
- Seating.soft and Seating.fixed give the same value and the same type as a full
  scan in placed order.
- place_labels on 200 crowded flows makes fewer than 3,000,000 overlap_area calls.
  The code before the seat grid made 26,514,709 calls (25.6 s). The seats are the
  same as the seats of that code.
- One obstacle box of 1e6 by 1e6 units does not make a cell entry for each cell.
  Seating finishes in less than 10 s and gives the full-scan cost. Before this
  limit, the box made approximately 2.4e8 cell entries: 1e5 by 1e5 took 7.2 s and
  1e6 by 1e6 did not finish in 60 s. An obstacle with a NaN coordinate does not
  raise an error. Before this limit, math.floor raised ValueError.
"""

from __future__ import annotations

import hashlib
import math
import random
import time

import pytest

from systemap import route, seat_grid
from systemap.seat_grid import Box, Placed, SeatGrid, Seating, overlap_area


def _box(rng: random.Random) -> Box:
    return (
        rng.uniform(-100.0, 900.0),
        rng.uniform(-100.0, 700.0),
        rng.uniform(0.0, 220.0),
        rng.uniform(0.0, 40.0),
    )


def _any_box(rng: random.Random) -> Box:
    # Some boxes are wide or have a coordinate that is not finite.
    roll = rng.random()
    if roll < 0.05:
        return (rng.uniform(-5e5, 0.0), rng.uniform(-5e5, 0.0), 1e6, 1e6)
    if roll < 0.08:
        return (math.nan, 10.0, 50.0, 20.0)
    return _box(rng)


def test_near_matches_a_full_scan_in_insertion_order() -> None:
    rng = random.Random(7)
    grid = SeatGrid()
    reference: dict[int, Box] = {}
    for _step in range(3000):
        key = rng.randrange(60)
        if key in reference and rng.random() < 0.3:
            del reference[key]
            grid.drop(key)
        else:
            reference[key] = _any_box(rng)
            grid.put(key, reference[key])
        query = _any_box(rng)
        want = [k for k, b in reference.items() if overlap_area(query, b)]
        got = [k for k in grid.near(query) if overlap_area(query, reference[k])]
        assert got == want


def _full_soft(state: Seating, box: Box, k: int) -> float:
    # The cost of the code before the seat grid: a sum over all placed labels.
    pb = state.pad(box)
    return sum(overlap_area(pb, o.box) for j, o in state.placed.items() if j != k)


def test_costs_match_a_full_scan_with_the_same_type() -> None:
    rng = random.Random(11)
    cands = {k: [(0, True, _box(rng)) for _n in range(20)] for k in range(40)}
    obstacles = [(f"card {i}", _box(rng)) for i in range(15)]
    state = Seating(cands, obstacles, 2.0)
    assert repr(state.soft(cands[0][0][2], 0)) == repr(_full_soft(state, cands[0][0][2], 0))
    for k in range(40):
        for n, (_seg, _longest, box) in enumerate(cands[k]):
            full = sum(overlap_area(box, ob) for _name, ob in obstacles)
            assert repr(state.fixed(k, n)) == repr(full)
            assert repr(state.soft(box, k)) == repr(_full_soft(state, box, k))
        state.put(k, Placed(box=cands[k][0][2], segment=0, on_longest=True, cost=0.0))
    empty = Seating({0: [(0, True, (0.0, 0.0, 5.0, 5.0))]}, [], 2.0)
    assert repr(empty.fixed(0, 0)) == repr(0)


def test_crowded_labels_count_work_and_keep_the_seats(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = [0]
    original = seat_grid.overlap_area

    def count(a: Box, b: Box) -> float:
        calls[0] += 1
        return original(a, b)

    monkeypatch.setattr(seat_grid, "overlap_area", count)
    monkeypatch.setattr(route, "_overlap_area", count)
    routes: dict[int, route.Route] = {}
    for i in range(200):
        y = 40.0 + (i % 40) * 20.0
        x0 = 20.0 + (i // 40) * 10.0
        routes[i] = route.Route(points=[(x0, y), (x0 + 600.0, y)], src_side="E", dst_side="W")
    widths = {i: 60.0 + (i % 7) * 10.0 for i in routes}
    obstacles = [(f"card{c}", (300.0 + 150.0 * c, 0.0, 40.0, 900.0)) for c in range(3)]
    seats = route.place_labels(routes, widths, 13.0, obstacles, (1000.0, 900.0))
    text = "\n".join(
        f"{k} {s.box!r} {s.segment!r} {s.on_longest!r} {s.cost!r} {s.hits!r}"
        for k, s in seats.items()
    )
    # The digest and the 20 collisions are the result of the code before the seat grid.
    assert hashlib.sha256(text.encode()).hexdigest()[:16] == "8c6105b017a6d702"
    assert sum(1 for s in seats.values() if s.cost > 0) == 20
    assert calls[0] < 3_000_000


def test_a_wide_obstacle_does_not_fill_the_grid() -> None:
    # Before the wide set, this box made approximately 2.4e8 cell entries and the
    # constructor did not finish in 60 s. The bound of 10 s is generous.
    start = time.monotonic()
    wide = (0.0, 0.0, 1e6, 1e6)
    state = Seating({0: [(0, True, (10.0, 10.0, 5.0, 5.0))]}, [("card", wide)], 3.0)
    assert repr(state.fixed(0, 0)) == repr(overlap_area((10.0, 10.0, 5.0, 5.0), wide))
    assert time.monotonic() - start < 10.0


def test_an_obstacle_that_is_not_finite_gives_the_full_scan_cost() -> None:
    odd = (math.nan, 0.0, math.inf, 50.0)
    box = (10.0, 10.0, 5.0, 5.0)
    state = Seating({0: [(0, True, box)]}, [("card", odd)], 3.0)
    assert repr(state.fixed(0, 0)) == repr(overlap_area(box, odd))
    state.grid.put(1, odd)
    assert state.grid.near(box) == [1]
    state.grid.drop(1)
    assert state.grid.near(box) == []
