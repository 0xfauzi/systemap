"""Which new module a module that disappeared became, between two commits.

`delta` reports a move where these questions pair two modules: the same
source, then the same public names, then a file name that reads the same and
most of the same names. `delta --jev` adds the pairings Jev reads, for the
modules the three leave unpaired, through `with_told`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Any

from systemap.model import public_names

# What the last question asks of a module renamed and edited at once:
# how much of its public surface it kept, and how alike the two file
# names read. Measured over every python rename git reports in kstrl,
# rich, poetry, mealie and paperless-ngx. 0.8 of the surface is the
# loosest value that costs nothing: at 0.6, mealie gains two wrong
# pairings. 0.6 of the file name buys two more real renames for one
# wrong one, and is what recognises route.py -> routing.py, which
# reads 0.78 alike.
SURFACE_OVERLAP = 0.8
NAME_ALIKE = 0.6


def _path(record: dict[str, Any]) -> PurePosixPath:
    """Where a module's file sits, as the facts recorded it."""
    return PurePosixPath(str(record.get("file", "")))


def _affinity(old: dict[str, Any], cand: dict[str, Any]) -> tuple[int, int, int]:
    """How alike two modules' files are: the tail of the path first, then
    how alike the two file names read, then the head of the path.

    The middle term is the one that earns its place. A package that
    renumbers its migrations offers a file per number with the same one
    class in each, so every other signal ties, and only `0003_widget.py`
    reading like `0004_widget.py` says which became which.
    """
    a, b = _path(old).parts, _path(cand).parts
    tail = 0
    for x, y in zip(reversed(a), reversed(b), strict=False):
        if x != y:
            break
        tail += 1
    head = 0
    for x, y in zip(a, b, strict=False):
        if x != y:
            break
        head += 1
    return (tail, int(_alike(a[-1] if a else "", b[-1] if b else "") * 1000), head)


def _first(score: tuple[int, int, int]) -> tuple[int, int, int]:
    """The sort key that puts the likeliest pairing first."""
    return (-score[0], -score[1], -score[2])


def _alike(a: str, b: str) -> float:
    """How alike two file names read, between 0 and 1."""
    return SequenceMatcher(None, a, b).ratio()


def _overlap(a: set[str], b: set[str]) -> float:
    """The share of the two surfaces' names that both of them have."""
    union = a | b
    return len(a & b) / len(union) if union else 0.0


@dataclass(frozen=True)
class Pair:
    """One old module and one new candidate, with their public names."""

    old: dict[str, Any]
    new: dict[str, Any]
    old_names: set[str]
    new_names: set[str]


def _same_content(p: Pair) -> bool:
    # The same source is strong evidence, except where there is no source
    # to speak of: two empty modules are alike for a reason that says
    # nothing about which is which, so their file names must agree.
    same_file_name = _path(p.old).name == _path(p.new).name
    return p.old["sha"] == p.new["sha"] and (bool(p.old_names) or same_file_name)


def _same_names(p: Pair) -> bool:
    return bool(p.old_names) and p.new_names == p.old_names


def _renamed_and_edited(p: Pair) -> bool:
    # A module renamed and edited in the same commit answers neither
    # question above: its source changed and so did its surface. What is
    # left is how much of the surface survived and how alike the two file
    # names read.
    if not p.old_names or not p.new_names:
        return False
    alike = _alike(_path(p.old).name, _path(p.new).name) >= NAME_ALIKE
    return alike and _overlap(p.old_names, p.new_names) >= SURFACE_OVERLAP


# The three questions, the strongest first, and how a pairing is reported.
QUESTIONS: tuple[tuple[Callable[[Pair], bool], str], ...] = (
    (_same_content, "same content"),
    (_same_names, "same public names"),
    (_renamed_and_edited, "a file name that reads the same and most of the same names"),
)


def _assign(
    pairs: list[tuple[tuple[int, int, int], str, str]],
    how: str,
    out: dict[str, tuple[str, str]],
    taken: set[str],
) -> None:
    """The best-scored pairings first; each old and each new module once."""
    for _score, old, cand in sorted(pairs, key=lambda p: (_first(p[0]), p[1], p[2])):
        if old in out or cand in taken:
            continue
        out[old] = (cand, how)
        taken.add(cand)


def find(
    base: dict[str, Any], head: dict[str, Any], gone: list[str], new: list[str]
) -> dict[str, tuple[str, str]]:
    """old module -> (new module, how it was recognised), for every move.

    Three questions, the strongest first: the same source (the extractor's
    sha), then the same public names, then a file name that reads the same
    and most of the same names. Each new module is matched once.

    Every pairing a question admits is scored by `_affinity` and the best
    is taken, because a question can admit a great many at once. When a
    package moves to a src layout, every empty `__init__.py` in it has the
    same source as every other, and pairing each old module with the first
    free candidate walks the whole set one place along, so each card is
    told to rename its claim to its neighbour's module. Measured on the
    renames git reports in five repositories, taking the best pairing
    rather than the first turned 27 such wrong lines into 12.
    """
    surface = {m: public_names(r) for m, r in list(base.items()) + list(head.items())}
    out: dict[str, tuple[str, str]] = {}
    taken: set[str] = set()
    for admits, how in QUESTIONS:
        pairs = [
            (_affinity(base[o], head[c]), o, c)
            for o in gone
            if o not in out
            for c in new
            if c not in taken and admits(Pair(base[o], head[c], surface[o], surface[c]))
        ]
        _assign(pairs, how, out, taken)
    return out


# No moves told from outside: the default for `told`, read-only.
NO_MOVES: Mapping[str, tuple[str, str]] = MappingProxyType({})


def with_told(
    found: dict[str, tuple[str, str]],
    told: Mapping[str, tuple[str, str]],
    gone: list[str],
    new: list[str],
) -> dict[str, tuple[str, str]]:
    """The moves found, and the moves told from outside (`delta --jev`) for modules
    the three questions left unpaired, each new module taken once."""
    out = dict(found)
    taken = {c for c, _ in found.values()}
    for old, (cand, how) in told.items():
        if old in gone and old not in out and cand in new and cand not in taken:
            out[old] = (cand, how)
            taken.add(cand)
    return out
