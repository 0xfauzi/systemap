"""The TypeScript test reader gives the names of the tests in a test file."""

from __future__ import annotations

import re

from tree_sitter import Node

from systemap.typescript_syntax import _root, _text, _walk, string_value

TEST_CALL = re.compile(r"(?:test|it)(?:\.(?:only|skip|concurrent|fails|todo))*")
# A table test: `it.each(rows)("name", ...)` or it.each`rows`("name", ...).
TABLE_CALL = re.compile(r"(?:test|it)(?:\.(?:only|skip|concurrent|fails))*\.each")


def test_names(raw: str, path: str = "") -> list[str]:
    """This function gives literal names passed to test and it, including nested test
    suites.

    A table test gives its name pattern. A template literal gives its text, with the
    `${...}` parts as written.
    """
    root = _root(raw, path)
    if root is None:
        return []
    out: list[str] = []
    for call in (node for node in _walk(root) if node.type == "call_expression"):
        if _is_test_call(call.child_by_field_name("function")) and (name := _name(call)):
            out.append(name)
    return out


def _is_test_call(function: Node | None) -> bool:
    if function is not None and function.type == "call_expression":
        return bool(TABLE_CALL.fullmatch(_text(function.child_by_field_name("function"))))
    return bool(TEST_CALL.fullmatch(_text(function)))


def _name(call: Node) -> str:
    arguments = call.child_by_field_name("arguments")
    first = arguments.named_children[0] if arguments and arguments.named_children else None
    if first is not None and first.type == "template_string":
        return _text(first)[1:-1]
    return string_value(first)
