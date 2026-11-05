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
of such an object in other ways after a claim was read from it. `clear` removes the
kept indexes, and the tests call it before each test. Other iterables get an index for
one call only.
"""

from __future__ import annotations

import bisect
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, TypeVar

LIMIT = 4  # the number of module collections that keep an index: the 4 used last

T = TypeVar("T")
_kept: list[tuple[object, int, str, Any]] = []  # source, size, kind, value


def clear() -> None:
    """Remove each kept index."""
    _kept.clear()


def kept_for(source: Any, kind: str, build: Callable[[Any], T]) -> T:
    """Give the value that `build` makes from a module collection, kept for the 4 last used.

    The value is kept while the same list, tuple or mapping is used and its size does not
    change. Other iterables get a new value for each call."""
    if not isinstance(source, (Mapping, list, tuple)):
        return build(source)
    size = len(source)
    for i, (held, held_size, held_kind, value) in enumerate(_kept):
        if held is source and held_size == size and held_kind == kind:
            _kept.append(_kept.pop(i))  # the last used value goes to the end
            return value  # type: ignore[no-any-return]
    value = build(source)
    _kept.append((source, size, kind, value))
    del _kept[:-LIMIT]
    return value


def is_symbol(pattern: str) -> bool:
    """True when an implemented_by value is a symbol claim in pkg.mod:name form.

    `model.is_symbol` is this function."""
    return ":" in pattern


def package_fact(module: str, records: object) -> str | None:
    """Give the `package` fact of the module, or None when it is not known.

    The records are the module records of the facts (`facts["components"]`). A list of
    module names, a missing record, or a record of an older extraction gives None.
    `model.package_fact` is this function."""
    record = records.get(module) if isinstance(records, Mapping) else None
    package = record.get("package") if isinstance(record, Mapping) else None
    return package if isinstance(package, str) and package else None


@dataclass(frozen=True)
class _Index:
    names: list[str]
    position: dict[str, list[int]]  # a list keeps each copy of a name that occurs twice
    keys: list[str]  # sorted keys: the package fact, or the module name without one
    key_positions: list[int]  # the position of the module of each key, in key order


def _build(modules: Iterable[str]) -> _Index:
    names = list(modules)
    records = modules if isinstance(modules, Mapping) else None
    position: dict[str, list[int]] = {}
    pairs: list[tuple[str, int]] = []
    for i, module in enumerate(names):
        position.setdefault(module, []).append(i)
        package = package_fact(module, records)
        pairs.append((package if package is not None else module, i))
    pairs.sort()
    return _Index(names, position, [k for k, _ in pairs], [i for _, i in pairs])


def _wildcard(index: _Index, head: str) -> set[int]:
    """The module `head`, a module whose package is `head`, and each key below `head.`."""
    out = set(index.position.get(head, ()))
    keys = index.keys
    same = range(bisect.bisect_left(keys, head), bisect.bisect_right(keys, head))
    # A key equal to `head` is a package fact `head`, or the module `head` itself.
    out.update(index.key_positions[j] for j in same)
    prefix = head + "."
    for j in range(bisect.bisect_left(keys, prefix), len(keys)):
        if not keys[j].startswith(prefix):
            break
        out.add(index.key_positions[j])
    return out


def claimed(patterns: Sequence[str], modules: Iterable[str]) -> list[str]:
    """Give the modules that the patterns cover, in the order of `modules`."""
    index = kept_for(modules, "claims", _build)
    found: set[int] = set()
    for pattern in patterns:
        if is_symbol(pattern):
            continue
        if pattern.endswith(".*"):
            found |= _wildcard(index, pattern[:-2])
        else:
            found.update(index.position.get(pattern, ()))
    return [index.names[i] for i in sorted(found)]


def kept() -> list[Any]:
    """Give the kept values, for tests."""
    return [value for _, _, _, value in _kept]
