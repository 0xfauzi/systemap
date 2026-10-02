"""Stable source evidence for exact judgement answers."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def _source_hash(root: Path, record: dict[str, Any]) -> str:
    """Read current source because saved facts may predate an uncommitted edit."""
    name = record.get("file")
    if not isinstance(name, str):
        return "unknown source"
    try:
        return hashlib.sha256((root / name).read_bytes()).hexdigest()
    except OSError:
        return "missing source"


def _answer_facts(record: dict[str, Any]) -> dict[str, Any]:
    """Keep evidence independent of AST dump spelling across Python minors."""
    stable = {key: value for key, value in record.items() if key not in {"syntax_sha", "api"}}
    stable["api"] = [
        {key: value for key, value in item.items() if key != "fingerprint"}
        for item in record.get("api", [])
    ]
    return stable


def answer_state(
    components: dict[str, Any],
    root: Path,
    model_hash: str,
    imports: list[tuple[str, str]] | None,
) -> Any:
    """Raw source still invalidates answers when implementation text changes."""
    if imports is None:
        return {
            "model": model_hash,
            "facts": [
                (name, _answer_facts(record), _source_hash(root, record))
                for name, record in sorted(components.items())
            ],
        }
    return [
        (
            source,
            target,
            components[source].get("uses", {}).get(target, []),
            _source_hash(root, components[source]),
            _source_hash(root, components[target]),
        )
        for source, target in imports
    ]
