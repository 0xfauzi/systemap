"""The TypeScript call-site reader writes the `call_sites` fact for the TypeScript adapter.

A call site is a local name that an import statement makes, or a local name that gets
its value or its type from an imported name. The fact gives each line that uses the
local name. For each use, it also gives the line of the function that contains the
use, and the property that the use reads. The adapter gives the function that finds
the target module of an import.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

from systemap.call_sites import IMPORT, VALUE, WHOLE, Binding, records
from systemap.typescript_syntax import string_value, syntax_tree

RECEIVER = "this"
DEFAULT = "default"
NAMED = ("function_declaration", "generator_function_declaration", "method_definition")
ANONYMOUS = ("arrow_function", "function_expression", "function")
# A function without a name gets the name of the declaration that holds it.
NAMING = ("variable_declarator", "public_field_definition", "assignment_expression", "pair")
PARAMETERS = ("required_parameter", "optional_parameter")
# The syntax that makes a local name. These identifiers are not uses.
BINDING_FIELDS = {
    "variable_declarator": "name",
    "assignment_expression": "left",
    "required_parameter": "pattern",
    "optional_parameter": "pattern",
}
NAMES = ("identifier", "type_identifier", "this", "member_expression", "nested_type_identifier")

Resolver = Callable[[str], str | None]
Site = tuple[str, str, str, int]


def _text(node: Any | None) -> str:
    return (node.text or b"").decode("utf-8") if node is not None else ""


def _line(node: Any) -> int:
    return int(node.start_point[0]) + 1


def _walk(node: Any) -> Iterator[Any]:
    yield node
    for child in node.named_children:
        yield from _walk(child)


def _dotted(node: Any | None) -> str | None:
    """Give `a.b.c` for a name or a property chain on a name, else None."""
    if node is None:
        return None
    if node.type in ("identifier", "type_identifier", "this"):
        return _text(node)
    parts = {
        "member_expression": ("object", "property"),
        "nested_type_identifier": ("module", "name"),
    }.get(node.type)
    if parts is None:
        return None
    head = _dotted(node.child_by_field_name(parts[0]))
    tail = _text(node.child_by_field_name(parts[1]))
    return f"{head}.{tail}" if head and tail else None


def _source(node: Any) -> str:
    return string_value(node.child_by_field_name("source"))


def _first_name(node: Any) -> Any | None:
    return next((c for c in node.named_children if c.type == "identifier"), None)


def _specifier_sites(named: Any) -> Iterator[Site]:
    for spec in (c for c in named.named_children if c.type == "import_specifier"):
        name = _text(spec.child_by_field_name("name"))
        alias = _text(spec.child_by_field_name("alias"))
        yield alias or name, name, name, _line(spec)


def _clause_sites(clause: Any) -> Iterator[Site]:
    """Give (local name, imported name, imported name, line) for one import clause."""
    for child in clause.named_children:
        name = _first_name(child) if child.type == "namespace_import" else None
        if child.type == "identifier":
            yield _text(child), DEFAULT, DEFAULT, _line(child)
        elif name is not None:
            yield _text(name), WHOLE, WHOLE, _line(name)
        elif child.type == "named_imports":
            yield from _specifier_sites(child)


def _import_sites(statement: Any) -> Iterator[tuple[str, str, str, int]]:
    """Give (local name, imported name, source text, line) for one import statement."""
    for clause in statement.named_children:
        name = _first_name(clause) if clause.type == "import_require_clause" else None
        if name is not None:
            yield _text(name), WHOLE, _source(clause), _line(name)
        elif clause.type == "import_clause":
            for local, name, _kind, line in _clause_sites(clause):
                yield local, name, _source(statement), line


def _export_sites(statement: Any) -> Iterator[tuple[str, str, str, int]]:
    """Give (exported name, imported name, source text, line) for one re-export statement.

    A re-export makes no local name. The record gives the exported name as `local`."""
    source = _source(statement)
    if not source:
        return
    clause = next((c for c in statement.named_children if c.type == "export_clause"), None)
    if clause is None:
        space = next((c for c in statement.named_children if c.type == "namespace_export"), None)
        name = _first_name(space) if space is not None else None
        yield (_text(name) if name is not None else WHOLE), WHOLE, source, _line(statement)
        return
    for spec in (c for c in clause.named_children if c.type == "export_specifier"):
        name = _text(spec.child_by_field_name("name"))
        alias = _text(spec.child_by_field_name("alias"))
        yield alias or name, name, source, _line(spec)


class _Reader:
    """Find the bindings and the uses in one parsed module."""

    def __init__(self, root: Any) -> None:
        self.root = root

    def function_line(self, node: Any) -> int:
        """Give the line of a named function, or 0 for a function without a name."""
        if node.type in NAMED:
            return _line(node)
        if node.type in ANONYMOUS and node.parent is not None and node.parent.type in NAMING:
            return _line(node.parent)
        return 0

    def functions(self, node: Any) -> list[Any]:
        """Give the named functions that contain the node, innermost first."""
        out: list[Any] = []
        current = node.parent
        while current is not None:
            if self.function_line(current):
                out.append(current)
            current = current.parent
        return out

    def scope(self, node: Any) -> Any:
        found = self.functions(node)
        return found[0] if found else None

    def in_scope(self, binding: Binding, node: Any) -> bool:
        if binding.scope is None:
            return True
        return any(f.id == binding.scope.id for f in self.functions(node))


def _root(value: Any | None, imports: dict[str, Binding]) -> tuple[Binding, str] | None:
    """Give the import binding at the root of a value, and the imported name it gives."""
    while value is not None and value.type in (
        "await_expression",
        "call_expression",
        "new_expression",
    ):
        inner = {"call_expression": "function", "new_expression": "constructor"}.get(value.type)
        value = (
            value.child_by_field_name(inner) if inner else next(iter(value.named_children), None)
        )
    text = _dotted(value)
    if text is None:
        return None
    for local, binding in imports.items():
        if text == local:
            return binding, binding.name
        if text.startswith(local + "."):
            rest = text[len(local) + 1 :].split(".")[0]
            return binding, rest if binding.name == WHOLE else binding.name
    return None


def _type_root(annotation: Any | None, imports: dict[str, Binding]) -> tuple[Binding, str] | None:
    if annotation is None:
        return None
    for node in _walk(annotation):
        found = _root(node, imports) if node.type in NAMES else None
        if found:
            return found
    return None


def _parameter_target(node: Any) -> tuple[str, Any, Any] | None:
    """A parameter with an access modifier is also a field of the class."""
    pattern = node.child_by_field_name("pattern")
    if pattern is None or pattern.type != "identifier":
        return None
    field = any(c.type == "accessibility_modifier" for c in node.named_children)
    local = f"{RECEIVER}.{_text(pattern)}" if field else _text(pattern)
    return local, None, node.child_by_field_name("type")


def _field_target(node: Any) -> tuple[str, Any, Any] | None:
    name = _text(node.child_by_field_name("name"))
    value, kind = node.child_by_field_name("value"), node.child_by_field_name("type")
    return (f"{RECEIVER}.{name}", value, kind) if name else None


def _value_target(node: Any) -> tuple[str, Any, Any] | None:
    """Give (local name, value, type) for a declaration, an assignment, or a parameter."""
    if node.type in PARAMETERS:
        return _parameter_target(node)
    if node.type == "public_field_definition":
        return _field_target(node)
    if node.type not in ("variable_declarator", "assignment_expression"):
        return None
    name, value = ("name", "value") if node.type == "variable_declarator" else ("left", "right")
    local = _dotted(node.child_by_field_name(name))
    return (
        (local, node.child_by_field_name(value), node.child_by_field_name("type"))
        if local
        else None
    )


def _value_bindings(reader: _Reader, imports: dict[str, Binding]) -> list[Binding]:
    out: list[Binding] = []
    for node in _walk(reader.root):
        found = _value_target(node)
        if found is None:
            continue
        local, value, kind = found
        root = _root(value, imports) or _type_root(kind, imports)
        if root is None or local in imports:
            continue
        scope = reader.scope(node) if "." not in local else None
        out.append(Binding(local, root[0].target, root[1], VALUE, _line(node), scope))
    return out


def _is_binding(node: Any) -> bool:
    """Find a name that a declaration, an assignment, a parameter, or an import makes."""
    parent = node.parent
    if parent is None:
        return False
    name = BINDING_FIELDS.get(parent.type)
    if name and parent.child_by_field_name(name) is not None:
        if parent.child_by_field_name(name).id == node.id:
            return True
    current = parent
    while current is not None:
        if current.type == "import_statement":
            return True
        current = current.parent
    return False


def _use(reader: _Reader, node: Any) -> tuple[int, int, str]:
    parent = node.parent
    obj = parent.child_by_field_name("object") if parent is not None else None
    member = ""
    if obj is not None and obj.id == node.id and parent.type == "member_expression":
        member = _text(parent.child_by_field_name("property"))
    functions = reader.functions(node)
    return _line(node), reader.function_line(functions[0]) if functions else 0, member


def _add_uses(reader: _Reader, bindings: dict[str, list[Binding]]) -> None:
    for node in _walk(reader.root):
        if node.type not in NAMES or _is_binding(node):
            continue
        for binding in bindings.get(_dotted(node) or "", []):
            if reader.in_scope(binding, node):
                binding.uses.add(_use(reader, node))


def call_sites(raw: str, path: str, module: str, resolve: Resolver) -> list[dict[str, Any]] | None:
    """Give the call-site records of one module, or None if the source does not parse.

    `resolve` gives the target module of an import source text, or None.
    """
    root = syntax_tree(raw, path)
    if root.has_error:
        return None
    reader = _Reader(root)
    imports: dict[str, Binding] = {}
    for statement in (c for c in root.named_children if c.type == "import_statement"):
        for local, name, source, line in _import_sites(statement):
            target = resolve(source) if source else None
            if target:
                imports[local] = Binding(local, target, name, IMPORT, line)
    values = _value_bindings(reader, imports)
    by_local: dict[str, list[Binding]] = {}
    for binding in [*imports.values(), *values]:
        by_local.setdefault(binding.local, []).append(binding)
    _add_uses(reader, by_local)
    return records([*imports.values(), *values, *_reexports(root, resolve)], module)


def _reexports(root: Any, resolve: Resolver) -> list[Binding]:
    out: list[Binding] = []
    for statement in (c for c in root.named_children if c.type == "export_statement"):
        for local, name, source, line in _export_sites(statement):
            target = resolve(source)
            if target:
                out.append(Binding(local, target, name, IMPORT, line))
    return out
