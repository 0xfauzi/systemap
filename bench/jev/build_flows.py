"""The datasets about edges: does the code carry a flow, does a crossing
import need an edge, does a recorded answer cover one."""

from __future__ import annotations

import re
import tomllib
from collections import defaultdict
from typing import Any

from common import REPOS, Repo, component_brief, load, noul, rng, row, write

# ---- idea 4: does the code carry the flow the sentence claims? ------------


def lines_using(repo: Repo, module: str, names: set[str]) -> list[str]:
    """The lines of one module's file that mention any of `names`."""
    try:
        text = (repo.root / repo.records[module]["file"]).read_text().splitlines()
    except (FileNotFoundError, UnicodeDecodeError):
        return []
    pat = re.compile(r"\b(" + "|".join(map(re.escape, sorted(names))) + r")\b")
    return [
        f"{module}:{i}: {line.strip()[:160]}" for i, line in enumerate(text, 1) if pat.search(line)
    ]


def code_between(repo: Repo, src: str, dst: str, cap: int = 30) -> list[str]:
    """Lines in either end's modules that use a name imported from the other end."""
    lines: list[str] = []
    for a_comp, b_comp in ((src, dst), (dst, src)):
        for a in repo.modules_of(a_comp):
            uses = repo.records[a].get("uses", {})
            names = {n for b in repo.modules_of(b_comp) for n in uses.get(b, [])}
            if names:
                lines += lines_using(repo, a, names)
    return lines[:cap]


def claim(repo: Repo, f) -> dict[str, str]:
    return {
        "from": f.src,
        "to": f.dst,
        "artifact": f.artifact,
        "sentence": repo.meaning.relations.get(f.edge, ""),
    }


VERIFY_Q = (
    "Does the code in `code` support the claim in `claim`: that `claim.from` passes "
    "`claim.artifact` to `claim.to` in the way `claim.sentence` describes? `ends` says what "
    "each component is."
)


def verify_pair(repo: Repo, name: str, f, code: list[str], r) -> list[dict]:
    """The flow's own claim, and a claim true of another edge with this edge's ends."""
    others = [g for g in repo.model.flows if g.src == f.src and g.dst != f.dst] or [
        g for g in repo.model.flows if g.edge != f.edge
    ]
    neg = r.choice(others)
    ends = {f.src: component_brief(repo, f.src), f.dst: component_brief(repo, f.dst)}
    swapped = {**claim(repo, neg), "from": f.src, "to": f.dst}
    return [
        row(
            "flowverify",
            name,
            f"{f.src}->{f.dst}:{polarity}",
            {"claim": cl, "ends": ends, "code": code},
            {"holds": noul(VERIFY_Q)},
            {"holds": polarity == "true", "negative_from": f"{neg.src}->{neg.dst}"},
        )
        for polarity, cl in (("true", claim(repo, f)), ("swapped", swapped))
    ]


def flowverify_rows(name: str, per_repo: int = 16) -> list[dict]:
    repo = load(name)
    flows = [
        f
        for f in repo.model.flows
        if repo.comp(f.src).kind != "actor" and repo.comp(f.dst).kind != "actor"
    ]
    r = rng(f"verify-{name}")
    r.shuffle(flows)
    rows: list[dict] = []
    for f in flows:
        code = code_between(repo, f.src, f.dst)
        if code:
            rows += verify_pair(repo, name, f, code, r)
        if len(rows) >= 2 * per_repo:
            break
    return rows


def build_flowverify() -> None:
    write("flowverify", [x for name in REPOS for x in flowverify_rows(name)])


# ---- idea 5: does a crossing import need an edge? -------------------------


def crossing_lines(
    repo: Repo, cap_names: int, skip_edges: bool
) -> dict[tuple[str, str], list[str]]:
    """Every ordered pair of cards one imports from the other, with one line per import."""
    placeable = {c.id for c in repo.placeable()}
    edges = {frozenset(f.edge) for f in repo.model.flows}
    pairs: dict[tuple[str, str], list[str]] = defaultdict(list)
    for m, a in repo.owner.items():
        for b_mod, names in repo.records[m].get("uses", {}).items():
            b = repo.owner.get(b_mod)
            if b is None or a not in placeable or b not in placeable or a == b:
                continue
            if skip_edges and frozenset((a, b)) in edges:
                continue
            pairs[(a, b)].append(f"{m} uses {', '.join(names[:cap_names])} from {b_mod}")
    return pairs


MATTERS_Q: dict[str, Any] = {
    "type": "score",
    "instructions": (
        "Code in `importer` imports code from `imported` (see `imports`). "
        "How much does a reader of the system map need to see an edge between "
        "these two parts?"
    ),
    "criteria": [
        "Incidental: only shared types, base classes, constants or small helpers; "
        "nothing a reader would call an artifact travels and neither part drives the other.",
        "Minor: one part uses the other for a small side task a reader could skip.",
        "Real: one part hands the other an artifact, receives one from it, or drives it; "
        "a reader walking the system needs this edge.",
    ],
}


def crossing_rows(name: str) -> list[dict]:
    repo = load(name)
    edges = {frozenset(f.edge) for f in repo.model.flows}
    pairs = crossing_lines(repo, cap_names=8, skip_edges=False)
    return [
        row(
            "crossing",
            name,
            f"{a}->{b}",
            {
                "importer": {"id": a, "description": component_brief(repo, a)},
                "imported": {"id": b, "description": component_brief(repo, b)},
                "imports": lines[:15],
                "modules_importing": len({ln.split(" uses ")[0] for ln in lines}),
            },
            {"matters": MATTERS_Q},
            {"edge": frozenset((a, b)) in edges, "n_lines": len(lines)},
        )
        for (a, b), lines in sorted(pairs.items())
    ]


def build_crossing() -> None:
    write("crossing", [x for name in REPOS for x in crossing_rows(name)])


# ---- does a recorded answer cover a new judgement line? -------------------


def covers(answer: dict, a: str, b: str) -> bool:
    """Does one bulk crossing answer suppress the line from card a to card b?"""
    if "crossing_into" in answer:
        return answer["crossing_into"] == b
    if "crossing_from" in answer:
        return answer["crossing_from"] == a
    ids = answer["crossing"] if isinstance(answer["crossing"], list) else [answer["crossing"]]
    return a in ids and b in ids


COVERS_Q = (
    "The map draws no edge from `importer` to `imported` although the code "
    "imports across them. Does `recorded_reason` explain why this particular "
    "import needs no edge?"
)


def answerfit_pair(
    repo: Repo, name: str, a: str, b: str, lines: list[str], cov, other
) -> list[dict]:
    return [
        row(
            "answerfit",
            name,
            f"{name}:{a}->{b}:{polarity}",
            {
                "importer": {"id": a, "description": component_brief(repo, a)},
                "imported": {"id": b, "description": component_brief(repo, b)},
                "imports": lines[:10],
                "recorded_reason": answer["reason"],
            },
            {"covers": noul(COVERS_Q)},
            {"covers": polarity == "covering"},
        )
        for polarity, answer in (("covering", cov), ("other", other))
    ]


def answerfit_rows(name: str, per_repo: int = 20) -> list[dict]:
    repo = load(name)
    config = tomllib.loads((repo.root / "systemap.toml").read_text())
    answers = config.get("judgement", {}).get("answered", [])
    fam = [x for x in answers if {"crossing_into", "crossing_from", "crossing"} & set(x)]
    if len(fam) < 2:
        return []
    lines = crossing_lines(repo, cap_names=6, skip_edges=True)
    r = rng(f"answerfit-{name}")
    pairs = sorted(lines)
    r.shuffle(pairs)
    rows: list[dict] = []
    for a, b in pairs:
        cov = [x for x in fam if covers(x, a, b)]
        other = [x for x in fam if not covers(x, a, b)]
        if cov and other:
            rows += answerfit_pair(repo, name, a, b, lines[(a, b)], cov[0], r.choice(other))
        if len(rows) >= 2 * per_repo:
            break
    return rows


def build_answerfit() -> None:
    write("answerfit", [x for name in REPOS for x in answerfit_rows(name)])
