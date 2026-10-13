"""The field check compares each value of a loaded model with the type of its field.

The model classes are dataclasses, and a dataclass does not examine its values. Thus a
model file can give a string where a Component must be. Without this check, a command
can stop with an AttributeError after the model loads. The check uses the types that the
model classes give for their fields. It accepts a list where the type is a tuple,
because the model file reader accepts the two forms. It does not examine a type that it
does not know.

After the check, `checked` puts a tuple in place of each list in a field of tuple type.
Thus a command can join a loaded field to a tuple, as it can join a field of a model
that Python code makes.
"""

from __future__ import annotations

import dataclasses
import functools
import types
import typing
from collections.abc import Mapping
from typing import Any

from systemap import model_names
from systemap.model import Meaning, Model

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


def checked(model: Model, meaning: Meaning) -> tuple[str, Model, Meaning]:
    """Give the first problem of the loaded MODEL and MEANING values, and the two values.

    If there is no problem, each list in a field of tuple type is a tuple in the values.
    A name that the page cannot use (`model_names`) is also a problem."""
    found = problem(model, Model, "MODEL") or problem(meaning, Meaning, "MEANING")
    found = found or model_names.problem(model, meaning)
    if found:
        return found, model, meaning
    return "", _tuples(model, Model), _tuples(meaning, Meaning)


def _tuples(value: Any, hint: Any) -> Any:
    """Give the value with a tuple in place of each list of a tuple type.

    The value must agree with its type (`problem`). A value without a list is the same
    object."""
    if isinstance(hint, type) and dataclasses.is_dataclass(hint):
        return _record_tuples(value, hint)
    origin, args = typing.get_origin(hint), typing.get_args(hint)
    if origin in (typing.Union, types.UnionType):
        return next((_tuples(value, a) for a in args if not problem(value, a, "")), value)
    if origin is tuple:
        return _tuple_tuples(value, args)
    if origin in (Mapping, dict) and len(args) == 2:
        return _mapping_tuples(value, args[1])
    return value


def _mapping_tuples(value: Any, hint: Any) -> Any:
    items = {key: _tuples(item, hint) for key, item in value.items()}
    return value if all(items[key] is item for key, item in value.items()) else items


def _record_tuples(value: Any, cls: type) -> Any:
    hints = _hints(cls)
    old = {item.name: getattr(value, item.name) for item in dataclasses.fields(cls)}
    new = {name: _tuples(item, hints[name]) for name, item in old.items()}
    changed = {name: item for name, item in new.items() if item is not old[name]}
    return dataclasses.replace(value, **changed) if changed else value


def _tuple_tuples(value: Any, args: tuple[Any, ...]) -> Any:
    members = [args[0]] * len(value) if args[1:] == (Ellipsis,) else list(args)
    items = tuple(_tuples(item, hint) for item, hint in zip(value, members, strict=True))
    same = isinstance(value, tuple) and all(a is b for a, b in zip(items, value, strict=True))
    return value if same else items


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
