"""Give the diagnostic kinds of the findings that come from a decision provider.

`systemap audit` prints the kinds in `KINDS`. `systemap delta --decide` prints `MOVE`
and `OWNER`. The names do not name a provider, because Jev or OpenAI can give the
answers.

Before 2.0.0, each kind name started with "jev". 2.0.0 and 3.0.0 also read an answer in
`[judgement] answered` with a previous name. From 3.1.0, systemap does not read the
previous names: an answer item with a previous name matches no line. `PREVIOUS` gives
the previous name of each kind for two uses only:

- The evidence digest of a line is the digest of the same line with its previous kind
  name (`previous_line`). Thus a digest recorded before the rename stays correct.
- `renamed` finds an answer item with a previous name. The judgement report then gives
  the new name to the maintainer.

The word "decision" in the line also does not select a module or a component with that
name.
"""

from __future__ import annotations

MISFOLD = "decision mis-fold"
OWNER = "decision owner"
SENTENCE = "decision sentence"
FLOW = "decision flow"
GOVERNS = "decision governs"
MOVE = "decision move"

# The kinds that `systemap audit` prints, and that `--kind` selects.
KINDS = (MISFOLD, OWNER, SENTENCE, FLOW, GOVERNS)

# The previous name of each kind. systemap does not read these names as kinds.
PREVIOUS = {
    "jev mis-fold": MISFOLD,
    "jev owner": OWNER,
    "jev sentence": SENTENCE,
    "jev flow": FLOW,
    "jev governs": GOVERNS,
    "jev move": MOVE,
}
_LATER = {new: old for old, new in PREVIOUS.items()}
_NAMES = (*KINDS, MOVE)


def _parts(line: str, names: tuple[str, ...] = _NAMES) -> tuple[str, str, str] | None:
    """Give the map prefix, the kind name, and the remaining text of a decision line."""
    head, sep, _rest = line.partition(": ")
    for prefix in ("", head + sep) if sep else ("",):
        body = line[len(prefix) :]
        for name in names:
            if body.startswith(name + ": "):
                return prefix, name, body[len(name) + 2 :]
    return None


def kind_of(line: str) -> str | None:
    """Give the kind name of a decision line, or None for a different line."""
    found = _parts(line)
    return found[1] if found else None


def bare(line: str) -> str:
    """Remove a nested-map `<map>: ` prefix from a decision line."""
    found = _parts(line)
    return line[len(found[0]) :] if found else line


def previous_line(line: str) -> str:
    """Change the kind name in a decision line to the previous name, for the digest."""
    found = _parts(line)
    if found is None:
        return line
    prefix, name, rest = found
    return f"{prefix}{_LATER.get(name, name)}: {rest}"


def renamed(line: str) -> tuple[str, str] | None:
    """Give the previous kind name and the new name if a line starts with a previous name."""
    found = _parts(line, tuple(PREVIOUS))
    return (found[1], PREVIOUS[found[1]]) if found else None
