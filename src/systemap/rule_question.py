"""Ask a decision provider for the import rule kind of an invariant, as information only.

`systemap judgement --propose-rules` uses this module. Without the option, the command
makes no provider and sends no request.

For each invariant that has no linked import rule and no pattern proposal
(`systemap.rule_proposal`), one choice question goes to the selected provider. The
options are "forbid_import", "allow_imports", "forbid_cycle", and "no import rule". The
state has the invariant and the cards of the components that the invariant names: the
components in `governs` and the component ids in the text. If the invariant names no
component, the state has the cards of all components of the map.

A proposal from this question must have a measured threshold for the provider
(`decision.Thresholds.rule_at`). No provider has one, because no measurement exists.
Thus the command gives the probabilities as information only. It gives no proposal and
no judgement line, and it does not change the open lines or the exit code.

A refusal gives no probabilities for its invariant. A provider error gives the cause and
no probabilities. No other answer replaces a missing answer.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from systemap import decision, jev, nest, providers, rule_proposal
from systemap.config import ArgumentError, Config
from systemap.config_decisions import PROVIDERS
from systemap.decision import ChoiceQuestion, DecisionError, DecisionProvider
from systemap.model import Component, Invariant

NAME = "import_rule"
NO_RULE = "no import rule"
OPTIONS = {
    "forbid_import": (
        "No module of one or more named components imports a module of the other named components."
    ),
    "allow_imports": (
        "The modules of one or more named components import only modules of the named components."
    ),
    "forbid_cycle": "No import cycle connects two or more of the named components.",
    NO_RULE: "The invariant does not give a rule about the imports between components.",
}
QUESTION = (
    "`invariant` gives a rule of a software system. `components` gives the components that "
    "the rule names. A program can examine the imports between the modules of components. "
    "Which import rule does the invariant give?"
)


@dataclass(frozen=True)
class Target:
    """One invariant for the question, with its map."""

    map: nest.Map
    invariant: Invariant

    @property
    def key(self) -> str:
        return f"{self.map.id}#{self.invariant.n}"


@dataclass(frozen=True)
class Asked:
    """The answers by target. An answer is None for a refusal. `error` is the provider error."""

    provider: str
    answers: list[tuple[Target, decision.ChoiceAnswer | None]] = field(default_factory=list)
    error: str = ""

    @property
    def reason(self) -> str:
        return (
            f"No proposal: the decision provider {self.provider} has no measured value for "
            "the rule proposal question. The probabilities are information only."
        )

    def rows(self) -> list[str]:
        """Give the text rows: one row for each invariant, then the reason or the error."""
        if self.error:
            return [f"rule question: No probabilities. Cause: {self.error}"]
        if not self.answers:
            return ["rule question: No invariant needs a question. No question was sent."]
        return [_row(t, a) for t, a in self.answers] + [f"rule question: {self.reason}"]

    def payload(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "proposal": False,
            "reason": self.reason,
            "error": self.error,
            "questions": [_record(t, a) for t, a in self.answers],
        }


def _row(target: Target, answer: decision.ChoiceAnswer | None) -> str:
    head = f"rule question: {target.map.prefix}invariant {target.invariant.n}: "
    if answer is None:
        return head + "refusal"
    ranked = sorted(decision.spread(answer).items(), key=lambda kv: -kv[1])
    return head + ", ".join(f"{name} {p:.2f}" for name, p in ranked)


def _record(target: Target, answer: decision.ChoiceAnswer | None) -> dict[str, Any]:
    return {
        "map": target.map.id,
        "invariant": target.invariant.n,
        "choice": answer.choice if answer else None,
        "probabilities": decision.spread(answer) if answer else None,
    }


# ---- the questions ---------------------------------------------------------------------


def targets(tree: nest.Tree) -> list[Target]:
    """Give the invariants without a linked rule and without a pattern proposal."""
    out: list[Target] = []
    for m in tree.maps:
        done = rule_proposal.linked(m.model) | {
            p.invariant for p in rule_proposal.proposals(m.model)
        }
        out += [Target(m, inv) for inv in m.model.invariants if inv.n not in done]
    return out


def _card(card: Component, m: nest.Map) -> dict[str, Any]:
    return {
        "id": card.id,
        "kind": card.kind,
        "does": card.does,
        "plain": m.meaning.plain.get(card.id, ""),
        "interface": card.interface,
    }


def cards(target: Target) -> list[dict[str, Any]]:
    """Give the cards of the components that the invariant names, in model order."""
    inv, m = target.invariant, target.map
    named = [
        c
        for c in m.model.components
        if c.id in inv.governs or re.search(rf"(?<![\w-]){re.escape(c.id)}(?![\w-])", inv.text)
    ]
    return [_card(c, m) for c in (named or m.model.components)]


def question(target: Target) -> ChoiceQuestion:
    inv = target.invariant
    state = {
        "invariant": {"n": inv.n, "text": inv.text, "governs": list(inv.governs)},
        "components": cards(target),
    }
    return ChoiceQuestion(target.key, NAME, QUESTION, state, dict(OPTIONS), tuple(OPTIONS))


def questions(tree: nest.Tree) -> list[ChoiceQuestion]:
    return [question(t) for t in targets(tree)]


# ---- the answers -----------------------------------------------------------------------

Make = Callable[[], DecisionProvider]


def ask(cfg: Config, tree: nest.Tree, make: Make) -> Asked:
    """Ask one question for each target. Without a target, make no provider."""
    name = cfg.decision_provider
    found = targets(tree)
    if not found:
        return Asked(name)
    try:
        decision.thresholds(name)
        provider = make()
    except DecisionError as exc:
        return Asked(name, error=jev.printable(str(exc)))
    asked = [question(t) for t in found]
    try:
        answers = provider.decide(asked)
        chosen = [decision.choice(a, q.key) for q, a in zip(asked, answers, strict=True)]
    except DecisionError as exc:
        return Asked(name, error=jev.printable(str(exc)))
    finally:
        _usage(provider)
    return Asked(name, list(zip(found, chosen, strict=True)))


def _usage(provider: Any) -> None:
    if isinstance(getattr(provider, "usage", None), jev.Usage):
        providers.usage_to_stderr(provider)


def _asked(cfg: Config, tree: nest.Tree, args: argparse.Namespace) -> Asked | None:
    """Give the answers with `--propose-rules`, or None without the option."""
    option = getattr(args, "provider", None)
    if not getattr(args, "propose_rules", False):
        if option is not None:
            raise ArgumentError("--provider applies only with --propose-rules.")
        return None
    chosen = providers.chosen(cfg, option)
    return ask(chosen, tree, lambda: providers.select(chosen))


def add_options(parser: argparse.ArgumentParser) -> None:
    """Add `--propose-rules` and `--provider` to `systemap judgement`."""
    parser.add_argument(
        "--propose-rules",
        action="store_true",
        help=(
            "Send one question to the decision provider for each invariant without an import "
            "rule and without a rule proposal line. The answer gives a probability for each "
            "rule kind, as information only. No measured value lets the command give a "
            "proposal. "
            "The option does not change the open lines or the exit code."
        ),
    )
    parser.add_argument(
        "--provider",
        choices=PROVIDERS,
        default=None,
        help=(
            "Select the decision provider of --propose-rules. The default is [decisions] "
            'provider in systemap.toml, or "jev". --order-by-drift always uses Jev.'
        ),
    )


def text(cfg: Config, tree: nest.Tree, args: argparse.Namespace) -> list[str]:
    """Give the rows of the text report. Without the option, give none and send nothing."""
    found = _asked(cfg, tree, args)
    return found.rows() if found is not None else []


def payload(cfg: Config, tree: nest.Tree, args: argparse.Namespace) -> dict[str, Any]:
    """Give `rule_questions` for the JSON object. Without the option, give nothing."""
    found = _asked(cfg, tree, args)
    return {"rule_questions": found.payload()} if found is not None else {}
