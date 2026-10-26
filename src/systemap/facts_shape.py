"""Examine the shape of the stored facts after `facts_file.read_facts` reads them.

A committed facts file can contain values that extraction does not write. The readers
of the facts index the fields that extraction always writes. Thus a wrong type, a
missing key, an absolute file path, or deep nesting stopped a command with a traceback.
This module finds such a file one time, after the read. `FactsError` then tells the
person to write a new facts file. `systemap refresh` and `systemap extract` do not
read the stored facts before they write a new file. Thus they can replace an incorrect
file.

The examination does not include each field. It includes the fields that the readers
index, and the type of each field that extraction writes. A key that extraction does not
write is permitted.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from systemap.config import ConfigError

# The deepest value that extraction writes has 7 levels: a use in a call site. The limit
# has space for new fields. A JSON value with more levels is not a facts file.
MAX_DEPTH = 32

# A problem is the keys from the file to the incorrect value, and the requirement that the
# value does not obey. The keys are a tuple in reverse order: each check adds the key of
# its value only if it finds a problem. Thus a correct file makes no location text.
Problem = tuple[tuple[str | int, ...], str]
# A check gives the problem of a value, or None if the value is correct.
Check = Callable[[Any], "Problem | None"]


class FactsError(ConfigError):
    """The stored facts file does not have the shape that extraction writes."""


def problem(data: Mapping[str, Any]) -> str | None:
    """Give the first shape problem of the facts, or None if the facts are correct."""
    found = depth_problem(data)
    if found:
        return found
    wrong = FACTS(data)
    return None if wrong is None else shown(wrong)


def shown(found: Problem) -> str:
    """Give the problem as text, for example `the value at ["components"]["a"]["file"]
    must be a relative path`. The location uses JSON text for each key."""
    keys, requirement = found
    if not keys:
        return f"the file {requirement}"
    where = "".join(f"[{json.dumps(key)}]" for key in reversed(keys))
    return f"the value at {where} {requirement}"


def depth_problem(data: Any) -> str | None:
    """Give a problem if the JSON value has more than `MAX_DEPTH` levels.

    The function does not use recursion. Thus a very deep value cannot stop it."""
    stack: list[tuple[Any, int]] = [(data, 1)]
    while stack:
        value, depth = stack.pop()
        if depth > MAX_DEPTH:
            return f"the JSON value has more than {MAX_DEPTH} levels"
        for child in value.values() if isinstance(value, dict) else value:
            if isinstance(child, (dict, list)):
                stack.append((child, depth + 1))
    return None


def _below(key: str | int, found: Problem | None) -> Problem | None:
    """Add the key of a value to the location of its problem."""
    return None if found is None else ((*found[0], key), found[1])


def kind(types: type, label: str) -> Check:
    """Give a check for one JSON type. A boolean is not an integer."""
    requirement = f"must be {label}"

    def check(value: Any) -> Problem | None:
        if isinstance(value, types) and (types is bool or not isinstance(value, bool)):
            return None
        return (), requirement

    return check


TEXT = kind(str, "a text value")
INTEGER = kind(int, "an integer")
BOOLEAN = kind(bool, "true or false")
OBJECT = kind(dict, "an object")
LIST = kind(list, "a list")


def relative_path(value: Any) -> Problem | None:
    """Make sure that the value is a relative file path. An absolute path, a Windows
    drive, and a UNC path are not relative."""
    if not isinstance(value, str):
        return (), "must be a text value"
    if PurePosixPath(value).is_absolute() or PureWindowsPath(value).anchor:
        return (), "must be a relative path"
    return None


def optional(inner: Check) -> Check:
    """Give a check that also accepts null."""

    def check(value: Any) -> Problem | None:
        return None if value is None else inner(value)

    return check


def list_of(item: Check) -> Check:
    """Give a check for a list. Each item must agree with `item`."""

    def check(value: Any) -> Problem | None:
        if not isinstance(value, list):
            return (), "must be a list"
        for index, entry in enumerate(value):
            found = item(entry)
            if found:
                return _below(index, found)
        return None

    return check


def map_of(item: Check) -> Check:
    """Give a check for an object. Each value must agree with `item`."""

    def check(value: Any) -> Problem | None:
        if not isinstance(value, dict):
            return (), "must be an object"
        for key, entry in value.items():
            found = item(entry)
            if found:
                return _below(key, found)
        return None

    return check


def record(required: Mapping[str, Check], permitted: Mapping[str, Check]) -> Check:
    """Give a check for an object with `required` keys and `permitted` keys.

    The object can have keys that are not in the two tables."""
    fields = [*required.items(), *permitted.items()]

    def check(value: Any) -> Problem | None:
        if not isinstance(value, dict):
            return (), "must be an object"
        for key in required:
            if key not in value:
                return (), f"has no {json.dumps(key)} key"
        for key, inner in fields:
            found = inner(value[key]) if key in value else None
            if found:
                return _below(key, found)
        return None

    return check


TEXTS = list_of(TEXT)
NAMED = record({"name": TEXT}, {})
UNKNOWN = record(
    {"reason": TEXT},
    {"line": optional(INTEGER), "source": TEXT, "parser": TEXT, "cause": TEXT},
)
CALL_SITE = record(
    {"local": TEXT, "target": TEXT, "name": TEXT, "bound": TEXT, "uses": list_of(LIST)},
    {"line": INTEGER},
)
COMPLETENESS = record(
    {},
    {
        "parsed": BOOLEAN,
        "line": INTEGER,
        "reason": TEXT,
        "cause": TEXT,
        "unresolved_imports": optional(TEXTS),
    },
)
MODULE = record(
    {
        "file": relative_path,
        "functions": list_of(NAMED),
        "classes": list_of(NAMED),
        "errors": list_of(NAMED),
        "tests_total": INTEGER,
        "tests_primary": INTEGER,
    },
    {
        "id": TEXT,
        "package": TEXT,
        "plane": TEXT,
        "sha": TEXT,
        "source_sha256": TEXT,
        "syntax_sha": TEXT,
        "tests_digest": TEXT,
        "loc": INTEGER,
        "empty_marker": BOOLEAN,
        "executes": BOOLEAN,
        "types": list_of(NAMED),
        "constants": list_of(NAMED),
        "names": list_of(NAMED),
        "api": list_of(NAMED),
        "unknown": list_of(UNKNOWN),
        "tests": TEXTS,
        "external": TEXTS,
        "imports": TEXTS,
        "imported_by": TEXTS,
        "uses": map_of(TEXTS),
        "call_sites": optional(list_of(CALL_SITE)),
        "completeness": COMPLETENESS,
        "parse_error": optional(UNKNOWN),
    },
)
ENTRY_POINT = record(
    {"kind": TEXT, "module": TEXT, "name": TEXT},
    {"target": TEXT, "label": TEXT, "symbol": TEXT, "same_as": TEXT},
)
ENTRY_ISSUE = record(
    {"kind": TEXT, "name": TEXT, "target": TEXT, "reason": TEXT},
    {"count": INTEGER, "cause": TEXT},
)
TEST_FILE_ISSUE = record({"file": relative_path, "problem": UNKNOWN}, {})
CONFIG_ISSUE = record({"file": relative_path, "reference": TEXT}, {"cause": TEXT})
FACTS = record(
    {"components": map_of(MODULE)},
    {
        "built_at_commit": TEXT,
        "packages": TEXTS,
        "provenance": OBJECT,
        "tests_dirs": TEXTS,
        "spec_sections": list_of(OBJECT),
        "entry_points": list_of(ENTRY_POINT),
        "entry_point_issues": list_of(ENTRY_ISSUE),
        "test_file_issues": list_of(TEST_FILE_ISSUE),
        "config_issues": list_of(CONFIG_ISSUE),
    },
)
