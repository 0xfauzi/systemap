"""The terminal text rule shows untrusted text as visible characters.

A model, a coding agent, a commit subject, or a source file can supply text that contains
control characters. A terminal can use such characters as commands. For example, ESC
starts a color change or a link (OSC 8), and BEL makes a sound. A line separator can
divide one output line into two lines. Thus the commands give this text to `printable`
before they write it to the terminal.

`printable` replaces each of these characters with a visible escape `\\uXXXX`:

- The C0 control characters U+0000 to U+001F, which include the newline and the tab.
- DEL (U+007F) and the C1 control characters U+0080 to U+009F.
- The line separator U+2028 and the paragraph separator U+2029.
- A surrogate character that has no pair. A file name that is not UTF-8 can give one.

The escape is also a valid escape in a JSON string. Thus a JSON output keeps its
meaning. The rule does not change other text. A backslash does not change, so a normal
line gives the same bytes as before.
"""

from __future__ import annotations

import re
import sys
from typing import TextIO

UNSAFE = re.compile("[\x00-\x1f\x7f-\x9f\u2028\u2029\ud800-\udfff]")
# The same characters without the newline. A command output can have more than one line.
UNSAFE_IN_LINES = re.compile("[\x00-\x09\x0b-\x1f\x7f-\x9f\u2028\u2029\ud800-\udfff]")


def _escape(match: re.Match[str]) -> str:
    return f"\\u{ord(match.group()):04x}"


def printable(text: str) -> str:
    """Give the text with each control character and separator as a visible escape."""
    return UNSAFE.sub(_escape, text)


def lines(text: str) -> str:
    """Give the text as `printable` gives it, but keep each newline.

    The commands use this function for a complete output that has more than one line.
    """
    return UNSAFE_IN_LINES.sub(_escape, text)


def has_control(text: str) -> bool:
    """Give True if the text contains a character that `printable` replaces."""
    return UNSAFE.search(text) is not None


def show(*parts: object, sep: str = " ", file: TextIO | None = None) -> None:
    """Write the parts as `print` writes them, with each line as `lines` gives it."""
    print(lines(sep.join(str(part) for part in parts)), file=file or sys.stdout)
