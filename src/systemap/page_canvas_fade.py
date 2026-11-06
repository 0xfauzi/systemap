"""The fade part of the canvas renderer: the value of each boundary flow from frame to frame.

`page_canvas` joins this part after the drawing part (`page_canvas_draw`). A boundary flow
fades in and out with the camera, as the maintainer rule of docs/design/nested-canvas.md
says: "Each change follows the zoom continuously. Nothing appears at one time."

- A boundary flow is under the cards, the texts and the portals, as the routes of a map
  are (decision of 2026-11-06). The frame draws the lines into a layer (`LAYER`). Then it
  removes the part of the layer under each box of OBST, with the opacity of the box, and
  it puts the layer on the screen before the portals. Thus a box that comes onto a line
  covers it, and a line is never on a card.
- A line uses a clear path (`boundaryPath`). When a box comes onto its path, the line
  changes to a different clear path, or it uses no path. The earlier path fades out by
  time while the box covers it, and the new path fades in.
- A value changes by 1 in FADE_MS or more, thus by 0.2 or less in one frame. A line of a
  map above that a deeper map replaces fades out (`spare`). A line with the value 0 costs
  nothing: the script draws only the paths with a value, and it keeps values only for the
  lines of the portals of the frame.
- A portal fades in and out by time, also when the chain changes (`portalFades`). Its
  `show` goes up or down by 1 in PORTAL_MS or more, and by PORTAL_DT / PORTAL_MS or less
  in one frame. A portal that the chain removes stays, with no lines, until it has faded
  out. The place that a portal keeps on its edge also grows and becomes smaller by time.
  Thus the other portals do not jump.
- With reduced motion, a line or a portal shows or goes at one time, as each camera move
  does.
"""

from __future__ import annotations

FADE = r"""
// ---- the fade of the boundary flows -------------------------------------------
// A boundary flow fades in and out with the camera. It does not appear or go at one time.
// FADE keeps a value from 0 to 1 for each of the 16 paths of each line, from frame to frame.
// - The line uses one path (`c`), and only a clear path (`clear` of `boundaryPath`). It
//   changes to the shortest clear path only when its path is not clear, or when its path
//   is much longer. When no path is clear, the line uses no path.
// - The value of the path of the line goes to 1, and the value of each other path goes to
//   0. A value changes by 1 in FADE_MS or more. The time between two frames counts as
//   FADE_DT or less, thus one frame changes a value by 0.2 or less.
// - A box can come onto a path while the path fades out. The line is under the boxes
//   (`LAYER`), thus the box covers it.
// - With reduced motion, each value is 1 or 0 at once.
// A line that is not in a portal of the frame has no value, and the script makes no path
// for it. `FADING` is true when a value did not get to its target in the frame.
var FADE = new Map(), FADE_MS = 200, FADE_DT = 40;
var FADE_LAST = 0, FADE_STEP = 1, PORTAL_STEP = 1, FADE_FRAME = 0, FADING = false;
function lineKey(nb, p, m) { return (m.id || '') + '>' + (nb.map.id || '') + '/' + nb.id + '|' + p.d; }
function fadeFrame() {
  var now = performance.now(), dt = FADE_LAST ? Math.min(now - FADE_LAST, FADE_DT) : FADE_DT;
  FADE_LAST = now; FADE_FRAME++; FADING = false;
  FADE_STEP = reduced() ? 1 : dt / FADE_MS;
  PORTAL_STEP = reduced() ? 1 : Math.min(dt, PORTAL_DT) / PORTAL_MS;
}
function portalKey(t) { return t.nb.map.id + '/' + t.nb.id; }
// A portal does not appear or go at one time. The camera gives the target `show` of a
// portal (`portalsOf`). The `show` that the frame draws goes to that target by `step` or
// less in each frame, from 0 for a new portal. A portal is drawn only with this `show`.
// Thus it is never more visible over a card. `room` is the part of its place that a
// portal keeps on its edge (`kept`). It goes to 1 by `step` in each frame while the
// portal is in `list`. A portal of the frame before that is not in `list` (the chain
// changed) stays at its side or in its row and follows its card, with no lines. Its `show`
// and its `room` go down by `step` in each frame, and it goes when its `room` is 0. A
// portal fades in PORTAL_MS, more slowly than a line, because a portal that fades in also
// pushes the portals near it (`apart`). The time between two frames counts as PORTAL_DT
// or less (one 60 Hz tick). Thus a portal moves by 16 pixels or less in one frame, also
// when the frames come more slowly. Then the fade takes more time. With reduced motion,
// `step` is 1.
var PORTALS = new Map(), PORTAL_MS = 400, PORTAL_DT = 17;
function portalFades(list) {
  var next = new Map(), out = [], step = PORTAL_STEP;
  list.forEach(function (t) {
    var was = PORTALS.get(portalKey(t)), to = t.show;
    t.show = approach(was ? was.show : 0, to, step);
    t.room = Math.min(1, (was ? was.room : 0) + step);
    if (t.show !== to || t.room < 1) FADING = true;
    next.set(portalKey(t), t); out.push(t);
  });
  PORTALS.forEach(function (t, key) {
    if (next.has(key) || t.room - step <= 0) return;
    FADING = true;
    var gone = Object.assign({}, t, {show: Math.max(0, t.show - step), room: t.room - step, lines: []});
    next.set(key, portalPlace(gone, screenBox(t.nb), null)); out.push(gone);
  });
  PORTALS = next;
  return out;
}
// The paths of a line to draw in this frame, each with its value. The record of the line
// keeps the portal `t` and the line `l` of the frame for `fadeLeft`.
function fadeOf(key, b, t, l) {
  var s = FADE.get(key), spare = l.spare;
  if (!s) { s = {c: -1, v: {}}; FADE.set(key, s); }
  s.frame = FADE_FRAME; s.t = t; s.l = l;
  var c = s.c;
  if (spare || !b || b.best < 0) c = -1;
  else if (c < 0 || !b.clear[c] || b.costs[c] > 1.25 * b.costs[b.best] + 40) c = b.best;
  s.c = c;
  var out = [], ids = Object.keys(s.v), step = FADE_STEP;
  if (c >= 0 && !(c in s.v)) ids.push(String(c));
  ids.forEach(function (id) {
    var i = +id, was = s.v[id] || 0, target = i === c ? 1 : 0;
    var v = approach(was, target, step);
    if (v !== target) FADING = true;
    if (v <= 0.004 || !b) { delete s.v[id]; return; }
    s.v[id] = v;
    out.push({i: i, pts: b.all[i], v: v});
  });
  if (!out.length && c < 0) FADE.delete(key);
  return out;
}
// Draw each line that has a value but that the frame did not draw, because the chain
// changed. It fades out. Its end is on the portal of the same neighbour in this frame, also
// when that portal fades out. When there is no such portal, its end stays on the portal
// box of its last frame. Thus a line does not go at one time.
function fadeLeft(each) {
  FADE.forEach(function (s) {
    if (s.frame !== FADE_FRAME) each(PORTALS.get(portalKey(s.t)) || s.t, Object.assign({}, s.l, {spare: true}));
  });
}
// Remove the values of the lines that the frame did not draw.
function fadeEnd() {
  FADE.forEach(function (s, key) { if (s.frame !== FADE_FRAME) FADE.delete(key); });
}

// ---- the layer of the boundary flows -------------------------------------------
// The boundary flows are under the cards, the texts and the portals. The frame draws them
// into LAYER, with the resolution of the canvas of the frame (`frameCanvas`). Each of the
// two canvases has its own layer, thus a start or a stop of the camera makes no new layer.
// Then the frame removes the part of LAYER under each box of OBST, with the opacity of the
// box. Then it puts LAYER on the canvas of the frame, before the portals. Only the box LBOX
// around the lines changes, and the next frame on that canvas clears that box first
// (`clear`). A frame with no line puts nothing of the layer on the screen. A frame with
// no portal and no line value does not use the layer (`LUSED`).
var LAYER = null, LG = null, LBOX = null, LCLEAR = null, LUSED = false, LNOW = null;
function layerOpen(screen) {
  var o = screen.canvas, L = screen._layer;
  if (!L) { L = screen._layer = {c: document.createElement('canvas'), clear: null}; L.g = L.c.getContext('2d'); }
  if (L.c.width !== o.width || L.c.height !== o.height) { L.c.width = o.width; L.c.height = o.height; L.clear = null; }
  LNOW = L; LAYER = L.c; LG = L.g;
  LG.setTransform(o.width / W, 0, 0, o.height / H, 0, 0);
  LG.globalCompositeOperation = 'source-over'; LG.globalAlpha = 1;
  if (L.clear) LG.clearRect(L.clear[0], L.clear[1], L.clear[2] - L.clear[0], L.clear[3] - L.clear[1]);
  L.clear = LCLEAR = null; LBOX = null;
  return LG;
}
// Make LBOX larger, so that it holds the points of a line and `pad` pixels around them.
function layerHold(pts, pad) {
  var b = LBOX || [Infinity, Infinity, -Infinity, -Infinity];
  pts.forEach(function (p) { b[0] = Math.min(b[0], p[0] - pad); b[1] = Math.min(b[1], p[1] - pad); b[2] = Math.max(b[2], p[0] + pad); b[3] = Math.max(b[3], p[1] + pad); });
  LBOX = b;
}
// Remove the part of the layer under the boxes, and put the layer on the canvas of the
// frame, which has the size of the layer.
function layerClose() {
  var b = LBOX;
  if (!b) return;
  b = LNOW.clear = LCLEAR = [Math.max(0, Math.floor(b[0])), Math.max(0, Math.floor(b[1])), Math.min(W, Math.ceil(b[2])), Math.min(H, Math.ceil(b[3]))];
  if (b[2] <= b[0] || b[3] <= b[1]) return;
  LG.globalCompositeOperation = 'destination-out'; LG.globalAlpha = 1; LG.fillStyle = '#000'; LG.beginPath();
  for (var i = 0; i < NOBST; i += OB) {
    var x0 = OBST[i], y0 = OBST[i + 1], x1 = OBST[i + 2], y1 = OBST[i + 3], al = OBST[i + 5];
    if (x0 >= b[2] || y0 >= b[3] || x1 <= b[0] || y1 <= b[1] || al <= 0) continue;
    if (al >= 1) LG.rect(x0, y0, x1 - x0, y1 - y0);
    else { LG.globalAlpha = al; LG.fillRect(x0, y0, x1 - x0, y1 - y0); LG.globalAlpha = 1; }
  }
  LG.fill(); LG.globalCompositeOperation = 'source-over';
  var sx = LAYER.width / W, sy = LAYER.height / H, px = Math.floor(b[0] * sx), py = Math.floor(b[1] * sy);
  var pw = Math.min(LAYER.width, Math.ceil(b[2] * sx)) - px, ph = Math.min(LAYER.height, Math.ceil(b[3] * sy)) - py;
  if (pw <= 0 || ph <= 0) return;
  ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1;
  ctx.drawImage(LAYER, px, py, pw, ph, px, py, pw, ph); ctx.restore();
}
"""
