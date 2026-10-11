"""The package root check finds configured package roots that the extractor cannot use.

An earlier `systemap init` wrote the model and out_dir keys after the [package_roots] line.
TOML reads these keys as package roots. If such an entry has the default value of its key,
the entry has no effect, and the check removes it. Each other entry must be a directory.
A Python import name cannot be a path.
"""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path
from typing import Any

# The keys that an earlier init wrote after the [package_roots] line, with defaults.
SETTINGS_IN_ROOTS = {"model": "map/model.py", "out_dir": "docs/map"}

Roots = tuple[tuple[str, str], ...]


def checked_roots(
    root: Path,
    language: str,
    raw: dict[str, Any],
    roots: Roots,
    settings: Collection[str],
    where: str,
) -> Roots:
    """Give the package roots without an entry that repeats the default value of its key.

    A configured root that the extractor cannot use gives ValueError. The message names a
    key from `settings` that is in the table."""
    if raw.get("package_roots") is None:
        return roots
    kept = tuple((rel, name) for rel, name in roots if not _repeats_setting(raw, rel, name))
    for rel, name in kept:
        path_name = language == "python" and "/" in name
        if path_name or not (root / rel).is_dir():
            raise ValueError(f"{where}: {_problem(rel, name, path_name, settings)}")
    return kept


def _repeats_setting(raw: dict[str, Any], rel: str, name: str) -> bool:
    default = SETTINGS_IN_ROOTS.get(rel)
    return default is not None and raw.get(rel, default) == name


def _problem(rel: str, name: str, path_name: bool, settings: Collection[str]) -> str:
    if rel in settings:
        return (
            f"[package_roots] contains the key {rel}. Move the {rel} line above the "
            f"[package_roots] line."
        )
    if path_name:
        return (
            f"The package root {rel} has the import name {name}. A Python import name cannot "
            f"contain a slash."
        )
    return f"The package root {rel} is not a directory. Correct the path in [package_roots]."
