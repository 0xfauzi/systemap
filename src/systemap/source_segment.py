"""The source text of a syntax node, for the values that a person reads.

The function signatures, the `constants` previews, and the class bases come from the
lines of the module text, not from `ast.unparse`. CPython does not keep `ast.unparse` the
same between versions, but the source text of a node does not change with the
interpreter. The column positions of a node count UTF-8 bytes, as in
`ast.get_source_segment`.

A value on more than one line becomes one line. The text removes each comment, and each
backslash at the end of a line. Each line loses the spaces at its two ends. Two lines get
one space between them, but no space after an opening bracket or before a closing
bracket.
"""

from __future__ import annotations

import ast
import re

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
    out = ""
    quote: str | None = None
    for line in text.split("\n"):
        code, quote = _code(line, quote)
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


def _code(line: str, quote: str | None) -> tuple[str, str | None]:
    """Remove the comment and the end backslash of one line.

    `quote` is the quote of a string that continues from the line before, or None. The
    function gives the quote of a string that continues on the next line.
    """
    out: list[str] = []
    index = 0
    while index < len(line):
        if quote is not None:
            index, quote = _in_string(line, index, quote, out)
            continue
        char = line[index]
        if char == "#":
            break
        if char in "'\"":
            quote = char * 3 if line.startswith(char * 3, index) else char
            out.append(quote)
            index += len(quote)
            continue
        out.append(char)
        index += 1
    code = "".join(out)
    if quote is None and code.rstrip().endswith("\\"):
        code = code.rstrip()[:-1]
    return code, quote


def _in_string(line: str, index: int, quote: str, out: list[str]) -> tuple[int, str | None]:
    """Copy one character or one escape of a string. Give the next index and the quote."""
    if line[index] == "\\":
        out.append(line[index : index + 2])
        return index + 2, quote
    if line.startswith(quote, index):
        out.append(quote)
        return index + len(quote), None
    out.append(line[index])
    return index + 1, quote


def signature(node: ast.FunctionDef | ast.AsyncFunctionDef, source: Source) -> str:
    """Give the signature of a function, in the form `def name(arguments) -> result`.

    The text of each annotation and each default value comes from the source. A part
    without a source position gives `...`.
    """
    returns = ""
    if node.returns is not None:
        returns = f" -> {source.text(node.returns) or '...'}"
    prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
    return f"{prefix}{node.name}({arguments(node.args, source)}){returns}"


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
