"""Measure context selectors for the `jev flow` question on the recorded flow cases.

    uv run --project bench/jev python bench/jev/flow_context.py build
    uv run --project bench/jev python bench/jev/run.py flowctx_base flowctx_around flowctx_calls flowctx_targets
    JEV_SET=holdout uv run --project bench/jev python bench/jev/flow_context.py build
    JEV_SET=holdout uv run --project bench/jev python bench/jev/run.py flowctx_base flowctx_around flowctx_calls flowctx_targets
    uv run --project bench/jev python bench/jev/flow_context.py score

The cases are the recorded rows of data/<set>/flowverify.jsonl: the same ids, claims,
and labels. Each arm sends the shipped question (`audit.VERIFY_Q`) and the shipped
`ends` (`audit.card_brief`). Only the `code` text is different between the arms.
`build` stops if a source file is not the file that the cached facts describe.

The arms:

- base: the `audit_code.code_between` that shipped at the time of the measurement.
  `import_context.py` keeps it, because the shipped selector now reads the
  `call_sites` fact. At most 30 lines.
- around: the shipped lines, then the adjacent lines (1, then 2 lines before and after
  each line). At most 60 lines.
- calls: the shipped lines, then the lines that use a name bound to an imported name
  (`x = Ledger(...)` or `x: Ledger`, then `x.record(...)`), then the `def`, `class`,
  or `function` line before each of these lines. At most 60 lines.
- targets: the lines of calls, then the signature from the facts of each imported
  function, class, or method that these lines use, then the first sentence of each
  target module docstring. At most 60 lines and 12 target lines.

Each line has 160 characters at most.

Acceptance value, written before the first Jev call:

- The threshold of each arm comes from the development set only. It is the largest
  value in GRID where at most 2.5% of the true development rows (2 of 80) get a flag.
  2 of 80 is the recorded development figure of the shipped selector. If no value
  of GRID satisfies this limit, the arm fails.
- At that threshold, the development catch rate must be 50% or more. This condition
  stops an arm with almost no flags from a pass.
- At that threshold, the holdout catch rate must be within 10 points of the
  development catch rate.
- At that threshold, at most 4.2% of the true holdout rows (2 of 48) can get a flag.
  2 of 48 is the recorded holdout figure "4%".
- If more than one arm satisfies these conditions, the arm with the highest development
  catch rate replaces `code_between`. If two arms have the same rate, the arm with the
  smaller median code size replaces it. If only base satisfies them, `code_between`
  does not change, and only the default kinds change.
- If an arm satisfies these conditions, `jev flow` can join the default kinds.
  If no arm satisfies them, `src/` does not change.
- Language rule: base and around use only the shipped use lines and line positions.
  calls and targets also use text patterns for Python and TypeScript syntax
  (`def`, `function`, `self.`, `this.`, `const`). Shared code must not contain these
  patterns. Thus, in this work item, only base and around can change `src/`. If calls or
  targets is the only arm that satisfies the conditions, `src/` does not change, and
  the result records that a call-site fact from each language adapter is necessary.

All the repositories in the two sets are Python repositories. Thus the result does not
show the behavior on TypeScript.

Each arm operates one time on development and then one time on holdout.
No selector changes after the holdout run.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import re
import statistics
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import build_flows
from common import DEV_REPOS, HERE, HOLDOUT_REPOS, SCRATCH, SET, SYSTEMAP, Repo
from import_context import DEFAULT, WHOLE, code_between
from import_context import bindings as _bindings

from systemap import audit, config, nest
from systemap.model import claimed
from systemap.source_facts import is_empty_marker

ARMS = ("base", "around", "calls", "targets")
LINES = 60
TARGET_LINES = 12
WIDTH = 160
GRID = (0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5)
DEV_FLAG_LIMIT = 0.025
HOLDOUT_FLAG_LIMIT = 0.042
DEV_CATCH_FLOOR = 0.5
WITHIN = 0.10

_DEF = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:def|class|function)\b")
_CALLED = re.compile(r"\.\s*(\w+)\s*\(")


# ---- the roots of the source that the cached facts describe -----------------------


def snapshot(commit: str) -> Path:
    """Write the systemap tree at the facts commit to bench/scratch, one time."""
    out = SCRATCH / f"systemap-{commit[:7]}"
    if not out.exists():
        out.mkdir(parents=True)
        tar = subprocess.run(
            ["git", "-C", str(SYSTEMAP), "archive", commit], check=True, capture_output=True
        ).stdout
        subprocess.run(["tar", "-x", "-C", str(out)], input=tar, check=True)
    return out


def root_of(name: str, facts: dict[str, Any]) -> Path:
    """The source root: JEV_ROOT_<NAME>, or the set's root, or a systemap snapshot."""
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


def folder_packages(facts: dict[str, Any]) -> dict[str, Any]:
    """Write the folder package into each cached record, as `call_site_context.py` does.

    Format 2 wrote the first name part as `package`. `audit.modules_by_card` reads the
    folder package: the parent package, or the name of a package root.
    """
    prefixes = set(facts["packages"])
    for module, record in facts["components"].items():
        record["package"] = module if module in prefixes else module.rsplit(".", 1)[0]
    return facts


def load_repo(name: str) -> tuple[Repo, Any]:
    """The repository at the cached facts, and the top map."""
    facts = folder_packages(json.loads((facts_dir() / f"facts-{name}.json").read_text()))
    root = root_of(name, facts)
    cfg = config.load(root)
    top = nest.load(cfg).top
    mods = [m for m, r in facts["components"].items() if not is_empty_marker(r)]
    owner: dict[str, str] = {}
    for c in top.model.components:
        for m in claimed(c, mods):
            owner.setdefault(m, c.id)
    return Repo(name, root, cfg, top.model, top.meaning, facts, owner), top


def stale(repo: Repo, modules: list[str]) -> list[str]:
    """The modules whose source file is not the file that the facts describe."""
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


# ---- the selectors ----------------------------------------------------------------


@dataclass
class Side:
    """One module at one end of a flow that uses names from the other end."""

    module: str
    lines: list[str]
    names: set[str]
    targets: list[str]


def _read(root: Path, facts: dict[str, Any], module: str) -> str | None:
    try:
        return (root / str(facts["components"][module]["file"])).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError, KeyError):
        return None


def _side(root: Path, facts: dict[str, Any], a: str, others: list[str]) -> Side | None:
    uses = facts["components"][a].get("uses", {})
    wanted = {b: set(uses[b]) for b in others if b in uses}
    text = _read(root, facts, a) if wanted else None
    if text is None:
        return None
    names: set[str] = set()
    for target, imported in wanted.items():
        names |= imported - {WHOLE, DEFAULT}
        if imported & {WHOLE, DEFAULT}:
            names |= _bindings(text, facts, a, target)
    return Side(a, text.splitlines(), names, sorted(wanted)) if names else None


def sides(root: Path, facts: dict[str, Any], by: dict[str, list[str]], src: str, dst: str):
    out: list[Side] = []
    for a_card, b_card in ((src, dst), (dst, src)):
        for a in by.get(a_card, []):
            s = _side(root, facts, a, by.get(b_card, []))
            if s is not None:
                out.append(s)
    return out


def word_pattern(names: set[str]) -> re.Pattern[str]:
    return re.compile(r"\b(" + "|".join(map(re.escape, sorted(names))) + r")\b")


def hits(s: Side) -> list[int]:
    pat = word_pattern(s.names)
    return [i for i, ln in enumerate(s.lines) if pat.search(ln)]


Pick = tuple[int, int]  # (side index, line index)


def fill(tiers: list[list[Pick]], sides_: list[Side], limit: int) -> list[Pick]:
    """Take the lines tier by tier until the limit. Blank lines do not count."""
    chosen: list[Pick] = []
    seen: set[Pick] = set()
    for tier in tiers:
        for k, i in tier:
            if len(chosen) >= limit:
                return chosen
            if (k, i) in seen or not (0 <= i < len(sides_[k].lines)):
                continue
            if sides_[k].lines[i].strip():
                seen.add((k, i))
                chosen.append((k, i))
    return chosen


def render(chosen: list[Pick], sides_: list[Side]) -> list[str]:
    return [
        f"{sides_[k].module}:{i + 1}: {sides_[k].lines[i].strip()[:WIDTH]}"
        for k, i in sorted(chosen)
    ]


def hit_tier(sides_: list[Side]) -> list[Pick]:
    return [(k, i) for k, s in enumerate(sides_) for i in hits(s)]


def around(root: Path, facts: dict[str, Any], by: dict[str, list[str]], src: str, dst: str):
    ss = sides(root, facts, by, src, dst)
    first = hit_tier(ss)
    tiers = [first] + [[(k, i + d) for k, i in first for d in (-r, r)] for r in (1, 2)]
    return render(fill(tiers, ss, LINES), ss)


def bound(s: Side) -> set[str]:
    """The local names bound to an imported name: `x = Name(...)` or `x: Name`."""
    alt = "|".join(map(re.escape, sorted(s.names)))
    target = rf"(?:await\s+)?(?:new\s+)?(?:[\w.]+\.)?(?:{alt})\b"
    keyword = r"(?:(?:export|const|let|var|private|public|protected|readonly)\s+)*"
    assign = re.compile(rf"^\s*{keyword}(?:(?:self|this)\.)?(\w+)\s*(?::[^=]*)?=\s*{target}")
    annot = re.compile(rf"\b(\w+)\??\s*:\s*(?:[\w.]+\[)?['\"]?{target}")
    out: set[str] = set()
    for ln in s.lines:
        out |= {m[1] for p in (assign, annot) for m in p.finditer(ln)}
    return {v for v in out if len(v) > 1 and v not in s.names}


def var_tier(sides_: list[Side]) -> list[Pick]:
    out: list[Pick] = []
    for k, s in enumerate(sides_):
        names = bound(s)
        if not names:
            continue
        # Not in a path or a file name: "run-manifest.json" is not a use of `manifest`.
        alt = "|".join(map(re.escape, sorted(names)))
        pat = re.compile(r"(?<![\w/\"'-])(?:" + alt + r")\s*\.\s*[A-Za-z_]\w*\b(?![\"'/-])")
        out += [(k, i) for i, ln in enumerate(s.lines) if pat.search(ln)]
    return out


def enclosing(s: Side, i: int) -> int | None:
    for j in range(i, -1, -1):
        if _DEF.match(s.lines[j]):
            return j
    return None


def def_tier(sides_: list[Side], picks: list[Pick]) -> list[Pick]:
    out: list[Pick] = []
    for k, i in picks:
        j = enclosing(sides_[k], i)
        if j is not None and j != i:
            out.append((k, j))
    return out


def call_picks(ss: list[Side]) -> list[Pick]:
    first, second = hit_tier(ss), var_tier(ss)
    return fill([first, second, def_tier(ss, first + second)], ss, LINES)


def calls(root: Path, facts: dict[str, Any], by: dict[str, list[str]], src: str, dst: str):
    ss = sides(root, facts, by, src, dst)
    return render(call_picks(ss), ss)


def used_names(chosen: list[Pick], ss: list[Side]) -> dict[str, set[str]]:
    """For each target module: the names and called attributes in the chosen lines."""
    out: dict[str, set[str]] = {}
    for k, i in chosen:
        ln = ss[k].lines[i]
        words = set(re.findall(r"\w+", ln)) | set(_CALLED.findall(ln))
        for t in ss[k].targets:
            out.setdefault(t, set()).update(words)
    return out


def signatures(rec: dict[str, Any], words: set[str]) -> list[str]:
    out = [f["signature"] for f in rec.get("functions", []) if f["name"] in words]
    for c in rec.get("classes", []):
        if c["name"] not in words:
            continue
        methods = [m for m in c.get("methods", []) if _method_name(m) in words]
        out.append(f"class {c['name']}" + (": " + "; ".join(methods[:2]) if methods else ""))
    return out


def _method_name(signature: str) -> str:
    m = re.search(r"(\w+)\s*\(", signature)
    return m[1] if m else ""


def target_lines(facts: dict[str, Any], used: dict[str, set[str]]) -> list[str]:
    defs: list[str] = []
    docs: list[str] = []
    for t, words in sorted(used.items()):
        rec = facts["components"].get(t, {})
        defs += [f"{t} defines: {sig}"[:WIDTH] for sig in signatures(rec, words)]
        doc = " ".join((rec.get("docstring") or "").split())
        if doc:
            docs.append(f"{t} docstring: {doc.split('. ')[0]}"[:WIDTH])
    return (defs + docs)[:TARGET_LINES]


def targets(root: Path, facts: dict[str, Any], by: dict[str, list[str]], src: str, dst: str):
    ss = sides(root, facts, by, src, dst)
    chosen = call_picks(ss)
    return render(chosen, ss) + target_lines(facts, used_names(chosen, ss))


def base(root: Path, facts: dict[str, Any], by: dict[str, list[str]], src: str, dst: str):
    return code_between(root, facts, by, src, dst)


SELECTORS = {"base": base, "around": around, "calls": calls, "targets": targets}


# ---- build: the rows of each arm ---------------------------------------------------


def edge_of(row: dict[str, Any]) -> tuple[str, str]:
    src, dst = row["id"].rsplit(":", 1)[0].split("->", 1)
    return src, dst


def build() -> None:
    old = [json.loads(x) for x in (facts_dir() / "flowverify.jsonl").read_text().splitlines()]
    out: dict[str, list[dict[str, Any]]] = {a: [] for a in ARMS}
    for name in sorted({r["repo"] for r in old}):
        repo, top = load_repo(name)
        build_repo(repo, top, [r for r in old if r["repo"] == name], out)
    for arm, rows in out.items():
        write_arm(arm, rows)


def write_arm(arm: str, rows: list[dict[str, Any]]) -> None:
    path = facts_dir() / f"flowctx_{arm}.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    sizes = [sum(len(x) for x in r["state"]["code"]) for r in rows]
    empty = sum(not r["state"]["code"] for r in rows)
    print(
        f"{arm}: {len(rows)} rows, median code {statistics.median(sizes):.0f} chars, "
        f"max {max(sizes)}, empty {empty} -> {path.name}"
    )


def build_repo(repo: Repo, top: Any, rows: list[dict[str, Any]], out: dict) -> None:
    by = audit.modules_by_card(top.model, repo.facts)
    ends = {c for r in rows for c in edge_of(r)}
    bad = stale(repo, sorted({m for c in ends for m in by.get(c, [])}))
    if bad:
        raise SystemExit(
            f"{repo.name}: the source is not the source of the facts:\n" + "\n".join(bad)
        )
    same = sum(build_flows.code_between(repo, *edge_of(r)) == r["state"]["code"] for r in rows)
    print(f"{repo.name} ({repo.root}): {len(rows)} rows, recorded code made again on {same}")
    question = {"holds": {"type": "noul", "instructions": audit.VERIFY_Q}}
    for r in rows:
        src, dst = edge_of(r)
        brief = {x: audit.card_brief(top.model, top.meaning, x) for x in (src, dst)}
        for arm, select in SELECTORS.items():
            code = select(repo.root, repo.facts, by, src, dst)
            state = {"claim": r["state"]["claim"], "ends": brief, "code": code}
            out[arm].append({**r, "exp": f"flowctx_{arm}", "state": state, "questions": question})


# ---- score: both sets, the threshold from development only ------------------------


def load_set(sub: str, arm: str) -> tuple[list[float], list[float], list[dict]]:
    """P(holds) for true rows, P(holds) for swapped rows, and the answer records."""
    data_path = HERE / "data" / sub / f"flowctx_{arm}.jsonl"
    res_path = HERE / "results" / sub / f"flowctx_{arm}.jsonl.gz"
    if not data_path.exists() or not res_path.exists():
        return [], [], []
    rows = {r["id"]: r for r in map(json.loads, data_path.read_text().splitlines())}
    with gzip.open(res_path, "rt") as fh:
        recs = [r for r in map(json.loads, fh.read().splitlines()) if "error" not in r]
    recs = [r for r in recs if r["id"] in rows]
    pos = [r["answers"]["holds"]["noul"] for r in recs if rows[r["id"]]["label"]["holds"]]
    neg = [r["answers"]["holds"]["noul"] for r in recs if not rows[r["id"]]["label"]["holds"]]
    return pos, neg, recs


def rates(pos: list[float], neg: list[float], t: float) -> tuple[float, float]:
    """The fraction of swapped rows caught and of true rows flagged at P < t."""
    return sum(p < t for p in neg) / len(neg), sum(p < t for p in pos) / len(pos)


def auc(pos: list[float], neg: list[float]) -> float:
    if not pos or not neg:
        return math.nan
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def select_threshold(pos: list[float], neg: list[float]) -> float | None:
    ok = [t for t in GRID if rates(pos, neg, t)[1] <= DEV_FLAG_LIMIT]
    return max(ok) if ok else None


def cost(recs: list[dict]) -> str:
    ins = [r["usage"]["input_tokens"] for r in recs if r.get("usage")]
    outs = [r["usage"]["output_tokens"] for r in recs if r.get("usage")]
    if not ins:
        return "no usage"
    return (
        f"{len(recs)} calls, {sum(ins)} in, {sum(outs)} out, median in {statistics.median(ins):.0f}"
    )


def verdict(dev: tuple[float, float], hold: tuple[float, float]) -> list[str]:
    fails = []
    if dev[0] < DEV_CATCH_FLOOR:
        fails.append("development catch below 50%")
    if abs(hold[0] - dev[0]) > WITHIN + 1e-9:
        fails.append(f"catch gap {100 * (hold[0] - dev[0]):+.1f} points")
    if hold[1] > HOLDOUT_FLAG_LIMIT:
        fails.append(f"holdout flags {hold[1]:.1%}")
    return fails


def score_arm(arm: str) -> tuple[str, float | None, list[str]]:
    dp, dn, drecs = load_set("", arm)
    hp, hn, hrecs = load_set("holdout", arm)
    print(f"== {arm}")
    print(
        f"   development: {cost(drecs)}; AUC {auc(dp, dn):.3f} (true {len(dp)}, swapped {len(dn)})"
    )
    print(
        f"   holdout:     {cost(hrecs)}; AUC {auc(hp, hn):.3f} (true {len(hp)}, swapped {len(hn)})"
    )
    if not (dp and dn):
        return arm, None, ["no development answers"]
    for t in GRID:
        d = rates(dp, dn, t)
        h = rates(hp, hn, t) if hp and hn else (math.nan, math.nan)
        print(
            f"   P<{t:<4}  dev caught {d[0]:4.0%} flagged {d[1]:4.0%}"
            f"   holdout caught {h[0]:4.0%} flagged {h[1]:4.0%}"
        )
    t = select_threshold(dp, dn)
    if t is None:
        return arm, None, ["no threshold keeps development flags at 2.5% or less"]
    if not (hp and hn):
        return arm, t, ["no holdout answers"]
    d, h = rates(dp, dn, t), rates(hp, hn, t)
    print(
        f"   selected P<{t}: dev {d[0]:.1%} caught, {d[1]:.1%} flagged; "
        f"holdout {h[0]:.1%} caught, {h[1]:.1%} flagged"
    )
    return arm, t, verdict(d, h)


def score() -> None:
    results = [score_arm(a) for a in ARMS]
    print("\n== acceptance")
    for arm, t, fails in results:
        print(f"   {arm:<8} threshold {t}: {'pass' if not fails else 'fail: ' + '; '.join(fails)}")


def contexts(arm: str, n: int) -> None:
    """Print the code of the first n rows of an arm, to examine the selector output."""
    rows = [json.loads(x) for x in (facts_dir() / f"flowctx_{arm}.jsonl").read_text().splitlines()]
    for r in rows[:n]:
        print(f"--- {r['repo']} {r['id']}")
        print("\n".join(r["state"]["code"]))


def main(args: list[str]) -> None:
    if args[:1] == ["build"]:
        build()
    elif args[:1] == ["score"]:
        score()
    elif args[:1] == ["show"]:
        contexts(args[1], int(args[2]))
    else:
        raise SystemExit("usage: flow_context.py build | score | show ARM N")


if __name__ == "__main__":
    main(sys.argv[1:])
