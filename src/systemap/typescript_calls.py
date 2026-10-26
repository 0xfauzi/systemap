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
from systemap.typescript_scopes import Scopes
from systemap.typescript_syntax import first_named, specifier_name, string_value, syntax_tree

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
# The property chains: the field of the head and the field of the last name.
CHAINS = {
    "member_expression": ("object", "property"),
    "nested_type_identifier": ("module", "name"),
}
# A longer property chain has no name. The earlier recursive reader stopped with
# RecursionError before 1000 links. Thus this limit changes no earlier result. Without a
# limit, a chain of N links keeps names with a total length in proportion to N * N.
MAX_LINKS = 1000

Resolver = Callable[[str], str | None]
Site = tuple[str, str, str, int]


def _text(node: Any | None) -> str:
    return (node.text or b"").decode("utf-8") if node is not None else ""


def _line(node: Any) -> int:
    return int(node.start_point[0]) + 1


def _walk(node: Any) -> Iterator[Any]:
    """Give the node and each named node below it, in source order.

    The walk uses a list as its stack, not recursion. Thus a deep tree does not go
    above the recursion limit of Python."""
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(current.named_children))


def _source(node: Any) -> str:
    return string_value(node.child_by_field_name("source"))


def _first_name(node: Any) -> Any | None:
    return next((c for c in node.named_children if c.type == "identifier"), None)


def _specifier_sites(named: Any) -> Iterator[Site]:
    for spec in (c for c in named.named_children if c.type == "import_specifier"):
        name = specifier_name(spec.child_by_field_name("name"))
        alias = specifier_name(spec.child_by_field_name("alias"))
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
        name = specifier_name(spec.child_by_field_name("name"))
        alias = specifier_name(spec.child_by_field_name("alias"))
        yield alias or name, name, source, _line(spec)


# The innermost named function that contains a node: the function node, its line, and
# the frame of the next function that contains it.
_Frame = tuple[Any, int, Any]


class _Reader:
    """Find the bindings and the uses in one parsed module.

    One walk from the root records the parent, the innermost named function, and the
    binding flag of each node. The reader then does not walk up the tree for each name.
    In tree-sitter, `parent` also walks down from the root. Each property chain gets
    its dotted name one time.
    """

    def __init__(self, root: Any) -> None:
        self.root = root
        self.nodes: list[Any] = []
        self.parents: dict[int, Any] = {}
        self.frames: dict[int, _Frame | None] = {}
        self.bound: set[int] = set()
        self._names: dict[int, tuple[str | None, int]] = {}
        self._index()

    def _index(self) -> None:
        stack: list[tuple[Any, Any, _Frame | None, bool]] = [(self.root, None, None, False)]
        while stack:
            node, parent, frame, imported = stack.pop()
            self.nodes.append(node)
            self.parents[node.id] = parent
            self.frames[node.id] = frame
            line = function_line(node, parent)
            inner = (node, line, frame) if line else frame
            field = BINDING_FIELDS.get(node.type)
            made = node.child_by_field_name(field) if field else None
            inside = imported or node.type == "import_statement"
            for child in reversed(node.named_children):
                if inside or (made is not None and child.id == made.id):
                    self.bound.add(child.id)
                stack.append((child, node, inner, inside))

    def parent(self, node: Any) -> Any | None:
        return self.parents[node.id] if node.id in self.parents else node.parent

    def scope(self, node: Any) -> Any:
        """Give the innermost named function that contains the node, or None.

        Each call gives a new node object, as the `parent` walk of the earlier reader
        did. `records` keys a binding by the identity of this object. Thus two bindings
        of one name in one function stay two records, as before this change."""
        frame = self.frames.get(node.id)
        return frame[0].walk().node if frame else None

    def function_line(self, node: Any) -> int:
        """Give the line of the innermost named function that contains the node, or 0."""
        frame = self.frames.get(node.id)
        return frame[1] if frame else 0

    def in_scope(self, binding: Binding, node: Any) -> bool:
        if binding.scope is None:
            return True
        frame = self.frames.get(node.id)
        while frame is not None:
            if frame[0].id == binding.scope.id:
                return True
            frame = frame[2]
        return False

    def dotted(self, node: Any | None) -> str | None:
        """Give `a.b.c` for a name or a property chain on a name, else None.

        The function goes down the chain without recursion, and keeps the name of each
        link of the chain. A chain with more than MAX_LINKS links gives None."""
        chain: list[Any] = []
        current = node
        while current is not None and current.id not in self._names and current.type in CHAINS:
            chain.append(current)
            current = current.child_by_field_name(CHAINS[current.type][0])
        head, links = self._known(current)
        for link in reversed(chain):
            tail = _text(link.child_by_field_name(CHAINS[link.type][1]))
            links += 1
            head = f"{head}.{tail}" if head and tail and links <= MAX_LINKS else None
            self._names[link.id] = (head, links)
        return head

    def _known(self, node: Any | None) -> tuple[str | None, int]:
        if node is None:
            return None, 0
        if node.id in self._names:
            return self._names[node.id]
        name = node.type in ("identifier", "type_identifier", "this")
        return (_text(node), 0) if name else (None, 0)


def function_line(node: Any, parent: Any | None) -> int:
    """Give the line of a named function, or 0 for a function without a name."""
    if node.type in NAMED:
        return _line(node)
    if node.type in ANONYMOUS and parent is not None and parent.type in NAMING:
        return _line(parent)
    return 0


def _root(
    reader: _Reader, value: Any | None, imports: dict[str, Binding]
) -> tuple[Binding, str] | None:
    """Give the import binding at the root of a value, and the imported name it gives."""
    while value is not None and value.type in (
        "await_expression",
        "call_expression",
        "new_expression",
    ):
        inner = {"call_expression": "function", "new_expression": "constructor"}.get(value.type)
        value = value.child_by_field_name(inner) if inner else first_named(value)
    text = reader.dotted(value)
    if text is None:
        return None
    for local, binding in imports.items():
        if text == local:
            return binding, binding.name
        if text.startswith(local + "."):
            rest = text[len(local) + 1 :].split(".")[0]
            return binding, rest if binding.name == WHOLE else binding.name
    return None


def _type_root(
    reader: _Reader, annotation: Any | None, imports: dict[str, Binding]
) -> tuple[Binding, str] | None:
    if annotation is None:
        return None
    for node in _walk(annotation):
        found = _root(reader, node, imports) if node.type in NAMES else None
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


def _value_target(reader: _Reader, node: Any) -> tuple[str, Any, Any] | None:
    """Give (local name, value, type) for a declaration, an assignment, or a parameter."""
    if node.type in PARAMETERS:
        return _parameter_target(node)
    if node.type == "public_field_definition":
        return _field_target(node)
    if node.type not in ("variable_declarator", "assignment_expression"):
        return None
    name, value = ("name", "value") if node.type == "variable_declarator" else ("left", "right")
    local = reader.dotted(node.child_by_field_name(name))
    return (
        (local, node.child_by_field_name(value), node.child_by_field_name("type"))
        if local
        else None
    )


def _value_bindings(
    reader: _Reader, imports: dict[str, Binding], origins: dict[int, Any]
) -> list[Binding]:
    """Give the bindings that get a value or a type from an import. `origins` gets the
    node that makes each binding."""
    out: list[Binding] = []
    for node in reader.nodes:
        found = _value_target(reader, node)
        if found is None:
            continue
        local, value, kind = found
        root = _root(reader, value, imports) or _type_root(reader, kind, imports)
        if root is None or local in imports:
            continue
        scope = reader.scope(node) if "." not in local else None
        out.append(Binding(local, root[0].target, root[1], VALUE, _line(node), scope))
        origins[id(out[-1])] = node
    return out


def _use(reader: _Reader, node: Any) -> tuple[int, int, str]:
    parent: Any = reader.parent(node)
    obj = parent.child_by_field_name("object") if parent is not None else None
    member = ""
    if obj is not None and obj.id == node.id and parent.type == "member_expression":
        member = _text(parent.child_by_field_name("property"))
    return _line(node), reader.function_line(node), member


def _add_uses(reader: _Reader, bindings: dict[str, list[Binding]], origins: dict[int, Any]) -> None:
    """Add each use of each binding. A use where an inner declaration hides the name is
    not a use of the binding (`typescript_scopes`). A name that a declaration, an
    assignment, a parameter, or an import makes is not a use."""
    scopes = Scopes(reader.parent)
    for node in reader.nodes:
        if node.type not in NAMES or node.id in reader.bound:
            continue
        for binding in bindings.get(reader.dotted(node) or "", []):
            origin = origins[id(binding)]
            if reader.in_scope(binding, node) and not scopes.hides(binding.local, origin, node):
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
    origins: dict[int, Any] = {}
    for statement in (c for c in root.named_children if c.type == "import_statement"):
        for local, name, source, line in _import_sites(statement):
            target = resolve(source) if source else None
            if target:
                imports[local] = Binding(local, target, name, IMPORT, line)
                origins[id(imports[local])] = statement
    values = _value_bindings(reader, imports, origins)
    by_local: dict[str, list[Binding]] = {}
    for binding in [*imports.values(), *values]:
        by_local.setdefault(binding.local, []).append(binding)
    _add_uses(reader, by_local, origins)
    return records([*imports.values(), *values, *_reexports(root, resolve)], module)


def _reexports(root: Any, resolve: Resolver) -> list[Binding]:
    out: list[Binding] = []
    for statement in (c for c in root.named_children if c.type == "export_statement"):
        for local, name, source, line in _export_sites(statement):
            target = resolve(source)
            if target:
                out.append(Binding(local, target, name, IMPORT, line))
    return out
