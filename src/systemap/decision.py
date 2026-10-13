"""Give typed questions to a decision provider and read typed answers.

This module has no provider code. A provider adapter, such as
`systemap.jev_provider`, changes the questions into the request format of its API.
It also changes each API answer into one of the answer records here.

A question is a choice question or a predicate question. Each question has a key,
a stable name, the instruction text, and the state. The key identifies the question
in one request. The state is the evidence as data.

A choice answer gives the selected option. It can also give a probability for each
option and a confidence. A predicate answer gives the probability that the condition
is correct. A refusal gives no decision. The raw provider data is optional metadata.

The thresholds are values for each provider and each question type. They came from
measurements on that provider. A provider without measured thresholds causes an error.
A question type that failed its measurement has no value (None). `value` gives the
reason for that question type, and the command does not send the question.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol


class DecisionError(Exception):
    """A provider cannot give the answers. The message gives the cause."""


@dataclass(frozen=True)
class ChoiceQuestion:
    """Select one option. `options` gives each option name and its description.

    `needs` gives the options that must have a probability in the answer.
    """

    key: str
    name: str
    instructions: str
    state: Any
    options: dict[str, str]
    needs: tuple[str, ...] = ()


@dataclass(frozen=True)
class PredicateQuestion:
    """Give the probability that the condition in `instructions` is correct."""

    key: str
    name: str
    instructions: str
    state: Any


Question = ChoiceQuestion | PredicateQuestion


@dataclass(frozen=True)
class ChoiceAnswer:
    """The selected option, the probability of each option when known, and the confidence."""

    choice: str
    probabilities: dict[str, float] = field(default_factory=dict)
    confidence: float | None = None
    raw: Any = None


@dataclass(frozen=True)
class PredicateAnswer:
    """The probability that the condition is correct."""

    probability: float
    raw: Any = None


@dataclass(frozen=True)
class Refusal:
    """The provider gave no decision. `reason` gives the text of the provider."""

    reason: str
    raw: Any = None


Answer = ChoiceAnswer | PredicateAnswer | Refusal


class DecisionProvider(Protocol):
    """Give one answer for each question, in the same sequence as the questions.

    `name` selects the thresholds of the provider.
    """

    name: str

    def decide(self, questions: Sequence[Question]) -> list[Answer]: ...


def choice(answer: Answer, key: str) -> ChoiceAnswer | None:
    """Give the choice answer, or None for a refusal."""
    if isinstance(answer, Refusal):
        return None
    if not isinstance(answer, ChoiceAnswer):
        raise DecisionError(f"the answer to {key} does not select an option")
    return answer


def probability(answer: Answer, key: str) -> float | None:
    """Give the probability of a predicate answer, or None for a refusal."""
    if isinstance(answer, Refusal):
        return None
    if not isinstance(answer, PredicateAnswer):
        raise DecisionError(f"the answer to {key} does not give a probability")
    return answer.probability


def spread(answer: ChoiceAnswer) -> dict[str, float]:
    """Give the probabilities of a choice answer, or the choice at its confidence."""
    if answer.probabilities:
        return dict(answer.probabilities)
    if answer.confidence is None:
        raise DecisionError(f"the answer {answer.choice} gives no probabilities and no confidence")
    return {answer.choice: answer.confidence}


def refused(questions: Sequence[Question], answers: Sequence[Answer]) -> list[str]:
    """Give the keys of the questions that got a refusal."""
    return [q.key for q, a in zip(questions, answers, strict=True) if isinstance(a, Refusal)]


@dataclass(frozen=True)
class Thresholds:
    """The measured limits of one provider for each question type.

    None: the question type has no measured value for this provider.
    `triage` is False when the triage measurement of the provider failed.
    """

    misfold_below: float | None
    owner_at: float | None
    sentence_below: float | None
    flow_below: float | None
    governs_at: float | None
    same_at: float | None
    move_at: float | None
    plan_cut: float | None
    provider: str = "jev"
    triage: bool = True


# The question type of each threshold, for the reason text.
QUESTION_TYPES = {
    "misfold_below": "jev mis-fold",
    "owner_at": "jev owner",
    "sentence_below": "jev sentence",
    "flow_below": "jev flow",
    "governs_at": "jev governs",
    "same_at": "suggest --jev",
    "move_at": "the move question of delta --jev",
    "plan_cut": "plan",
}


# The Jev values came from five first maps in bench/scratch, recorded in bench/jev.
JEV = Thresholds(
    # P(current card) below this: planted in a neighbouring card, 95% caught;
    # 4% of correctly placed modules flagged.
    misfold_below=0.05,
    # Choice confidence at or above this: 56% of modules get one card, 98% right.
    owner_at=0.9,
    # P(sentence describes its modules) below this: 67% of wrong sentences caught,
    # 1% of right ones flagged.
    sentence_below=0.2,
    # P(code carries the claim) below this: 66% of wrong claims caught, 2% of
    # real ones flagged; on the holdout maps 54% and 4%, so asked only on request.
    flow_below=0.2,
    # P(invariant governs card) at or above this: 31% of governed cards found,
    # 1% of the rest suggested.
    governs_at=0.8,
    # Pairs at or above this are one part, for `suggest --jev`: with the threshold
    # chosen on four development maps and scored on the fifth, pairwise F1 beat one
    # card per package by 0.18 on average, and lost on two maps of five
    # (bench/jev/results/grouping-report.txt).
    same_at=0.4,
    # A move pick at this confidence or more prints. Delta and these picks found 82
    # renames against delta's 66, and 16 of the 17 added pairs were right, with earlier
    # prompts on Python repositories (bench/jev/README.md, "What did tests 7 and 8
    # measure?").
    move_at=0.8,
    # A card is in a plan projection when it gets at least this probability
    # (bench/jev/plan_eval.py).
    plan_cut=0.05,
)

# The OpenAI values came from the Jev bench rows (bench/jev/README.md, "Can OpenAI
# Decisions use the measured audit rules?"). Each value was selected on the five
# development maps, and each figure on the holdout maps was within 10 points.
OPENAI = Thresholds(
    # Not available: on holdout, 61.5% of planted modules were caught, 82.1% on development.
    misfold_below=None,
    # 9.5% of modules get one card, 100% right (holdout 4.7%, 100%).
    owner_at=0.99,
    # 81.0% of wrong sentences caught, 1.3% of right ones flagged (holdout 75.0%, 0.0%).
    sentence_below=0.3,
    # 46.2% of wrong claims caught, 2.5% of real ones flagged (holdout 56.2%, 8.3%).
    flow_below=0.05,
    # 19.8% of governed cards found, 1.1% of the rest suggested (holdout 17.2%, 6.0%).
    governs_at=0.99,
    # Not available: the pair question has no holdout rows.
    same_at=None,
    # Not available: the move question has no holdout rows.
    move_at=None,
    # Not available: on holdout, the plan covered 0.39 of the changed cards, 0.73 on
    # development.
    plan_cut=None,
    provider="openai",
    # Not available: the top-1 rate was 82.5% on development and 69.2% on holdout.
    triage=False,
)

THRESHOLDS: dict[str, Thresholds] = {"jev": JEV, "openai": OPENAI}


def thresholds(provider: str) -> Thresholds:
    """Give the measured thresholds of a provider, or raise DecisionError."""
    found = THRESHOLDS.get(provider)
    if found is None:
        raise DecisionError(
            f"the decision provider {provider} has no measured thresholds. Measure them before use"
        )
    return found


def value(limits: Thresholds, name: str) -> float:
    """Give one measured threshold, or raise DecisionError if the measurement failed."""
    found = getattr(limits, name)
    if found is None:
        raise DecisionError(unmeasured(limits.provider, QUESTION_TYPES[name]))
    return float(found)


def value_reason(provider: str, name: str) -> str:
    """Give the reason text for one threshold without a measured value."""
    return unmeasured(provider, QUESTION_TYPES[name])


def unmeasured(provider: str, question_type: str) -> str:
    """Give the reason text for a question type without a measured value."""
    return (
        f"the decision provider {provider} has no measured value for {question_type}. "
        "The command does not send this question (bench/jev/README.md)"
    )
