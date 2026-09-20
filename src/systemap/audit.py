"""`systemap audit`: a second opinion from Jev on the calls the map makes.

`systemap judgement` finds what to look at with rules that read names and
imports. This asks TypeSafe's Jev model about meaning, one narrow question
at a time, and prints a line where its answer disagrees with the map:

    jev mis-fold ... a module whose card Jev finds unlikely: the map may
                     have folded it into the wrong part
    jev owner ...... a module no card claims, and the card it reads like
    jev sentence ... a card whose sentence may not describe its modules
    jev flow ....... a flow the code where its two cards meet may not carry
    jev governs .... an invariant that may govern a card it does not name

Each threshold below was chosen on the five first maps in bench/scratch and
is quoted with what it measured there (bench/jev, results/report.txt). The
questions and the state they read are the ones measured; change either and
the numbers no longer hold. Each was then checked on three maps no threshold
was chosen on (JEV_SET=holdout): every kind held within 10 points but `jev
flow`, which caught 54% of wrong flows there against 66%, so it is asked
only on request (`--kind "jev flow"`).

A known limit, measured with it: a flow's evidence is the lines in either
card's modules that name something imported from the other, so a call made
through an instance (`ledger.record(parts)` after `from pkg.ledger import
Ledger`) is not shown to Jev, and the flow can be doubted for that alone.

It is a report, never a gate: the command exits 0 whatever it prints, and
`check` and `judgement` never call it, so CI stays offline and the same
every run. A line is answered like a judgement line, in `[judgement]
answered` (an exact `item`, or `kind = "jev flow"` for a family); audit
reads only the answers that name its own lines, and judgement ignores them.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
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
    "Which component of this system does `module` belong to? Each option is one part of the "
    "system with one job, a part a reader would point at and name. Pick the part whose job "
    "this module carries out."
)
DESCRIBES_Q = (
    "Does `sentence` accurately describe what the code in `modules` "
    "does, taken together as one part of the system?"
)
VERIFY_Q = (
    "Does the code in `code` support the claim in `claim`: that `claim.from` passes "
    "`claim.artifact` to `claim.to` in the way `claim.sentence` describes? `ends` says what "
    "each component is."
)
GOVERNS_Q = (
    "Does `rule` directly govern `component`: is it one of the parts whose "
    "code must keep this rule true, so a change to it could break the rule?"
)


@dataclass(frozen=True)
class Line:
    """One line to act on or answer, and the numbers behind it, printed under it."""

    text: str
    detail: tuple[str, ...] = ()


@dataclass
class Plan:
    """Every question one audit asks, and what each answer is for."""

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
    crit[NONE] = "No component on this map carries out what this module does."
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
    """Lines in either end's modules that use a name imported from the other end, 30 at most."""
    lines: list[str] = []
    for a_card, b_card in ((src, dst), (dst, src)):
        for a in mods.get(a_card, []):
            lines += _uses_of(root, facts, a, mods.get(b_card, []))
    return lines[:30]


# ---- planning: one Ask per question, keyed so the answers find their way back -


def modules_by_card(model: Model, facts: dict[str, Any]) -> dict[str, list[str]]:
    """The modules each card claims, empty package markers left out, as the measurements did."""
    comps = facts.get("components", {})
    by: dict[str, list[str]] = {}
    for module, cid in sorted(owners(model, facts).items()):
        if not is_empty_marker(comps[module]):
            by.setdefault(cid, []).append(module)
    return by


def unclaimed(model: Model, facts: dict[str, Any], ignores: Iterable[str]) -> list[str]:
    """Modules no card claims, left out of coverage by no ignore and no empty marker."""
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
    """One owner question per claimed module (the mis-fold check) and per module in
    `extra` (no card claims it); `placed_too=False` asks about `extra` alone."""
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
    """The questions behind `kinds`, for every map: the top map also asks about the
    modules no card claims."""
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
    """The facts a sub-map reads: only the modules its cards claim."""
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
    """A line without a sub-map's `<map>: ` in front."""
    head, sep, rest = line.partition(": ")
    return rest if sep and rest.startswith("jev ") and not head.startswith("jev ") else line


def is_audit_answer(answer: Answer) -> bool:
    """Does this answer name audit lines rather than judgement lines?"""
    if answer.kind:
        return answer.kind in KINDS
    return bool(answer.items) and all(_bare(i).startswith("jev ") for i in answer.items)


def _covers(answer: Answer, line: str) -> bool:
    if answer.items:
        return line in answer.items
    return _bare(line).startswith(answer.kind + ": ")


def _asked_about(answer: Answer, kinds: Iterable[str]) -> bool:
    """Does this answer name a kind this run asked? Others cannot be judged stale."""
    names = [answer.kind] if answer.kind else [_bare(i).split(": ", 1)[0] for i in answer.items]
    return all(n in kinds for n in names)


def apply(
    found: list[Line], given: Iterable[Answer], kinds: Iterable[str] = DEFAULT_KINDS
) -> tuple[list[Line], int, list[str]]:
    """(open lines, how many answered, stale answers), reading only the audit answers
    about the kinds this run asked."""
    kinds = tuple(kinds)
    mine = [a for a in given if is_audit_answer(a) and _asked_about(a, kinds)]
    texts = [x.text for x in found]
    stale = [i for a in mine for i in a.items if i not in texts]
    stale += [a.label for a in mine if a.kind and not any(_covers(a, t) for t in texts)]
    open_lines = [x for x in found if not any(_covers(a, x.text) for a in mine)]
    return open_lines, len(found) - len(open_lines), stale


def report(
    open_lines: list[Line],
    answered: int,
    stale: list[str],
    usage: str,
    teach: bool = True,
) -> list[str]:
    """The lines the CLI prints. `teach` says why each kind matters and what
    to do, once under the first line of that kind; `--brief` turns it off."""
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
    out.append(usage)
    return out


def _taught(open_lines: list[Line], teach: bool) -> list[str]:
    """Each line with what it stands for, and its kind taught once."""
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
    """What an audit would send, and what leaves the machine."""
    kinds: dict[str, int] = {}
    for a in plan.asks:
        kinds[a.key.split("|")[1]] = kinds.get(a.key.split("|")[1], 0) + 1
    chars = sum(a.chars() for a in plan.asks)
    sent = "unknown until a key is set" if pending is None else f"{pending} not in the cache"
    return [
        f"audit --dry-run: {len(plan.asks)} questions ({sent}), {chars:,} characters of state "
        "and questions",
        "  by kind: " + ", ".join(f"{k} {n}" for k, n in sorted(kinds.items())),
        "  what leaves this machine: module names, docstrings (600 characters at most), public "
        "names, internal imports, card ids and sentences, invariants, flow sentences, and the "
        "source lines where two cards' modules use each other (30 lines per flow at most)",
    ]
