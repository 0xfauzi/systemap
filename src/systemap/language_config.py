"""Configuration values shared by the source-language adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def package_roots(
    root: Path, language: str, value: Any, source: str
) -> tuple[tuple[str, str], ...]:
    """Configured or discovered package roots for one source language."""
    if value is not None:
        if isinstance(value, dict) and all(
            isinstance(path, str) and isinstance(name, str) for path, name in value.items()
        ):
            return tuple(value.items())
        raise ValueError(f'{source}: package_roots must be a table of "path" = "module name"')
    if language == "typescript":
        from systemap.typescript_config import discover_typescript_roots

        return tuple(discover_typescript_roots(root))
    from systemap.config import discover_roots

    return tuple(discover_roots(root))


def tests_directories(value: Any, source: str) -> tuple[str, ...]:
    """The configured test directories, with the config file's error context."""
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(value)
    raise ValueError(f"{source}: tests_dir must be a directory or a list of directories")
