"""The drawing part of the canvas renderer: maps, cards, flows, rings, portals and the path.

`page_canvas` joins this part after the scene part (`page_canvas_scene`). The part
follows the rules of the section "Performance" of docs/design/nested-canvas.md:

- It paints with the 2D API of a `<canvas>` element. It makes no SVG element.
- It draws only the cards and the flows that the box index of a map gives for the screen.
- It puts the boxes of one style in one path (`Batch`), and it draws no text below 7 px.
- It draws a large map from images of that map (`page_canvas_image`).

Level of detail. The screen size of a card selects what the card shows: a mark in its
layer color, then the name, then the card text, the description and the fact row, and
then the lists of flows and modules. Each step fades in as the card grows. A card that
opens a map shows the preview of that map in the same positions. Between OPEN0 and
OPEN1 of the screen width, the card changes into the frame of the map.

Rings and portals. They come from the camera at each frame. A ring is the frame of an
open map that is larger than the screen. A portal is a neighbour of an open map that is
not on the screen. Each neighbour has one portal. For each direction, the deepest map
that has a port to the neighbour gives the boundary flow, and the flow is drawn one time,
from the portal. That line has right angles. It goes from the actor card of the nested
flow (`fp` of the port in the canvas data) to the port on the frame of the open card,
around the frame, and to the portal. It crosses no card and no text, and it stays on the
screen. It crosses no portal that has a `show` of HARD or more. A portal with a smaller
`show` only makes the line fade. When no such line is possible, the portal has no line.
The line fades in and out with the camera (`page_canvas_fade`).

A portal is in a band at the screen edge, and the camera fit keeps the cards of a map out
of these bands. On a narrow screen, a portal is at the top or the bottom only. Portals on
the same edge move along it as far as necessary, so that they do not cover each other.
While the camera moves, the cards can go below the portals, as they can go below the path.
"""

from __future__ import annotations

DRAW = r"""
// ---- batches of boxes ----------------------------------------------------------
var DASH = {'': [], a: [4, 3], s: [3, 4], d: [7, 5], r: [3, 3], p: [5, 4]};
function Batch(fill) { this.fill = fill; this.items = new Map(); }
Batch.prototype.rect = function (color, alpha, x, y, w, h, r, width, dash) {
  if (!color || color === 'none' || alpha <= 0.02) return;
  var al = Math.round(alpha * 16) / 16, key = color + '|' + al + '|' + (width || 1) + '|' + (dash || '');
  var e = this.items.get(key);
  if (!e) { e = {color: color, alpha: al, width: width || 1, dash: dash || '', list: []}; this.items.set(key, e); }
  e.list.push(x, y, w, h, r);
};
Batch.prototype.flush = function (g) {
  var fill = this.fill;
  this.items.forEach(function (e) {
    var l = e.list;
    g.globalAlpha = e.alpha; g.beginPath();
    for (var i = 0; i < l.length; i += 5) rr(g, l[i], l[i + 1], l[i + 2], l[i + 3], l[i + 4]);
    if (fill) { g.fillStyle = e.color; g.fill(); }
    else { g.strokeStyle = e.color; g.lineWidth = e.width; g.setLineDash(DASH[e.dash]); g.stroke(); }
  });
  this.items.clear();
};
// The browser paints a long path in software, and a dashed path dash by dash. When the
// camera is deep in a map, a box of a map above it can be a million pixels wide. Thus
// each box and each route point is cut to the target, with a margin of CUT pixels.
var CUT = 8;
function bounds(g) { return g === ctx ? [W, H] : [g.canvas.width, g.canvas.height]; }
function rr(g, x, y, w, h, r) {
  var b = bounds(g), x0 = Math.max(x, -CUT), y0 = Math.max(y, -CUT), x1 = Math.min(x + w, b[0] + CUT), y1 = Math.min(y + h, b[1] + CUT);
  if (x1 <= x0 || y1 <= y0) return;
  if (r > 0.5 && g.roundRect) g.roundRect(x0, y0, x1 - x0, y1 - y0, Math.min(r, (x1 - x0) / 2, (y1 - y0) / 2));
  else g.rect(x0, y0, x1 - x0, y1 - y0);
}
// A line of segments with right angles, cut to the target. A point cut to the target
// keeps each segment on its line.
function cutLine(g, p, ox, oy, a) {
  var b = bounds(g), bx = b[0] + CUT, by = b[1] + CUT;
  g.moveTo(clamp(ox + a * p[0][0], -CUT, bx), clamp(oy + a * p[0][1], -CUT, by));
  for (var i = 1; i < p.length; i++) g.lineTo(clamp(ox + a * p[i][0], -CUT, bx), clamp(oy + a * p[i][1], -CUT, by));
}
// The arrowhead at (x2, y2) of a segment from (x1, y1).
function arrowHead(g, x2, y2, x1, y1, size) {
  var an = Math.atan2(y2 - y1, x2 - x1);
  g.moveTo(x2, y2);
  g.lineTo(x2 - size * Math.cos(an - 0.45), y2 - size * Math.sin(an - 0.45));
  g.lineTo(x2 - size * Math.cos(an + 0.45), y2 - size * Math.sin(an + 0.45));
}
var BACK = new Batch(true), FILL = new Batch(true), LINE = new Batch(false);
function flushCards(g) { BACK.flush(g); FILL.flush(g); LINE.flush(g); }
function q(size) { return Math.round(size * 2) / 2; }
// The font size of the box names and the flow labels, and if the labels show.
function labelSize(a) { return q(clamp(10.5 * a, 0, 13)); }
function hasLabels(fs, alpha) { return fs >= 8 && alpha > 0.05; }
// If a card of screen height h shows its text.
function hasText(h) { return h >= MARK_H - 4; }
function near(u, v) { return Math.abs(u - v) < 0.5; }
function colors(c) {
  if (c._c && c._c.e === EPOCH) return c._c;
  var s = c.s || 'built', actor = c.k === 'actor';
  var line = actor ? C['--card-line'] : C['--card-' + s + '-line'], mark = line;
  (c.l || []).forEach(function (l) { if (mark === line && C['--l-' + l] && l !== 'system') mark = C['--l-' + l]; });
  c._c = {e: EPOCH, fill: actor ? C['--actor'] : C['--card-' + s], line: line, mark: mark};
  return c._c;
}
// While NOTE is true, each text is also a box that a boundary flow must not cross.
var NOTE = false;
function text(s, x, y, size, color, alpha, weight, mono, align) {
  if (size < MIN_TEXT || alpha <= 0.02 || !s) return;
  ctx.globalAlpha = alpha; ctx.fillStyle = color; ctx.font = font(weight || 400, size, mono);
  ctx.textAlign = align || 'left'; ctx.fillText(s, x, y);
  if (NOTE) textBox(s, x, y, size, weight, mono, align);
}
// The box of a text, as a box that a boundary flow must not cross.
function textBox(s, x, y, size, weight, mono, align) {
  var w = unitWidth(s, weight || 400, mono) * size;
  obstacle(align === 'center' ? x - w / 2 : x, y - size, w, size * 1.3);
}

// ---- containers, regions and flows -------------------------------------------
function drawBoxes(g, m, a, ox, oy, alpha, labels) {
  if (alpha <= 0.02) return;
  var fills = new Batch(true), lines = new Batch(false), r = clamp(6 * a, 0, 6);
  m.boxes.forEach(function (b) {
    var x = ox + a * b.b[0], y = oy + a * b.b[1], w = a * b.b[2], h = a * b.b[3];
    fills.rect(C['--box-' + b.t], alpha, x, y, w, h, r);
    lines.rect(C['--box-' + b.t + '-line'], alpha, x, y, w, h, r, 1);
  });
  m.regions.forEach(function (b) {
    lines.rect(C['--region'], alpha * 0.8, ox + a * b.b[0], oy + a * b.b[1], a * b.b[2], a * b.b[3], r, 1, 'r');
  });
  fills.flush(g); lines.flush(g);
  var fs = labelSize(a);
  if (!labels || fs < MIN_TEXT) return;
  NOTE = g === ctx;
  boxNames(m, a, ox, oy, function (s, x, y, color) { text(s, x, y, fs, color, alpha, 600); });
  NOTE = false;
}
// The name of each container and region, at its screen point.
function boxNames(m, a, ox, oy, each) {
  m.boxes.forEach(function (b) { each(b.n, ox + a * (b.b[0] + 13), oy + a * (b.b[1] + 19), C['--ink-3']); });
  m.regions.forEach(function (b, i) { each((i + 1) + '  ' + b.n, ox + a * (b.b[0] + 13), oy + a * (b.b[1] + 20), C['--ink-2']); });
}
function drawFlows(g, list, a, ox, oy, alpha, arrows) {
  if (alpha <= 0.02 || !list.length) return;
  var groups = new Map(), width = clamp(1.3 * a, 0.6, 2), head = clamp(7 * a, 3, 8);
  list.forEach(function (f) {
    if (!f.p.length) return;
    var key = f.l + '|' + f.ev, e = groups.get(key);
    if (!e) { e = {color: C['--l-' + f.l] || C['--flow'], ev: f.ev, list: []}; groups.set(key, e); }
    e.list.push(f);
  });
  g.globalAlpha = alpha;
  groups.forEach(function (e) {
    g.strokeStyle = e.color; g.lineWidth = width;
    g.setLineDash(e.ev === 'structural' ? DASH.s : e.ev === 'declared' ? DASH.d : DASH['']);
    g.beginPath();
    e.list.forEach(function (f) { cutLine(g, f.p, ox, oy, a); });
    g.stroke();
    if (!arrows) return;
    g.setLineDash([]); g.fillStyle = e.color; g.beginPath();
    e.list.forEach(function (f) {
      var p = f.p, n = p.length;
      if (n > 1) arrowHead(g, ox + a * p[n - 1][0], oy + a * p[n - 1][1], ox + a * p[n - 2][0], oy + a * p[n - 2][1], head);
    });
    g.fill();
  });
}
function drawLabels(list, a, ox, oy, alpha) {
  var fs = labelSize(a);
  if (!hasLabels(fs, alpha)) return;
  // The plate fits the text. The text stops at 13 px, so a plate of the label box would
  // grow past the text and cover the routes.
  var bg = new Batch(true);
  plates(list, a, ox, oy, fs, function (px, py, pw, ph) {
    bg.rect(C['--map'], alpha * 0.9, px, py, pw, ph, 3);
    obstacle(px, py, pw, ph);
  });
  bg.flush(ctx);
  list.forEach(function (f) {
    if (!f.lb) return;
    text(f.a, ox + a * (f.lb[0] + f.lb[2] / 2), oy + a * (f.lb[1] + f.lb[3] / 2) + fs * 0.36, fs, C['--ink-2'], alpha, 500, false, 'center');
  });
}

// The screen box of the plate of each flow label with a font size of `fs`.
function plates(list, a, ox, oy, fs, each) {
  var ph = fs * 1.5;
  list.forEach(function (f) {
    if (!f.lb) return;
    var pw = unitWidth(f.a, 500) * fs + 6;
    each(ox + a * (f.lb[0] + f.lb[2] / 2) - pw / 2, oy + a * (f.lb[1] + f.lb[3] / 2) - ph / 2, pw, ph);
  });
}

// ---- cards ------------------------------------------------------------------------
function cardBox(c, x, y, w, h, alpha) {
  STATS.cards++;
  var t = smooth(MARK_H - 6, MARK_H + 6, h), k = colors(c), r = w > 60 ? clamp(h * 0.1, 2, 8) : 0;
  if (t < 1) FILL.rect(k.mark, alpha * (1 - t), x, y, w, h, 0);
  if (t <= 0) return;
  if (c.child) BACK.rect(C['--line-2'], alpha * t, x + 4, y + 4, w, h, r);
  FILL.rect(k.fill, alpha * t, x, y, w, h, r);
  LINE.rect(k.line, alpha * t, x, y, w, h, r, 1, c.k === 'actor' ? 'a' : '');
}
function title(c, x, y, w, size, alpha, extra) {
  if (size < MIN_TEXT || alpha <= 0.02) return;
  var name = fit(c.id, size, w, 600);
  text(name, x, y + size, size, C['--ink'], alpha, 600);
  if (extra && extra.alpha > 0.02) {
    var at = unitWidth(name, 600) * size + size * 0.6, small = q(size * 0.82);
    text(fit(extra.s, small, w - at, 400), x + at, y + size, small, C['--ink-3'], alpha * extra.alpha);
  }
}
// The name of each card has the same size and place, also on a card that opens a map.
// Thus the name does not move when the preview comes into view.
function titleSize(h) { return q(clamp(Math.max(Math.min(h * 0.28, 9), h * 0.12), 0, 26)); }
function inset(h) { return clamp(h * 0.1, 3, 14); }
function cardText(c, x, y, w, h, alpha) {
  var t = alpha * smooth(MARK_H - 4, MARK_H + 6, h), pad = inset(h), u = titleSize(h), top = y + Math.max(2, h * 0.06);
  if (u < MIN_TEXT || t <= 0.02) return;
  title(c, x + pad, top, w - 2 * pad, u, t);
  top += u * 1.4;
  // While the camera moves, a card with a name below MOVE_TEXT shows only its name. While
  // the name grows from MOVE_TEXT to MOVE_TEXT + 2, the text under the name fades in.
  // Text is the largest cost of a moving frame.
  details(c, x + pad, top, w - 2 * pad, y + h - pad * 0.6 - top, sharp ? t : t * smooth(MOVE_TEXT, MOVE_TEXT + 2, u), u);
}
function facts(c) {
  var n = (c.m || []).length, parts = [];
  parts.push(c.k === 'actor' ? 'actor' : n + (n === 1 ? ' module' : ' modules'));
  parts.push(c.ins.length + ' in · ' + c.outs.length + ' out');
  if (c.as) parts.push(c.as[0] + ' · ' + c.as[1]);
  return parts.join('  ·  ');
}
// The text of a card under its name: the card text, the description, the lists and
// the fact row. Each part comes into view when the box has space for it.
function details(c, x, y, w, h, alpha, u) {
  var fs = q(clamp(u * 0.78, MIN_TEXT, 19)), lh = fs * 1.38, small = q(clamp(u * 0.66, MIN_TEXT, 15));
  if (h < lh * 0.9 || w < 30 || alpha <= 0.02) return;
  var bottom = y + h, rows = Math.floor(h / lh), factRow = rows >= 3 && w > 90;
  if (factRow) bottom -= small * 1.7;
  var at = y;
  at = lines(wrap(c, 'p', c.p, fs, w, clamp(Math.floor((bottom - at) / lh), 0, 2), 400), x, at, fs, lh, C['--ink-2'], alpha);
  var room = Math.floor((bottom - at) / lh), large = room >= 7 && w >= 150;
  if (c.d && room >= 2) {
    var shown = alpha * smooth(1.5, 2.5, (bottom - at) / lh);
    at = lines(wrap(c, 'd', c.d, fs, w, large ? Math.min(4, room - 4) : room, 400), x, at + lh * 0.3, fs, lh, C['--ink-3'], shown);
  }
  if (large) lists(c, x, at + lh * 0.5, w, bottom - at - lh * 0.5, fs, small, lh, alpha * smooth(7, 9, room));
  if (factRow) text(fit(facts(c), small, w, 400), x, y + h - small * 0.3, small, C['--ink-3'], alpha * smooth(2.5, 3.5, rows));
}
function lines(list, x, y, fs, lh, color, alpha) {
  for (var i = 0; i < list.length; i++) text(list[i], x, y + fs + i * lh, fs, color, alpha);
  return y + list.length * lh;
}
function lists(c, x, y, w, h, fs, small, lh, alpha) {
  if (alpha <= 0.02) return;
  var flows = c.outs.map(function (f) { return 'to ' + f.t + ' · ' + f.a; })
    .concat(c.ins.map(function (f) { return 'from ' + f.s + ' · ' + f.a; }));
  var mods = (c.m || []).concat(c.u || []), two = w >= 320, cw = two ? (w - fs) / 2 : w;
  var rows = Math.floor(h / lh);
  if (two) {
    list('FLOWS', flows, x, y, cw, rows, false);
    list('MODULES', mods, x + cw + fs, y, cw, rows, true);
    return;
  }
  var first = Math.min(rows, Math.max(2, Math.ceil(rows / 2)));
  list('FLOWS', flows, x, y, cw, first, false);
  list('MODULES', mods, x, y + first * lh, cw, rows - first, true);
  function list(name, items, lx, ly, lw, n, mono) {
    if (n < 2) return;
    text(name, lx, ly + small, small, C['--ink-3'], alpha, 600);
    if (!items.length) { text('none', lx, ly + small + lh, fs, C['--ink-3'], alpha); return; }
    var fitN = items.length <= n - 1 ? items.length : n - 2;
    for (var i = 0; i < fitN; i++) text(fit(items[i], fs, lw, 400, mono), lx, ly + small + (i + 1) * lh, fs, C['--ink-2'], alpha, 400, mono);
    if (fitN < items.length) text('+ ' + (items.length - fitN) + ' more', lx, ly + small + (fitN + 1) * lh, fs, C['--ink-3'], alpha);
  }
}

// ---- a card that opens a map -----------------------------------------------------
function drawOpening(c, a, ox, oy, alpha) {
  var x = ox + a * c.b[0], y = oy + a * c.b[1], w = a * c.b[2], h = a * c.b[3];
  if (x > W || y > H || x + w < 0 || y + h < 0) return;
  STATS.cards++;
  var o = openness(c), pv = smooth(PREVIEW0, PREVIEW1, w), k = colors(c), r = clamp(h * 0.06, 2, 10), g = ctx;
  g.setLineDash([]);
  if (o < 1) { g.globalAlpha = alpha * (1 - o); g.fillStyle = C['--line-2']; g.beginPath(); rr(g, x + 4, y + 4, w, h, r); g.fill(); }
  g.beginPath(); rr(g, x, y, w, h, r);
  g.globalAlpha = alpha; g.fillStyle = C['--map']; g.fill();
  if (o < 1) { g.globalAlpha = alpha * (1 - o); g.fillStyle = k.fill; g.fill(); }
  g.globalAlpha = alpha; g.strokeStyle = o > 0.5 ? C['--ink-3'] : k.line; g.lineWidth = 1 + 0.4 * o; g.stroke();
  var u = titleSize(h), pad = inset(h), n = c.child.cards.length;
  var more = {s: n + (n === 1 ? ' card' : ' cards') + ' in this map', alpha: o};
  // A boundary flow can go through an open card, but not through its text.
  NOTE = CHAIN.indexOf(c) >= 0;
  if (!NOTE) obstacle(x, y, w, h);
  title(c, x + pad, y + Math.max(2, h * 0.06), w - 2 * pad, u, alpha, more);
  if (c.side) {
    var s = c.side;
    details(c, ox + a * s[0], oy + a * s[1], a * s[2], a * s[3], alpha * (1 - 0.4 * o), u);
  }
  NOTE = false;
  drawMap(c.child, alpha * pv, o);
}

// ---- a map --------------------------------------------------------------------
function drawMap(m, alpha, open) {
  if (alpha <= 0.01) return;
  var v = view(m), a = v.a, ox = v.ox, oy = v.oy, mw = m.size[0] * a, mh = m.size[1] * a;
  if (ox > W || oy > H || ox + mw < 0 || oy + mh < 0) return;
  var big = m.cards.length >= BIG, marks = big && m.maxH * a < MARK_H - 6 && m.maxW * a < PREVIEW0;
  // Also ask for the map image in a frame of marks, which has free time to make it.
  var whole = big && !sharp && open >= 1 ? mapImage(m, a) : null;
  if (marks) {
    var img = marksImage(m, a);
    if (img) {
      ctx.globalAlpha = alpha; ctx.drawImage(img.canvas, ox, oy, mw, mh); STATS.image++; STATS.cards += m.cards.length;
      obstacle(ox, oy, mw, mh);
      return;
    }
  }
  var x0 = -ox / a, y0 = -oy / a, x1 = (W - ox) / a, y1 = (H - oy) / a;
  if (whole) {
    ctx.globalAlpha = alpha; ctx.drawImage(whole.lo.canvas, ox, oy, mw, mh);
    ctx.globalAlpha = alpha * whole.t; ctx.drawImage(whole.hi.canvas, ox, oy, mw, mh);
    STATS.image += 2; STATS.cards += mapObstacles(m, a, ox, oy, [x0, y0, x1, y1], alpha); return;
  }
  drawBoxes(ctx, m, a, ox, oy, alpha * (0.4 + 0.6 * open), open > 0.5);
  var flows = m.flowIndex.query(x0, y0, x1, y1, []);
  drawFlows(ctx, flows, a, ox, oy, alpha * (0.35 + 0.65 * open), m.maxH * a > 14);
  var cards = m.cardIndex.query(x0, y0, x1, y1, []), opening = [], texts = [];
  for (var i = 0; i < cards.length; i++) {
    var c = cards[i], b = c.b, x = ox + a * b[0], y = oy + a * b[1], w = a * b[2], h = a * b[3];
    if (x > W || y > H || x + w < 0 || y + h < 0) continue;
    if (c.child && w >= PREVIEW0) { opening.push(c); continue; }
    cardBox(c, x, y, w, h, alpha);
    obstacle(x, y, w, h);
    if (hasText(h)) texts.push(c);
  }
  flushCards(ctx);
  if (open > 0.3) drawLabels(flows, a, ox, oy, alpha * smooth(0.3, 0.8, open));
  texts.forEach(function (c) { cardText(c, ox + a * c.b[0], oy + a * c.b[1], a * c.b[2], a * c.b[3], alpha); });
  opening.forEach(function (c) { drawOpening(c, a, ox, oy, alpha); });
}

// ---- depth: the chain, rings and portals --------------------------------------
// The chain: the open cards around the middle of the screen, from the top map down.
function focusChain() {
  var chain = [], m = TOP, cx = W / 2, cy = H / 2;
  for (var d = 0; d <= DEEPEST; d++) {
    var v = view(m), lx = (cx - v.ox) / v.a, ly = (cy - v.oy) / v.a, near = m.cardIndex.query(lx, ly, lx, ly, []), found = null;
    for (var i = 0; i < near.length && !found; i++) {
      var c = near[i], b = c.b;
      if (c.child && lx >= b[0] && lx <= b[0] + b[2] && ly >= b[1] && ly <= b[1] + b[3] && openness(c) > 0.6) found = c;
    }
    if (!found) break;
    chain.push(found); m = found.child;
  }
  return chain;
}
// The edges x0, y0, x1, y1 of the screen box r, cut to `inset` pixels from the screen edge.
function onScreenEdges(r, inset) {
  return [Math.max(r[0], inset), Math.max(r[1], inset), Math.min(r[0] + r[2], W - inset), Math.min(r[1] + r[3], H - inset)];
}
function drawRings(chain) {
  ctx.setLineDash([]);
  chain.forEach(function (c, i) {
    var r = screenBox(c), over = Math.max(-r[0], -r[1], r[0] + r[2] - W, r[1] + r[3] - H), al = smooth(0, 120, over);
    if (al <= 0.01) return;
    var e = onScreenEdges(r, 6 + (chain.length - 1 - i) * 6);
    if (e[2] <= e[0] || e[3] <= e[1]) return;
    ctx.globalAlpha = al * (0.3 + 0.5 * (i + 1) / chain.length); ctx.strokeStyle = C['--ink-3']; ctx.lineWidth = 1.2;
    ctx.beginPath(); rr(ctx, e[0], e[1], e[2] - e[0], e[3] - e[1], 14); ctx.stroke();
  });
}
// A neighbour is a card of the map of an open card, or of a map above it. A card that is
// not an actor comes first: an actor in a nested map stands for a card of a map above.
function neighbour(chain, i, id) {
  var first = null;
  for (var j = i; j >= 0; j--) {
    var c = chain[j].map.byId[id];
    if (!c || c === chain[j]) continue;
    if (c.k !== 'actor') return c;
    first = first || c;
  }
  return first;
}
// One portal for each neighbour card. A portal has one boundary flow for each direction
// of a port to that neighbour. The deepest map that has a port in that direction gives it.
// A port of a map above that gave a visible flow in the last frames stays as a `spare`
// line of its portal, so that its flow fades out (`fadeOf`).
function portalsOf(chain) {
  var out = [], seen = {}, at = new Map();
  for (var i = chain.length - 1; i >= 0; i--) {
    var m = chain[i].child;
    (m.ports || []).forEach(function (p) {
      var key = p.x + '|' + p.d;
      if (seen[key] && !FADE.size) return;
      var nb = neighbour(chain, i, p.x);
      if (!nb) return;
      if (seen[key]) {
        var s = at.get(nb);
        if (s && FADE.has(lineKey(nb, p, m))) s.lines.push({p: p, m: m, open: chain[i], spare: true});
        return;
      }
      seen[key] = true;
      var t = at.get(nb);
      if (!t) {
        var r = screenBox(nb), mg = 30, off = Math.max(mg - (r[0] + r[2]), mg - (r[1] + r[3]), r[0] - (W - mg), r[1] - (H - mg));
        var show = smooth(0, 160, off);
        if (show <= 0.01) return;
        var where = whereOf(nb.map);
        t = portalPlace({nb: nb, show: show, where: where, h: P_H, w: portalWidth(nb.id, where), lines: []}, r, screenBox(sibling(chain, nb)));
        at.set(nb, t); out.push(t);
      }
      t.lines.push({p: p, m: m, open: chain[i]});
    });
  }
  return apart(out);
}
// The open card in the map of a neighbour.
function sibling(chain, nb) {
  for (var j = 0; j < chain.length; j++) if (chain[j].map === nb.map) return chain[j];
  return chain[0];
}
// The second line of a portal: the map of the neighbour.
function whereOf(m) { return 'in ' + (m.id ? m.id.split('/').pop() : DATA.name); }
// The portals are in a band at each screen edge. The camera fit keeps the cards of a map
// out of these bands (`gutters`, `fitBox`). Thus a portal does not cover a card of the
// open map. P_TOP and P_BOTTOM are the middle of a portal at the top and at the bottom
// (P_BOTTOM when the help line has one line, `bottomRow`).
var P_H = 34, P_EDGE = 20, P_GAP = 6, P_TOP = 84, P_BOTTOM = 52, P_MAX = 150, P_WIDEST = 0;
function portalSpan(idUnit, whereUnit) { return Math.min(Math.max(idUnit * 12, whereUnit * 10.5) + 30, P_MAX); }
function portalWidth(id, where) { return portalSpan(unitWidth(id, 600), unitWidth(where, 400)); }
// The largest portal width of the data. It is the width of the bands at the left and the
// right. A portal width increases with the two texts, thus the widest texts give it.
function portalWidest() {
  if (P_WIDEST) return P_WIDEST;
  var id = 0, where = 0;
  ORDER.forEach(function (m) {
    where = Math.max(where, unitWidth(whereOf(m), 400));
    (m.ports || []).forEach(function (p) { id = Math.max(id, unitWidth(p.x, 600)); });
  });
  P_WIDEST = portalSpan(id, where) || 1;
  return P_WIDEST;
}
// The screen bands that the camera fit keeps free: at the left and the right, at the top
// (the path and the portals) and at the bottom (the portals and the help line). The side
// bands are there only when the widest portal fits in 12 % of the screen width. On a narrow
// screen, each portal is in the top or the bottom row. Then the side bands are 0, and the
// open map can use all the width (`fitBox` keeps a small margin).
function gutters() {
  var side = P_EDGE + portalWidest() + P_GAP;
  return {x: side <= 0.12 * W ? side : 0, top: P_TOP + P_H / 2 + P_GAP, bottom: bottomRow() + P_H / 2 + P_GAP};
}
// The middle of a portal in the bottom row, from the screen bottom. When the help line
// wraps, the row moves up by the height of each added line.
function bottomRow() { return P_BOTTOM + HELP_LH * (helpLines().length - 1); }
// The place of a portal: the middle of its neighbour, moved into the screen. A portal that
// touches the left or the right band is on that side (`side` -1 or 1). Else it is at the
// top or the bottom (`side` 0). When a portal is wider than the side band (on a narrow
// screen), it is at the top or the bottom. Then the row is the top row if the neighbour is
// above the middle of the open card `o` in its map. A camera move does not change this.
// `along` is the place along the edge before the portals move apart. Its order does not
// change while the camera moves, thus the stacks below do not jump.
function portalPlace(t, r, o) {
  var cx = r[0] + r[2] / 2, cy = r[1] + r[3] / 2, x0 = P_EDGE + t.w / 2, x1 = W - P_EDGE - t.w / 2;
  var band = gutters().x >= P_EDGE + t.w + P_GAP, bottom = Math.max(P_TOP, H - bottomRow());
  t.x = clamp(cx, x0, x1); t.y = clamp(cy, P_TOP, bottom);
  t.side = !band ? 0 : cx <= x0 ? -1 : cx >= x1 ? 1 : 0;
  if (!band) t.y = cy < o[1] + o[3] / 2 ? P_TOP : bottom;
  t.along = t.side ? cy : cx;
  return t;
}
function order(a, b) { return a < b ? -1 : a > b ? 1 : 0; }
// Portals on the same edge must not cover each other. Each one moves along its edge only
// as far as necessary. A portal that comes into view pushes the others gradually (`show`).
function apart(list) {
  list.sort(function (a, b) { return a.along - b.along || order(a.nb.id, b.nb.id) || order(a.where, b.where); });
  var low = H - bottomRow();
  [-1, 1].forEach(function (side) {
    stack(list.filter(function (t) { return t.side === side; }), 'y', function () { return P_H + P_GAP; }, P_TOP, low);
  });
  [P_TOP, Math.max(P_TOP, low)].forEach(function (row) {
    var line = list.filter(function (t) { return !t.side && t.y === row; }), ends = rowEnds(list, row);
    stack(line, 'x', function (a, b) { return (a.w + b.w) / 2 + P_GAP; }, ends[0], ends[1]);
  });
  return list;
}
// The part of the gap that two portals keep. It is full when `show` of the newer portal is
// 0.3 or more. Thus only a portal with a small `show` can cover a part of a different portal.
function kept(a, b) { return smooth(0, 0.3, Math.min(a.show, b.show)); }
// Push each portal after the one before it.
function push(line, key, gap) {
  for (var i = 1; i < line.length; i++) {
    line[i][key] = Math.max(line[i][key], line[i - 1][key] + gap(line[i - 1], line[i]) * kept(line[i - 1], line[i]));
  }
}
// Push each portal after the one before it, then move the stack back from the far end.
// The limit at the start can push two portals into one place. Thus push them one more time.
function stack(line, key, gap, lo, hi) {
  push(line, key, gap);
  for (var i = line.length - 1; i >= 0; i--) {
    var size = key === 'x' ? line[i].w / 2 : 0, end = i === line.length - 1 ? hi - size : line[i + 1][key] - gap(line[i], line[i + 1]) * kept(line[i], line[i + 1]);
    line[i][key] = Math.max(Math.min(line[i][key], end), lo + size);
  }
  push(line, key, gap);
}
// The free part of a top or a bottom row. A side portal near the row takes its corner.
// The corner becomes free gradually while that portal moves away from the row.
function rowEnds(list, row) {
  var lo = P_EDGE, hi = W - P_EDGE;
  list.forEach(function (s) {
    if (!s.side) return;
    var keep = (1 - smooth(P_H + P_GAP, 2 * (P_H + P_GAP), Math.abs(s.y - row))) * s.show, w = (s.w + P_GAP) * keep;
    if (s.side < 0) lo = Math.max(lo, P_EDGE + w); else hi = Math.min(hi, W - P_EDGE - w);
  });
  return [lo, hi];
}

// ---- boundary flows ---------------------------------------------------------------
// The screen boxes that a boundary flow must not cross, as x0, y0, x1, y1, a weight and the
// box in the frame before: each card that a frame draws, the text of each open card, each
// flow label, each portal, the path and the help line. The weight is 1, but the weight of a
// portal is its `show`. A box with a weight of less than HARD does not stop a path. It only
// makes the fade value of a path near it less (`boxCap`). Thus a portal that comes into
// view pushes a line away gradually. A box that moves with the camera has no box `was`:
// `before` gives it. A portal, the path and the help line give it. The array is used again
// in each frame, so its size does not grow.
var OBST = [], NOBST = 0, HARD = 0.5, OB = 10;
function obstacle(x, y, w, h, weight, was) {
  if (w <= 0 || h <= 0 || x > W || y > H || x + w < 0 || y + h < 0) return;
  OBST[NOBST++] = x; OBST[NOBST++] = y; OBST[NOBST++] = x + w; OBST[NOBST++] = y + h;
  OBST[NOBST++] = weight === undefined ? 1 : weight; OBST[NOBST++] = was ? 0 : 1;
  for (var k = 0; k < 4; k++) OBST[NOBST++] = was ? was[k] : 0;
}
// Tell if a segment with a right angle goes into no box. A segment can touch a box.
function clear(p, q) {
  for (var i = 0; i < NOBST; i += OB) if (OBST[i + 4] >= HARD && into(p, q, OBST, i)) return false;
  return true;
}
// Tell if the segment goes into the box x0, y0, x1, y1 at index i of b, by more than 1 pixel.
// It is the same test as `gap(p, q, ...) < 0` (page_canvas_fade). This form is faster.
function into(p, q, b, i) {
  i = i || 0;
  return Math.min(p[0], q[0]) < b[i + 2] - 1 && Math.max(p[0], q[0]) > b[i] + 1 &&
    Math.min(p[1], q[1]) < b[i + 3] - 1 && Math.max(p[1], q[1]) > b[i + 1] + 1;
}
function onScreen(p) { return p[0] >= 1 && p[0] <= W - 1 && p[1] >= 1 && p[1] <= H - 1; }
// The sides of a box x0, y0, x1, y1 in clockwise order: 0 top, 1 right, 2 bottom, 3 left.
// A point on side `side`, as near to (x, y) as possible.
function onSide(e, side, x, y) {
  return side % 2 ? [e[side === 1 ? 2 : 0], clamp(y, e[1], e[3])] : [clamp(x, e[0], e[2]), e[side === 0 ? 1 : 3]];
}
// The corner after side `i` in clockwise order.
function cornerOf(e, i) { return [i < 2 ? e[2] : e[0], i === 1 || i === 2 ? e[3] : e[1]]; }
// Remove each point that is on the line of the points before and after it.
function straight(p) {
  var out = [p[0]];
  for (var i = 1; i < p.length; i++) {
    var b = p[i], a = out[out.length - 1], z = out[out.length - 2];
    if (near(a[0], b[0]) && near(a[1], b[1])) continue;
    if (z && ((near(z[0], a[0]) && near(a[0], b[0])) || (near(z[1], a[1]) && near(a[1], b[1])))) out.pop();
    out.push(b);
  }
  return out;
}
// The last two segments to the edge of a portal box pr: across, then up or down (or the
// opposite order). When the point is in the range of the portal, there is one segment only.
// Else the second segment goes to the near corner of the portal, and it moves to the middle
// of the edge while the point moves away from the range (`slide`). Thus the path does not
// jump when the point goes out of the range. Give the length of the one segment, or
// Infinity: when that length goes to 0, the gutter goes into the portal.
function slide(lo, hi, v, out) { return v < (lo + hi) / 2 ? lo + Math.min(out, (hi - lo) / 2) : hi - Math.min(out, (hi - lo) / 2); }
function legs(pts, q, pr, across) {
  var cx = (pr[0] + pr[2]) / 2, cy = (pr[1] + pr[3]) / 2;
  var outX = Math.max(pr[0] - q[0], q[0] - pr[2], 0), outY = Math.max(pr[1] - q[1], q[1] - pr[3], 0), x, y;
  if (across && !outY) { x = q[0] < cx ? pr[0] : pr[2]; pts.push([x, q[1]]); return Math.abs(x - q[0]); }
  if (!across && !outX) { y = q[1] < cy ? pr[1] : pr[3]; pts.push([q[0], y]); return Math.abs(y - q[1]); }
  if (across) { x = slide(pr[0], pr[2], q[0], outY); pts.push([x, q[1]], [x, q[1] < cy ? pr[1] : pr[3]]); }
  else { y = slide(pr[1], pr[3], q[1], outX); pts.push([q[0], y], [q[0] < cx ? pr[0] : pr[2], y]); }
  return Infinity;
}
// One possible path from the gutter point `from` on side s: around the frame (at the
// gutter `e`) in the direction `step` to side `side`, and then to the portal. Give null
// when a point is not on the screen, or when a segment goes into `f` or into a box.
function aroundTo(a, from, f, e, s, side, step, pr, across) {
  var pts = [a, from], k = s, n = 0;
  while (k !== side && n++ < 4) { pts.push(cornerOf(e, step > 0 ? k : (k + 3) % 4)); k = (k + step + 4) % 4; }
  var q = onSide(e, side, (pr[0] + pr[2]) / 2, (pr[1] + pr[3]) / 2);
  pts.push(q);
  var leg = legs(pts, q, pr, across);
  pts = straight(pts);
  pts.leg = leg;
  for (var i = 1; i < pts.length; i++) {
    if (!onScreen(pts[i]) || (i > 1 && (!clear(pts[i - 1], pts[i]) || into(pts[i - 1], pts[i], f)))) return null;
  }
  return pts;
}
// The length of a path, with 24 pixels more for each bend.
function pathCost(p) {
  var l = 24 * (p.length - 2);
  for (var j = 1; j < p.length; j++) l += Math.abs(p[j][0] - p[j - 1][0]) + Math.abs(p[j][1] - p[j - 1][1]);
  return l;
}
// The boundary flow of one port, in screen points. The route of the nested flow in the
// map goes from the actor card to the internal card, and drawFlows draws it. This path
// goes from the actor card along `fp` to the frame of the open card (the port), and out to
// GUTTER pixels from the frame. Then it goes around the frame, at that distance, and to the
// edge of the portal. When the frame is larger than the screen, the path goes RING pixels
// from the screen edge, on the part of the frame that has no card and no text. Each
// segment has a right angle to the next, as a route does. The
// script makes the paths on the four sides, in the two directions, and with the two orders
// of the last segments. It gives each of these 16 paths (`all`, null for a path that goes off
// the screen or into a box of OBST) and its cost, and `best`, the index of the shortest path.
// Give null when the port has no `fp`, or when the first segment is not possible.
var GUTTER = 16, RING = 4;
function boundaryPath(t, l) {
  var p = l.p, fp = p.fp;
  if (!fp || p.f === undefined) return null;
  var v = view(l.m), r = screenBox(l.open), G = GUTTER, R = RING;
  var f = onScreenEdges(r, R + 1), e = onScreenEdges([r[0] - G, r[1] - G, r[2] + 2 * G, r[3] + 2 * G], R);
  var a = [v.ox + v.a * fp[0][0], v.oy + v.a * fp[0][1]], dx = fp[1][0] - fp[0][0], dy = fp[1][1] - fp[0][1];
  var s = dy < 0 ? 0 : dx > 0 ? 1 : dy > 0 ? 2 : 3, from = onSide(e, s, a[0], a[1]);
  if (!onScreen(a) || !onScreen(from) || !clear(a, from)) return null;
  var pr = t.box, all = [], costs = [], best = -1;
  for (var side = 0; side < 4; side++) {
    for (var c = 0; c < 4; c++) {
      var pts = aroundTo(a, from, f, e, s, side, c < 2 ? 1 : -1, pr, c % 2 === 0), k = pts ? pathCost(pts) : Infinity;
      if (best < 0 ? k < Infinity : k < costs[best]) best = all.length;
      all.push(pts); costs.push(k);
    }
  }
  return {all: all, costs: costs, best: best, pr: pr, f: f, e: e, port: onSide([r[0], r[1], r[0] + r[2], r[1] + r[3]], s, a[0], a[1])};
}

function drawBoundary(t, l) {
  var key = lineKey(t.nb, l.p, l.m), b = boundaryPath(t, l), paths = fadeOf(key, b, l.spare);
  if (!paths.length) return;
  var color = C['--l-' + flowLayer(l)] || C['--flow'], most = 0;
  paths.forEach(function (one) {
    var p = one.pts.slice(), n = p.length, alpha = t.show * one.v;
    if (l.p.d === 'in') p.reverse();
    most = Math.max(most, alpha);
    LINKS.push({id: t.nb.id, d: l.p.d, points: p, key: key + '#' + one.i, alpha: alpha});
    ctx.globalAlpha = alpha * 0.9; ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.setLineDash(DASH.p);
    ctx.beginPath(); cutLine(ctx, p, 0, 0, 1); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = color; ctx.beginPath(); arrowHead(ctx, p[n - 1][0], p[n - 1][1], p[n - 2][0], p[n - 2][1], 8); ctx.fill();
  });
  // The port: a small circle on the frame of the open card.
  ctx.globalAlpha = most * 0.9; ctx.fillStyle = C['--map']; ctx.beginPath(); ctx.arc(b.port[0], b.port[1], 3.5, 0, 2 * Math.PI); ctx.fill(); ctx.stroke();
}
// The portal boxes of the frame before, for the speed of a portal (`boxCap`).
var HITS = [], LINKS = [], PLACES = new Map();
// The lines come first, so that no line goes over the text of a portal.
function drawPortals(list, chain) {
  fadeFrame();
  var path = pathParts(chain), help = helpLines();
  fixedObstacle(12, 10, path.total, 38);
  help.forEach(function (line, i) { fixedObstacle(18, helpY(i, help.length) - 12, unitWidth(line, 400) * HELP_FS, 16); });
  var places = new Map();
  list.forEach(function (t) {
    var key = portalKey(t);
    t.box = [t.x - t.w / 2, t.y - t.h / 2, t.x + t.w / 2, t.y + t.h / 2];
    places.set(key, t.box);
    obstacle(t.box[0], t.box[1], t.w, t.h, t.show, PLACES.get(key) || t.box);
  });
  PLACES = places;
  list.forEach(function (t) { t.lines.forEach(function (l) { drawBoundary(t, l); }); });
  fadeEnd();
  list.forEach(function (t) {
    var w = t.w, h = t.h, x = t.box[0], y = t.box[1];
    var sc = 0.85 + 0.15 * t.show;
    ctx.save(); ctx.translate(t.x, t.y); ctx.scale(sc, sc); ctx.translate(-t.x, -t.y);
    ctx.globalAlpha = t.show; ctx.fillStyle = C['--raised']; ctx.strokeStyle = C['--ink-3']; ctx.lineWidth = 1.2;
    ctx.beginPath(); rr(ctx, x, y, w, h, h / 2); ctx.fill(); ctx.stroke();
    text(fit(t.nb.id, 12, w - 20, 600), t.x, y + 15, 12, C['--ink'], t.show, 600, false, 'center');
    text(fit(t.where, 10.5, w - 20, 400), t.x, y + 28, 10.5, C['--ink-3'], t.show, 400, false, 'center');
    ctx.restore();
    HITS.push({x: x, y: y, w: w, h: h, kind: 'portal', id: t.nb.id, go: function () { flyTo(worldBox(t.nb), 0.3); }});
  });
}
// A box that does not move with the camera.
function fixedObstacle(x, y, w, h) { obstacle(x, y, w, h, 1, [x, y, x + w, y + h]); }
function flowLayer(l) {
  if (l.p.f !== undefined && l.m.flows[l.p.f]) return l.m.flows[l.p.f].l;
  var up = l.m.owner && l.m.owner.map, f = up && (l.p.pf || []).length ? up.flows[l.p.pf[0]] : null;
  return f ? f.l : '';
}

// ---- the path, the help line and the frame readout ---------------------------
// The parts of the path and the width of its plate.
function pathParts(chain) {
  var parts = [{label: DATA.name || 'map', m: TOP}].concat(chain.map(function (c) { return {label: c.id, m: c.child}; }));
  var total = 12, level = 'level ' + chain.length;
  parts.forEach(function (p, i) { p.w = Math.min(unitWidth(p.label, 600) * 12.5, 220) + 16; total += p.w + (i ? 16 : 0); });
  return {parts: parts, level: level, total: total + unitWidth(level, 400) * 11.5 + 20};
}
function drawPath(chain) {
  var path = pathParts(chain), parts = path.parts, level = path.level, total = path.total;
  var x = 22, y = 14, h = 30, fs = 12.5, gap = 10;
  ctx.globalAlpha = 0.96; ctx.fillStyle = C['--raised']; ctx.strokeStyle = C['--line-2']; ctx.lineWidth = 1; ctx.setLineDash([]);
  ctx.beginPath(); rr(ctx, 12, y - 4, total, h + 8, (h + 8) / 2); ctx.fill(); ctx.stroke();
  parts.forEach(function (p, i) {
    var last = i === parts.length - 1;
    if (i) { text('/', x + 1, y + 20, 13, C['--ink-3'], 1); x += gap + 6; }
    if (last) { ctx.globalAlpha = 1; ctx.fillStyle = C['--ink']; ctx.beginPath(); rr(ctx, x, y + 2, p.w, h - 4, (h - 4) / 2); ctx.fill(); }
    text(fit(p.label, fs, p.w - 16, 600), x + p.w / 2, y + 19.5, fs, last ? C['--raised'] : C['--ink'], 1, 600, false, 'center');
    if (!last) HITS.push({x: x, y: y, w: p.w, h: h, kind: 'path', id: p.m.id, go: function () { flyTo(frameOf(p.m), 0.06); }});
    x += p.w;
  });
  text(level, x + 12, y + 19.5, 11.5, C['--ink-3'], 1);
}
var HELP = ['Wheel or pinch: zoom', 'drag: move', 'double-click a card: go in', 'Esc: go out', 'F: fit'], HELP_FS = 11.5, HELP_LH = 15;
// The help line in lines that fit the screen width, with 18 px at each side. A line breaks
// only between two parts. The last line is at the screen bottom. The lines change only
// when the screen width or the fonts change (`HELP_MEMO`).
var HELP_MEMO = null;
function helpLines() {
  if (HELP_MEMO && HELP_MEMO.w === W && HELP_MEMO.t === TEXTS) return HELP_MEMO.lines;
  var out = [], cur = '', room = (W - 36) / HELP_FS;
  HELP.forEach(function (part) {
    var next = cur ? cur + ' · ' + part : part;
    if (cur && unitWidth(next, 400) > room) { out.push(cur); cur = part; } else cur = next;
  });
  out.push(cur);
  HELP_MEMO = {w: W, t: TEXTS, lines: out};
  return out;
}
// The baseline of help line i of n.
function helpY(i, n) { return H - 16 - HELP_LH * (n - 1 - i); }
function drawHelp() {
  var lines = helpLines();
  lines.forEach(function (line, i) { text(line, 18, helpY(i, lines.length), HELP_FS, C['--ink-3'], 0.9); });
}
var FRAMES = [];
function drawHud(began, half) {
  var now = performance.now();
  FRAMES.push(now);
  while (FRAMES.length && now - FRAMES[0] > 1000) FRAMES.shift();
  var s = FRAMES.length + ' fps · draw ' + (now - began).toFixed(1) + ' ms · ' + (half ? 'half' : 'full') +
    ' · ' + STATS.cards + ' cards · ' + STATS.image + ' images';
  ctx.globalAlpha = 0.95; ctx.fillStyle = C['--raised']; ctx.fillRect(W - 330, 10, 320, 26);
  text(s, W - 320, 27, 12, C['--ink'], 1, 400, true);
}
"""
