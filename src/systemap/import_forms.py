"""The import forms tell when the imports of a module operate (facts format 15).

A language adapter gives the form of each import statement:

- `load`: the import operates when the module loads.
- `call`: the import operates in a function body, when the function operates.
- `type`: the import operates only for type checks. It never operates at run time.

The module record keeps the forms in `import_forms`, a sparse map: a target module whose
only form is `load` is not in the map. Thus the map is empty for most modules, and a
reader that does not know the key gets the earlier meaning of `uses`. The record keeps
each import by a string value in `dynamic_imports`. These records do not change `uses`.

An adapter writes `type` only when the import can never operate at run time. When the
adapter is not sure, it writes `load`. Thus a false `type` form is the only adapter error
that can hide an import from a check.

This module reads no language name and no file suffix.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from systemap.terminal_text import has_control

LOAD, CALL, TYPE = "load", "call", "type"
FORMS = (CALL, LOAD, TYPE)
# The import details that an adapter can give (`LanguageAdapter.import_details`).
DETAILS = ("call", "dynamic", "type")
# The keys of each record in `dynamic_imports`.
DYNAMIC_KEYS = ("call", "text", "target", "line")


@dataclass(frozen=True)
class ImportFacts:
    """The import forms and the imports by a string value of one module.

    `forms` gives the forms of each target module that the adapter finds. `dynamic` gives
    the records of `dynamic_imports`."""

    forms: Mapping[str, tuple[str, ...]]
    dynamic: tuple[Mapping[str, Any], ...]


# The facts of an adapter that gives no import details.
NONE = ImportFacts({}, ())


def forms(record: Mapping[str, Any] | None, target: str) -> tuple[str, ...]:
    """Give the forms of the imports of `target` in the module record.

    A target that is not in `import_forms` has the form `load`. A key of `import_forms`
    that is not in `uses` is ignored."""
    if not isinstance(record, Mapping):
        return (LOAD,)
    stored = record.get("import_forms")
    uses = record.get("uses")
    if not isinstance(stored, Mapping) or not isinstance(uses, Mapping) or target not in uses:
        return (LOAD,)
    found = stored.get(target)
    if not isinstance(found, list) or not found:
        return (LOAD,)
    return tuple(str(form) for form in found)


def runtime(record: Mapping[str, Any] | None, target: str) -> bool:
    """Tell if an import of `target` can operate at run time: it has a form that is not
    `type`. A missing record gives True."""
    return any(form != TYPE for form in forms(record, target))


def deferred(record: Mapping[str, Any] | None, target: str) -> bool:
    """Tell if each import of `target` operates only in a function body."""
    return forms(record, target) == (CALL,)


def normal(found: ImportFacts, uses: Mapping[str, Any]) -> dict[str, list[str]]:
    """Give the stored `import_forms` map: sorted forms without duplicates, only for the
    targets of `uses`, and without the targets whose only form is `load`."""
    out: dict[str, list[str]] = {}
    for target in sorted(found.forms):
        kept = sorted({form for form in found.forms[target] if form in FORMS})
        if target in uses and kept and kept != [LOAD]:
            out[target] = kept
    return out


def dynamic_records(record: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Give the `dynamic_imports` records of a module record, or an empty list."""
    stored = record.get("dynamic_imports") if isinstance(record, Mapping) else None
    if not isinstance(stored, list):
        return []
    return [dict(item) for item in stored if isinstance(item, Mapping)]


def stored_dynamic(found: ImportFacts) -> list[dict[str, Any]]:
    """Give the stored `dynamic_imports` list: by line, then call, then text.

    A text with a control character becomes an empty text, as for a value that is not a
    fixed string, because a row below a finding line can contain the text."""
    rows = []
    for item in found.dynamic:
        row = {key: item[key] for key in DYNAMIC_KEYS}
        if has_control(row["text"]):
            row["text"] = row["target"] = ""
        rows.append(row)
    return sorted(rows, key=lambda row: (row["line"], row["call"], row["text"]))
