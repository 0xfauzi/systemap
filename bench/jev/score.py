"""Score every experiment against its labels and against the heuristic systemap uses today.

uv run python score.py [exp ...]
"""

from __future__ import annotations

import gzip
import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from common import load

from systemap.judgement import package_of, share_a_package, share_a_word, words

HERE = Path(__file__).parent


def rows(exp: str) -> dict[str, dict]:
    return {
        r["id"]: r
        for r in map(json.loads, (HERE / "data" / f"{exp}.jsonl").read_text().splitlines())
    }


def results(exp: str) -> dict[str, dict]:
    path = HERE / "results" / f"{exp}.jsonl.gz"
    out = {}
    if path.exists():
        with gzip.open(path, "rt") as fh:
            lines = fh.read().splitlines()
        for r in map(json.loads, lines):
            if "error" not in r:
                out[r["id"]] = r
    return out


def auc(pos: list[float], neg: list[float]) -> float:
    """Probability a random positive outranks a random negative (ties count half)."""
    if not pos or not neg:
        return float("nan")
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def usage_line(res: dict[str, dict]) -> str:
    ins = [r["usage"]["input_tokens"] for r in res.values() if r.get("usage")]
    outs = [r["usage"]["output_tokens"] for r in res.values() if r.get("usage")]
    secs = sorted(r["seconds"] for r in res.values())
    if not secs:
        return "no results"
    return (
        f"n={len(res)} tokens in median {statistics.median(ins):.0f} (max {max(ins)}), "
        f"out median {statistics.median(outs):.0f}; latency p50 {secs[len(secs) // 2]:.2f}s "
        f"p90 {secs[int(len(secs) * 0.9)]:.2f}s"
    )


def probs(answer: dict) -> dict[str, float]:
    p = answer.get("probabilities")
    if isinstance(p, dict):
        return p
    return {}


def per_repo(fn, items):
    by = defaultdict(list)
    for it in items:
        by[it[0]].append(it[1])
    return {k: fn(v) for k, v in sorted(by.items())}


def pct(xs) -> str:
    return f"{100 * sum(xs) / len(xs):.0f}% ({sum(xs)}/{len(xs)})" if xs else "-"


# ---- baselines from the facts alone ---------------------------------------


def comp_words(repo, cid) -> set[str]:
    c = repo.comp(cid)
    return words(c.id) | words(c.does) | words(repo.meaning.plain.get(cid, "")) | words(c.interface)


def package_guess(repo, m: str) -> str | None:
    """Leave-one-out: the component that claims most other modules in m's package."""
    votes = Counter(c for o, c in repo.owner.items() if o != m and package_of(o) == package_of(m))
    return votes.most_common(1)[0][0] if votes else None


def word_guess(repo, text_words: set[str]) -> str | None:
    best = max(
        repo.placeable(),
        key=lambda c: len({w for w in text_words if share_a_word({w}, comp_words(repo, c.id))}),
    )
    return best.id


def misfold_fires(repo, m: str, cid: str) -> bool:
    """systemap's current `possible mis-fold` test for module m in component cid."""
    others = [o for o in repo.modules_of(cid) if o != m]
    if len(others) + 1 < 2:
        return False
    if share_a_word(words(m), comp_words(repo, cid)):
        return False
    return not any(share_a_package(m, o) for o in others)


# ---- experiments ----------------------------------------------------------


def owner_accuracy(data: dict, res: dict) -> None:
    top1, top3, base_pkg, base_word, conf = [], [], [], [], {True: [], False: []}
    for i, r in res.items():
        d = data[i]
        repo = load(d["repo"])
        a = r["answers"]["owner"]
        p = probs(a)
        true = d["label"]["owner"]
        top1.append((d["repo"], a["choice"] == true))
        top3.append((d["repo"], true in sorted(p, key=lambda k: p[k], reverse=True)[:3]))
        conf[a["choice"] == true].append(a["confidence"])
        base_pkg.append((d["repo"], package_guess(repo, i) == true))
        base_word.append((d["repo"], word_guess(repo, words(i)) == true))
    print(
        "   Jev top-1      ",
        pct([x for _, x in top1]),
        per_repo(lambda v: f"{sum(v)}/{len(v)}", top1),
    )
    print("   Jev top-3      ", pct([x for _, x in top3]))
    print("   baseline pkg   ", pct([x for _, x in base_pkg]), "(leave-one-out package majority)")
    print("   baseline words ", pct([x for _, x in base_word]))
    print(
        f"   confidence when right {statistics.median(conf[True]):.2f}, "
        f"when wrong {statistics.median(conf[False] or [0]):.2f}"
    )
    for t in (0.8, 0.9, 0.95):
        sel = [i for i in res if res[i]["answers"]["owner"]["confidence"] >= t]
        right = sum(res[i]["answers"]["owner"]["choice"] == data[i]["label"]["owner"] for i in sel)
        print(
            f"   suggest at confidence >= {t}: answers {len(sel) / len(res):.0%}, right {right / len(sel):.0%}"
        )


def neighbour(repo, true: str, r: random.Random) -> str | None:
    """A card in the same region or container as the true one, with two modules or more."""
    home = repo.comp(true).home
    near = [
        c.id
        for c in repo.placeable()
        if c.id != true and c.home == home and len(repo.modules_of(c.id)) >= 2
    ]
    return r.choice(near) if near else None


def misfold_report(title: str, planted: list[tuple[str, str, str, float, float]]) -> None:
    """planted: (repo, module, true card, P(true), P(planted card))."""
    p_true = [x[3] for x in planted]
    p_wrong = [x[4] for x in planted]
    print(f"   mis-fold, module planted in {title} (n={len(planted)}):")
    print(
        f"     Jev AUC (1 - P(current owner)) = {auc([1 - x for x in p_wrong], [1 - x for x in p_true]):.3f}"
    )
    for t in (0.05, 0.1, 0.2):
        caught = sum(x < t for x in p_wrong) / len(p_wrong)
        false_rate = sum(x < t for x in p_true) / len(p_true)
        print(
            f"     Jev flag P<{t}: catches {caught:.0%} of planted, flags {false_rate:.0%} of correct"
        )


def owner_misfold(data: dict, res: dict) -> None:
    rnd, near, rule = [], [], {"random": [0, 0], "neighbour": [0, 0]}
    r = random.Random(7)
    for i, x in res.items():
        d = data[i]
        repo = load(d["repo"])
        true, wrong = d["label"]["owner"], d["label"]["wrong"]
        p = probs(x["answers"]["owner"])
        rnd.append((d["repo"], i, true, p.get(true, 0.0), p.get(wrong, 0.0)))
        rule["random"][0] += misfold_fires(repo, i, wrong)
        rule["random"][1] += misfold_fires(repo, i, true)
        nb = neighbour(repo, true, r)
        if nb is not None:
            near.append((d["repo"], i, true, p.get(true, 0.0), p.get(nb, 0.0)))
            rule["neighbour"][0] += misfold_fires(repo, i, nb)
    misfold_report("a random wrong card", rnd)
    misfold_report("a neighbouring card", near)
    print(
        f"     current word rule: catches {rule['random'][0] / len(rnd):.0%} planted at random, "
        f"{rule['neighbour'][0] / len(near):.0%} planted next door; flags {rule['random'][1] / len(rnd):.0%} of correct"
    )


def score_owner():
    data, res = rows("owner"), results("owner")
    print("== owner (ideas 1+2): which card claims this module?")
    print("  ", usage_line(res))
    owner_accuracy(data, res)
    owner_misfold(data, res)


def score_where():
    data, res = rows("where"), results("where")
    top1, top3, base = [], [], []
    for i, r in res.items():
        d = data[i]
        repo = load(d["repo"])
        a = r["answers"]["where"]
        p = probs(a)
        ranked = sorted(p, key=p.get, reverse=True)
        true = d["label"]["owner"]
        top1.append((d["repo"], a["choice"] == true))
        top3.append((d["repo"], true in ranked[:3]))
        base.append((d["repo"], word_guess(repo, words(d["state"]["question"])) == true))
    print("== where (N1): which card does this described behaviour live in?")
    print("  ", usage_line(res))
    print(
        "   Jev top-1      ",
        pct([x for _, x in top1]),
        per_repo(lambda v: f"{sum(v)}/{len(v)}", top1),
    )
    print("   Jev top-3      ", pct([x for _, x in top3]))
    print("   baseline words ", pct([x for _, x in base]))


def score_pairs():
    data, res = rows("pairs"), results("pairs")
    by = defaultdict(list)
    for i, r in res.items():
        d = data[i]
        by[d["label"]["tag"]].append((r["answers"]["same"]["noul"], d))
    same = [p for p, _ in by["same"]]
    print("== pairs (N10): do two modules make one part?")
    print("  ", usage_line(res))
    print(
        f"   Jev AUC same vs all-different  {auc(same, [p for p, _ in by['hard'] + by['easy']]):.3f}"
    )
    print(
        f"   Jev AUC same vs same-package   {auc(same, [p for p, _ in by['hard']]):.3f}  (the hard case)"
    )

    def pkg(d):
        a, b = d["id"].split("|")
        return 1.0 if package_of(a) == package_of(b) else 0.0

    print(
        f"   baseline same-package AUC      {auc([pkg(d) for _, d in by['same']], [pkg(d) for _, d in by['hard'] + by['easy']]):.3f}"
    )
    print(
        f"   baseline on the hard case      {auc([pkg(d) for _, d in by['same']], [pkg(d) for _, d in by['hard']]):.3f}"
    )


def score_flowkind():
    data, res = rows("flowkind"), results("flowkind")
    ok, maj = [], []
    confusion = Counter()
    for i, r in res.items():
        d = data[i]
        true = d["label"]["kind"]
        got = r["answers"]["kind"]["choice"]
        ok.append((d["repo"], got == true))
        confusion[(true, got)] += 1
    counts = defaultdict(Counter)
    for d in data.values():
        counts[d["repo"]][d["label"]["kind"]] += 1
    for i in res:
        d = data[i]
        maj.append(d["label"]["kind"] == counts[d["repo"]].most_common(1)[0][0])
    print("== flowkind (N6): does the flow's kind match its sentence?")
    print("  ", usage_line(res))
    print(
        "   Jev accuracy       ",
        pct([x for _, x in ok]),
        per_repo(lambda v: f"{sum(v)}/{len(v)}", ok),
    )
    print("   baseline majority  ", pct(maj))
    print(
        "   disagreements (map kind -> Jev):",
        dict((f"{a}->{b}", n) for (a, b), n in confusion.most_common() if a != b),
    )


def score_noul(exp: str, q: str, label: str, title: str):
    data, res = rows(exp), results(exp)
    pos = [r["answers"][q]["noul"] for i, r in res.items() if data[i]["label"][label]]
    neg = [r["answers"][q]["noul"] for i, r in res.items() if not data[i]["label"][label]]
    print(title)
    print("  ", usage_line(res))
    print(f"   Jev AUC {auc(pos, neg):.3f}   (n pos {len(pos)}, neg {len(neg)})")
    if pos and neg:
        print(
            f"   median P(yes): true {statistics.median(pos):.2f}, false {statistics.median(neg):.2f}"
        )
        for t in (0.5,):
            print(
                f"   at {t}: accepts {sum(p >= t for p in pos) / len(pos):.0%} of true, {sum(p >= t for p in neg) / len(neg):.0%} of false"
            )
    return data, res


def score_crossing():
    data, res = rows("crossing"), results("crossing")
    pos, neg, bpos, bneg = [], [], [], []
    by_repo = defaultdict(lambda: ([], []))
    for i, r in res.items():
        d = data[i]
        s = r["answers"]["matters"]["score"]
        edge = d["label"]["edge"]
        (pos if edge else neg).append(s)
        by_repo[d["repo"]][0 if edge else 1].append(s)
        (bpos if edge else bneg).append(d["state"]["modules_importing"])
    print("== crossing (idea 5): is this crossing import an edge the reader needs?")
    print("  ", usage_line(res))
    print(
        f"   Jev AUC {auc(pos, neg):.3f}  (edge drawn {len(pos)}, answered as incidental {len(neg)})"
    )
    print("   per repo:", {k: f"{auc(*v):.2f}" for k, v in sorted(by_repo.items())})
    print(f"   baseline AUC (how many modules import) {auc(bpos, bneg):.3f}")
    ranked = sorted(pos + neg, reverse=True)
    for frac in (0.25, 0.5):
        cut = ranked[int(len(ranked) * frac)]
        print(
            f"   answering the lowest-scored {1 - frac:.0%} as incidental would wrongly drop "
            f"{sum(p < cut for p in pos) / len(pos):.0%} of drawn edges and clear {sum(n < cut for n in neg) / len(neg):.0%} of answered lines"
        )


def score_drift():
    data, res = rows("drift"), results("drift")
    print("== drift (the PR idea): does the card's sentence still hold after this diff?")
    print("  ", usage_line(res))
    pos = [
        1 - r["answers"]["does_holds"]["noul"]
        for i, r in res.items()
        if data[i]["label"]["does_changed"]
    ]
    neg = [
        1 - r["answers"]["does_holds"]["noul"]
        for i, r in res.items()
        if not data[i]["label"]["does_changed"]
    ]
    print(f"   does: AUC {auc(pos, neg):.3f} (sentence rewritten {len(pos)}, kept {len(neg)})")
    ipos = [
        1 - r["answers"]["interface_holds"]["noul"]
        for i, r in res.items()
        if data[i]["label"]["interface_changed"]
    ]
    ineg = [
        1 - r["answers"]["interface_holds"]["noul"]
        for i, r in res.items()
        if not data[i]["label"]["interface_changed"]
    ]
    print(f"   interface: AUC {auc(ipos, ineg):.3f} (rewritten {len(ipos)}, kept {len(ineg)})")
    print("   rewritten cases:")
    for i, r in sorted(res.items()):
        if data[i]["label"]["does_changed"]:
            print(
                f"     {i}: P(still holds) {r['answers']['does_holds']['noul']:.2f}, kind {r['answers']['change_kind']['choice']}"
            )
    flagged = sorted(
        (
            (r["answers"]["does_holds"]["noul"], i)
            for i, r in res.items()
            if not data[i]["label"]["does_changed"]
        )
    )[:6]
    print("   kept sentences Jev doubts most (candidates for missed drift, or false alarms):")
    for p, i in flagged:
        print(
            f"     {i}: P(still holds) {p:.2f}, kind {res[i]['answers']['change_kind']['choice']}"
        )
    print(
        "   change kind distribution:",
        Counter(r["answers"]["change_kind"]["choice"] for r in res.values()),
    )


def score_issues():
    data, res = rows("issues"), results("issues")
    top1, top3, base = [], [], []
    for i, r in res.items():
        d = data[i]
        repo = load(d["repo"])
        a = r["answers"]["where"]
        p = probs(a)
        ranked = sorted(p, key=lambda k: p[k], reverse=True)
        owners = set(d["label"]["owners"])
        top1.append((d["repo"], a["choice"] in owners))
        top3.append((d["repo"], bool(owners & set(ranked[:3]))))
        base.append((d["repo"], word_guess(repo, words(d["state"]["report"])) in owners))
    print("== issues (N5): which card will the fix for this real bug report change?")
    print("  ", usage_line(res))
    print(
        "   Jev top-1      ",
        pct([x for _, x in top1]),
        per_repo(lambda v: f"{sum(v)}/{len(v)}", top1),
    )
    print("   Jev top-3      ", pct([x for _, x in top3]))
    print("   baseline words ", pct([x for _, x in base]))


def score_cardkind():
    data, res = rows("cardkind"), results("cardkind")
    conf = Counter(
        (data[i]["label"]["kind"], r["answers"]["kind"]["choice"]) for i, r in res.items()
    )
    ok = [data[i]["label"]["kind"] == r["answers"]["kind"]["choice"] for i, r in res.items()]
    print("== cardkind (N7): what kind of card are these modules?")
    print("  ", usage_line(res))
    print(
        "   Jev accuracy",
        pct(ok),
        " baseline all-component",
        pct([data[i]["label"]["kind"] == "component" for i in res]),
    )
    print("   (map kind, Jev kind):", dict((f"{a}->{b}", n) for (a, b), n in conf.most_common()))


SCORERS = {
    "owner": score_owner,
    "where": score_where,
    "pairs": score_pairs,
    "flowkind": score_flowkind,
    "flowverify": lambda: score_noul(
        "flowverify",
        "holds",
        "holds",
        "== flowverify (idea 4): does the code carry the flow the sentence claims?",
    ),
    "crossing": score_crossing,
    "sentence": lambda: score_noul(
        "sentence",
        "describes",
        "describes",
        "== sentence (N4): does the card's sentence describe its modules?",
    ),
    "drift": score_drift,
    "issues": score_issues,
    "cardkind": score_cardkind,
    "governs": lambda: score_noul(
        "governs", "governs", "governs", "== governs (N3): does this invariant govern this card?"
    ),
    "answerfit": lambda: score_noul(
        "answerfit",
        "covers",
        "covers",
        "== answerfit (N8): does a recorded answer cover this crossing import?",
    ),
}

if __name__ == "__main__":
    for exp in sys.argv[1:] or SCORERS:
        if results(exp):
            SCORERS[exp]()
            print()
        else:
            print(f"== {exp}: no results yet\n")
