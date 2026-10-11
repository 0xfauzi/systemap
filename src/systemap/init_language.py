"""The init language selection finds the source language and package roots for a new map.

Python package directories and a TypeScript root configuration give the package roots.
A TypeScript workspace can have tsconfig.json files only in its package directories.
Then the language is TypeScript, and the maintainer sets the package roots.
"""

from __future__ import annotations

import os
from pathlib import Path

from systemap import config
from systemap.config import ConfigError
from systemap.typescript_config import discover_typescript_roots

TSCONFIG = "tsconfig.json"


def language_roots(root: Path) -> tuple[str, list[tuple[str, str]]]:
    """Give the source language and the discovered package roots for `init`."""
    python_roots = config.discover_roots(root)
    typescript_roots = discover_typescript_roots(root)
    if python_roots and typescript_roots:
        raise ConfigError(
            "The source contains Python and TypeScript. Set language in systemap.toml."
        )
    if typescript_roots or (not python_roots and has_tsconfig(root)):
        return "typescript", typescript_roots
    return "python", python_roots


def has_tsconfig(root: Path, depth: int = config.CANDIDATE_DEPTH) -> bool:
    """Find a tsconfig.json file within `depth` directory levels of the root.

    The search skips node_modules, the other directories in `config.SKIP_WALK`, and
    directories with a name that starts with a period."""
    for dirpath, dirnames, filenames in os.walk(root):
        level = len(Path(dirpath).relative_to(root).parts)
        dirnames[:] = [
            d for d in dirnames if level < depth and d not in config.SKIP_WALK and d[0] != "."
        ]
        if TSCONFIG in filenames:
            return True
    return False
