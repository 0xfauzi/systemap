"""The datasets about meaning: a card's sentence against its code, a sentence
against a diff, an issue against the cards, an invariant against the cards,
and a card's kind."""

from __future__ import annotations

import ast
import json
import random
import subprocess
from pathlib import Path
from typing import Any

from common import (
    DATA,
    REPOS,
    SCRATCH,
    SYSTEMAP,
    Repo,
    choice,
    component_brief,
    load,
    module_state,
    noul,
    owner_criteria,
    rng,
    row,
    write,
)

# ---- does this sentence describe these modules? ---------------------------

DESCRIBES_Q = (
    "Does `sentence` accurately describe what the code in `modules` "
    "does, taken together as one part of the system?"
)


def sentence_rows(name: str) -> list[dict]:
    repo = load(name)
    cards = [c for c in repo.placeable() if repo.modules_of(c.id)]
    r = rng(f"sentence-{name}")
    r.shuffle(cards)
    rows = []
    for c in cards[:16]:
        state_mods = [
            module_state(repo, m, doc_cap=300, names_cap=15) for m in repo.modules_of(c.id)[:6]
        ]
        siblings = [d for d in cards if d.id != c.id and d.home == c.home] or [
            d for d in cards if d.id != c.id
        ]
        neg = r.choice(siblings)
        rows += [
            row(
                "sentence",
                name,
                f"{c.id}:{polarity}",
                {"sentence": text, "modules": state_mods},
                {"describes": noul(DESCRIBES_Q)},
                {"describes": polarity == "own", "sibling": neg.id},
            )
            for polarity, text in (("own", c.does), ("sibling", neg.does))
        ]
    return rows


def build_sentence() -> None:
    write("sentence", [x for name in REPOS for x in sentence_rows(name)])


# ---- the PR idea: meaning drift -------------------------------------------

DRIFT_QS = {
    "does_holds": noul(
        "`component.does` was written to describe this component before the change in `diff`. "
        "After the change, does that sentence still accurately describe what the component does?"
    ),
    "interface_holds": noul(
        "`component.interface` was the component's one-line signature before the change in `diff`. "
        "After the change, is it still accurate? If it is empty, answer yes."
    ),
    "change_kind": choice(
        "What did the change in `diff` do to the component described in `component`?",
        {
            "no behaviour change": "Formatting, comments, tests, typing or renames inside the code; the component does exactly what it did.",
            "internal refactor": "The code is restructured but the component's job and its interface are the same.",
            "extends its job": "The component does more of the same kind of thing it already did.",
            "new responsibility": "The component takes on a job its description does not cover.",
            "interface change": "What other parts call on it, or what it returns, changed.",
            "removed responsibility": "The component stops doing something its description says it does.",
        },
    ),
}


def literal_keywords(node: ast.Call) -> dict[str, Any]:
    kw = {}
    for k in node.keywords:
        try:
            kw[k.arg] = ast.literal_eval(k.value)
        except ValueError:
            continue
    return kw


def model_components(src: str) -> dict[str, dict[str, Any]]:
    """Component(...) calls in a model file, by id: the literal keyword values."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return {}
    calls = [
        literal_keywords(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Component"
    ]
    return {
        kw["id"]: {"does": "", "interface": "", "implemented_by": (), **kw}
        for kw in calls
        if "id" in kw
    }


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    ).stdout


def file_module(path: str) -> str | None:
    """The dotted module a .py path holds, with a src/ layout and __init__ folded."""
    if not path.endswith(".py"):
        return None
    return path[:-3].replace("/", ".").removesuffix(".__init__").removeprefix("src.")


def pattern_names(pattern: str, mod: str) -> bool:
    if pattern.endswith(".*"):
        return mod == pattern[:-2] or mod.startswith(pattern[:-1])
    return mod == pattern


def module_files(pattern: str, files: list[str]) -> list[str]:
    """Files a module pattern names, among the tree's .py files."""
    return [f for f in files if (m := file_module(f)) is not None and pattern_names(pattern, m)]


def norm(s: str) -> str:
    return " ".join(str(s).split())


def drift_label(c: dict, after: dict | None, diff: str, cap: int, touched: list[str]) -> dict:
    return {
        "removed": after is None,
        "does_changed": after is None or norm(after["does"]) != norm(c["does"]),
        "interface_changed": after is None
        or norm(after.get("interface", "")) != norm(c.get("interface", "")),
        "diff_chars": len(diff),
        "truncated": len(diff) > cap,
        "files": touched,
    }


def drift_rows(
    root: Path, base: str, head: str, old_model: str, new_model: str, tag: str, cap: int
) -> list[dict]:
    old, new = model_components(old_model), model_components(new_model)
    files = git(root, "ls-tree", "-r", "--name-only", base).split()
    changed = set(git(root, "diff", "--name-only", base, head).split())
    rows = []
    for cid, c in old.items():
        own = sorted({f for p in c["implemented_by"] for f in module_files(p, files)})
        touched = [f for f in own if f in changed]
        if not touched:
            continue
        diff = git(root, "diff", "-U3", base, head, "--", *touched)
        state = {
            "component": {"id": cid, "does": c["does"], "interface": c.get("interface", "")},
            "diff": diff[:cap],
        }
        label = drift_label(c, new.get(cid), diff, cap, touched)
        rows.append(row("drift", tag, f"{tag}:{cid}", state, DRIFT_QS, label))
    return rows


def build_drift(cap: int = 12000) -> None:
    rows = []
    # systemap's own history: every commit that edits the self-map, against its parent
    for c in git(SYSTEMAP, "log", "--format=%H", "--", "map/model.py").split():
        old = git(SYSTEMAP, "show", f"{c}^:map/model.py")
        if old:
            new = git(SYSTEMAP, "show", f"{c}:map/model.py")
            rows += drift_rows(SYSTEMAP, f"{c}^", c, old, new, f"systemap@{c[:7]}", cap)
    # the kstrl maintenance runs: the map as committed, the map as the agent left it
    for d in sorted(SCRATCH.glob("repo-maintenance-*")):
        root = d / "repo"
        old = git(root, "show", "HEAD:map/model.py")
        new = (root / "map/model.py").read_text()
        rows += drift_rows(root, "maint-base", "HEAD", old, new, f"kstrl-maint@{d.name[-6:]}", cap)
    write("drift", rows)


# ---- route a real bug report to the card the fixing PR touched ------------

ISSUE_Q = (
    "`report` is an issue filed against this system. Which component will "
    "the fix most likely have to change?"
)


def issue_text(gh_repo: str, number: int) -> str | None:
    out = subprocess.run(
        ["gh", "issue", "view", str(number), "-R", gh_repo, "--json", "title,body"],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        return None
    body = json.loads(out.stdout)
    return f"{body['title']}\n\n{(body['body'] or '')[:1500]}"


def touched_cards(repo: Repo, pr: dict) -> set[str]:
    placeable = {c.id for c in repo.placeable()}
    comps = {repo.owner.get(file_module(f["path"]) or "") for f in pr["files"]}
    return {c for c in comps if c is not None and c in placeable}


def issue_rows(name: str, gh_repo: str, per_repo: int) -> list[dict]:
    repo = load(name)
    prs = json.loads((DATA / f"raw-prs-{name}.json").read_text())
    rows: list[dict] = []
    for pr in prs:
        comps = touched_cards(repo, pr)
        if not pr["closingIssuesReferences"] or not comps or len(comps) > 3:
            continue
        number = pr["closingIssuesReferences"][0]["number"]
        text = issue_text(gh_repo, number)
        if text is None:
            continue
        state = {"system": name, "report": text}
        questions = {"where": choice(ISSUE_Q, owner_criteria(repo))}
        label = {"owners": sorted(comps), "pr": pr["number"]}
        rows.append(row("issues", name, f"{name}#{number}", state, questions, label))
        if len(rows) >= per_repo:
            break
    return rows


def build_issues(per_repo: int = 40) -> None:
    sources = (("rich", "Textualize/rich"), ("poetry", "python-poetry/poetry"))
    write("issues", [x for name, gh in sources for x in issue_rows(name, gh, per_repo)])


# ---- which cards does an invariant govern? --------------------------------

GOVERNS_Q = (
    "Does `rule` directly govern `component`: is it one of the parts whose "
    "code must keep this rule true, so a change to it could break the rule?"
)


def governs_rows(name: str) -> list[dict]:
    repo = load(name)
    return [
        row(
            "governs",
            name,
            f"{name}:inv{inv.n}:{c.id}",
            {
                "rule": inv.text,
                "component": {"id": c.id, "description": component_brief(repo, c.id)},
            },
            {"governs": noul(GOVERNS_Q)},
            {"governs": c.id in inv.governs},
        )
        for inv in repo.model.invariants
        for c in repo.placeable()
    ]


def build_governs() -> None:
    """Every governed pair, and twice as many ungoverned ones drawn at random."""
    rows = [x for name in REPOS for x in governs_rows(name)]
    pos = [x for x in rows if x["label"]["governs"]]
    neg = [x for x in rows if not x["label"]["governs"]]
    random.Random(1).shuffle(neg)
    write("governs", pos + neg[: 2 * len(pos)])


# ---- card kind ------------------------------------------------------------

CARD_KINDS = {
    "component": "Ordinary code with one job: it computes, transforms, routes or serves.",
    "store": "Where state is kept: a database, a set of files, a cache, a queue at rest.",
    "agent": "Runs a language model and acts on its output, in a loop or with tools.",
    "tool": "A function an agent calls as one of its tools.",
    "context": "Content that enters an agent's context window: a system prompt, a template, a memory, retrieved knowledge.",
}

KIND_Q = "What kind of part of the system are the modules in `modules`, taken together?"


def cardkind_rows(name: str) -> list[dict]:
    repo = load(name)
    rows = []
    for c in repo.placeable():
        mods = repo.modules_of(c.id)[:6]
        if not mods:
            continue
        state = {
            "modules": [module_state(repo, m, doc_cap=300, names_cap=15) for m in mods],
            "third_party_imports": sorted(
                {e for m in mods for e in repo.records[m].get("external", [])}
            )[:30],
        }
        rows.append(
            row(
                "cardkind",
                name,
                f"{name}:{c.id}",
                state,
                {"kind": choice(KIND_Q, CARD_KINDS)},
                {"kind": c.kind},
            )
        )
    return rows


def build_cardkind() -> None:
    write("cardkind", [x for name in REPOS for x in cardkind_rows(name)])
