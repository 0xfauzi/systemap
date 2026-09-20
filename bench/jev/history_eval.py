"""Is a year of the system worth reading, and can it be read in five minutes?

`systemap history` would sample the repository back through time, read the
facts at each commit against today's map, and print what moved: cards that
grew or shrank, crossing imports that appeared, ways in added or removed.
Before building it, two things have to hold.

**The bar, set before the run.**

    time ....... 26 samples over a year of mealie: the first run is whatever
                 it is, and the second, with the cache warm, is at most five
                 minutes. A command nobody waits for is a command nobody runs.
    truth ...... of the five largest changes the trend names, at least three
                 match an event a person can find in the commits of that
                 window. A trend that names nothing real is a chart.

Run it after `bench/run.sh` has produced the first maps:

    uv run --project bench/jev python bench/jev/history_eval.py
    uv run --project bench/jev python bench/jev/history_eval.py --repo rich

The facts at each commit are cached under the repository's own
`.systemap/facts/`, which is what the warm run reads.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

from common import DEV_REPOS

from systemap import config, history, nest, trend

RESULTS = Path(__file__).parent / "results"
# The bar, stated before the run.
WARM_SECONDS = 300.0
TRENDS_REAL = 3
# A year, sampled every fortnight: 26 windows.
SINCE = "1 year ago"
EVERY_DAYS = 14
TOP = 5


def run(name: str, root: Path) -> dict[str, Any]:
    cfg = config.load(root)
    model = nest.load(cfg).top.model
    shas = history.sample(root, SINCE, EVERY_DAYS)
    cold = time.monotonic()
    rows = trend.walk(cfg, model, shas)
    cold = time.monotonic() - cold
    warm = time.monotonic()
    trend.walk(cfg, model, shas)
    warm = time.monotonic() - warm
    ranked = [trend.with_causes(root, w) for w in sorted(rows, key=lambda w: w.size, reverse=True)]
    return {
        "map": name,
        "samples": len(shas),
        "cold_seconds": round(cold, 1),
        "warm_seconds": round(warm, 1),
        "windows": rows,
        "top": ranked[:TOP],
        "commits": {w.head: _titles(root, w.base, w.head) for w in ranked[:TOP]},
    }


def _titles(root: Path, base: str, head: str) -> list[str]:
    """The commit subjects in one window, for judging whether a trend is real.

    A fortnight of a busy repository is mostly dependency bumps and
    translation updates, so the ones that change behaviour come first;
    otherwise the reader judges a real event by five renovate commits.
    """
    out = history.git(root, "log", "--format=%s", f"{base}..{head}")
    titles = [line for line in out.splitlines() if line]
    noise = ("chore(deps)", "fix(deps)", "chore(l10n)", "chore(deps-dev)")
    speaking = [t for t in titles if not t.startswith(noise)]
    return (speaking or titles)[:40]


def report(found: dict[str, Any]) -> None:
    print(
        f"{found['map']}: {found['samples']} samples over a year, "
        f"{found['cold_seconds']}s cold, {found['warm_seconds']}s warm "
        f"(bar: {WARM_SECONDS:.0f}s warm)"
    )
    sizes = [w.size for w in found["windows"]] or [0]
    print(f"  windows: {len(found['windows'])}, median change {statistics.median(sizes):.0f}")
    for window in found["top"]:
        print(f"  {window.base[:7]}..{window.head[:7]}: size {window.size}")
        for line in trend._window_lines(window)[1:]:
            print(f"  {line}")
        if not window.caused_by:
            for title in found["commits"][window.head][:3]:
                print(f"     in the window: {title[:100]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="mealie", choices=sorted(DEV_REPOS))
    args = ap.parse_args()
    found = run(args.repo, DEV_REPOS[args.repo])
    RESULTS.mkdir(parents=True, exist_ok=True)
    rows = [vars(w) for w in found["windows"]]
    (RESULTS / f"history-{args.repo}.json").write_text(
        json.dumps(
            {**found, "windows": rows, "top": [vars(w) for w in found["top"]]},
            indent=1,
            default=list,
        )
    )
    report(found)
    passed = found["warm_seconds"] <= WARM_SECONDS
    print(f"\ntime: {'PASSES' if passed else 'fails'} the warm bar")
    print(f"truth: read the commits above; at least {TRENDS_REAL} of {TOP} must name a real event")
    return 0


if __name__ == "__main__":
    sys.exit(main())
