"""Find the modules that implemented_by patterns cover, with an index of the modules.

`model.claimed` compared each pattern with each module. On a tree of 50 maps and about
1,900 modules, one build of the canvas data made 20 million comparisons
(bench/jev/README.md). The index gives the same modules in the same order:

- An exact module name is one dictionary lookup.
- A `head.*` pattern gives the module `head`, and each module whose key starts with
  `head.`, from a sorted list of keys. The key of a module is its `package` fact, or the
  module name when the module has no such fact. A module whose `package` fact is `head`
  is also covered. These are the rules of `model.module_matches`.
- A symbol claim (`pkg.mod:name`) covers no module.

A list, a tuple or a mapping of modules keeps its index while it is one of the 4
collections used last. The index holds the object, so its identity cannot go to a
different object, and the object stays in memory while its index is kept. A change of
the number of modules makes a new index. The caller must not change the module records
of such an object in other ways after a claim was read from it. `evidence.clear_evidence`
and `clear` remove the kept indexes. Other iterables get an index for one call only.
"""

from __future__ import annotations

import bisect
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

LIMIT = 4  # the number of module collections that keep an index: the 4 used last


@dataclass(frozen=True)
class _Index:
    source: object
    size: int
    names: list[str]
    position: dict[str, list[int]]  # a list keeps each copy of a name that occurs twice
    keys: list[str]  # sorted keys
    key_positions: list[int]  # the position of the module of each key, in key order
    in_package: dict[str, list[int]]  # package fact to positions


_kept: list[_Index] = []


def clear() -> None:
    """Remove each kept index."""
    _kept.clear()


def package_fact(module: str, records: object) -> str | None:
    """Give the `package` fact of the module, or None when it is not known.

    The records are the module records of the facts (`facts["components"]`). A list of
    module names, a missing record, or a record of an older extraction gives None.
    `model.package_fact` is this function."""
    record = records.get(module) if isinstance(records, Mapping) else None
    package = record.get("package") if isinstance(record, Mapping) else None
    return package if isinstance(package, str) and package else None


def _build(modules: Iterable[str], source: object) -> _Index:
    names = list(modules)
    records = source if isinstance(source, Mapping) else None
    pairs: list[tuple[str, int]] = []
    in_package: dict[str, list[int]] = {}
    for i, module in enumerate(names):
        package = package_fact(module, records)
        pairs.append((package if package is not None else module, i))
        if package is not None:
            in_package.setdefault(package, []).append(i)
    pairs.sort()
    return _Index(
        source=source,
        size=len(names),
        names=names,
        position=_positions(names),
        keys=[k for k, _ in pairs],
        key_positions=[i for _, i in pairs],
        in_package=in_package,
    )


def _positions(names: list[str]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for i, name in enumerate(names):
        out.setdefault(name, []).append(i)
    return out


def _index(modules: Iterable[str]) -> _Index:
    if not isinstance(modules, (Mapping, list, tuple)):
        return _build(modules, modules)
    size = len(modules)
    for i, found in enumerate(_kept):
        if found.source is modules and found.size == size:
            _kept.append(_kept.pop(i))  # the last used index goes to the end
            return found
    made = _build(modules, modules)
    _kept.append(made)
    del _kept[:-LIMIT]
    return made


def _wildcard(index: _Index, head: str) -> set[int]:
    out: set[int] = set()
    out.update(index.position.get(head, ()))
    out.update(index.in_package.get(head, ()))
    prefix = head + "."
    start = bisect.bisect_left(index.keys, prefix)
    for j in range(start, len(index.keys)):
        if not index.keys[j].startswith(prefix):
            break
        out.add(index.key_positions[j])
    return out


def claimed(patterns: Sequence[str], modules: Iterable[str]) -> list[str]:
    """Give the modules that the patterns cover, in the order of `modules`."""
    index = _index(modules)
    found: set[int] = set()
    for pattern in patterns:
        if ":" in pattern:
            continue
        if pattern.endswith(".*"):
            found |= _wildcard(index, pattern[:-2])
        else:
            found.update(index.position.get(pattern, ()))
    return [index.names[i] for i in sorted(found)]


def kept() -> list[Any]:
    """Give the kept indexes, for tests."""
    return list(_kept)
