#!/usr/bin/env python3
"""One summary line from a headless session's stream-json log.

`bench/run.sh` runs the documented recipe and streams the session to a
file, one JSON event per line. This script reads that file back and
writes the one line `bench/results.jsonl` keeps per run: the model the
session's init event names, and the turns, minutes and dollars the
result event reports. Nothing is estimated: a field the log does not
carry is null, and a session with no result event is recorded as cut
off. The recipe requires the session's first tool call to be the
systemap skill; `first_tool_ok` says whether it was.

Standard library only; `systemap` itself is not involved.

    python3 bench/summary.py LOG --repository R --mode first-map|maintenance
        [--systemap VERSION] [--ref SHA] [--base REF] [--modules N]
        [--check clean|failed] [--judgement clean|open] [--wall-seconds S]
        [--append bench/results.jsonl]

Prints the JSON line; `--append` also appends it to the file.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MODES = ("first-map", "maintenance")


def events(lines: Iterable[str]) -> list[dict[str, Any]]:
    """Every JSON object in the log, in order; a line that is not one is skipped."""
    out: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            out.append(event)
    return out


def tool_calls(evs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every tool call the assistant made: name and input, in order."""
    out: list[dict[str, Any]] = []
    for event in evs:
        if event.get("type") != "assistant":
            continue
        message = event.get("message") or {}
        for block in message.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                out.append({"name": block.get("name", ""), "input": block.get("input") or {}})
    return out


def _count(commands: Iterable[str], word: str) -> int:
    pattern = re.compile(rf"(?<![\w-])systemap {word}(?![\w-])")
    return sum(len(pattern.findall(command)) for command in commands)


def summarize(lines: Iterable[str]) -> dict[str, Any]:
    """What the log says about the session: model, turns, minutes, dollars, how it ended."""
    evs = events(lines)
    init = next((e for e in evs if e.get("type") == "system" and e.get("subtype") == "init"), {})
    result = next((e for e in evs if e.get("type") == "result"), None)
    calls = tool_calls(evs)
    first = calls[0] if calls else {"name": "", "input": {}}
    first_ok = first["name"] == "Skill" and first["input"].get("skill") == "systemap"
    bash = [str(c["input"].get("command", "")) for c in calls if c["name"] == "Bash"]
    model = str(init.get("model") or "")
    if not model and result is not None:
        usage = result.get("modelUsage") or {}
        model = ", ".join(sorted(usage)) if isinstance(usage, dict) else ""
    turns: int | None
    minutes: float | None
    dollars: float | None
    if result is None:
        turns = sum(1 for e in evs if e.get("type") == "assistant") or None
        minutes = None
        dollars = None
        run = "cut off (no result event)"
    else:
        turns = result.get("num_turns")
        duration = result.get("duration_ms")
        minutes = round(duration / 60000, 1) if isinstance(duration, int | float) else None
        cost = result.get("total_cost_usd")
        dollars = round(cost, 2) if isinstance(cost, int | float) else None
        subtype = str(result.get("subtype") or "")
        if subtype == "success" and not result.get("is_error"):
            run = "finished"
        else:
            why = subtype or str(result.get("stop_reason") or "error")
            run = f"cut off ({why})"
    return {
        "model": model,
        "turns": turns,
        "minutes": minutes,
        "dollars": dollars,
        "run": run,
        "tool_calls": len(calls),
        "check_calls": _count(bash, "check"),
        "refresh_calls": _count(bash, "refresh"),
        "first_tool": f"{first['name']} {json.dumps(first['input'], sort_keys=True)}".strip(),
        "first_tool_ok": first_ok,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="one summary line from a stream-json log")
    parser.add_argument("log", help="the stream-json file the session wrote")
    parser.add_argument("--repository", required=True, help="the repository, as the table names it")
    parser.add_argument("--mode", required=True, choices=MODES)
    parser.add_argument("--systemap", default="", help="the systemap version installed")
    parser.add_argument("--ref", default="", help="the commit the tree was at")
    parser.add_argument("--base", default="", help="maintenance: the base ref given")
    parser.add_argument("--modules", type=int, default=None, help="modules in the facts after")
    parser.add_argument("--check", default="", choices=["", "clean", "failed"])
    parser.add_argument("--judgement", default="", choices=["", "clean", "open"])
    parser.add_argument("--wall-seconds", dest="wall_seconds", type=int, default=None)
    parser.add_argument("--append", default="", help="also append the line to this file")
    args = parser.parse_args(argv)
    with open(args.log, encoding="utf-8") as handle:
        summary = summarize(handle)
    line = {
        "date": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "repository": args.repository,
        "mode": args.mode,
        "systemap": args.systemap,
        "ref": args.ref,
        "base": args.base,
        "modules": args.modules,
        **summary,
        "check": args.check,
        "judgement": args.judgement,
        "wall_seconds": args.wall_seconds,
    }
    text = json.dumps(line, sort_keys=True)
    if args.append:
        with open(Path(args.append), "a", encoding="utf-8") as handle:
            handle.write(text + "\n")
    sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
