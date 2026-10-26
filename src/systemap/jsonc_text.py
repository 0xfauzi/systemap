r"""The JSONC reader removes the comments and the trailing commas of a tsconfig text.

Each step reads the text from start to end one time. Thus the cost is linear in the
length of the text. The result is the same text that these two regular expressions gave:
`"(?:\\.|[^"\\])*"|//[^\r\n]*|/\*[\s\S]*?\*/` (comments become spaces) and then
`"(?:\\.|[^"\\])*"|,(?=\s*[}\]])` (trailing commas are removed). Those expressions
tried a new string at each quote, and a new comment at each "/*", so an unclosed
string or comment made their cost quadratic.
"""

from __future__ import annotations

import re

# The body of a JSON string after the opening quote. The match stops at the closing
# quote, at a backslash before a line feed or at the end, or at the end of the text.
# The two parts of the body cannot match the same character, so the match does not go
# back.
_STRING_BODY = re.compile(r'[^"\\]*(?:\\.[^"\\]*)*')
_LINE_END = re.compile(r"[\r\n]")
_NOT_LINE_END = re.compile(r"[^\r\n]")


class _Strings:
    """This record finds the JSON strings of one text.

    A string that has no closing quote stops at an index, `open_until`. Each quote
    before that index is in an escape of the same string, so a string from that quote
    has no closing quote either. Thus the reader does not examine those quotes.
    """

    def __init__(self, text: str) -> None:
        self._text = text
        self.open_until = 0

    def end(self, start: int) -> int | None:
        """Give the index after the string at `start`, or None if the string is not closed."""
        if start < self.open_until:
            return None
        match = _STRING_BODY.match(self._text, start + 1)
        stop = match.end() if match is not None else start + 1
        if self._text.startswith('"', stop):
            return stop + 1
        self.open_until = stop
        return None


def strip_jsonc(text: str) -> str:
    """This function removes JSONC comments and trailing commas without changing string
    values.

    A comment becomes spaces, and its line ends stay. Thus the line and column of a JSON
    error stay the same. An unclosed string or comment stays in the text, and the JSON
    parser gives the error.
    """
    without_comments = _rewrite(_Comments(text.lstrip("\ufeff")))
    return _rewrite(_Commas(without_comments))


class _Step:
    """This record is one step of the reader: the marks that start a token, and the rule
    that gives the token.

    `marks` gives two patterns. The first pattern finds a token in the part of an
    unclosed string, where a quote cannot start a string. The second pattern finds a
    token in other parts of the text.
    """

    def __init__(self, text: str) -> None:
        self.text = text
        self.strings = _Strings(text)

    def marks(self) -> tuple[re.Pattern[str], re.Pattern[str]]:
        raise NotImplementedError

    def other(self, match: re.Match[str]) -> tuple[int, str | None] | None:
        raise NotImplementedError

    def token(self, match: re.Match[str]) -> tuple[int, str | None] | None:
        """Give the index after the token and its replacement, or None if no token
        starts at the match. A replacement of None keeps the token text."""
        if match.group() == '"':
            end = self.strings.end(match.start())
            return None if end is None else (end, None)
        return self.other(match)


class _Comments(_Step):
    """This step changes each comment to spaces."""

    BOTH = (re.compile(r"//|/\*"), re.compile(r'"|//|/\*'))
    LINE = (re.compile(r"//"), re.compile(r'"|//'))

    def __init__(self, text: str) -> None:
        super().__init__(text)
        # If no comment closes after an index, no later comment closes.
        self.block_close = True

    def marks(self) -> tuple[re.Pattern[str], re.Pattern[str]]:
        return self.BOTH if self.block_close else self.LINE

    def other(self, match: re.Match[str]) -> tuple[int, str | None] | None:
        start, text = match.start(), self.text
        if match.group() == "//":
            line_end = _LINE_END.search(text, start + 2)
            end = len(text) if line_end is None else line_end.start()
        else:
            close = text.find("*/", start + 2)
            self.block_close = close >= 0
            if close < 0:
                return None
            end = close + 2
        return end, _NOT_LINE_END.sub(" ", text[start:end])


class _Commas(_Step):
    """This step removes each comma before a closing bracket or brace."""

    MARKS = (re.compile(r",(?=\s*[}\]])"), re.compile(r'"|,(?=\s*[}\]])'))

    def marks(self) -> tuple[re.Pattern[str], re.Pattern[str]]:
        return self.MARKS

    def other(self, match: re.Match[str]) -> tuple[int, str | None] | None:
        return match.start() + 1, ""


def _rewrite(step: _Step) -> str:
    """This function finds each token from the start of the text to the end, and
    replaces it.

    After a token, the search continues after the token. Otherwise, it continues at the
    next character.
    """
    text = step.text
    parts: list[str] = []
    done = position = 0
    while (match := _next_mark(step, position)) is not None:
        result = step.token(match)
        if result is None:
            position = match.start() + 1
            continue
        end, replacement = result
        if replacement is not None:
            parts += [text[done : match.start()], replacement]
            done = end
        position = end
    parts.append(text[done:])
    return "".join(parts)


def _next_mark(step: _Step, position: int) -> re.Match[str] | None:
    """Give the next possible token, or None at the end of the text.

    The part of an unclosed string ends at a backslash or at the end of the text. Thus a
    mark in the part cannot continue after the end of the part, and the search can stop
    there.
    """
    inside, outside = step.marks()
    open_until = step.strings.open_until
    if position < open_until:
        found = inside.search(step.text, position, open_until)
        if found is not None:
            return found
        position = open_until
    return outside.search(step.text, position)
