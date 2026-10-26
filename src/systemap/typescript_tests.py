"""The TypeScript test reader gives the names of the tests in a test file."""

from __future__ import annotations

import re

from tree_sitter import Node

from systemap.typescript_syntax import _root, _text, first_argument, string_value

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
    same identity in one file gets the suffix " #2", a third gets " #3", and so on. A
    suffix that gives the identity of a different test is not used: the next number is
    used. Thus each test has a different identity.

    A table test gives its name pattern. A template literal gives its text, with the
    `${...}` parts as written. A suite name that is not a literal gives its source text.
    A test name that is not a literal gives no test.
    """
    root = _root(raw, path)
    if root is None:
        return []
    found: list[str] = []
    _visit(root, (), found)
    return unique_names(found)


def unique_names(found: list[str]) -> list[str]:
    """This function gives each name one time, in order. A repeated name gets the first
    free suffix " #N", with N from 2. A name in `found` is never a free suffix."""
    used = set(found)
    counts: dict[str, int] = {}
    seen: set[str] = set()
    out: list[str] = []
    for name in found:
        if name not in seen:
            seen.add(name)
            out.append(name)
            continue
        number = counts.get(name, 1) + 1
        while f"{name} #{number}" in used:
            number += 1
        counts[name] = number
        used.add(f"{name} #{number}")
        out.append(f"{name} #{number}")
    return out


def _visit(root: Node, suites: tuple[str, ...], found: list[str]) -> None:
    """Add the test identities below the root to `found`, in source order.

    A list is the stack, not recursion, because a file can have more suite levels than
    the recursion limit of Python."""
    stack = [(root, suites)]
    while stack:
        node, names = stack.pop()
        if node.type == "call_expression":
            function = node.child_by_field_name("function")
            if _is_call(function, TEST_CALL, TABLE_CALL) and (name := _name(node)):
                found.append(SEPARATOR.join((*names, name)))
            elif _is_call(function, SUITE_CALL, SUITE_TABLE):
                names = (*names, _suite_name(node))
        stack.extend((child, names) for child in reversed(node.named_children))


def _is_call(function: Node | None, plain: re.Pattern[str], table: re.Pattern[str]) -> bool:
    if function is not None and function.type == "call_expression":
        return bool(table.fullmatch(_text(function.child_by_field_name("function"))))
    return bool(plain.fullmatch(_text(function)))


def _name(call: Node) -> str:
    first = first_argument(call)
    if first is not None and first.type == "template_string":
        return _text(first)[1:-1]
    return string_value(first)


def _suite_name(call: Node) -> str:
    return _name(call) or " ".join(_text(first_argument(call)).split())
