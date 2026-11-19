"""The marks of the atlas page: the open boundary lines and the changes of a revision comparison.

`atlas_script` joins this part after the drawing part (`atlas_draw`). It gives the parity of
docs/design/atlas.md ("Requirements of the product page") with the ports of the canvas page
(`page_canvas_ports`) and with its Changes view (`page_canvas_changes`). The atlas page has
no Changes view: the marks are on the Map view, because the specification adds no
comparison view.

The open boundary lines. The page data gives the open `boundary flow` and
`boundary import` lines of each port of a nested map (`ports` in `canvas_data`). The actor
card of an open port has a dotted ring in --ink-2 and a tag above its top right corner. The
tag gives the short text of the line (`page_canvas_ports.WORDS`), or the count of the open
lines when the card has more than one text. The page never says "verified".

The changes. With `render --base`, the page data has the change keys of each map
(`canvas_changes`). A card with changed source has a ring of 2 px in --change and the tag
CHANGED. A card with only changed tests has a ring of 1.2 px and the tag TESTS. A card that
imports changed source has a dashed ring and the tag IMPORTS. A card that opens a map with
a change inside it has the tag CHANGED INSIDE. Each lost flow (a flow of a card with changed
source that has structural or declared evidence) has a dashed line in --change over its
wire. The headline gives the count of the cards with changed source.

The words. The list of the tree gives the words of each marked card and of each map with
marks, the reading line gives the words of a pointed card, and the live region gives the
words of a map when the camera goes into it. The values of each card are constant, thus
the part makes them one time, and a frame only reads them. A frame draws a mark only for a
card that the frame draws, and only when the card is 6 px high or more on the screen. A map
that shows as a small picture in its card has no marks (`drawMap` in `atlas_draw`).

The place of a tag. A tag obeys the rule of the labels at rest (docs/design/atlas.md): it
goes above or below the card, at its right end or its left end, at the first side with no
card, no name, no other tag and no line in it (`tagsOf`). The labels at rest and the lit
labels do not cover a tag. The tag has a thin edge in the ground color under its letters, not
a box, thus it does not cut a line or a ring.
"""

from __future__ import annotations

import json

from systemap import page_canvas_ports

_SCRIPT = r"""
// ---- the marks: open boundary lines and changes (atlas_marks) ---------------------------
var MARK_TAG = {changed: 'changed', tests: 'tests', imports: 'imports'};
var MARK_WORDS = {changed: 'Change: changed source.', tests: 'Change: only tests changed.', imports: 'Change: imports changed source.'};
var MARK_RING = {changed: {c: '--change', w: 2, d: null}, tests: {c: '--change', w: 1.2, d: null}, imports: {c: '--change', w: 1.2, d: [4, 3]}};
var PORT_RING = {c: '--ink-2', w: 1.5, d: [1.5, 2.5]};
ORDER.forEach(function (m) {
  var told = [];
  (m.ports || []).forEach(function (p) {
    (p.w || []).forEach(function (form) {
      var w = PORT_WORDS[form], c = m.byId[p.x];
      told.push(w + ': ' + p.x + '.');
      if (!c || c.k !== 'actor') return;
      var e = c._pm || (c._pm = []);
      if (e.indexOf(w) < 0) e.push(w);
    });
  });
  m._ps = told.length ? 'Open boundary lines: ' + told.length + '. ' + told.join(' ') : '';
  if (!m.ch) return;
  var cm = m.cm || {};
  m.cards.forEach(function (c) { if (MARK_RING[cm[c.id]]) c._cg = cm[c.id]; });
  (m.ci || []).forEach(function (id) { if (m.byId[id]) m.byId[id]._ci = true; });
  (m.cl || []).forEach(function (i) { if (m.flows[i]) m.flows[i]._lo = true; });
});
// The mark of card c: its ring and its tag, or null. The data does not change, thus the
// part keeps the mark on the card.
function markOf(c) {
  if (c._mk !== undefined) return c._mk;
  var tags = [], ring = null;
  if (c._pm) { ring = PORT_RING; tags.push(c._pm.length === 1 ? c._pm[0] : counted(c._pm.length, 'open line')); }
  if (c._cg) { ring = MARK_RING[c._cg]; tags.push(MARK_TAG[c._cg]); }
  if (c._ci) tags.push('changed inside');
  c._mk = tags.length ? {ring: ring, tag: tags.join(' · '), port: !!c._pm} : null;
  return c._mk;
}
// The size of the tag of card c at the map scale a: the font size and the width, in px.
function tagSize(c, a) {
  var k = markOf(c), fs = q(Math.min(Math.max(8.5 * Math.min(a, 1.6), 7), CAPS_MAX));
  return {fs: fs, tw: (unitWidth(k.tag.toUpperCase(), 500, true) + 0.09 * k.tag.length) * fs};
}
// The sides of a tag, in their order: above the right end of the card, above its left end,
// below its right end and below its left end. [x, y]: 1 is right or below, -1 is left or above.
var TAG_SIDES = [[1, -1], [-1, -1], [1, 1], [-1, 1]];
// The tag of card c at the side `side`, for the card box x, y, w, h on the screen: the point
// of the text and its box on the screen.
function tagAt(c, side, x, y, w, h, a) {
  var z = tagSize(c, a), tx = side[0] > 0 ? x + w - 2 : x + 2, ty = side[1] < 0 ? y - 7 : y + h + 7 + z.fs;
  var left = side[0] > 0 ? tx - z.tw - 3 : tx - 3;
  return {x: tx, y: ty, fs: z.fs, box: [left, ty - z.fs, left + z.tw + 6, ty + 2]};
}
// The sides of the tags of map m in layer `id` at the map scale a, and their boxes in the
// coordinates of the map. A tag obeys the rule of the labels at rest: the first side that is on
// no card, on no name, on no other tag and with no line through it. With no such side, the first
// side on no card, no name and no other tag, else the first side. The labels at rest and the lit
// labels do not cover these boxes (`seatsOf` and `litSeats`). The places are calculated again for
// a new step of zoom, in the full drawing at rest.
function tagsOf(m, id, a) {
  var L = linesOf(m, id), step = Math.floor(Math.log2(a) * 4), key = step + '|' + TEXTS;
  if (L._tags && (L._tags.key === key || !sharp)) return L._tags;
  var s = Math.pow(2, step / 4), wall = walls(m), taken = [], side = Object.create(null);
  function boxOf(c, i) {
    var b = c.b, t = tagAt(c, TAG_SIDES[i], s * b[0], s * b[1], s * b[2], s * b[3], s);
    return t.box.map(function (v) { return v / s; });
  }
  m.cards.forEach(function (c, n) {
    if (!markOf(c)) return;
    var pick = -1, open = -1;
    for (var i = 0; i < TAG_SIDES.length && pick < 0; i++) {
      var box = boxOf(c, i);
      if (wall.some(function (o, j) { return j !== n && over(box, o); }) || taken.some(function (o) { return over(box, o); })) continue;
      if (open < 0) open = i;
      if (!crossed(box, L.list, null)) pick = i;
    }
    side[c.id] = pick >= 0 ? pick : Math.max(open, 0);
    taken.push(boxOf(c, side[c.id]));
  });
  L._tags = {key: key, side: side, boxes: taken};
  return L._tags;
}
// The marks of the cards `cards` of map m, at the scale `a`, after the cards. A map that
// shows as a small picture in its card has no marks: its card has the tag CHANGED INSIDE.
function drawMarks(m, cards, a, ox, oy, alpha) {
  if (alpha <= 0.02) return;
  var lit = litOf(m), tags = tagsOf(m, shownLayer(m), a);
  ctx.lineJoin = 'round';
  for (var i = 0; i < cards.length; i++) {
    var c = cards[i], k = markOf(c);
    if (!k) continue;
    var b = c.b, x = ox + a * b[0], y = oy + a * b[1], w = a * b[2], h = a * b[3];
    if (h < 6 || x > W || y > H + 20 || x + w < 0 || y + h < -20) continue;
    var al = alpha * backCard(lit, c), r = cardCorner(c, w, h);
    if (k.ring) {
      ctx.globalAlpha = al; ctx.strokeStyle = C[k.ring.c]; ctx.lineWidth = k.ring.w; ctx.setLineDash(k.ring.d || []);
      ctx.beginPath(); rr(ctx, x - 3, y - 3, w + 6, h + 6, r + 3); ctx.stroke(); ctx.setLineDash([]);
    }
    var side = TAG_SIDES[tags.side[c.id] || 0], t = tagAt(c, side, x, y, w, h, a), align = side[0] > 0 ? 'right' : 'left';
    // A thin edge in the ground color under the letters, as a label at rest has. It covers
    // only the letters, not a box.
    if (t.fs >= textMin()) {
      try {
        spaced(ctx, t.fs * 0.09); ctx.font = font(500, t.fs, true); ctx.textAlign = align;
        ctx.globalAlpha = al; ctx.strokeStyle = C['--map']; ctx.lineWidth = 3; ctx.strokeText(k.tag.toUpperCase(), t.x, t.y);
      } finally { spaced(ctx, 0); }
    }
    caps(k.tag, t.x, t.y, t.fs, k.port ? C['--ink-2'] : C['--change'], al, 0.09, align);
    logged({t: 'mark', id: c.id, map: m.id, tag: k.tag, port: k.port, size: t.fs, alpha: al, b: [x, y, w, h], box: t.box, side: side,
      ring: k.ring ? {color: C[k.ring.c], w: k.ring.w, dash: !!k.ring.d} : null});
  }
}
// The lost flows of the lines `list` of map m: a dashed line in --change over the wire.
function drawMarkLines(m, list, a, ox, oy, alpha) {
  if (!m.ch || alpha <= 0.02) return;
  var lit = litOf(m), ww = clamp(1.6 * a * 1.5, 0.8, 1.6);
  list.forEach(function (e) {
    if (!e.f._lo) return;
    ctx.globalAlpha = alpha * backLine(lit, e.f.i); ctx.strokeStyle = C['--change']; ctx.lineWidth = ww; ctx.setLineDash([5, 3]);
    ctx.beginPath(); cutLine(ctx, e.d, ox, oy, a); ctx.stroke();
    logged({t: 'changed line', f: e.f.i, map: m.id, color: C['--change'], w: ww});
  });
  ctx.setLineDash([]);
}
// The words of the marks of card c, for the list of the tree and the reading line.
function markWords(c) {
  var out = [];
  if (c._pm) out.push((c._pm.length === 1 ? 'Open boundary line: ' : 'Open boundary lines: ') + c._pm.join(', ') + '.');
  if (c._cg) out.push(MARK_WORDS[c._cg]);
  if (c._ci) out.push('Changed inside: the map of this card or a map below it has map changes.');
  return out.join(' ');
}
// A commit name of 40 hex characters is cut to 7, as Git gives it.
function shortRev(s) { s = String(s || ''); return /^[0-9a-f]{40}$/.test(s) ? s.slice(0, 7) : s; }
// The count of the cards of map m with changed source.
function changedCount(m) { return m.ch ? m.cards.filter(function (c) { return c._cg === 'changed'; }).length : 0; }
// The words of the marks of map m: its open boundary lines and its comparison.
function mapMarkWords(m) {
  var out = m._ps ? [m._ps] : [];
  if (m.ch) {
    out.push('Compare ' + shortRev(m.ch.base) + ' to ' + shortRev(m.ch.head) + '. Changed source: ' + counted(changedCount(m), 'card') + '.');
    var r = m.cr || {};
    if (r.e) out.push('The map changes are not known, because ' + String(r.e).replace(/[\s.]+$/, '') + '.');
    else if (r.n) out.push('Map changes: ' + r.w + '.');
    if ((m.ci || []).length) out.push('Changed inside: ' + m.ci.join(', ') + '.');
  }
  return out.join(' ');
}
// The part of the counts of the headline for the marks of map m.
function markHead(m) {
  var n = 0;
  (m.ports || []).forEach(function (p) { n += (p.w || []).length; });
  return (n ? ' · ' + counted(n, 'open boundary line') : '') + (m.ch ? ' · ' + counted(changedCount(m), 'changed card') + ' since ' + shortRev(m.ch.base) : '');
}
// The marks of map m for the tests.
function markState(mapId) {
  var m = MAPS[mapId || ''];
  return m ? {words: mapMarkWords(m), head: markHead(m), cards: m.cards.filter(markOf).map(function (c) { return {id: c.id, tag: markOf(c).tag, words: markWords(c)}; }),
    lost: m.flows.filter(function (f) { return f._lo; }).map(function (f) { return f.i; })} : null;
}
"""

MARKS = f"var PORT_WORDS = {json.dumps(page_canvas_ports.WORDS)};\n" + _SCRIPT
