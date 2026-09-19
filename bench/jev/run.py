"""Send every dataset row to Jev once; cache the raw answers with usage and latency.

    uv run python run.py [exp ...] [--limit N]

A row already in results/<exp>.jsonl.gz is skipped, so a rerun resumes. A
failed call is written with its error and retried on the next run; it is
never replaced by a guess.
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import time
from pathlib import Path

from typesafe_sdk import AsyncTypeSafeClient, TypeSafeAPIError

HERE = Path(__file__).parent
DATA, RESULTS = HERE / "data", HERE / "results"
RESULTS.mkdir(exist_ok=True)


def done(exp: str) -> set[str]:
    path = RESULTS / f"{exp}.jsonl.gz"
    if not path.exists():
        return set()
    with gzip.open(path, "rt") as fh:
        return {r["id"] for r in map(json.loads, fh.read().splitlines()) if "error" not in r}


async def one(client, sem, row, out):
    async with sem:
        t0 = time.perf_counter()
        try:
            resp = await client.system_one(row["state"], row["questions"])
            rec = {
                "id": row["id"],
                "repo": row["repo"],
                "answers": resp.model_dump(mode="json")["answers"],
                "usage": resp.model_dump(mode="json").get("usage"),
                "seconds": round(time.perf_counter() - t0, 3),
            }
        except TypeSafeAPIError as e:
            rec = {
                "id": row["id"],
                "repo": row["repo"],
                "error": f"{e.status} {e}",
                "request_id": e.request_id,
            }
        except Exception as e:  # noqa: BLE001 - surfaced, never swallowed
            rec = {"id": row["id"], "repo": row["repo"], "error": repr(e)}
        out.write(json.dumps(rec) + "\n")
        out.flush()
        return rec


def todo_rows(exp: str, limit: int) -> tuple[int, list[dict]]:
    """How many rows the experiment has, and the ones not answered yet."""
    rows = [json.loads(line) for line in (DATA / f"{exp}.jsonl").read_text().splitlines()]
    have = done(exp)
    todo = [r for r in rows if r["id"] not in have]
    return len(rows), todo[:limit] if limit else todo


def summary(exp: str, recs: list[dict]) -> None:
    errors = [r for r in recs if "error" in r]
    secs = sorted(r["seconds"] for r in recs if "seconds" in r)
    p50 = secs[len(secs) // 2] if secs else None
    print(f"{exp}: {len(recs) - len(errors)} ok, {len(errors)} errors, p50 {p50}s")
    for e in errors[:3]:
        print("  ", e["id"], e["error"][:300])


async def run_exp(client, sem, exp: str, limit: int) -> None:
    total, todo = todo_rows(exp, limit)
    if not todo:
        print(f"{exp}: all {total} cached")
        return
    with gzip.open(RESULTS / f"{exp}.jsonl.gz", "at") as out:
        recs = await asyncio.gather(*(one(client, sem, r, out) for r in todo))
    summary(exp, recs)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("exps", nargs="*")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--concurrency", type=int, default=8)
    a = ap.parse_args()
    exps = a.exps or [p.stem for p in sorted(DATA.glob("*.jsonl"))]
    async with AsyncTypeSafeClient() as client:
        sem = asyncio.Semaphore(a.concurrency)
        for exp in exps:
            await run_exp(client, sem, exp, a.limit)


if __name__ == "__main__":
    asyncio.run(main())
