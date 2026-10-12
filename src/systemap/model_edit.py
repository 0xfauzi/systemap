"""The model editor changes one keyword value of one model class call in model source.

The editor keeps all other text of the file: comments, line breaks, and spaces. If the
call has the keyword, the editor replaces its value. If not, the editor adds the keyword
after the last argument, in the format of the call: on the same line for a call on one
line, or on a new line with the indent of the last argument.
"""

from __future__ import annotations

import ast
import json
import re

from systemap.model_load import SCHEMA_MODULES

_NEWLINE = re.compile(r"\r\n|\r|\n")
_INDENT = "    "


def calls(tree: ast.Module, cls: str) -> list[ast.Call]:
    """Give each call of the model class `cls`, also with a name from `import ... as`."""
    names = {cls}
    for stmt in tree.body:
        if isinstance(stmt, ast.ImportFrom) and stmt.module in SCHEMA_MODULES:
            names.update(alias.asname for alias in stmt.names if alias.name == cls and alias.asname)
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in names
    ]


def literal(call: ast.Call, position: int, name: str) -> str | None:
    """Give the string constant of an argument, by keyword or by position, or None."""
    node = next((kw.value for kw in call.keywords if kw.arg == name), None)
    if node is None and len(call.args) > position:
        node = call.args[position]
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def set_keyword(source: str, call: ast.Call, name: str, value: str) -> str:
    """Give the source with the keyword `name` of `call` set to the string `value`."""
    text = json.dumps(value, ensure_ascii=False)
    starts = _line_starts(source)
    found = next((kw.value for kw in call.keywords if kw.arg == name), None)
    if found is not None:
        begin = _offset(source, starts, found.lineno, found.col_offset)
        end = _offset(source, starts, _end_line(found), _end_col(found))
        return source[:begin] + text + source[end:]
    return _insert(source, starts, call, f"{name}={text}")


def _insert(source: str, starts: list[int], call: ast.Call, keyword: str) -> str:
    """Add the keyword after the last argument of the call."""
    last = max((*call.args, *call.keywords), key=lambda node: (_end_line(node), _end_col(node)))
    end = _offset(source, starts, _end_line(last), _end_col(last))
    close = _offset(source, starts, _end_line(call), _end_col(call)) - 1
    comma = _comma(source[end:close])
    after = end if comma < 0 else end + comma + 1
    added = "," if comma < 0 else ""
    tail = "" if comma < 0 else ","
    if call.lineno == _end_line(call):
        return source[:after] + f"{added} {keyword}{tail}" + source[after:]
    newline = "\r\n" if "\r\n" in source else "\n"
    indent = _indent(source, starts, call, last)
    if _NEWLINE.search(source, after, close):
        line_end = _NEWLINE.search(source, after, close)
        assert line_end is not None
        cut = line_end.end()
        return (
            source[:after]
            + added
            + source[after:cut]
            + f"{indent}{keyword},{newline}"
            + source[cut:]
        )
    return source[:after] + f"{added}{newline}{indent}{keyword}{tail}" + source[after:]


def _comma(text: str) -> int:
    """Give the index of the comma in the text between the last argument and `)`.

    That text has only spaces, line breaks, comments and one optional comma."""
    at = 0
    for line in text.split("\n"):
        code = line.split("#", 1)[0]
        if "," in code:
            return at + code.index(",")
        at += len(line) + 1
    return -1


def _indent(source: str, starts: list[int], call: ast.Call, last: ast.AST) -> str:
    """Give the indent of the last argument line. On the first line of the call, add one
    level to the indent of that line."""
    line_no = getattr(last, "lineno", call.lineno)
    begin = starts[line_no - 1]
    line = _NEWLINE.split(source[begin:], maxsplit=1)[0]
    lead = line[: len(line) - len(line.lstrip(" \t"))]
    return lead + _INDENT if line_no == call.lineno else lead


def _line_starts(source: str) -> list[int]:
    return [0, *(match.end() for match in _NEWLINE.finditer(source))]


def _offset(source: str, starts: list[int], line_no: int, column: int) -> int:
    """Change a syntax tree position (a line, and a UTF-8 byte column) to a text index."""
    begin = starts[line_no - 1]
    line = source[begin : begin + column]
    return begin + len(line.encode("utf-8")[:column].decode("utf-8", errors="ignore"))


def _end_line(node: ast.AST) -> int:
    value = getattr(node, "end_lineno", None)
    assert isinstance(value, int)
    return value


def _end_col(node: ast.AST) -> int:
    value = getattr(node, "end_col_offset", None)
    assert isinstance(value, int)
    return value
