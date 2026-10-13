"""The Python call-site reader writes the `call_sites` fact for the Python adapter.

It also gives the target module of each Python import, for the `uses` fact. The two
facts thus use the same import resolution.

A call site is a local name that an import statement makes, or a local name that gets
its value from an imported name. The fact gives each line that uses the local name.
For each use, it also gives the line of the function that contains the use, and the
attribute that the use reads.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator, Mapping
from typing import Any

from systemap.call_sites import IMPORT, VALUE, WHOLE, Binding, records
from systemap.python_imports import relative_source

RECEIVER = "self"
FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def _in_package(name: str, prefixes: Iterable[str]) -> bool:
    return any(name == p or name.startswith(p + ".") for p in prefixes)


def _resolve(name: str, known: set[str]) -> str | None:
    parts = name.split(".")
    while parts:
        candidate = ".".join(parts)
        if candidate in known:
            return candidate
        parts.pop()
    return None


def import_targets(
    tree: ast.AST, prefixes: set[str], known: set[str], module: str = "", is_package: bool = False
) -> Iterator[tuple[ast.AST, str, str, str, int]]:
    """Give each local import as (statement, local name, target module, imported name, line).

    The imported name is `*` for a whole-module import. A `from m import *` statement
    gives the local name `*`. Relative imports use the module and its package state. Only
    targets in the module inventory are given.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from _plain_targets(node, prefixes, known)
        elif isinstance(node, ast.ImportFrom):
            yield from _from_targets(node, prefixes, known, module, is_package)


def _plain_targets(
    node: ast.Import, prefixes: set[str], known: set[str]
) -> Iterator[tuple[ast.AST, str, str, str, int]]:
    for alias in node.names:
        target = _resolve(alias.name, known) if _in_package(alias.name, prefixes) else None
        if target:
            yield node, alias.asname or alias.name, target, WHOLE, alias.lineno


def _from_targets(
    node: ast.ImportFrom, prefixes: set[str], known: set[str], module: str, is_package: bool
) -> Iterator[tuple[ast.AST, str, str, str, int]]:
    if node.level:
        src = relative_source(module, is_package, node.level, node.module or "")
        if not module or src is None:
            return
    elif node.module:
        src = node.module
    else:
        return
    if not _in_package(src, prefixes):
        return
    base = _resolve(src, known)
    for alias in node.names:
        local = alias.asname or alias.name
        # Exact membership only: a class name must not resolve to its module.
        if alias.name != WHOLE and f"{src}.{alias.name}" in known:
            yield node, local, f"{src}.{alias.name}", WHOLE, alias.lineno
        elif base:
            yield node, local, base, alias.name, alias.lineno


def _dotted(node: ast.AST) -> str | None:
    """Give `a.b.c` for a name or an attribute chain on a name, else None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        head = _dotted(node.value)
        return f"{head}.{node.attr}" if head else None
    return None


class _Reader:
    """Find the bindings and the uses in one parsed module."""

    def __init__(self, tree: ast.AST) -> None:
        self.parent: dict[ast.AST, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                self.parent[child] = node
        self.tree = tree

    def functions(self, node: ast.AST) -> list[ast.AST]:
        """Give the named functions that contain the node, innermost first."""
        out: list[ast.AST] = []
        current = self.parent.get(node)
        while current is not None:
            if isinstance(current, FUNCTIONS) and self.function_line(current):
                out.append(current)
            current = self.parent.get(current)
        return out

    def function_line(self, node: ast.AST) -> int:
        """Give the line of a named function: a `def`, or a lambda that an assignment names."""
        if isinstance(node, ast.Lambda):
            above = self.parent.get(node)
            return above.lineno if isinstance(above, ast.Assign) else 0
        return int(getattr(node, "lineno", 0))

    def scope(self, node: ast.AST) -> ast.AST | None:
        found = self.functions(node)
        return found[0] if found else None

    def in_scope(self, binding: Binding, node: ast.AST) -> bool:
        return binding.scope is None or binding.scope in self.functions(node)

    def in_class_body(self, node: ast.AST) -> bool:
        return isinstance(self.parent.get(node), ast.ClassDef)


def _root(value: ast.AST | None, imports: dict[str, Binding]) -> tuple[Binding, str] | None:
    """Give the import binding at the root of a value, and the imported name it gives."""
    while isinstance(value, ast.Await | ast.Call):
        value = value.value if isinstance(value, ast.Await) else value.func
    text = _dotted(value) if value is not None else None
    if text is None:
        return None
    for local, binding in imports.items():
        if text == local:
            return binding, binding.name
        if text.startswith(local + "."):
            rest = text[len(local) + 1 :].split(".")[0]
            return binding, rest if binding.name == WHOLE else binding.name
    return None


def _annotation_root(
    annotation: ast.AST | None, imports: dict[str, Binding]
) -> tuple[Binding, str] | None:
    if annotation is None:
        return None
    for node in ast.walk(annotation):
        found = _annotation_part(node, imports)
        if found:
            return found
    return None


def _annotation_part(node: ast.AST, imports: dict[str, Binding]) -> tuple[Binding, str] | None:
    """Read one part of an annotation. A string annotation is parsed as an expression."""
    if isinstance(node, ast.Name | ast.Attribute):
        return _root(node, imports)
    if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
        return None
    try:
        return _annotation_root(ast.parse(node.value, mode="eval").body, imports)
    except (SyntaxError, ValueError):
        return None


def _value_targets(node: ast.AST) -> list[tuple[ast.AST, ast.AST | None, ast.AST | None]]:
    """Give (target, value, annotation) for each binding statement or argument."""
    if isinstance(node, ast.Assign):
        return [(t, node.value, None) for t in node.targets]
    if isinstance(node, ast.AnnAssign):
        return [(node.target, node.value, node.annotation)]
    if isinstance(node, ast.arg):
        return [(node, None, node.annotation)]
    return []


def _value_binding(
    reader: _Reader,
    node: ast.AST,
    bound: tuple[ast.AST, ast.AST | None, ast.AST | None],
    imports: dict[str, Binding],
) -> Binding | None:
    target, value, annotation = bound
    local = target.arg if isinstance(target, ast.arg) else _dotted(target)
    found = _root(value, imports) or _annotation_root(annotation, imports)
    if not local or not found or local in imports:
        return None
    if reader.in_class_body(node) and isinstance(target, ast.Name):
        local = f"{RECEIVER}.{local}"
    scope = reader.scope(node) if "." not in local else None
    root, name = found
    return Binding(local, root.target, name, VALUE, int(getattr(node, "lineno", 0)), scope)


def _value_bindings(reader: _Reader, imports: dict[str, Binding]) -> list[Binding]:
    found = (
        _value_binding(reader, node, bound, imports)
        for node in ast.walk(reader.tree)
        for bound in _value_targets(node)
    )
    return [b for b in found if b is not None]


def _use(reader: _Reader, node: ast.AST) -> tuple[int, int, str]:
    """Give the line of a use, the line of its function (0 for none), and its attribute."""
    above = reader.parent.get(node)
    member = above.attr if isinstance(above, ast.Attribute) else ""
    functions = reader.functions(node)
    line = reader.function_line(functions[0]) if functions else 0
    return int(getattr(node, "lineno", 0)), line, member


def _add_uses(reader: _Reader, bindings: dict[str, list[Binding]]) -> None:
    for node in ast.walk(reader.tree):
        if not isinstance(node, ast.Name | ast.Attribute) or isinstance(node.ctx, ast.Store):
            continue
        for binding in bindings.get(_dotted(node) or "", []):
            if reader.in_scope(binding, node):
                binding.uses.add(_use(reader, node))


def _star_bindings(
    node: ast.AST, target: str, line: int, components: Mapping[str, Mapping[str, Any]]
) -> list[tuple[ast.AST, str, str, str, int]]:
    names = components.get(target, {}).get("names", [])
    public = [str(n["name"]) for n in names if n.get("star_export", True)]
    return [(node, name, target, name, line) for name in public]


def call_sites(
    raw: str,
    prefixes: set[str],
    known: set[str],
    components: Mapping[str, Mapping[str, Any]],
    module: str = "",
    is_package: bool = False,
) -> list[dict[str, Any]] | None:
    """Give the call-site records of one module, or None if the source does not parse."""
    try:
        tree = ast.parse(raw)
    except (SyntaxError, ValueError):
        return None
    reader = _Reader(tree)
    imports: dict[str, Binding] = {}
    for node, local, target, name, line in import_targets(
        tree, prefixes, known, module, is_package
    ):
        found = (
            _star_bindings(node, target, line, components)
            if local == WHOLE
            else [(node, local, target, name, line)]
        )
        for _node, each, each_target, each_name, each_line in found:
            scope = reader.scope(node)
            imports[each] = Binding(each, each_target, each_name, IMPORT, each_line, scope)
    values = _value_bindings(reader, imports)
    by_local: dict[str, list[Binding]] = {}
    for binding in [*imports.values(), *values]:
        by_local.setdefault(binding.local, []).append(binding)
    _add_uses(reader, by_local)
    return records([*imports.values(), *values], module)
