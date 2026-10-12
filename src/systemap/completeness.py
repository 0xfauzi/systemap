"""Make the read condition of a module record, with the same meaning for each language.

Each module record in the facts has one `completeness` record. A language adapter
writes it, and extraction adds `unresolved_imports`. Shared code reads it through
`model.source_parsed`, and does not read `parse_error` or `unknown`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def parse_state(problem: Mapping[str, Any] | None) -> dict[str, Any]:
    """Give the read condition from the first read problem or parse problem of a module.

    Without a problem, `parsed` is `true`, `line` is 0, and `reason` is empty.
    """
    if problem is None:
        return {"parsed": True, "line": 0, "reason": ""}
    return {
        "parsed": False,
        "line": int(problem.get("line", 0) or 0),
        "reason": str(problem.get("reason", "")),
    }
