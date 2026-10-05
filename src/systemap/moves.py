"""The move detector pairs removed modules with added modules.

It compares source content, then public names, then file names and public-name overlap.
A weak same-name pair remains a candidate for source examination. External answers can
add unpaired moves.
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
    """This function reads the module file path from its facts record."""
    return PurePosixPath(str(record.get("file", "")))


def _affinity(old: dict[str, Any], cand: dict[str, Any]) -> tuple[int, int, int]:
    """This function compares path endings, file names, and path starts for move ranking."""
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
    """This function gives the sort key for a module pair."""
    return (-score[0], -score[1], -score[2])


def _alike(a: str, b: str) -> float:
    """This function calculates file-name similarity on the interval from 0 to 1."""
    return SequenceMatcher(None, a, b).ratio()


def _overlap(a: set[str], b: set[str]) -> float:
    """This function calculates the fraction of public names common to both modules."""
    union = a | b
    return len(a & b) / len(union) if union else 0.0


@dataclass(frozen=True)
class Pair:
    """This record contains one removed module, one added candidate, and their public
    names.
    """

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
    return (
        bool(p.old_names)
        and p.new_names == p.old_names
        and _alike(_path(p.old).name, _path(p.new).name) >= NAME_ALIKE
    )


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
    (_renamed_and_edited, "the same file name and most of the same public names"),
)


def _assign(
    pairs: list[tuple[tuple[int, int, int], str, str]],
    how: str,
    out: dict[str, tuple[str, str]],
    taken: set[str],
) -> None:
    """This function selects pairs in score order, with each old and new module in one pair
    only.
    """
    for _score, old, cand in sorted(pairs, key=lambda p: (_first(p[0]), p[1], p[2])):
        if old in out or cand in taken:
            continue
        out[old] = (cand, how)
        taken.add(cand)


def find(
    base: dict[str, Any], head: dict[str, Any], gone: list[str], new: list[str]
) -> dict[str, tuple[str, str]]:
    """This function pairs module moves by source identity, public-name identity, and
    file-name similarity.

    The result gives each removed module, its new name, and the identification method.
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


def candidates(
    base: dict[str, Any],
    head: dict[str, Any],
    gone: list[str],
    new: list[str],
    confirmed: Mapping[str, tuple[str, str]],
) -> dict[str, tuple[str, ...]]:
    """This function keeps all weak same-name pairs as candidates for source examination."""
    taken = {name for name, _how in confirmed.values()}
    out: dict[str, tuple[str, ...]] = {}
    for old in gone:
        if old in confirmed:
            continue
        names = public_names(base[old])
        if not names:
            continue
        alternatives = tuple(
            sorted(cand for cand in new if cand not in taken and public_names(head[cand]) == names)
        )
        if alternatives:
            out[old] = alternatives
    return out


# No moves told from outside: the default for `told`, read-only.
NO_MOVES: Mapping[str, tuple[str, str]] = MappingProxyType({})


def with_told(
    found: dict[str, tuple[str, str]],
    told: Mapping[str, tuple[str, str]],
    gone: list[str],
    new: list[str],
) -> dict[str, tuple[str, str]]:
    """This function adds external move answers for unpaired modules. Each new module can
    occur in one pair only.
    """
    out = dict(found)
    taken = {c for c, _ in found.values()}
    for old, (cand, how) in told.items():
        if old in gone and old not in out and cand in new and cand not in taken:
            out[old] = (cand, how)
            taken.add(cand)
    return out
