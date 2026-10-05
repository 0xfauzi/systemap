"""Get Jev's second opinion on semantic map claims.

`systemap judgement` uses names and imports. Audit gives TypeSafe's Jev questions
about owners, component sentences, flow claims, and invariants.
Disagreements print with `jev mis-fold`, `jev owner`, `jev sentence`, `jev flow`,
or `jev governs` identifiers.

Thresholds came from five first maps in bench/scratch, recorded in bench/jev.
Three holdout maps used the same thresholds. All results stayed within 10 points
except flow claims: 54% of incorrect claims found, compared with 66%.
Thus, `jev flow` needs explicit selection with `--kind "jev flow"`.
Language changes to prompts have not been measured again.

Flow questions include source lines naming imports from the other component.
Instance calls can be absent, such as `ledger.record(parts)` after a Ledger
import. That limitation can cause doubt without a source defect.

Completed reports exit 0. A request error can cause exit 1.
Check and judgement do not call Jev. Audit answers use `[judgement] answered`.
Audit reads only answers for its findings; judgement ignores them.
Exact answers must have reviewed-evidence digests. Family answers must have
`policy = true`. Reports count matches outside the reviewed baseline.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from systemap import explain, nest
from systemap.config import AUDIT_KINDS, Answer, Config
from systemap.evidence import owners
from systemap.extract import is_empty_marker
from systemap.jev import Answers, Ask, Jev
from systemap.model import Meaning, Model, module_matches

# ---- thresholds, each with what it measured on the development maps ----------

# P(current card) below this: planted in a neighbouring card, 95% caught;
# 4% of correctly placed modules flagged.
MISFOLD_BELOW = 0.05
# Choice confidence at or above this: 56% of modules get one card, 98% right.
OWNER_AT = 0.9
# P(sentence describes its modules) below this: 67% of wrong sentences caught,
# 1% of right ones flagged.
SENTENCE_BELOW = 0.2
# P(code carries the claim) below this: 66% of wrong claims caught, 2% of
# real ones flagged; on the holdout maps 54% and 4%, so asked only on request.
FLOW_BELOW = 0.2
# P(invariant governs card) at or above this: 31% of governed cards found,
# 1% of the rest suggested.
GOVERNS_AT = 0.8

# The question each line kind comes from: the owner question gives two kinds.
QUESTION_OF = {
    "jev mis-fold": "owner",
    "jev owner": "owner",
    "jev sentence": "sentence",
    "jev flow": "flow",
    "jev governs": "governs",
}
# The kinds asked when none is named: all but the one that missed the holdout bar.
DEFAULT_KINDS = tuple(k for k in QUESTION_OF if k != "jev flow")
KINDS = AUDIT_KINDS
NONE = "none of these"

OWNER_Q = (
    "Which component has the function of `module`? Each option is a system part with "
    "one function. Select the component whose function includes the work of this module."
)
DESCRIBES_Q = (
    "Does `sentence` give the correct function of the code in `modules`, read "
    "together as one system part?"
)
VERIFY_Q = (
    "Does `code` show that `claim.from` sends `claim.artifact` to `claim.to` as "
    "stated in `claim.sentence`? `ends` gives each component's function."
)
GOVERNS_Q = (
    "Does `rule` apply directly to `component`? Must its code obey this rule? Can a "
    "change to its code make the rule incorrect?"
)


@dataclass(frozen=True)
class Line:
    """One finding with its measured details for action or a recorded answer."""

    text: str
    detail: tuple[str, ...] = ()


@dataclass
class Plan:
    """Collect audit questions and the use of each answer."""

    asks: list[Ask] = field(default_factory=list)
    reads: dict[str, Any] = field(default_factory=dict)

    def add(self, key: str, state: Any, questions: dict[str, Any], read: Any) -> None:
        self.asks.append(Ask(key, state, questions))
        self.reads[key] = read


# ---- the state each question reads ------------------------------------------


def module_state(
    facts: dict[str, Any], m: str, doc_cap: int = 600, names_cap: int = 40
) -> dict[str, Any]:
    r = facts["components"][m]
    doc = " ".join((r.get("docstring") or "").split())[:doc_cap]
    names = [f"{n['name']} ({n['kind']})" for n in r.get("names", [])][:names_cap]
    return {
        "module": m,
        "docstring": doc or None,
        "public_names": names,
        "imports": sorted(r.get("imports", []))[:20],
        "imported_by": sorted(r.get("imported_by", []))[:20],
    }


def card_brief(model: Model, meaning: Meaning, cid: str) -> str:
    c = model.component(cid)
    plain = meaning.plain.get(cid, "")
    parts = [f"{plain}." if plain else "", c.does]
    if c.interface:
        parts.append(f"Interface: {c.interface}")
    return " ".join(p for p in parts if p)


def owner_criteria(model: Model, meaning: Meaning) -> dict[str, str]:
    crit = {c.id: card_brief(model, meaning, c.id) for c in model.components if c.kind != "actor"}
    crit[NONE] = "No component on this map has the function of this module."
    return crit


def owner_question(model: Model, meaning: Meaning) -> dict[str, Any]:
    return {"type": "choice", "instructions": OWNER_Q, "criteria": owner_criteria(model, meaning)}


def lines_using(root: Path, facts: dict[str, Any], module: str, names: set[str]) -> list[str]:
    try:
        text = (root / facts["components"][module]["file"]).read_text().splitlines()
    except (FileNotFoundError, UnicodeDecodeError, KeyError):
        return []
    pat = re.compile(r"\b(" + "|".join(map(re.escape, sorted(names))) + r")\b")
    return [f"{module}:{i}: {ln.strip()[:160]}" for i, ln in enumerate(text, 1) if pat.search(ln)]


def _uses_of(root: Path, facts: dict[str, Any], a: str, others: list[str]) -> list[str]:
    uses = facts["components"][a].get("uses", {})
    names = {n for b in others for n in uses.get(b, [])}
    return lines_using(root, facts, a, names) if names else []


def code_between(
    root: Path, facts: dict[str, Any], mods: dict[str, list[str]], src: str, dst: str
) -> list[str]:
    """Get at most 30 lines using an import name from the other component."""
    lines: list[str] = []
    for a_card, b_card in ((src, dst), (dst, src)):
        for a in mods.get(a_card, []):
            lines += _uses_of(root, facts, a, mods.get(b_card, []))
    return lines[:30]


# ---- planning: one Ask per question, keyed so the answers find their way back -


def modules_by_card(model: Model, facts: dict[str, Any]) -> dict[str, list[str]]:
    """Get component module claims, excluding empty markers as in the measured experiments."""
    comps = facts.get("components", {})
    by: dict[str, list[str]] = {}
    for module, cid in sorted(owners(model, facts).items()):
        if not is_empty_marker(comps[module]):
            by.setdefault(cid, []).append(module)
    return by


def unclaimed(model: Model, facts: dict[str, Any], ignores: Iterable[str]) -> list[str]:
    """Get unclaimed modules without a coverage ignore, excluding empty package markers."""
    comps = facts.get("components", {})
    owned = owners(model, facts)
    patterns = list(ignores)
    return [
        m
        for m in sorted(comps)
        if m not in owned
        and not is_empty_marker(comps[m])
        and not any(module_matches(p, m) for p in patterns)
    ]


def plan_owner(
    plan: Plan,
    m: nest.Map,
    facts: dict[str, Any],
    extra: list[str],
    system: str,
    placed_too: bool = True,
) -> None:
    """Add owner questions for claimed modules and `extra` modules.

    `placed_too=False` selects only the unclaimed `extra` modules.
    """
    by = modules_by_card(m.model, facts) if placed_too else {}
    question = {"owner": owner_question(m.model, m.meaning)}
    placed = [(mod, cid) for cid, ms in by.items() for mod in ms]
    placed = [(mod, cid) for mod, cid in placed if m.model.component(cid).kind != "actor"]
    for mod, cid in placed + [(mod, "") for mod in extra]:
        state = {"system": system, "module": module_state(facts, mod)}
        plan.add(f"{m.id}|owner|{mod}", state, question, ("owner", m, mod, cid))


def plan_sentences(plan: Plan, m: nest.Map, facts: dict[str, Any]) -> None:
    by = modules_by_card(m.model, facts)
    for c in m.model.components:
        mods = by.get(c.id, [])[:6]
        if c.kind == "actor" or not mods:
            continue
        state = {
            "sentence": c.does,
            "modules": [module_state(facts, x, doc_cap=300, names_cap=15) for x in mods],
        }
        questions = {"describes": {"type": "noul", "instructions": DESCRIBES_Q}}
        plan.add(f"{m.id}|sentence|{c.id}", state, questions, ("sentence", m, c.id))


def plan_flows(plan: Plan, m: nest.Map, facts: dict[str, Any], root: Path) -> None:
    by = modules_by_card(m.model, facts)
    for f in m.model.flows:
        if "actor" in (m.model.component(f.src).kind, m.model.component(f.dst).kind):
            continue
        code = code_between(root, facts, by, f.src, f.dst)
        if not code:
            continue
        brief = {x: card_brief(m.model, m.meaning, x) for x in (f.src, f.dst)}
        claim = {
            "from": f.src,
            "to": f.dst,
            "artifact": f.artifact,
            "sentence": m.meaning.relations.get(f.edge, ""),
        }
        state = {"claim": claim, "ends": brief, "code": code}
        questions = {"holds": {"type": "noul", "instructions": VERIFY_Q}}
        key = f"{m.id}|flow|{f.src}->{f.dst}:{f.artifact}"
        plan.add(key, state, questions, ("flow", m, f))


def plan_governs(plan: Plan, m: nest.Map) -> None:
    for inv in m.model.invariants:
        for c in m.model.components:
            if c.kind == "actor" or c.id in inv.governs:
                continue
            state = {
                "rule": inv.text,
                "component": {"id": c.id, "description": card_brief(m.model, m.meaning, c.id)},
            }
            questions = {"governs": {"type": "noul", "instructions": GOVERNS_Q}}
            plan.add(f"{m.id}|governs|{inv.n}|{c.id}", state, questions, ("governs", m, inv, c.id))


def make_plan(
    tree: nest.Tree, facts: dict[str, Any], cfg: Config, kinds: Iterable[str] = DEFAULT_KINDS
) -> Plan:
    """Make selected questions for every map.

    The top map also includes unclaimed modules.
    """
    asked = {QUESTION_OF[k] for k in kinds}
    plan = Plan()
    ignores = [i.module for i in cfg.coverage_ignore]
    for m in tree.maps:
        extra = unclaimed(m.model, facts, ignores) if m.top else []
        view = facts if m.top else _view(facts, m)
        if "owner" in asked:
            plan_owner(plan, m, view, extra, cfg.name)
        if "sentence" in asked:
            plan_sentences(plan, m, view)
        if "flow" in asked:
            plan_flows(plan, m, view, cfg.root)
        if "governs" in asked:
            plan_governs(plan, m)
    return plan


def _view(facts: dict[str, Any], m: nest.Map) -> dict[str, Any]:
    """Select facts for the modules claimed by one nested map."""
    own = set(owners(m.model, facts))
    return {**facts, "components": {k: v for k, v in facts["components"].items() if k in own}}


# ---- reading the answers ----------------------------------------------------------


def _top(probs: dict[str, float], n: int) -> list[tuple[str, float]]:
    return sorted(probs.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


def _reads_like(pick: str) -> str:
    return "none of the cards" if pick == NONE else pick


def owner_line(read: tuple[Any, ...], answers: Answers) -> Line | None:
    _, m, mod, cid = read
    a = answers["owner"]
    probs = a.get("probabilities", {})
    detail = ", ".join(f"{k} {v:.2f}" for k, v in _top(probs, 3))
    if cid:
        p = probs.get(cid, 0.0)
        if p >= MISFOLD_BELOW:
            return None
        text = f"jev mis-fold: {cid} claims {mod}, which reads like {_reads_like(a['choice'])}"
        return Line(m.prefix + text, (f"P({cid}) {p:.2f}; most likely: {detail}",))
    if a.get("confidence", 0.0) >= OWNER_AT:
        text = f"jev owner: {mod} is claimed by no card; it reads like {_reads_like(a['choice'])}"
        return Line(m.prefix + text, (f"confidence {a['confidence']:.2f}",))
    closest = ", ".join(k for k, _ in _top(probs, 3))
    text = f"jev owner: {mod} is claimed by no card; closest: {closest}"
    return Line(m.prefix + text, (f"confidence {a.get('confidence', 0.0):.2f}; {detail}",))


def sentence_line(read: tuple[Any, ...], answers: Answers) -> Line | None:
    _, m, cid = read
    p = answers["describes"]["noul"]
    if p >= SENTENCE_BELOW:
        return None
    text = f"jev sentence: {cid}'s sentence may not describe its modules"
    return Line(m.prefix + text, (f"P(describes) {p:.2f}",))


def flow_line(read: tuple[Any, ...], answers: Answers) -> Line | None:
    _, m, f = read
    p = answers["holds"]["noul"]
    if p >= FLOW_BELOW:
        return None
    text = (
        f"jev flow: {f.src} -> {f.dst} ('{f.artifact}'): the code where they meet may not carry it"
    )
    return Line(m.prefix + text, (f"P(carries it) {p:.2f}",))


def governs_line(read: tuple[Any, ...], answers: Answers) -> Line | None:
    _, m, inv, cid = read
    p = answers["governs"]["noul"]
    if p < GOVERNS_AT:
        return None
    text = f"jev governs: invariant {inv.n} may govern {cid}, which it does not name"
    return Line(m.prefix + text, (f"P(governs) {p:.2f}",))


READERS = {
    "owner": owner_line,
    "sentence": sentence_line,
    "flow": flow_line,
    "governs": governs_line,
}


def lines(plan: Plan, answered: dict[str, Answers]) -> list[Line]:
    out = []
    for ask in plan.asks:
        read = plan.reads[ask.key]
        line = READERS[read[0]](read, answered[ask.key])
        if line is not None:
            out.append(line)
    return out


def run(
    tree: nest.Tree,
    facts: dict[str, Any],
    cfg: Config,
    jev: Jev,
    kinds: Iterable[str] = DEFAULT_KINDS,
) -> list[Line]:
    plan = make_plan(tree, facts, cfg, kinds)
    return lines(plan, jev.ask(plan.asks))


# ---- answers, shared with judgement ---------------------------------------------


def _bare(line: str) -> str:
    """Remove a nested-map `<map>: ` prefix from a finding."""
    head, sep, rest = line.partition(": ")
    return rest if sep and rest.startswith("jev ") and not head.startswith("jev ") else line


def is_audit_answer(answer: Answer) -> bool:
    """Determine whether an answer names audit findings."""
    if answer.kind:
        return answer.kind in KINDS
    return bool(answer.items) and all(_bare(i).startswith("jev ") for i in answer.items)


def _covers(answer: Answer, line: str) -> bool:
    if answer.items:
        return line in answer.items
    return _bare(line).startswith(answer.kind + ": ")


def _asked_about(answer: Answer, kinds: Iterable[str]) -> bool:
    """Determine whether the answer names types selected in this run."""
    names = [answer.kind] if answer.kind else [_bare(i).split(": ", 1)[0] for i in answer.items]
    return all(n in kinds for n in names)


def apply(
    found: list[Line], given: Iterable[Answer], kinds: Iterable[str] = DEFAULT_KINDS
) -> tuple[list[Line], int, list[str]]:
    """Get open findings, answered count, and stale answers for selected audit types."""
    kinds = tuple(kinds)
    mine = [a for a in given if is_audit_answer(a) and _asked_about(a, kinds)]
    texts = [x.text for x in found]
    stale = [i for a in mine for i in a.items if i not in texts]
    stale += [a.label for a in mine if a.kind and not any(_covers(a, t) for t in texts)]
    open_lines = [x for x in found if not any(_covers(a, x.text) for a in mine)]
    return open_lines, len(found) - len(open_lines), stale


@dataclass(frozen=True)
class Reviewed:
    """Audit answers after examination of source evidence and standing policies."""

    open: list[Line]
    answered: int
    stale: list[str]
    pending: list[str]
    policies: list[str]


def apply_reviewed(
    found: list[Line],
    given: Iterable[Answer],
    evidence: Mapping[str, str],
    kinds: Iterable[str] = DEFAULT_KINDS,
) -> Reviewed:
    """Open exact answers with changed evidence again. Accept only explicit family policies."""
    kinds = tuple(kinds)
    mine = [a for a in given if is_audit_answer(a) and _asked_about(a, kinds)]
    texts = [x.text for x in found]
    stale = [i for a in mine for i in a.items if i not in texts]
    stale += [a.label for a in mine if a.kind and not any(_covers(a, t) for t in texts)]
    accepted, pending, policies = _reviewed_audit_answers(mine, texts, evidence)
    open_lines = [x for x in found if not any(_covers(a, x.text) for a in accepted)]
    return Reviewed(open_lines, len(found) - len(open_lines), stale, pending, policies)


def _reviewed_audit_answers(
    mine: list[Answer], texts: list[str], evidence: Mapping[str, str]
) -> tuple[list[Answer], list[str], list[str]]:
    accepted: list[Answer] = []
    pending: list[str] = []
    policies: list[str] = []
    for answer in mine:
        matches = [line for line in texts if _covers(answer, line)]
        if not matches:
            continue
        issue = reviewed_answer_issue(answer, evidence)
        if issue is None:
            accepted.append(answer)
            if not answer.items:
                policies.append(_audit_policy_line(answer, matches))
        else:
            pending.append(issue)
    return accepted, pending, policies


def _audit_policy_line(answer: Answer, matches: list[str]) -> str:
    new = sum(line not in answer.reviewed for line in matches)
    return (
        f"{answer.label} covers {len(matches)} current lines; {new} outside its reviewed baseline"
    )


def reviewed_answer_issue(
    answer: Answer,
    evidence: Mapping[str, str],
) -> str | None:
    from systemap.judgement import answer_digest

    if answer.items:
        digest = answer_digest(answer.items, evidence)
        if answer.evidence and answer.evidence == digest and digest != "unavailable":
            return None
        return f"'{answer.label}' needs renewed review; current evidence = \"{digest}\""
    if answer.policy:
        return None
    return f"'{answer.label}' needs policy = true to cover a family of lines"


def report(
    open_lines: list[Line],
    answered: int,
    stale: list[str],
    usage: str,
    teach: bool = True,
    pending: Iterable[str] = (),
    policies: Iterable[str] = (),
) -> list[str]:
    """Give CLI findings and explanations.

    `teach` adds one explanation per finding type. `--brief` removes explanations.
    """
    tail = (f", {answered} answered" if answered else "") + (
        f", {len(stale)} stale" if stale else ""
    )
    if not open_lines:
        head = f"audit: nothing to confirm{tail}"
    else:
        noun = "item" if len(open_lines) == 1 else "items"
        head = f"audit: {len(open_lines)} {noun} for the maintainer to confirm{tail}"
    out = [head, *_taught(open_lines, teach)]
    out += [f"  stale answer: {s}" for s in stale]
    out += [f"  pending answer: {s}" for s in pending]
    out += [f"  policy answer: {s}" for s in policies]
    out.append(usage)
    return out


def _taught(open_lines: list[Line], teach: bool) -> list[str]:
    """Give each finding's details and one explanation per type."""
    out: list[str] = []
    taught: set[str] = set()
    for line in open_lines:
        out.append(f"  {line.text}")
        out += [f"      {d}" for d in line.detail]
        kind = _bare(line.text).split(": ", 1)[0]
        if teach and kind not in taught:
            taught.add(kind)
            out += explain.rows(kind)
    return out


def dry_run(plan: Plan, pending: int | None) -> list[str]:
    """Count planned questions and give the outgoing data fields."""
    kinds: dict[str, int] = {}
    for a in plan.asks:
        kinds[a.key.split("|")[1]] = kinds.get(a.key.split("|")[1], 0) + 1
    chars = sum(a.chars() for a in plan.asks)
    sent = "unknown until a key is set" if pending is None else f"{pending} not in the cache"
    return [
        f"audit --dry-run: {len(plan.asks)} questions ({sent}), {chars:,} characters of state "
        "and questions",
        "  by type: " + ", ".join(f"{k} {n}" for k, n in sorted(kinds.items())),
        "  outgoing data: module names, docstrings (600 characters at most), public "
        "names, internal imports, component ids and sentences, invariants, flow sentences, and "
        "source lines with imports between components (30 lines per flow at most)",
    ]
