"""The Python adapter gives the import forms and the imports by a string value.

The form of one `import` or `from ... import` statement comes from its position in the
syntax tree:

- `type`: the statement is in the body of `if X:`, where X is `TYPE_CHECKING`, an alias
  of it from `typing` or `typing_extensions`, or an attribute that ends in
  `.TYPE_CHECKING`. The `else` body of `if not X:` is also `type`. A function or a class in
  such a body is also `type`.
- `call`: else, the statement is in the body of a function or a lambda, at any depth.
- `load`: else. A compound test, such as `if TYPE_CHECKING or flag:`, is not a test for
  type checks.

An import by a string value is a call of `__import__`, of `importlib.import_module`, or of
`import_module` after `from importlib import import_module`. The adapter knows only these
functions of the standard library.

The walk uses a list as the stack, not recursion. Thus a deep tree does not go above the
recursion limit of Python.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from systemap import python_calls, python_tree
from systemap.import_forms import CALL, LOAD, TYPE, ImportFacts

TYPE_MODULES = ("typing", "typing_extensions")
TYPE_FLAG = "TYPE_CHECKING"
DETAILS = frozenset({"call", "dynamic", "type"})


def import_facts(
    raw: str, prefixes: set[str], known: set[str], module: str = "", is_package: bool = False
) -> ImportFacts:
    """Give the import forms and the imports by a string value of one module text.

    A text that does not parse gives `import_forms.NONE`."""
    tree = python_tree.tree(raw)
    if tree is None:
        return ImportFacts({}, ())
    return tree_facts(tree, prefixes, known, module, is_package)


def tree_facts(
    tree: ast.AST, prefixes: set[str], known: set[str], module: str = "", is_package: bool = False
) -> ImportFacts:
    """Give the import facts of one parsed module."""
    by_node = statement_forms(tree)
    found: dict[str, set[str]] = defaultdict(set)
    for node, _local, target, _name, _line in python_calls.import_targets(
        tree, prefixes, known, module, is_package
    ):
        found[target].add(by_node.get(id(node), LOAD))
    forms = {target: tuple(sorted(values)) for target, values in found.items()}
    return ImportFacts(forms, tuple(dynamic_imports(tree, known)))


def _flag_names(tree: ast.AST) -> set[str]:
    """Give the local names of `TYPE_CHECKING` in the module."""
    out = {TYPE_FLAG}
    for node in python_tree.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in TYPE_MODULES:
            out.update(
                alias.asname or alias.name for alias in node.names if alias.name == TYPE_FLAG
            )
    return out


def _flag_sign(test: ast.expr, flags: set[str]) -> int:
    """Give 1 for a test of the flag, -1 for `not` and the flag, and 0 for a different test."""
    sign = 1
    while isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        sign, test = -sign, test.operand
    if isinstance(test, ast.Name) and test.id in flags:
        return sign
    if isinstance(test, ast.Attribute) and test.attr == TYPE_FLAG:
        return sign
    return 0


def statement_forms(tree: ast.AST) -> dict[int, str]:
    """Give the form of each import statement, by the identity of the node."""
    flags = _flag_names(tree)
    out: dict[int, str] = {}
    stack: list[tuple[ast.AST, str]] = [(tree, LOAD)]
    while stack:
        node, form = stack.pop()
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            out[id(node)] = form
            continue
        stack.extend(_children(node, form, flags))
    return out


def _children(node: ast.AST, form: str, flags: set[str]) -> Iterable[tuple[ast.AST, str]]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        inner = TYPE if form == TYPE else CALL
        return ((child, inner) for child in ast.iter_child_nodes(node))
    sign = _flag_sign(node.test, flags) if isinstance(node, ast.If) else 0
    if isinstance(node, ast.If) and sign:
        return _flag_children(node, form, sign)
    return ((child, form) for child in ast.iter_child_nodes(node))


def _flag_children(node: ast.If, form: str, sign: int) -> list[tuple[ast.AST, str]]:
    """Give the children of a test of the flag. The body of `if X:` and the `else` body
    of `if not X:` operate only for type checks."""
    body_form, else_form = (TYPE, form) if sign == 1 else (form, TYPE)
    return [
        *((child, body_form) for child in node.body),
        *((child, else_form) for child in node.orelse),
        (node.test, form),
    ]


def _import_module_names(tree: ast.AST) -> set[str]:
    """Give the local names of `importlib.import_module` after `from importlib import`."""
    out: set[str] = set()
    for node in python_tree.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "importlib" and not node.level:
            out.update(
                alias.asname or alias.name for alias in node.names if alias.name == "import_module"
            )
    return out


def _called(function: ast.expr, local: set[str]) -> str:
    """Give the called import function, or an empty string."""
    if isinstance(function, ast.Name) and function.id == "__import__":
        return "__import__"
    if isinstance(function, ast.Name) and function.id in local:
        return "import_module"
    if (
        isinstance(function, ast.Attribute)
        and function.attr == "import_module"
        and isinstance(function.value, ast.Name)
        and function.value.id == "importlib"
    ):
        return "import_module"
    return ""


def dynamic_imports(tree: ast.AST, known: set[str]) -> list[dict[str, Any]]:
    """Give the `dynamic_imports` records of one parsed module, sorted."""
    local = _import_module_names(tree)
    out: list[dict[str, Any]] = []
    for node in python_tree.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call = _called(node.func, local)
        if not call:
            continue
        first = node.args[0] if node.args else None
        text = (
            first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else ""
        )
        target = text if text in known else ""
        out.append({"call": call, "text": text, "target": target, "line": node.lineno})
    return sorted(out, key=lambda row: (row["line"], row["call"], row["text"]))
