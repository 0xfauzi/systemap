"""Compare current move inference with unique exact-content matching only.

Acceptance before execution: fewer disagreements with the saved Git rename
reference and no loss of correctly paired renames. A method that misses that
bar is not proposed as an automatic replacement. Git's -M50% labels are a
heuristic reference, not independent truth. This replay has 33 historical
commits selected for containing renames, so it does not estimate precision
on arbitrary deletion/addition commits. No agent or service runs.

Run: PYTHONPATH=src uv run --no-project --python 3.12 bench/jev/accuracy_moves.py
Python 3.12 is required to parse the Mealie snapshots in this reference set.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from typing import Any

from common import DATA, DEV_REPOS, RESULTS

from systemap import config, delta, moves


def conservative(b: dict, h: dict, gone: list[str], new: list[str]) -> dict[str, str]:
    old_counts = Counter(b[m]["sha"] for m in gone)
    new_counts = Counter(h[m]["sha"] for m in new)
    candidates = {h[m]["sha"]: m for m in new if new_counts[h[m]["sha"]] == 1}
    return {
        m: candidates[b[m]["sha"]]
        for m in gone
        if old_counts[b[m]["sha"]] == 1 and b[m]["sha"] in candidates
    }


def score(wanted: dict[str, str], predicted: dict[str, str]) -> dict[str, int]:
    correct = sum(wanted.get(old) == new for old, new in predicted.items())
    return dict(
        correct=correct,
        disagreements=len(predicted) - correct,
        missed=len(wanted) - correct,
        emitted=len(predicted),
    )


def main() -> None:
    truth = json.loads((DATA / "moves-truth.json").read_text())
    rows: list[dict[str, Any]] = []
    totals: dict[str, Counter] = {"current": Counter(), "exact_only": Counter()}
    for row in truth:
        cfg = config.load(DEV_REPOS[row["repo"]])
        b = delta.facts_at(cfg, row["sha"] + "^")["components"]
        h = delta.facts_at(cfg, row["sha"])["components"]
        gone, new = row["gone"], row["new"]
        current = {old: cand for old, (cand, _why) in moves.find(b, h, gone, new).items()}
        exact = conservative(b, h, gone, new)
        counts = {"current": score(row["want"], current), "exact_only": score(row["want"], exact)}
        for name, found in counts.items():
            totals[name].update(found)
        rows.append(
            dict(
                repo=row["repo"],
                sha=row["sha"],
                gone=len(gone),
                wanted=row["want"],
                predictions={"current": current, "exact_only": exact},
                counts=counts,
            )
        )
        print(f"{row['repo']}@{row['sha'][:8]} {counts}", flush=True)
    met = (
        totals["exact_only"]["disagreements"] < totals["current"]["disagreements"]
        and totals["exact_only"]["correct"] >= totals["current"]["correct"]
    )
    output = dict(interpreter=sys.version, totals=totals, acceptance_met=met, rows=rows)
    path = RESULTS / "no-jev-accuracy-moves.json"
    path.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(dict(totals=totals, acceptance_met=met)))


if __name__ == "__main__":
    main()
