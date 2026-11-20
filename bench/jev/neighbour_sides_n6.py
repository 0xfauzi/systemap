"""N6: a blind test of the side rule of a nested map, on generated nested maps.

docs/design/atlas.md, rule "Neighbours of a nested map". N5 was not blind: the step of the
side moves was written after N4 failed on the nested map Page. Stage 2 of the open faults of
the atlas page changed the rule again on Page (the count of region columns of the frame,
`place_sides.grid_counts` and `place_sides.fit_rank`). This script measures the rule on
nested maps that a seeded generator makes. The rule was never tuned on these maps.

The generator (`generate`) makes COUNT nested maps from one seed. Each map has one frame
with 3 to 15 parts in 1 to 5 regions, and 2 to 12 neighbours in the actor container. The
flow pattern of the parts is one of PATTERNS: a chain, a star around one hub, tiers with
flows between two tiers that follow, random pairs, and few flows. Each neighbour has flows
with 1 to 6 parts, in one direction or in the two directions. One map of each seed has a
neighbour with no flow. The artifacts are 1 to 6 words, thus some labels are long. The
generator gives a different set for each seed. Before this text, no map of the generator
was laid out or measured.

The measure of each map is the measure of N4 with no change (`neighbour_sides.measure`):
two fresh layouts with `place.compute(model, all_cards=True)`, `column` (nested=False) and
`sides` (nested=True).

Acceptance values, written on 2026-11-20 before the first run of this script. They are the
six values of N4, with no change (bench/jev/neighbour_sides_n4.py). No input of this script
is named `page`, thus value 5 is 80 percent or more on each input. The commands keep the
rule (`place.SIDES_IN_COMMANDS = True`) only if all of them hold.

1. On each input, `refused` and `collisions` of `sides` are not more than those of
   `column`.
2. The total `bends` of `sides` over all inputs is not more than that of `column`.
3. The total `length` of `sides` over all inputs is not more than that of `column`.
4. On each input with an actor, `reach` of `sides` is not more than that of `column`, and
   the total `reach` of `sides` over these inputs is less than that of `column`.
5. On `page`, `shown` of `sides` is 90 percent or more of that of `column`. On each other
   input, it is 80 percent or more.
6. No `sides` layout has a layout problem (`Model.layout_problems`).

N6 uses the seed 6. If N6 fails and the rule changes, N7 uses a new seed that no run used
before, with the same values.

Run from the repository root:
    uv run python bench/jev/neighbour_sides_n6.py [--seed N]
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import neighbour_sides as ns  # noqa: E402  (a neighbour script in bench/jev)

from systemap.model import Component, Container, Flow, Model, Region  # noqa: E402

COUNT = 12
PATTERNS = ("chain", "star", "tiers", "random", "few")
WORDS = (
    "records",
    "paths",
    "names",
    "events",
    "rows",
    "keys",
    "limits",
    "rules",
    "tokens",
    "orders",
    "states",
    "digests",
    "requests",
    "answers",
    "findings",
    "levels",
    "changes",
    "lines",
)


def _artifact(rng: random.Random) -> str:
    words = rng.sample(WORDS, rng.choice((1, 1, 2, 2, 3, 4, 6)))
    if len(words) > 3:
        return ", ".join(" ".join(words[k : k + 2]) for k in range(0, len(words), 2))
    return " ".join(words)


Pairs = set[tuple[int, int]]


def _chain(_rng: random.Random, n: int) -> Pairs:
    return {(k, k + 1) for k in range(n - 1)}


def _star(rng: random.Random, n: int) -> Pairs:
    hub = rng.randrange(n)
    return {(hub, k) if rng.random() < 0.5 else (k, hub) for k in range(n) if k != hub}


def _tiers(rng: random.Random, n: int) -> Pairs:
    tiers = [list(range(n))[k::3] for k in range(3)]
    return {(x, rng.choice(b)) for a, b in zip(tiers, tiers[1:], strict=False) for x in a}


def _pairs(rng: random.Random, n: int, count: int) -> Pairs:
    return {tuple(rng.sample(range(n), 2)) for _ in range(count)}  # type: ignore[misc]


def _part_pairs(rng: random.Random, n: int, pattern: str) -> Pairs:
    """Give the flows between the parts 0 to n - 1 for one pattern."""
    if pattern == "chain":
        return _chain(rng, n)
    if pattern == "star":
        return _star(rng, n)
    if pattern == "tiers":
        return _tiers(rng, n)
    return _pairs(rng, n, int(n * 1.5) if pattern == "random" else max(1, n // 3))


def _one(rng: random.Random, index: int, lonely: bool) -> Model:
    """Give one nested map with no positions."""
    n_parts = rng.randint(3, 15)
    n_actors = rng.randint(2, 12)
    pattern = PATTERNS[index % len(PATTERNS)]
    n_regions = min(rng.randint(1, 5), n_parts)
    regions = tuple(
        Region(id=f"r{k}", label=f"REGION {k}", box=(0, 0, 0, 0), container="part")
        for k in range(n_regions)
    )
    parts = [f"Part{k}" for k in range(n_parts)]
    actors = [f"Near{k}" for k in range(n_actors)]
    cards = [
        Component(
            id=pid,
            does=f"The part {k}.",
            kind="store" if rng.random() < 0.15 else "component",
            region=f"r{k % n_regions}",
        )
        for k, pid in enumerate(parts)
    ]
    cards += [
        Component(id=a, does="A card of the map above.", kind="actor", container="around")
        for a in actors
    ]
    flows = [
        Flow(parts[a], parts[b], _artifact(rng), rng.choice(("data", "control")))
        for a, b in sorted(_part_pairs(rng, n_parts, pattern))
    ]
    for k, a in enumerate(actors):
        if lonely and k == n_actors - 1:
            continue
        reach = rng.choice((1, 1, 2, 3, 6))
        what = _artifact(rng)
        for p in rng.sample(parts, min(reach, n_parts)):
            pair = (a, p) if rng.random() < 0.6 else (p, a)
            flows.append(Flow(pair[0], pair[1], what, "data"))
    return Model(
        canvas=(0, 0),
        containers=(
            Container(id="around", label="AROUND", box=(0, 0, 0, 0), tone="host"),
            Container(id="part", label="PART", box=(0, 0, 0, 0), tone="server"),
        ),
        regions=regions,
        components=tuple(cards),
        flows=tuple(flows),
        flow_kinds=(),
    )


def generate(seed: int, count: int = COUNT) -> dict[str, Model]:
    """Give `count` nested maps of the seed, by name."""
    rng = random.Random(seed)
    lonely = rng.randrange(count)
    return {f"gen {seed}.{k}": _one(rng, k, k == lonely) for k in range(count)}


def verdicts(results: dict[str, dict[str, dict[str, Any]]]) -> list[tuple[str, bool]]:
    """Give the six acceptance values of N4, each with its result. Value 5 is 80 percent on
    each input, because no input is named `page`."""
    col = {n: r["column"] for n, r in results.items()}
    sid = {n: r["sides"] for n, r in results.items()}
    one = all(
        sid[n]["refused"] <= col[n]["refused"] and sid[n]["collisions"] <= col[n]["collisions"]
        for n in results
    )
    bends = (sum(v["bends"] for v in sid.values()), sum(v["bends"] for v in col.values()))
    length = (sum(v["length"] for v in sid.values()), sum(v["length"] for v in col.values()))
    with_actor = [n for n in results if col[n]["reach"] is not None]
    reach = (sum(sid[n]["reach"] for n in with_actor), sum(col[n]["reach"] for n in with_actor))
    four = all(sid[n]["reach"] <= col[n]["reach"] for n in with_actor) and reach[0] < reach[1]
    ratio = {n: sid[n]["shown"] / col[n]["shown"] for n in results}
    worst = min(ratio, key=lambda n: ratio[n])
    return [
        ("1. refused and collisions not more on each input", one),
        (f"2. total bends {bends[0]} against {bends[1]}", bends[0] <= bends[1]),
        (f"3. total length {length[0]} against {length[1]}", length[0] <= length[1]),
        (f"4. reach not more on each input, total {reach[0]:.0f} against {reach[1]:.0f}", four),
        (
            f"5. shown zoom 80 percent or more, smallest {ratio[worst]:.3f} ({worst})",
            ratio[worst] >= 0.8,
        ),
        ("6. no layout problem in a sides layout", all(not sid[n]["problems"] for n in results)),
    ]


def main(argv: list[str]) -> int:
    seed = int(argv[argv.index("--seed") + 1]) if "--seed" in argv else 6
    models = generate(seed)
    results: dict[str, dict[str, dict[str, Any]]] = {}
    print(f"seed {seed}")
    print(
        "| input | layout | canvas | area | zoom | shown | collisions | refused | bends | "
        "length | reach |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for name, model in models.items():
        results[name] = {"column": ns.measure(model, False), "sides": ns.measure(model, True)}
        for layout in ("column", "sides"):
            print(ns._row(name, layout, results[name][layout]), flush=True)
    for name, r in results.items():
        for layout in ("column", "sides"):
            if r[layout]["problems"]:
                print(f"{name} {layout}: {r[layout]['problems']}")
    print()
    found = verdicts(results)
    for text, ok in found:
        print(f"{text}: {'PASS' if ok else 'FAIL'}")
    print(f"Result: {'PASS' if all(ok for _t, ok in found) else 'FAIL'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
