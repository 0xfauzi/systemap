"""Measure the module comment rule proposed in issue #91.

Acceptance, before measurement: use the tag rule only if it removes symbol comments
and keeps every module description found by manual examination in ky and vite.
Otherwise, record the loss and select a narrower rule.

Read all tracked TypeScript source files, including tests. Exclude declaration files.
Keep the repository revisions and each changed description in the JSON result.
Run: uv run python bench/typescript_descriptions.py /path/to/ky /path/to/vite
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from tree_sitter import Node

from systemap.notice_text import description, is_notice
from systemap.typescript_config import DECLARATION_SUFFIXES, SOURCE_SUFFIXES
from systemap.typescript_syntax import (
    DIRECTIVE,
    LEGAL,
    _comment_text,
    _text,
    docstring,
    syntax_tree,
)

TAG = re.compile(r"(?m)^\s*@(?:module|packageDocumentation)(?:\s|$)")


def earlier_description(root: Node) -> str:
    """Apply the comment rule from systemap revision 077155e, before issue #91."""
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


def measure(repo: Path) -> dict[str, object]:
    """Give the current description and the tag-rule result for each described file."""
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=repo).decode().split("\0")
    rows = []
    files = 0
    for name in tracked:
        path = repo / name
        if path.suffix not in SOURCE_SUFFIXES or name.endswith(DECLARATION_SUFFIXES):
            continue
        files += 1
        root = syntax_tree(path.read_text(encoding="utf-8"), name)
        current = earlier_description(root)
        if not current:
            continue
        rows.append({"file": name, **description_row(root, current)})
    return {"repository": repo.name, "revision": revision, "files": files, "descriptions": rows}


def description_row(root: Node, current: str) -> dict[str, object]:
    """Give the description results and the position of the comment."""
    comment = next(
        node
        for node in root.named_children
        if node.type == "comment" and description(_comment_text(_text(node))) == current
    )
    text = _comment_text(_text(comment))
    match = TAG.search(text) if _text(comment).startswith("/**") else None
    following = comment.next_named_sibling
    return {
        "current": current,
        "tagged": description(text[: match.start()]) if match else "",
        "revised": docstring(root),
        "following": following.type if following else "",
        "blank_line": bool(following and following.start_point.row > comment.end_point.row + 1),
    }


if __name__ == "__main__":
    print(json.dumps([measure(Path(name)) for name in sys.argv[1:]], indent=2))
