"""The seat grid finds the placed labels near a box.

The label-placement algorithm keeps each placed label box in grid cells. A query
examines only the labels in the cells that the query box touches. A label in a
different cell cannot overlap the query box, so the query gives the same result
as a full scan.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass, field

Box = tuple[float, float, float, float]

# The cell size in map units. A label box is approximately 14 units high and
# 40 to 200 units wide.
CELL = 64.0


def _cells(box: Box) -> Iterator[tuple[int, int]]:
    x, y, w, h = box
    x0, x1 = math.floor(x / CELL), math.floor((x + w) / CELL)
    y0, y1 = math.floor(y / CELL), math.floor((y + h) / CELL)
    for cx in range(x0, x1 + 1):
        for cy in range(y0, y1 + 1):
            yield cx, cy


class SeatGrid:
    """This record keeps label boxes by key, in the order of their first insertion.

    The order is the same as the order of a dict. A new box for a key keeps the
    position of the key. A key that the record removes and adds again goes to
    the end.
    """

    def __init__(self) -> None:
        self._boxes: dict[int, Box] = {}
        self._rank: dict[int, int] = {}
        self._next = 0
        self._cells: dict[tuple[int, int], set[int]] = {}

    def put(self, key: int, box: Box) -> None:
        """This method adds a box or replaces the box of a key."""
        if key in self._boxes:
            self._unlink(key)
        else:
            self._rank[key] = self._next
            self._next += 1
        self._boxes[key] = box
        for cell in _cells(box):
            self._cells.setdefault(cell, set()).add(key)

    def drop(self, key: int) -> None:
        """This method removes the box of a key."""
        self._unlink(key)
        del self._boxes[key]
        del self._rank[key]

    def _unlink(self, key: int) -> None:
        for cell in _cells(self._boxes[key]):
            keys = self._cells[cell]
            keys.discard(key)
            if not keys:
                del self._cells[cell]

    def near(self, box: Box) -> list[int]:
        """This method gives the keys whose cells the box touches, in insertion order.

        The result contains each key whose box overlaps the box. It can also contain
        keys whose boxes do not overlap the box.
        """
        found: set[int] = set()
        for cell in _cells(box):
            keys = self._cells.get(cell)
            if keys:
                found |= keys
        return sorted(found, key=self._rank.__getitem__)


@dataclass
class Placed:
    """This record gives a label position and collision details.

    The hits field identifies touched obstacles. The fix field gives the action from
    measured gutter capacity or label width.
    """

    box: Box
    segment: int
    on_longest: bool
    cost: float
    hits: list[str] = field(default_factory=list)
    fix: str = ""


def overlap_area(a: Box, b: Box) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    w = min(ax + aw, bx + bw) - max(ax, bx)
    h = min(ay + ah, by + bh) - max(ay, by)
    return w * h if w > 0 and h > 0 else 0.0


class Seating:
    """This record keeps the state of one label placement.

    Two seat grids hold the obstacle boxes and the placed label boxes. Thus a cost
    calculation examines only the boxes near a candidate. The sums add the same
    nonzero overlaps in the same order as a full scan, so the costs are equal.
    """

    def __init__(
        self,
        cands: dict[int, list[tuple[int, bool, Box]]],
        obstacles: list[tuple[str, Box]],
        gap: float,
    ) -> None:
        self.cands = cands
        self.obstacles = obstacles
        self.gap = gap
        self.placed: dict[int, Placed] = {}
        self.grid = SeatGrid()
        self.walls = SeatGrid()
        for i, (_name, ob) in enumerate(obstacles):
            self.walls.put(i, ob)
        self.fixed_cost: dict[tuple[int, int], float] = {}

    def pad(self, b: Box) -> Box:
        gap = self.gap
        return (b[0] - gap, b[1] - gap, b[2] + 2 * gap, b[3] + 2 * gap)

    def fixed(self, k: int, n: int) -> float:
        key = (k, n)
        if key not in self.fixed_cost:
            box = self.cands[k][n][2]
            terms = [overlap_area(box, self.obstacles[i][1]) for i in self.walls.near(box)]
            self.fixed_cost[key] = sum(terms) if terms else (0.0 if self.obstacles else 0)
        return self.fixed_cost[key]

    def soft(self, box: Box, k: int) -> float:
        pb = self.pad(box)
        placed = self.placed
        terms = [overlap_area(pb, placed[j].box) for j in self.grid.near(pb) if j != k]
        if terms:
            return sum(terms)
        return 0.0 if any(j != k for j in placed) else 0

    def put(self, k: int, seat: Placed) -> None:
        self.placed[k] = seat
        self.grid.put(k, seat.box)

    def drop(self, k: int) -> None:
        del self.placed[k]
        self.grid.drop(k)

    def seat(self, k: int) -> Placed | None:
        """This method selects a label position from the occupancy state.

        A collision-free position on the longest segment has priority. A collision-free
        position elsewhere has priority over a collision on the longest segment.
        """
        best: Placed | None = None
        for n, (seg, on_longest, box) in enumerate(self.cands[k]):
            cost = self.fixed(k, n) + self.soft(box, k)
            rank = (cost > 0, not on_longest, cost)
            if best is None or rank < (best.cost > 0, not best.on_longest, best.cost):
                best = Placed(box=box, segment=seg, on_longest=on_longest, cost=cost)
            if cost == 0 and on_longest:
                break
        return best

    def repair(self, k: int) -> Placed | None:
        """This method moves earlier labels that block a seat that touches no card.

        Each moved label must find a different clean seat. The method moves two labels
        at most. If more labels block the seat, the gutter is full and the collision
        stays.
        """
        for n, (seg, on_longest, box) in enumerate(self.cands[k]):
            if self.fixed(k, n) > 0:
                continue
            pb = self.pad(box)
            blockers = [j for j in self.grid.near(pb) if overlap_area(pb, self.placed[j].box)]
            if not blockers or len(blockers) > 2:
                continue
            if self._move(
                k, Placed(box=box, segment=seg, on_longest=on_longest, cost=0.0), blockers
            ):
                return self.placed[k]
        return None

    def _move(self, k: int, clean: Placed, blockers: list[int]) -> bool:
        saved = {j: self.placed[j] for j in blockers}
        self.put(k, clean)
        for j in blockers:
            alt = self.seat(j)
            if alt is None or alt.cost > 0:
                break
            self.put(j, alt)
        else:
            return True
        for j, old in saved.items():
            self.put(j, old)
        self.drop(k)
        return False
