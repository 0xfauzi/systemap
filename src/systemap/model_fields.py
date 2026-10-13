"""The field check compares each value of a loaded model with the type of its field.

The model classes are dataclasses, and a dataclass does not examine its values. Thus a
model file can give a string where a Component must be. Without this check, a command
can stop with an AttributeError after the model loads. The check uses the types that the
model classes give for their fields. It accepts a list where the type is a tuple,
because the model file reader accepts the two forms. It does not examine a type that it
does not know.
"""

from __future__ import annotations

import dataclasses
import functools
import types
import typing
from collections.abc import Mapping
from typing import Any

PLAIN = {str: "a string", bool: "true or false", int: "an integer", float: "a number"}


def problem(value: Any, hint: Any, where: str) -> str:
    """Give the first value that does not agree with its type, or an empty string."""
    if isinstance(hint, type) and dataclasses.is_dataclass(hint):
        return _record(value, hint, where)
    origin = typing.get_origin(hint)
    if origin in (typing.Union, types.UnionType):
        return _union(value, hint, where)
    if origin is tuple:
        return _tuple(value, typing.get_args(hint), where)
    if origin in (Mapping, dict):
        return _mapping(value, typing.get_args(hint), where)
    return _plain(value, hint, where)


def _record(value: Any, cls: type, where: str) -> str:
    if not isinstance(value, cls):
        return _wrong(where, f"a {cls.__name__}", value)
    hints = _hints(cls)
    for item in dataclasses.fields(cls):
        found = problem(getattr(value, item.name), hints[item.name], f"{where}.{item.name}")
        if found:
            return found
    return ""


@functools.cache
def _hints(cls: type) -> dict[str, Any]:
    return typing.get_type_hints(cls)


def _union(value: Any, hint: Any, where: str) -> str:
    options = typing.get_args(hint)
    if any(not problem(value, option, where) for option in options):
        return ""
    return _wrong(where, " or ".join(_name(option) for option in options), value)


def _tuple(value: Any, args: tuple[Any, ...], where: str) -> str:
    if not isinstance(value, (tuple, list)):
        return _wrong(where, "a tuple", value)
    if len(args) == 2 and args[1] is Ellipsis:
        members = [args[0]] * len(value)
    elif len(value) != len(args):
        return f"{where} must contain {len(args)} values. It contains {len(value)} values."
    else:
        members = list(args)
    for k, (item, hint) in enumerate(zip(value, members, strict=True)):
        found = problem(item, hint, f"{where}[{k}]")
        if found:
            return found
    return ""


def _mapping(value: Any, args: tuple[Any, ...], where: str) -> str:
    if not isinstance(value, Mapping):
        return _wrong(where, "a dict", value)
    if len(args) != 2:
        return ""
    for key, item in value.items():
        found = problem(key, args[0], f"{where} key") or problem(item, args[1], f"{where}[{key!r}]")
        if found:
            return found
    return ""


def _plain(value: Any, hint: Any, where: str) -> str:
    if hint is type(None):
        return "" if value is None else _wrong(where, "None", value)
    if hint not in PLAIN:
        return ""
    if isinstance(value, bool) and hint is not bool:
        return _wrong(where, PLAIN[hint], value)
    accepted = (int, float) if hint is float else hint
    return "" if isinstance(value, accepted) else _wrong(where, PLAIN[hint], value)


def _name(hint: Any) -> str:
    if hint is type(None):
        return "None"
    if isinstance(hint, type) and dataclasses.is_dataclass(hint):
        return f"a {hint.__name__}"
    origin = typing.get_origin(hint)
    if origin is tuple:
        return "a tuple"
    if origin in (Mapping, dict):
        return "a dict"
    return PLAIN.get(hint, str(hint))


def _wrong(where: str, expected: str, value: Any) -> str:
    return f"{where} must be {expected}. The value {value!r:.60} is a {type(value).__name__}."
