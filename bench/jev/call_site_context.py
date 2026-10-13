"""Measure the `jev flow` context that `audit_code.code_between` selects from the call-site fact.

    uv run --project bench/jev python bench/jev/call_site_context.py build
    uv run --project bench/jev python bench/jev/run.py flowctx_facts
    SYSTEMAP_TRUST_MODEL_CODE=1 JEV_SET=holdout JEV_ROOT_SCORECARD=../scorecard \
        uv run --project bench/jev python bench/jev/call_site_context.py build
    JEV_SET=holdout uv run --project bench/jev python bench/jev/run.py flowctx_facts
    uv run --project bench/jev python bench/jev/call_site_context.py score

The rows are the recorded rows of data/<set>/flowverify.jsonl: the same ids, claims,
and labels as `flow_context.py`. Each row sends the shipped question (`audit.VERIFY_Q`)
and the shipped `ends` (`audit.card_brief`). Only the `code` text is new.

The arm `facts`: the `code` text is the result of `audit_code.code_between` in this
work. That function reads only the `call_sites` fact and the source lines that the fact
names. The cached facts have format 2 and do not have the fact. Thus `build` writes
the fact with the Python adapter (`PythonLanguage.call_sites`) from the source of the
cached facts. `build` stops if a source file is not the file that the cached facts
describe, or if the fact of a flow module is not known.

If the context of a row is empty, the shipped audit asks no question for the flow.
Such a row is not sent. The score counts it as not caught and not flagged, because
the shipped audit gives no finding for it. `build` gives the count of these rows.

Acceptance value, written before the first Jev call. It is the value that `calls` and
`targets` satisfied in `flow_context.py`:

- The threshold comes from the development set only. It is the largest value in GRID
  where at most 2.5% of the true development rows (2 of 80) get a flag. If no value
  satisfies this limit, the arm fails.
- At that threshold, the development catch rate must be 50% or more.
- At that threshold, the holdout catch rate must be within 10 points of the
  development catch rate.
- At that threshold, at most 4.2% of the true holdout rows (2 of 48) can get a flag.
- If the arm satisfies these conditions, `audit_code.code_between` uses the fact. If it
  does not, `audit_code.py` does not change.

All the repositories in the two sets are Python repositories. Thus the result does not
show the behavior on TypeScript.

The arm operates one time on development and then one time on holdout.
The selector does not change after the holdout run.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import math
import os
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any

from common import DEV_REPOS, HERE, HOLDOUT_REPOS, SCRATCH, SET, SYSTEMAP, Repo

from systemap import audit, config, nest
from systemap.audit_code import code_between
from systemap.extract import PYTHON
from systemap.language import repository
from systemap.model import claimed
from systemap.source_facts import is_empty_marker

ARM = "facts"
GRID = (0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5)
DEV_FLAG_LIMIT = 0.025
HOLDOUT_FLAG_LIMIT = 0.042
DEV_CATCH_FLOOR = 0.5
WITHIN = 0.10
NOT_ASKED = 1.0  # an empty context gives no question, thus no flag and no catch


# ---- the source of the cached facts (as in flow_context.py) ----------------------


def snapshot(commit: str) -> Path:
    out = SCRATCH / f"systemap-{commit[:7]}"
    if not out.exists():
        out.mkdir(parents=True)
        tar = subprocess.run(
            ["git", "-C", str(SYSTEMAP), "archive", commit], check=True, capture_output=True
        ).stdout
        subprocess.run(["tar", "-x", "-C", str(out)], input=tar, check=True)
    return out


def root_of(name: str, facts: dict[str, Any]) -> Path:
    override = os.environ.get(f"JEV_ROOT_{name.upper()}")
    if override:
        return Path(override)
    if SET == "dev":
        return DEV_REPOS[name]
    if name == "systemap":
        return snapshot(facts["built_at_commit"])
    root = HOLDOUT_REPOS[name]
    if root is None:
        raise SystemExit(f"{name}: no source root. Set JEV_ROOT_{name.upper()}.")
    return root


def facts_dir() -> Path:
    return HERE / "data" / ("" if SET == "dev" else "holdout")


def load_repo(name: str) -> tuple[Repo, Any]:
    facts = json.loads((facts_dir() / f"facts-{name}.json").read_text())
    root = root_of(name, facts)
    top = nest.load(config.load(root)).top
    mods = [m for m, r in facts["components"].items() if not is_empty_marker(r)]
    owner: dict[str, str] = {}
    for c in top.model.components:
        for m in claimed(c, mods):
            owner.setdefault(m, c.id)
    return Repo(name, root, config.load(root), top.model, top.meaning, facts, owner), top


def stale(repo: Repo, modules: list[str]) -> list[str]:
    out = []
    for m in modules:
        rec = repo.records[m]
        try:
            raw = (repo.root / rec["file"]).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            out.append(f"{m}: not readable")
            continue
        sha = hashlib.sha1(raw.encode("utf-8"), usedforsecurity=False).hexdigest()[:12]
        if sha != rec.get("sha"):
            out.append(f"{m}: sha {sha}, facts {rec.get('sha')}")
    return out


# ---- the call-site fact, from the Python adapter ----------------------------------


def with_call_sites(repo: Repo) -> dict[str, Any]:
    """The cached facts with the `call_sites` fact that extraction writes."""
    facts = copy.deepcopy(repo.facts)
    components = facts["components"]
    known, prefixes = set(components), set(facts["packages"])
    for module, record in components.items():
        # Format 2 wrote the first name part as `package`. Format 6 and later write the
        # folder package: the parent package, or the name of a package root.
        record["package"] = module if module in prefixes else module.rsplit(".", 1)[0]
        path = repo.root / record["file"]
        try:
            raw = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            record["call_sites"] = None
            continue
        sites = PYTHON.call_sites(
            raw, module, prefixes, known, components, PYTHON.is_package_module(path)
        )
        uses = record.get("uses", {})
        record["call_sites"] = None if sites is None else [s for s in sites if s["target"] in uses]
    return facts


# ---- build ------------------------------------------------------------------------


def edge_of(row: dict[str, Any]) -> tuple[str, str]:
    src, dst = row["id"].rsplit(":", 1)[0].split("->", 1)
    return src, dst


def build() -> None:
    old = [json.loads(x) for x in (facts_dir() / "flowverify.jsonl").read_text().splitlines()]
    sent: list[dict[str, Any]] = []
    empty: list[dict[str, Any]] = []
    for name in sorted({r["repo"] for r in old}):
        repo, top = load_repo(name)
        build_repo(repo, top, [r for r in old if r["repo"] == name], sent, empty)
    path = facts_dir() / f"flowctx_{ARM}.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in sent))
    (facts_dir() / f"flowctx_{ARM}_empty.json").write_text(
        json.dumps([{"id": r["id"], "label": r["label"]} for r in empty])
    )
    sizes = [sum(len(x) for x in r["state"]["code"]) for r in sent]
    lines = [len(r["state"]["code"]) for r in sent]
    print(
        f"{ARM}: {len(sent)} rows sent, {len(empty)} rows with an empty context; median code "
        f"{statistics.median(sizes):.0f} chars, max {max(sizes)}, median lines "
        f"{statistics.median(lines):.0f} -> {path.name}"
    )


def build_repo(repo: Repo, top: Any, rows: list[dict], sent: list[dict], empty: list[dict]) -> None:
    facts = with_call_sites(repo)
    by = audit.modules_by_card(top.model, facts)
    owner = {m: c for c, ms in by.items() for m in ms}
    if owner != repo.owner:
        diff = sorted(set(owner.items()) ^ set(repo.owner.items()))[:5]
        raise SystemExit(f"{repo.name}: the module claims are not the measured claims: {diff}")
    ends = {c for r in rows for c in edge_of(r)}
    bad = stale(repo, sorted({m for c in ends for m in by.get(c, [])}))
    if bad:
        raise SystemExit(
            f"{repo.name}: the source is not the source of the facts:\n" + "\n".join(bad)
        )
    question = {"holds": {"type": "noul", "instructions": audit.VERIFY_Q}}
    python = repository("python")
    n_empty = 0
    for r in rows:
        src, dst = edge_of(r)
        code = code_between(repo.root, facts, by, (src, dst), python)
        if code is None:
            raise SystemExit(f"{repo.name} {r['id']}: the call-site fact is not known")
        if not code:
            empty.append(r)
            n_empty += 1
            continue
        brief = {x: audit.card_brief(top.model, top.meaning, x) for x in (src, dst)}
        state = {"claim": r["state"]["claim"], "ends": brief, "code": code}
        sent.append({**r, "exp": f"flowctx_{ARM}", "state": state, "questions": question})
    print(f"{repo.name} ({repo.root}): {len(rows)} rows, {n_empty} with an empty context")


# ---- score: the threshold from development only ----------------------------------


def load_set(sub: str) -> tuple[list[float], list[float], list[dict], int]:
    """P(holds) for true rows and for swapped rows. An empty-context row gets NOT_ASKED."""
    data = HERE / "data" / sub
    rows = {
        r["id"]: r
        for r in map(json.loads, (data / f"flowctx_{ARM}.jsonl").read_text().splitlines())
    }
    res_path = HERE / "results" / sub / f"flowctx_{ARM}.jsonl.gz"
    if not res_path.exists():
        return [], [], [], 0
    with gzip.open(res_path, "rt") as fh:
        recs = [r for r in map(json.loads, fh.read().splitlines()) if "error" not in r]
    recs = [r for r in recs if r["id"] in rows]
    errors = len(rows) - len(recs)
    pos = [r["answers"]["holds"]["noul"] for r in recs if rows[r["id"]]["label"]["holds"]]
    neg = [r["answers"]["holds"]["noul"] for r in recs if not rows[r["id"]]["label"]["holds"]]
    for r in json.loads((data / f"flowctx_{ARM}_empty.json").read_text()):
        (pos if r["label"]["holds"] else neg).append(NOT_ASKED)
    return pos, neg, recs, errors


def rates(pos: list[float], neg: list[float], t: float) -> tuple[float, float]:
    return sum(p < t for p in neg) / len(neg), sum(p < t for p in pos) / len(pos)


def counts(pos: list[float], neg: list[float], t: float) -> str:
    return (
        f"caught {sum(p < t for p in neg)}/{len(neg)}, flagged {sum(p < t for p in pos)}/{len(pos)}"
    )


def auc(pos: list[float], neg: list[float]) -> float:
    if not pos or not neg:
        return math.nan
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def cost(recs: list[dict]) -> str:
    ins = [r["usage"]["input_tokens"] for r in recs if r.get("usage")]
    outs = [r["usage"]["output_tokens"] for r in recs if r.get("usage")]
    secs = [r["seconds"] for r in recs if "seconds" in r]
    models = sorted({str(r.get("model")) for r in recs})
    if not ins:
        return "no usage"
    return (
        f"{len(recs)} calls, {sum(ins)} in, {sum(outs)} out, median in "
        f"{statistics.median(ins):.0f}, median {statistics.median(secs):.2f} s, models {models}"
    )


def score() -> None:
    dp, dn, drecs, derr = load_set("")
    hp, hn, hrecs, herr = load_set("holdout")
    print(f"== {ARM}")
    print(f"   development: {cost(drecs)}; errors {derr}; AUC {auc(dp, dn):.3f}")
    print(f"   holdout:     {cost(hrecs)}; errors {herr}; AUC {auc(hp, hn):.3f}")
    for t in GRID:
        h = counts(hp, hn, t) if hp and hn else "no answers"
        print(f"   P<{t:<4}  dev {counts(dp, dn, t)}   holdout {h}")
    ok = [t for t in GRID if rates(dp, dn, t)[1] <= DEV_FLAG_LIMIT]
    if not ok:
        print("   fail: no threshold keeps development flags at 2.5% or less")
        return
    t = max(ok)
    d, h = rates(dp, dn, t), rates(hp, hn, t)
    print(f"   selected P<{t}: dev {counts(dp, dn, t)}; holdout {counts(hp, hn, t)}")
    fails = []
    if d[0] < DEV_CATCH_FLOOR:
        fails.append("development catch below 50%")
    if abs(h[0] - d[0]) > WITHIN + 1e-9:
        fails.append(f"catch gap {100 * (h[0] - d[0]):+.1f} points")
    if h[1] > HOLDOUT_FLAG_LIMIT:
        fails.append(f"holdout flags {h[1]:.1%}")
    print(f"   gap {100 * (h[0] - d[0]):+.1f} points")
    print("   " + ("pass" if not fails else "fail: " + "; ".join(fails)))


def contexts(n: int) -> None:
    rows = [json.loads(x) for x in (facts_dir() / f"flowctx_{ARM}.jsonl").read_text().splitlines()]
    for r in rows[:n]:
        print(f"--- {r['repo']} {r['id']}")
        print("\n".join(r["state"]["code"]))


def main(args: list[str]) -> None:
    if args[:1] == ["build"]:
        build()
    elif args[:1] == ["score"]:
        score()
    elif args[:1] == ["show"]:
        contexts(int(args[1]))
    else:
        raise SystemExit("usage: call_site_context.py build | score | show N")


if __name__ == "__main__":
    main(sys.argv[1:])
