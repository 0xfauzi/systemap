"""The drawing part of the atlas renderer: the containers, the regions, the lines and the cards.

`atlas_script` joins this part after the lines part (`atlas_lines`). It is a fork of the
drawing part of the canvas page (`page_canvas_draw`), with the look of docs/design/atlas.md.
It keeps the rules of the canvas engine for speed: it paints with the 2D API of a
`<canvas>` element, it draws only the cards and the lines that the box index of a map gives
for the screen, it puts the boxes of one style in one path (`Batch`), it draws no text
below MIN_TEXT (OPEN_TEXT in an open map), and it draws a large map from stored images
(`atlas_image`).

The look at rest:

- A container that holds only actors is a label above its first actor, not a surface. A
  different container is a surface with its name and its subtitle. A region is a faint
  tint with its number in a ring and its name. The tint keeps 3 units from the edge of the
  region, so adjacent regions do not touch.
- A line has one neutral color, and a casing in the color of the ground below it. Each
  line draws its casing and then its wire, so that a line goes over a different line with
  a small gap. Each line has a dot at its source and an arrowhead at its target.
- A card shows its name. Its short name shows below the name when the scale of its map is
  0.95 or more. An actor has round ends. A card that is not a component and not an actor
  has a small tag with its kind. A quiet card keeps a faint outline (`quietOf`).
- A card that opens a map has a second edge behind it and a small picture of its map at
  its right (`layout` in `atlas_scene`). The map above fades while the nested map takes
  the screen (`inside`).
"""

from __future__ import annotations

DRAW = r"""
// ---- batches of boxes ----------------------------------------------------------
function Batch(fill) { this.fill = fill; this.items = new Map(); }
Batch.prototype.rect = function (color, alpha, x, y, w, h, r, width) {
  if (!color || color === 'none' || alpha <= 0.02) return;
  var al = Math.round(alpha * 16) / 16, key = color + '|' + al + '|' + (width || 1);
  var e = this.items.get(key);
  if (!e) { e = {color: color, alpha: al, width: width || 1, list: []}; this.items.set(key, e); }
  e.list.push(x, y, w, h, r);
};
Batch.prototype.flush = function (g) {
  var fill = this.fill;
  this.items.forEach(function (e) {
    var l = e.list;
    g.globalAlpha = e.alpha; g.beginPath();
    for (var i = 0; i < l.length; i += 5) rr(g, l[i], l[i + 1], l[i + 2], l[i + 3], l[i + 4]);
    if (fill) { g.fillStyle = e.color; g.fill(); } else { g.strokeStyle = e.color; g.lineWidth = e.width; g.stroke(); }
  });
  this.items.clear();
};
// Each box and each line point is cut to the target, with a margin of CUT pixels. When the
// camera is deep in a map, a box of a map above it can be a million pixels wide.
var CUT = 8;
function bounds(g) { return g === ctx ? [W, H] : [g.canvas.width, g.canvas.height]; }
function rr(g, x, y, w, h, r) {
  var b = bounds(g), x0 = Math.max(x, -CUT), y0 = Math.max(y, -CUT), x1 = Math.min(x + w, b[0] + CUT), y1 = Math.min(y + h, b[1] + CUT);
  if (x1 <= x0 || y1 <= y0) return;
  if (r > 0.5 && g.roundRect) g.roundRect(x0, y0, x1 - x0, y1 - y0, Math.min(r, (x1 - x0) / 2, (y1 - y0) / 2));
  else g.rect(x0, y0, x1 - x0, y1 - y0);
}
var UNDER = new Batch(true), UNDER_LINE = new Batch(false), FILL = new Batch(true), LINE = new Batch(false), MARK = new Batch(true);
function flushCards(g) { UNDER.flush(g); UNDER_LINE.flush(g); MARK.flush(g); FILL.flush(g); LINE.flush(g); }
function q(size) { return Math.round(size * 2) / 2; }
// From NAME_H to NAME_H + 4 of screen height, a card changes from a mark into a card. In an
// open map (OPEN: the top map, or a nested map that has the screen) the card keeps its
// shape from OPEN_H, and its text draws from OPEN_TEXT, as in the design study. Thus the
// opening view and the Fit view of a phone show the cards, their names and the names of
// the regions. The marks stay for the small picture of a nested map and for a large map
// (`marksImage`), because they keep the frame time low.
var OPEN = false, OPEN_H = 3, OPEN_TEXT = 2.5;
function cardShow(h) { return OPEN ? smooth(OPEN_H, OPEN_H + 3, h) : smooth(NAME_H, NAME_H + 4, h); }
function hasText(h) { return h >= (OPEN ? OPEN_H : NAME_H); }
function textMin() { return OPEN ? OPEN_TEXT : MIN_TEXT; }
function text(s, x, y, size, color, alpha, weight, mono, align) {
  if (size < textMin() || alpha <= 0.02 || !s) return;
  ctx.globalAlpha = alpha; ctx.fillStyle = color; ctx.font = font(weight || 400, size, mono);
  ctx.textAlign = align || 'left'; ctx.fillText(s, x, y);
  if (TLOG && (ctx === PAGE_CTX || ctx === STILL_CTX)) TLOG.push(drawnText(s, x, y, size, alpha, weight, color));
}
// While TLOG is a list, each text adds its size, its alpha, its color and its screen box.
// While DLOG is a list, each map, container, region, line and card of the page frame adds
// its screen geometry (`systemapCanvas.drawn`). The tests read them.
var TLOG = null, DLOG = null;
function logged(o) { if (DLOG && (ctx === PAGE_CTX || ctx === STILL_CTX)) DLOG.push(o); }
function drawnText(s, x, y, size, alpha, weight, color) {
  var m = ctx.measureText(s);
  return {s: s, size: size, alpha: alpha, weight: weight || 400, color: color,
    box: [x - m.actualBoundingBoxLeft, y - m.actualBoundingBoxAscent, x + m.actualBoundingBoxRight, y + m.actualBoundingBoxDescent]};
}
// The letter spacing of the uppercase names, where the browser has it.
function spaced(g, px) { if ('letterSpacing' in g) g.letterSpacing = px ? px.toFixed(2) + 'px' : '0px'; }
// An uppercase name in the mono font: the names of the containers and the regions, and the
// tag of a kind. It has the smallest size of a different text (`textMin`).
// The size is in half pixels, CAPS_MAX or less. A new font size in each frame of a zoom
// costs time.
var CAPS_MAX = 13;
function caps(s, x, y, size, color, alpha, track, align) {
  size = q(Math.min(size, CAPS_MAX));
  if (size < textMin() || alpha <= 0.02) return;
  try { spaced(ctx, size * track); text(s.toUpperCase(), x, y, size, color, alpha, 500, true, align); } finally { spaced(ctx, 0); }
}

// ---- the dot grid ----------------------------------------------------------------
// One round dot in each cell. The cell on the screen is from GRID_MIN to 2 times GRID_MIN
// pixels: it divides by 2 each time the zoom doubles. The dot has a constant size on the
// screen. The page keeps the pattern of each cell size.
var GRID = {made: new Map(), color: ''}, GRID_PITCH = 24, GRID_MIN = 17, GRID_R = 0.9;
function gridPattern(size, d, color) {
  if (GRID.color !== color) { GRID.made.clear(); GRID.color = color; }
  var key = size + ':' + d, p = GRID.made.get(key);
  if (p === undefined) {
    var cvs = document.createElement('canvas'), g = cvs.getContext('2d');
    cvs.width = cvs.height = size; g.fillStyle = color; g.globalAlpha = 0.6;
    g.beginPath(); g.arc(GRID_R * d + 0.5, GRID_R * d + 0.5, GRID_R * d, 0, 2 * Math.PI); g.fill();
    p = ctx.createPattern(cvs, 'repeat'); GRID.made.set(key, p || null);
  }
  return p;
}
function drawGrid() {
  var raw = GRID_PITCH * cam.k;
  if (!(raw > 0) || !window.DOMMatrix) return;
  var pitch = raw / Math.pow(2, Math.floor(Math.log(raw / GRID_MIN) / Math.LN2)), d = dpr() * (sharp ? 1 : 0.5);
  var size = Math.max(4, Math.round(pitch * d)), p = gridPattern(size, d, C['--line-2']);
  if (!p || !p.setTransform) return;
  var s = pitch / size;
  // The offset is taken modulo the cell. A deep zoom has a large offset, and the pattern
  // matrix of the browser has a low precision.
  function off(v) { return -(((v % pitch) + pitch) % pitch) - GRID_R; }
  p.setTransform(new DOMMatrix([s, 0, 0, s, off(cam.x * cam.k), off(cam.y * cam.k)]));
  ctx.globalAlpha = 1; ctx.fillStyle = p; ctx.fillRect(0, HEAD_H, W, H - HEAD_H);
}

// ---- containers and regions -------------------------------------------------------
// The cards inside a box b of map m, by the top left corner of each card.
function inside(m, b) {
  return m.cards.filter(function (c) { return c.b[0] >= b[0] && c.b[0] < b[0] + b[2] && c.b[1] >= b[1] && c.b[1] < b[1] + b[3]; });
}
// The kind of each container: 'actors' (only actors: a label), 'none' (no card) or 'box'.
function boxKind(m, b) {
  if (b._kind) return b._kind;
  var list = inside(m, b.b);
  b._kind = !list.length ? 'none' : list.every(function (c) { return c.k === 'actor'; }) ? 'actors' : 'box';
  if (b._kind === 'actors') {
    b._at = [Math.min.apply(null, list.map(function (c) { return c.b[0]; })) + 6, Math.min.apply(null, list.map(function (c) { return c.b[1]; })) - 14];
  }
  return b._kind;
}
function drawBoxes(g, m, a, ox, oy, alpha, labels, open) {
  if (alpha <= 0.02) return;
  var fills = new Batch(true), lines = new Batch(false), tint = new Batch(true), rings = new Batch(false);
  m.boxes.forEach(function (b) {
    if (boxKind(m, b) !== 'box') return;
    var x = ox + a * b.b[0], y = oy + a * b.b[1], w = a * b.b[2], h = a * b.b[3];
    // A soft shadow under the surface, only in the full drawing at rest of the screen.
    if (sharp && g === PAGE_CTX && w < 4 * W && alpha > 0.5) {
      g.save(); g.globalAlpha = alpha; g.shadowColor = C['--shade']; g.shadowBlur = 18; g.shadowOffsetY = 10;
      g.fillStyle = C['--surface']; g.beginPath(); rr(g, x, y, w, h, 16 * a); g.fill(); g.restore();
    }
    logged({t: 'box', n: b.n, b: [x, y, w, h]});
    fills.rect(C['--surface'], alpha, x, y, w, h, 16 * a);
    lines.rect(C['--line'], alpha, x, y, w, h, 16 * a, 1);
  });
  var ra = alpha * smooth(0.1, 0.25, open);
  m.regions.forEach(function (r) {
    logged({t: 'region', n: r.n, a: ra, b: [ox + a * (r.b[0] + 3), oy + a * (r.b[1] + 3), a * (r.b[2] - 6), a * (r.b[3] - 6)]});
    tint.rect(C['--tint'], ra, ox + a * (r.b[0] + 3), oy + a * (r.b[1] + 3), a * (r.b[2] - 6), a * (r.b[3] - 6), 12 * a);
  });
  fills.flush(g); lines.flush(g); tint.flush(g);
  if (!labels) return;
  m.boxes.forEach(function (b) {
    var kind = boxKind(m, b), x = ox + a * b.b[0], y = oy + a * b.b[1];
    if (kind === 'actors') { logged({t: 'actors', n: b.n}); if (m === TOP) caps(b.n, ox + a * b._at[0], oy + a * b._at[1], 9.5 * a, C['--ink-3'], alpha, 0.11); return; }
    if (kind !== 'box') return;
    var fs = 9.5 * a, nw = (unitWidth(b.n.toUpperCase(), 500, true) + 0.11 * b.n.length) * q(Math.min(fs, CAPS_MAX));
    caps(b.n, x + 20 * a, y + 30 * a, fs, C['--ink-3'], alpha, 0.11);
    var us = q(Math.min(10 * a, 14));
    if (b.u) text(fit(b.u, us, a * b.b[2] - 50 * a - nw, 400), x + 20 * a + nw + 10 * a, y + 30 * a, us, C['--ink-3'], alpha);
  });
  if (ra <= 0.02) return;
  m.regions.forEach(function (r, i) {
    var x = ox + a * r.b[0], y = oy + a * r.b[1];
    rings.rect(C['--line-2'], ra, x + 10 * a, y + 10 * a, 14 * a, 14 * a, 7 * a, 1);
    caps(String(i + 1), x + 17 * a, y + 20 * a, 8.5 * a, C['--ink-3'], ra, 0, 'center');
    caps(r.n, x + 31 * a, y + 20.5 * a, 9 * a, C['--ink-3'], ra, 0.11);
  });
  rings.flush(g);
}

// ---- lines ----------------------------------------------------------------------
// A line of segments with right angles and round corners, cut to the target. The radius of
// a corner is 7 units of the map, and half of the shorter of its two segments or less.
function cutLine(g, p, ox, oy, a) {
  var b = bounds(g), bx = b[0] + CUT, by = b[1] + CUT, n = p.length, most = 7 * a;
  function X(i) { return clamp(ox + a * p[i][0], -CUT, bx); }
  function Y(i) { return clamp(oy + a * p[i][1], -CUT, by); }
  function len(i) { return Math.abs(X(i) - X(i - 1)) + Math.abs(Y(i) - Y(i - 1)); }
  g.moveTo(X(0), Y(0));
  for (var i = 1; i < n - 1; i++) g.arcTo(X(i), Y(i), X(i + 1), Y(i + 1), Math.min(most, len(i) / 2, len(i + 1) / 2));
  g.lineTo(X(n - 1), Y(n - 1));
}
// The arrowhead at the end z of a line from y, and the dot at the start.
function arrowHead(g, z, y, s, w) {
  var l = Math.hypot(z[0] - y[0], z[1] - y[1]) || 1, ux = (z[0] - y[0]) / l, uy = (z[1] - y[1]) / l;
  g.moveTo(z[0], z[1]);
  g.lineTo(z[0] - ux * s - uy * w, z[1] - uy * s + ux * w);
  g.lineTo(z[0] - ux * s + uy * w, z[1] - uy * s - ux * w);
  g.closePath();
}
// The lines of map m in the layer of the frame. `list` is the list of the lines to draw
// (`linesOf`), or the lines of the index for the screen. Each line draws its casing and
// its wire. Then the dots and the arrowheads draw in one path.
var CASE_W = 5, WIRE_W = 1.15;
function drawLines(g, m, list, L, a, ox, oy, alpha) {
  if (alpha <= 0.02 || !list.length) return;
  var rest = alpha * L.rest, cw = Math.min(CASE_W, CASE_W * a * 1.5), ww = clamp(WIRE_W * a * 1.5, 0.5, WIRE_W), lit = g === ctx ? litOf(m) : null;
  var steps = stepping(m), dw = clamp(DONE_W * a * 1.5, 0.6, DONE_W);
  g.lineJoin = 'round'; g.setLineDash([]);
  list.forEach(function (e) {
    var st = steps ? stepState(m, e.f.i) : '';
    g.beginPath(); cutLine(g, e.d, ox, oy, a);
    g.globalAlpha = rest * backLine(lit, e.f.i) * (st === 'later' ? LATER_A : 1); g.strokeStyle = C['--map']; g.lineWidth = cw; g.stroke();
    g.strokeStyle = st === 'was' ? C['--ink-2'] : C['--wire']; g.lineWidth = st === 'was' ? dw : ww; g.stroke();
    if (!VIEW_AIM) STATS.flows++;
    if (DLOG) logged({t: 'line', f: e.f.i, casing: cw, wire: g.lineWidth, alpha: g.globalAlpha, color: g.strokeStyle, step: st, p: e.d.map(function (v) { return [ox + a * v[0], oy + a * v[1]]; })});
  });
  var s = clamp(7.5 * a, 2.5, 9), w = s * 0.48, r = clamp(2 * a, 0.8, 2.6);
  if (steps) { stepEnds(g, m, list, L, alpha, a, ox, oy, s, w, r); return; }
  g.fillStyle = C['--ink-3'];
  // The dots and the arrowheads in two paths: of the lines that the light makes go back, and
  // of the other lines.
  [true, false].forEach(function (back) {
    var n0 = 0;
    g.beginPath();
    list.forEach(function (e) {
      if ((backLine(lit, e.f.i) < 1) !== back) return;
      var p = e.q, n = p.length, z = [ox + a * p[n - 1][0], oy + a * p[n - 1][1]], y = [ox + a * p[n - 2][0], oy + a * p[n - 2][1]];
      arrowHead(g, z, y, s, w); n0++;
      if (DLOG) logged({t: 'ends', f: e.f.i, dot: [ox + a * p[0][0], oy + a * p[0][1], r], tip: z, from: y, s: s, w: w});
      g.moveTo(ox + a * p[0][0] + r, oy + a * p[0][1]); g.arc(ox + a * p[0][0], oy + a * p[0][1], r, 0, 2 * Math.PI);
    });
    g.globalAlpha = alpha * L.ends * (back ? 1 - 0.78 * DIM : 1);
    if (n0) g.fill();
  });
}
// The dots and the arrowheads of the lines of a sequence with a current step: dark for an
// earlier step, faint for a later step (`stepState` in `atlas_sequences`).
var DONE_W = 1.6;
function stepEnds(g, m, list, L, alpha, a, ox, oy, s, w, r) {
  list.forEach(function (e) {
    var st = stepState(m, e.f.i), p = e.q, n = p.length, z = [ox + a * p[n - 1][0], oy + a * p[n - 1][1]], y = [ox + a * p[n - 2][0], oy + a * p[n - 2][1]];
    g.beginPath(); arrowHead(g, z, y, s, w);
    g.moveTo(ox + a * p[0][0] + r, oy + a * p[0][1]); g.arc(ox + a * p[0][0], oy + a * p[0][1], r, 0, 2 * Math.PI);
    g.fillStyle = st === 'was' ? C['--ink-2'] : C['--ink-3']; g.globalAlpha = alpha * L.ends * (st === 'later' ? LATER_A : 1); g.fill();
    if (DLOG) logged({t: 'ends', f: e.f.i, dot: [ox + a * p[0][0], oy + a * p[0][1], r], tip: z, from: y, s: s, w: w, step: st, color: g.fillStyle, alpha: g.globalAlpha});
  });
}
// The labels at rest (`seatsOf`), with a constant size on the screen. A label has a halo
// in the color of the ground.
// While a light is on the map, the labels of the lines that go back fade out, and the
// labels of the lit lines draw with the lit lines (`drawLitLabels`).
function drawLabels(m, id, a, ox, oy, alpha) {
  var fs = q(labelPx(a)), lit = litOf(m);
  if (fs < textMin() || alpha <= 0.02) return;
  var seats = seatsOf(m, id, a);
  if (!seats) return;
  ctx.font = font(500, fs); ctx.textAlign = 'center'; ctx.lineJoin = 'round'; ctx.setLineDash([]);
  var steps = stepping(m);
  seats.list.forEach(function (s) {
    var st = steps ? stepState(m, s.e.f.i) : '', x = ox + a * s.x, y = oy + a * s.y + fs * 0.34;
    var la = alpha * (lit && lit.focus && !lit.step ? 1 - DIM : 1) * (st === 'later' ? LATER_A : 1);
    if (x < -200 || x > W + 200 || y < -20 || y > H + 20 || la <= 0.02) return;
    ctx.globalAlpha = la; ctx.strokeStyle = C['--map']; ctx.lineWidth = 5; ctx.strokeText(s.e.s, x, y);
    if (DLOG) logged({t: 'label', f: s.e.f.i, s: s.e.s, x: x, y: y, alpha: la, step: st});
    text(s.e.s, x, y, fs, C['--ink-2'], la, 500, false, 'center');
  });
}

// ---- cards -----------------------------------------------------------------------
// The corner radius of a card: round ends for an actor, else 9 units of the map.
function cardCorner(c, w, h) { return c.k === 'actor' ? h / 2 : w > 30 ? Math.min(9 * h / c.b[3], h / 2) : 0; }
// The box of a card into the batches. `qv` is its quiet value (`quietOf`).
function cardBox(c, x, y, w, h, alpha, qv) {
  STATS.cards++;
  var lit = litOf(c.map), ink = lit || c === SEL || HOT.c === c ? inkCard(c) : false;
  alpha *= backCard(lit, c);
  if (ink) qv = 0;
  var t = cardShow(h), actor = c.k === 'actor', r = cardCorner(c, w, h), live = 1 - qv;
  if (DLOG) logged({t: 'card', id: c.id, k: c.k, b: [x, y, w, h], r: r, shape: t, under: !!c.child && t > 0, map: c.map.id, alpha: alpha});
  if (t < 1) MARK.rect(C['--line-2'], alpha * (1 - t) * (0.6 - 0.3 * qv), x, y, w, h, 0);
  if (t <= 0) return;
  if (c.child) {
    UNDER.rect(C['--card'], alpha * t * live, x + 4 * h / c.b[3], y + 4 * h / c.b[3], w, h, r);
    UNDER_LINE.rect(C['--line-2'], alpha * t * live, x + 4 * h / c.b[3], y + 4 * h / c.b[3], w, h, r, 1);
  }
  FILL.rect(actor ? C['--map'] : C['--card'], alpha * t * (actor ? 1 : live), x, y, w, h, r);
  LINE.rect(ink ? C['--ink'] : actor && !qv ? C['--ink-3'] : C['--line-2'], alpha * t * (1 - 0.3 * qv), x, y, w, h, r, 1);
}
// The text of a card: the name, the short name below it at a scale of 0.95 or more, and
// the tag of the kind. The sizes follow the scale `a` of the map, to a limit.
function cardText(c, x, y, w, h, alpha, qv) {
  var lit = litOf(c.map);
  if (lit || c === SEL || HOT.c === c) { alpha *= backCard(lit, c); if (inkCard(c)) qv = 0; }
  var t = alpha * cardShow(h);
  if (t <= 0.02) return;
  var a = h / c.b[3], u = Math.min(a, 1.6), actor = c.k === 'actor', pad = (actor ? 20 : 13) * u;
  // A small card keeps a name of 7.5 px or more while the card is high enough for it.
  var ns = q(Math.max(13.5 * u, Math.min(7.5, h * 0.3))), far = rest(smooth(0.9, 0.95, a)), thumb = c.child ? c.child.size[0] * c.child.T.s / c.map.T.s * a + 10 * u : 0;
  var right = w - pad - 8 * u - thumb;
  if (c.k !== 'actor' && c.k !== 'component') {
    var ks = q(8.5 * u), kw = (unitWidth(c.k.toUpperCase(), 500, true) + 0.09 * c.k.length) * ks;
    caps(c.k, x + w - 9 * u - thumb - kw, y + 14 * u, ks, C['--ink-3'], t * (1 - 0.5 * qv), 0.09);
  }
  var mid = y + h / 2, base = mid - 1.5 * u + (1 - far * (1 - qv)) * 6 * u;
  text(fit(c.id, ns, right, 600), x + pad, base, ns, qv > 0.5 ? C['--ink-3'] : C['--ink'], t * (1 - 0.4 * qv), qv > 0.5 ? 500 : 600);
  if (c.p && far > 0) text(fit(c.p, q(10 * u), right, 400), x + pad, mid + 13 * u, q(10 * u), C['--ink-3'], t * far * (1 - qv) * (1 - HIDE));
}
// A weight that follows the zoom: the value while the camera moves, and 0 or 1 in the full
// drawing at rest. Thus a text at rest is not partly transparent.
function rest(v) { return sharp && ctx === PAGE_CTX ? (v < 0.5 ? 0 : 1) : v; }

// ---- a map --------------------------------------------------------------------
// How far the nested map of card c takes the screen: 0 when it is a small picture in its
// card, and 1 when it has the screen: its frame is 75 % of the width or of the height of the
// screen, or the zoom is 90 % of the zoom of its fit. The camera is in the nested map from 0.5.
function deepOf(c) {
  if (!c.child) return 0;
  var f = frameOf(c.child), cx = (f[0] + f[2] / 2 - cam.x) * cam.k, cy = (f[1] + f[3] / 2 - cam.y) * cam.k;
  var seen = cx + f[2] * cam.k / 2 > 0 && cx - f[2] * cam.k / 2 < W && cy + f[3] * cam.k / 2 > HEAD_H && cy - f[3] * cam.k / 2 < H;
  if (!seen) return 0;
  // A small nested map has a fit with a scale of 1.6 that does not fill the screen. At 90 %
  // of the zoom of its fit or more, it also has the screen.
  var fitK = c._fit && c._fit.w === W && c._fit.h === H ? c._fit.k : (c._fit = {w: W, h: H, k: mapFit(f, true).k}).k;
  return smooth(0.3, 0.75, Math.max(f[2] * cam.k / W, f[3] * cam.k / Math.max(1, H - HEAD_H), 0.84 * cam.k / fitK));
}
function openness(c) { return deepOf(c); }
function drawMap(m, alpha, open) {
  if (alpha <= 0.01) return;
  var v = view(m), a = v.a, ox = v.ox, oy = v.oy, mw = m.size[0] * a, mh = m.size[1] * a;
  if (ox > W || oy > H || ox + mw < 0 || oy + mh < 0) return;
  var x0 = -ox / a, y0 = -oy / a, x1 = (W - ox) / a, y1 = (H - oy) / a;
  var cards = m.cardIndex.query(x0, y0, x1, y1, []), hosts = [], deep = 0;
  cards.forEach(function (c) { if (c.child) { var d = deepOf(c); c._deep = d; hosts.push(c); deep = Math.max(deep, d); } });
  var own = alpha * (1 - deep), id = shownLayer(m), L = linesOf(m, id);
  logged({t: 'map', id: m.id, own: own, a: a, b: [ox, oy, mw, mh]});
  var big = m.cards.length >= BIG, marks = big && m.maxH * a < NAME_H && m.maxW * a < PREVIEW0;
  var near = !marks || (zoomingIn() && m.maxH * a >= NAME_H * Math.pow(2, -MARKS_OVER * MAP_STEP));
  var whole = big ? imageLayer(m, a, !sharp && !LIGHT_MOVE && open >= 1, near) : null, full = whole && layerFull(whole);
  if (marks && own > 0.01 && !litOf(m)) {
    var img = marksImage(m, a);
    if (full) img = null;
    if (img || full) {
      if (img) { ctx.globalAlpha = own; ctx.drawImage(img.canvas, ox, oy, mw, mh); STATS.image++; }
      if (whole) drawLayer(whole, ox, oy, mw, mh, own);
      STATS.cards += m.cards.length;
      hosts.forEach(function (c) { drawMap(c.child, alpha, c._deep); });
      return;
    }
  }
  if (full) { drawLayer(whole, ox, oy, mw, mh, own); STATS.cards += cards.length; return; }
  OPEN = open >= 0.5;
  if (own > 0.01) {
    var flowA = own * SWAP_A * smooth(0.1, 0.25, open);
    drawBoxes(ctx, m, a, ox, oy, own, true, open);
    var fl = layerFlags(m, id).flow, list = [];
    m.flowIndex.query(x0, y0, x1, y1, []).forEach(function (f) { if (fl[f.i]) list.push(f); });
    var byFlow = L._by || (L._by = (function () { var o = []; L.list.forEach(function (e) { o[e.f.i] = e; }); return o; })());
    drawLines(ctx, m, list.map(function (f) { return byFlow[f.i]; }).filter(Boolean), L, a, ox, oy, flowA);
    drawLit(m, L, a, ox, oy, flowA);
    if (open > 0.3) drawLitLabels(m, id, a, ox, oy, flowA * smooth(0.3, 0.8, open), true);
    var texts = [];
    for (var i = 0; i < cards.length; i++) {
      var c = cards[i], b = c.b, x = ox + a * b[0], y = oy + a * b[1], w = a * b[2], h = a * b[3];
      if (x > W || y > H || x + w < 0 || y + h < 0) continue;
      var qv = quietOf(c);
      cardBox(c, x, y, w, h, own, qv);
      if (hasText(h)) texts.push([c, x, y, w, h, qv]);
    }
    flushCards(ctx);
    drawSelected(m, a, ox, oy, own);
    if (open > 0.3 && !L.dense) drawLabels(m, id, a, ox, oy, flowA * smooth(0.3, 0.8, open));
    if (open > 0.3) drawLitLabels(m, id, a, ox, oy, flowA * smooth(0.3, 0.8, open), false);
    texts.forEach(function (e) { cardText(e[0], e[1], e[2], e[3], e[4], own, e[5]); });
    if (whole) drawLayer(whole, ox, oy, mw, mh, own);
  }
  OPEN = false;
  hosts.forEach(function (c) { if (c.child.size[0] * c.child.T.s * cam.k >= 8) drawMap(c.child, alpha, c._deep); });
}
// The chain: the cards whose nested map has the screen, from the top map down.
function focusChain() {
  var chain = [], m = TOP;
  for (var d = 0; d <= DEEPEST; d++) {
    var found = null;
    m.cards.forEach(function (c) { if (!found && c.child && deepOf(c) > 0.5) found = c; });
    if (!found) break;
    chain.push(found); m = found.child;
  }
  return chain;
}
function boxOnScreen(r) { return r[0] + r[2] > 0 && r[1] + r[3] > HEAD_H && r[0] < W && r[1] < H; }
"""
