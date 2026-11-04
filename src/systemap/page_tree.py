"""The map tree of a page: the Map tree panel and the search across maps.

Each page of a tree with nested maps has a Map tree panel. The panel is a nested list of
links, one item for each map of the tree. It is not an ARIA tree, so the usual link keys
operate. Each item gives the card ID of the map (the system name for the top map), the
number of internal components, the text "changed" when the map or a map below it
changed, and the number of open findings of the map.

The open findings are the open judgement lines of the render (`page_context.open_boundary`,
the rules of `systemap judgement`). A line belongs to the map of its map prefix. A render
of `render`, `refresh`, `check`, or `live` runs the judgement, so its items give a count.
If a render has no judgement result, the item shows "not examined", not zero. Unknown is
never zero. If the base tree of a comparison does not load, the change flag of a map is
not known, and the item does not show "changed".

Each page also has one compact list of the maps and a search index of the components of
the other maps: the map, the component ID, the kind, and the card text, cut to
`PLAIN_CHARACTERS` characters. The Find dialog shows these results in the group "Other
maps", after the results of the current map, with the hint "in <map ID>". The key of a
result is the map ID and the component ID, because a component ID is unique only in one
model. In each map, the internal components come before the actors. Each page has its own
copy of the index, because a static page opens from the file system and sends no request.

A tree with one map has no panel and no index.
"""

from __future__ import annotations

import html
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from systemap import judgement, nest, page_rollup
from systemap.boundary_changes import plural
from systemap.config import Config
from systemap.page_rollup import Changes, href

# The card text of a search row is cut to this number of characters.
PLAIN_CHARACTERS = 60
NOT_EXAMINED = "not examined"


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


@dataclass(frozen=True)
class Overview:
    """The data of the map tree for all pages of one render.

    `findings` gives the number of open lines of each map, or is None if the render has no
    judgement result. `changes` is the roll-up of the changes, or None without a comparison."""

    name: str
    maps: tuple[nest.Map, ...] = ()
    findings: dict[str, int] | None = None
    changes: Changes | None = None
    kinds: tuple[str, ...] = ()
    index: tuple[tuple[int, str, int, str], ...] = field(default=())


def line_map(line: str) -> str:
    """Give the ID of the map of a judgement line: its map prefix, or "" for the top map."""
    bare = judgement.unprefixed(line)
    return line[: len(line) - len(bare) - 2] if bare != line else ""


def finding_counts(tree: nest.Tree, still: Iterable[str] | None) -> dict[str, int] | None:
    """Give the number of open lines of each map, or None without a judgement result."""
    if still is None:
        return None
    out = dict.fromkeys(tree.ids, 0)
    for line in still:
        found = line_map(line)
        if found in out:
            out[found] += 1
    return out


def _index(
    maps: tuple[nest.Map, ...],
) -> tuple[tuple[str, ...], tuple[tuple[int, str, int, str], ...]]:
    """Give the kinds and the search rows of all maps. The actors come last in each map."""
    kinds: list[str] = []
    rows = []
    for k, m in enumerate(maps):
        ordered = sorted(m.model.components, key=lambda c: c.kind == "actor")
        for c in ordered:
            if c.kind not in kinds:
                kinds.append(c.kind)
            text = m.meaning.plain.get(c.id, "") or c.does
            rows.append((k, c.id, kinds.index(c.kind), text[:PLAIN_CHARACTERS]))
    return tuple(kinds), tuple(rows)


def overview(
    name: str,
    tree: nest.Tree,
    still: Iterable[str] | None,
    changes: Changes | None = None,
) -> Overview:
    """Give the map tree data of a render. A tree with one map gives an empty overview."""
    if not tree.nested:
        return Overview(name)
    kinds, rows = _index(tree.maps)
    return Overview(name, tree.maps, finding_counts(tree, still), changes, kinds, rows)


def for_render(
    cfg: Config,
    tree: nest.Tree,
    still: Iterable[str] | None,
    pages: Mapping[str, Mapping[str, Any]],
    base: str,
) -> Overview:
    """Give the map tree of a render, with the roll-up of the changes for a base.

    `pages` gives the change data of the page of each map."""
    changes = page_rollup.collect(cfg, tree, pages) if base and tree.nested else None
    return overview(cfg.name, tree, still, changes)


def _changed(ov: Overview, map_id: str) -> bool | None:
    """Tell if the map or a map below it changed, or give None if it is not known."""
    if ov.changes is None or not ov.changes.known:
        return None
    return ov.changes.rollups[map_id].changed


def mark_changed(ov: Overview, tree: nest.Tree, m: nest.Map, opens: dict[str, Any]) -> None:
    """Add the change flag of each child map to the child map records of the map `m`."""
    for child in tree.children(m):
        if _changed(ov, child.id):
            opens[child.card]["changed"] = True


def _found(ov: Overview, map_id: str) -> str:
    if ov.findings is None:
        return NOT_EXAMINED
    return plural(ov.findings.get(map_id, 0), "finding")


def item_text(ov: Overview, m: nest.Map) -> str:
    """Give the text after the name of one item: the counts, and "changed"."""
    parts = [plural(m.inside, "component")]
    if _changed(ov, m.id):
        parts.append("changed")
    parts.append(_found(ov, m.id))
    return ", ".join(parts)


def _item(ov: Overview, m: nest.Map, at: str, below: Mapping[str, list[nest.Map]]) -> str:
    label = esc(m.card or ov.name)
    if m.id == at:
        name = f'<span class="tree__at" aria-current="page">{label}</span>'
    else:
        link = esc(href(at, m.id))
        name = f'<a href="{link}" data-child-map="{link}">{label}</a>'
    children = below.get(m.id, [])
    inner = (
        "<ul>" + "".join(_item(ov, child, at, below) for child in children) + "</ul>"
        if children
        else ""
    )
    return f'<li>{name} <span class="tree__n">{esc(item_text(ov, m))}</span>{inner}</li>'


def panel(ov: Overview, at: str) -> str:
    """Give the Map tree panel of the page of the map `at`, or nothing for one map.

    The T key opens the panel. In the Changes view, the page script adds `#changes` to
    each link (`page_nav`)."""
    if not ov.maps:
        return ""
    below: dict[str, list[nest.Map]] = {}
    for m in ov.maps[1:]:
        below.setdefault(m.parent or "", []).append(m)
    return (
        '<details class="map-links map-tree" id="maptree"><summary>Map tree</summary>'
        f"<ul>{_item(ov, ov.maps[0], at, below)}</ul></details>"
    )


def data(ov: Overview, at: str) -> dict[str, Any] | None:
    """Give the compact list of the maps and the search index of the other maps, for the
    page of the map `at`. A map row has the map ID, the parent ID, the number of internal
    components, the change flag (None without a comparison), and the number of open
    findings (None if not examined)."""
    if not ov.maps:
        return None
    ids = [m.id for m in ov.maps]
    maps = [
        [
            m.id,
            m.parent or "",
            m.inside,
            _changed(ov, m.id),
            None if ov.findings is None else ov.findings.get(m.id, 0),
        ]
        for m in ov.maps
    ]
    here = ids.index(at)
    return {
        "at": here,
        "up": page_rollup.up(at),
        "top": ov.name,
        "maps": maps,
        "kinds": list(ov.kinds),
        "index": [list(row) for row in ov.index if row[0] != here],
    }


CSS = (
    r"""
.map-tree ul{margin:4px 0;padding-left:18px;list-style:none}
.map-tree>ul{padding-left:0}
.map-tree li{margin:2px 0}
.map-tree a,.map-tree .tree__at{display:inline-block;min-height:24px;font-weight:600}
.tree__at{color:var(--ink)}
.tree__n{color:var(--ink-2)}
"""
    + page_rollup.CSS
)

# The Find dialog calls `P.findMore` with its function `add`. Each row of the other maps
# is a quiet result: it shows only for a search text.
SCRIPT = r"""
(function(){
  var svg = document.getElementById('schematic');
  var P = svg && svg.page, T = (window.systemapWorkspace || {}).tree;
  if(!P || !T){ return; }
  function href(id, cid){
    var down = id ? id.split('/').map(encodeURIComponent).join('/') + '/' : '';
    return T.up + down + 'index.html#' + encodeURIComponent(cid);
  }
  P.findMore = function(add){
    T.index.forEach(function(r){
      var id = T.maps[r[0]][0], kind = T.kinds[r[2]], actor = kind === 'actor';
      add('Other maps', r[1], r[3], function(){ location.href = href(id, r[1]); },
        {quiet:true, late:actor, hint:'in ' + (id || T.top), words:kind + ' ' + id,
          glyph:'<i class="pal__card' + (actor ? ' actor' : '') + '"></i>'});
    });
  };
})();
"""
