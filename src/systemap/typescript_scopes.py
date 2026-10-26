"""The TypeScript scope reader finds a local declaration that hides a name.

A parameter, a variable, a function, a class, or a catch parameter in an inner scope
hides a name of an outer scope with the same text. The call-site reader then does not
give a use of the outer name. A type name is in a different name space: a value
declaration does not hide it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

from tree_sitter import Node

from systemap.typescript_syntax import _text

FUNCTIONS = frozenset(
    {
        "function_declaration",
        "generator_function_declaration",
        "function_expression",
        "function",
        "generator_function",
        "arrow_function",
        "method_definition",
    }
)
# The statements that declare a value name in their block.
NAMED_DECLARATIONS = frozenset(
    {
        "function_declaration",
        "generator_function_declaration",
        "class_declaration",
        "abstract_class_declaration",
        "enum_declaration",
    }
)
VARIABLES = frozenset({"lexical_declaration", "variable_declaration"})
PARAMETERS = frozenset({"required_parameter", "optional_parameter"})


def pattern_names(node: Node | None) -> list[str]:
    """Give the names that a binding pattern declares. A default value declares no name.

    The function uses a list as its stack, not recursion, because a pattern can have
    more levels than the recursion limit of Python."""
    out: list[str] = []
    stack = [node]
    while stack:
        current = stack.pop()
        if current is None:
            continue
        if current.type in ("identifier", "shorthand_property_identifier_pattern"):
            out.append(_text(current))
        elif current.type == "pair_pattern":
            stack.append(current.child_by_field_name("value"))
        elif current.type in ("assignment_pattern", "object_assignment_pattern"):
            stack.append(current.child_by_field_name("left"))
        elif current.type in ("object_pattern", "array_pattern", "rest_pattern"):
            stack.extend(reversed(current.named_children))
    return out


class Scopes:
    """This reader keeps the declared names of each scope node of one syntax tree.

    `parent` gives the parent of a node. The default is the `parent` of tree-sitter,
    which walks down from the root for each call. A caller with a parent index can
    give a faster function."""

    def __init__(self, parent: Callable[[Node], Node | None] | None = None) -> None:
        self._names: dict[int, frozenset[str]] = {}
        self._scopes: dict[tuple[str, int], Node | None] = {}
        self._parent = parent or _parent

    def hides(self, local: str, origin: Node, use: Node) -> bool:
        """Tell if a scope between the use and the scope of the binding declares the name.

        `origin` is the node that makes the binding: an import statement, a declarator,
        a parameter, or an assignment. A property name such as `this.client` and a type
        use are never hidden. The scope of the binding is the innermost scope above
        `origin` that declares the name. A different innermost scope above the use hides
        the name.
        """
        if "." in local or use.type != "identifier":
            return False
        outer = self._declaring(local, self._parent(origin))
        found = self._declaring(local, self._parent(use))
        return found is not None and (outer is None or found.id != outer.id)

    def _declaring(self, local: str, node: Node | None) -> Node | None:
        """Give the innermost scope that declares the name: the node or a node above it.

        The reader keeps the result for each node on the path. Thus many uses of one
        name in a deep tree do not walk the same path again."""
        path: list[Node] = []
        found: Node | None = None
        while node is not None:
            key = (local, node.id)
            if key in self._scopes:
                found = self._scopes[key]
                break
            path.append(node)
            if local in self.declared(node):
                found = node
                break
            node = self._parent(node)
        for item in path:
            self._scopes[(local, item.id)] = found
        return found

    def declared(self, node: Node) -> frozenset[str]:
        """Give the value names that a scope node declares. The module scope declares no
        name here, because the bindings of the call-site reader are in it."""
        if node.id not in self._names:
            self._names[node.id] = frozenset(_declared(node))
        return self._names[node.id]


def _parent(node: Node) -> Node | None:
    return node.parent


def _declared(node: Node) -> Iterator[str]:
    if node.type in FUNCTIONS:
        yield from _function_names(node)
    elif node.type in ("statement_block", "switch_body", "class_static_block"):
        yield from _block_names(node)
    elif node.type == "for_statement":
        yield from _variable_names(node.child_by_field_name("initializer"))
    elif node.type == "for_in_statement" and node.child_by_field_name("kind") is not None:
        yield from pattern_names(node.child_by_field_name("left"))
    elif node.type == "catch_clause":
        yield from pattern_names(node.child_by_field_name("parameter"))


def _function_names(node: Node) -> Iterator[str]:
    """Give the parameters, the name of a function expression, and each `var` name."""
    if node.type in ("function_expression", "function", "generator_function"):
        name = node.child_by_field_name("name")
        if name is not None:
            yield _text(name)
    single = node.child_by_field_name("parameter")
    if single is not None:
        yield from pattern_names(single)
    parameters = node.child_by_field_name("parameters")
    for parameter in parameters.named_children if parameters is not None else ():
        if parameter.type in PARAMETERS:
            yield from pattern_names(parameter.child_by_field_name("pattern"))
    body = node.child_by_field_name("body")
    if body is not None and body.type == "statement_block":
        yield from _hoisted(body)


def _hoisted(node: Node) -> Iterator[str]:
    """Give the `var` names in a function body. They are not in a nested function.

    The function uses a list as its stack, not recursion, as `pattern_names` does."""
    stack = list(reversed(node.named_children))
    while stack:
        child = stack.pop()
        if child.type == "variable_declaration":
            yield from _variable_names(child)
        elif child.type not in FUNCTIONS and child.type not in NAMED_DECLARATIONS:
            stack.extend(reversed(child.named_children))


def _block_names(node: Node) -> Iterator[str]:
    for child in node.named_children:
        if child.type in ("switch_case", "switch_default"):
            yield from _block_names(child)
        elif child.type in VARIABLES:
            yield from _variable_names(child)
        elif child.type in NAMED_DECLARATIONS:
            name = child.child_by_field_name("name")
            if name is not None:
                yield _text(name)


def _variable_names(node: Node | None) -> Iterator[str]:
    if node is None or node.type not in VARIABLES:
        return
    for declarator in node.named_children:
        if declarator.type == "variable_declarator":
            yield from pattern_names(declarator.child_by_field_name("name"))
