"""The A* search gives the path of the Dijkstra search in route_search, with fewer states.

Only a strict search uses it. A strict search cannot use a segment that crosses a region
that is not allowed.

The result of the Dijkstra search is a function of the exact float distances only:
- The path ends at the target state with the lowest tuple (total, distance, state, port
  number).
- The step before a state is the neighbor with the lowest tuple (distance, state) whose
  distance plus the step cost is equal to the distance of the state.
- A source state with a distance equal to its port cost has no step before it.

The A* search keeps these rules. Its bound is lower than the true cost to a target by at
least MARGIN. Thus each state on a path of lowest cost has a key below the lowest total.
The search takes all such states from the heap before it stops. When it takes a state,
it uses the latest distance, and it takes the state again after a decrease. Thus each
such state has its exact distance at the end, and the search gives the same path.

A state is not necessary if the other state of its node has a distance that is lower by
BEND_COST + MARGIN or more. A path through the other state then costs less than the same
path through the state, also after float rounding. If rounding makes the two costs
equal at a later state, the other state has the lower distance and wins the tie. The
search does not continue from such a state. Without MARGIN, a float sum in a different
sequence can give a cost that is one bit higher, and the result changes.

The bound is a cut bound. A path from a node to a target node crosses each row interval
and each column interval between them. All segments in one interval have the same
length. A segment costs its length, or USED_LANE_FACTOR times its length after a use.
"""

from __future__ import annotations

import heapq
import math
from itertools import accumulate

from systemap.route_search import BEND_COST, USED_LANE_FACTOR, Entry, Found, Grid, Key, Port

# Float sums in a different sequence can have a different last bit. The bound is lower
# than the true cost by this value. For path costs below 1e6 and paths of fewer than 1e5
# steps, the sum of such differences is less than 1e6 * 2**-53 * 1e5, about 1.1e-5. This
# sum is less than this value.
MARGIN = 1e-3
# A step: the next state, its column and row, the step costs of the segment, 1 for a
# bend, and the set of crossed regions.
Move = tuple[int, int, int, list[float], int, int]
# The lowest total, its distance, its state, and its port number.
Best = tuple[float, float, int, int]


class Cuts:
    """This class keeps the counts of open segments and unused open segments of each interval.

    It keeps the counts for each set of crossed regions. The grid must know the set of
    crossed regions of each segment.
    """

    def __init__(self, grid: Grid, xs: list[float], ys: list[float]) -> None:
        self.grid = grid
        self.lengths = (
            [b - a for a, b in zip(xs, xs[1:], strict=False)],
            [b - a for a, b in zip(ys, ys[1:], strict=False)],
        )
        # For each orientation and each set of crossed regions: open and unused counts.
        self.counts: tuple[dict[int, tuple[list[int], list[int]]], ...] = ({}, {})
        for seg, (orient, key) in enumerate(grid.segments):
            size = len(self.lengths[orient])
            fresh = ([0] * size, [0] * size)
            total, unused = self.counts[orient].setdefault(grid.kind[seg], fresh)
            total[key[orient]] += 1
            unused[key[orient]] += grid.used[seg] == 0
        # The steps from each state. The column and the row of the next node are indexes
        # into the costs that bound gives: the second half is for a vertical state.
        nx, ny = len(grid.steps) // grid.ny, grid.ny
        # The step costs of each segment, without and with a bend. The steps share these
        # lists, and use() changes them.
        self.step = [list(cost) for cost in grid.plain]
        self.moves: list[list[Move]] = [
            [
                (
                    nstate,
                    (nstate >> 1) // ny + (nstate & 1) * nx,
                    (nstate >> 1) % ny + (nstate & 1) * ny,
                    self.step[seg],
                    int(orient != state & 1),
                    grid.kind[seg],
                )
                for nstate, orient, seg in grid.steps[state >> 1]
            ]
            for state in range(len(grid.steps) * 2)
        ]

    def use(self, seg: int) -> None:
        """Record the first use of a segment."""
        orient, key = self.grid.segments[seg]
        self.counts[orient][self.grid.kind[seg]][1][key[orient]] -= 1
        self.step[seg][:] = self.grid.plain[seg]

    def costs(self, orient: int, allowed: set[str]) -> list[float]:
        """Give the lowest step cost of an allowed segment in each interval, or infinity."""
        regions = self.grid.regions
        kinds = [found for k, found in self.counts[orient].items() if regions[k] <= allowed]
        if not kinds:
            return [math.inf] * len(self.lengths[orient])
        unused = map(any, zip(*(found[1] for found in kinds), strict=True))
        total = map(any, zip(*(found[0] for found in kinds), strict=True))
        return [
            n if free else (n * USED_LANE_FACTOR if some else math.inf)
            for n, free, some in zip(self.lengths[orient], unused, total, strict=False)
        ]


def _sums(costs: list[float], lo: int, hi: int) -> list[float]:
    """Give for each grid line the lowest cost of the crossings to the lines lo to hi."""
    before = list(accumulate(reversed(costs[:lo]), initial=0.0))
    before.reverse()
    return before[:lo] + [0.0] * (hi - lo) + list(accumulate(costs[hi:], initial=0.0))


def bound(
    cuts: Cuts, allowed: set[str], entries: dict[int, list[Entry]]
) -> tuple[list[float], list[float]]:
    """Give costs for the columns and costs for the rows.

    Each list has the values for a horizontal state, then the values for a vertical
    state. For each state, the sum of the cost of its column and the cost of its row is
    lower than the cost to each target port. The sum is infinity if no path can get to a
    target port.

    A horizontal state outside the target rows must turn to a vertical step one time. A
    vertical state outside the target columns must turn to a horizontal step one time.
    """
    ny = cuts.grid.ny
    cols = [n // ny for n in entries]
    rows = [n % ny for n in entries]
    fx = _sums(cuts.costs(0, allowed), min(cols), max(cols))
    fy = _sums(cuts.costs(1, allowed), min(rows), max(rows))
    base = min(entry[4] for found in entries.values() for entry in found) - MARGIN
    turn_x = _turns(fx, min(cols), max(cols))
    turn_y = _turns(fy, min(rows), max(rows))
    return fx + turn_x, list(map(base.__add__, turn_y + fy))


def _turns(costs: list[float], lo: int, hi: int) -> list[float]:
    """Add BEND_COST to the costs of the grid lines that are not from lo to hi."""
    return [c if lo <= n <= hi else c + BEND_COST for n, c in enumerate(costs)]


def _arrive(found: list[Entry], g: float, state: int, best: Best) -> Best:
    """Give the lower of the best tuple and the tuples of the target ports at the state."""
    o = state & 1
    for n, entry in enumerate(found):
        here = (g + entry[4] + (BEND_COST if entry[3] != o else 0.0), g, state, n)
        if here < best:
            best = here
    return best


class _Walk:
    """This class keeps the distances and the heap of one A* search."""

    def __init__(
        self, cuts: Cuts, other: list[bool], lower: tuple[list[float], list[float]]
    ) -> None:
        self.cuts = cuts
        self.grid = cuts.grid
        self.other = other
        self.lower = lower
        self.dist = [math.inf] * len(cuts.moves)
        self.heap: list[tuple[float, float, int]] = []
        self.begin: dict[int, Port] = {}

    def seed(self, starts: list[Port]) -> None:
        """Put the source ports in the heap, with the rule of route_search._seed."""
        ny, dist = self.grid.ny, self.dist
        for port in starts:
            i, j = port[3]
            state = (i * ny + j) * 2 + port[4]
            if port[5] < dist[state]:
                dist[state] = port[5]
                self.begin[state] = port
        fx, fy = self.lower
        nx = len(fx) // 2
        for state in self.begin:
            i, j = divmod(state >> 1, ny)
            o = state & 1
            key = dist[state] + fx[i + o * nx] + fy[j + o * ny]
            heapq.heappush(self.heap, (key, dist[state], state))

    def run(self, entries: dict[int, list[Entry]]) -> Best:
        """Give the lowest tuple (total, distance, state, port number) of a target state."""
        dist, heap, other = self.dist, self.heap, self.other
        fx, fy = self.lower
        # A state is not necessary if the other state of its node is lower by this value.
        moves, worse = self.cuts.moves, BEND_COST + MARGIN
        pop, push = heapq.heappop, heapq.heappush
        best: Best = (math.inf, math.inf, -1, -1)
        # The search stops when the lowest key is above the lowest total.
        limit = math.inf
        while heap and heap[0][0] <= limit:
            _f, g, state = pop(heap)
            if g > dist[state] or dist[state ^ 1] + worse <= g:
                continue
            if state >> 1 in entries:
                best = _arrive(entries[state >> 1], g, state, best)
                limit = best[0]
            for nstate, col, row, cost, bend, kind in moves[state]:
                ng = g + cost[bend]
                if ng < dist[nstate] and not other[kind] and dist[nstate ^ 1] + worse > ng:
                    dist[nstate] = ng
                    push(heap, (ng + fx[col] + fy[row], ng, nstate))
        return best

    def before(self, state: int) -> int:
        """Give the step before the state: the neighbor with the lowest (distance, state).

        Give -1 if no neighbor gives the distance of the state.
        """
        dist, other = self.dist, self.other
        o, goal = state & 1, dist[state]
        best = (math.inf, -1)
        # A step from the state to a neighbor with the same orientation crosses the same
        # segment as a step from that neighbor to the state.
        for nstate, _col, _row, cost, _bend, kind in self.cuts.moves[state]:
            if nstate & 1 != o or other[kind]:
                continue
            straight, turn = cost
            for prev, price in ((nstate, straight), (nstate ^ 1, turn)):
                d = dist[prev]
                if d + price == goal and (d, prev) < best:
                    best = (d, prev)
        return best[1]

    def back(self, state: int) -> tuple[list[Key], int]:
        """Give the grid nodes of the path to the state and the first state of the path."""
        out: list[Key] = [divmod(state >> 1, self.grid.ny)]
        while not (state in self.begin and self.dist[state] == self.begin[state][5]):
            state = self.before(state)
            if state < 0:
                raise RuntimeError("The A* search found no step before a state of the path")
            out.append(divmod(state >> 1, self.grid.ny))
        out.reverse()
        return out, state


def astar(cuts: Cuts, allowed: set[str], ports: tuple[list[Port], list[Port]]) -> Found | None:
    """Give the path of lowest cost of a strict search, as route_search.search gives it.

    If no path is available, give None.
    """
    grid = cuts.grid
    starts, targets = ports
    entries: dict[int, list[Entry]] = {}
    for side, off, p, (i, j), orient, cost in targets:
        entries.setdefault(i * grid.ny + j, []).append((side, off, p, orient, cost))
    if not entries:
        return None
    other = [not regions <= allowed for regions in grid.regions]
    walk = _Walk(cuts, other, bound(cuts, allowed, entries))
    walk.seed(starts)
    total, _g, state, n = walk.run(entries)
    if total == math.inf:
        return None
    nodes, first = walk.back(state)
    return nodes, walk.begin[first], entries[state >> 1][n]
