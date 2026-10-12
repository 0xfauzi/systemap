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

Flow questions include source lines naming imports from the other component
(`systemap.audit_code`). Instance calls can be absent, such as `ledger.record(parts)`
after a Ledger import. That limitation can cause doubt without a source defect.
A flow without such lines gets no question. The report gives the count of these flows.

The questions and the answers use the provider records in `systemap.decision`.
The Jev values in `decision.JEV` are the thresholds. `systemap.jev_provider` sends
the questions to Jev. A refusal from a provider gives no finding, and the report
gives the count of the questions that got a refusal.

A finding line is an identifier. It does not contain Jev's pick, so a new model
release that changes only the pick does not change the line. The pick is in the
detail row. `migrated` changes a line in the earlier form, which ended with the
pick, to the current form, so that recorded answers continue to match.

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

from systemap import decision, explain, nest
from systemap.audit_code import code_between
from systemap.config import AUDIT_KINDS, Answer, Config
from systemap.decision import (
    ChoiceAnswer,
    ChoiceQuestion,
    DecisionError,
    DecisionProvider,
    PredicateQuestion,
    Question,
    Thresholds,
)
from systemap.evidence import owners
from systemap.extract import is_empty_marker
from systemap.model import Meaning, Model, module_matches

# The thresholds of each provider are in `systemap.decision.THRESHOLDS`.

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

    questions: list[Question] = field(default_factory=list)
    reads: dict[str, Any] = field(default_factory=dict)
    # Flows without a source line that uses a name from the other component.
    unasked: list[str] = field(default_factory=list)

    def add(self, question: Question, read: Any) -> None:
        self.questions.append(question)
        self.reads[question.key] = read


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


# ---- planning: one question for each item, with a key to find its answer -----


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
    options = owner_criteria(m.model, m.meaning)
    placed = [(mod, cid) for cid, ms in by.items() for mod in ms]
    placed = [(mod, cid) for mod, cid in placed if m.model.component(cid).kind != "actor"]
    for mod, cid in placed + [(mod, "") for mod in extra]:
        state = {"system": system, "module": module_state(facts, mod)}
        # A mis-fold reads P(claimed component): an answer without it is refused.
        needs = (cid,) if cid else ()
        key = f"{m.id}|owner|{mod}"
        question = ChoiceQuestion(key, "owner", OWNER_Q, state, options, needs)
        plan.add(question, ("owner", m, mod, cid))


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
        key = f"{m.id}|sentence|{c.id}"
        plan.add(PredicateQuestion(key, "describes", DESCRIBES_Q, state), ("sentence", m, c.id))


def plan_flows(plan: Plan, m: nest.Map, facts: dict[str, Any], root: Path) -> None:
    by = modules_by_card(m.model, facts)
    for f in m.model.flows:
        if "actor" in (m.model.component(f.src).kind, m.model.component(f.dst).kind):
            continue
        code = code_between(root, facts, by, f.src, f.dst)
        if not code:
            plan.unasked.append(f"{f.src} -> {f.dst} ({f.artifact})")
            continue
        brief = {x: card_brief(m.model, m.meaning, x) for x in (f.src, f.dst)}
        claim = {
            "from": f.src,
            "to": f.dst,
            "artifact": f.artifact,
            "sentence": m.meaning.relations.get(f.edge, ""),
        }
        state = {"claim": claim, "ends": brief, "code": code}
        key = f"{m.id}|flow|{f.src}->{f.dst}:{f.artifact}"
        plan.add(PredicateQuestion(key, "holds", VERIFY_Q, state), ("flow", m, f))


def plan_governs(plan: Plan, m: nest.Map) -> None:
    for inv in m.model.invariants:
        for c in m.model.components:
            if c.kind == "actor" or c.id in inv.governs:
                continue
            state = {
                "rule": inv.text,
                "component": {"id": c.id, "description": card_brief(m.model, m.meaning, c.id)},
            }
            key = f"{m.id}|governs|{inv.n}|{c.id}"
            question = PredicateQuestion(key, "governs", GOVERNS_Q, state)
            plan.add(question, ("governs", m, inv, c.id))


def make_plan(
    tree: nest.Tree, facts: dict[str, Any], cfg: Config, kinds: Iterable[str] = DEFAULT_KINDS
) -> Plan:
    """Make selected questions for every map.

    The top map also includes unclaimed modules.
    """
    kinds = tuple(kinds)
    asked = {QUESTION_OF[k] for k in kinds}
    plan = Plan()
    ignores = [i.module for i in cfg.coverage_ignore]
    for m in tree.maps:
        extra = _owner_extra(m, facts, ignores, kinds)
        view = facts if m.top else _view(facts, m)
        if "owner" in asked:
            plan_owner(plan, m, view, extra, cfg.name, placed_too="jev mis-fold" in kinds)
        if "sentence" in asked:
            plan_sentences(plan, m, view)
        if "flow" in asked:
            plan_flows(plan, m, view, cfg.root)
        if "governs" in asked:
            plan_governs(plan, m)
    return plan


def _owner_extra(
    m: nest.Map, facts: dict[str, Any], ignores: list[str], kinds: tuple[str, ...]
) -> list[str]:
    """Give the unclaimed modules for the owner question: top map, `jev owner` only."""
    if not m.top or "jev owner" not in kinds:
        return []
    return unclaimed(m.model, facts, ignores)


def _view(facts: dict[str, Any], m: nest.Map) -> dict[str, Any]:
    """Select facts for the modules claimed by one nested map."""
    own = set(owners(m.model, facts))
    return {**facts, "components": {k: v for k, v in facts["components"].items() if k in own}}


# ---- reading the answers ----------------------------------------------------------


def _top(probs: dict[str, float], n: int) -> list[tuple[str, float]]:
    return sorted(probs.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


def _reads_like(pick: str) -> str:
    return "none of the cards" if pick == NONE else pick


def owner_line(read: tuple[Any, ...], answer: decision.Answer, limits: Thresholds) -> Line | None:
    """Give a mis-fold line or an owner line. A refusal gives no line."""
    _, m, mod, cid = read
    a = decision.choice(answer, f"{m.id}|owner|{mod}")
    if a is None:
        return None
    if cid:
        return _misfold_line(m, mod, cid, a, limits)
    text = f"jev owner: {mod} is claimed by no card"
    pick = f"reads like {_reads_like(a.choice)}"
    sure = "no confidence" if a.confidence is None else f"confidence {a.confidence:.2f}"
    if a.confidence is not None and a.confidence >= limits.owner_at:
        return Line(m.prefix + text, (f"{pick}; {sure}",))
    detail = ", ".join(f"{k} {v:.2f}" for k, v in _top(a.probabilities, 3))
    closest = ", ".join(k for k, _ in _top(a.probabilities, 3))
    return Line(m.prefix + text, (f"closest: {closest}; {sure}; {detail}",))


def _misfold_line(
    m: nest.Map, mod: str, cid: str, a: ChoiceAnswer, limits: Thresholds
) -> Line | None:
    probs = a.probabilities
    if cid not in probs:
        raise DecisionError(f"the answer gives no probability for {cid}, the component of {mod}")
    p = probs[cid]
    if p >= limits.misfold_below:
        return None
    text = f"jev mis-fold: {cid} claims {mod}"
    detail = ", ".join(f"{k} {v:.2f}" for k, v in _top(probs, 3))
    pick = f"reads like {_reads_like(a.choice)}"
    return Line(m.prefix + text, (f"{pick}; P({cid}) {p:.2f}; most likely: {detail}",))


def sentence_line(
    read: tuple[Any, ...], answer: decision.Answer, limits: Thresholds
) -> Line | None:
    _, m, cid = read
    p = decision.probability(answer, f"{m.id}|sentence|{cid}")
    if p is None or p >= limits.sentence_below:
        return None
    text = f"jev sentence: {cid}'s sentence may not describe its modules"
    return Line(m.prefix + text, (f"P(describes) {p:.2f}",))


def flow_line(read: tuple[Any, ...], answer: decision.Answer, limits: Thresholds) -> Line | None:
    _, m, f = read
    p = decision.probability(answer, f"{m.id}|flow|{f.src}->{f.dst}:{f.artifact}")
    if p is None or p >= limits.flow_below:
        return None
    text = (
        f"jev flow: {f.src} -> {f.dst} ('{f.artifact}'): the code where they meet may not carry it"
    )
    return Line(m.prefix + text, (f"P(carries it) {p:.2f}",))


def governs_line(read: tuple[Any, ...], answer: decision.Answer, limits: Thresholds) -> Line | None:
    _, m, inv, cid = read
    p = decision.probability(answer, f"{m.id}|governs|{inv.n}|{cid}")
    if p is None or p < limits.governs_at:
        return None
    text = f"jev governs: invariant {inv.n} may govern {cid}, which it does not name"
    return Line(m.prefix + text, (f"P(governs) {p:.2f}",))


READERS = {
    "owner": owner_line,
    "sentence": sentence_line,
    "flow": flow_line,
    "governs": governs_line,
}


def lines(plan: Plan, answers: list[decision.Answer], limits: Thresholds) -> list[Line]:
    """Give the findings. `answers` has one answer for each question, in the same order."""
    out = []
    for question, answer in zip(plan.questions, answers, strict=True):
        read = plan.reads[question.key]
        line = READERS[read[0]](read, answer, limits)
        if line is not None:
            out.append(line)
    return out


def run(
    tree: nest.Tree,
    facts: dict[str, Any],
    cfg: Config,
    provider: DecisionProvider,
    kinds: Iterable[str] = DEFAULT_KINDS,
) -> list[Line]:
    plan = make_plan(tree, facts, cfg, kinds)
    return lines(plan, provider.decide(plan.questions), decision.thresholds(provider.name))


# ---- answers, shared with judgement ---------------------------------------------


# The earlier form of the mis-fold and owner lines ended with Jev's pick.
_EARLIER = re.compile(
    r"^(?P<line>(?:\S+: )?jev (?:mis-fold: \S+ claims \S+|owner: \S+ is claimed by no card))"
    r"(?:, which reads like .+|; it reads like .+|; closest: .+)$"
)


def migrated(line: str) -> str:
    """Change a line in the earlier form, with Jev's pick at the end, to the current form."""
    found = _EARLIER.match(line)
    return found["line"] if found else line


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
        return any(migrated(item) == line for item in answer.items)
    return _bare(line).startswith(answer.kind + ": ")


def _stale(mine: list[Answer], texts: list[str]) -> list[str]:
    """Give the configured items and kinds that match no current line."""
    stale = [i for a in mine for i in a.items if migrated(i) not in texts]
    return stale + [a.label for a in mine if a.kind and not any(_covers(a, t) for t in texts)]


def _with_earlier_lines(evidence: Mapping[str, str], mine: list[Answer]) -> dict[str, str]:
    """Give each item in the earlier form the evidence of its current line.

    A digest of a group of items was recorded over the configured item text.
    """
    out = dict(evidence)
    for item in (i for a in mine for i in a.items):
        if migrated(item) in evidence:
            out.setdefault(item, evidence[migrated(item)])
    return out


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
    open_lines = [x for x in found if not any(_covers(a, x.text) for a in mine)]
    return open_lines, len(found) - len(open_lines), _stale(mine, texts)


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
    accepted, pending, policies = _reviewed_audit_answers(
        mine, texts, _with_earlier_lines(evidence, mine)
    )
    open_lines = [x for x in found if not any(_covers(a, x.text) for a in accepted)]
    stale = _stale(mine, texts)
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
    reviewed = {migrated(line) for line in answer.reviewed}
    new = sum(line not in reviewed for line in matches)
    return (
        f"{answer.label} covers {len(matches)} lines at this snapshot. {new} lines are "
        f"outside the source-review baseline."
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
        return (
            f"'{answer.label}' must have a new source review. The evidence digest is \"{digest}\""
        )
    if answer.policy:
        return None
    return f"'{answer.label}' must have policy = true for a family of lines."


def report(
    open_lines: list[Line],
    answered: int,
    stale: list[str],
    usage: str,
    teach: bool = True,
    pending: Iterable[str] = (),
    policies: Iterable[str] = (),
    unasked: Iterable[str] = (),
    refused: Iterable[str] = (),
) -> list[str]:
    """Give CLI findings and explanations.

    `teach` adds one explanation per finding type. `--brief` removes explanations.
    `unasked` gives the flows without source lines for a `jev flow` question.
    `refused` gives the keys of the questions that got a refusal.
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
    out += unasked_lines(list(unasked))
    out += refused_lines(list(refused))
    out.append(usage)
    return out


def refused_lines(refused: list[str]) -> list[str]:
    """Give the count of questions that got a refusal, and the first five keys."""
    if not refused:
        return []
    more = f", and {len(refused) - 5} more" if len(refused) > 5 else ""
    return [
        f"  no answer: the decision provider gave a refusal for {len(refused)} questions: "
        f"{', '.join(refused[:5])}{more}"
    ]


def unasked_lines(unasked: list[str]) -> list[str]:
    """Give the count of flows that got no `jev flow` question, and the first five."""
    if not unasked:
        return []
    noun = "flow has" if len(unasked) == 1 else "flows have"
    more = f", and {len(unasked) - 5} more" if len(unasked) > 5 else ""
    return [
        f"  not asked: {len(unasked)} {noun} no source line that uses a name from the "
        f"other component: {', '.join(unasked[:5])}{more}"
    ]


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


def _sent(pending: int | str | None) -> str:
    if pending is None:
        return "unknown until a key is set"
    if isinstance(pending, str):
        return pending
    return f"{pending} not in the cache"


def dry_run(plan: Plan, pending: int | str | None, chars: int) -> list[str]:
    """Count planned questions and give the outgoing data fields.

    `pending` is the count without cached answers, None without a key, or the reason
    that the count is not known. `chars` is the count of characters that the provider
    sends: the provider adapter counts them.
    """
    kinds: dict[str, int] = {}
    for a in plan.questions:
        kinds[a.key.split("|")[1]] = kinds.get(a.key.split("|")[1], 0) + 1
    sent = _sent(pending)
    return [
        f"audit --dry-run: {len(plan.questions)} questions ({sent}), {chars:,} characters of state "
        "and questions",
        "  by type: " + ", ".join(f"{k} {n}" for k, n in sorted(kinds.items())),
        "  outgoing data: module names, docstrings, public names, internal imports, component "
        "ids and sentences, invariants, flow sentences, and source lines with imports between "
        "components. A docstring has 600 characters at most. A flow has 30 source lines at most.",
        *unasked_lines(plan.unasked),
    ]
