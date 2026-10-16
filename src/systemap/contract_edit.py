"""The contract editor moves the rule values of a model file text into a contract file text.

The editor changes only the moved text. In the model file, it removes the `invariants`
and `import_rules` keywords of the MODEL call. If a keyword value is a name, it also
removes the assignment of that name, with the comment lines directly above it. Then it
removes each name that the model file imported from systemap and does not use after
the move.

In the contract file, the editor replaces the value of the same keyword of the CONTRACT
call with each moved value. If that keyword value is a name, the editor replaces the
value of the assignment of the name. The comment lines go above that assignment.

The editor parses the text again after each change. It does not examine the result: the
caller reads the two new texts and compares the values (`contract_move`).
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from systemap.contract import FIELDS
from systemap.model_edit import _line_starts, _offset
from systemap.model_load import SCHEMA_MODULES


class EditError(Exception):
    """The editor cannot move the rules. The message gives the cause."""


@dataclass(frozen=True)
class Moved:
    """One moved value: the keyword, the value text, the comment lines above its
    assignment, and the name of the assignment, if the keyword gives a name."""

    field: str
    value: str
    comments: str = ""
    name: str = ""


POSITION = ("lineno", "col_offset", "end_lineno", "end_col_offset")


def _position(node: ast.AST) -> tuple[int, int, int, int]:
    """Give the first row, the first column, the last row, and the end column of a node."""
    found = [getattr(node, key, None) for key in POSITION]
    assert all(isinstance(value, int) for value in found)
    first, column, last, end = (int(value or 0) for value in found)
    return first, column, last, end


def _span(text: str, node: ast.AST) -> tuple[int, int]:
    """Give the text indexes of the start and the end of a node."""
    starts = _line_starts(text)
    first, column, last, end = _position(node)
    return _offset(text, starts, first, column), _offset(text, starts, last, end)


def _call(tree: ast.Module, name: str) -> ast.Call:
    """Give the call of the one top-level statement `NAME = Class(...)`."""
    found = [
        stmt.value
        for stmt in tree.body
        if isinstance(stmt, ast.Assign | ast.AnnAssign)
        and _target(stmt) == name
        and isinstance(stmt.value, ast.Call)
    ]
    if len(found) != 1:
        raise EditError(f"the file has no one statement {name} = a model class call")
    call = found[0]
    assert isinstance(call, ast.Call)
    return call


def _target(stmt: ast.Assign | ast.AnnAssign) -> str:
    if isinstance(stmt, ast.AnnAssign):
        return stmt.target.id if isinstance(stmt.target, ast.Name) else ""
    one = len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name)
    return stmt.targets[0].id if one and isinstance(stmt.targets[0], ast.Name) else ""


def _assignment(tree: ast.Module, name: str) -> ast.Assign | ast.AnnAssign:
    """Give the one top-level assignment of the name."""
    found = [
        stmt
        for stmt in tree.body
        if isinstance(stmt, ast.Assign | ast.AnnAssign)
        and _target(stmt) == name
        and stmt.value is not None
    ]
    if len(found) != 1:
        raise EditError(f"the file has {len(found)} assignments of {name}. It must have one")
    return found[0]


def _keyword(call: ast.Call, field: str) -> ast.keyword | None:
    return next((kw for kw in call.keywords if kw.arg == field), None)


def _comment_rows(rows: list[str], first: int) -> int:
    """Give the index of the first comment row directly above the row `first`."""
    while first > 0 and rows[first - 1].lstrip().startswith("#"):
        first -= 1
    return first


def _uses(tree: ast.Module, name: str) -> bool:
    """Tell if the file reads the name. An assignment of the name is not a use."""
    return any(
        isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load)
        for node in ast.walk(tree)
    )


# ---- the model file -------------------------------------------------------------------


def taken(source: str) -> list[Moved]:
    """Give the values of the contract keywords of the MODEL call, in FIELDS order."""
    tree = ast.parse(source)
    call = _call(tree, "MODEL")
    rows = source.splitlines(keepends=True)
    out: list[Moved] = []
    for field in FIELDS:
        kw = _keyword(call, field)
        if kw is None:
            continue
        if not isinstance(kw.value, ast.Name):
            out.append(Moved(field, _segment(source, kw.value)))
            continue
        stmt = _assignment(tree, kw.value.id)
        assert stmt.value is not None
        first = _comment_rows(rows, stmt.lineno - 1)
        comments = "".join(rows[first : stmt.lineno - 1])
        out.append(Moved(field, _segment(source, stmt.value), comments, kw.value.id))
    return out


def _segment(source: str, node: ast.AST) -> str:
    begin, end = _span(source, node)
    return source[begin:end]


def model_text(source: str, moved: list[Moved]) -> str:
    """Give the model file text without the moved keywords, assignments, and imports."""
    text = source
    for item in moved:
        text = _drop_keyword(text, item.field)
    for item in moved:
        if not item.name:
            continue
        if _uses(ast.parse(text), item.name):
            raise EditError(f"the model file also uses {item.name} in a different place")
        text = _drop_assignment(text, item.name)
    names = {
        node.id
        for item in moved
        for node in ast.walk(ast.parse(item.value, mode="eval"))
        if isinstance(node, ast.Name)
    }
    for name in sorted(names):
        text = _drop_import(text, name)
    return text


def _drop_keyword(text: str, field: str) -> str:
    kw = _keyword(_call(ast.parse(text), "MODEL"), field)
    assert kw is not None
    begin, end = _span(text, kw)
    after = re.match(r"[ \t]*,?[ \t]*", text[end:])
    assert after is not None
    stop = end + after.end()
    row_start = text.rfind("\n", 0, begin) + 1
    if not text[row_start:begin].strip() and (stop == len(text) or text[stop] == "\n"):
        return text[:row_start] + text[stop + 1 :]
    if "," in after.group():
        return text[:begin] + text[stop:]
    before = re.search(r",\s*$", text[:begin])
    if before is None:
        raise EditError(f"the editor cannot remove the keyword {field} of the MODEL call")
    return text[: before.start()] + text[end:]


def _drop_assignment(text: str, name: str) -> str:
    stmt = _assignment(ast.parse(text), name)
    rows = text.splitlines(keepends=True)
    row, _column, last_row, end = _position(stmt)
    first = _comment_rows(rows, row - 1)
    last = last_row - 1
    if rows[last][end:].strip():
        raise EditError(f"the row of the assignment of {name} contains more text")
    blank_above = first > 0 and not rows[first - 1].strip()
    if blank_above and last + 1 < len(rows) and not rows[last + 1].strip():
        last += 1
    return "".join(rows[:first] + rows[last + 1 :])


def _drop_import(text: str, name: str) -> str:
    """Remove the name from the systemap import if the file does not use it now."""
    tree = ast.parse(text)
    if _uses(tree, name):
        return text
    for stmt in tree.body:
        if not isinstance(stmt, ast.ImportFrom) or stmt.module not in SCHEMA_MODULES:
            continue
        for alias in stmt.names:
            if (alias.asname or alias.name) != name:
                continue
            if len(stmt.names) == 1:
                rows = text.splitlines(keepends=True)
                return "".join(rows[: stmt.lineno - 1] + rows[_position(stmt)[2] :])
            return _drop_alias(text, alias)
    return text


def _drop_alias(text: str, alias: ast.alias) -> str:
    begin, end = _span(text, alias)
    after = re.match(r"[ \t]*,[ \t]*", text[end:])
    if after is not None:
        text = text[:begin] + text[end + after.end() :]
    else:
        before = re.search(r",\s*$", text[:begin])
        assert before is not None
        text = text[: before.start()] + text[end:]
        begin = before.start()
    row_start = text.rfind("\n", 0, begin) + 1
    row_end = text.find("\n", begin)
    if row_end >= 0 and not text[row_start:row_end].strip():
        text = text[:row_start] + text[row_end + 1 :]
    return text


# ---- the contract file ----------------------------------------------------------------


def contract_text(base: str, moved: list[Moved]) -> str:
    """Give the contract file text with the moved values."""
    text = base
    for item in moved:
        tree = ast.parse(text)
        kw = _keyword(_call(tree, "CONTRACT"), item.field)
        if kw is None:
            raise EditError(f"the CONTRACT call has no {item.field} keyword")
        if not isinstance(kw.value, ast.Name):
            begin, end = _span(text, kw.value)
            text = text[:begin] + item.value + text[end:]
            continue
        stmt = _assignment(tree, kw.value.id)
        assert stmt.value is not None
        begin, end = _span(text, stmt.value)
        text = text[:begin] + item.value + text[end:]
        if item.comments:
            row_start = text.rfind("\n", 0, _span(text, stmt)[0]) + 1
            text = text[:row_start] + item.comments + text[row_start:]
    return text
