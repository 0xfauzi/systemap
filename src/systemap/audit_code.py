"""Find the source lines where the modules of two components meet, for `jev flow`.

The facts give the names that each module imports from another module. A named
import gives the names directly. A whole-module import (`*`) and a default import
(`default`) do not give the local name. The language adapter then reads the import
statements of the module to find the local names that bind the target module.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from systemap.language import RepositoryAdapter

WHOLE = "*"
DEFAULT = "default"
LINES_PER_FLOW = 30


def _source(root: Path, facts: dict[str, Any], module: str) -> str | None:
    try:
        return (root / str(facts["components"][module]["file"])).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError, KeyError):
        return None


def lines_using(text: str, module: str, names: set[str]) -> list[str]:
    """Give the lines of a module source that use one of the names."""
    pat = re.compile(r"\b(" + "|".join(map(re.escape, sorted(names))) + r")\b")
    return [
        f"{module}:{i}: {ln.strip()[:160]}"
        for i, ln in enumerate(text.splitlines(), 1)
        if pat.search(ln)
    ]


def _uses_of(
    root: Path,
    facts: dict[str, Any],
    module: str,
    others: list[str],
    language: RepositoryAdapter,
) -> list[str]:
    uses = facts["components"][module].get("uses", {})
    wanted = {b: set(uses[b]) for b in others if b in uses}
    if not wanted:
        return []
    text = _source(root, facts, module)
    if text is None:
        return []
    names: set[str] = set()
    for target, imported in wanted.items():
        names |= imported - {WHOLE, DEFAULT}
        if imported & {WHOLE, DEFAULT}:
            record = facts["components"].get(target, {})
            names |= language.local_bindings(text, target, record)
    return lines_using(text, module, names) if names else []


def code_between(
    root: Path,
    facts: dict[str, Any],
    mods: dict[str, list[str]],
    cards: tuple[str, str],
    language: RepositoryAdapter,
) -> list[str]:
    """Get at most 30 lines using an import name from the other component."""
    src, dst = cards
    lines: list[str] = []
    for a_card, b_card in ((src, dst), (dst, src)):
        for a in mods.get(a_card, []):
            lines += _uses_of(root, facts, a, mods.get(b_card, []), language)
    return lines[:LINES_PER_FLOW]
