"""The TypeScript test reader gives the names of the tests in a test file."""

from __future__ import annotations

import re

from tree_sitter import Node

from systemap.typescript_syntax import _root, _text, string_value

TEST_CALL = re.compile(r"(?:test|it)(?:\.(?:only|skip|concurrent|fails|todo))*")
# A table test: `it.each(rows)("name", ...)` or it.each`rows`("name", ...).
TABLE_CALL = re.compile(r"(?:test|it)(?:\.(?:only|skip|concurrent|fails))*\.each")
# A test suite of Jest, Vitest, or Mocha, and its table form `describe.each(rows)("name")`.
SUITE_CALL = re.compile(
    r"(?:describe|suite)(?:\.(?:only|skip|concurrent|sequential|shuffle|todo))*"
)
SUITE_TABLE = re.compile(
    r"(?:describe|suite)(?:\.(?:only|skip|concurrent|sequential|shuffle))*\.each"
)
# The text between the suite names and the test name in a test identity.
SEPARATOR = " > "


def test_names(raw: str, path: str = "") -> list[str]:
    """This function gives the identities of the tests passed to test and it.

    An identity has the names of the enclosing suites, then the test name, with " > "
    between them. Two suites can thus contain the same test name. A second test with the
    same identity in one file gets the suffix " #2", a third gets " #3", and so on.

    A table test gives its name pattern. A template literal gives its text, with the
    `${...}` parts as written. A suite name that is not a literal gives its source text.
    A test name that is not a literal gives no test.
    """
    root = _root(raw, path)
    if root is None:
        return []
    found: list[str] = []
    _visit(root, (), found)
    counts: dict[str, int] = {}
    out: list[str] = []
    for name in found:
        counts[name] = counts.get(name, 0) + 1
        out.append(name if counts[name] == 1 else f"{name} #{counts[name]}")
    return out


def _visit(node: Node, suites: tuple[str, ...], found: list[str]) -> None:
    if node.type == "call_expression":
        function = node.child_by_field_name("function")
        if _is_call(function, TEST_CALL, TABLE_CALL) and (name := _name(node)):
            found.append(SEPARATOR.join((*suites, name)))
        elif _is_call(function, SUITE_CALL, SUITE_TABLE):
            suites = (*suites, _suite_name(node))
    for child in node.named_children:
        _visit(child, suites, found)


def _is_call(function: Node | None, plain: re.Pattern[str], table: re.Pattern[str]) -> bool:
    if function is not None and function.type == "call_expression":
        return bool(table.fullmatch(_text(function.child_by_field_name("function"))))
    return bool(plain.fullmatch(_text(function)))


def _first_argument(call: Node) -> Node | None:
    arguments = call.child_by_field_name("arguments")
    return arguments.named_children[0] if arguments and arguments.named_children else None


def _name(call: Node) -> str:
    first = _first_argument(call)
    if first is not None and first.type == "template_string":
        return _text(first)[1:-1]
    return string_value(first)


def _suite_name(call: Node) -> str:
    return _name(call) or " ".join(_text(_first_argument(call)).split())
