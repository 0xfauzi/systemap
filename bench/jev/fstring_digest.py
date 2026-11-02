"""Measure issue 126: does the syntax dump of a file change with the Python patch version?

For each source file in FILE_LIST, the script parses the file with the current
interpreter and prints one JSON line:

- "now": the SHA-256 of `_dump_python_syntax` without the issue 126 change. The script
  calls the dump with the empty constants in place, so the value is the earlier dump.
- "fixed": the SHA-256 after the removal of each empty `Constant('')` from the parts of
  each f-string, which is the issue 126 change.
- "empties": the number of such empty constants in the parsed tree.

Acceptance values, written before the run on 2026-11-02:

1. With the change, each file gives the same "fixed" digest on 3.11, 3.12.3, 3.12.13
   and 3.13.
2. On 3.11, 3.12.13 and 3.13, "fixed" equals "now" for 100% of the files. Then a user on
   those versions keeps each recorded digest.

Run from the repository root, once for each interpreter:

    uv run --isolated --python 3.12.3 python bench/jev/fstring_digest.py FILES > out-3.12.3.jsonl

FILES is a text file with one source path on each line.
"""

from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path

from systemap import extract


def empties(tree: ast.AST) -> int:
    """Count the empty string constants in the parts of each f-string."""
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.JoinedStr)
        for part in node.values
        if isinstance(part, ast.Constant) and part.value == ""
    )


def earlier_dump(tree: ast.AST) -> str:
    """Give the dump without the issue 126 change: the empty constants stay."""
    found = extract._hide_empty_strings(tree)
    for joined, values in found:
        joined.values = values
    hidden = extract._hide_empty_type_params(tree)
    fields = {"show_empty": True} if sys.version_info >= (3, 13) else {}
    try:
        return ast.dump(tree, include_attributes=False, **fields)
    finally:
        extract._restore(hidden, [])


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(listing: Path) -> None:
    version = sys.version.split()[0]
    for path in listing.read_text(encoding="utf-8").split():
        try:
            tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, ValueError):
            continue
        row = {
            "v": version,
            "path": path,
            "empties": empties(tree),
            "now": sha(earlier_dump(tree)),
            "fixed": sha(extract._dump_python_syntax(tree)),
        }
        print(json.dumps(row))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
