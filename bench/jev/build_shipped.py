"""Make two question sets on the same rows: the measured questions and the shipped questions.

    JEV_SET=holdout uv run --project bench/jev python bench/jev/build_shipped.py [kind ...]

The kinds are owner, sentence, flowverify, governs, and issues. This script does not call Jev.

The old set is the rows that build.py, build_flows.py, and build_meaning.py make, with no
change. This script writes them to data/<set>/<kind>_old.jsonl. The shipped set,
data/<set>/<kind>_shipped.jsonl, has the same row ids, items, and labels. Its state and
questions come from the shipped systemap code for that kind: audit.make_plan for owner,
sentence, and flowverify, audit.plan_governs for governs, and the triage values in jev_cli
for issues. This script does not copy question text.

The two sets have new file names. Thus run.py does not use the recorded answers in
results/<set>/<kind>.jsonl.gz, which came from earlier maps.

Each shipped row also has `needs`: the options that the shipped answer check must find
in the probabilities (jev.Ask.needs). run.py does not send it.

Before it writes a kind, the script does a check on each shipped question. Each name in
backticks must be in the state, each needed option must be an option, and the shipped
answer check (jev.checked) must accept a correct answer. If a question fails, the script
shows the problem and stops without a write.
"""

from __future__ import annotations

import dataclasses
import re
import statistics
import subprocess
import sys
from collections import Counter
from collections.abc import Callable
from typing import Any

import build
import build_flows
import build_meaning
from common import REPOS, load, write

from systemap import audit, jev, jev_cli, nest

Notes = Counter[str]
Rows = list[dict[str, Any]]


def top_map(name: str) -> nest.Map:
    return nest.load(load(name).cfg).top


def plan_asks(name: str, kinds: tuple[str, ...]) -> dict[str, jev.Ask]:
    """The shipped audit requests for one repository, by request key."""
    repo = load(name)
    plan = audit.make_plan(nest.load(repo.cfg), repo.facts, repo.cfg, kinds)
    return {a.key: a for a in plan.asks}


def governs_asks(name: str) -> dict[str, jev.Ask]:
    """The shipped governs requests for every invariant and component pair.

    The shipped audit does not ask about a pair that `governs` already lists. This
    function removes the `governs` lists from a copy of the top map, so that
    audit.plan_governs makes the same request for the listed pairs too.
    """
    top = top_map(name)
    invariants = tuple(dataclasses.replace(i, governs=()) for i in top.model.invariants)
    model = dataclasses.replace(top.model, invariants=invariants)
    plan = audit.Plan()
    audit.plan_governs(plan, dataclasses.replace(top, model=model))
    return {a.key: a for a in plan.asks}


def triage_ask(name: str, report: str) -> jev.Ask:
    """The request that `systemap triage` sends for one report.

    jev_cli.cmd_triage makes this state and question in its body, not in a function.
    This function makes the same structure from the shipped values.
    """
    top = top_map(name)
    state = {"system": load(name).cfg.name, "report": report[: jev_cli.REPORT_CAP]}
    criteria = audit.owner_criteria(top.model, top.meaning)
    question = {"type": "choice", "instructions": jev_cli.TRIAGE_Q, "criteria": criteria}
    return jev.Ask("triage", state, {"where": question})


def shipped_row(old: dict[str, Any], ask: jev.Ask, state: Any = None) -> dict[str, Any]:
    new_state = ask.state if state is None else state
    return {**old, "state": new_state, "questions": ask.questions, "needs": list(ask.needs)}


def note_differences(old: dict[str, Any], new: dict[str, Any], notes: Notes) -> None:
    for key in sorted(set(old["state"]) | set(new["state"])):
        if old["state"].get(key) != new["state"].get(key):
            notes[f"state `{key}` is different from the old row"] += 1


def by_repo(rows: Rows, make: Callable[[str], dict[str, jev.Ask]]) -> dict[str, dict]:
    return {name: make(name) for name in sorted({r["repo"] for r in rows})}


# ---- one function for each kind: the old rows in, the shipped rows out --------------


def owner_shipped(old_rows: Rows, notes: Notes) -> Rows:
    asks = by_repo(old_rows, lambda n: plan_asks(n, ("jev mis-fold",)))
    out = []
    for r in old_rows:
        ask = asks[r["repo"]].get(f"{top_map(r['repo']).id}|owner|{r['id']}")
        if ask is None:
            notes["left out: the shipped audit does not ask about this module"] += 1
            continue
        if ask.needs != (r["label"]["owner"],):
            notes["the shipped claimed component is not the label"] += 1
        new = shipped_row(r, ask)
        note_differences(r, new, notes)
        out.append(new)
    return out


def sentence_shipped(old_rows: Rows, notes: Notes) -> Rows:
    """The shipped state with the sentence of the old row: own or of a sibling."""
    asks = by_repo(old_rows, lambda n: plan_asks(n, ("jev sentence",)))
    out = []
    for r in old_rows:
        cid = r["id"].rsplit(":", 1)[0]
        ask = asks[r["repo"]].get(f"{top_map(r['repo']).id}|sentence|{cid}")
        if ask is None:
            notes["left out: the shipped audit does not ask about this component"] += 1
            continue
        if r["label"]["describes"] and ask.state["sentence"] != r["state"]["sentence"]:
            notes["the shipped sentence is not the sentence of the old row"] += 1
        new = shipped_row(r, ask, {**ask.state, "sentence": r["state"]["sentence"]})
        note_differences(r, new, notes)
        out.append(new)
    return out


def flowverify_shipped(old_rows: Rows, notes: Notes) -> Rows:
    """The shipped state with the claim of the old row: own or of a different flow."""
    asks = by_repo(old_rows, lambda n: plan_asks(n, ("jev flow",)))
    artifact = {
        r["id"].rsplit(":", 1)[0]: r["state"]["claim"]["artifact"]
        for r in old_rows
        if r["label"]["holds"]
    }
    if len({r["id"] for r in old_rows}) != len(old_rows):
        notes["two old rows have the same id"] += 1
    out = []
    for r in old_rows:
        edge = r["id"].rsplit(":", 1)[0]
        ask = asks[r["repo"]].get(f"{top_map(r['repo']).id}|flow|{edge}:{artifact[edge]}")
        if ask is None:
            notes["left out: the shipped audit finds no source line for this flow"] += 1
            continue
        if r["label"]["holds"] and ask.state["claim"] != r["state"]["claim"]:
            notes["the shipped claim is not the claim of the old row"] += 1
        new = shipped_row(r, ask, {**ask.state, "claim": r["state"]["claim"]})
        note_differences(r, new, notes)
        out.append(new)
    return out


def governs_shipped(old_rows: Rows, notes: Notes) -> Rows:
    asks = by_repo(old_rows, governs_asks)
    out = []
    for r in old_rows:
        _, inv, cid = r["id"].split(":", 2)
        key = f"{top_map(r['repo']).id}|governs|{inv.removeprefix('inv')}|{cid}"
        ask = asks[r["repo"]].get(key)
        if ask is None:
            notes["left out: the shipped audit does not ask about this pair"] += 1
            continue
        if r["label"]["governs"]:
            notes["listed pair: the shipped audit does not ask it (same question form)"] += 1
        new = shipped_row(r, ask)
        note_differences(r, new, notes)
        out.append(new)
    return out


def issues_shipped(old_rows: Rows, notes: Notes) -> Rows:
    out = []
    for r in old_rows:
        new = shipped_row(r, triage_ask(r["repo"], r["state"]["report"]))
        note_differences(r, new, notes)
        out.append(new)
    return out


OLD: dict[str, Callable[[], Rows]] = {
    "owner": lambda: [x for name in REPOS for x in build.owner_rows(name)],
    "sentence": lambda: [x for name in REPOS for x in build_meaning.sentence_rows(name)],
    "flowverify": lambda: [x for name in REPOS for x in build_flows.flowverify_rows(name)],
    "governs": build_meaning.governs_selected,
    "issues": build_meaning.issues_selected,
}
SHIPPED: dict[str, Callable[[Rows, Notes], Rows]] = {
    "owner": owner_shipped,
    "sentence": sentence_shipped,
    "flowverify": flowverify_shipped,
    "governs": governs_shipped,
    "issues": issues_shipped,
}


# ---- the question checks ------------------------------------------------------------

REF = re.compile(r"`([^`]+)`")


def resolves(state: Any, path: str) -> bool:
    for part in path.split("."):
        if not isinstance(state, dict) or part not in state:
            return False
        state = state[part]
    return True


def question_problems(name: str, q: dict[str, Any], state: Any, needs: list[str]) -> list[str]:
    if q.get("type") not in ("noul", "choice"):
        return [f"{name}: the type is not noul or choice"]
    text = q.get("instructions")
    if not isinstance(text, str) or not text.strip():
        return [f"{name}: the question has no instructions"]
    refs = REF.findall(text)
    out = [f"{name}: `{ref}` is not in the state" for ref in refs if not resolves(state, ref)]
    if q["type"] == "choice":
        crit = q.get("criteria")
        if not isinstance(crit, dict) or not crit:
            return [*out, f"{name}: the question has no options"]
        out += [f"{name}: option {k} has no text" for k, v in crit.items() if not str(v).strip()]
        out += [f"{name}: the needed option {n} is not an option" for n in needs if n not in crit]
    return out


def correct_answer(q: dict[str, Any]) -> dict[str, Any]:
    if q["type"] == "noul":
        return {"type": "noul", "noul": 0.5}
    options = list(q["criteria"])
    spread = {o: 1 / len(options) for o in options}
    return {"type": "choice", "choice": options[0], "confidence": 0.5, "probabilities": spread}


def check_problems(row: dict[str, Any]) -> list[str]:
    """Why the shipped code cannot use the row as a request, or an empty list."""
    needs = row.get("needs", [])
    out = [
        p for n, q in row["questions"].items() for p in question_problems(n, q, row["state"], needs)
    ]
    if out:
        return out
    ask = jev.Ask(row["id"], row["state"], row["questions"], tuple(needs))
    answers = {n: correct_answer(q) for n, q in row["questions"].items()}
    try:
        jev.checked(ask, answers)
    except jev.JevError as exc:
        return [f"the shipped answer check refuses a correct answer: {exc}"]
    return []


# ---- the build ----------------------------------------------------------------------


def chars(row: dict[str, Any]) -> int:
    return jev.Ask(row["id"], row["state"], row["questions"]).chars()


def count_line(kind: str, arm: str, rows: Rows) -> str:
    repos = dict(sorted(Counter(r["repo"] for r in rows).items()))
    median = statistics.median(chars(r) for r in rows) if rows else 0
    return f"  {kind:<10} {arm:<8} {len(rows):>4} questions {repos}, median input {median:.0f} characters"


def old_rows(kind: str) -> Rows:
    try:
        return OLD[kind]()
    except subprocess.CalledProcessError as exc:
        command = " ".join(str(c) for c in exc.cmd[:4])
        detail = (exc.stderr or "").strip()[:400]
        raise SystemExit(
            f"{kind}: `{command}` stopped with exit {exc.returncode}: {detail}"
        ) from exc


def build_kind(kind: str) -> None:
    notes: Notes = Counter()
    old = old_rows(kind)
    shipped = SHIPPED[kind](old, notes)
    problems = {r["id"]: p for r in shipped if (p := check_problems(r))}
    if problems:
        for rid, p in list(problems.items())[:5]:
            print(f"  {kind} {rid}: {'; '.join(p)}")
        raise SystemExit(
            f"{kind}: {len(problems)} shipped questions fail the checks. The script writes no file."
        )
    write(f"{kind}_old", old)
    write(f"{kind}_shipped", shipped)
    print(count_line(kind, "old", old))
    print(count_line(kind, "shipped", shipped))
    print(f"  {kind}: all {len(shipped)} shipped questions pass the question and answer checks")
    for note, n in sorted(notes.items()):
        print(f"  {kind}: {note}: {n}")


if __name__ == "__main__":
    for kind in sys.argv[1:] or OLD:
        build_kind(kind)
