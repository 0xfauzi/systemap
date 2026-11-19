"""The page of each map that `render`, `refresh`, `check` and `live` make: the canvas page
(`canvas_page`) with a small page for each nested map, or with `[render] canvas = false`
one linked page for each map (`config_render`). With `[render] page = "atlas"`, the atlas
page (`atlas_page`) replaces the canvas page, with the same small pages.

`change_of` gives the change data of the page of a map (`page_change`). Without it, the
pages have no change. With the canvas page, the canvas data holds the change data of
each map. `skip` gives the IDs of maps that get no linked page (`check` gives the maps
with model contradictions).

`notice` gives the notice line of `[render] canvas = false` for the commands that write
or serve the pages.

`history` gives the history data of the atlas page (`history_data`) and its notice lines.
`render`, `refresh` and `live` read it from Git. The output check (`check` and
`render --check`) uses the history of the page file (`stored`), and does not read Git.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from typing import Any

from systemap import atlas_page, canvas_page, change, config_render, history_data, nest, page
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
    return [] if cfg.render_canvas else [config_render.NOTICE]


def history(
    cfg: Config, tree: nest.Tree, facts: dict[str, Any], stored: bool = False
) -> tuple[dict[str, Any] | None, list[str]]:
    """Give the history data of the atlas page and the notice lines. With `stored`, the
    data comes from the page file, not from Git."""
    if stored:
        return history_data.stored(cfg, tree), []
    return history_data.of_tree(cfg, tree, facts)


def pages(
    cfg: Config,
    tree: nest.Tree,
    facts: dict[str, Any],
    change_of: ChangeOf | None = None,
    skip: Collection[str] = (),
    history: Mapping[str, Any] | None = None,
) -> list[tuple[nest.Map, str]]:
    """Give each map of the tree with the text of its page, in tree order.

    A map in `skip` has no item. `history` is the history data of the atlas page."""

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
    return _ONE_PAGE[cfg.render_page](cfg, tree, facts, changes, history)


def _canvas(
    cfg: Config,
    tree: nest.Tree,
    facts: dict[str, Any],
    changes: Mapping[str, Mapping[str, Any]] | None,
    _history: Mapping[str, Any] | None,
) -> list[tuple[nest.Map, str]]:
    """The canvas page, which has no History view."""
    return canvas_page.pages(cfg, tree, facts, changes)


# The page of all maps of the tree for each value of `[render] page` that is not "linked".
_ONE_PAGE: dict[str, Callable[..., list[tuple[nest.Map, str]]]] = {
    "atlas": atlas_page.pages,
    "canvas": _canvas,
}
