"""Test 9: can Jev group modules into cards better than their packages do?

    uv run python grouping.py build   # candidate pairs -> data/grouping.jsonl
    uv run python run.py grouping
    uv run python grouping.py score

Asking about every pair does not scale (mealie: about 95,000), so only
candidate pairs are asked: two modules an import joins, and neighbours in
name order within one package, which chains every package together. A
grouping is the connected components of the pairs Jev calls one part. It is
scored by pairwise F1 against the finished map, beside the grouping
`systemap suggest` starts from: one card per package.
"""

from __future__ import annotations

import sys
from collections import defaultdict

from build import SAME_Q, package
from common import REPOS, Repo, load, module_state, noul, row, write


def modules(repo: Repo) -> list[str]:
    placeable = {c.id for c in repo.placeable()}
    return sorted(m for m, c in repo.owner.items() if c in placeable)


def candidates(repo: Repo) -> list[tuple[str, str]]:
    mods = modules(repo)
    known = set(mods)
    by_package: dict[str, list[str]] = defaultdict(list)
    for m in mods:
        by_package[package(m)].append(m)
    pairs: set[tuple[str, str]] = {
        (a, b) for ms in by_package.values() for a, b in zip(ms, ms[1:], strict=False)
    }
    for a in mods:
        for b in repo.records[a].get("imports", []):
            if b in known and b != a:
                pairs.add((a, b) if a < b else (b, a))
    return sorted(pairs)


def build() -> None:
    rows = []
    for name in REPOS:
        repo = load(name)
        rows += [
            row(
                "grouping",
                name,
                f"{name}:{a}|{b}",
                {
                    "system": name,
                    "module_a": module_state(repo, a, names_cap=25),
                    "module_b": module_state(repo, b, names_cap=25),
                },
                {"same": noul(SAME_Q)},
                {"same": repo.owner[a] == repo.owner[b]},
            )
            for a, b in candidates(repo)
        ]
    write("grouping", rows)


def components(mods: list[str], edges: list[tuple[str, str]]) -> dict[str, str]:
    """module -> the smallest module name in its connected component (union-find)."""
    parent = {m: m for m in mods}

    def find(m: str) -> str:
        while parent[m] != m:
            parent[m] = parent[parent[m]]
            m = parent[m]
        return m

    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    return {m: find(m) for m in mods}


def pairwise_f1(
    mods: list[str], truth: dict[str, str], guess: dict[str, str]
) -> tuple[float, float, float]:
    tp = fp = fn = 0
    for i, a in enumerate(mods):
        for b in mods[i + 1 :]:
            t, g = truth[a] == truth[b], guess[a] == guess[b]
            tp += t and g
            fp += g and not t
            fn += t and not g
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


THRESHOLDS = (0.1, 0.2, 0.3, 0.4, 0.5)


def repo_scores(name: str, res: dict) -> dict[str, tuple[float, float, float]]:
    repo = load(name)
    mods = modules(repo)
    truth = {m: repo.owner[m] for m in mods}
    out = {"package": pairwise_f1(mods, truth, {m: package(m) for m in mods})}
    p_same: dict[tuple[str, str], float] = {}
    for i, r in res.items():
        if i.startswith(name + ":"):
            a, b = i.split(":", 1)[1].split("|")
            p_same[(a, b)] = r["answers"]["same"]["noul"]
    for t in THRESHOLDS:
        guess = components(mods, [e for e, p in p_same.items() if p >= t])
        out[f"Jev>={t}"] = pairwise_f1(mods, truth, guess)
    return out


def score() -> None:
    from score import results, rows

    data, res = rows("grouping"), results("grouping")
    print("== grouping (test 9): pairwise F1 against the finished map")
    print(f"   calls per repo: { {n: sum(d['repo'] == n for d in data.values()) for n in REPOS} }")
    table = {name: repo_scores(name, res) for name in REPOS}
    for name, scores in table.items():
        print(
            f"   {name:10s} "
            + "; ".join(f"{k} {f:.2f} (P {p:.2f} R {r:.2f})" for k, (p, r, f) in scores.items())
        )
    keys = list(next(iter(table.values())))
    means = {k: sum(table[n][k][2] for n in REPOS) / len(REPOS) for k in keys}
    print("   mean F1: " + ", ".join(f"{k} {v:.2f}" for k, v in means.items()))
    best = max((k for k in keys if k != "package"), key=lambda k: means[k])
    print(
        f"   best Jev threshold {best}: {means[best] - means['package']:+.2f} over package grouping (pass: +0.10)"
    )
    held_out(table, [k for k in keys if k != "package"])


def held_out(table: dict, jev_keys: list[str]) -> None:
    """Choose the threshold on four repos, score it on the fifth: the estimate a new repo would see."""
    gains = []
    for name in REPOS:
        others = [n for n in REPOS if n != name]
        k = max(jev_keys, key=lambda key: sum(table[n][key][2] for n in others))
        gain = table[name][k][2] - table[name]["package"][2]
        gains.append(gain)
        print(
            f"   held out {name:10s}: threshold chosen on the others {k}, F1 {table[name][k][2]:.2f} vs package {table[name]['package'][2]:.2f} ({gain:+.2f})"
        )
    print(
        f"   held-out mean gain {sum(gains) / len(gains):+.2f}; repos where Jev loses: {sum(g < 0 for g in gains)} of {len(gains)}"
    )


if __name__ == "__main__":
    {"build": build, "score": score}[sys.argv[1]]()
