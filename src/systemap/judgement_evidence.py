"""The evidence digests bind exact judgement answers to source data."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def _source_hash(root: Path, record: dict[str, Any]) -> str:
    """This function hashes source bytes because saved facts can predate an uncommitted
    edit.
    """
    name = record.get("file")
    if not isinstance(name, str):
        return "unknown source"
    try:
        return hashlib.sha256((root / name).read_bytes()).hexdigest()
    except OSError:
        return "missing source"


def _answer_facts(record: dict[str, Any]) -> dict[str, Any]:
    """This function removes Python-version-specific AST fingerprints from the evidence
    state.
    """
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
    """This function includes source bytes hashes so implementation changes invalidate
    exact answers.
    """
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
