"""Does the map's own graph predict where a change spreads, better than the imports?

`systemap ripple` would answer: you changed these cards, which others does
this reach? Before building it, the walk has to beat what systemap can
already do with imports alone.

**The ground truth.** The plan was to pair a pull request with the pull
request that fixed it within thirty days, and ask which cards the fix
touched. Measured first: over 2,406 merged pull requests across rich,
poetry, mealie, paperless-ngx and httpie, a rule strict enough to exclude
release rollups found 6 such pairs. Six is not a sample; a ten point
difference cannot be seen in it. So the truth used here is co-change: a
pull request that touches several cards is a change that spread, and the
question becomes, from the card where the change starts, which other cards
of that same pull request does the walk find?

    seed ...... the card claiming the file with the most changed lines
    truth ..... the other cards the same pull request touched
    ripple .... the cards `graph.walk` reaches from the seed over the flows
    closure ... the cards claiming every module the seed's modules import,
                transitively: what systemap could say with no map at all

**The bar, set before the run.** The walk must recall the touched cards
within 10 points of the import closure, at no more than half its size.
Below that, the map's edges add nothing to the imports and `ripple` would
be a prettier way to print the same thing.

    gh auth status                       # the pull requests come from GitHub
    uv run --project bench/jev python bench/jev/ripple.py

Pull requests are cached under `data/prs-<repo>.json`; delete one to refetch.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any

from common import DEV_REPOS, SCRATCH

from systemap import config, graph, nest
from systemap.evidence import owners

HERE = Path(__file__).parent
DATA = HERE / "data"
RESULTS = HERE / "results"
# The bar, stated before the run.
RECALL_WITHIN = 0.10
SIZE_AT_MOST = 0.50
# How far a ripple is followed. Past three hops a walk over a connected map
# reaches everything, which is not an answer a reader can act on.
MAX_DEPTH = 3
# How many pull requests to read per repository.
PRS = 500

SLUGS = {
    "rich": "Textualize/rich",
    "poetry": "python-poetry/poetry",
    "mealie": "mealie-recipes/mealie",
    "paperless": "paperless-ngx/paperless-ngx",
    "kstrl": "0xfauzi/kstrl",
}
HTTPIE = SCRATCH / "cli-first-map-20260919T193559Z/repo"


def repos() -> dict[str, Path]:
    found = dict(DEV_REPOS)
    if (HTTPIE / "docs/map/map.json").exists():
        found["httpie"] = HTTPIE
        SLUGS["httpie"] = "httpie/cli"
    return {k: v for k, v in found.items() if k in SLUGS}


def pulls(name: str, slug: str) -> list[dict[str, Any]]:
    """The merged pull requests of one repository, with the files each touched."""
    cached = DATA / f"prs-{name}.json"
    if cached.exists():
        return list(json.loads(cached.read_text()))
    out = subprocess.run(
        ["gh", "pr", "list", "-R", slug, "--state", "merged", "--limit", str(PRS),
         "--json", "number,title,mergedAt,files"],
        capture_output=True, text=True, timeout=1800,
    )  # fmt: skip
    out.check_returncode()
    found = json.loads(out.stdout)
    cached.write_text(json.dumps(found))
    return list(found)


def module_of_file(facts: dict[str, Any]) -> dict[str, str]:
    """Every file the facts know, as the module it holds."""
    return {rec["file"]: module for module, rec in facts["components"].items() if rec.get("file")}


def closure(facts: dict[str, Any], start: set[str]) -> set[str]:
    """Every module the starting modules import, followed as far as it goes."""
    seen = set(start)
    stack = list(start)
    while stack:
        used = facts["components"].get(stack.pop(), {}).get("uses", {})
        for module in used:
            if module in facts["components"] and module not in seen:
                seen.add(module)
                stack.append(module)
    return seen - start


def cards_of(modules: set[str], owner: dict[str, str]) -> set[str]:
    return {owner[m] for m in modules if m in owner}


def biggest(files: list[dict[str, Any]], known: dict[str, str]) -> str:
    """The module of the file the pull request changed most: where it starts."""
    ranked = sorted(
        (f for f in files if f["path"] in known),
        key=lambda f: -(f["additions"] + f["deletions"]),
    )
    return known[ranked[0]["path"]] if ranked else ""


def row(
    pr: dict[str, Any],
    facts: dict[str, Any],
    model: Any,
    owner: dict[str, str],
    meaning: Any = None,
) -> dict | None:
    """One pull request: where the change started, where it spread, what each rule found."""
    known = module_of_file(facts)
    touched = {known[f["path"]] for f in pr["files"] if f["path"] in known}
    start = biggest(pr["files"], known)
    if not start or len(touched) < 2:
        return None
    seed = owner.get(start)
    if seed is None:
        return None
    truth = cards_of(touched, owner) - {seed}
    if not truth:
        return None
    imported = cards_of(closure(facts, {start}), owner) - {seed}
    out: dict[str, Any] = {
        "pr": pr["number"],
        "seed": seed,
        "truth": sorted(truth),
        "cards": len(model.components),
    }
    for label, found in {**walks(model, seed, meaning), "imports": imported}.items():
        found = found - {seed}
        out[f"{label}_recall"] = len(found & truth) / len(truth)
        out[f"{label}_precision"] = len(found & truth) / len(found) if found else 0.0
        out[f"{label}_size"] = len(found)
    return out


def walks(model: Any, seed: str, meaning: Any = None) -> dict[str, set[str]]:
    """The ways a walk over the map can answer "what else does this reach"."""
    both = undirected(model)
    return {
        "forward1": set(graph.walk(model, [seed], max_depth=1).reached),
        "forward3": set(graph.walk(model, [seed], max_depth=MAX_DEPTH).reached),
        "near1": set(graph.walk(both, [seed], max_depth=1).reached),
        "near2": set(graph.walk(both, [seed], max_depth=2).reached),
        # what the map claims is special: a change to a card is felt by the
        # walks that pass through it
        "near1+j": set(graph.walk(both, [seed], max_depth=1).reached) | on_journeys(seed, meaning),
    }


def on_journeys(seed: str, meaning: Any = None) -> set[str]:
    """The cards a journey through the seed also passes through."""
    if meaning is None:
        return set()
    out: set[str] = set()
    for j in meaning.journeys:
        cards = {c for step in j.steps for c in (*step.acts, *step.measures, *step.edge)}
        if seed in cards:
            out |= cards
    return out - {seed}


def undirected(model: Any) -> Any:
    """The same map with every flow drawn both ways: a change reaches what it
    calls and what calls it, and the arrow on the map says only which way the
    artifact travels."""
    from dataclasses import replace

    back = [replace(f, src=f.dst, dst=f.src) for f in model.flows]
    return replace(model, flows=(*model.flows, *back))


def rows(name: str, root: Path) -> list[dict[str, Any]]:
    cfg = config.load(root)
    facts = json.loads(cfg.facts_path.read_text())
    top = nest.load(cfg).top
    owner = owners(top.model, facts)
    found = [row(pr, facts, top.model, owner, top.meaning) for pr in pulls(name, SLUGS[name])]
    return [{**r, "map": name} for r in found if r is not None]


RULES = ("forward1", "forward3", "near1", "near2", "near1+j", "imports")


def report(found: list[dict[str, Any]]) -> None:
    def med(rule: str, what: str) -> float:
        return statistics.median([r[f"{rule}_{what}"] for r in found]) if found else 0.0

    cards = statistics.median([r["cards"] for r in found]) if found else 0
    print(f"{len(found)} pull requests that touched two or more cards, over {len(repos())} maps")
    print(f"the map they are read on holds {cards:.0f} cards at the median\n")
    print(f"{'rule':10} {'recall':>7} {'precision':>10} {'cards named':>12} {'share of map':>13}")
    for rule in RULES:
        print(
            f"{rule:10} {med(rule, 'recall'):7.2f} {med(rule, 'precision'):10.2f} "
            f"{med(rule, 'size'):12.0f} {med(rule, 'size') / cards:13.2f}"
        )
    _per_map(found)
    _verdicts(found, med)


def _per_map(found: list[dict[str, Any]]) -> None:
    print(f"\n{'map':12} {'n':>4}  " + "  ".join(f"{r:>9}" for r in RULES))
    for name in sorted({r["map"] for r in found}):
        mine = [r for r in found if r["map"] == name]
        scores = [statistics.median([r[f"{rule}_recall"] for r in mine]) for rule in RULES]
        print(f"{name:12} {len(mine):4}  " + "  ".join(f"{x:9.2f}" for x in scores))


def _verdicts(found: list[dict[str, Any]], med: Any) -> None:
    print(
        f"\nthe bar: recall within {RECALL_WITHIN:.2f} of the imports, "
        f"at no more than {SIZE_AT_MOST:.2f} of their size"
    )
    for rule in RULES[:-1]:
        gap = med("imports", "recall") - med(rule, "recall")
        share = med(rule, "size") / med("imports", "size") if med("imports", "size") else 0.0
        verdict = "PASSES" if gap <= RECALL_WITHIN and share <= SIZE_AT_MOST else "fails"
        print(f"  {rule:10} behind by {gap:+.2f}, at {share:.2f} of their size: {verdict}")


def main() -> int:
    found = [r for name, root in repos().items() for r in rows(name, root)]
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "ripple.json").write_text(json.dumps(found, indent=1))
    report(found)
    return 0


if __name__ == "__main__":
    sys.exit(main())
