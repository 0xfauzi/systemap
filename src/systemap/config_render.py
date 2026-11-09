"""The `[render]` table of the configuration: the settings of the page output.

`render` and `refresh` write the canvas page (docs/design/nested-canvas.md) at the top
page, and a small page that goes to it at the page of each nested map. This is the
default, and `canvas = true` gives the same output.

`canvas = false` makes the commands write the linked pages, one page for each map, with
no change from the earlier releases. This setting is for one release only. The linked
pages get no new function. `render`, `refresh` and `live` then give the notice line
`NOTICE` (`render_pages.notice`), and the exit code does not change.

A ValueError gives the configuration error. The configuration reader changes it to a
ConfigError.
"""

from __future__ import annotations

from typing import Any

KEYS = frozenset({"canvas"})

NOTICE = (
    "notice: [render] canvas = false writes the linked pages. The next release removes "
    "the linked pages. Remove the setting to write the canvas page."
)


def canvas(raw: dict[str, Any], where: str) -> bool:
    """Read `[render] canvas`. Give true if the table or the key is not there."""
    table = raw.get("render", {})
    if not isinstance(table, dict):
        raise ValueError(f"{where}: render must be a table")
    bad = sorted(set(table) - KEYS)
    if bad:
        raise ValueError(f"{where}: render has an unknown key: {', '.join(bad)}")
    value = table.get("canvas", True)
    if not isinstance(value, bool):
        raise ValueError(f"{where}: render.canvas must be true or false")
    return value
