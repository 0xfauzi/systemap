"""Where a first map's turns go, read from the session logs bench/run.sh keeps.

Each tool call the agent made is put in one class, by what it touched:

    orient ........ everything before the first write of map/model.py
    draft ......... that first write
    claims ........ a later edit of the model whose text names implemented_by
    model ......... any other later edit or write of the model
    answers ....... an edit of systemap.toml ([judgement] answered and the rest)
    loop .......... a systemap command after the draft (check, judgement, place, ...)
    read .......... anything else after the draft (reading files, facts, grep)

and the first check after the draft is read for how many modules the draft
left to no card (`unmapped:` lines). The question it answers: how much of a
first map is the agent assigning modules to cards, the work Jev could take.

    uv run python bench/jev/turns.py
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from common import SCRATCH

RUNS = sorted(d for d in SCRATCH.glob("*-first-map-2*") if (d / "summary.json").exists())


def _text(body: object) -> str:
    if isinstance(body, list):
        return "\n".join(x.get("text", "") for x in body if isinstance(x, dict))
    return str(body or "")


def _results(rows: list[dict]) -> dict[str, str]:
    """Each tool call's result text, by its id."""
    out: dict[str, str] = {}
    for r in rows:
        content = r.get("message", {}).get("content") if r.get("type") == "user" else None
        for c in content if isinstance(content, list) else []:
            if c.get("type") == "tool_result":
                out[c["tool_use_id"]] = _text(c.get("content"))
    return out


def calls(session: Path) -> list[tuple[dict, str, int]]:
    """(tool_use, its result text, output tokens charged to it), in order."""
    rows = [json.loads(line) for line in session.read_text().splitlines() if line.strip()]
    results = _results(rows)
    out = []
    for r in (r for r in rows if r.get("type") == "assistant"):
        uses = [c for c in r["message"]["content"] if c.get("type") == "tool_use"]
        tokens = (r["message"].get("usage") or {}).get("output_tokens", 0)
        out += [(u, results.get(u["id"], ""), tokens // max(1, len(uses))) for u in uses]
    return out


def touches(use: dict, name: str) -> bool:
    path = str(use["input"].get("file_path", ""))
    return path.endswith(name)


def classify(use: dict, drafted: bool) -> str:
    tool = use["name"]
    if tool in ("Write", "Edit") and touches(use, "map/model.py"):
        if not drafted:
            return "draft"
        text = json.dumps(use["input"])
        return "claims" if "implemented_by" in text else "model"
    if not drafted:
        return "orient"
    if tool in ("Write", "Edit") and touches(use, "systemap.toml"):
        return "answers"
    if tool == "Bash" and re.search(
        r"\bsystemap (check|judgement|place|refresh|describe|audit)",
        use["input"].get("command", ""),
    ):
        return "loop"
    return "read"


def one(run: Path) -> dict:
    counts: Counter[str] = Counter()
    tokens: Counter[str] = Counter()
    drafted = False
    unmapped_after_draft = None
    for use, result, tok in calls(run / "session.jsonl"):
        kind = classify(use, drafted)
        drafted = drafted or kind == "draft"
        counts[kind] += 1
        tokens[kind] += tok
        command = use["input"].get("command", "") if use["name"] == "Bash" else ""
        if drafted and unmapped_after_draft is None and "systemap check" in command:
            unmapped_after_draft = len(re.findall(r"unmapped: ", result))
    summary = json.loads((run / "summary.json").read_text())
    return {
        "run": run.name.split("-first-map")[0],
        "modules": summary.get("modules"),
        "turns": summary.get("turns"),
        "dollars": summary.get("dollars"),
        "counts": counts,
        "tokens": tokens,
        "unmapped_after_draft": unmapped_after_draft,
    }


KINDS = ("orient", "draft", "claims", "model", "answers", "loop", "read")


def main() -> None:
    rows = [one(r) for r in RUNS]
    head = (
        f"{'run':<14}{'mods':>5}{'turns':>6}{'$':>7}  "
        + "".join(f"{k:>8}" for k in KINDS)
        + "  unmapped@1st-check"
    )
    print("tool calls per class (share of all calls)")
    print(head)
    total: Counter[str] = Counter()
    for r in rows:
        n = sum(r["counts"].values())
        total.update(r["counts"])
        cells = "".join(f"{r['counts'][k]:>4}{r['counts'][k] / n:>4.0%}" for k in KINDS)
        print(
            f"{r['run']:<14}{r['modules']:>5}{r['turns']:>6}{r['dollars']:>7}  {cells}  {r['unmapped_after_draft']}"
        )
    n = sum(total.values())
    print(f"{'all':<32}  " + "".join(f"{total[k]:>4}{total[k] / n:>4.0%}" for k in KINDS))
    print("\noutput tokens per class, share")
    for r in rows:
        n = sum(r["tokens"].values()) or 1
        print(f"{r['run']:<14}" + "".join(f"{k}={r['tokens'][k] / n:.0%} " for k in KINDS))


if __name__ == "__main__":
    main()
