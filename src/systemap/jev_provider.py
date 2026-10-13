"""Use TypeSafe's Jev as a decision provider.

`JevProvider` implements `systemap.decision.DecisionProvider` on the Jev client in
`systemap.jev`. Each question becomes one Jev request with one question.
A choice question becomes a Jev `choice` question with the options as `criteria`.
A predicate question becomes a Jev `noul` question.
The Jev `noul` value is the probability of the predicate answer.

The request bodies and the cache keys are the same as before this adapter.
Thus the recorded caches and the benchmark results stay valid.
Jev gives no refusal. The client does not accept an answer that does not agree
with its question. It raises `JevError`.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from systemap import jev
from systemap.decision import (
    Answer,
    ChoiceAnswer,
    ChoiceQuestion,
    PredicateAnswer,
    Question,
)
from systemap.jev import Ask


def ask_of(question: Question) -> Ask:
    """Make the Jev request for one question."""
    if isinstance(question, ChoiceQuestion):
        body = {
            "type": "choice",
            "instructions": question.instructions,
            "criteria": question.options,
        }
        return Ask(question.key, question.state, {question.name: body}, question.needs)
    noul = {"type": "noul", "instructions": question.instructions}
    return Ask(question.key, question.state, {question.name: noul})


def answer_of(question: Question, raw: dict[str, Any]) -> Answer:
    """Make the answer record from one Jev answer that the client accepted."""
    if isinstance(question, ChoiceQuestion):
        return ChoiceAnswer(
            choice=raw["choice"],
            probabilities=dict(raw.get("probabilities") or {}),
            confidence=raw["confidence"],
            raw=raw,
        )
    return PredicateAnswer(probability=raw["noul"], raw=raw)


def chars(questions: Sequence[Question]) -> int:
    """Count the JSON characters of the state and the questions that Jev gets."""
    return sum(ask_of(q).chars() for q in questions)


class JevProvider:
    """Give the answers of one Jev model. Cached answers are used when available."""

    name = "jev"

    def __init__(self, client: jev.Jev) -> None:
        self.client = client

    @property
    def usage(self) -> jev.Usage:
        return self.client.usage

    def decide(self, questions: Sequence[Question]) -> list[Answer]:
        """Give one answer for each question, in sequence. A request error raises JevError."""
        answered = self.client.ask([ask_of(q) for q in questions])
        return [answer_of(q, answered[q.key][q.name]) for q in questions]

    def pending(self, questions: Sequence[Question]) -> int:
        """Count the questions without a cached answer. Only the model list is read."""
        return len(self.client.pending([ask_of(q) for q in questions]))


def from_env(
    model: str, cache_path: Path | None, send: jev.Send | None = None, root: Path | None = None
) -> JevProvider:
    """Make the provider with an injected transport, or HTTPS with an environment key.

    `root` is the folder that contains the cache file: the repository root."""
    return JevProvider(jev.from_env(model, cache_path, send, root))
