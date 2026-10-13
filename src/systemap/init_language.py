"""The init language selection finds the source language and package roots for a new map.

A `language` key in an existing configuration selects the language. Without the key, the
language adapters examine the repository. A TypeScript workspace can have tsconfig.json
files only in its package directories. Then the language is TypeScript, and the
maintainer sets the package roots.
"""

from __future__ import annotations

from pathlib import Path

from systemap import config
from systemap import language as languages
from systemap.config import ConfigError


def language_roots(root: Path) -> tuple[str, list[tuple[str, str]]]:
    """Give the source language and the discovered package roots for `init`.

    If the language is not known, the function stops and tells the maintainer to set
    the language key."""
    raw, _source = config.read_raw(root)
    configured = raw.get("language")
    try:
        name = configured if isinstance(configured, str) else languages.detect(root)
        return name, languages.repository(name).discover_roots(root)
    except languages.LanguageError as exc:
        raise ConfigError(str(exc)) from exc
