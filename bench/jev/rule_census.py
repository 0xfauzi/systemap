"""How many invariants of the benchmark maps give a rule proposal?

`systemap.rule_proposal` reads the text of each invariant for a rule pattern, for example
"Core must not import Store". This script counts the invariants of the five development
maps and the three holdout maps, and the invariants that give a proposal.

Acceptance value, written before the run: each proposal must be a rule that the text of
its invariant states, when a person examines it. One incorrect proposal fails the
patterns. The count of proposals is information only. No target count exists.

    uv run --project bench/jev python bench/jev/rule_census.py
"""

from __future__ import annotations

import sys

from common import DEV_REPOS, HOLDOUT_REPOS, _present

from systemap import config, nest, rule_proposal


def main() -> None:
    repos = _present({**DEV_REPOS, **HOLDOUT_REPOS})
    total = linked = 0
    found: list[str] = []
    other: list[str] = []
    for name, root in repos.items():
        tree = nest.load(config.load(root))
        for m in tree.maps:
            done = rule_proposal.linked(m.model)
            proposed = {p.invariant: p for p in rule_proposal.proposals(m.model)}
            for inv in m.model.invariants:
                total += 1
                linked += inv.n in done
                where = f"{name}{'/' + m.id if m.id else ''} {inv.n}"
                if inv.n in proposed:
                    found.append(f"{where}: {rule_proposal.line(proposed[inv.n])}")
                elif inv.n not in done:
                    other.append(f"{where}: {inv.text}")
    print(f"maps: {len(repos)} of {len(DEV_REPOS) + len(HOLDOUT_REPOS)}")
    print(f"invariants: {total}, with a linked rule: {linked}, with a proposal: {len(found)}")
    print(*found, sep="\n")
    print("examples without a proposal:")
    print(*other[:3], sep="\n")
    if len(repos) != len(DEV_REPOS) + len(HOLDOUT_REPOS):
        sys.exit(1)


if __name__ == "__main__":
    main()
