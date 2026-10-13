"""The earlier `jev flow` context: the source lines that use a name imported from the other side.

`flow_context.py` measured this selector as its `base` arm, and its other arms start
from these lines. `audit_code.code_between` replaced it with the selector that reads the
`call_sites` fact. This module keeps the earlier selector for the bench only. It is the
code of `src/systemap/audit_code.py` at the parent of commit 0f70d82, with these changes:
the bench reads only Python modules, and a module of a different language stops the
command. All the repositories in the bench sets are Python repositories.

A named import gives the names directly. A whole-module import (`*`) does not give the
local name. Then the import statements give it:

- `import a.b` gives `a.b`, and `import a.b as x` gives `x`.
- `from a import b` gives `b`, and `from a.b import *` gives the public names of `a.b`.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

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


def _is_or_in(name: str, target: str) -> bool:
    return name == target or name.startswith(target + ".")


def _from_bindings(node: ast.ImportFrom, last: str, public: list[str]) -> set[str]:
    out: set[str] = set()
    for alias in node.names:
        if alias.name == WHOLE and (node.module or "").rsplit(".", 1)[-1] == last:
            out |= set(public)
        elif alias.name == last:
            out.add(alias.asname or alias.name)
    return out


def _python_bindings(text: str, target: str, public: list[str]) -> set[str]:
    """Give the local names that the import statements bind for the target module."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return set()
    last = target.rsplit(".", 1)[-1]
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.asname or a.name for a in node.names if _is_or_in(a.name, target)}
        elif isinstance(node, ast.ImportFrom):
            out |= _from_bindings(node, last, public)
    return out


def bindings(text: str, facts: dict[str, Any], module: str, target: str) -> set[str]:
    """Give the local names that bind the target module in the source of the module."""
    if not str(facts["components"][module].get("file", "")).endswith(".py"):
        raise SystemExit(f"{module}: the bench reads only Python modules")
    record = facts["components"].get(target, {})
    public = [n["name"] for n in record.get("names", [])]
    return _python_bindings(text, target, public)


def _uses_of(root: Path, facts: dict[str, Any], module: str, others: list[str]) -> list[str]:
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
            names |= bindings(text, facts, module, target)
    return lines_using(text, module, names) if names else []


def code_between(
    root: Path, facts: dict[str, Any], mods: dict[str, list[str]], src: str, dst: str
) -> list[str]:
    """Get at most 30 lines that use an import name from the other component."""
    lines: list[str] = []
    for a_card, b_card in ((src, dst), (dst, src)):
        for a in mods.get(a_card, []):
            lines += _uses_of(root, facts, a, mods.get(b_card, []))
    return lines[:LINES_PER_FLOW]
