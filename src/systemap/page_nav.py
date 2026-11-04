"""The navigation between the pages of a map tree: the map path, the title, and the keys.

Each map of a tree has its own page. A link opens the page of a nested map, and the
Back control of the browser goes back to the parent page. Thus each page has its own
URL, and a reader can keep or send the link of a nested map. The pages do not show a
map in a frame.

The header gives the map path: one link for each ancestor map and the name of the
current map. The data comes from the map ID alone. The page title gives the map ID and
the level of the map. In the Changes view, a link to a nested map adds `#changes`, so
the nested page also opens the Changes view.

The U key goes to the parent page and selects the card that opens the current map. The
T key opens the list of child maps. The key handler of the page script (`letter` in
page_script.py) calls `P.nav`, so these keys have the same conditions as the other letter
keys: they do not operate in a text field, with a modifier key, or while a dialog is open.
"""

from __future__ import annotations

from urllib.parse import quote

from systemap.schematic_cards import esc

# The keys of this module, for the keyboard sheet. The page script uses the same keys.
UP_KEY = ("U", "Go to the parent map")
TREE_KEY = ("T", "Open the list of child maps")


def segments(map_id: str) -> list[str]:
    """Give the card IDs of a map ID, from the top. The top map has no segments.

    A card ID is one path segment (nest._one_segment), so a slash in a map ID always
    separates two card IDs."""
    return map_id.split("/") if map_id else []


def title(name: str, map_id: str) -> str:
    """Give the page title: the system name, and the map ID and the level of a nested map."""
    parts = segments(map_id)
    if not parts:
        return f"{name} system map"
    return f"{name} system map: {map_id} (level {len(parts)})"


def heading(name: str, map_id: str) -> str:
    """Give the text of the page heading: the last segment of the map ID, or the name."""
    parts = segments(map_id)
    return parts[-1] if parts else name


def up_href(map_id: str) -> str:
    """Give the parent page with the fragment of the card that opens the map.

    The parent page selects that card from the fragment. The top map has no parent."""
    parts = segments(map_id)
    return f"../index.html#{quote(parts[-1], safe='')}" if parts else ""


def path(name: str, map_id: str) -> str:
    """Give the map path for the header of a nested page, or nothing for the top page.

    The path is an ordered list. Each ancestor map has a link, which goes up one folder
    for each level. The current map is the last item, with `aria-current="page"`. The
    page heading shows the name of the current map, so this item is only for screen
    readers. On a phone, the path shows only the parent link, with the mark "<"."""
    parts = segments(map_id)
    if not parts:
        return ""
    depth = len(parts)
    labels = [name, *parts[:-1]]
    items = "".join(
        f'<li class="crumbs__up"><a class="crumb" href="{"../" * (depth - k)}index.html">'
        f'<span class="crumb__back" aria-hidden="true">&lt; </span>{esc(label)}</a>'
        '<span class="crumb__sep" aria-hidden="true">/</span></li>'
        for k, label in enumerate(labels)
    )
    return (
        f'<nav class="crumbs" id="mappath" aria-label="Map path" '
        f'data-up="{esc(up_href(map_id))}"><ol>{items}'
        f'<li class="sr-only"><span aria-current="page">{esc(parts[-1])}</span></li>'
        "</ol></nav>"
    )


def keys(map_id: str, opens: bool) -> tuple[tuple[str, str], ...]:
    """Give the rows of the keyboard sheet for the keys that operate on this page.

    U operates on a nested page, and T operates on a page with child maps."""
    return ((UP_KEY,) if map_id else ()) + ((TREE_KEY,) if opens else ())


def hint(map_id: str, opens: bool) -> str:
    """Give the screen reader hint about the keys and the links between the maps."""
    sentences = []
    if opens:
        sentences.append(
            "Double-click a card that opens a map to go to the page of that map. "
            "Enter on a selected card does the same."
        )
    if map_id:
        sentences.append("Press U to go to the parent map.")
    if not sentences:
        return ""
    return f'<p class="hint sr-only">{" ".join(sentences)}</p>'


def child_list(opens: dict[str, dict[str, object]]) -> str:
    """Give the list of the child maps, with one link for each child map.

    The T key opens this list. In the Changes view, the page script adds `#changes` to
    each link."""
    if not opens:
        return ""
    links = ", ".join(
        f'<a href="{esc(child["href"])}" data-child-map="{esc(child["href"])}">'
        f"{esc(child['name'])}</a>"
        for child in opens.values()
    )
    return f'<details class="map-links" id="maptree"><summary>Child maps</summary>{links}</details>'


CSS = r"""
.crumbs{min-width:0}
.crumbs ol{display:flex;align-items:baseline;gap:18px;margin:0;padding:0;list-style:none}
.crumbs__up{display:flex;align-items:baseline;gap:18px;white-space:nowrap}
.crumbs .crumb{display:inline-block;max-width:16em;overflow:hidden;text-overflow:ellipsis;
  vertical-align:bottom}
.crumb__back{display:none}
@media (max-width:640px){
.crumbs{flex:none}
.crumbs__up{display:none}
.crumbs__up:nth-last-child(2){display:flex}
.crumbs .crumb{display:inline-flex;align-items:center;min-height:44px;max-width:40vw;
  overflow:hidden;text-overflow:ellipsis}
.crumb__back{display:inline;white-space:pre}
.crumbs .crumb__sep{display:none}
}
"""

SCRIPT = r"""
(function(){
  var svg = document.getElementById('schematic');
  var P = svg && svg.page;
  if(!P){ return; }
  var path = document.getElementById('mappath');
  function all(sel){ return Array.prototype.slice.call(document.querySelectorAll(sel)); }
  // In the Changes view, a link to a nested map opens the Changes view of that map.
  function target(href){ return href + (P.mode() === 'change' ? '#changes' : ''); }
  function retarget(){
    all('a[data-child-map]').forEach(function(a){
      a.setAttribute('href', target(a.getAttribute('data-child-map')));
    });
  }
  // A double-click or a second Enter on a card that opens a map goes to its page.
  document.addEventListener('systemap:open', function(e){
    var d = e.detail || {};
    if(d.href){ location.href = target(d.href); }
  });
  ['systemap:mode', 'systemap:select'].forEach(function(n){
    svg.addEventListener(n, retarget); });
  function tree(){
    var list = document.getElementById('maptree');
    if(!list){ return false; }
    list.setAttribute('open', '');
    var s = list.querySelector('summary');
    if(s){ s.focus(); }
    return true;
  }
  function up(){
    var href = path && path.getAttribute('data-up');
    if(!href){ return false; }
    location.href = href;
    return true;
  }
  // The key handler of the page script calls these for U and T.
  P.nav = {up:up, tree:tree};
  retarget();
})();
"""
