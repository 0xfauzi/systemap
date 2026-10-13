"""The pull request comment: one link to the Changes view of the published map page.

A repository can publish the map page of each pull request, for example with
`systemap render --base REF`. `[delta] page_url` gives the URL of that page, with
`{number}` in the place of the pull request number. CI then posts one comment with a
link to the Changes view of the page. If the map needs an update, the comment also has
one line that says so. Without `page_url`, `systemap delta` writes no comment.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from systemap import file_write

# The first line of the comment. CI finds the comment with it and changes that comment.
MARKER = "<!-- systemap delta -->"
NUMBER = "{number}"
# The page opens the Changes view for this URL fragment.
CHANGES = "#changes"
KEYS = {"page_url"}


class LinkError(Exception):
    """The command cannot write the comment. The message gives the reason."""


def page_url(raw: dict[str, Any], where: str) -> str:
    """Read `[delta] page_url`. An empty value means that the repository has no page URL.

    A ValueError gives the configuration error.
    """
    table = raw.get("delta", {})
    if not isinstance(table, dict):
        raise ValueError(f"{where}: delta must be a table")
    bad = sorted(set(table) - KEYS)
    if bad:
        raise ValueError(f"{where}: delta has an unknown key: {', '.join(bad)}")
    url = table.get("page_url", "")
    if not isinstance(url, str):
        raise ValueError(f"{where}: delta.page_url must be a string")
    return _checked(url.strip(), where) if url.strip() else ""


def _checked(url: str, where: str) -> str:
    """Give the URL if it is an absolute web address with one place for the number."""
    said = f"{where}: delta.page_url"
    if not url.startswith(("https://", "http://")):
        raise ValueError(f"{said} must start with https:// or http://. The value is {url}")
    if NUMBER not in url:
        raise ValueError(
            f"{said} must contain {NUMBER}. The pull request number replaces it, "
            f'for example "https://example.org/pr-{NUMBER}/".'
        )
    rest = url.replace(NUMBER, "")
    if "{" in rest or "}" in rest:
        raise ValueError(f"{said} can contain only the {NUMBER} placeholder. The value is {url}")
    if "#" in url or any(c.isspace() for c in url):
        raise ValueError(
            f"{said} must not contain # or a space character. The link adds {CHANGES}."
        )
    return url


def number(text: str) -> int:
    """Read the pull request number of the `--pr` option."""
    if not text.isdigit() or int(text) < 1:
        raise argparse.ArgumentTypeError(f"give a pull request number, such as 42, not {text!r}")
    return int(text)


def link(url: str, pr: int) -> str:
    """Give the link to the Changes view of the page for the pull request."""
    return url.replace(NUMBER, str(pr)) + CHANGES


def comment(url: str, pr: int, open_lines: int) -> str:
    """Give the comment: the link, and one line if the map needs an update."""
    out = [MARKER, f"[Open the Changes view of the map]({link(url, pr)})"]
    if open_lines:
        word = "line" if open_lines == 1 else "lines"
        out += [
            "",
            f"A map update is necessary ({open_lines} {word}). The log of the delta job "
            "gives the action for each line.",
        ]
    return "\n".join(out) + "\n"


def write(path: str, url: str, pr: int, open_lines: int, root: Path) -> bool:
    """Write the comment to `path` if the configuration has a page URL.

    Without a page URL, the function writes no file. The result tells if it wrote one.
    The write replaces a link at the path. It does not write to the target of the link.
    For a path in the repository at `root`, each folder of the path must be in the
    repository. A different path is in a folder of the person who runs the command, for
    example a folder of the CI runner. `file_write.RefusedFile` gives a refused path.
    """
    if not url:
        return False
    if not pr:
        raise LinkError("delta --comment must have --pr with the pull request number.")
    target = Path(os.path.abspath(path))
    inside = any(target.is_relative_to(base) for base in (root, root.resolve()))
    file_write.write_atomic(root if inside else target.parent, target, comment(url, pr, open_lines))
    return True
