"""Can a task written before the work name the cards the work will touch?

`systemap plan "<task>"` would project a piece of work onto the map: these
cards will change, and here is what each is for. Before building it, the
projection has to be good enough to act on.

The truth is the issue set already built for triage: a real bug report, and
the cards the pull request that fixed it actually touched
(`data/issues.jsonl`, `label.owners`). The input is the report alone, written
before anyone did the work, which is what a plan is. Jev's answer to the
triage question is a probability over every card, and those answers are
already recorded (`results/issues.jsonl.gz`), so the whole curve is scored
here without sending anything.

**The bar, set before the run:** the projection covers 70% of the cards the
fix touched, with no more than 2 extra cards per issue on average. A
projection that names three cards to find one is a list to argue with, not a
plan to work from.

    uv run --project bench/jev python bench/jev/plan_eval.py
    JEV_SET=holdout uv run --project bench/jev python bench/jev/plan_eval.py
"""

from __future__ import annotations

import statistics
import sys
from typing import Any

from common import SET
from score import results, rows

# The bar, stated before the run.
COVER_AT_LEAST = 0.70
EXTRA_AT_MOST = 2.0
# The thresholds the curve is read at: a card is in the projection when Jev
# gives it at least this much of the probability.
CUTS = (0.5, 0.3, 0.2, 0.1, 0.05, 0.02)
NONE = "none of these"


def projection(probabilities: dict[str, float], cut: float) -> set[str]:
    return {cid for cid, p in probabilities.items() if p >= cut and cid != NONE}


def scored(cut: float, pairs: list[tuple[set[str], set[str]]]) -> dict[str, float]:
    """How much of each fix the projection covered, and how much it added."""
    covered = [len(found & truth) / len(truth) for found, truth in pairs]
    extra = [len(found - truth) for found, truth in pairs]
    whole = [1.0 for found, truth in pairs if truth <= found]
    return {
        "cut": cut,
        "cover": statistics.mean(covered),
        "extra": statistics.mean(extra),
        "whole": len(whole) / len(pairs),
        "named": statistics.mean([len(found) for found, _t in pairs]),
    }


def pairs_of(
    data: dict[str, dict[str, Any]], answers: dict[str, dict[str, Any]]
) -> list[tuple[dict[str, float], set[str]]]:
    """Each issue as Jev's spread over the cards, and the cards its fix touched."""
    out = []
    for rid, row in data.items():
        answer = answers.get(rid)
        truth = set(row["label"]["owners"])
        if answer is None or not truth:
            continue
        out.append((answer["answers"]["where"].get("probabilities", {}), truth))
    return out


def main() -> int:
    data = rows("issues")
    probable = pairs_of(data, results("issues"))
    print(f"{len(probable)} issues with the cards their fix touched, set {SET}")
    print(f"{'cut':>5} {'covered':>8} {'extra':>7} {'all of it':>10} {'cards named':>12}")
    passed = []
    for cut in CUTS:
        marked = [(projection(p, cut), truth) for p, truth in probable]
        score = scored(cut, marked)
        ok = score["cover"] >= COVER_AT_LEAST and score["extra"] <= EXTRA_AT_MOST
        passed.append((ok, score))
        print(
            f"{cut:5.2f} {score['cover']:8.2f} {score['extra']:7.2f} "
            f"{score['whole']:10.2f} {score['named']:12.2f}" + ("  PASSES" if ok else "")
        )
    print(
        f"\nthe bar: cover at least {COVER_AT_LEAST:.2f} of the cards the fix touched, "
        f"with at most {EXTRA_AT_MOST:.1f} extra cards per issue"
    )
    print("VERDICT:", "a plan can be projected" if any(ok for ok, _s in passed) else "it cannot")
    return 0


if __name__ == "__main__":
    sys.exit(main())
