"""The TypeScript syntax reader parses source and reads the text of syntax nodes.

It also reads the module docstring from the first comment of a module.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

TS = Language(tree_sitter_typescript.language_typescript())
TSX = Language(tree_sitter_typescript.language_tsx())
# A comment that gives an instruction to a tool, not a description of the module.
DIRECTIVE = re.compile(
    r"(?:eslint|prettier|istanbul|c8\s|tslint|jshint|global\s|@ts-|@jsx|/\s*<(?:reference|amd))"
)
# The grammar does not read `export type * from` and the variance keywords `in` and `out`
# in a type parameter list. A second parse replaces these keywords with spaces.
_TYPE_STAR = re.compile(r"(?m)^([ \t]*export\s+)(type)(?=\s+\*)")
_VARIANCE = re.compile(
    r"(?<=[<,])(\s*(?:const\s+)?)((?:(?:in|out)\s+)+)"
    r"(?=[A-Za-z_$][\w$]*\s*(?:extends\b|[,>=]))"
)


def _tree(raw: str, path: str = "") -> Node:
    language = TSX if path.endswith(".tsx") else TS
    return Parser(language).parse(raw.encode("utf-8")).root_node


def syntax_tree(raw: str, path: str = "") -> Node:
    """This function parses TypeScript or TSX source.

    If the first parse has an error, a second parse reads the source without the
    keyword `type` in `export type * from` and without variance keywords. The function
    uses the second tree only if it has no error. The other tokens keep their positions.
    """
    root = _tree(raw, path)
    if not root.has_error:
        return root
    rewritten = _VARIANCE.sub(_blank_keywords, _TYPE_STAR.sub(_blank_keywords, raw))
    if rewritten == raw:
        return root
    second = _tree(rewritten, path)
    return root if second.has_error else second


def _blank_keywords(match: re.Match[str]) -> str:
    return match.group(1) + re.sub(r"[^\n]", " ", match.group(2))


def _root(raw: str, path: str = "") -> Node | None:
    root = syntax_tree(raw, path)
    return None if root.has_error else root


def _walk(node: Node) -> Iterator[Node]:
    yield node
    for child in node.named_children:
        yield from _walk(child)


def _text(node: Node | None) -> str:
    return (node.text or b"").decode("utf-8") if node is not None else ""


def _one_line(text: str) -> str:
    return " ".join(text.split())


def string_value(node: Node | None) -> str:
    """This function gives the value of a string literal. Each escape sequence gives its
    character.

    The value is empty if the node is not a string literal.
    """
    if node is None or node.type != "string":
        return ""
    parts = (
        _escape(_text(child)) if child.type == "escape_sequence" else _text(child)
        for child in node.named_children
    )
    # Two escape sequences such as `\ud83d\ude00` give one character. A surrogate
    # without its pair becomes U+FFFD, because UTF-8 output cannot contain it.
    value = "".join(parts)
    return value.encode("utf-16", "surrogatepass").decode("utf-16", "replace")


SIMPLE_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v"}
LINE_ENDS = ("\n", "\r", "\u2028", "\u2029")


def _escape(sequence: str) -> str:
    """This function gives the character of one escape sequence of the JavaScript grammar.

    A backslash before a line end continues the line and gives no character.
    """
    body = sequence[1:]
    if body.startswith(LINE_ENDS):
        return ""
    digits = body[1:].strip("{}") if body[:1] in ("x", "u") else body
    base = 16 if body[:1] in ("x", "u") else 8
    if digits.isalnum() and (base == 16 or digits.isdigit()):
        try:
            return chr(int(digits, base))
        except ValueError:
            pass
    return SIMPLE_ESCAPES.get(body, body)


def docstring(root: Node) -> str:
    """This function gives the first paragraph of the first comment before the first
    statement, without comment marks.

    A tool directive such as `eslint-disable` or `@ts-check` is not a docstring.
    """
    for node in root.named_children:
        if node.type == "hash_bang_line":
            continue
        if node.type != "comment":
            return ""
        text = _comment_text(_text(node))
        if text and not DIRECTIVE.match(text):
            paragraph = _one_line(text.split("\n\n")[0])
            return paragraph if len(paragraph) <= 320 else paragraph[:319] + "\u2026"
    return ""


def _comment_text(comment: str) -> str:
    body = comment.removeprefix("//") if comment.startswith("//") else comment
    body = body.removeprefix("/**").removeprefix("/*").removesuffix("*/")
    lines = (line.strip().removeprefix("*").strip() for line in body.splitlines())
    return "\n".join(lines).strip()
