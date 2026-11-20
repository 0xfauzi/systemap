"""The region order of the placer: the score, the estimate, and the search.

Up to SEARCH_ALL regions, the search tries every order of the regions in each container.
Past that, it starts from a greedy order and exchanges pairs. The router scores the
best orders of the estimate, and the order with the smallest score is the result.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Iterator
from dataclasses import replace

from systemap import place_sides
from systemap.model import Box, Model, Region
from systemap.place_layout import (
    PORT_REACH_X,
    PORT_REACH_Y,
    REGION_COLUMNS,
    ROUTE_CLEAR,
    ROUTED,
    SEARCH_ALL,
    Placement,
    Score,
    _first_layout,
    apply,
)
from systemap.route import place_labels, route_all
from systemap.schematic import LABEL_CHAR_W, LABEL_H, geometry


def score(model: Model) -> Score:
    """This function calculates the routing cost with the page router and label-placement
    algorithm.
    """
    geo = geometry(model)
    edges = [(f.src, f.dst) for f in model.flows]
    canvas = (float(model.canvas[0]), float(model.canvas[1]))
    routes = route_all(
        edges, geo.boxes, geo.actors, geo.blocks, geo.region_boxes, geo.region_of, canvas
    )
    widths = {i: len(model.flows[i].artifact) * LABEL_CHAR_W + 6 for i in routes}
    seats = place_labels(
        routes,
        widths,
        LABEL_H,
        geo.obstacles,
        canvas,
        cards=geo.boxes,
        region_of=geo.region_of,
    )
    length = 0.0
    for route in routes.values():
        pts = route.points
        length += sum(
            abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(pts, pts[1:], strict=False)
        )
    return Score(
        collisions=sum(1 for seat in seats.values() if seat.cost > 0),
        refused=sum(1 for route in routes.values() if route.fallback),
        bends=sum(max(0, len(route.points) - 2) for route in routes.values()),
        length=int(round(length)),
    )


def _crosses(a: tuple[float, float], b: tuple[float, float], box: Box) -> bool:
    """This function finds whether segment a-b crosses a box with route clearance."""
    x, y, w, h = box
    x0, y0 = x - ROUTE_CLEAR, y - ROUTE_CLEAR
    x1, y1 = x + w + ROUTE_CLEAR, y + h + ROUTE_CLEAR
    if abs(a[1] - b[1]) < 1e-9:
        lo, hi = min(a[0], b[0]), max(a[0], b[0])
        return y0 < a[1] < y1 and lo < x1 and hi > x0
    lo, hi = min(a[1], b[1]), max(a[1], b[1])
    return x0 < a[0] < x1 and lo < y1 and hi > y0


def _clear(a: tuple[float, float], b: tuple[float, float], walls: list[Box]) -> bool:
    return not any(_crosses(a, b, wall) for wall in walls)


def _ports(a: Box, b: Box) -> tuple[float, float, float, float]:
    """This function gives the side of a that faces b and the side of b that faces a, as
    the x of each vertical side and the y of each horizontal side.
    """
    dx = (b[0] + b[2] / 2) - (a[0] + a[2] / 2)
    dy = (b[1] + b[3] / 2) - (a[1] + a[3] / 2)
    a_side_x = a[0] + a[2] if dx > 0 else a[0]
    b_side_x = b[0] if dx > 0 else b[0] + b[2]
    a_side_y = a[1] + a[3] if dy > 0 else a[1]
    b_side_y = b[1] if dy > 0 else b[1] + b[3]
    return a_side_x, b_side_x, a_side_y, b_side_y


def _bends(a: Box, b: Box, walls: list[Box]) -> int:
    """This function gives the minimum bend count of one route from card a to card b."""
    ax, ay = a[0] + a[2] / 2, a[1] + a[3] / 2
    bx, by = b[0] + b[2] / 2, b[1] + b[3] / 2
    dx, dy = bx - ax, by - ay
    a_side_x, b_side_x, a_side_y, b_side_y = _ports(a, b)
    if abs(dy) <= PORT_REACH_Y and abs(dx) > a[2]:
        return 0 if _clear((a_side_x, ay), (b_side_x, ay), walls) else 2
    if abs(dx) <= PORT_REACH_X and abs(dy) > a[3]:
        return 0 if _clear((ax, a_side_y), (ax, b_side_y), walls) else 2
    across = _clear((a_side_x, ay), (bx, ay), walls) and _clear((bx, ay), (bx, b_side_y), walls)
    down = _clear((ax, a_side_y), (ax, by), walls) and _clear((ax, by), (b_side_x, by), walls)
    return 1 if across or down else 2


def estimate(model: Model) -> tuple[int, float]:
    """This function calculates minimum bend counts and path lengths from component boxes
    and port reach.
    """
    cards = {c.id: c.box for c in model.components}
    region_of = {c.id: c.region or "" for c in model.components}
    regions = {r.id: r.box for r in model.regions}
    bends = 0
    length = 0.0
    for f in model.flows:
        if f.src == f.dst or f.src not in cards or f.dst not in cards:
            continue
        a, b = cards[f.src], cards[f.dst]
        dx = (b[0] + b[2] / 2) - (a[0] + a[2] / 2)
        dy = (b[1] + b[3] / 2) - (a[1] + a[3] / 2)
        length += abs(dx) + abs(dy)
        allowed = {region_of[f.src], region_of[f.dst]}
        walls = [box for cid, box in cards.items() if cid not in (f.src, f.dst)]
        walls += [box for rid, box in regions.items() if rid not in allowed]
        bends += _bends(a, b, walls)
    return bends, length


def _region_weights(model: Model) -> dict[tuple[str, str], int]:
    """This function counts flows for each region pair in either direction."""
    region_of = {c.id: c.region for c in model.components}
    out: dict[tuple[str, str], int] = {}
    for f in model.flows:
        a, b = region_of.get(f.src), region_of.get(f.dst)
        if a is None or b is None or a == b:
            continue
        out[(a, b)] = out.get((a, b), 0) + 1
        out[(b, a)] = out.get((b, a), 0) + 1
    return out


def _greedy(
    group: list[Region], weights: dict[tuple[str, str], int], ids: list[str]
) -> list[Region]:
    """This function selects region order by connection counts. Equal counts use the listed
    order.
    """
    total = {r.id: sum(w for (a, _b), w in weights.items() if a == r.id) for r in group}
    rank = {rid: k for k, rid in enumerate(ids)}
    left = list(group)
    out: list[Region] = []
    while left:
        if not out:
            pick = max(left, key=lambda r: (total[r.id], -rank[r.id]))
        else:
            pick = max(
                left,
                key=lambda r: (
                    sum(weights.get((r.id, o.id), 0) for o in out),
                    total[r.id],
                    -rank[r.id],
                ),
            )
        out.append(pick)
        left.remove(pick)
    return out


def _groups(model: Model) -> list[list[Region]]:
    """This function groups regions by container in model order, with uncontained regions
    first.
    """
    by: dict[str | None, list[Region]] = {}
    for r in model.regions:
        by.setdefault(r.container, []).append(r)
    return list(by.values())


def _grouped(model: Model) -> tuple[Region, ...]:
    """This function gives the model sequence of the regions, with the regions of each
    container together. The layout and _orders use this sequence. In the model, a region of
    one container can be between two regions of a different container.
    """
    return tuple(r for group in _groups(model) for r in group)


def _orders(model: Model) -> Iterator[tuple[Region, ...]]:
    """This function gives region-order combinations within each container, with the model
    order first.
    """
    perms = [list(itertools.permutations(group)) for group in _groups(model)]
    for combo in itertools.product(*perms):
        yield tuple(r for part in combo for r in part)


def _column(model: Model, order: tuple[Region, ...], columns: int = REGION_COLUMNS) -> Placement:
    """This function sets the layout with the selected region order and `columns` columns of
    regions, with the actors of a nested map in one column."""
    laid = _first_layout(replace(model, regions=order), columns)
    return replace(laid, regions={r.id: laid.regions[r.id] for r in model.regions})


def _form(nested: bool | str) -> place_sides.Form:
    return place_sides.KEPT if nested is True else place_sides.FORMS[str(nested)]


def _laid(
    model: Model,
    order: tuple[Region, ...],
    nested: bool | str = False,
    columns: int = REGION_COLUMNS,
) -> Placement:
    """This function sets the layout with the selected region order. In a nested map, the
    actors then go to the sides of the frame (`place_sides`). True gives the form of the
    commands (`place_sides.KEPT`), and "box" or "study" gives the form of that name.
    """
    laid = _column(model, order, columns)
    if not nested:
        return laid
    return place_sides.around(model, laid, _form(nested))


Ranked = tuple[int, int, int, Score]


def _ranked(model: Model, laid: Placement) -> Ranked:
    """This function gives the rank of a sides layout: the label collisions, the refused
    routes, the area of the map, then the score."""
    got = score(apply(model, laid))
    return (got.collisions, got.refused, laid.canvas[0] * laid.canvas[1], got)


def _move_trials(
    model: Model, column: Placement, form: place_sides.Form, moves: dict[str, str]
) -> Iterator[tuple[Ranked, dict[str, str], Placement]]:
    """This function gives each layout with one actor more at a different side."""
    sides = place_sides.sides_of(model, column, moves) or {}
    for side, ids in sides.items():
        for actor in ids:
            for to in place_sides.SIDES:
                trial = {**moves, actor: to}
                if to == side or place_sides.sides_of(model, column, trial) == sides:
                    continue
                laid = place_sides.around(model, column, form, trial)
                yield _ranked(model, laid), trial, laid


def _clear_sides(model: Model, laid: Placement, nested: bool | str) -> Placement:
    """This function moves actors of a nested map to different sides of the frame while a
    move removes a label collision or a refused route (`place_sides`). Each step keeps the
    move with the smallest rank (`_ranked`).
    """
    if not nested or place_sides.frame_of(model) is None:
        return laid
    order = tuple(next(r for r in model.regions if r.id == i) for i in laid.order)
    column, form = _column(model, order, laid.grid_columns), _form(nested)
    best, moves = _ranked(model, laid), dict[str, str]()
    while best[0] or best[1]:
        found = min(_move_trials(model, column, form, moves), default=None, key=lambda t: t[0])
        if found is None or found[0][:2] >= best[:2]:
            break
        best, moves = found[0], found[1]
        laid = replace(found[2], order=laid.order, tried=laid.tried, routed=laid.routed)
    return replace(laid, score=best[3])


Estimate = tuple[int, float, int]


def _swapped(groups: list[list[Region]]) -> Iterator[tuple[Region, ...]]:
    """This function gives each order with two regions of one container exchanged, in the
    order of the containers and the pairs.
    """
    for g, group in enumerate(groups):
        for i, j in itertools.combinations(range(len(group)), 2):
            swapped = [list(part) for part in groups]
            swapped[g][i], swapped[g][j] = swapped[g][j], swapped[g][i]
            yield tuple(r for part in swapped for r in part)


def _best_swap(
    groups: list[list[Region]],
    best: Estimate,
    try_order: Callable[[tuple[Region, ...]], Estimate],
) -> tuple[Estimate, tuple[Region, ...]] | None:
    """This function tries each exchange of two regions in one container. It gives the
    exchange with the smallest estimate below `best`, or None.
    """
    improved: tuple[Estimate, tuple[Region, ...]] | None = None
    for order in _swapped(groups):
        key = try_order(order)
        if key[:2] < best[:2] and (improved is None or key < improved[0]):
            improved = (key, order)
    return improved


def _swaps(model: Model, try_order: Callable[[tuple[Region, ...]], Estimate]) -> None:
    """This function starts from the greedy order of each container and exchanges two
    regions while an exchange decreases the estimate. `try_order` records each order.
    """
    weights = _region_weights(model)
    listed_ids = [r.id for r in model.regions]
    groups = [_greedy(group, weights, listed_ids) for group in _groups(model)]
    best = try_order(tuple(r for group in groups for r in group))
    while (improved := _best_swap(groups, best, try_order)) is not None:
        best, current = improved
        groups = [[r for r in current if r.container == group[0].container] for group in groups]


def _routed(
    model: Model,
    seen: dict[tuple[str, ...], tuple[Estimate, Placement]],
    listed: tuple[str, ...],
    nested: bool | str = False,
) -> Placement:
    """This function routes the ROUTED best orders of the estimate and the listed order,
    and gives the layout with the smallest score. In a nested map with the side rule, the
    rank is `place_sides.fit_rank`: a larger fit comes before a smaller score.
    """
    ranked = sorted(seen, key=lambda ids: seen[ids][0])
    shortlist = ranked[:ROUTED]
    if listed not in shortlist:
        shortlist.append(listed)
    winner: tuple[tuple[object, ...], Score, tuple[str, ...]] | None = None
    for ids in shortlist:
        key, laid = seen[ids]
        got_score = score(apply(model, laid))
        rank = place_sides.fit_rank(replace(laid, score=got_score)) if nested else ()
        got = ((*rank, got_score, key[2]), got_score, ids)
        if winner is None or got[0] < winner[0]:
            winner = got
    assert winner is not None
    _rank, best_score, best_ids = winner
    return replace(
        seen[best_ids][1],
        order=best_ids,
        score=best_score,
        tried=len(seen),
        routed=len(shortlist),
    )


def _search(model: Model, nested: bool | str = False) -> Placement:
    """This function selects the layout with the smallest measured routing score. In a
    nested map with the side rule, it does the search for each count of region columns of
    `place_sides.grid_counts`, and keeps the result with the smallest `place_sides.fit_rank`.
    It gives the column layout when that result has more label collisions or refused routes
    (`place_sides.kept_or_column`).
    """
    counts = place_sides.grid_counts(model) if nested else (REGION_COLUMNS,)
    found = min((_search_grid(model, nested, n) for n in counts), key=place_sides.fit_rank)
    if not nested or place_sides.frame_of(model) is None:
        return found
    return place_sides.kept_or_column(found, _search_grid(model, False, REGION_COLUMNS))


def _search_grid(model: Model, nested: bool | str, columns: int) -> Placement:
    """This function selects the layout with the smallest measured routing score, with
    `columns` columns of regions."""
    if len(model.regions) <= 1:
        laid = _laid(model, model.regions, nested, columns)
        placed = apply(model, laid)
        laid = replace(laid, order=tuple(r.id for r in model.regions), score=score(placed))
        return _clear_sides(model, laid, nested)

    # Every order laid out and estimated, keyed by its ids; the estimate
    # carries the index so a tie goes to the order tried first.
    seen: dict[tuple[str, ...], tuple[Estimate, Placement]] = {}
    grouped = _grouped(model)

    def try_order(order: tuple[Region, ...]) -> Estimate:
        ids = tuple(r.id for r in order)
        if ids in seen:
            return seen[ids][0]
        laid = _laid(model, order, nested, columns)
        bends, length = estimate(apply(model, laid))
        key = (bends, length, len(seen))
        seen[ids] = (key, laid)
        return key

    if len(model.regions) <= SEARCH_ALL:
        for order in _orders(model):
            try_order(order)
    else:
        try_order(grouped)
        _swaps(model, try_order)
    listed = tuple(r.id for r in grouped)
    return _clear_sides(model, _routed(model, seen, listed, nested), nested)


def _listed(model: Model, nested: bool | str = False) -> Placement:
    """This function sets the layout in the model region order for --keep-order. In a
    nested map with the side rule, it keeps the count of region columns with the smallest
    `place_sides.fit_rank`, or the column layout as `_search` does."""
    counts = place_sides.grid_counts(model) if nested else (REGION_COLUMNS,)
    found = min((_listed_grid(model, nested, n) for n in counts), key=place_sides.fit_rank)
    if not nested or place_sides.frame_of(model) is None:
        return found
    return place_sides.kept_or_column(found, _listed_grid(model, False, REGION_COLUMNS))


def _listed_grid(model: Model, nested: bool | str, columns: int) -> Placement:
    """This function sets the layout in the model region order with `columns` columns."""
    laid = _laid(model, model.regions, nested, columns)
    laid = replace(laid, order=tuple(r.id for r in model.regions), score=score(apply(model, laid)))
    return _clear_sides(model, laid, nested)


def grid_order(model: Model) -> tuple[str, ...]:
    """This function reads region order from a positioned model, by container and grid row."""
    out: list[str] = []
    for group in _groups(model):
        out += [r.id for r in sorted(group, key=lambda r: (r.box[1], r.box[0]))]
    return tuple(out)


def order_line(placement: Placement) -> str:
    """This function formats the region order, routing score, and search counts."""
    assert placement.score is not None
    order = ", ".join(placement.order) if placement.order else "none"
    how = (
        f"{placement.tried} orders examined, {placement.routed} routed"
        if placement.tried
        else "as listed"
    )
    return f"region order: {order}. {placement.score.text()}. {how}"
