"""Test a package-evidence addition to the Jev-free mis-fold question.

Acceptance bar, set before running: on both development and holdout owner
samples, catch at least 50% of modules planted in a neighbouring wrong card,
while flagging no more than 3% of the unchanged module owners. The existing
rule catches 38% and flags 1% on holdout. A gain smaller than twelve points
does not justify another rule a maintainer has to understand.

The finished maps supply labels, not independent proof of semantic ownership.
The planted cases test whether a rule can notice a known wrong assignment.
"""

from __future__ import annotations

import json
import random
from collections import Counter

from common import DATA, load
from score import misfold_fires, neighbour

from systemap.judgement import package_of


def package_evidence(repo, module: str, current: str) -> bool:
    """Another card claims at least two peers in this module's package."""
    peers = Counter(
        owner
        for other, owner in repo.owner.items()
        if other != module and package_of(other) == package_of(module)
    )
    return peers[current] == 0 and any(
        count >= 2 for card, count in peers.items() if card != current
    )


def score() -> None:
    rows = [json.loads(line) for line in (DATA / "owner.jsonl").read_text().splitlines()]
    old = [0, 0]
    new = [0, 0]
    total = [0, 0]
    rng = random.Random(7)
    for row in rows:
        repo = load(row["repo"])
        module = row["id"]
        correct = row["label"]["owner"]
        wrong = neighbour(repo, correct, rng)
        if wrong is None:
            continue
        for slot, card in enumerate((wrong, correct)):
            total[slot] += 1
            previous = misfold_fires(repo, module, card)
            old[slot] += previous
            new[slot] += previous or package_evidence(repo, module, card)
    print(f"n={total[0]} planted neighbour, n={total[1]} unchanged")
    print(f"current: {old[0]}/{total[0]} caught; {old[1]}/{total[1]} false alarms")
    print(f"combined: {new[0]}/{total[0]} caught; {new[1]}/{total[1]} false alarms")


if __name__ == "__main__":
    score()
