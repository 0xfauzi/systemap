"""Measure the OpenAI flow threshold with the flow context from the call-site fact.

    uv run --project bench/jev python bench/jev/call_site_context.py build
    SYSTEMAP_TRUST_MODEL_CODE=1 JEV_SET=holdout JEV_ROOT_SCORECARD=../scorecard \
        uv run --project bench/jev python bench/jev/call_site_context.py build
    OPENAI_API_KEY=... uv run --project bench/jev python bench/jev/run.py \
        --provider openai flowctx_facts
    OPENAI_API_KEY=... JEV_SET=holdout uv run --project bench/jev python bench/jev/run.py \
        --provider openai flowctx_facts
    uv run --project bench/jev python bench/jev/openai_flow_context.py score

The `decision.OPENAI` flow value (0.05) came from `provider_eval.py` with the earlier
flow context: the lines that use an imported name. `audit_code.code_between` now
selects the context from the `call_sites` fact. Thus the earlier value does not apply.

The rows are the rows of `call_site_context.py`: data/<set>/flowctx_facts.jsonl, with
the same ids, claims, labels, question, and `code` text that Jev answered. The recorded
Jev answers are results/<set>/flowctx_facts.jsonl.gz. The OpenAI answers go to
results/<set>/openai/flowctx_facts.jsonl.gz. No command here sends a request.

Each figure uses only the rows that the two providers answered. A row with an OpenAI
refusal is not in the figures of the two providers. The output gives the count.
A row with an empty context is not sent, as in `call_site_context.py`. It counts as
not caught and not flagged for the two providers.

Acceptance value, written before the first OpenAI request of these rows. It is the
rule of the flow kind in `provider_eval.py`, and this script uses its functions:

- The threshold comes from the development set only.
- The budget is the fraction of correct development claims that Jev flags at the
  shipped Jev threshold, P<0.2, on the same rows.
- The threshold is the largest value of `provider_eval.BELOW` where OpenAI flags a
  fraction of the correct development claims that is at most the budget.
- If no value satisfies this rule, or if the selected value catches no incorrect
  development claim, the flow kind fails.
- At the selected value, the holdout catch rate must be within 10 points of the
  development catch rate. The holdout flag rate must be within 10 points of the
  development flag rate.
- If the kind passes, `decision.OPENAI.flow_below` gets the selected value. If it fails,
  `decision.OPENAI.flow_below` stays None, and OpenAI does not answer the flow question.

The rows go to OpenAI one time on development, and then one time on holdout.
All the repositories in the two sets are Python repositories. Thus the result does not
show the behavior on TypeScript.
"""

from __future__ import annotations

import gzip
import json
import statistics
import sys
from pathlib import Path
from typing import Any

import provider_eval
from common import HERE

EXP = "flowctx_facts"
NOT_ASKED = 1.0  # an empty context gives no question, thus no flag and no catch


def _answers(path: Path) -> tuple[dict[str, dict[str, Any]], int, int]:
    """Give the answered records by id, the count of errors, and the count of refusals."""
    if not path.exists():
        return {}, 0, 0
    with gzip.open(path, "rt") as fh:
        recs = [json.loads(x) for x in fh.read().splitlines()]
    ok = {r["id"]: r for r in recs if "error" not in r}
    errors = len({r["id"] for r in recs if "error" in r} - set(ok))
    # Jev answers are a dict by name. OpenAI answers are a list, and only these can refuse.
    refused = {
        i
        for i, r in ok.items()
        if isinstance(r["answers"], list) and any(a["type"] == "refusal" for a in r["answers"])
    }
    return {i: r for i, r in ok.items() if i not in refused}, errors, len(refused)


def _p(rec: dict[str, Any], provider: str) -> float:
    if provider == "jev":
        return float(rec["answers"]["holds"]["noul"])
    return float(next(a for a in rec["answers"] if a["name"] == "holds")["probability"])


def load(sub: str) -> dict[str, Any]:
    """Give the curves of the two providers on one set, the counts, and the usage."""
    data = HERE / "data" / sub
    rows = {r["id"]: r for r in map(json.loads, (data / f"{EXP}.jsonl").read_text().splitlines())}
    jev, jev_errors, _ = _answers(HERE / "results" / sub / f"{EXP}.jsonl.gz")
    oa, oa_errors, refused = _answers(HERE / "results" / sub / "openai" / f"{EXP}.jsonl.gz")
    ids = [i for i in rows if i in jev and i in oa]
    out: dict[str, Any] = {
        "counts": {
            "rows": len(rows),
            "jev": len(jev),
            "openai": len(oa),
            "both": len(ids),
            "jev errors": jev_errors,
            "openai errors": oa_errors,
            "refused": refused,
        }
    }
    empty = json.loads((data / f"{EXP}_empty.json").read_text())
    out["counts"]["empty"] = len(empty)
    for provider, recs in (("jev", jev), ("openai", oa)):
        pos = [_p(recs[i], provider) for i in ids if rows[i]["label"]["holds"]]
        neg = [_p(recs[i], provider) for i in ids if not rows[i]["label"]["holds"]]
        for r in empty:
            (pos if r["label"]["holds"] else neg).append(NOT_ASKED)
        out[provider] = provider_eval.below_curve(pos, neg, provider_eval.BELOW)
        out[f"{provider} auc"] = auc(pos, neg)
    out["usage"] = usage([oa[i] for i in ids])
    return out


def auc(pos: list[float], neg: list[float]) -> float:
    if not pos or not neg:
        return float("nan")
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def usage(recs: list[dict[str, Any]]) -> str:
    ins = [r["usage"]["input_tokens"] for r in recs if r.get("usage")]
    outs = [r["usage"].get("output_tokens", 0) for r in recs if r.get("usage")]
    secs = [r["seconds"] for r in recs if "seconds" in r]
    models = sorted({str(r.get("model")) for r in recs})
    if not ins:
        return "no usage"
    return (
        f"{len(recs)} requests, {sum(ins)} input tokens, {sum(outs)} output tokens, "
        f"median input {statistics.median(ins):.0f}, median {statistics.median(secs):.2f} s, "
        f"models {models}"
    )


def score() -> None:
    dev, hold = load(""), load("holdout")
    print("== OpenAI flow threshold, context from the call-site fact")
    for name, d in (("development", dev), ("holdout", hold)):
        print(f"   {name}: {d['counts']}")
        print(f"   {name}: AUC jev {d['jev auc']:.3f}, openai {d['openai auc']:.3f}")
        print(f"   {name}: openai usage {d['usage']}")
    for t in provider_eval.BELOW:
        cells = [
            f"{who} {name} caught {provider_eval.show(s[who][str(t)]['caught'])}, "
            f"flagged {provider_eval.show(s[who][str(t)]['flagged'])}"
            for who in ("jev", "openai")
            for name, s in (("dev", dev), ("holdout", hold))
        ]
        print(f"   P<{t:<4}  " + "; ".join(cells))
    provider_eval._jev_lines("flow", dev, hold)
    pick, rule = provider_eval.select("flow", dev)
    if pick is None:
        print(f"   openai: FAIL ({rule})")
        return
    results = [provider_eval._compare(pick, name, dev, hold) for name in ("caught", "flagged")]
    print(f"   openai: {'PASS' if all(results) else 'FAIL'} at P<{pick} ({rule})")


if __name__ == "__main__":
    if sys.argv[1:2] == ["score"]:
        score()
    else:
        raise SystemExit("usage: openai_flow_context.py score")
