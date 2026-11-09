"""The 2.0.0 text of the Python signatures and the `constants` previews (issue 143).

The 2.0.0 evidence of an answer has the full module record (`judgement_evidence`). In
2.0.0 and 3.0.0, `ast.unparse` gave the text of the function signatures, the class
methods, and the `constants` previews. From facts format 14, this text comes from the
source lines (`source_segment`). Thus the two texts are different for a module with, for
example, a string constant or a default value without spaces around `=`.

`record` gives the module record with the `ast.unparse` text again, from the source file.
`answer_upgrade` uses it through the Python adapter (`extract.PythonLanguage.earlier_record`)
only to calculate the 2.0.0 form of the evidence. Then an answer
from 2.0.0 that agrees with the source gets the current digest, also after this change of
the text. The current facts do not change.

`ast.unparse` is a function of the current interpreter. If its text is different from
the text of the interpreter that systemap 2.0.0 used, the answer stays pending, as in
3.0.0.
"""

from __future__ import annotations

import ast
import contextlib
from collections import defaultdict, deque
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from systemap import python_syntax, python_tree, source_segment, source_text
from systemap.unknown_causes import DEPTH_ERRORS

# The maximum number of characters in a 2.0.0 preview of a constant value.
_PREVIEW_LIMIT = 80

_Function = ast.FunctionDef | ast.AsyncFunctionDef
# The errors of `ast.unparse` for a node that it cannot give as text.
_UNPARSE_ERRORS = (AttributeError, ValueError, *DEPTH_ERRORS)


def record(root: Path, module: dict[str, Any]) -> dict[str, Any]:
    """Give the record with the 2.0.0 text of its signatures, methods, and previews.

    A record without a Python source file that the parser can read stays the same."""
    name = module.get("file")
    if not isinstance(name, str) or not name.endswith(".py"):
        return module
    try:
        raw = source_text.read(root, root / name)
        tree = python_tree.parse(raw)
    except (OSError, UnicodeError, SyntaxError, ValueError):
        return module
    statements = python_syntax.active_statements(tree.body)
    functions = _queues(
        (node.name, _signature(node)) for node in statements if isinstance(node, _Function)
    )
    classes = _class_queues(statements, source_segment.Source(raw))
    constants = _queues(_previews(statements))
    out = dict(module)
    out["functions"] = [
        {**item, "signature": _next(functions, item, "signature")}
        for item in module.get("functions", [])
    ]
    for key, queues in classes.items():
        out[key] = [
            {**item, "methods": _next(queues, item, "methods")} for item in module.get(key, [])
        ]
    out["constants"] = [
        {**item, "value": _next(constants, item, "value")} for item in module.get("constants", [])
    ]
    return out


def _class_queues(
    statements: list[ast.stmt], source: source_segment.Source
) -> dict[str, dict[str, deque[Any]]]:
    """Give the method queues of the `classes` records and of the `errors` records.

    `extract` puts an error class only in `errors`, with the same test of the class.
    """
    kinds: dict[bool, list[tuple[str, list[str]]]] = {True: [], False: []}
    for node in statements:
        if isinstance(node, ast.ClassDef):
            kinds[source_segment.is_error(node, source)].append((node.name, _methods(node)))
    return {"classes": _queues(kinds[False]), "errors": _queues(kinds[True])}


def _queues(pairs: Iterable[tuple[str, Any]]) -> dict[str, deque[Any]]:
    """Put the values of each name in a queue, in the sequence of the source."""
    out: dict[str, deque[Any]] = defaultdict(deque)
    for name, value in pairs:
        out[name].append(value)
    return out


def _next(queues: dict[str, deque[Any]], item: dict[str, Any], key: str) -> Any:
    """Give the next 2.0.0 value for the name of the item, or its current value."""
    queue = queues.get(item.get("name", ""))
    return queue.popleft() if queue else item.get(key)


def _signature(node: _Function) -> str:
    """Give the signature of a function as 2.0.0 and 3.0.0 gave it."""
    try:
        args = ast.unparse(node.args)
    except _UNPARSE_ERRORS:
        args = "..."
    ret = ""
    if node.returns is not None:
        with contextlib.suppress(*_UNPARSE_ERRORS):
            ret = f" -> {ast.unparse(node.returns)}"
    prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
    return f"{prefix}{node.name}({args}){ret}"


def _methods(node: ast.ClassDef) -> list[str]:
    """Give the signatures of the public methods of a class."""
    return [
        _signature(child)
        for child in node.body
        if isinstance(child, _Function) and not child.name.startswith("_")
    ]


def _previews(statements: list[ast.stmt]) -> Iterable[tuple[str, str]]:
    """Give the name and the 2.0.0 preview of each assigned value."""
    for node in statements:
        if not isinstance(node, ast.Assign | ast.AnnAssign) or node.value is None:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        try:
            value = ast.unparse(node.value)[:_PREVIEW_LIMIT]
        except _UNPARSE_ERRORS:
            value = "?"
        for target in targets:
            if isinstance(target, ast.Name):
                yield target.id, value
