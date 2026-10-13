"""Find the source lines where the modules of two components meet, for `jev flow`.

The facts give the names that each module imports from another module. A named
import gives the names directly. A whole-module import (`*`) and a TypeScript
default import (`default`) do not give the local name, so this module reads the
import statement to find it:

- Python `import a.b` gives `a.b`, and `import a.b as x` gives `x`.
- Python `from a import b` gives `b`, and `from a.b import *` gives the public names of `a.b`.
- TypeScript `import * as x from "..."` and `import x from "..."` give `x`,
  when the last part of the import path is the file name of the target module.

The TypeScript rule compares file names only. It does not resolve the import path.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path, PurePosixPath
from typing import Any

from systemap import repo_files

WHOLE = "*"
DEFAULT = "default"
LINES_PER_FLOW = 30

_TS_NAMESPACE = re.compile(r"""import\s+(?:\w+\s*,\s*)?\*\s+as\s+(\w+)\s+from\s+["']([^"']+)["']""")
_TS_DEFAULT = re.compile(
    r"""import\s+(?:type\s+)?(\w+)\s*(?:,\s*[{*][^;]*?)?\s+from\s+["']([^"']+)["']"""
)


def _source(root: Path, facts: dict[str, Any], module: str) -> str | None:
    try:
        return repo_files.read_text(root, str(facts["components"][module]["file"]))
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


def _python_bindings(text: str, target: str, public: list[str]) -> set[str]:
    """Give the local names that Python import statements bind for the target module."""
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


def _imports_target(specifier: str, target_file: str) -> bool:
    """Compare the last part of a TypeScript import path with the target file name."""
    path = PurePosixPath(target_file)
    stem = path.parent.name if path.stem == "index" else path.stem
    last = PurePosixPath(specifier).name
    return last.split(".", 1)[0] == stem


def _typescript_bindings(text: str, target_file: str) -> set[str]:
    """Give the local names that TypeScript namespace and default imports bind."""
    out: set[str] = set()
    for pattern in (_TS_NAMESPACE, _TS_DEFAULT):
        out |= {m[1] for m in pattern.finditer(text) if _imports_target(m[2], target_file)}
    return out - {"type"}


def _bindings(text: str, facts: dict[str, Any], module: str, target: str) -> set[str]:
    record = facts["components"].get(target, {})
    if str(facts["components"][module].get("file", "")).endswith(".py"):
        public = [n["name"] for n in record.get("names", [])]
        return _python_bindings(text, target, public)
    return _typescript_bindings(text, str(record.get("file", "")))


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
            names |= _bindings(text, facts, module, target)
    return lines_using(text, module, names) if names else []


def code_between(
    root: Path, facts: dict[str, Any], mods: dict[str, list[str]], src: str, dst: str
) -> list[str]:
    """Get at most 30 lines using an import name from the other component."""
    lines: list[str] = []
    for a_card, b_card in ((src, dst), (dst, src)):
        for a in mods.get(a_card, []):
            lines += _uses_of(root, facts, a, mods.get(b_card, []))
    return lines[:LINES_PER_FLOW]
