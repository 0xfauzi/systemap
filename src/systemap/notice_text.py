"""The notice rule finds a license notice or a copyright notice in the opening text of a
module. A notice is not a description of the module.

Each language adapter uses this rule for the module description: the Python docstring,
or the first TypeScript comment. A text is a notice if it starts with one of these
marks, with any letter case: `Copyright`, `©`, `(c)`, `SPDX-` (the SPDX tags of the
REUSE specification), `Licensed under`, `@license`, or `@preserve`. The full text is
then a notice, because the paragraphs after a copyright line usually give the license
terms. The TypeScript adapter also skips a legal comment of esbuild: a comment that
starts with `/*!` or `//!`.
"""

from __future__ import annotations

import re

NOTICE = re.compile(
    r"(?:copyright\b|©|\(c\)|spdx-|licensed\s+under\b|@license\b|@preserve\b)", re.IGNORECASE
)
# The length limit of a module description in the facts.
LIMIT = 320


def is_notice(text: str) -> bool:
    """Give True if a text starts with a license mark or a copyright mark."""
    return bool(NOTICE.match(text.strip()))


def description(text: str | None) -> str:
    """Give the first paragraph of a text on one line, with a length limit. A notice
    gives an empty string. A paragraph ends at a blank line.

    The facts keep only this paragraph. Full descriptions doubled the facts file, but the
    page did not show that text.
    """
    if not text or is_notice(text):
        return ""
    found = " ".join(text.strip().split("\n\n")[0].split())
    return found if len(found) <= LIMIT else found[: LIMIT - 1] + "…"
