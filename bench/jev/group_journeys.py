"""One walk for a crowd of ways in, instead of one walk each.

`systemap journeys` writes a walk per way in, three to a run. Finding the ways
a framework registers took paperless-ngx to 98 ways in and mealie to 195, so a
walk each is sixty-five runs for one repository, and nobody will do that.

`judgement` already says it the other way: once a card takes more than a few
ways in of one kind, it prints one line for the card. This asks whether the
generation can follow that grouping: one walk per (kind, card) crowd, written
to stand for all of them.

    group ...... every way in of one kind whose module one card claims
    walk ....... what the agent answers: steps over flows the map draws
    passes ..... the walk is a journey the map can hold, by the same rules
                 `systemap journeys` applies before writing one in

**The bar, set before the run.** Seven in ten attempts or more must come back
as a walk the map can hold. Below that, the grouping is not the problem and
generation is, and neither ships.

    uv run --project bench/jev python bench/jev/group_journeys.py
    uv run --project bench/jev python bench/jev/group_journeys.py --repo poetry

It calls a coding agent once per group, in the repository being read, and the
answers are cached under `results/group-journeys-cache.json`, so a second run
costs nothing. Facts are re-extracted in memory: the maps in bench/scratch were
drawn before systemap could see a route or a task, and their stored facts still
say a repository of routes has no way in at all.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from common import DEV_REPOS

from systemap import config, extract, journeys, nest
from systemap.agent import Agent
from systemap.jev import Cache
from systemap.model import Meaning, Model

RESULTS = Path(__file__).parent / "results"
# The bar, stated before the run.
PASSES_AT_LEAST = 0.70
# The agent that writes the walks, and how long one may take.
COMMAND = "claude -p"
TIMEOUT = 900.0
# The question is the shipped one, not a copy: a measurement of a wording
# nothing sends is a measurement of nothing.
QUESTION = journeys.GROUP_QUESTION


def attempt(
    agent: Agent, model: Model, meaning: Meaning, facts: Any, group: journeys.Group
) -> dict[str, Any]:
    """One group, asked and checked, through the code that ships.

    A refusal is a result, not an error: what is being measured is how often
    the answer is a walk the map can hold.
    """
    kind, card = group.one["kind"], group.card
    try:
        answer = agent.ask(QUESTION, journeys.context(model, meaning, facts, group))
    except Exception as exc:  # noqa: BLE001 - an agent that fails is an attempt that failed
        return {"kind": kind, "card": card, "problems": [str(exc)[:200]]}
    draft = journeys.read_answer(answer, model, group)
    return {
        "kind": kind,
        "card": card,
        "of": len(group.ways_in),
        "passed": bool(draft.journey) and not draft.problems,
        "steps": len(draft.journey.steps) if draft.journey else 0,
        "label": draft.journey.label if draft.journey else "",
        "problems": list(draft.problems),
    }


def run(name: str, root: Path) -> dict[str, Any]:
    cfg = config.load(root)
    facts = extract.build(cfg)
    top = nest.load(cfg).top
    # The crowds only: a way in on its own is the path `journeys` already had,
    # and the question here is whether a crowd can be walked once.
    found = [g for g in journeys.gather(top.model, top.meaning, facts) if g.whole]
    agent = Agent(
        command=COMMAND,
        root=root,
        cache=Cache(RESULTS / "group-journeys-cache.json"),
        timeout=TIMEOUT,
    )
    tries = []
    for group in found:
        one = attempt(agent, top.model, top.meaning, facts, group)
        print(f"  {one['card']:24} {one['kind']:10} {one.get('of', 0):4} ways in: ", end="")
        print("a walk the map can hold" if one.get("passed") else f"refused: {one['problems'][:1]}")
        tries.append(one)
    return {
        "map": name,
        "ways_in_open": sum(len(g.ways_in) for g in found),
        "groups": len(found),
        "tries": tries,
        "usage": agent.usage.line(),
    }


def report(found: list[dict[str, Any]]) -> bool:
    tries = [t for one in found for t in one["tries"]]
    passed = sum(1 for t in tries if t.get("passed"))
    print(f"\n{'repo':12} {'ways in in crowds':>18} {'crowds':>7} {'walks the map can hold':>24}")
    for one in found:
        held = sum(1 for t in one["tries"] if t.get("passed"))
        print(f"{one['map']:12} {one['ways_in_open']:18} {one['groups']:7} {held:24}")
    share = passed / len(tries) if tries else 0.0
    print(f"\nthe bar: {PASSES_AT_LEAST:.0%} of attempts come back as a walk the map can hold")
    print(
        f"measured: {passed} of {len(tries)} ({share:.0%}): "
        + ("passed" if share >= PASSES_AT_LEAST else "failed")
    )
    return share >= PASSES_AT_LEAST


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", action="append", default=[], choices=sorted(DEV_REPOS))
    args = ap.parse_args()
    names = args.repo or ["mealie", "paperless", "poetry"]
    RESULTS.mkdir(parents=True, exist_ok=True)
    found = []
    for name in names:
        print(f"{name}:")
        found.append(run(name, DEV_REPOS[name]))
    (RESULTS / "group-journeys.json").write_text(json.dumps(found, indent=1))
    for one in found:
        print(f"{one['map']}: {one['usage']}")
    return 0 if report(found) else 1


if __name__ == "__main__":
    sys.exit(main())
