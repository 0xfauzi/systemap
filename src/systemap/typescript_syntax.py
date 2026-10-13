"""The TypeScript syntax reader parses source and reads the text of syntax nodes.

It also reads the module docstring from the first comment of a module.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

from systemap import unknown_causes
from systemap.notice_text import description, is_notice
from systemap.typescript_repo import TYPESCRIPT_REPOSITORY
from systemap.typescript_strings import escape, joined

TS = Language(tree_sitter_typescript.language_typescript())
TSX = Language(tree_sitter_typescript.language_tsx())
# A comment that gives an instruction to a tool, not a description of the module.
DIRECTIVE = re.compile(
    r"(?:eslint|prettier|istanbul|c8\s|tslint|jshint|global\s|@ts-|@jsx|/\s*<(?:reference|amd))"
)
# A legal comment of esbuild: minifiers keep it, because it holds a license notice.
LEGAL = ("/*!", "//!")
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
    A replacement in a string, a template, a regular expression, or a comment of the
    second tree is not used. Thus the second tree has the literal text of the source.
    """
    root = _tree(raw, path)
    if not root.has_error:
        return root
    spans = _keyword_spans(raw)
    if not spans:
        return root
    second = _tree(_blank(raw, spans), path)
    kept = [span for span in spans if not _in_literal(second, raw, span)]
    if kept != spans:
        if not kept:
            return root
        second = _tree(_blank(raw, kept), path)
    return root if second.has_error else second


# The syntax nodes that contain literal text, not tokens.
LITERALS = frozenset({"string", "template_string", "regex", "comment"})


def _keyword_spans(raw: str) -> list[tuple[int, int]]:
    """Give the character spans of the keywords that the second parse replaces."""
    spans = [found.span(2) for found in _TYPE_STAR.finditer(raw)]
    spans += [found.span(2) for found in _VARIANCE.finditer(_blank(raw, spans))]
    return sorted(spans)


def _blank(raw: str, spans: list[tuple[int, int]]) -> str:
    """Replace each character in the spans with a space. A line end stays."""
    text = list(raw)
    for start, end in spans:
        text[start:end] = re.sub(r"[^\n]", " ", raw[start:end])
    return "".join(text)


def _in_literal(root: Node, raw: str, span: tuple[int, int]) -> bool:
    """Tell if a literal node of the tree contains the span."""
    start = len(raw[: span[0]].encode("utf-8"))
    end = len(raw[: span[1]].encode("utf-8"))
    node: Node | None = root.descendant_for_byte_range(start, end)
    while node is not None:
        if node.type in LITERALS:
            return True
        node = node.parent
    return False


# The text limit of a source excerpt in a parse problem.
EXCERPT = 120


def parse_problem(raw: str, path: str = "") -> dict[str, Any]:
    """This function gives the first parser error for a retained module record.

    The excerpt is the source line of the error and the line before it, because the
    error node can be only one token, such as `,`. The `parser` field gives the parser
    version. A valid file can fail when the grammar of that version does not read its
    syntax.
    """
    root = _tree(raw, path)
    node = next((child for child in _walk(root) if child.type == "ERROR" or child.is_missing), root)
    row = node.start_point.row
    source = _one_line(" ".join(raw.splitlines()[max(row - 1, 0) : row + 1]))
    if len(source) > EXCERPT:
        source = "\u2026" + source[-(EXCERPT - 1) :]
    # The reason goes into a shared finding line. Thus it names no language. The line is
    # the identity of the finding. Thus the excerpt and the parser version are separate
    # fields. `answer_migrations` reads the earlier forms.
    return {
        "line": row + 1,
        "reason": "The parser could not parse the source syntax.",
        "source": source,
        "parser": TYPESCRIPT_REPOSITORY.parser_version(),
        "cause": unknown_causes.SYNTAX,
    }


def _root(raw: str, path: str = "") -> Node | None:
    root = syntax_tree(raw, path)
    return None if root.has_error else root


def _walk(node: Node) -> Iterator[Node]:
    yield node
    for child in node.named_children:
        yield from _walk(child)


def _text(node: Node | None) -> str:
    return (node.text or b"").decode("utf-8") if node is not None else ""


def first_named(node: Node | None) -> Node | None:
    """This function gives the first named child of a node that is not a comment.

    The grammar gives a comment as a named node at each position, as in
    `import(/* name */ "./a")`.
    """
    if node is None:
        return None
    return next((child for child in node.named_children if child.type != "comment"), None)


def first_argument(call: Node) -> Node | None:
    """This function gives the first argument of a call, or None. A comment is not an
    argument."""
    return first_named(call.child_by_field_name("arguments"))


def _one_line(text: str) -> str:
    return " ".join(text.split())


def specifier_name(node: Node | None) -> str:
    """This function gives the name of an import or export specifier part: an identifier,
    or the value of a string, as in `export { a as 'module.exports' }`."""
    if node is None:
        return ""
    return string_value(node) if node.type == "string" else _text(node)


def string_value(node: Node | None) -> str:
    """This function gives the value of a string literal. Each escape sequence gives its
    character.

    The value is empty if the node is not a string literal.
    """
    if node is None or node.type != "string":
        return ""
    parts = (
        escape(_text(child)) if child.type == "escape_sequence" else _text(child)
        for child in node.named_children
    )
    # Two escape sequences such as `\ud83d\ude00` give one character.
    return joined("".join(parts))


def docstring(root: Node) -> str:
    """This function gives the first paragraph of the first comment before the first
    statement, without comment marks.

    A tool directive such as `eslint-disable` or `@ts-check` is not a docstring. A
    license notice is not a docstring (`notice_text`): a legal comment that starts with
    `/*!` or `//!`, or a comment that starts with a notice mark. The `//` comments on
    the lines directly below a notice are part of the notice. The next comment can then
    give the docstring.
    """
    notice_end = -2
    for node in root.named_children:
        if node.type == "hash_bang_line":
            continue
        if node.type != "comment":
            return ""
        raw = _text(node)
        if raw.startswith("//") and node.start_point.row == notice_end + 1:
            notice_end = node.end_point.row
            continue
        text = _comment_text(raw)
        if raw.startswith(LEGAL) or (text and is_notice(text)):
            notice_end = node.end_point.row
        elif text and not DIRECTIVE.match(text):
            return description(text)
    return ""


def _comment_text(comment: str) -> str:
    body = comment.removeprefix("//") if comment.startswith("//") else comment
    body = body.removeprefix("/**").removeprefix("/*").removesuffix("*/")
    lines = (line.strip().removeprefix("*").strip() for line in body.splitlines())
    return "\n".join(lines).strip()
