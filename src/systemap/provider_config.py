"""Read the `[decision]` and `[openai]` tables of the configuration.

`[decision] provider` selects the decision provider of the commands that ask
questions: "jev" (the default) or "openai". A key in the environment does not select a
provider. `[openai] model` and `[openai] cache` set the OpenAI model and its cache file.
An incorrect value raises ValueError. `systemap.config` changes it into ConfigError.
"""

from __future__ import annotations

from typing import Any

PROVIDERS = ("jev", "openai")
DECISION_KEYS = {"provider"}
OPENAI_KEYS = {"model", "cache"}
OPENAI_MODEL = "gpt-6-luna"
OPENAI_CACHE = ".systemap/openai-cache.json"


def _table(raw: dict[str, Any], name: str, keys: set[str], where: str) -> dict[str, Any]:
    table = raw.get(name, {})
    if not isinstance(table, dict):
        raise ValueError(f"{where}: {name} must be a table")
    bad = sorted(set(table) - keys)
    if bad:
        raise ValueError(f"{where}: {name} has an unknown key: {', '.join(bad)}")
    return table


def _text(table: dict[str, Any], key: str, default: str, where: str) -> str:
    value = table.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where}: {key} must be a string that is not empty")
    return value.strip()


def settings(raw: dict[str, Any], where: str) -> dict[str, Any]:
    """Give the provider, the OpenAI model, and the OpenAI cache path."""
    decision = _table(raw, "decision", DECISION_KEYS, where)
    openai = _table(raw, "openai", OPENAI_KEYS, where)
    provider = _text(decision, "provider", "jev", f"{where}: decision")
    if provider not in PROVIDERS:
        names = " or ".join(f'"{p}"' for p in PROVIDERS)
        raise ValueError(f"{where}: decision.provider must be {names}")
    return {
        "decision_provider": provider,
        "openai_model": _text(openai, "model", OPENAI_MODEL, f"{where}: openai"),
        "openai_cache": _text(openai, "cache", OPENAI_CACHE, f"{where}: openai"),
    }
