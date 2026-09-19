"""Build every labelled dataset. No API calls here; run.py sends them.

    uv run python build.py [experiment ...]

Each row: {exp, repo, id, state, questions, label}. `questions` is in the
API's JSON form so the runner is generic. This file holds the questions
about modules (owner, where, pairs) and flow kinds; build_flows.py holds
the questions about edges and build_meaning.py the ones about sentences,
invariants and history.
"""

from __future__ import annotations

import ast
import sys
from collections import defaultdict

import build_flows
import build_meaning
from common import (
    REPOS,
    Repo,
    choice,
    component_brief,
    first_sentence,
    load,
    module_state,
    noul,
    owner_criteria,
    rng,
    row,
    write,
)

OWNER_Q = (
    "Which component of this system does `module` belong to? Each option is one part of the "
    "system with one job, a part a reader would point at and name. Pick the part whose job "
    "this module carries out."
)


# ---- ideas 1 and 2: which card claims this module -------------------------


def owner_rows(name: str) -> list[dict]:
    repo = load(name)
    placeable = {c.id for c in repo.placeable()}
    mods = sorted(m for m, c in repo.owner.items() if c in placeable)
    r = rng(f"owner-{name}")
    sample = r.sample(mods, min(40, len(mods)))
    multi = sorted(c for c in placeable if len(repo.modules_of(c)) >= 2)
    rows = []
    for m in sample:
        true = repo.owner[m]
        wrong = r.choice([c for c in multi if c != true])
        state = {"system": name, "module": module_state(repo, m)}
        questions = {"owner": choice(OWNER_Q, owner_criteria(repo))}
        rows.append(row("owner", name, m, state, questions, {"owner": true, "wrong": wrong}))
    return rows


def build_owner() -> None:
    write("owner", [x for name in REPOS for x in owner_rows(name)])


# ---- "where does this happen?" from function docstrings -------------------


def docstring_queries(repo: Repo, m: str) -> list[str]:
    path = repo.root / repo.records[m]["file"]
    try:
        tree = ast.parse(path.read_text())
    except (SyntaxError, UnicodeDecodeError, FileNotFoundError):
        return []
    functions = (ast.FunctionDef, ast.AsyncFunctionDef)
    docs = [
        first_sentence(ast.get_docstring(node) or "", 240)
        for node in ast.walk(tree)
        if isinstance(node, functions) and not node.name.startswith("_")
    ]
    return [s for s in docs if len(s.split()) >= 6]


def two_per_card(repo: Repo, pool: list[tuple[str, str]], cap: int = 30) -> list[tuple[str, str]]:
    """At most two queries per card, so one big card does not dominate."""
    per: dict[str, int] = defaultdict(int)
    picked = []
    for m, q in pool:
        c = repo.owner[m]
        if per[c] < 2:
            per[c] += 1
            picked.append((m, q))
        if len(picked) >= cap:
            break
    return picked


WHERE_Q = (
    "A developer asks where, in this system, the thing described in "
    "`question` happens. Which component is it in?"
)


def where_rows(name: str) -> list[dict]:
    repo = load(name)
    placeable = {c.id for c in repo.placeable()}
    pool = [
        (m, q)
        for m, c in sorted(repo.owner.items())
        if c in placeable
        for q in docstring_queries(repo, m)
    ]
    rng(f"where-{name}").shuffle(pool)
    return [
        row(
            "where",
            name,
            f"{name}-{i}",
            {"system": name, "question": q},
            {"where": choice(WHERE_Q, owner_criteria(repo))},
            {"owner": repo.owner[m], "module": m},
        )
        for i, (m, q) in enumerate(two_per_card(repo, pool))
    ]


def build_where() -> None:
    write("where", [x for name in REPOS for x in where_rows(name)])


# ---- do two modules make one part? ----------------------------------------


def package(m: str) -> str:
    return m.rsplit(".", 1)[0]


def sample_pairs(repo: Repo, mods: list[str], seed: str) -> dict[str, list[tuple[str, str]]]:
    """Twenty pairs each: same card, different card in one package, different card and package."""
    r = rng(seed)
    buckets: dict[str, list[tuple[str, str]]] = {"same": [], "hard": [], "easy": []}
    for _ in range(20000):
        a, b = r.sample(mods, 2)
        key = (a, b) if a < b else (b, a)
        if repo.owner[a] == repo.owner[b]:
            tag = "same"
        elif package(a) == package(b):
            tag = "hard"
        else:
            tag = "easy"
        if len(buckets[tag]) < 20 and key not in buckets[tag]:
            buckets[tag].append(key)
        if all(len(b) >= 20 for b in buckets.values()):
            break
    return buckets


SAME_Q = (
    "Do `module_a` and `module_b` belong to the same component of "
    "this system: one part with one job that a reader would point at "
    "and name? Two parts that merely call each other or share types "
    "are two components."
)


def pairs_rows(name: str) -> list[dict]:
    repo = load(name)
    placeable = {c.id for c in repo.placeable()}
    mods = sorted(m for m, c in repo.owner.items() if c in placeable)
    buckets = sample_pairs(repo, mods, f"pairs-{name}")
    return [
        row(
            "pairs",
            name,
            f"{a}|{b}",
            {
                "system": name,
                "module_a": module_state(repo, a, names_cap=25),
                "module_b": module_state(repo, b, names_cap=25),
            },
            {"same": noul(SAME_Q)},
            {"same": repo.owner[a] == repo.owner[b], "tag": tag},
        )
        for tag, bucket in buckets.items()
        for a, b in bucket
    ]


def build_pairs() -> None:
    write("pairs", [x for name in REPOS for x in pairs_rows(name)])


# ---- flow kind ------------------------------------------------------------

KIND_TEXT = {
    "data": "An artifact moves from one part to the other: a file, a record, a message, a response, a request.",
    "control": "One part invokes, schedules or drives the other; what matters is who is in charge, not what travels.",
    "context": "Content that enters an agent's model context window: a prompt, a template, a memory, retrieved knowledge.",
    "tool": "An agent calls a tool: the part at the start runs a model and invokes the other as one of its tools.",
}


def custom_kind_text(repo: Repo, kind: str) -> str:
    layers = {layer.id: layer for layer in repo.meaning.layers}
    layer = layers.get(repo.meaning.layer_of_kind.get(kind, kind))
    if layer is None:
        return kind
    text = layer.question or kind
    return f"{text} ({layer.sub})" if layer.sub else text


def kind_criteria(repo: Repo) -> dict[str, str]:
    used = {f.kind for f in repo.model.flows}
    crit = {k: v for k, v in KIND_TEXT.items() if k in used or k in ("data", "control")}
    for k in repo.model.flow_kinds:
        crit[k] = custom_kind_text(repo, k)
    return crit


def brief_or_actor(repo: Repo, cid: str) -> dict[str, str]:
    c = repo.comp(cid)
    return {"id": cid, "kind": c.kind, "description": component_brief(repo, cid)}


KIND_Q = (
    "The system map draws one edge from `from` to `to`, carrying "
    "`artifact`, described by `sentence`. Which kind of flow is it?"
)


def flowkind_rows(name: str) -> list[dict]:
    repo = load(name)
    flows = list(repo.model.flows)
    rng(f"kind-{name}").shuffle(flows)
    crit = kind_criteria(repo)
    return [
        row(
            "flowkind",
            name,
            f"{f.src}->{f.dst}",
            {
                "from": brief_or_actor(repo, f.src),
                "to": brief_or_actor(repo, f.dst),
                "artifact": f.artifact,
                "sentence": repo.meaning.relations.get(f.edge, ""),
            },
            {"kind": choice(KIND_Q, crit)},
            {"kind": f.kind, "options": sorted(crit)},
        )
        for f in flows[:40]
    ]


def build_flowkind() -> None:
    write("flowkind", [x for name in REPOS for x in flowkind_rows(name)])


BUILDERS = {
    "owner": build_owner,
    "where": build_where,
    "pairs": build_pairs,
    "flowkind": build_flowkind,
    "flowverify": build_flows.build_flowverify,
    "crossing": build_flows.build_crossing,
    "answerfit": build_flows.build_answerfit,
    "sentence": build_meaning.build_sentence,
    "drift": build_meaning.build_drift,
    "issues": build_meaning.build_issues,
    "governs": build_meaning.build_governs,
    "cardkind": build_meaning.build_cardkind,
}

if __name__ == "__main__":
    for w in sys.argv[1:] or BUILDERS:
        BUILDERS[w]()
