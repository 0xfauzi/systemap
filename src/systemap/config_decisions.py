"""The settings validate `[decisions]`, `[judgement] require_reviews`, `[rules]`, and citations.

`systemap decisions` records the verdicts of a coding agent. A supported answer for a
judgement line can keep its citations in `[judgement] answered`. These functions give a
ValueError for an incorrect value. The configuration reader changes it to a ConfigError.
"""

from __future__ import annotations

import re
from typing import Any

DECISIONS_KEYS = {"max_contradicted"}
# A loop bound, not a measured value: the quantity of `contradicted` results for one claim
# before the request becomes unknown.
MAX_CONTRADICTED = 3
RULES_UNKNOWN = ("warn", "fail")
CITATION_KEYS = ("file", "start_line", "end_line", "sha256")
SHA256 = re.compile(r"[0-9a-f]{64}")

Citation = tuple[str, int, int, str]


def read(raw: dict[str, Any], where: str) -> dict[str, Any]:
    """Give the values of `[decisions] max_contradicted` and `[judgement] require_reviews`."""
    decisions = raw.get("decisions", {})
    if not isinstance(decisions, dict):
        raise ValueError(f"{where}: decisions must be a table")
    bad = sorted(set(decisions) - DECISIONS_KEYS)
    if bad:
        raise ValueError(f"{where}: decisions has an unknown key: {', '.join(bad)}")
    limit = decisions.get("max_contradicted", MAX_CONTRADICTED)
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError(f"{where}: decisions.max_contradicted must be an integer of 1 or more.")
    judgement = raw.get("judgement", {})
    required = judgement.get("require_reviews", False) if isinstance(judgement, dict) else False
    if not isinstance(required, bool):
        raise ValueError(f"{where}: judgement.require_reviews must be true or false.")
    return {"max_contradicted": limit, "require_reviews": required}


def citations(value: Any, location: str) -> tuple[Citation, ...]:
    """Give the citations of one answer. Each citation is (file, start_line, end_line, sha256)."""
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{location} citations must be a list of tables.")
    return tuple(citation(item, f"{location} citations[{k}]") for k, item in enumerate(value, 1))


def citation(item: Any, location: str) -> Citation:
    """Give one citation, or a ValueError that tells the incorrect field."""
    if not isinstance(item, dict) or set(item) != set(CITATION_KEYS):
        raise ValueError(f"{location} must be a table with the keys {', '.join(CITATION_KEYS)}.")
    file, start, end, digest = (item[key] for key in CITATION_KEYS)
    if not isinstance(file, str) or not file.strip():
        raise ValueError(f"{location} file must be a path relative to the repository root.")
    for name, number in (("start_line", start), ("end_line", end)):
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise ValueError(f"{location} {name} must be an integer of 1 or more.")
    if start > end:
        raise ValueError(f"{location} start_line must not be more than end_line.")
    if not isinstance(digest, str) or SHA256.fullmatch(digest) is None:
        raise ValueError(f"{location} sha256 must be a SHA-256 digest of the full file.")
    return file, start, end, digest


def rules_unknown(raw: dict[str, Any], where: str) -> str:
    """Give `[rules] unknown`: the effect of an import rule with the result unknown."""
    rules = raw.get("rules", {})
    if not isinstance(rules, dict):
        raise ValueError(f"{where}: rules must be a table")
    bad = sorted(set(rules) - {"unknown"})
    if bad:
        raise ValueError(f"{where}: rules has an unknown key: {', '.join(bad)}")
    value = rules.get("unknown", "warn")
    if value not in RULES_UNKNOWN:
        raise ValueError(f'{where}: rules.unknown must be "warn" or "fail"')
    return str(value)
