"""The TypeScript string reader decodes string literals without the parser.

The syntax reader uses it for the escape sequences of a parsed string. The repository
adapter uses it for a quoted method name in a recorded method header. Thus the two
readers give the same name.
"""

from __future__ import annotations

import re

SIMPLE_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v"}
LINE_ENDS = ("\n", "\r", "\u2028", "\u2029")
# A quoted string literal at the start of a text: the name of a method such as
# `"get"(): number`.
QUOTED = r"\"(?:\\[\s\S]|[^\"\\])*\"|'(?:\\[\s\S]|[^'\\])*'"
# One escape sequence of the JavaScript grammar.
_SEQUENCE = re.compile(
    r"\\(?:u\{[0-9A-Fa-f]*\}|u[0-9A-Fa-f]{4}|x[0-9A-Fa-f]{2}|[0-7]{1,3}|\r\n|[\s\S])"
)


def escape(sequence: str) -> str:
    """This function gives the character of one escape sequence of the JavaScript grammar.

    A backslash before a line end continues the line and gives no character. If a code
    point is not valid, for example a code point above U+10FFFF, the function gives the
    escape text without the backslash.
    """
    body = sequence[1:]
    if body.startswith(LINE_ENDS):
        return ""
    digits = body[1:].strip("{}") if body[:1] in ("x", "u") else body
    base = 16 if body[:1] in ("x", "u") else 8
    if digits.isalnum() and (base == 16 or digits.isdigit()):
        try:
            return chr(int(digits, base))
        except (ValueError, OverflowError):
            pass
    return SIMPLE_ESCAPES.get(body, body)


def joined(value: str) -> str:
    """This function joins each surrogate pair into one character. A surrogate without
    its pair becomes U+FFFD, because UTF-8 output cannot contain it."""
    return value.encode("utf-16", "surrogatepass").decode("utf-16", "replace")


def decode_quoted(text: str) -> str:
    """This function gives the value of a quoted string literal, or the text unchanged if
    the text is not a quoted string literal."""
    if not re.fullmatch(QUOTED, text):
        return text
    return joined(_SEQUENCE.sub(lambda found: escape(found.group()), text[1:-1]))
