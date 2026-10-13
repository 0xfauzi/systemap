"""Give the diagnostic kinds of the findings that come from a decision provider.

`systemap audit` prints the kinds in `KINDS`. `systemap delta --decide` prints `MOVE`
and `OWNER`. The names do not name a provider, because Jev or OpenAI can give the
answers.

Before this release, each kind name started with "jev". `PREVIOUS` gives the previous
name of each kind. For one release, an answer in `[judgement] answered` can use an
previous name, and it matches the line with the current name. `warnings` gives one
warning for each previous name in the answers.

The evidence digest of a line is the digest of the same line with its previous kind
name (`previous_line`). Thus a digest recorded before the rename stays correct. The
word "decision" in the line also does not select a module or a component with that
name.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

MISFOLD = "decision mis-fold"
OWNER = "decision owner"
SENTENCE = "decision sentence"
FLOW = "decision flow"
GOVERNS = "decision governs"
MOVE = "decision move"

# The kinds that `systemap audit` prints, and that `--kind` selects.
KINDS = (MISFOLD, OWNER, SENTENCE, FLOW, GOVERNS)

# The previous name of each kind. systemap reads these names for one release.
PREVIOUS = {
    "jev mis-fold": MISFOLD,
    "jev owner": OWNER,
    "jev sentence": SENTENCE,
    "jev flow": FLOW,
    "jev governs": GOVERNS,
    "jev move": MOVE,
}
_LATER = {new: old for old, new in PREVIOUS.items()}
# The audit kinds with their previous names, for the `--kind` option.
AUDIT_NAMES = (*KINDS, *(old for old, new in PREVIOUS.items() if new in KINDS))
_NAMES = (*KINDS, MOVE, *PREVIOUS)


class Answered(Protocol):
    """The fields of a configured answer that can contain a kind name."""

    @property
    def items(self) -> tuple[str, ...]: ...

    @property
    def kind(self) -> str: ...

    @property
    def reviewed(self) -> tuple[str, ...]: ...


def current(kind: str) -> str:
    """Give the current name of a kind. A current name or another kind stays the same."""
    return PREVIOUS.get(kind, kind)


def _parts(line: str) -> tuple[str, str, str] | None:
    """Give the map prefix, the kind name, and the remaining text of a decision line."""
    head, sep, _rest = line.partition(": ")
    for prefix in ("", head + sep) if sep else ("",):
        body = line[len(prefix) :]
        for name in _NAMES:
            if body.startswith(name + ": "):
                return prefix, name, body[len(name) + 2 :]
    return None


def kind_of(line: str) -> str | None:
    """Give the current kind name of a decision line, or None for a different line."""
    found = _parts(line)
    return current(found[1]) if found else None


def bare(line: str) -> str:
    """Remove a nested-map `<map>: ` prefix from a decision line."""
    found = _parts(line)
    return line[len(found[0]) :] if found else line


def current_line(line: str) -> str:
    """Change an previous kind name in a decision line to the current name."""
    found = _parts(line)
    if found is None:
        return line
    prefix, name, rest = found
    return f"{prefix}{current(name)}: {rest}"


def previous_line(line: str) -> str:
    """Change the current kind name in a decision line to the previous name."""
    found = _parts(line)
    if found is None:
        return line
    prefix, name, rest = found
    return f"{prefix}{_LATER.get(name, name)}: {rest}"


def previous_names(answers: Iterable[Answered]) -> list[str]:
    """Give each previous kind name in the answers one time, in the configured sequence."""
    found: list[str] = []
    for answer in answers:
        lines = (*answer.items, *answer.reviewed)
        names = [answer.kind] + [p[1] for p in map(_parts, lines) if p]
        found += [n for n in names if n in PREVIOUS and n not in found]
    return found


def warnings(answers: Iterable[Answered]) -> list[str]:
    """Give one warning for each previous kind name in `[judgement] answered`."""
    return [
        f'warning: [judgement] answered uses the previous name "{name}". '
        f'Change it to "{PREVIOUS[name]}". Only this release reads the previous names.'
        for name in previous_names(answers)
    ]


def option_warning(name: str) -> str:
    """Give the warning for an previous kind name in the `--kind` option."""
    return (
        f'warning: "{name}" is the previous name of "{PREVIOUS[name]}". Use the new name. '
        "Only this release reads the previous names."
    )
