"""The `[tool.systemap]` table of a pyproject.toml file.

The `tool` value and the `tool.systemap` value must be tables. A different type is a
configuration error with the key. It is not an empty configuration: the defaults would
then replace the settings that the file gives incorrectly.
"""

from __future__ import annotations

from typing import Any


def section(data: dict[str, Any]) -> dict[str, Any] | None:
    """Give the `tool.systemap` table of the TOML data, or None if it has no such table.

    A `tool` value or a `tool.systemap` value that is not a table gives a ValueError."""
    tool = data.get("tool", {})
    if not isinstance(tool, dict):
        raise ValueError("tool must be a table.")
    found = tool.get("systemap")
    if found is not None and not isinstance(found, dict):
        raise ValueError("tool.systemap must be a table.")
    return found
