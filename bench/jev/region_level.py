"""R1: the count of cards and lines of a map at the region level.

The region level is a proposal for the first view of the canvas page. Each region shows as
one card, and the components in it do not show. An actor stays one card. A component with
no region stays one card. A line connects two cards of this level. A flow between two
components of one region does not show.

For each map and each layer, the script gives:

- the cards and the flows at the component level (the current page),
- the cards at the region level,
- the directed lines: the different ordered pairs of cards that one flow or more connects,
- the pairs: the different pairs of cards with no order (the 3.0.0 page showed one grey
  line for each such pair in its All layer),
- the flows in one region, which the region level does not show,
- the largest count of flows that one directed line stands for.

Acceptance values, written before the first run on 2026-11-15. The limit of 12 is a design
target for a first screen. It is not a measured limit of a reader. The first view of the
linked page of 3.0.0 had 17 lines, and board 3 of the design canvas has 9.

1. The map of this repository, layer System context: 12 cards or fewer and 12 directed
   lines or fewer at the region level, and the directed lines are 60 percent or less of
   the flows of the layer.
2. The map of this repository, layer All: 20 pairs or fewer. The 3.0.0 page showed 16
   groups for this map in its All layer, with 80 flows.
3. In each map of the two trees, the region level applies: the map has two regions or
   more with a component. A map with one region becomes one card, which shows nothing.

The inputs are the canvas data (`canvas_data.build`) of the map of this repository, from
the committed facts, and of the M11 tree (`canvas_frames.m11_tree`, 50 maps, about 30 s).
The M11 tree is a generated fixture, not a real repository. The script sends no data out.

Run from the repository root:
    uv run python bench/jev/region_level.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

import canvas_frames as frames  # noqa: E402

CARD_LIMIT = 12
LINE_LIMIT = 12
PART_LIMIT = 0.6
PAIR_LIMIT = 20


def _self_data() -> dict[str, Any]:
    from systemap import canvas_data, config, facts_file, nest  # noqa: PLC0415

    cfg = config.load(ROOT)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    if not facts:
        raise SystemExit("The committed facts are necessary. Run: systemap refresh")
    return canvas_data.build(cfg, nest.load(cfg), facts)


def _ends(m: dict[str, Any]) -> dict[str, str]:
    """Give the card of the region level for each card of the map."""
    regions = {r["id"] for r in m["regions"]}
    out = {}
    for c in m["cards"]:
        in_region = c["k"] != "actor" and c.get("r") in regions
        out[c["id"]] = "region " + c["r"] if in_region else "card " + c["id"]
    return out


def measure(m: dict[str, Any], flow_ids: list[int]) -> dict[str, Any]:
    """Give the counts of one map for the flows `flow_ids`."""
    ends = _ends(m)
    lines: dict[tuple[str, str], int] = {}
    inside = 0
    touched = set()
    for i in flow_ids:
        f = m["flows"][i]
        a, b = ends[f["s"]], ends[f["t"]]
        touched |= {f["s"], f["t"]}
        if a == b:
            inside += 1
            continue
        lines[(a, b)] = lines.get((a, b), 0) + 1
    return {
        "cards": len(m["cards"]),
        "flows": len(flow_ids),
        "level_cards": len(set(ends.values())),
        "regions": len({e for e in ends.values() if e.startswith("region ")}),
        "lines": len(lines),
        "pairs": len({frozenset(k) for k in lines}),
        "inside": inside,
        "most": max(lines.values(), default=0),
    }


def rows(data: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    out = []
    for m in data["maps"]:
        for lay in m["layers"]:
            if lay["e"]:
                out.append((m["id"] or "(top)", lay["n"], measure(m, lay["e"])))
        out.append((m["id"] or "(top)", "All", measure(m, list(range(len(m["flows"]))))))
    return out


def _show(name: str, found: list[tuple[str, str, dict[str, Any]]]) -> None:
    print(f"== {name}")
    print("map                  layer           cards flows | cards lines pairs inside most")
    for map_id, layer, r in found:
        print(
            f"{map_id[:20]:20} {layer[:15]:15} {r['cards']:5} {r['flows']:5} | "
            f"{r['level_cards']:5} {r['lines']:5} {r['pairs']:5} {r['inside']:6} {r['most']:4}"
        )


def main() -> int:
    own = rows(_self_data())
    _show("the map of this repository", own)
    by_layer = {layer: r for _m, layer, r in own}
    first = by_layer["System context"]
    one = (
        first["level_cards"] <= CARD_LIMIT
        and first["lines"] <= LINE_LIMIT
        and first["lines"] <= PART_LIMIT * first["flows"]
    )
    two = by_layer["All"]["pairs"] <= PAIR_LIMIT
    print(f"acceptance 1: {'PASS' if one else 'FAIL'}")
    print(f"acceptance 2: {'PASS' if two else 'FAIL'}")

    m11 = rows(frames.m11_tree())
    whole = [(m, layer, r) for m, layer, r in m11 if layer == "All"]
    _show("the M11 tree, layer All, the first 6 maps", whole[:6])
    few = [m for m, _layer, r in whole if r["regions"] < 2]
    own_regions = by_layer["All"]["regions"]
    print(f"M11: {len(whole)} maps, {len(few)} with less than two regions")
    three = own_regions >= 2 and not few
    print(f"acceptance 3: {'PASS' if three else 'FAIL'}")
    passed = one and two and three
    print("RESULT:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
