"""Select the decision provider of a command that asks questions.

The provider comes from the `--provider` option, or else from `[decisions] provider`
in the configuration. The default is Jev. A key in the environment never selects a
provider: with `OPENAI_API_KEY` set and no selection, no request goes to OpenAI.
If the selected provider fails, the command shows the failure and stops. It does not
use a different provider.

A provider can have no measured value for a question type (`decision.Thresholds`).
The commands use `missing` and `require` before they send a question, so that no data
goes to the provider for a question type that the command cannot use.
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from collections.abc import Iterable, Sequence
from typing import Protocol

from systemap import decision, decision_kinds, jev, jev_provider, openai_provider
from systemap.config import Config
from systemap.config_decisions import PROVIDERS
from systemap.decision import DecisionError, Question

# The threshold of each audit question type.
AUDIT_FIELDS = {
    decision_kinds.MISFOLD: "misfold_below",
    decision_kinds.OWNER: "owner_at",
    decision_kinds.SENTENCE: "sentence_below",
    decision_kinds.FLOW: "flow_below",
    decision_kinds.GOVERNS: "governs_at",
}


class Metered(Protocol):
    """A decision provider that records its usage and counts the cached answers."""

    name: str

    @property
    def usage(self) -> jev.Usage: ...

    def decide(self, questions: Sequence[Question]) -> list[decision.Answer]: ...

    def pending(self, questions: Sequence[Question]) -> int: ...


def add_option(parser: argparse.ArgumentParser) -> None:
    """Add the `--provider` option to a command that asks questions."""
    parser.add_argument(
        "--provider",
        choices=PROVIDERS,
        default=None,
        help="Select the decision provider. The default is [decisions] provider in "
        'systemap.toml, or "jev". A key in the environment does not select a provider. '
        "OpenAI gets the question state (module facts and map text) and the questions.",
    )


def chosen(cfg: Config, option: str | None) -> Config:
    """Give the configuration with the provider of the option, if the option is given."""
    if option is None or option == cfg.decision_provider:
        return cfg
    return dataclasses.replace(cfg, decision_provider=option)


def select(cfg: Config, send: jev.Send | None = None) -> Metered:
    """Make the selected provider, with an injected transport or the environment key."""
    if cfg.decision_provider == openai_provider.NAME:
        return openai_provider.from_env(cfg.openai_model, cfg.openai_cache_path, send)
    return jev_provider.from_env(cfg.jev_model, cfg.jev_cache_path, send)


def has_key(cfg: Config) -> bool:
    """Tell if the environment has the key of the selected provider."""
    if cfg.decision_provider == openai_provider.NAME:
        return openai_provider.has_key()
    return jev.has_key()


def chars(cfg: Config, questions: Sequence[Question]) -> int:
    """Count the JSON characters that the selected provider gets."""
    if cfg.decision_provider == openai_provider.NAME:
        return openai_provider.chars(questions)
    return jev_provider.chars(questions)


def missing(cfg: Config, kinds: Iterable[str]) -> list[str]:
    """Give the audit question types without a measured value for the selected provider."""
    limits = decision.thresholds(cfg.decision_provider)
    return [k for k in kinds if getattr(limits, AUDIT_FIELDS[k]) is None]


def require(cfg: Config, name: str) -> float:
    """Give one measured value of the selected provider, or raise DecisionError."""
    return decision.value(decision.thresholds(cfg.decision_provider), name)


def require_triage(cfg: Config) -> None:
    """Raise DecisionError if the triage measurement of the selected provider failed."""
    if not decision.thresholds(cfg.decision_provider).triage:
        raise DecisionError(decision.unmeasured(cfg.decision_provider, "triage"))


def usage_to_stderr(provider: Metered) -> None:
    """Print usage to stderr when a run used the provider or its cache."""
    if provider.usage.sent or provider.usage.cached:
        print(provider.usage.line(), file=sys.stderr)
