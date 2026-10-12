"""Measure the thresholds of a second decision provider (OpenAI) on the Jev rows.

    uv run --project bench/jev python bench/jev/provider_eval.py curve
    JEV_SET=holdout ... python bench/jev/provider_eval.py curve
    uv run --project bench/jev python bench/jev/provider_eval.py verdict

`curve` scores the recorded Jev answers and the recorded OpenAI answers of one set at
each candidate threshold. It writes `results/<set>/openai/curve.json`. `verdict` reads
the two curves, selects each OpenAI threshold on development, and compares holdout.
No command here sends a request. `run.py --provider openai` sends the rows.

The rows are the recorded rows of `data/` (development, five maps) and
`data/holdout/` (holdout). Each kind uses the rows that both providers answered.
A row with an OpenAI refusal is not in the figures of the two providers. The output
gives the count of these rows.

Acceptance value, written before the first OpenAI request of the bench rows:

- The threshold of each kind comes from the development set only.
- The budget of each kind is the Jev development figure at the shipped Jev threshold,
  on the same rows. The selection rule of each kind:
  - mis-fold (planted in a neighbour card): the largest value of BELOW where the
    fraction of correct modules flagged is at most the Jev budget at P<0.05.
  - sentence and flow: the largest value of BELOW where the fraction of true rows
    flagged is at most the Jev budget at P<0.2.
  - governs: the smallest value of AT where the fraction of false pairs suggested is
    at most the Jev budget at P>=0.8.
  - owner: the smallest value of AT where the fraction of correct answers, of the
    answers at or above the value, is at least the Jev budget at confidence >= 0.9.
  - plan: the largest value of `plan_eval.CUTS` that satisfies the plan bar on
    development (coverage at least 0.70, at most 2.0 extra components).
  - triage: no threshold. The figure is the top-1 rate.
- If no candidate satisfies the rule, or if the selected value flags, suggests, or
  answers no development row, the kind fails.
- At the selected value, each figure of the kind on holdout must be within 10 points of
  the same figure on development. The figures: mis-fold, sentence, and flow: caught and
  flagged. Governs: found and suggested. Owner: answered and right. Plan: covered.
  Triage: top-1.
- A kind that fails is not available for OpenAI: `decision.thresholds("openai")` gives
  no value for it.
- The same-pair kind (`suggest --jev`) and the move kind (`delta --jev`) have no holdout
  rows. Thus they cannot satisfy the value, and the experiment does not send their rows.

Each set operates one time: development, and then holdout.
"""

from __future__ import annotations

import gzip
import json
import math
import sys
from collections import Counter
from typing import Any

import plan_eval
import score
from common import HERE, RESULTS, SET

BELOW = (0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5)
AT = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0)
WITHIN = 0.10
# The shipped Jev value of each kind: the budget comes from Jev at this value.
JEV_AT = {
    "misfold": 0.05,
    "owner": 0.9,
    "sentence": 0.2,
    "flow": 0.2,
    "governs": 0.8,
    "plan": 0.05,
}
# The bench experiment of each kind, and the question name in its rows.
EXPERIMENT = {
    "misfold": "owner",
    "owner": "owner",
    "sentence": "sentence",
    "flow": "flowverify",
    "governs": "governs",
    "plan": "issues",
    "triage": "issues",
}
NOUL = {"sentence": ("describes", "describes"), "flow": ("holds", "holds")}


# ---- the recorded answers --------------------------------------------------------


def jev_shape(raw: dict[str, Any]) -> dict[str, Any]:
    """Give an OpenAI answer in the form of a Jev answer, for the score.py functions."""
    if raw["type"] == "predicate":
        return {"type": "noul", "noul": raw["probability"]}
    spread = {p["value"]: p["probability"] for p in raw.get("probabilities", [])}
    return {
        "type": "choice",
        "choice": raw["choice"],
        "probabilities": spread,
        "confidence": raw["confidence"],
    }


def openai_results(exp: str) -> tuple[dict[str, dict], int]:
    """Give the OpenAI answers in Jev form, and the count of rows with a refusal."""
    path = RESULTS / "openai" / f"{exp}.jsonl.gz"
    out: dict[str, dict] = {}
    refused = 0
    if not path.exists():
        return out, 0
    with gzip.open(path, "rt") as fh:
        for rec in map(json.loads, fh.read().splitlines()):
            if "error" in rec:
                continue
            if any(a.get("type") == "refusal" for a in rec["answers"]):
                refused += 1
                continue
            answers = {a["name"]: jev_shape(a) for a in rec["answers"]}
            out[rec["id"]] = {**rec, "answers": answers}
    return out, refused


def both(exp: str) -> tuple[dict, dict[str, dict], dict[str, dict], dict[str, int]]:
    """Give the rows, and the answers of each provider for the ids that both answered."""
    data = score.rows(exp)
    jev_all = score.results(exp)
    oa_all, refused = openai_results(exp)
    ids = [i for i in data if i in jev_all and i in oa_all]
    counts = {"rows": len(data), "jev": len(jev_all), "openai": len(oa_all), "refused": refused}
    jev_res = {i: jev_all[i] for i in ids}
    oa_res = {i: oa_all[i] for i in ids}
    return data, jev_res, oa_res, counts


# ---- the figures at each candidate value -----------------------------------------


def frac(n: int, d: int) -> dict[str, Any]:
    return {"n": n, "d": d, "value": n / d if d else math.nan}


def below_curve(pos: list[float], neg: list[float], grid: tuple[float, ...]) -> dict[str, Any]:
    """At each value: the false rows caught, and the true rows flagged (P below the value)."""
    return {
        str(t): {
            "caught": frac(sum(p < t for p in neg), len(neg)),
            "flagged": frac(sum(p < t for p in pos), len(pos)),
        }
        for t in grid
    }


def at_curve(pos: list[float], neg: list[float], grid: tuple[float, ...]) -> dict[str, Any]:
    """At each value: the true rows found, and the false rows suggested (P at or above it)."""
    return {
        str(t): {
            "found": frac(sum(p >= t for p in pos), len(pos)),
            "suggested": frac(sum(p >= t for p in neg), len(neg)),
        }
        for t in grid
    }


def misfold_curve(data: dict, res: dict) -> dict[str, Any]:
    _, near, _ = score.planted(data, res)
    return below_curve([x[3] for x in near], [x[4] for x in near], BELOW)


def owner_curve(data: dict, res: dict) -> dict[str, Any]:
    out = {}
    for t in AT:
        sel = [i for i in res if res[i]["answers"]["owner"]["confidence"] >= t]
        right = sum(res[i]["answers"]["owner"]["choice"] == data[i]["label"]["owner"] for i in sel)
        out[str(t)] = {"answered": frac(len(sel), len(res)), "right": frac(right, len(sel))}
    return out


def noul_curve(kind: str):
    q, label = NOUL[kind]

    def curve(data: dict, res: dict) -> dict[str, Any]:
        return below_curve(*score.pos_neg(data, res, q, label), BELOW)

    return curve


def governs_curve(data: dict, res: dict) -> dict[str, Any]:
    return at_curve(*score.pos_neg(data, res, "governs", "governs"), AT)


def plan_curve(data: dict, res: dict) -> dict[str, Any]:
    pairs = plan_eval.pairs_of(data, res)
    out = {}
    for cut in plan_eval.CUTS:
        s = plan_eval.scored(cut, [(plan_eval.projection(p, cut), t) for p, t in pairs])
        out[str(cut)] = {
            "covered": {"value": s["cover"], "n": len(pairs)},
            "extra": {"value": s["extra"], "n": len(pairs)},
        }
    return out


def triage_curve(data: dict, res: dict) -> dict[str, Any]:
    top1, _, _ = score.issue_hits(data, res)
    hits = [x for _, x in top1]
    return {"-": {"top-1": frac(sum(hits), len(hits))}}


CURVES = {
    "misfold": misfold_curve,
    "owner": owner_curve,
    "sentence": noul_curve("sentence"),
    "flow": noul_curve("flow"),
    "governs": governs_curve,
    "plan": plan_curve,
    "triage": triage_curve,
}


def usage(res: dict[str, dict]) -> dict[str, Any]:
    tokens = [r["usage"]["input_tokens"] for r in res.values() if r.get("usage")]
    models = Counter(r.get("model") for r in res.values())
    return {"requests": len(res), "input_tokens": sum(tokens), "models": dict(models)}


def curve() -> None:
    out: dict[str, Any] = {"set": SET, "kinds": {}, "usage": {}}
    for kind, fn in CURVES.items():
        exp = EXPERIMENT[kind]
        data, jev_res, oa_res, counts = both(exp)
        out["kinds"][kind] = {
            "counts": counts,
            "jev": fn(data, jev_res) if jev_res else {},
            "openai": fn(data, oa_res) if oa_res else {},
        }
        out["usage"][exp] = {"jev": usage(jev_res), "openai": usage(openai_results(exp)[0])}
    path = RESULTS / "openai" / "curve.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1) + "\n")
    print(f"{SET}: wrote {path.relative_to(HERE)}")


# ---- the selection on development and the holdout comparison ----------------------

FIGURES = {
    "misfold": ("caught", "flagged"),
    "owner": ("answered", "right"),
    "sentence": ("caught", "flagged"),
    "flow": ("caught", "flagged"),
    "governs": ("found", "suggested"),
    "plan": ("covered",),
    "triage": ("top-1",),
}


def _value(figures: dict[str, Any], name: str) -> float:
    return float(figures[name]["value"])


def _plan_pick(oa: dict[str, Any]) -> tuple[str | None, str]:
    passed = [
        c
        for c in plan_eval.CUTS
        if _value(oa[str(c)], "covered") >= plan_eval.COVER_AT_LEAST
        and _value(oa[str(c)], "extra") <= plan_eval.EXTRA_AT_MOST
    ]
    if not passed:
        return None, "no cut satisfies the bar"
    return str(max(passed)), "largest cut that satisfies the bar"


def _at_most(value: float, budget: float) -> bool:
    return value <= budget


def _at_least(value: float, budget: float) -> bool:
    return value >= budget


# The budget figure of each kind, the candidates, the test, and the pick (min or max).
BUDGET: dict[str, tuple[str, tuple[float, ...], Any, Any]] = {
    "misfold": ("flagged", BELOW, _at_most, max),
    "sentence": ("flagged", BELOW, _at_most, max),
    "flow": ("flagged", BELOW, _at_most, max),
    "governs": ("suggested", AT, _at_most, min),
    "owner": ("right", AT, _at_least, min),
}


def select(kind: str, dev: dict[str, Any]) -> tuple[str | None, str]:
    """Give the OpenAI value on development, and the rule result."""
    jev, oa = dev["jev"], dev["openai"]
    if not oa:
        return None, "no OpenAI answers"
    if kind == "triage":
        return "-", "no threshold"
    if kind == "plan":
        return _plan_pick(oa)
    name, grid, fits, pick_of = BUDGET[kind]
    budget = _value(jev[str(JEV_AT[kind])], name)
    ok = [t for t in grid if fits(_value(oa[str(t)], name), budget)]
    rule = f"Jev budget {name} {budget:.4f}"
    if not ok:
        return None, f"no candidate satisfies the {rule}"
    pick = pick_of(ok)
    first = FIGURES[kind][0]
    if oa[str(pick)][first]["n"] == 0:
        return None, f"{pick} gives no development row ({first} 0)"
    return str(pick), rule


def show(fig: dict[str, Any]) -> str:
    if "d" in fig:
        return f"{fig['n']}/{fig['d']} ({100 * fig['value']:.1f}%)" if fig["d"] else "-"
    return f"{fig['value']:.2f}"


def _jev_lines(kind: str, d: dict[str, Any], h: dict[str, Any]) -> None:
    value = str(JEV_AT.get(kind, "-"))
    for name in FIGURES[kind]:
        jd = d["jev"].get(value, {}).get(name)
        jh = h["jev"].get(value, {}).get(name)
        if jd and jh:
            print(f"   jev    {value:>5} {name:<10} dev {show(jd):<18} holdout {show(jh)}")


def _compare(pick: str, name: str, d: dict[str, Any], h: dict[str, Any]) -> bool:
    """Print one OpenAI figure on the two sets. Give True if it is within the limit."""
    fd, fh = d["openai"][pick][name], h["openai"].get(pick, {}).get(name)
    if fh is None:
        print(f"   openai {pick:>5} {name:<10} dev {show(fd):<18} holdout: no value")
        return False
    diff = 100 * (fh["value"] - fd["value"])
    ok = not math.isnan(diff) and abs(diff) <= 100 * WITHIN
    print(
        f"   openai {pick:>5} {name:<10} dev {show(fd):<18} holdout {show(fh):<18} "
        f"{diff:+.1f} points {'pass' if ok else 'fail'}"
    )
    return ok


def verdict() -> None:
    dev = json.loads((HERE / "results/openai/curve.json").read_text())
    hold = json.loads((HERE / "results/holdout/openai/curve.json").read_text())
    print("== OpenAI thresholds: selected on development, compared on holdout")
    for kind in CURVES:
        d, h = dev["kinds"][kind], hold["kinds"][kind]
        print(f"-- {kind}: development {d['counts']}, holdout {h['counts']}")
        _jev_lines(kind, d, h)
        pick, rule = select(kind, d)
        if pick is None:
            print(f"   openai: FAIL ({rule})")
            continue
        results = [_compare(pick, name, d, h) for name in FIGURES[kind]]
        print(f"   openai: {'PASS' if all(results) else 'FAIL'} ({rule})")
    for name, curves in (("development", dev), ("holdout", hold)):
        for exp, u in curves["usage"].items():
            print(f"   usage {name} {exp}: jev {u['jev']}; openai {u['openai']}")


def _cells(d: dict[str, Any], value: str) -> list[str]:
    out = []
    for who in ("jev", "openai"):
        figs = d[who].get(value, {})
        out.append(", ".join(f"{k} {show(v)}" for k, v in figs.items()))
    return out


def table() -> None:
    """Print each provider's figures at each candidate value, for the README."""
    for path in (HERE / "results/openai/curve.json", HERE / "results/holdout/openai/curve.json"):
        curves = json.loads(path.read_text())
        print(f"== {curves['set']}")
        for kind, d in curves["kinds"].items():
            for value in d["openai"] or d["jev"]:
                cells = _cells(d, value)
                print(f"   {kind:<8} {value:>5}  jev: {cells[0]:<44}  openai: {cells[1]}")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "curve":
        curve()
    elif command == "verdict":
        verdict()
    elif command == "table":
        table()
    else:
        raise SystemExit("give curve, verdict, or table")
