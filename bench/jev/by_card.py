"""Where a system grew over a year, and whether the growth names real work.

`history` reads a year as windows: what moved between two samples. The same
walk summed the other way answers a question a maintainer asks out loud, which
is not "what happened in March" but "which part of this system keeps growing".

    growth ..... how many modules a card gained over the year, summed over
                 every window, so a card that gained four and lost one counts
                 three
    cause ...... the commits that wrote the modules that card gained, which is
                 what turns a number into something a person can check

**The bar, set before the work.** On four repositories, the three
fastest-growing cards must each trace to at least one commit a person can name
as a piece of work, on at least three of the four. A number nobody can trace is
a chart.

    uv run --project bench/jev python bench/jev/by_card.py

It reads git and the facts at each sampled commit (cached under each
repository's `.systemap/facts/`) and sends nothing anywhere. The judgement is
made by reading the output: this file prints the evidence, it does not score it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from common import DEV_REPOS

from systemap import config, history, nest, trend

RESULTS = Path(__file__).parent / "results"
# The bar, stated before the run.
CARDS_JUDGED = 3
REPOS_THAT_MUST_PASS = 3
# A year, sampled every fortnight, as `history` samples it.
SINCE = "1 year ago"
EVERY_DAYS = 14
# How many commits are shown per card. More than this and the reader is not
# judging, they are reading a changelog.
COMMITS_SHOWN = 6


def growth(windows: list[trend.Window]) -> dict[str, int]:
    """How many modules each card gained over the whole year."""
    out: dict[str, int] = {}
    for window in windows:
        for card, moved in window.grew.items():
            out[card] = out.get(card, 0) + moved
    return out


def files_of(card: str, windows: list[trend.Window], owner: dict[str, str]) -> list[str]:
    """The files of the modules that card gained, in the order they appeared."""
    want = {module for module, cid in owner.items() if cid == card}
    out: list[str] = []
    for window in windows:
        for path in window.new_files:
            module = path.replace("/", ".").removesuffix(".py").removesuffix(".__init__")
            if any(module.endswith(w) or w.endswith(module) for w in want) and path not in out:
                out.append(path)
    return out


def causes(root: Path, files: list[str], base: str, head: str) -> list[str]:
    """The commits that added those files: the work that made the card grow.

    Every commit touching them is the wrong list over a year. A file added
    once is edited for months afterwards, so the newest commits are fixes to
    the thing rather than the thing, and `--diff-filter=A` asks for the commit
    that brought each file into the tree.
    """
    if not files:
        return []
    out = history.git(
        root,
        "log",
        "--diff-filter=A",
        "--format=%s",
        f"{base}..{head}",
        "--",
        *files[: trend.FILES_ASKED],
    )
    return [line for line in out.splitlines() if line][:COMMITS_SHOWN]


def run(name: str, root: Path) -> dict[str, Any]:
    cfg = config.load(root)
    model = nest.load(cfg).top.model
    shas = history.sample(root, SINCE, EVERY_DAYS)
    windows = trend.walk(cfg, model, shas)
    facts = json.loads(cfg.facts_path.read_text())
    from systemap.evidence import owners

    owner = owners(model, facts)
    grew = growth(windows)
    ranked = sorted(grew.items(), key=lambda kv: (-kv[1], kv[0]))
    cards = []
    for card, gained in ranked[:CARDS_JUDGED]:
        files = files_of(card, windows, owner)
        cards.append(
            {
                "card": card,
                "gained": gained,
                "files": files[:12],
                "commits": causes(root, files, shas[0], shas[-1]),
            }
        )
    return {
        "map": name,
        "samples": len(shas),
        "shrank": sorted(c for c, n in grew.items() if n < 0),
        "cards": cards,
    }


def report(found: dict[str, Any]) -> None:
    print(f"\n{found['map']}: {found['samples']} samples over a year")
    fell = ", ".join(found["shrank"]) or "no card lost a module"
    print(f"  shrank: {fell}")
    for card in found["cards"]:
        print(f"  {card['card']} +{card['gained']} modules")
        for path in card["files"][:4]:
            print(f"      {path}")
        for title in card["commits"]:
            print(f"      written by: {title[:96]}")
        if not card["commits"]:
            print("      written by: nothing git names, which fails the bar for this card")


def main() -> int:
    found = [run(name, root) for name, root in DEV_REPOS.items()]
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "by-card.json").write_text(json.dumps(found, indent=1))
    for one in found:
        report(one)
    print(
        f"\nthe bar: on at least {REPOS_THAT_MUST_PASS} repositories, each of the "
        f"{CARDS_JUDGED} fastest-growing cards traces to a commit a person can name "
        "as a piece of work. Read the commits above and decide."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
