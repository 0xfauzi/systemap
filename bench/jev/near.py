"""What the cards next to a change are worth as a short list, not as a prediction.

`ripple.py` asked whether the map's edges predict where a change spreads, and
the answer was no: no walk recalled the touched cards within ten points of the
import closure at half its size. On the way it measured something else. One hop
either way over the flows names a quarter as many cards as the imports do, and
names a card the pull request really touched about as often.

That is not a prediction, and this file does not call it one. It is a short
list: `delta` would print "these cards sit next to what you changed" as context
beside the lines it already prints.

    list ...... the cards one hop either way over the flows from the seed
    seed ...... the card claiming the file with the most changed lines
    truth ..... the other cards the same pull request touched
    hit ....... the pull requests whose list holds at least one truth card

**The bar, set before the run.** Over the same 366 pull requests, at most six
cards at the median, and a hit in half of them or more. Below either, nothing
ships.

    uv run --project bench/jev python bench/jev/near.py

It reads `results/ripple.json`, which `ripple.py` wrote, and sends nothing
anywhere. Delete that file and run `ripple.py` to rebuild it from GitHub.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path
from typing import Any

from common import DEV_REPOS

from systemap import config, graph, nest
from systemap.evidence import owners

RESULTS = Path(__file__).parent / "results"
ROWS = RESULTS / "ripple.json"
# The bar, stated before the run.
CARDS_AT_MOST = 6
HIT_AT_LEAST = 0.50
# The rules to print beside it: what the same pull requests give with no map at
# all, and what the arrows alone give.
BESIDE = ("forward1", "near2", "imports")


def score(rows: list[dict[str, Any]], label: str) -> dict[str, float]:
    """The median size of one rule's list, and how often it holds a touched card."""
    sizes = [row[f"{label}_size"] for row in rows]
    hits = sum(1 for row in rows if row[f"{label}_recall"] > 0)
    return {
        "median": statistics.median(sizes),
        "mean": statistics.mean(sizes),
        "hit": hits / len(rows),
        "share": statistics.median(row[f"{label}_size"] / row["cards"] for row in rows),
    }


def one_pr(pr: dict[str, Any], seen: dict[str, Any]) -> dict[str, Any] | None:
    """One pull request, scored on the shape `delta` can print."""
    import ripple

    owner, known, both, facts = seen["owner"], seen["known"], seen["both"], seen["facts"]
    modules = [known[f["path"]] for f in pr["files"] if f["path"] in known]
    touched: dict[str, int] = {}
    for module in modules:
        card = owner.get(module, "")
        if card:
            touched[card] = touched.get(card, 0) + 1
    if len(touched) < 2:
        return None
    seed = max(sorted(touched), key=lambda c: touched[c])
    truth = set(touched) - {seed}
    near = set(graph.walk(both, [seed], max_depth=1).reached) - {seed}
    union = set(graph.walk(both, sorted(touched), max_depth=1).reached) - set(touched)
    seeded = {m for m in modules if owner.get(m) == seed}
    imports = ripple.cards_of(ripple.closure(facts, seeded), owner) - {seed}
    return {
        "map": seen["name"],
        "seed_size": len(near),
        "seed_hit": 1 if near & truth else 0,
        "union_size": len(union),
        "imports_size": len(imports),
        "imports_hit": 1 if imports & truth else 0,
        "cards": seen["cards"],
    }


def shipped(name: str, root: Path) -> list[dict[str, Any]]:
    """The list `delta` can actually print, scored the same way.

    The table above seeds from the card holding the file with the most changed
    lines. `delta` reads the facts at two commits, not the diff, so it does not
    know a line count; what it knows is which modules changed. This seeds from
    the card holding the most changed modules instead.

    The union of every changed card's neighbours is measured beside it, because
    that is the obvious shape and it has to be ruled out on a number.
    """
    import ripple

    cfg = config.load(root)
    facts = json.loads(cfg.facts_path.read_text())
    top = nest.load(cfg).top
    seen = {
        "name": name,
        "facts": facts,
        "owner": owners(top.model, facts),
        "known": ripple.module_of_file(facts),
        "both": ripple.undirected(top.model),
        "cards": sum(1 for c in top.model.components if c.kind != "actor"),
    }
    found = [one_pr(pr, seen) for pr in ripple.pulls(name, ripple.SLUGS[name])]
    return [r for r in found if r is not None]


def _table(rows: list[dict[str, Any]]) -> None:
    print(f"{len(rows)} pull requests, {len({r['map'] for r in rows})} repositories\n")
    print(f"{'rule':10} {'cards (median)':>15} {'of the map':>11} {'hit':>6}")
    for label in ("near1", *BESIDE):
        s = score(rows, label)
        mark = "  <- the list" if label == "near1" else ""
        print(f"{label:10} {s['median']:15.1f} {s['share']:11.2f} {s['hit']:6.2f}{mark}")
    print("\nper repository, for the list:")
    print(f"{'repo':12} {'prs':>5} {'cards (median)':>15} {'hit':>6}")
    for name in sorted({row["map"] for row in rows}):
        mine = [row for row in rows if row["map"] == name]
        s = score(mine, "near1")
        print(f"{name:12} {len(mine):5} {s['median']:15.1f} {s['hit']:6.2f}")


def _line(what: str, sizes: list[int], hit: float | None = None) -> str:
    told = (
        f"{statistics.median(sizes):.0f} cards at the median, "
        f"{statistics.quantiles(sizes, n=10)[-1]:.0f} at the ninetieth"
    )
    return f"  {what:45}{told}" + (f", a hit in {hit:.0%}" if hit is not None else "")


def _shapes(found: list[dict[str, Any]]) -> None:
    """What each shape would put in front of a reader, and how often it helps."""
    hit = sum(r["seed_hit"] for r in found) / len(found)
    print(f"\nthe shapes delta could print, over {len(found)} pull requests:")
    print(_line("from the card with the most changed modules:", _sizes(found, "seed"), hit))
    print(_line("from every changed card at once:", _sizes(found, "union")))
    for share in (1 / 3, 1 / 2):
        kept = [r for r in found if r["seed_size"] <= r["cards"] * share]
        print(
            _line(
                f"the first, only below {share:.2f} of the map ({len(kept) / len(found):.0%}):",
                _sizes(kept, "seed"),
                sum(r["seed_hit"] for r in kept) / len(kept),
            )
        )
    import_hit = sum(r["imports_hit"] for r in found) / len(found)
    print(_line("what that card's imports reach, same seed:", _sizes(found, "imports"), import_hit))


def _sizes(rows: list[dict[str, Any]], what: str) -> list[int]:
    return [r[f"{what}_size"] for r in rows]


def main() -> int:
    if not ROWS.exists():
        print(f"no {ROWS}: run bench/jev/ripple.py first", file=sys.stderr)
        return 1
    rows: list[dict[str, Any]] = json.loads(ROWS.read_text())
    _table(rows)
    _shapes([r for name, root in DEV_REPOS.items() for r in shipped(name, root)])

    whole = score(rows, "near1")
    ok = whole["median"] <= CARDS_AT_MOST and whole["hit"] >= HIT_AT_LEAST
    print(
        f"\nthe bar: at most {CARDS_AT_MOST} cards at the median, a hit in "
        f"{HIT_AT_LEAST:.0%} or more"
    )
    print(
        f"measured: {whole['median']:.0f} cards at the median, a hit in {whole['hit']:.0%}: "
        + ("passed" if ok else "failed")
    )
    (RESULTS / "near.json").write_text(
        json.dumps(
            {
                "prs": len(rows),
                "bar": {"cards_at_most": CARDS_AT_MOST, "hit_at_least": HIT_AT_LEAST},
                "rules": {label: score(rows, label) for label in ("near1", *BESIDE)},
                "passed": ok,
            },
            indent=1,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
