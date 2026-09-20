"""Can the imports propose the walk a person wrote?

`systemap.journeys.propose` follows the imports out of a way in and names
the cards a run would pass through. This scores those proposals against the
journeys the agent wrote by hand on the seven maps: for each written
journey, the way in it covers is found, a path is proposed from that way in,
and the two card lists are compared.

The bar, set before the run: a median overlap of 0.6 or more. Below that,
the proposal is not a starting point, it is a distraction, and
`systemap journeys` would be better off asking the agent from a blank page.

    uv run --project bench/jev python bench/jev/paths.py
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

import propose as journeys
from common import SCRATCH, SYSTEMAP

from systemap import config, nest
from systemap.evidence import mentioned
from systemap.extract import entry_label

MAPS = {"systemap": SYSTEMAP}
MAPS.update(
    {
        d.name.split("-first-map")[0]: d / "repo"
        for d in sorted(SCRATCH.glob("*-first-map-2*"))
        if (d / "summary.json").exists()
    }
)


def covers(journey, point) -> bool:
    """Does this written journey walk from this way in?"""
    text = "\n".join([journey.id, journey.label, *(s.say for s in journey.steps)]).lower()
    return mentioned(point["name"], text)


def rows(name: str, root: Path) -> list[dict]:
    cfg = config.load(root)
    facts = json.loads(cfg.facts_path.read_text())
    tree = nest.load(cfg)
    points = facts.get("entry_points", [])
    out = []
    for m in tree.maps:
        for journey in m.meaning.journeys:
            found = [p for p in points if covers(journey, p)]
            if not found:
                continue
            written = journeys.actors(m.meaning, journey.id)
            best = max(
                (journeys.propose(m.model, facts, p, root) for p in found),
                key=lambda path: journeys.overlap(path.cards, written),
            )
            out.append(
                {
                    "map": name,
                    "journey": journey.id,
                    "entry": entry_label(best.entry),
                    "written": written,
                    "proposed": best.cards,
                    "overlap": journeys.overlap(best.cards, written),
                    "missing_flows": len(best.missing_flows),
                    "hops": len(best.hops),
                }
            )
    return out


def main() -> None:
    found = [row for name, root in MAPS.items() for row in rows(name, root)]
    out = Path(__file__).parent / "results" / "paths.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(found, indent=1))
    scores = [r["overlap"] for r in found]
    print(f"{len(found)} written journeys matched to a way in, over {len(MAPS)} maps")
    for name in MAPS:
        mine = [r["overlap"] for r in found if r["map"] == name]
        if mine:
            print(f"   {name:14} n={len(mine):2}  median {statistics.median(mine):.2f}")
    print(f"   {'all':14} n={len(scores):2}  median {statistics.median(scores):.2f} (bar 0.60)")
    hops = sum(r["hops"] for r in found)
    missing = sum(r["missing_flows"] for r in found)
    print(f"   hops proposed {hops}, of which {missing} have no flow on the map")
    worst = sorted(found, key=lambda r: r["overlap"])[:5]
    for r in worst:
        print(f"   worst: {r['map']}/{r['journey']} {r['overlap']:.2f} from {r['entry']}")
        print(f"      written  {r['written']}")
        print(f"      proposed {r['proposed']}")


if __name__ == "__main__":
    sys.exit(main())
