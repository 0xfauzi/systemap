"""The source text of a syntax node, for the values that a person reads.

The function signatures, the `constants` previews, and the class bases come from the
lines of the module text, not from `ast.unparse`. CPython does not keep `ast.unparse` the
same between versions, but the source text of a node does not change with the
interpreter. The column positions of a node count UTF-8 bytes, as in
`ast.get_source_segment`.

A value on more than one line becomes one line. The text removes each comment (found with
`tokenize`), and each backslash at the end of a line. Each line loses the spaces at its
two ends. Two lines get one space between them, but no space after an opening bracket or
before a closing bracket.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize

from systemap import python_syntax

# The line ends that the Python parser uses. A form feed does not end a line.
_LINE_END = re.compile(r"\r\n|\r|\n")
_OPENING = "([{"
_CLOSING = ")]}"


class Source:
    """The lines of one module text. Each call gives the text of one node."""

    def __init__(self, raw: str) -> None:
        self.lines = _LINE_END.split(raw)

    def segment(self, node: ast.AST) -> str | None:
        """Give the exact source text of the node, or None for a node without a position."""
        first = getattr(node, "lineno", None)
        last = getattr(node, "end_lineno", None)
        start = getattr(node, "col_offset", None)
        end = getattr(node, "end_col_offset", None)
        if first is None or last is None or start is None or end is None:
            return None
        if not 0 < first <= last <= len(self.lines):
            return None
        if first == last:
            return _columns(self.lines[first - 1], start, end)
        parts = [_columns(self.lines[first - 1], start, None)]
        parts.extend(self.lines[first : last - 1])
        parts.append(_columns(self.lines[last - 1], 0, end))
        return "\n".join(parts)

    def text(self, node: ast.AST, limit: int | None = None) -> str | None:
        """Give the source text of the node on one line, with not more than `limit` characters."""
        found = self.segment(node)
        return None if found is None else flat(found, limit)


def _columns(line: str, start: int, end: int | None) -> str:
    if line.isascii():
        return line[start:end]
    return line.encode("utf-8")[start:end].decode("utf-8", errors="replace")


def flat(text: str, limit: int | None = None) -> str:
    """Give the text on one line, with not more than `limit` characters."""
    if "\n" not in text:
        return text[:limit]
    comments, open_ends = _marks(text)
    out = ""
    for row, line in enumerate(text.split("\n"), 1):
        code = line[: comments.get(row)]
        if row not in open_ends and code.rstrip().endswith("\\"):
            code = code.rstrip()[:-1]
        out = _join(out, code.strip())
        if limit is not None and len(out) >= limit:
            break
    return out[:limit]


def _join(left: str, right: str) -> str:
    if not left or not right:
        return left or right
    if left[-1] in _OPENING or right[0] in _CLOSING:
        return left + right
    return f"{left} {right}"


def _marks(text: str) -> tuple[dict[int, int], set[int]]:
    """Find the comments and the strings that continue on the next line, with `tokenize`.

    Give the column of the comment of each line, and the lines whose end is in a string.
    The tokenizer of the running interpreter reads the nested strings of an f-string
    (PEP 701) correctly. If the tokenizer stops on an error, only the comments before
    the error are found.
    """
    comments: dict[int, int] = {}
    open_ends: set[int] = set()
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.COMMENT:
                comments[token.start[0]] = token.start[1]
            open_ends.update(range(token.start[0], token.end[0]))
    except (tokenize.TokenError, SyntaxError):
        pass
    return comments, open_ends


def signature(node: ast.FunctionDef | ast.AsyncFunctionDef, source: Source) -> str:
    """Give the signature of a function, in the form `def name(arguments) -> result`.

    The text of each annotation and each default value comes from the source. A part
    without a source position gives `...`.
    """
    returns = None if node.returns is None else source.text(node.returns) or "..."
    return python_syntax.function_line(node, arguments(node.args, source), returns)


def arguments(args: ast.arguments, source: Source) -> str:
    """Give the parameters of a function, as `ast.unparse` puts them in sequence."""
    parts: list[str] = []
    positional = [*args.posonlyargs, *args.args]
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(args.defaults))
    defaults.extend(args.defaults)
    for index, (item, default) in enumerate(zip(positional, defaults, strict=True), 1):
        parts.append(_parameter(item, default, source))
        if index == len(args.posonlyargs):
            parts.append("/")
    if args.vararg is not None or args.kwonlyargs:
        parts.append("*" + ("" if args.vararg is None else _parameter(args.vararg, None, source)))
    for item, default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        parts.append(_parameter(item, default, source))
    if args.kwarg is not None:
        parts.append("**" + _parameter(args.kwarg, None, source))
    return ", ".join(parts)


def _parameter(item: ast.arg, default: ast.expr | None, source: Source) -> str:
    text = item.arg
    if item.annotation is not None:
        text += f": {source.text(item.annotation) or '...'}"
    if default is not None:
        text += f"={source.text(default) or '...'}"
    return text
