"""The touch part of the canvas renderer: the selected card and its plate of facts.

`page_canvas` joins this part after the fade part (`page_canvas_fade`) and before the
input part. The part follows the section "Access" of docs/design/nested-canvas.md:

- A tap on a card selects the card (`tapAt`). The page draws a line around the selected
  card. When there is space on the screen above or below the card, the page also draws a
  plate with the name and the facts of the card (`selectedPlate`).
- A second tap on the selected card goes into it when it opens a map. A tap on the
  plate does the same.
- A tap on empty space removes the selection. When the map of the selected card closes,
  the selection also goes.

The selection does not appear or go at one time. Its alpha changes by 1 in SEL_MS or
more, and by 0.2 or less in one frame. With reduced motion, it changes at one time. The
work in a frame does not grow with the count of cards: the frame draws only the selected
card and the card that fades out.

On a touch screen, the plate is TARGET pixels high or more, as each other target is.
"""

from __future__ import annotations

TOUCH_PART = r"""
// ---- the selected card ----------------------------------------------------------------
// SEL_C is the selected card, or null. SELS has the cards that the frame draws as selected,
// each with its alpha `a`: the selected card, and the cards that fade out.
// `SEL_FADING` is true when an alpha did not get to its target in the frame.
var SEL_C = null, SELS = [], SEL_MS = 160, SEL_LAST = 0, SEL_FADING = false, PLATE_H = Math.max(38, TARGET);
function select(c) {
  SEL_C = c || null;
  if (SEL_C) say('Selected: card ' + SEL_C.id + '.');
  if (SEL_C && !SELS.some(function (e) { return e.c === SEL_C; })) SELS.push({c: SEL_C, a: 0});
  request();
}
// Tell if the map of card c is on the screen as an open map: the top map or a map of the chain.
function mapOpen(c) {
  if (c.map === TOP) return true;
  for (var i = 0; i < CHAIN.length; i++) if (CHAIN[i].child === c.map) return true;
  return false;
}
function selFrame() {
  var now = performance.now(), dt = SEL_LAST ? now - SEL_LAST : Infinity, step = reduced() ? 1 : Math.min(0.2, dt / SEL_MS);
  SEL_LAST = now; SEL_FADING = false;
  if (SEL_C && !mapOpen(SEL_C)) SEL_C = null;
  SELS = SELS.filter(function (e) {
    var to = e.c === SEL_C ? 1 : 0;
    e.a = approach(e.a, to, step);
    if (e.a !== to) SEL_FADING = true;
    return e.a > 0 || to > 0;
  });
}
// The line around each selected card. It is over the cards and under the portals.
function drawSelected() {
  ctx.setLineDash([]);
  SELS.forEach(function (e) {
    var b = screenBox(e.c);
    if (e.a <= 0.01 || !boxOnScreen(b)) return;
    ctx.globalAlpha = e.a; ctx.strokeStyle = C['--accent']; ctx.lineWidth = 2.5;
    ctx.beginPath(); rr(ctx, b[0] - 3, b[1] - 3, b[2] + 6, b[3] + 6, clamp(b[3] * 0.1, 2, 10)); ctx.stroke();
  });
}
// The screen box x, y, w, h of the plate of card c, below the card or above it. It is
// between the plate of the path and the plate of the help line. When it does not fit
// there, the result is null. `path` is the path of the frame (`pathParts`).
function selectedPlate(c, path) {
  var b = screenBox(c);
  if (!boxOnScreen(b)) return null;
  var w = Math.min(W - 24, Math.max(TARGET, unitWidth(c.id, 600) * 12.5, unitWidth(facts(c), 400) * 11) + 20);
  var x = clamp(b[0] + b[2] / 2 - w / 2, 12, W - 12 - w), top = pathPlate(path), lo = top[1] + top[3] + 6, hi = helpPlate()[1] - 6;
  if (b[1] + b[3] + 8 + PLATE_H <= hi) return [x, Math.max(lo, b[1] + b[3] + 8), w, PLATE_H];
  if (b[1] - 8 - PLATE_H >= lo) return [x, Math.min(hi - PLATE_H, b[1] - 8 - PLATE_H), w, PLATE_H];
  return null;
}
// The plate of each selected card: the name and the facts. It is over the portals. A tap on
// the plate of the selected card is a second tap on that card.
function drawPlates(path) {
  SELS.forEach(function (e) {
    var p = e.a > 0.01 ? selectedPlate(e.c, path) : null, c = e.c;
    if (!p) return;
    plate(p, 0.96 * e.a);
    text(fit(c.id, 12.5, p[2] - 20, 600), p[0] + 10, p[1] + p[3] / 2 - 3, 12.5, C['--ink'], e.a, 600);
    text(fit(facts(c), 11, p[2] - 20, 400), p[0] + 10, p[1] + p[3] / 2 + 12, 11, C['--ink-3'], e.a);
    if (c === SEL_C) HITS.push({x: p[0], y: p[1], w: p[2], h: p[3], kind: 'facts', id: c.id, map: c.map.id, show: e.a, go: function () { tapCard(c); }});
  });
}
// A tap on card c, or on empty space when c is null.
function tapCard(c) {
  if (c && c === SEL_C && c.child && openness(c) < 0.5) { select(null); flyGoal(goalOf(c.map, c, null)); return; }
  select(c);
}
// A tap at a screen point. An open card is empty space: its map is on the screen.
function tapAt(px, py) {
  var c = pick(px, py);
  tapCard(c && !(c.child && openness(c) >= 0.5) ? c : null);
}
"""
