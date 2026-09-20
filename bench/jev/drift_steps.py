"""What Jev says about the fifteen labelled steps, and what that would cost a reader.

`delta` would like to say "this is what changed for the people using it": for
each journey step through a card the change touched, whether the step's
sentence still describes what happens. This asks Jev exactly that question
about the fifteen cases in `data/label-drift-cases.json`, and compares its
answer with the label.

The labels say the sentence still holds in all fifteen. That makes this a
measurement of one thing only, and it is the thing that decides the feature:
how often Jev would raise an alarm where nothing is wrong. Recall cannot be
measured from a set with no positives in it, and this file does not pretend
otherwise.

    uv run --project bench/jev python bench/jev/drift_steps.py

Needs TYPESAFE_API_KEY. Answers are cached under `.systemap/jev-cache.json`
in this repository, so a second run sends nothing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from common import SYSTEMAP

from systemap import jev
from systemap.jev import Ask

DATA = Path(__file__).parent / "data"
RESULTS = Path(__file__).parent / "results"
CASES = DATA / "label-drift-cases.json"

# The question, in the words `delta` would use.
STILL_HOLDS = (
    "`step` is one step of a journey through this system: what a reader is "
    "told happens when a run passes from `from_card` to `to_card`. It was "
    "written when the map was drawn, at the commit before `diff`. After the "
    "change in `diff`, does that sentence still describe what happens?"
)
# Where a "no" would be printed. Above this, delta would tell a reader the
# step no longer holds; the threshold is what this run is here to judge.
CUTS = (0.5, 0.6, 0.7, 0.8, 0.9)


def ask_of(case: dict[str, Any]) -> Ask:
    state = {
        "system": case["repo"],
        "journey": case["journey"],
        "step": case["says"],
        "from_card": {"id": case["edge"][0], "is": case["cards"].get(case["edge"][0], "")},
        "to_card": {"id": case["edge"][1], "is": case["cards"].get(case["edge"][1], "")},
        "what_landed": case["commits"],
        "files_that_moved": case["stat"],
        "diff": case["diff"],
    }
    return Ask(
        case["id"],
        state,
        {"still_holds": {"type": "noul", "instructions": STILL_HOLDS}},
    )


def main() -> int:
    cases = json.loads(CASES.read_text())
    client = jev.from_env("jev-latest", SYSTEMAP / ".systemap/jev-cache.json")
    answers = client.ask([ask_of(c) for c in cases])
    rows = []
    for case in cases:
        p = float(answers[case["id"]]["still_holds"]["noul"])
        rows.append({"id": case["id"], "holds": p, "label": case["label"]["verdict"]})
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "drift-steps.json").write_text(json.dumps(rows, indent=1))

    print(f"{len(rows)} steps, every one labelled 'the sentence still holds'\n")
    print(f"{'step':34} {'Jev says it holds':>18}")
    for row in sorted(rows, key=lambda r: r["holds"]):
        print(f"{row['id']:34} {row['holds']:18.2f}")
    print("\nwhat delta would have told a reader:")
    for cut in CUTS:
        wrong = [r for r in rows if r["holds"] < cut]
        print(
            f"  below {cut:.1f}: {len(wrong)} of {len(rows)} steps reported as no longer holding, "
            f"and all {len(wrong)} would be wrong"
        )
    print(client.usage.line())
    return 0


if __name__ == "__main__":
    sys.exit(main())
