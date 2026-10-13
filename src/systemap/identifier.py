"""This module reads a complete source identifier that can contain Unicode letters.

A Python name and a TypeScript name start with a Unicode letter or `_`. The other
characters can be Unicode letters, combining marks, digits, or connector characters.
A TypeScript name can also contain `$` and the two zero-width joiner characters. The
rule accepts these characters for each language, as the earlier ASCII rule accepted `$`.
The interface check and the method readers of the language adapters use this rule.
"""

from __future__ import annotations

# The characters that the Unicode identifier test does not accept but a TypeScript
# name can contain: `$`, the zero-width non-joiner, and the zero-width joiner.
EXTRA = frozenset({"$", "\N{ZERO WIDTH NON-JOINER}", "\N{ZERO WIDTH JOINER}"})


def starts(char: str) -> bool:
    """Give `True` if the character can be the first character of an identifier."""
    return char == "$" or char.isidentifier()


def continues(char: str) -> bool:
    """Give `True` if the character can be a character after the first one."""
    return char in EXTRA or f"_{char}".isidentifier()


def read(text: str, start: int = 0) -> str:
    """Give the complete identifier that starts at `start`, or an empty string.

    The identifier ends before the first character that cannot continue it. Thus the
    result is not a part of a longer identifier.
    """
    if start >= len(text) or not starts(text[start]):
        return ""
    end = start + 1
    while end < len(text) and continues(text[end]):
        end += 1
    return text[start:end]


def complete(text: str) -> bool:
    """Give `True` if all of the text is one identifier."""
    return bool(text) and read(text) == text
