"""The page of each map that `render`, `refresh`, `check` and `live` make: the canvas page
(`canvas_page`) with a small page for each nested map, or with `[render] canvas = false`
one linked page for each map (`config_render`).

`change_of` gives the change data of the page of a map (`page_change`). Without it, the
pages have no change. With the canvas page, the canvas data holds the change data of
each map. `skip` gives the IDs of maps that get no linked page (`check` gives the maps
with model contradictions).

`notice` gives the notice line of `[render] canvas = false` for the commands that write
or serve the pages.
"""

from __future__ import annotations

from collections.abc import Callable, Collection
from typing import Any

from systemap import canvas_page, change, config_render, nest, page
from systemap.config import Config

ChangeOf = Callable[[nest.Map], dict[str, Any]]


def page_change(
    cfg: Config,
    facts: dict[str, Any],
    base: str,
    head: str,
    source: change.SourceChange | None,
    pr: dict[str, Any],
) -> ChangeOf:
    """Give the function for the change data of a map page, relative to the revision `base`."""

    def of(m: nest.Map) -> dict[str, Any]:
        ch = change.for_page(cfg, m, base, facts, head, source)
        ch["pr"] = pr
        return ch

    return of


def notice(cfg: Config) -> list[str]:
    """Give the notice line of the linked pages, or no line for the canvas page."""
    return config_render.notice(cfg.render_canvas)


def pages(
    cfg: Config,
    tree: nest.Tree,
    facts: dict[str, Any],
    change_of: ChangeOf | None = None,
    skip: Collection[str] = (),
) -> list[tuple[nest.Map, str]]:
    """Give each map of the tree with the text of its page, in tree order.

    A map in `skip` has no item."""

    def linked(m: nest.Map) -> str:
        return page.build(
            cfg,
            m.model,
            m.meaning,
            m.theme,
            facts,
            change_of(m) if change_of else {"has_change": False},
            nesting=page.nesting_of(cfg, tree, m, facts),
        )

    if not cfg.render_canvas:
        return [(m, linked(m)) for m in tree.maps if m.id not in skip]
    changes = {m.id: change_of(m) for m in tree.maps} if change_of else None
    return canvas_page.pages(cfg, tree, facts, changes)
