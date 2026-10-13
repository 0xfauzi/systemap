"""Ask the decision provider about a delta, and print its answers as suggestions.

The provider gets two types of questions:

- Which new module did a removed module become? Delta asks only about removed modules
  that its own rules left unpaired. A pick at confidence MOVE_AT or more prints as
  a `decision move` line.
- Which component has the function of a module that no component claims? Delta takes
  these modules from the `module` field of its lines. An answer prints as a
  `decision owner` line.

A provider answer is a suggestion for source examination, not evidence. It does not
change the delta lines or the exit code. Thus a run with a provider, a run without
a key, and a run where the provider does not answer give the same result.
The printed text names the provider that gave the answers (`decision.label`).
If there is no question, no client is made and no message prints.

The questions and the answers use the provider records in `systemap.decision`.
`systemap.providers` selects the provider: Jev by default, or OpenAI when the user
selects it. A question type without a measured value for the provider is not sent,
and the report gives the reason. A refusal gives no suggestion, and the report gives
the count of the questions that got a refusal.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from systemap import (
    audit,
    decision,
    decision_kinds,
    explain,
    jev,
    moves,
    nest,
    providers,
    source_facts,
)
from systemap.config import Config
from systemap.decision import ChoiceQuestion, DecisionError, DecisionProvider, Thresholds
from systemap.delta import Delta

BECAME_Q = (
    "The commit removed `old_module` and added the option modules. Which "
    "new module is the removed module after a move, rename, or edit? If no option "
    "continues the removed module, select the deleted option."
)
NOT_MOVED = "not moved: deleted"
# How many new modules the question offers: the measured cap.
MOVE_OPTIONS = 250
# The confidence of a printed pick is `move_at` in `systemap.decision.THRESHOLDS`.
LABEL = "delta --decide"


@dataclass(frozen=True)
class Asked:
    """The provider suggestions for one delta, and the reasons for absent answers.

    `provider` is the name of the provider that gave the suggestions.
    """

    lines: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    provider: str = ""


NOTHING = Asked()


# ---- the questions ----------------------------------------------------------------


@dataclass(frozen=True)
class Unpaired:
    """The removed modules that delta did not pair, the new modules, and delta's pairs."""

    left: list[str]
    options: list[str]
    found: dict[str, tuple[str, str]]


def unpaired(base: dict[str, Any], head: dict[str, Any]) -> Unpaired:
    """Give the removed modules to ask about. Without new modules, there are none."""
    b, h = base.get("components", {}), head.get("components", {})
    gone = sorted(set(b) - set(h))
    new = sorted(set(h) - set(b))
    found = moves.find(b, h, gone, new)
    left = [m for m in gone if m not in found and not source_facts.is_empty_marker(b[m])]
    options = [m for m in new if not source_facts.is_empty_marker(h[m])]
    return Unpaired(left if options else [], options, found)


def unclaimed(d: Delta) -> dict[str, list[str]]:
    """Give the modules that no component claims, by nested map id, from the delta lines."""
    out: dict[str, list[str]] = {}
    for line in d.lines:
        if line.decide and line.module:
            out.setdefault(line.map_id, []).append(line.module)
    return out


def _first_sentence(text: str, cap: int) -> str:
    text = " ".join((text or "").split())
    for end in (". ", ".\n"):
        i = text.find(end)
        if i != -1:
            text = text[: i + 1]
            break
    return text[:cap]


def _brief(record: dict[str, Any]) -> str:
    names = ", ".join(n["name"] for n in record.get("names", [])[:12])
    doc = _first_sentence(record.get("docstring") or "", 160)
    return f"{record.get('file')}: {doc} Names: {names}"


def _move_question(base: dict[str, Any], old: str, options: dict[str, str]) -> ChoiceQuestion:
    record = base[old]
    state = {
        "old_module": {
            "module": old,
            "file": record.get("file"),
            "docstring": record.get("docstring"),
            "names": [n["name"] for n in record.get("names", [])][:40],
        }
    }
    return ChoiceQuestion(old, "became", BECAME_Q, state, options)


def jev_moves(
    base: dict[str, Any], head: dict[str, Any], provider: DecisionProvider
) -> dict[str, tuple[str, str]]:
    """Pair removed modules with new modules at the `move_at` confidence or more.

    Delta's rules first remove known pairs. The provider selects from the new modules.
    A new module that delta paired, or that a pick with more confidence took, is not
    used again. A refusal or an answer without a confidence gives no pair.
    """
    b, h = base.get("components", {}), head.get("components", {})
    found = unpaired(base, head)
    if not found.left:
        return {}
    criteria = {m: _brief(h[m]) for m in found.options[:MOVE_OPTIONS]}
    criteria[NOT_MOVED] = "The removed module was deleted. No new module continues its function."
    questions = [_move_question(b, old, criteria) for old in found.left]
    move_at = decision.value(decision.thresholds(provider.name), "move_at")
    answers = provider.decide(questions)
    picks = sorted(_sure_picks(questions, answers), key=lambda p: (-p[1], p[2]))
    taken = {new for new, _how in found.found.values()}
    out: dict[str, tuple[str, str]] = {}
    for choice, confidence, old in picks:
        if choice == NOT_MOVED or confidence < move_at or choice in taken:
            continue
        taken.add(choice)
        by = decision.label(provider.name)
        out[old] = (choice, f"read as the same module by {by}, confidence {confidence:.2f}")
    return out


def _sure_picks(
    questions: list[ChoiceQuestion], answers: list[decision.Answer]
) -> list[tuple[str, float, str]]:
    """Give the pick, the confidence, and the removed module of each answer with a confidence."""
    out = []
    for question, answer in zip(questions, answers, strict=True):
        a = decision.choice(answer, question.key)
        if a is not None and a.confidence is not None:
            out.append((a.choice, a.confidence, question.key))
    return out


def owner_suggestions(
    cfg: Config,
    tree: nest.Tree,
    head: dict[str, Any],
    modules: dict[str, list[str]],
    provider: DecisionProvider,
) -> list[str]:
    """Give one owner prediction or three candidates per unclaimed module, in its own map."""
    plan = audit.Plan()
    for m in tree.maps:
        if modules.get(m.id):
            audit.plan_owner(plan, m, head, modules[m.id], cfg.name, placed_too=False)
    limits: Thresholds = decision.thresholds(provider.name)
    decision.value(limits, "owner_at")
    answers = provider.decide(plan.questions)
    out = []
    for question, answer in zip(plan.questions, answers, strict=True):
        line = audit.owner_line(plan.reads[question.key], answer, limits)
        if line is not None:
            out.append(f"{line.text} ({'; '.join(line.detail)})")
    return out


# ---- asking -----------------------------------------------------------------------


def ask(
    cfg: Config,
    tree: nest.Tree,
    base: dict[str, Any],
    head: dict[str, Any],
    d: Delta,
    send: jev.Send | None = None,
) -> Asked:
    """Ask the provider about the delta. A missing key or an error gives a reason."""
    left = unpaired(base, head).left
    owners = unclaimed(d)
    unmeasured = _unmeasured(cfg, bool(left), bool(owners))
    left = [] if "move_at" in unmeasured else left
    owners = {} if "owner_at" in unmeasured else owners
    reasons = tuple(
        f"{LABEL}: {decision.value_reason(cfg.decision_provider, n)}" for n in unmeasured
    )
    if not left and not owners:
        return Asked(errors=reasons) if reasons else NOTHING
    try:
        provider = providers.select(cfg, send)
    except DecisionError as exc:
        return Asked(errors=(f"{LABEL}: {exc}", *reasons))
    counted = Counted(provider)
    lines: list[str] = []
    try:
        moved = jev_moves(base, head, counted) if left else {}
        move = decision_kinds.MOVE
        lines += [f"{move}: {old} -> {new} ({how})" for old, (new, how) in moved.items()]
        lines += owner_suggestions(cfg, tree, head, owners, counted) if owners else []
    except DecisionError as exc:
        errors = (f"{LABEL}: {exc}", *reasons, *counted.errors())
        return Asked(tuple(lines), errors, provider.name)
    finally:
        providers.usage_to_stderr(provider)
    return Asked(tuple(lines), (*reasons, *counted.errors()), provider.name)


def _unmeasured(cfg: Config, moves_asked: bool, owners_asked: bool) -> list[str]:
    """Give the thresholds of the asked question types that have no measured value."""
    limits = decision.thresholds(cfg.decision_provider)
    asked = [n for n, on in (("move_at", moves_asked), ("owner_at", owners_asked)) if on]
    return [n for n in asked if getattr(limits, n) is None]


class Counted:
    """Give the answers of a decision provider. Keep the keys of the refusals."""

    def __init__(self, provider: DecisionProvider) -> None:
        self.provider = provider
        self.name = provider.name
        self.refused: list[str] = []

    def decide(self, questions: Sequence[decision.Question]) -> list[decision.Answer]:
        answers = self.provider.decide(questions)
        self.refused += decision.refused(questions, answers)
        return answers

    def errors(self) -> tuple[str, ...]:
        """Give a reason line when the decision provider gave a refusal."""
        if not self.refused:
            return ()
        return (f"{LABEL}: the decision provider gave a refusal for {len(self.refused)} questions",)


# ---- the report -------------------------------------------------------------------

HEAD = "{provider} suggestions. They do not change the delta lines or the exit code"


def text(asked: Asked, teach: bool = True) -> list[str]:
    """Give the suggestions with one explanation per kind, then the reasons."""
    out: list[str] = []
    if asked.lines:
        head = HEAD.format(provider=decision.label(asked.provider))
        out.append(f"{head} ({len(asked.lines)}):")
    taught: set[str] = set()
    for line in asked.lines:
        out.append(f"  {line}")
        kind = decision_kinds.kind_of(line) or ""
        if teach and kind not in taught:
            taught.add(kind)
            out += explain.rows(kind)
    return out + list(asked.errors)
