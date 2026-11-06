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
- A portal moves off the cards, the flow label plates and the texts of the maps on the
  screen (`dodge`). It uses the boxes that the frame records in OBST before the portals.
  It moves along its edge, or a short distance into the screen. This move changes by
  DODGE_PX pixels for each millisecond or less, thus the portal does not jump.
- With reduced motion, a line or a portal shows or goes at one time, as each camera move
  does. A portal also goes off the boxes at one time.
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
  var pdt = Math.min(dt, PORTAL_DT), still = reduced();
  FADE_STEP = still ? 1 : dt / FADE_MS;
  PORTAL_STEP = still ? 1 : pdt / PORTAL_MS;
  DODGE_STEP = still ? Infinity : pdt * DODGE_PX;
}
function portalKey(t) { return t.nb.map.id + '/' + t.nb.id; }
// A portal does not appear or go at one time. The target `show` of each portal in `list`
// is 1. A neighbour has a portal only while no part of its card is on the screen
// (`portalsOf`). The `show` that the frame draws goes to 1 by `step` or less in each frame,
// from 0 for a new portal. A portal that is not in `list` fades out (below). Thus, when the
// camera stops, each `show` gets to 1 or 0. A portal is drawn only with this `show`. Thus
// it is never more visible over a card. `room` is the part of its place that a portal
// keeps on its edge (`kept`). It goes to 1 by `step` in each frame while the
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
    var was = PORTALS.get(portalKey(t));
    t.show = approach(was ? was.show : 0, 1, step);
    t.room = Math.min(1, (was ? was.room : 0) + step);
    if (was) { t.dx = was.dx; t.dy = was.dy; t.x0 = was.x0; t.y0 = was.y0; }
    if (t.show < 1 || t.room < 1) FADING = true;
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

// ---- the portals keep off the maps ----------------------------------------------
// A portal moves off the boxes of the maps on the screen: the cards, the flow label plates
// and the texts (the first NMAP values of OBST). A box counts when its opacity is
// DODGE_MIN or more and it is not a box of the neighbour of the portal. A portal keeps
// DODGE_PAD pixels from such a box, and P_GAP pixels from the other portals. This occurs
// after `apart`. When the place of the portal is open, the portal stays there. Else it
// goes to the open place that is nearest to its move in the frame before: along its edge,
// or DODGE_IN pixels or less into the screen. Thus it does not go from one side of a box
// to the other side while the camera moves. When no place is open, the portal stays at
// its place. The move from the place (`dx`, `dy`) goes to its target by DODGE_STEP pixels
// or less in each frame: DODGE_PX pixels for each millisecond, for PORTAL_DT ms or less.
// Thus, while the camera moves, this move adds 3.4 pixels or less in one frame to the move
// of the place. While the place does not move, the move can be faster (`dodgeStep`). When
// the place moves by `moved` pixels in a frame, the step is also DODGE_JUMP - `moved` or less.
// Thus this move does not make a move of the portal of more than DODGE_JUMP pixels in one
// frame. When the place moves by DODGE_JUMP pixels or more (a fast camera move, a jump of
// the camera or a change of the screen size), the step is `moved` or less. Thus the move
// from the place does not stay from an earlier view, and the portal moves by 2 times
// `moved` or less. While the move goes step by step, it does not go over a different
// portal (`dodgePath`). The portal stays in the range of its edge. A new portal starts at
// its target, because it fades in from 0. With reduced motion, a portal goes to its target
// at once.
var NMAP = 0, DODGE_MIN = 0.05, DODGE_PAD = 4, DODGE_PX = 0.2, DODGE_STEP = Infinity, DODGE_IN = 34, DODGE_JUMP = 16;
function dodge(list) {
  list.forEach(function (t) {
    t.moved = t.x0 === undefined ? 0 : Math.hypot(t.x - t.x0, t.y - t.y0);
    t.x0 = t.x; t.y0 = t.y;
    if (t.dx !== undefined) { t.x += t.dx; t.y += t.dy; }
  });
  list.forEach(function (t) {
    var fresh = t.dx === undefined, jump = t.moved >= DODGE_JUMP, at = fresh || jump || DODGE_STEP === Infinity;
    var to = dodgeEdge(t, dodgeTo(t, list, at));
    if (!fresh) { var here = dodgeEdge(t, [t.dx, t.dy]); t.dx = here[0]; t.dy = here[1]; }
    var ex = fresh ? 0 : to[0] - t.dx, ey = fresh ? 0 : to[1] - t.dy, far = Math.hypot(ex, ey);
    var step = fresh || DODGE_STEP === Infinity ? Infinity : jump ? t.moved : dodgeStep(t.moved, far);
    if (far > step) { t.dx += ex * step / far; t.dy += ey * step / far; FADING = true; }
    else { t.dx = to[0]; t.dy = to[1]; }
    t.x = t.x0 + t.dx; t.y = t.y0 + t.dy;
  });
  return list;
}
// The step of the move from the place in one frame, when the place moves by `moved` pixels
// (less than DODGE_JUMP) and the move has `far` pixels to its target. While the place
// moves by DODGE_CALM pixels or more, the step is DODGE_STEP or less. While the place does
// not move, the step is DODGE_EASE of `far`, and DODGE_STEP or more. Thus the move slows
// down near its target, and a long move ends soon after the camera stops. Between the two,
// the step changes with `moved`. The step is also DODGE_JUMP - `moved` or less, with a
// margin of DODGE_ROUND pixels for the rounding of the floating point values.
var DODGE_CALM = 4, DODGE_EASE = 0.25, DODGE_ROUND = 0.05;
function dodgeStep(moved, far) {
  var still = clamp(1 - moved / DODGE_CALM, 0, 1), more = Math.max(0, DODGE_EASE * far - DODGE_STEP);
  return Math.min(DODGE_STEP + still * more, DODGE_JUMP - DODGE_ROUND - moved);
}
// The move m of portal `t`, with the portal in the range of its edge. When `apart` puts
// the place out of that range, the range goes to the place.
function dodgeEdge(t, m) {
  var ends = t.side ? [P_TOP, bottomRow()] : rowRange(t), at = t.side ? t.y0 : t.x0;
  var to = clamp(at + (t.side ? m[1] : m[0]), Math.min(ends[0], at), Math.max(ends[1], at)) - at;
  return t.side ? [m[0], to] : [to, m[1]];
}
// The boxes near the edge of portal `t` that it must keep off, as x0, y0, x1, y1 with the
// space around them: the boxes of the maps, and then the other portals from index `n`.
function dodgeBoxes(t, list) {
  var nb = screenBox(t.nb), row = !t.side, reach = DODGE_IN + (row ? t.h : t.w) / 2 + P_GAP, out = [];
  var lo = (row ? t.y0 : t.x0) - reach, hi = (row ? t.y0 : t.x0) + reach, a = row ? 1 : 0;
  for (var i = 0; i < NMAP; i += OB) {
    if (OBST[i + 5] < DODGE_MIN || OBST[i + a] >= hi || OBST[i + a + 2] <= lo) continue;
    if (OBST[i] >= nb[0] - 1 && OBST[i + 1] >= nb[1] - 1 && OBST[i + 2] <= nb[0] + nb[2] + 1 && OBST[i + 3] <= nb[1] + nb[3] + 1) continue;
    out.push([OBST[i] - DODGE_PAD, OBST[i + 1] - DODGE_PAD, OBST[i + 2] + DODGE_PAD, OBST[i + 3] + DODGE_PAD]);
  }
  out.n = out.length;
  list.forEach(function (o) {
    if (o !== t) out.push([o.x - o.w / 2 - P_GAP, o.y - o.h / 2 - P_GAP, o.x + o.w / 2 + P_GAP, o.y + o.h / 2 + P_GAP]);
  });
  return out;
}
// Tell if portal `t`, on its way from the middle x, y to the middle u, v, covers none of
// the boxes from index i0 to index i1, by more than 0.5 pixels.
function dodgeOpen(t, x, y, u, v, boxes, i0, i1) {
  var x0 = Math.min(x, u) - t.w / 2 + 0.5, y0 = Math.min(y, v) - t.h / 2 + 0.5;
  var x1 = Math.max(x, u) + t.w / 2 - 0.5, y1 = Math.max(y, v) + t.h / 2 - 0.5;
  for (var i = i0; i < i1; i++) { var b = boxes[i]; if (b[0] < x1 && x0 < b[2] && b[1] < y1 && y0 < b[3]) return false; }
  return true;
}
// The moves dx, dy of portal `t` to a place next to each box: along its edge in the two
// directions, and into the screen (`dir`) by DODGE_IN pixels or less.
function dodgeMoves(t, boxes) {
  var row = !t.side, dir = row ? (t.y0 < H / 2 ? 1 : -1) : -t.side, out = [];
  var ends = row ? rowRange(t) : [P_TOP, bottomRow()], lo = ends[0], hi = ends[1];
  var at = row ? t.x0 : t.y0, half = (row ? t.w : t.h) / 2, across = row ? t.y0 : t.x0, deep = (row ? t.h : t.w) / 2;
  boxes.forEach(function (b) {
    var a0 = row ? b[0] : b[1], a1 = row ? b[2] : b[3], c = dir > 0 ? (row ? b[3] : b[2]) + deep : (row ? b[1] : b[0]) - deep;
    [a0 - half, a1 + half].forEach(function (p) { if (p >= lo && p <= hi) out.push(row ? [p - at, 0] : [0, p - at]); });
    if ((c - across) * dir > 0 && Math.abs(c - across) <= DODGE_IN) out.push(row ? [0, c - across] : [c - across, 0]);
  });
  return out;
}
// Tell if portal `t` can go from its place of this frame to the move m step by step and
// not go over a different portal. A portal that it covers now does not stop it. With
// `at` true (a new portal, reduced motion, or a place that moves by DODGE_JUMP pixels or
// more), the portal does not slide over the portals between, thus each move can go.
function dodgePath(t, m, boxes, at) {
  if (at) return true;
  var x = t.x0 + (t.dx || 0), y = t.y0 + (t.dy || 0), u = t.x0 + m[0], v = t.y0 + m[1];
  for (var i = boxes.n; i < boxes.length; i++) {
    if (!dodgeOpen(t, x, y, x, y, boxes, i, i + 1)) continue;
    if (!dodgeOpen(t, x, y, u, v, boxes, i, i + 1)) return false;
  }
  return true;
}
// The target move dx, dy of portal `t` from its place. `apart` keeps the portals apart at
// their places, thus only the boxes of the maps can close the place. A move goes to no box.
// When no move is possible, the portal goes back to its place, or it stays where it is if
// a different portal is on the way.
function dodgeTo(t, list, at) {
  var boxes = dodgeBoxes(t, list), back = [0, 0], here = [t.dx || 0, t.dy || 0];
  if (dodgeOpen(t, t.x0, t.y0, t.x0, t.y0, boxes, 0, boxes.n)) return dodgePath(t, back, boxes, at) ? back : here;
  var best = dodgePath(t, back, boxes, at) ? back : here, far = Infinity;
  dodgeMoves(t, boxes).forEach(function (m) {
    var d = Math.abs(m[0] - here[0]) + Math.abs(m[1] - here[1]);
    if (d < far && dodgeOpen(t, t.x0 + m[0], t.y0 + m[1], t.x0 + m[0], t.y0 + m[1], boxes, 0, boxes.length) && dodgePath(t, m, boxes, at)) { far = d; best = m; }
  });
  return best;
}
"""
