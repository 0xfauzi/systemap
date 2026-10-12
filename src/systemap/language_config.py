"""The language configuration helpers validate settings shared by source adapters.

They also validate the writing profile for the map text that a person reads.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# The writing profiles of the language policy. The first profile is the default.
PROFILES = ("plain", "asd-ste100")


def package_roots(
    root: Path, language: str, value: Any, source: str
) -> tuple[tuple[str, str], ...]:
    """This function gets configured or discovered package roots for a source language."""
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
    """This function validates test directories with configuration-path error context."""
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(value)
    raise ValueError(f"{source}: tests_dir must be a directory or a list of directories.")


def writing_profile(value: Any, source: str) -> str:
    """This function validates the `[writing]` table and gives the writing profile.

    Without the table or its profile key, the profile is "plain"."""
    if value is None:
        return PROFILES[0]
    if not isinstance(value, dict):
        raise ValueError(f"{source}: writing must be a table")
    bad = sorted(set(value) - {"profile"})
    if bad:
        raise ValueError(f"{source}: writing has an unknown key: {', '.join(bad)}")
    profile = value.get("profile", PROFILES[0])
    if profile not in PROFILES:
        raise ValueError(f'{source}: writing.profile must be "plain" or "asd-ste100"')
    return str(profile)
