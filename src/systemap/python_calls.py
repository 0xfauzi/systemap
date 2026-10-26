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

from systemap import python_tree
from systemap.call_sites import IMPORT, VALUE, WHOLE, Binding, records
from systemap.python_imports import relative_source

RECEIVER = "self"
FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def _in_package(name: str, prefixes: Iterable[str]) -> bool:
    return any(name == p or name.startswith(p + ".") for p in prefixes)


def _resolve(name: str, known: set[str]) -> str | None:
    """Give the module of an import source, or None if it is not in the inventory.

    Exact membership only: the package of an absent module is not its target. The import
    of an absent module is an unresolved import (`python_imports.python_unresolved`)."""
    return name if name in known else None


def import_targets(
    tree: ast.AST, prefixes: set[str], known: set[str], module: str = "", is_package: bool = False
) -> Iterator[tuple[ast.AST, str, str, str, int]]:
    """Give each local import as (statement, local name, target module, imported name, line).

    The imported name is `*` for a whole-module import. A `from m import *` statement
    gives the local name `*`. Relative imports use the module and its package state. Only
    targets in the module inventory are given.
    """
    for node in python_tree.walk(tree):
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
        for node in python_tree.walk(tree):
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

    def in_class_body(self, node: ast.AST) -> bool:
        return isinstance(self.parent.get(node), ast.ClassDef)


class _Visible:
    """Give the import binding of a local name that a use at one node reads.

    A binding in the innermost function that contains the node hides a binding of the
    same name in an outer function or in the module. In one scope, the last binding is
    kept. The order of a name is the position of its first binding that the use can
    read. If two names agree with a value, the name with the lower order applies.
    The index of the bindings by local name keeps the work for each assignment small.
    Thus a module with many imports and many assignments is not slow.
    """

    def __init__(self, imports: _Imports, functions: list[ast.AST]):
        self.index = imports.index
        self.parts = imports.parts
        self.functions = functions

    def get(self, local: str) -> tuple[int, Binding] | None:
        """Give the order and the binding of the local name, or None."""
        found: tuple[int, int, Binding] | None = None
        for order, binding in self.index.get(local, ()):
            rank = _rank(self.functions, binding)
            if rank is None:
                continue
            if found is None or rank <= found[1]:
                found = (order if found is None else found[0], rank, binding)
        return None if found is None else (found[0], found[2])


class _Imports:
    """Index the import bindings by local name, with their positions in the list.

    `parts` is the largest number of dotted parts in a local name, such as 2 for `a.b`.
    """

    def __init__(self, imports: list[Binding]) -> None:
        self.index: dict[str, list[tuple[int, Binding]]] = {}
        for order, binding in enumerate(imports):
            self.index.setdefault(binding.local, []).append((order, binding))
        self.parts = max((local.count(".") + 1 for local in self.index), default=0)


def _rank(functions: list[ast.AST], binding: Binding) -> int | None:
    """Give the depth of the scope of the binding from a use: 0 for the innermost function
    of the use. A module binding is after all functions. None: the use cannot read it."""
    if binding.scope is None:
        return len(functions)
    for rank, function in enumerate(functions):
        if function is binding.scope:
            return rank
    return None


def _root(value: ast.AST | None, imports: _Visible) -> tuple[Binding, str] | None:
    """Give the import binding at the root of a value, and the imported name it gives.

    A local name agrees with the value text if it is equal to the text, or to a part of
    the text before a period."""
    while isinstance(value, ast.Await | ast.Call):
        value = value.value if isinstance(value, ast.Await) else value.func
    text = _dotted(value) if value is not None else None
    if text is None:
        return None
    parts = text.split(".")
    found = [
        (hit, size)
        for size in range(1, min(len(parts), imports.parts) + 1)
        if (hit := imports.get(".".join(parts[:size]))) is not None
    ]
    if not found:
        return None
    (_order, binding), size = min(found, key=lambda item: item[0][0])
    if size == len(parts):
        return binding, binding.name
    return binding, parts[size] if binding.name == WHOLE else binding.name


def _annotation_root(annotation: ast.AST | None, imports: _Visible) -> tuple[Binding, str] | None:
    if annotation is None:
        return None
    for node in ast.walk(annotation):
        found = _annotation_part(node, imports)
        if found:
            return found
    return None


def _annotation_part(node: ast.AST, imports: _Visible) -> tuple[Binding, str] | None:
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
    imports: _Imports,
) -> Binding | None:
    target, value, annotation = bound
    local = target.arg if isinstance(target, ast.arg) else _dotted(target)
    visible = _Visible(imports, reader.functions(node))
    found = _root(value, visible) or _annotation_root(annotation, visible)
    if not local or not found or visible.get(local) is not None:
        return None
    if reader.in_class_body(node) and isinstance(target, ast.Name):
        local = f"{RECEIVER}.{local}"
    scope = reader.scope(node) if "." not in local else None
    root, name = found
    return Binding(local, root.target, name, VALUE, int(getattr(node, "lineno", 0)), scope)


def _value_bindings(reader: _Reader, imports: list[Binding]) -> list[Binding]:
    index = _Imports(imports)
    found = (
        _value_binding(reader, node, bound, index)
        for node in python_tree.walk(reader.tree)
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
    """Add each use to the bindings of its name in the innermost scope that has one."""
    for node in python_tree.walk(reader.tree):
        if not isinstance(node, ast.Name | ast.Attribute) or isinstance(node.ctx, ast.Store):
            continue
        candidates = bindings.get(_dotted(node) or "", [])
        if candidates:
            for binding in _nearest(reader.functions(node), candidates):
                binding.uses.add(_use(reader, node))


def _nearest(functions: list[ast.AST], candidates: list[Binding]) -> list[Binding]:
    """Give the bindings of the innermost scope that a use in `functions` can read."""
    ranked = [(_rank(functions, binding), binding) for binding in candidates]
    reached = [(rank, binding) for rank, binding in ranked if rank is not None]
    nearest = min((rank for rank, _binding in reached), default=None)
    return [binding for rank, binding in reached if rank == nearest]


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
    tree = python_tree.tree(raw)
    if tree is None:
        return None
    reader = _Reader(tree)
    # One binding for each scope and local name. An import in one function does not
    # replace an import of the same name in a different function.
    imports: dict[tuple[int, str], Binding] = {}
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
            binding = Binding(each, each_target, each_name, IMPORT, each_line, scope)
            imports[id(scope), each] = binding
    values = _value_bindings(reader, list(imports.values()))
    by_local: dict[str, list[Binding]] = {}
    for binding in [*imports.values(), *values]:
        by_local.setdefault(binding.local, []).append(binding)
    _add_uses(reader, by_local)
    return records([*imports.values(), *values], module)
