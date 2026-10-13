"""The Python rules for a `from module import *` re-export.

The Python adapter writes these rules into the language-neutral name records. The shared
re-export resolver reads the records and does not examine Python source.

- A `*` re-export in a package `__init__` has `star` and `rebinds`: in Python, a later
  binding of a name replaces an earlier binding.
- A literal `__all__` gives the names of a `*` import. A public name that is not in it
  gets `star_export` set to `false`. An empty `__all__` gives no name.
- If `__all__` has a value that is not a literal list of strings, each public name gets
  `star_export` set to `null`: the adapter does not know if the name is in a `*` import.
- The `__all__` rule also applies to the names that a `*` re-export of the package gives.
  The `*` record then gets `star_export_names`, the names of a literal `__all__`, or
  `star_export` set to `null`. The shared resolver applies them, and it does not write
  them to the facts.
"""

from __future__ import annotations

import ast
from typing import Any

ALL = "__all__"
# A value that `__all__` can have, but that the adapter cannot read.
NOT_KNOWN = None
# The module has no `__all__`.
_MISSING = object()


def reexports(aliases: list[ast.alias], source: str) -> list[dict[str, Any]]:
    """This function gives the records of `from source import ...` in a package `__init__`.

    A private name is not a re-export. An alias keeps its source name in `defined_as`."""
    out: list[dict[str, Any]] = []
    for alias in aliases:
        public = alias.asname or alias.name
        if alias.name == "*":
            out.append(star_reexport(source))
        elif not public.startswith("_"):
            entry = {"name": public, "kind": "reexport", "reexport_of": source}
            if alias.asname:
                entry["defined_as"] = alias.name
            out.append(entry)
    return out


def star_reexport(source: str) -> dict[str, Any]:
    """This function gives the record of `from source import *` in a package `__init__`."""
    return {"name": "*", "kind": "reexport", "reexport_of": source, "star": True, "rebinds": True}


def mark_star_exports(statements: list[ast.stmt], names: list[dict[str, Any]]) -> None:
    """This function writes `star_export` from the `__all__` statements of a module.

    A module without `__all__` gives each public name, so no record changes."""
    listed = _all_names(statements)
    if listed is _MISSING:
        return
    for entry in names:
        if entry.get("star"):
            _mark_star(entry, listed)
            continue
        if listed is NOT_KNOWN:
            entry["star_export"] = None
        elif entry["name"] not in listed:
            entry["star_export"] = False


def _mark_star(entry: dict[str, Any], listed: Any) -> None:
    """This function writes the `__all__` rule of the package on its `*` re-export record."""
    if listed is NOT_KNOWN:
        entry["star_export"] = None
    else:
        entry["star_export_names"] = list(listed)


def _all_names(statements: list[ast.stmt]) -> Any:
    """This function gives the names in `__all__`, `_MISSING` without `__all__`, or `None`
    when the value is not a literal list of strings."""
    found: list[str] = []
    assigned = False
    for node in statements:
        value = _all_value(node)
        if value is _ABSENT:
            continue
        assigned = True
        strings = _strings(value)
        if strings is None:
            return NOT_KNOWN
        if isinstance(node, ast.Assign | ast.AnnAssign):
            found = []
        found.extend(strings)
    return tuple(found) if assigned else _MISSING


_ABSENT = object()


def _all_value(node: ast.stmt) -> Any:
    """This function gives the value that a statement gives to `__all__`, or `_ABSENT`.

    A statement that changes `__all__` in a different way gives `None`, which is not a
    literal value."""
    if isinstance(node, ast.Assign):
        return _assigned(node)
    if isinstance(node, ast.AnnAssign | ast.AugAssign):
        return _changed(node)
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        func = node.value.func
        if isinstance(func, ast.Attribute) and _is_all(func.value):
            return _call_value(func.attr, node.value)
    return _ABSENT


def _assigned(node: ast.Assign) -> Any:
    if not any(_is_all(target) for target in node.targets):
        return _ABSENT
    return node.value if len(node.targets) == 1 else None


def _changed(node: ast.AnnAssign | ast.AugAssign) -> Any:
    if not _is_all(node.target) or node.value is None:
        return _ABSENT
    if isinstance(node, ast.AugAssign) and not isinstance(node.op, ast.Add):
        return None
    return node.value


def _call_value(method: str, call: ast.Call) -> ast.expr | None:
    if method == "extend" and len(call.args) == 1 and not call.keywords:
        return call.args[0]
    if method == "append" and len(call.args) == 1 and not call.keywords:
        return ast.List(elts=[call.args[0]], ctx=ast.Load())
    return None


def _is_all(node: ast.expr) -> bool:
    return isinstance(node, ast.Name) and node.id == ALL


def _strings(value: ast.expr | None) -> list[str] | None:
    if not isinstance(value, ast.List | ast.Tuple):
        return None
    out: list[str] = []
    for item in value.elts:
        if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
            return None
        out.append(item.value)
    return out
