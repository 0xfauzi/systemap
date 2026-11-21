"""The settings read and validate the answers of `[judgement] answered`.

An answer selects exact lines with `item` or `items`, or a family of lines with
`crossing`, `crossing_into`, `crossing_from`, `kind` or `module_sdk`. Exact answers can
have an evidence digest and citations. Family answers must have `policy = true`. An
answer for a `module use` line also has a module role in `role`, and it can have `symbol`
and `handoff`. These functions give a ValueError for an incorrect value. The
configuration reader changes it to a ConfigError.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from typing import Any

from systemap import config_decisions, decision_kinds

JUDGEMENT_KEYS = {"answered", "require_reviews"}
ANSWER_FORMS = ("item", "items", "crossing", "crossing_into", "crossing_from", "kind", "module_sdk")
ROLE_KEYS = ("role", "symbol", "handoff")
ROLES = ("helper", "handoff", "mixed")
ANSWER_KEYS = {*ANSWER_FORMS, "reason", "evidence", "policy", "reviewed", "citations", *ROLE_KEYS}
# An item for a `module use` line, with or without the prefix of a nested map.
MODULE_USE_ITEM = re.compile(r"^(?:\S+: )?module use: ")
NAME = re.compile(r"\S+")
# The kinds of line `systemap judgement` prints, as `kind = "..."` names them.
LINE_KINDS = (
    "single module",
    "possible mis-fold",
    "no sentence",
    "thin layer",
    "entry point",
    "journey start",
    "drafted journey",
    "step source",
    "crossing import",
    "module use",
    "declared flow",
    "flow review",
    "no endpoint source",
    "stale source review",
    "missing source review",
    "model sdk",
    "unknown surface",
    "contract reason",
    "boundary flow",
    "boundary import",
)
# The kinds of line `systemap audit` prints; answered in the same list.
AUDIT_KINDS = decision_kinds.KINDS


@dataclass(frozen=True)
class Answer:
    """This record gives a maintainer answer for exact diagnostic lines or a line family.

    Exact items contain the full printed line without the two-space indent. Family
    selectors use component IDs, a diagnostic kind, or an SDK import. Evidence binds
    exact answers to source data. A policy lets family answers accept diagnostics. An
    answer for a module use line gives the module role in `role`, a name of the module in
    `symbol`, and the handoff names of a mixed module in `handoff`.
    """

    items: tuple[str, ...]
    reason: str
    crossing: tuple[str, ...] | None = None
    kind: str = ""
    module_sdk: str = ""
    crossing_into: str = ""
    crossing_from: str = ""
    evidence: str = ""
    policy: bool = False
    reviewed: tuple[str, ...] = ()
    # (file, start_line, end_line, sha256) for each source span that supports the answer.
    citations: tuple[tuple[str, int, int, str], ...] = ()
    role: str = ""
    symbol: str = ""
    handoff: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        """This property gives the answer selector as configuration text for stale-answer
        reports."""
        if self.crossing is not None:
            return "crossing = [" + ", ".join(f'"{cid}"' for cid in self.crossing) + "]"
        if self.crossing_into:
            return f'crossing_into = "{self.crossing_into}"'
        if self.crossing_from:
            return f'crossing_from = "{self.crossing_from}"'
        if self.kind:
            return f'kind = "{self.kind}"'
        if self.module_sdk:
            return f'module_sdk = "{self.module_sdk}"'
        return self.items[0] if len(self.items) == 1 else f"items = {list(self.items)}"


def _answer_selector(form: str, value: Any, location: str) -> Answer:
    """Validate the answer selector without its reason or evidence."""
    if form in ("item", "items"):
        return Answer(items=_answer_lines(form, value, location), reason="")
    if form == "crossing":
        return Answer(items=(), reason="", crossing=_answer_crossing(value, location))
    if form in ("crossing_into", "crossing_from"):
        name = _answer_name(value, f"{location} {form} must contain one component ID.")
        if form == "crossing_into":
            return Answer(items=(), reason="", crossing_into=name)
        return Answer(items=(), reason="", crossing_from=name)
    if form == "kind":
        error = f"{location} kind must be one of {', '.join((*LINE_KINDS, *AUDIT_KINDS))}"
        name = _answer_name(value, error)
        if name not in (*LINE_KINDS, *AUDIT_KINDS):
            raise ValueError(error + decision_kinds.previous_name_note(name))
        return Answer(items=(), reason="", kind=name)
    name = _answer_name(value, f"{location} module_sdk must be an import name.")
    return Answer(items=(), reason="", module_sdk=name)


def _answer_name(value: Any, error: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(error)
    return value.strip()


def _answer_lines(form: str, value: Any, location: str) -> tuple[str, ...]:
    if form == "item":
        return (_answer_name(value, f"{location} item must be a line."),)
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(v, str) and v.strip() for v in value)
    ):
        raise ValueError(f"{location} items must be a list with one or more lines.")
    return tuple(v.strip() for v in value)


def _answer_crossing(value: Any, location: str) -> tuple[str, ...]:
    ids = (
        [v.strip() if isinstance(v, str) else "" for v in value] if isinstance(value, list) else []
    )
    if len(ids) < 2 or not all(ids) or len(set(ids)) != len(ids):
        raise ValueError(
            f"{location} crossing must contain two or more different component IDs, such "
            f'as ["A", "B"].'
        )
    return tuple(ids)


def judgement_answered(raw: dict[str, Any], where: str) -> tuple[Answer, ...]:
    """This function reads and validates `[judgement] answered`, with reasons and evidence."""
    judgement = raw.get("judgement", {})
    if not isinstance(judgement, dict):
        raise ValueError(f"{where}: judgement must be a table")
    bad = sorted(set(judgement) - JUDGEMENT_KEYS)
    if bad:
        raise ValueError(f"{where}: judgement has an unknown key: {', '.join(bad)}")
    entries = judgement.get("answered", [])
    if not isinstance(entries, list):
        raise ValueError(f"{where}: judgement.answered must be a list of tables")
    return tuple(
        _answer_entry(entry, f"{where}: judgement.answered[{k}]")
        for k, entry in enumerate(entries, start=1)
    )


def _answer_entry(entry: Any, location: str) -> Answer:
    if not isinstance(entry, dict):
        raise ValueError(f"{location} must be a table with item (or items) and reason.")
    bad = sorted(set(entry) - ANSWER_KEYS)
    if bad:
        raise ValueError(f"{location} has an unknown key: {', '.join(bad)}")
    forms = [form for form in ANSWER_FORMS if entry.get(form) is not None]
    if len(forms) != 1:
        raise ValueError(
            f"{location} must contain one selector: item, items, crossing, crossing_into, "
            f"crossing_from, kind, or module_sdk. The selector count is {len(forms)}"
        )
    (form,) = forms
    answer = _answer_selector(form, entry[form], location)
    evidence, policy, reviewed = _answer_review(entry, form, location)
    reason = entry.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError(
            f"{location} ({answer.label}) must contain a reason. Give the reason for the answer."
        )
    cited = config_decisions.citations(entry.get("citations"), location)
    role, symbol, handoff = _answer_role(entry, form, answer, location)
    return dataclasses.replace(
        answer,
        reason=reason,
        evidence=evidence,
        policy=policy,
        reviewed=reviewed,
        citations=cited,
        role=role,
        symbol=symbol,
        handoff=handoff,
    )


def _answer_review(
    entry: dict[str, Any], form: str, location: str
) -> tuple[str, bool, tuple[str, ...]]:
    exact = form in ("item", "items")
    evidence = entry.get("evidence", "")
    policy = entry.get("policy", False)
    reviewed = entry.get("reviewed", [])
    if not isinstance(evidence, str) or (evidence and not exact):
        raise ValueError(f"{location} evidence is permitted only for an exact item.")
    if evidence and re.fullmatch(r"[0-9a-f]{64}", evidence) is None:
        raise ValueError(f"{location} evidence must be a SHA-256 digest")
    if not isinstance(policy, bool) or (policy and exact):
        raise ValueError(f"{location} policy is permitted only for a family selector.")
    if not isinstance(reviewed, list) or not all(isinstance(v, str) and v for v in reviewed):
        raise ValueError(f"{location} reviewed must be a list of lines")
    if reviewed and not policy:
        raise ValueError(f"{location} reviewed is permitted only with policy = true.")
    return evidence, policy, tuple(reviewed)


def _answer_role(
    entry: dict[str, Any], form: str, answer: Answer, location: str
) -> tuple[str, str, tuple[str, ...]]:
    """Validate the module role keys. Only the facts tell if a helper answer needs a symbol."""
    given = [key for key in ROLE_KEYS if entry.get(key) is not None]
    if given and form != "item":
        raise ValueError(f"{location} role, symbol, and handoff are permitted only with item.")
    if form != "item":
        return "", "", ()
    if MODULE_USE_ITEM.match(answer.items[0]) is None:
        if given:
            raise ValueError(f"{location} role is permitted only for a module use line.")
        return "", "", ()
    role = entry.get("role")
    if role is None:
        raise ValueError(
            f'{location} ({answer.label}) must contain role: "helper", "handoff", or "mixed".'
        )
    if role not in ROLES:
        raise ValueError(f'{location} role must be "helper", "handoff", or "mixed".')
    symbol = entry.get("symbol")
    if symbol is not None and not _is_name(symbol):
        raise ValueError(f"{location} symbol must be one name without spaces.")
    return role, symbol or "", _answer_handoff(entry.get("handoff"), role, symbol, location)


def _answer_handoff(value: Any, role: str, symbol: Any, location: str) -> tuple[str, ...]:
    if role != "mixed":
        if value is not None:
            raise ValueError(f'{location} handoff is permitted only with role "mixed".')
        return ()
    if not isinstance(value, list) or not value or not all(_is_name(v) for v in value):
        raise ValueError(
            f'{location} role "mixed" must have handoff: a list of one or more names of the module.'
        )
    if symbol is not None:
        raise ValueError(
            f'{location} symbol is not permitted with role "mixed". Put the names in handoff.'
        )
    return tuple(value)


def _is_name(value: Any) -> bool:
    return isinstance(value, str) and NAME.fullmatch(value) is not None
