"""The TypeScript import readers give the imports of one module and their import forms.

The readers give each static import or re-export statement at the top level of a module,
and each `import("x")` or `require("x")` call with a string literal. The TypeScript adapter
resolves the specifiers to modules (`typescript.TypeScriptLanguage.internal_uses`).

The import form of a statement (`import_forms`) is `type` for an import or re-export that
the TypeScript compiler removes: `import type`, `import { type A, type B }` when each name
has `type`, `import type X = require()`, `export type { A } from`, and `export type * from`.
Each other static statement is `load`, also `import "./x"` and `import { type A, B }`. A
literal `import()` or `require()` call is `call` in the body of a function, a method, an
accessor or a constructor, and `load` outside such a body. A call of `import()` or
`require()` with a different first argument is an import by a string value. It does not
change `uses`.

Each walk uses a list as the stack, not recursion, because a deep tree goes above the
recursion limit of Python.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable, Iterator
from typing import Any

from systemap.import_forms import CALL, LOAD, TYPE, ImportFacts
from systemap.typescript_syntax import first_argument, specifier_name, string_value

WHOLE_MODULE = "*"
DETAILS = frozenset({"call", "dynamic", "type"})
# The syntax nodes whose body operates only when the code calls them.
FUNCTION_NODES = frozenset(
    {
        "function_declaration",
        "function_expression",
        "function",
        "generator_function_declaration",
        "generator_function",
        "arrow_function",
        "method_definition",
    }
)
# `export type * from`. The second parse of `syntax_tree` replaces `type` with spaces, so
# the form comes from the source bytes at the position of the statement.
_TYPE_STAR = re.compile(rb"export\s+type\s+\*")
IMPORT_CALLS = ("import", "require")


def _imported_names(node: Any) -> set[str]:
    clause = next((child for child in node.named_children if child.type == "import_clause"), None)
    if clause is None:
        return {WHOLE_MODULE}
    if any(child.type == "namespace_import" for child in _walk(clause)):
        return {WHOLE_MODULE}
    out: set[str] = set()
    if any(child.type == "identifier" for child in clause.named_children):
        out.add("default")
    for specifier in (child for child in _walk(clause) if child.type == "import_specifier"):
        if original := specifier_name(specifier.child_by_field_name("name")):
            out.add(original)
    return out


def _exported_names(node: Any) -> set[str]:
    clause = next((child for child in node.named_children if child.type == "export_clause"), None)
    if clause is None:
        return {WHOLE_MODULE}
    out: set[str] = set()
    for specifier in (child for child in clause.named_children if child.type == "export_specifier"):
        # A string name, as in `export { 'a-b' as c } from`, is the name in the module.
        if original := specifier_name(specifier.child_by_field_name("name")):
            out.add(original)
    return out or {WHOLE_MODULE}


def _walk(node: Any) -> Iterator[Any]:
    """Give the node and each named node below it, in source order. A list is the stack,
    not recursion, because a deep tree goes above the recursion limit of Python."""
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(current.named_children))


def _text(node: Any | None) -> str:
    return (node.text or b"").decode("utf-8") if node is not None else ""


def _source(node: Any) -> str:
    return string_value(node.child_by_field_name("source"))


def _static_imports(root: Any) -> Iterator[tuple[str, set[str]]]:
    for node in root.named_children:
        imported = _static_import(node)
        if imported is not None:
            yield imported


def _static_import(node: Any) -> tuple[str, set[str]] | None:
    if node.has_error:
        return _error_import(node)
    specifier = _source(node)
    if node.type == "import_statement" and not specifier:
        clause = next(
            (child for child in node.named_children if child.type == "import_require_clause"),
            None,
        )
        if clause is not None and (specifier := _source(clause)):
            return specifier, {WHOLE_MODULE}
    if not specifier:
        return None
    if node.type == "import_statement":
        return specifier, _imported_names(node)
    if node.type == "export_statement":
        return specifier, _exported_names(node)
    return None


def _error_import(node: Any) -> tuple[str, set[str]] | None:
    if node.type == "export_statement" and _text(node).lstrip().startswith("export type * from"):
        if specifier := _source(node):
            return specifier, {WHOLE_MODULE}
    return None


def _dynamic_imports(root: Any) -> Iterator[tuple[str, set[str]]]:
    for node in _walk(root):
        specifier = _dynamic_specifier(node)
        if specifier is not None:
            yield specifier, {WHOLE_MODULE}


def _dynamic_specifier(node: Any) -> str | None:
    if node.type != "call_expression" or node.has_error:
        return None
    function = node.child_by_field_name("function")
    if _text(function) not in ("import", "require"):
        return None
    first = first_argument(node)
    if first is None or first.type != "string":
        return None
    return string_value(first)


def _imports(root: Any) -> Iterator[tuple[str, set[str]]]:
    yield from _static_imports(root)
    yield from _dynamic_imports(root)


# One import of a module: the specifier, the imported names, and the import form.
Import = tuple[str, set[str], str]


def read_imports(root: Any, raw: str) -> tuple[list[Import], list[Any]]:
    """Give the imports that `_imports` gives, each with its import form, and the call
    nodes of each import by a string value. One walk of the tree gives both."""
    data = raw.encode("utf-8")
    found: list[Import] = []
    for node in root.named_children:
        imported = _static_import(node)
        if imported is not None:
            found.append((*imported, _static_form(node, data)))
    calls: list[Any] = []
    for node, in_function in _import_calls(root):
        literal = _dynamic_specifier(node)
        if literal is None:
            calls.append(node)
        else:
            found.append((literal, {WHOLE_MODULE}, CALL if in_function else LOAD))
    return found, calls


def import_facts(
    imports: list[Import], calls: list[Any], resolve: Callable[[str], str | None]
) -> ImportFacts:
    """Give the import forms of each resolved target, and the imports by a string value.

    `imports` and `calls` come from `read_imports`. `resolve` gives the module of a
    specifier, or None."""
    found: dict[str, set[str]] = defaultdict(set)
    for specifier, _names, form in imports:
        if target := resolve(specifier):
            found[target].add(form)
    forms = {target: tuple(sorted(values)) for target, values in found.items()}
    return ImportFacts(forms, tuple(_dynamic_record(node, resolve) for node in calls))


def _static_form(node: Any, data: bytes) -> str:
    if node.has_error:
        # Only `export type * from` gives an import from a statement with an error.
        return TYPE
    if any(child.type == "type" for child in node.children):
        return TYPE
    if node.type == "export_statement":
        return TYPE if _TYPE_STAR.match(data[node.start_byte : node.end_byte]) else LOAD
    clause = next((child for child in node.named_children if child.type == "import_clause"), None)
    return TYPE if clause is not None and _only_types(clause) else LOAD


def _only_types(clause: Any) -> bool:
    """Tell if each name of an import clause has `type`, as in `import { type A, type B }`."""
    if any(child.type in ("identifier", "namespace_import") for child in clause.named_children):
        return False
    names = [child for child in _walk(clause) if child.type == "import_specifier"]
    return bool(names) and all(any(part.type == "type" for part in name.children) for name in names)


def _import_calls(root: Any) -> Iterator[tuple[Any, bool]]:
    """Give each call of `import` or `require` without a syntax error, and True if a
    function body contains it. The walk goes to the same nodes as `_walk`."""
    stack: list[tuple[Any, bool]] = [(root, False)]
    while stack:
        current, in_function = stack.pop()
        if current.type == "call_expression" and not current.has_error:
            if _text(current.child_by_field_name("function")) in IMPORT_CALLS:
                yield current, in_function
        inner = in_function or current.type in FUNCTION_NODES
        stack.extend((child, inner) for child in reversed(current.named_children))


def _dynamic_record(node: Any, resolve: Callable[[str], str | None]) -> dict[str, Any]:
    first = first_argument(node)
    text = ""
    if first is not None and first.type == "template_string":
        if not any(child.type == "template_substitution" for child in first.named_children):
            text = _text(first)[1:-1]
    return {
        "call": _text(node.child_by_field_name("function")),
        "text": text,
        "target": (resolve(text) or "") if text else "",
        "line": node.start_point[0] + 1,
    }
