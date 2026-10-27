"""The search finds the path of lowest cost on the routing grid for one flow.

The grid keeps the open steps of each node in lists. The search calculates the cost of
a segment one time and keeps it. It does not make a set for each step. The search is
the Dijkstra search of the earlier router, with the same heap order and the same float
sums. Thus the routes do not change.

A node number is i * ny + j for the grid point at xs[i] and ys[j]. A state number is
node * 2 + o. The orientation o is 0 for a horizontal step into the node and 1 for a
vertical step. The order of state numbers is the order of the tuples (i, j, o). Thus
the heap gives the states in the same order as the earlier heap of (d, i, j, o).
"""

from __future__ import annotations

import heapq
import math
from collections.abc import Callable

Point = tuple[float, float]
Key = tuple[int, int]
# A port of a component: side, offset, port point, grid node, orientation, and cost.
Port = tuple[str, float, Point, Key, int, float]
# A port at a target node: side, offset, port point, orientation, and cost.
Entry = tuple[str, float, Point, int, float]
Found = tuple[list[Key], Port, Entry]
# The function gives the regions that the grid segment (orientation, key) crosses.
RegionsOf = Callable[[int, Key], set[str]]

BEND_COST = 40.0
USED_LANE_FACTOR = 5.0
FOREIGN_REGION_COST = 40.0
MOVES = ((1, 0, 0), (-1, 0, 0), (0, 1, 1), (0, -1, 1))


class Grid:
    """This class keeps the open steps of each grid node and the use count of each segment.

    A segment is open if it does not go through a card margin or a block.
    """

    def __init__(
        self, xs: list[float], ys: list[float], closed: Callable[[int, Key], bool]
    ) -> None:
        self.ny = len(ys)
        self.segments: list[tuple[int, Key]] = []
        self.lengths: list[float] = []
        self.number: dict[tuple[int, Key], int] = {}
        # For each node: the next state, the orientation, and the segment of each open step.
        self.steps: list[list[tuple[int, int, int]]] = [
            self._open(xs, ys, closed, i, j) for i in range(len(xs)) for j in range(len(ys))
        ]
        self.used = [0] * len(self.segments)
        # For each segment: the step cost without a bend and with a bend, if the segment
        # is in the allowed regions. The sums are in the sequence of the earlier router.
        self.plain = [self._plain(seg) for seg in range(len(self.segments))]
        # For each segment: the number of its set of crossed regions, or -1 if not known.
        self.kind = [-1] * len(self.segments)
        self.kinds: dict[frozenset[str], int] = {}
        self.regions: list[frozenset[str]] = []

    def _open(
        self, xs: list[float], ys: list[float], closed: Callable[[int, Key], bool], i: int, j: int
    ) -> list[tuple[int, int, int]]:
        out: list[tuple[int, int, int]] = []
        for di, dj, orient in MOVES:
            ni, nj = i + di, j + dj
            if not (0 <= ni < len(xs) and 0 <= nj < len(ys)):
                continue
            key = (min(i, ni), j) if orient == 0 else (i, min(j, nj))
            if closed(orient, key):
                continue
            seg = self.number.get((orient, key))
            if seg is None:
                seg = self.number[(orient, key)] = len(self.segments)
                self.segments.append((orient, key))
                self.lengths.append(abs(xs[ni] - xs[i]) if orient == 0 else abs(ys[nj] - ys[j]))
            out.append(((ni * self.ny + nj) * 2 + orient, orient, seg))
        return out

    def use(self, a: Key, b: Key) -> int:
        """Add 1 to the use count of the segment between two adjacent grid nodes.

        Give the segment number.
        """
        (i0, j0), (i1, j1) = a, b
        key = (min(i0, i1), j0) if j0 == j1 else (i0, min(j0, j1))
        seg = self.number[(0 if j0 == j1 else 1, key)]
        self.used[seg] += 1
        self.plain[seg] = self._plain(seg)
        return seg

    def classify(self, crossed: list[frozenset[str]]) -> None:
        """Keep the set of crossed regions of each segment."""
        for seg, regions in enumerate(crossed):
            found = self.kinds.setdefault(regions, len(self.regions))
            if found == len(self.regions):
                self.regions.append(regions)
            self.kind[seg] = found

    def _plain(self, seg: int) -> tuple[float, float]:
        base = self.lengths[seg] * (USED_LANE_FACTOR if self.used[seg] else 1.0)
        return base, base + BEND_COST

    def crossed(self, seg: int, regions_of: RegionsOf) -> int:
        """Give the number of the set of regions that the segment crosses. Keep it."""
        found = self.kind[seg]
        if found < 0:
            regions = frozenset(regions_of(*self.segments[seg]))
            found = self.kinds.setdefault(regions, len(self.regions))
            if found == len(self.regions):
                self.regions.append(regions)
            self.kind[seg] = found
        return found


class _Costs:
    """This class gives the step costs of the segments that need more than Grid.plain.

    The list "other" tells for each set of crossed regions if the set is not in the
    allowed regions. Its last value is True, for a segment with no known set (-1).
    """

    def __init__(self, grid: Grid, regions_of: RegionsOf, allowed: set[str], strict: bool) -> None:
        self.grid = grid
        self.regions_of = regions_of
        self.allowed = allowed
        self.strict = strict
        self.other = [not regions <= allowed for regions in grid.regions] + [True]
        self.costs: list[tuple[float, float] | None] = [None] * len(grid.segments)

    def get(self, seg: int) -> tuple[float, float]:
        """Give the step cost without a bend and with a bend.

        A strict search cannot use a segment that crosses a region that is not allowed.
        The cost of such a segment is infinity. The sums are in the sequence of the
        earlier router: length times the use factor, then the bend, then the region cost.
        """
        grid = self.grid
        kind = grid.kind[seg]
        if kind < 0:
            kind = grid.crossed(seg, self.regions_of)
        if kind >= len(self.other) - 1:
            self.other.insert(kind, not grid.regions[kind] <= self.allowed)
        foreign = self.other[kind]
        found = grid.plain[seg]
        if foreign:
            extra = FOREIGN_REGION_COST + grid.lengths[seg]
            found = (math.inf, math.inf) if self.strict else (found[0] + extra, found[1] + extra)
        self.costs[seg] = found
        return found


def _arrive(
    entries: list[Entry] | None, state: int, d: float, end: tuple[float, int, Entry | None]
) -> tuple[float, int, Entry | None]:
    """Give the lowest total, its last state, and its target port after a visit to the state.

    The earlier search kept the first target port with a total below the lowest total.
    """
    o = state & 1
    for entry in entries or ():
        total = d + entry[4] + (BEND_COST if entry[3] != o else 0.0)
        if total < end[0]:
            end = (total, state, entry)
    return end


def _nodes(prev: list[int], state: int, ny: int) -> tuple[list[Key], int]:
    """Give the grid nodes of the path to the state and the first state of the path."""
    out: list[Key] = [divmod(state >> 1, ny)]
    while prev[state] >= 0:
        state = prev[state]
        out.append(divmod(state >> 1, ny))
    out.reverse()
    return out, state


def _seed(
    starts: list[Port], ny: int, dist: list[float]
) -> tuple[list[tuple[float, int]], dict[int, Port]]:
    """Give the heap of the source ports and the port of each first state."""
    heap: list[tuple[float, int]] = []
    begin: dict[int, Port] = {}
    for port in starts:
        i, j = port[3]
        state = (i * ny + j) * 2 + port[4]
        if port[5] < dist[state]:
            dist[state] = port[5]
            begin[state] = port
            heapq.heappush(heap, (port[5], state))
    return heap, begin


def _walk(
    heap: list[tuple[float, int]],
    paths: tuple[list[float], list[int]],
    entries: dict[int, list[Entry]],
    steps: list[list[tuple[int, int, int]]],
    costs: _Costs,
) -> tuple[float, int, Entry | None]:
    """Take states from the heap in order and make the distances of their neighbors lower.

    Give the lowest total, its last state, and its target port.
    """
    dist, prev = paths
    known, other, plain, kind = costs.costs, costs.other, costs.grid.plain, costs.grid.kind
    pop, push = heapq.heappop, heapq.heappush
    end: tuple[float, int, Entry | None] = (math.inf, -1, None)
    while heap:
        d, state = pop(heap)
        if d > dist[state]:
            continue
        if d >= end[0]:
            break
        end = _arrive(entries.get(state >> 1), state, d, end)
        o = state & 1
        for nstate, orient, seg in steps[state >> 1]:
            step = (known[seg] or costs.get(seg)) if other[kind[seg]] else plain[seg]
            nd = d + step[orient != o]
            if nd < dist[nstate]:
                dist[nstate] = nd
                prev[nstate] = state
                push(heap, (nd, nstate))
    return end


def search(
    grid: Grid,
    regions_of: RegionsOf,
    allowed: set[str],
    strict: bool,
    ports: tuple[list[Port], list[Port]],
) -> Found | None:
    """Give the grid nodes, the source port, and the target port of the path of lowest cost.

    If no path is available, give None.
    """
    starts, targets = ports
    entries: dict[int, list[Entry]] = {}
    for side, off, p, (i, j), orient, cost in targets:
        entries.setdefault(i * grid.ny + j, []).append((side, off, p, orient, cost))
    size = len(grid.steps) * 2
    dist = [math.inf] * size
    prev = [-1] * size
    heap, begin = _seed(starts, grid.ny, dist)
    costs = _Costs(grid, regions_of, allowed, strict)
    steps = grid.steps
    end = _walk(heap, (dist, prev), entries, steps, costs)
    if end[2] is None:
        return None
    nodes, first = _nodes(prev, end[1], grid.ny)
    return nodes, begin[first], end[2]
