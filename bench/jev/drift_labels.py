"""Test 7 (PR drift): items for a person to label, and the score once they have.

    uv run python drift_labels.py build    # kstrl PRs merged after its map -> data/drift_kstrl.jsonl
    uv run python run.py drift_kstrl
    uv run python drift_labels.py pick     # 60 items, half Jev doubts -> data/label-drift.json
    uv run python drift_labels.py score labels.json

The map is kstrl's first map, drawn at 0f5e0f1. Each PR merged after it is a
real change the map did not see: for every card whose modules the PR touched,
the question is whether the card's sentence still holds after the PR. Nobody
rewrote these sentences, so the labels come from a person reading the diff.
The systemap history rows from drift.jsonl join them, so the pick covers both.
"""

from __future__ import annotations

import json
import random
import sys

from build_meaning import DRIFT_QS, git, model_components, module_files
from common import DATA, SCRATCH, row, write

KSTRL = SCRATCH / "kstrl-first-map-20260826T114300Z/repo"
MAP_AT = "9e27946"  # the commit holding the benchmark's first map
DRAWN_AT = "0f5e0f1"  # the code that map describes
CAP = 12000


def pr_rows(merge: str, title: str, cards: dict) -> list[dict]:
    base, head = f"{merge}^1", merge
    files = git(KSTRL, "ls-tree", "-r", "--name-only", base).split()
    changed = set(git(KSTRL, "diff", "--name-only", base, head).split())
    rows = []
    for cid, c in cards.items():
        own = sorted({f for p in c["implemented_by"] for f in module_files(p, files)})
        touched = [f for f in own if f in changed]
        if not touched:
            continue
        diff = git(KSTRL, "diff", "-U3", base, head, "--", *touched)
        state = {
            "component": {"id": cid, "does": c["does"], "interface": c.get("interface", "")},
            "diff": diff[:CAP],
        }
        label = {
            "pr_title": title,
            "diff_chars": len(diff),
            "truncated": len(diff) > CAP,
            "files": touched,
        }
        rows.append(row("drift", "kstrl-pr", f"kstrl@{merge[:7]}:{cid}", state, DRIFT_QS, label))
    return rows


def build() -> None:
    cards = model_components(git(KSTRL, "show", f"{MAP_AT}:map/model.py"))
    merges = git(
        KSTRL, "log", "--first-parent", "--merges", "--format=%H\t%s", f"{DRAWN_AT}..origin/main"
    )
    rows = []
    for line in merges.splitlines():
        sha, title = line.split("\t", 1)
        rows += pr_rows(sha, title, cards)
    write("drift_kstrl", rows)


def pick(n: int = 60) -> None:
    """Half the items where Jev doubts the sentence most, half where it trusts it most."""
    from score import results, rows

    pool = []
    for exp in ("drift_kstrl", "drift"):
        data, res = rows(exp), results(exp)
        pool += [(res[i]["answers"]["does_holds"]["noul"], data[i]) for i in res]
    pool.sort(key=lambda x: x[0])
    r = random.Random(3)
    doubted = [x for x in pool if x[0] < 0.5]
    trusted = [x for x in pool if x[0] >= 0.5]
    chosen = r.sample(doubted, min(n // 2, len(doubted)))
    chosen += r.sample(trusted, n - len(chosen))
    r.shuffle(chosen)
    items = [
        {
            "id": d["id"],
            "set": "drift",
            "card": d["state"]["component"]["id"],
            "sentence": d["state"]["component"]["does"],
            "title": d["label"].get("pr_title", d["repo"]),
            "diff": d["state"]["diff"],
            "truncated": d["label"]["truncated"],
        }
        for _, d in chosen
    ]
    (DATA / "label-drift.json").write_text(json.dumps(items, indent=1))
    print(
        f"picked {len(items)}: {sum(p < 0.5 for p, _ in chosen)} doubted by Jev, the rest trusted"
    )


def score(path: str) -> None:
    """labels.json: {item id: "holds" | "stale" | "unsure"}. Unsure items are left out."""
    from score import auc, results, rows

    labels = json.loads(open(path).read())
    p = {}
    for exp in ("drift_kstrl", "drift"):
        p.update({i: r["answers"]["does_holds"]["noul"] for i, r in results(exp).items()})
    stale = [1 - p[i] for i, v in labels.items() if v == "stale" and i in p]
    holds = [1 - p[i] for i, v in labels.items() if v == "holds" and i in p]
    print(
        f"== test 7: {len(stale)} stale, {len(holds)} hold, {sum(v == 'unsure' for v in labels.values())} unsure"
    )
    print(f"   AUC {auc(stale, holds):.3f}  (pass: 0.85 or more)")
    for t in (0.3, 0.4, 0.5):
        caught = sum(x > 1 - t for x in stale) / max(len(stale), 1)
        alarms = sum(x > 1 - t for x in holds) / max(len(holds), 1)
        print(
            f"   flag P(holds)<{t}: catches {caught:.0%} of stale, alarms on {alarms:.0%} of cards that hold"
        )
    del rows


if __name__ == "__main__":
    {"build": build, "pick": pick, "score": lambda: score(sys.argv[2])}[sys.argv[1]]()
