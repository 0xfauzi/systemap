"""Send bench rows to OpenAI Decisions, for `run.py --provider openai`.

Each row becomes one request with the body of `systemap.openai_provider.request_body`:
the state is the `input` text, a Jev `noul` question is a `predicate` question, and a
Jev `choice` question is a `choice` question with the criteria as `choices`.
The raw answers, the usage, the model, and the time go to results/openai/<exp>.jsonl.gz.
A failed request is written with its error and is sent again on the next run.
It is never replaced by a guess.
"""

from __future__ import annotations

import gzip
import json
import os
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from common import RESULTS

from systemap import openai_provider
from systemap.decision import ChoiceQuestion, DecisionError, PredicateQuestion, Question
from systemap.jev import Send


def questions_of(row: dict[str, Any]) -> list[Question]:
    """Make the provider questions of one bench row."""
    out: list[Question] = []
    for name, q in row["questions"].items():
        if q["type"] == "choice":
            out.append(
                ChoiceQuestion(row["id"], name, q["instructions"], row["state"], q["criteria"])
            )
        elif q["type"] == "noul":
            out.append(PredicateQuestion(row["id"], name, q["instructions"], row["state"]))
        else:
            raise SystemExit(f"{row['id']}: no OpenAI form for the question type {q['type']}")
    return out


def one(send: Send, row: dict[str, Any]) -> dict[str, Any]:
    t0 = time.perf_counter()
    body = openai_provider.request_body(openai_provider.MODEL, questions_of(row))
    try:
        resp = send("POST", openai_provider.PATH, body)
    except DecisionError as exc:
        return {"id": row["id"], "repo": row["repo"], "error": str(exc)}
    return {
        "id": row["id"],
        "repo": row["repo"],
        "answers": resp.get("answers"),
        "usage": resp.get("usage"),
        "model": resp.get("model"),
        "seconds": round(time.perf_counter() - t0, 3),
    }


def run_exp(
    exp: str,
    total: int,
    todo: list[dict[str, Any]],
    concurrency: int,
    summary: Callable[[str, list[dict[str, Any]]], None],
) -> None:
    if not todo:
        print(f"{exp}: all {total} answered by openai")
        return
    key = os.environ.get(openai_provider.KEY_ENV, "").strip()
    if not key:
        raise SystemExit(f"set {openai_provider.KEY_ENV}. No row was sent")
    send = openai_provider.with_retries(openai_provider.http_send(key))
    out_dir = RESULTS / "openai"
    out_dir.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    recs: list[dict[str, Any]] = []
    with gzip.open(out_dir / f"{exp}.jsonl.gz", "at") as out:

        def keep(row: dict[str, Any]) -> None:
            rec = one(send, row)
            with lock:
                out.write(json.dumps(rec) + "\n")
                out.flush()
                recs.append(rec)

        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
            list(pool.map(keep, todo))
    summary(exp, recs)
