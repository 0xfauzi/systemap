"""The access part of the canvas renderer: the list of the tree and the canvas label.

The canvas page (`canvas_page`) has an empty `nav` element after the canvas. After the
first frame is on the screen, this part writes the list of the tree into it from the
canvas data, in one step (`buildTree`). Thus the page bytes do not grow with the list, and
the list does not make the time to the first frame longer. The list gives each map, its
cards and its flows. Each card has its name, its card text, its `does` text and its facts: the
modules, the count of flows in and out, the assurance level and the freshness. The cards
of a map are in the reading order of Tab (`page_canvas_keys`): the rows from the top to the
bottom, and in each row the cards from the left to the right.
A card that opens a map holds the list of that map.

Each item is a link. Its `href` is the URL hash of its card, or of its map for a flow, for
example `#Gateway/Routes`. A click, or Enter on the link, moves the camera to the item. The list
is visually hidden, but a screen reader reads it. The Tab key also goes to each link. A
link with the focus is visible at the top left of the screen, as a skip link is.

The label of the canvas gives the current path. The script writes it when the camera
stops (`settled`), and only when it changes. Thus no frame writes to the page. When the
open map changes, a live region tells the path and the count of cards of the new map. When
the canvas has the keyboard focus on a card, the same text then also gives that card, and
the selected card (`heldWords`). Thus the text of the map does not remove the name of the
focused card before a screen reader reads it.

The script writes the list again after a change of the view (`buildTree`). When a link of
the list has the keyboard focus, the same link of the new list gets it. Thus the focus does
not go to the body of the page.

The URL hash `#changes`, the link of a pull request comment (`delta_link.CHANGES`), opens
the Changes view at the top map. `#Gateway/changes` opens it at the map Gateway. The small
page of a nested map gives such a hash for `Gateway/index.html#changes`
(`canvas_redirect`). A map or a card with the ID `changes` keeps its link: then the hash
moves the camera to that map or card, as each other hash does, and the view does not
change. When the camera stops in the Changes view at the map of the hash, the hash stays.
Thus a load of the page again opens the same view.

A view part can add words (`viewFacts` and `viewSay` in `page_canvas_view`): the words of
the current view for each card in the list, and for each map in the live region and in the
top line of the list. For example, the Changes view gives the change of each card.
"""

from __future__ import annotations

CSS = """
.tree{position:absolute;left:0;top:0;width:1px;height:1px;margin:-1px;overflow:hidden;
white-space:nowrap}
.tree a:focus{position:fixed;left:12px;top:56px;z-index:3;box-sizing:border-box;
min-height:44px;max-width:calc(100% - 24px);padding:12px 16px;overflow:hidden;
text-overflow:ellipsis;white-space:nowrap;font:600 14px/20px var(--fs);color:var(--ink);
background:var(--raised);border:1px solid var(--line-2);border-radius:8px;
outline:2px solid var(--accent);outline-offset:2px;text-decoration:none}
"""

HTML = (
    '<nav id="canvas-tree" class="tree" aria-label="Map tree"></nav>'
    '<p id="canvas-said" class="sr-only" aria-live="polite"></p>'
)

# The list text has "<\\/" in place of "</": the page embeds the script in a script element.
TREE = r"""
// ---- the list of the tree and the canvas label -------------------------------------
var TREE_EL = document.getElementById('canvas-tree'), LABEL = '', SAID_MAP = null, TREE_MS = null;
function esc(s) {
  return String(s).replace(/[&<>"]/g, function (ch) { return ch === '&' ? '&amp;' : ch === '<' ? '&lt;' : ch === '>' ? '&gt;' : '&quot;'; });
}
function counted(n, one) { return n + ' ' + one + (n === 1 ? '' : 's'); }
// The ID that the URL hash gives to a card: the ID of its map, a slash and the card ID.
// For a card that opens a map, this is the ID of that map.
function cardId(c) { return c.map.id ? c.map.id + '/' + c.id : c.id; }
function mapName(m) {
  var names = [];
  for (var x = m; x.owner; x = x.owner.map) names.unshift(x.owner.id);
  return [DATA.name || 'map'].concat(names).join(' / ');
}
function sizeText(m) { return counted(m.cards.length, 'card') + ' and ' + counted(m.flows.length, 'flow'); }
function factsText(c) {
  var n = (c.m || []).length, out = [];
  if (c.p) out.push(c.p + '.');
  if (c.d) out.push(c.d);
  if (c.k === 'actor') out.push('Actor.');
  else out.push(n ? (n === 1 ? 'Module: ' : 'Modules: ') + c.m.join(', ') + '.' : 'No module.');
  out.push('Flows in: ' + c.ins.length + '. Flows out: ' + c.outs.length + '.');
  if (c.as) out.push('Assurance level: ' + c.as[0] + '. Freshness: ' + c.as[1] + '.');
  if (c.child) out.push('Opens a map of ' + sizeText(c.child) + '.');
  var more = viewFacts(c);
  if (more) out.push(more);
  return out.join(' ');
}
function link(hash, data, text) { return '<a href="' + esc(hash || '#') + '" ' + data + '>' + esc(text) + '<\/a>'; }
// The lists of the cards and of the flows of a map. The cards are in the reading order of
// Tab (`readingOrder` in `page_canvas_keys`). The item of a card that opens a map holds the
// lists of that map.
function mapLists(m) {
  var name = esc(mapName(m)), at = 'data-m="' + m.oi + '" ', out = ['<ul aria-label="Cards of ' + name + '">'];
  readingOrder(m).forEach(function (c) {
    out.push('<li>', link(hashOf(cardId(c)), at + 'data-c="' + c.i + '"', c.id), ' ', esc(factsText(c)));
    if (c.child) out.push(mapLists(c.child));
    out.push('<\/li>');
  });
  out.push('<\/ul>');
  if (m.flows.length) {
    out.push('<ul aria-label="Flows of ' + name + '">');
    m.flows.forEach(function (f) {
      out.push('<li>', link(hashOf(m.id), at + 'data-f="' + f.i + '"', 'Flow from ' + f.s + ' to ' + f.t + ': ' + f.a), '<\/li>');
    });
    out.push('<\/ul>');
  }
  return out.join('');
}
// A new list replaces the links. When a link of the list has the keyboard focus, the same
// link of the new list gets it (`data-m` and `data-c` or `data-f`).
function buildTree() {
  if (!TREE_EL) return;
  var t0 = performance.now(), a = document.activeElement, keep = null;
  if (a && a.tagName === 'A' && TREE_EL.contains(a)) {
    keep = ['data-m', 'data-c', 'data-f'].map(function (n) { return a.hasAttribute(n) ? '[' + n + '="' + a.getAttribute(n) + '"]' : ''; }).join('');
  }
  TREE_EL.innerHTML = '<ul><li>' + link('', 'data-m="0"', 'Map: ' + mapName(TOP)) + ' ' + esc(sizeText(TOP) + '.' + viewSay(TOP)) + mapLists(TOP) + '<\/li><\/ul>';
  var back = keep && TREE_EL.querySelector('a' + keep);
  if (back) back.focus({preventScroll: true});
  TREE_MS = performance.now() - t0;
}
function union(a, b) {
  var x = Math.min(a[0], b[0]), y = Math.min(a[1], b[1]);
  return [x, y, Math.max(a[0] + a[2], b[0] + b[2]) - x, Math.max(a[1] + a[3], b[1] + b[3]) - y];
}
// The camera goal of a map, a card or a flow: a world box and the margin of its fit. A
// card that opens a map has the goal of that map.
function goalOf(m, c, f) {
  if (f) {
    var s = m.byId[f.s], t = m.byId[f.t];
    return s && t ? {box: union(worldBox(s), worldBox(t)), pad: 0.2} : {box: frameOf(m), pad: FIT};
  }
  if (c && !c.child) return {box: worldBox(c), pad: 0.2};
  return {box: frameOf(c ? c.child : m), pad: FIT};
}
function flyGoal(g) { flyTo(g.box, g.pad); }
// The ID that the URL hash gives, or '' when the hash is not a correct URI part.
function hashId() { try { return decodeURIComponent(location.hash.slice(1)); } catch (e) { return ''; } }
// Write the hash `h` with no new history entry. An empty `h` removes the hash.
function setHash(h) {
  try { history.replaceState(null, '', h || location.pathname + location.search); } catch (e) { /* a file page can refuse it */ }
}
// The goal that the URL hash gives: a map, or a card of a map. The view link `#changes`
// (`delta_link.CHANGES`) or `#<map>/changes` also sets the Changes view (`linkedMap`). When
// the hash names no map and no card, it is the top map.
function hashGoal() {
  var id = hashId(), c = hashCard(id), v;
  if (id && MAPS[id] && MAPS[id].T) return goalOf(MAPS[id], null, null);
  if (c) return goalOf(c.map, c, null);
  if ((v = linkedMap(id))) { setView('changes'); return goalOf(v, null, null); }
  return goalOf(TOP, null, null);
}
// The map of the view link of the ID `id` of a URL hash: the top map for `changes`, and the
// map M for `M/changes`, or null. A map or a card with the ID keeps its link, because
// `hashGoal` looks for them first.
function linkedMap(id) {
  if (!VIEWS.changes) return null;
  if (id === 'changes') return TOP;
  var cut = id.lastIndexOf('/'), m = cut > 0 && id.slice(cut + 1) === 'changes' ? MAPS[id.slice(0, cut)] : null;
  return m && m.T ? m : null;
}
// The card that the ID `id` of a URL hash names, when it is a card that opens no map. An
// empty ID names no card.
function hashCard(id) {
  if (!id) return null;
  var cut = id.lastIndexOf('/'), m = MAPS[cut < 0 ? '' : id.slice(0, cut)];
  var c = m && m.T ? m.byId[id.slice(cut + 1)] : null;
  return c && !c.child ? c : null;
}
if (TREE_EL) {
  TREE_EL.addEventListener('click', function (e) {
    var a = e.target.closest ? e.target.closest('a[data-m]') : null;
    if (!a) return;
    var m = ORDER[+a.getAttribute('data-m')], c = a.hasAttribute('data-c') ? m.cards[+a.getAttribute('data-c')] : null;
    var f = a.hasAttribute('data-f') ? m.flows[+a.getAttribute('data-f')] : null, href = a.getAttribute('href');
    e.preventDefault();
    setHash(href === '#' ? '' : href);
    flyGoal(goalOf(m, c, f));
  });
}
// The words for the focused card and the selected card, after the words of a new map.
function heldWords() {
  var f = FOCUS && document.activeElement === cv && focusHeld(FOCUS) ? FOCUS : null, out = f ? ' ' + cardWords(f) : '';
  if (SEL_C) out += SEL_C === f ? ' Selected.' : ' Selected: card ' + SEL_C.id + '.';
  return out;
}
// When the camera stops: the label of the canvas gives the current path. When the open map
// changes, the live region tells the new map. Each element changes only when its text changes.
function tell(m) {
  relabel(m);
  if (SAID_MAP && m !== SAID_MAP) say(openWords(m) + heldWords());
  SAID_MAP = m;
}
// The words of an open map: its path, its count of cards, and the words of the view.
function openWords(m) { return 'Open map: ' + mapName(m) + '. ' + counted(m.cards.length, 'card') + '.' + viewSay(m); }
// The label of the canvas: the path, the level, and the view when it is not the Map view
// with All (`viewLabel` in `page_canvas_view`).
function relabel(m) {
  var label = 'System map: ' + mapName(m) + '. Level ' + CHAIN.length + '.' + viewLabel();
  if (label !== LABEL) { LABEL = label; cv.setAttribute('aria-label', label); }
  viewHere(m);
}
"""
