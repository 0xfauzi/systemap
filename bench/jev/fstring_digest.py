"""Measure issue 126: does the syntax dump of a file change with the Python patch version?

For each source file in FILE_LIST, the script parses the file with the current
interpreter and prints one JSON line:

- "digest": the SHA-256 of `_dump_python_syntax` with the issue 126 change. Issue 136
  replaced that function with `syntax_text.text`. The script now uses the new function,
  so a new run does not give the recorded digests.
- "empties": the number of empty `Constant('')` items in the parts of each f-string.
  The change removes exactly these items from the dump. Thus the change gives a
  different digest from the earlier dump if and only if "empties" is more than 0.

Acceptance values, written before the run on 2026-11-02:

1. With the change, each file gives the same digest on 3.11, 3.12.3, 3.12.13 and 3.13.
2. On 3.11, 3.12.13 and 3.13, "empties" is 0 for 100% of the files, so the change gives
   the earlier digest. Then a user on those versions keeps each recorded digest.

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

from systemap import syntax_text


def empties(tree: ast.AST) -> int:
    """Count the empty string constants in the parts of each f-string."""
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.JoinedStr)
        for part in node.values
        if isinstance(part, ast.Constant) and part.value == ""
    )


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(listing: Path) -> None:
    version = sys.version.split()[0]
    for path in listing.read_text(encoding="utf-8").splitlines():
        if not path.strip():
            continue
        try:
            tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, ValueError):
            continue
        row = {
            "v": version,
            "path": path,
            "empties": empties(tree),
            "digest": sha(syntax_text.text(tree)),
        }
        print(json.dumps(row))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
