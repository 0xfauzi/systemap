"""The open boundary lines of the canvas page: the marks of the open ports and their words.

`page_canvas` joins this part after the Changes view (`page_canvas_changes`) and before
the input part. Thus the marks are there in the first frame. The canvas data gives the
open `boundary flow` and `boundary import` lines of each port (`n`) when the page received
the open lines of the judgement (`judged`, `canvas_page.pages`). A port with no open line
shows no join state, because no check confirms the boundary. The page never says
"verified". These are the rules of the ports of step 7 of docs/design/nested-parts.md.

Each open line has a short text for its form (`WORDS`, and `w` of the port in `canvas_data`):

- "No flow inside": the parent flow has no nested flow to or from the actor.
- "Import with no flow": an internal component imports the component of an actor, and no
  flow connects them.
- "No flow in the parent map": a nested flow to or from an actor has no parent flow.

The mark. In the Map view, the actor card of an open port in its nested map has a dotted
ring in --ink-2 and a tag at its top right. The tag has the short text of the line, or the
count of the open lines when the card has more than one text. The part gives the mark
through the seam of the Map view (`VIEWS.map.card` in `page_canvas_view`). Thus the mark
fades as each mark of a view does: by 0.2 or less in one frame and by 1 in 160 ms or more,
and at one time with reduced motion. A quiet card of a layer keeps its mark with the alpha
of a quiet card. The other views do not show the mark. Each card holds its mark from the
start (`_pm`), thus a frame reads one property and makes no object. A card with no open
line keeps the plain value with no call in the Map view with all layers (`VIEW_IDLE`).

The words. In the Map view, the list of the tree gives the words of each marked card, and
the live region and the top line of the list give the open lines of a map (`facts` and
`say` of the seam). A line about a component that is not an actor of the map has no card.
Its words are only in the words of the map.
"""

from __future__ import annotations

import json

# The short text of each form of an open boundary line (`w` of a port in `canvas_data`).
WORDS = {
    "n": "No flow inside",
    "i": "Import with no flow",
    "p": "No flow in the parent map",
}


_SCRIPT = r"""
// ---- the open boundary lines -------------------------------------------------------
// The mark of each actor card with an open line (`_pm`), and the words of each map with
// an open line (`_ps`). The data does not change, thus the part makes them one time.
var PORT_RING = {c: '--ink-2', w: 1.5, d: 'r'}, PORT_LINE = {c: '--ink-2', d: 'r'};
(function () {
  ORDER.forEach(function (m) {
    var told = [];
    (m.ports || []).forEach(function (p) {
      (p.w || []).forEach(function (form) {
        var w = PORT_WORDS[form], c = m.byId[p.x];
        told.push(w + ': ' + p.x + '.');
        if (!c || c.k !== 'actor') return;
        var e = c._pm || (c._pm = {w: []});
        if (e.w.indexOf(w) < 0) e.w.push(w);
      });
    });
    if (told.length) m._ps = ' Open boundary lines: ' + told.length + '. ' + told.join(' ');
    m.cards.forEach(function (c) {
      var e = c._pm;
      if (!e) return;
      var tag = {s: e.w.length === 1 ? e.w[0] : counted(e.w.length, 'open line'), c: '--raised', t: '--ink-2', o: PORT_LINE};
      e.full = {a: 1, ring: PORT_RING, tag: tag, back: null, note: null};
      e.quiet = {a: QUIET, ring: PORT_RING, tag: tag, back: null, note: null};
      e.say = (e.w.length === 1 ? 'Open boundary line: ' : 'Open boundary lines: ') + e.w.join(', ') + '.';
    });
  });
})();
var PORT_MAP_CARD = VIEWS.map.card;
VIEWS.map.card = function (c) {
  var v = PORT_MAP_CARD(c), e = c._pm;
  return e ? (v ? e.quiet : e.full) : v;
};
VIEWS.map.facts = function (c) { return c._pm ? c._pm.say : ''; };
VIEWS.map.say = function (m) { return m._ps || ''; };
// The state of the open ports for the tests: the words of the map, and the words, the
// tag and the alpha of the mark (`d` of `viewCard`) of each marked card of a map.
function portState(mapId) {
  var m = MAPS[mapId || ''];
  return {judged: !!DATA.judged, say: m ? m._ps || '' : '',
    cards: m ? m.cards.filter(function (c) { return c._pm; }).map(function (c) {
      return {id: c.id, words: c._pm.w.slice(), tag: c._pm.full.tag.s, mark: c._v && c._vAt >= drawn - 1 ? c._v.d : null};
    }) : []};
}
"""

PORTS = f"var PORT_WORDS = {json.dumps(WORDS)};\n" + _SCRIPT
