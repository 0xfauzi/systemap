"""The `[render]` table of the configuration: the settings of the page output.

`canvas = true` makes `render` and `refresh` write the canvas page
(docs/design/nested-canvas.md) in place of the linked pages. The default is false.
Then the commands write the linked pages with no change. A ValueError gives the
configuration error. The configuration reader changes it to a ConfigError.
"""

from __future__ import annotations

from typing import Any

KEYS = frozenset({"canvas"})


def canvas(raw: dict[str, Any], where: str) -> bool:
    """Read `[render] canvas`. Give false if the table or the key is not there."""
    table = raw.get("render", {})
    if not isinstance(table, dict):
        raise ValueError(f"{where}: render must be a table")
    bad = sorted(set(table) - KEYS)
    if bad:
        raise ValueError(f"{where}: render has an unknown key: {', '.join(bad)}")
    value = table.get("canvas", False)
    if not isinstance(value, bool):
        raise ValueError(f"{where}: render.canvas must be true or false")
    return value
