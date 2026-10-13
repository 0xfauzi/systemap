"""Compare a repository-relative path with the configured `test_patterns`.

Each language adapter uses this rule. Thus, a pattern has the same meaning for each
language. The `*` wildcard can also include a `/`. A pattern that starts with `**/` can
also select a file in the repository root.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Iterable
from pathlib import PurePosixPath


def matches_test_pattern(path: str, patterns: Iterable[str]) -> bool:
    """Give `True` if a configured test pattern selects the repository-relative path."""
    relative = PurePosixPath(path).as_posix()
    return any(
        fnmatch.fnmatchcase(relative, pattern)
        or fnmatch.fnmatchcase(relative, pattern.replace("**/", ""))
        for pattern in patterns
    )
