#!/usr/bin/env python3
"""Render `bench/results.jsonl` into `docs/benchmarks.md`.

One row per repository per mode, the latest run of each; the model and
the systemap version named on every row, and the dollars per module for
a first map. The table is the measurement the README quotes; when nothing
has been measured it says so, and a test keeps the committed file equal
to what this script renders. Standard library only; `systemap` itself is
not involved.

    python3 bench/table.py [--results bench/results.jsonl] [--out docs/benchmarks.md] [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "bench" / "results.jsonl"
OUT = ROOT / "docs" / "benchmarks.md"
MODES = ("first-map", "maintenance", "first-map-jev")
COLUMNS = (
    "repository",
    "mode",
    "modules",
    "systemap",
    "model",
    "turns",
    "minutes",
    "dollars",
    "dollars per module",
    "check",
    "judgement",
    "run",
    "skill first",
    "date",
)

HEAD = """# Benchmarks

`bench/table.py` writes this document from `bench/results.jsonl`.
Do not edit the generated document. Change the generator instead.
Each repository and mode has one row for its latest run.

`bench/run.sh` executes the documented headless procedure.
The session's result event gives the model, turns, minutes, and dollars.
After the session, the harness executes `systemap check` and
`systemap judgement --strict`. Their results use the `check` and `judgement`
columns.

The `run` column shows whether the session completed without
intervention or stopped at its limit. The `skill first` column shows whether
the first tool call used the systemap skill. The procedure specifies this first
call.

The experiment recorded two acceptance limits before implementation:

- A first map must cost no more than 0.15 dollars per module.
- Maintenance on a medium pull request must use no more than 15 turns and
 2 dollars.

Four of the six first maps cost less than 0.15 dollars per module.
The other two cost 0.159 and 0.177.
The maintenance runs cost 2.31, 4.39, and 2.50 dollars.
They used 51, 63, and 46 turns.
All three exceeded both maintenance limits.

The 15-turn limit used an incorrect two-step assumption.
The maintenance procedure executes delta, refresh, check, and judgement.
The experiment did not change either limit after the results.

The maintenance runs used the reverse comparison direction.
Each run reverted a merged pull request but kept the map unchanged.
Thus, the map contained claims for removed code structure.
The report used the identifiers `entry vanished`, `interface vanished`, and
`evidence lost`.

The workflow from `init` uses the forward direction, from the pull-request base
to its head. That comparison can print `new crossing import`.
The test suite includes both directions.
The table's turns and dollars are from the reverse runs.

"""

EMPTY = "No run recorded yet: the table is empty until a repository is measured."

# The decision provider measurements are not rows of results.jsonl. They come from
# bench/jev/README.md, which gives the method, the acceptance values, and the commands.
DECISIONS = """
## Decision provider measurements

A decision provider answers the semantic questions of `systemap audit` and the other
decision commands. This section gives the current measurements of these questions.
`bench/jev/README.md` gives the method, the acceptance value, the commands, and the full output.

All rows come from Python repositories: 5 development maps and 3 holdout maps.
The development maps give each threshold. The holdout maps do not.
No TypeScript row set is available. Thus no result applies to TypeScript.

"Caught" is the fraction of incorrect claims below the threshold.
"Flagged" is the fraction of correct claims below the threshold.

### `decision flow` with Jev and the `call_sites` context (2026-10-13)

The question gets its source lines from the `call_sites` fact.
The rows are 160 development rows and 96 holdout rows. The model was `jev-1.13.0`.
The acceptance value: development caught 50% or more, a holdout catch rate
10 points or less from development, and 2 or fewer of 48 holdout claims flagged.

| context | threshold | dev caught | dev flagged | holdout caught | holdout flagged | result |
|---|---|---|---|---|---|---|
| `call_sites` fact | P < 0.2 | 48/80 (60.0%) | 2/80 (2.5%) | 25/48 (52.1%) | 1/48 (2.1%) | pass |

The AUC was 0.904 on development and 0.936 on holdout.
The cost was 256 requests and 279,288 input tokens.
`decision flow` is not a default question of `audit`, because no TypeScript row set is available.

### OpenAI Decisions (2026-10-13)

The model was `gpt-6-luna`. The rows are the Jev bench rows.
A kind is available only if each holdout figure is 10 points or less from its development figure.
The first measurement had 1,636 requests, with 0 errors and 0 refusals.
They used 1,211,893 input tokens and cost 0.121 dollars.

| kind | threshold | development | holdout | result |
|---|---|---|---|---|
| mis-fold | P < 0.02 | 82.1% caught, 3.1% flagged | 61.5% caught, 1.0% flagged | fail |
| owner | 0.99 or more | 9.5% answered, 100% correct | 4.7% answered, 100% correct | pass |
| sentence | P < 0.3 | 81.0% caught, 1.3% flagged | 75.0% caught, 0.0% flagged | pass |
| flow | P < 0.02 | 33.8% caught, 2.5% flagged | 37.5% caught, 6.2% flagged | pass |
| governs | 0.99 or more | 19.8% found, 1.1% suggested | 17.2% found, 6.0% suggested | pass |
| plan | cut 0.5 | 0.73 covered | 0.39 covered | fail |
| triage | none | 82.5% first | 69.2% first | fail |

The flow row comes from a second measurement with the `call_sites` context.
It used the 160 development rows and the 96 holdout rows of the Jev measurement above.
On development, OpenAI caught 27 of 80 incorrect claims and flagged 2 of 80 correct claims.
On holdout, it caught 18 of 48 and flagged 3 of 48.
The AUC was 0.881 on development and 0.862 on holdout.
The 256 requests had 0 errors and 0 refusals, and used 213,942 input tokens (0.021 dollars).

At P < 0.05, OpenAI flagged 4 of 80 correct development claims, more than the Jev budget of 2.
Thus the rule selected P < 0.02. At its threshold, Jev caught 48 of 80 on the same rows.

### Earlier measurements of the flow question

These figures are earlier measurements. The current figures above replace them.

The recorded figures of the first flow question used an earlier question and an earlier model.
That question caught 53 of 80 (66%) on development and flagged 2 of 80.
On holdout, it caught 26 of 48 (54%) and flagged 2 of 48.
The catch rate changed by more than 10 points. Thus the flow question became opt-in.

On 2026-10-13, four context selectors were measured with `jev-1.13.0` on the same rows:

| context | threshold | dev caught | dev flagged | holdout caught | holdout flagged | result |
|---|---|---|---|---|---|---|
| `base` (earlier) | P < 0.15 | 39/80 (48.8%) | 1/80 (1.2%) | 19/48 (39.6%) | 1/48 (2.1%) | fail |
| `around` | P < 0.15 | 34/80 (42.5%) | 1/80 (1.2%) | 14/48 (29.2%) | 1/48 (2.1%) | fail |
| `calls` | P < 0.2 | 48/80 (60.0%) | 2/80 (2.5%) | 26/48 (54.2%) | 0/48 (0.0%) | pass |
| `targets` | P < 0.2 | 47/80 (58.8%) | 2/80 (2.5%) | 28/48 (58.3%) | 0/48 (0.0%) | pass |

`calls` and `targets` used text patterns for Python and TypeScript syntax in shared code.
Thus they did not go into systemap. The `call_sites` fact gives the `targets` lines from each
language adapter.

The first OpenAI measurement used the `base` context. It selected P < 0.05 for the flow question.
At that threshold, OpenAI caught 37 of 80 (46.2%) on development and flagged 2 of 80 (2.5%).
On holdout, it caught 27 of 48 (56.2%) and flagged 4 of 48 (8.3%).
The second OpenAI measurement above replaces these figures.
"""


def rows(lines: Iterable[str]) -> list[dict[str, Any]]:
    """The latest run per repository and mode, in repository then mode order."""
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        key = (str(row.get("repository", "")), str(row.get("mode", "")))
        if key not in latest or str(row.get("date", "")) >= str(latest[key].get("date", "")):
            latest[key] = row
    order = {mode: k for k, mode in enumerate(MODES)}
    return [
        latest[key] for key in sorted(latest, key=lambda k: (k[0], order.get(k[1], len(order))))
    ]


def _cell(value: Any) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".") if value != int(value) else f"{int(value)}"
    return str(value).replace("|", "\\|")


def _per_module(row: dict[str, Any]) -> Any:
    dollars, modules = row.get("dollars"), row.get("modules")
    first = row.get("mode") in ("first-map", "first-map-jev")
    if not first or not isinstance(dollars, int | float) or not modules:
        return None
    return round(dollars / modules, 3)


def _line(row: dict[str, Any]) -> str:
    cells = [
        row.get("repository"),
        row.get("mode"),
        row.get("modules"),
        row.get("systemap"),
        row.get("model"),
        row.get("turns"),
        row.get("minutes"),
        row.get("dollars"),
        _per_module(row),
        row.get("check"),
        row.get("judgement"),
        row.get("run"),
        row.get("first_tool_ok"),
        str(row.get("date", ""))[:10],
    ]
    return "| " + " | ".join(_cell(c) for c in cells) + " |"


def render(table: list[dict[str, Any]]) -> str:
    if not table:
        return HEAD + "\n" + EMPTY + "\n"
    out = [HEAD, "| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    out += [_line(row) for row in table]
    return "\n".join(out) + "\n" + DECISIONS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="render the benchmark table")
    parser.add_argument("--results", default=str(RESULTS))
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument(
        "--check", action="store_true", help="exit 1 when the file differs from the render"
    )
    args = parser.parse_args(argv)
    results = Path(args.results)
    lines = results.read_text(encoding="utf-8").splitlines() if results.is_file() else []
    text = render(rows(lines))
    out = Path(args.out)
    if args.check:
        current = out.read_text(encoding="utf-8") if out.is_file() else ""
        if current != text:
            sys.stderr.write(f"{out} differs from the render; run: python3 bench/table.py\n")
            return 1
        sys.stdout.write(f"{out} is current\n")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    sys.stdout.write(f"wrote {out}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
