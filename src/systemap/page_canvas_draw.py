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

Views. The view part (`page_canvas_view`) gives the alpha and the marks of each card and
the alpha and the color of each flow that a frame draws (`viewCard`, `viewFlow`), and it
draws its parts after the cards of a map (`viewOver`). The header band is at the top of the
screen (`HEAD_H`): the path, the portals, the rings and the boundary flows are below it.

Rings and portals. They come from the camera at each frame. A ring is the frame of an
open map that is larger than the screen. A portal is a neighbour of an open map that is
not on the screen. Each neighbour has one portal. For each direction, the deepest map
that has a port to the neighbour gives the boundary flow, and the flow is drawn one time,
from the portal. That line has right angles. It goes from the actor card of the nested
flow (`fp` of the port in the canvas data) to the port on the frame of the open card,
around the frame, and to the portal. The line uses a clear path: a path that crosses no
card, no text and no portal with a `show` of HARD or more, and that stays on the screen.
When no clear path is possible, the portal has no line. The line is under the cards, the
texts and the portals, and it fades in and out with the camera (`page_canvas_fade`).
Thus a box that comes onto the line covers it while the line fades out.

A portal is in a band at the screen edge, and the camera fit keeps the cards of a map out
of these bands. On a narrow screen, a portal is at the top or the bottom only. Portals on
the same edge move along it as far as necessary, so that they do not cover each other.
Then each portal moves off the cards, the flow label plates and the texts of the maps on
the screen (`dodge` in `page_canvas_fade`). While the camera moves, the cards can go below
the portals, as they can go below the path.
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
var BACK = new Batch(true), BACK_LINE = new Batch(false), FILL = new Batch(true), LINE = new Batch(false);
function flushCards(g) { BACK.flush(g); BACK_LINE.flush(g); FILL.flush(g); LINE.flush(g); }
function q(size) { return Math.round(size * 2) / 2; }
// The font size of the box names and the flow labels, and if the labels show.
function labelSize(a) { return q(clamp(10.5 * a, 0, 13)); }
function hasLabels(fs, alpha) { return fs >= 8 && alpha > 0.05; }
// A text fades in from the size `from` at which the page starts to draw it, for the size
// `raw` before the rounding to half pixels. Thus a text does not appear at one time in a
// zoom. The flow labels start at 8 px, and the box names at MIN_TEXT.
function sizeFade(raw, from) { return smooth(from - 0.25, from + 1.5, raw); }
function labelAlpha(a, alpha) { return alpha * sizeFade(10.5 * a, 8); }
function nameAlpha(a, alpha) { return alpha * sizeFade(10.5 * a, MIN_TEXT); }
// If a card of screen height h shows its text.
function hasText(h) { return h >= NAME_H; }
// From NAME_H to NAME_H + 4 of screen height, a card changes from a mark into a card, and
// its name fades in. Thus the name is not on the mark color when it has the full alpha.
function cardShow(h) { return smooth(NAME_H, NAME_H + 4, h); }
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
  if (TLOG && (ctx === PAGE_CTX || ctx === STILL_CTX)) TLOG.push(drawnText(s, x, y, size, alpha, weight));
  if (NOTE) textBox(s, x, y, size, weight, mono, align, alpha);
}
// While TLOG is a list, each text adds its size, its alpha and its screen box x0, y0, x1, y1
// to it (`systemapCanvas.texts`). The box comes from the font measurement of the browser.
var TLOG = null;
function drawnText(s, x, y, size, alpha, weight) {
  var m = ctx.measureText(s);
  return {s: s, size: size, alpha: alpha, weight: weight || 400,
    box: [x - m.actualBoundingBoxLeft, y - m.actualBoundingBoxAscent, x + m.actualBoundingBoxRight, y + m.actualBoundingBoxDescent]};
}
// The box of a text, as a box that covers a boundary flow. It covers the flow with
// the opacity `alpha` of the text.
function textBox(s, x, y, size, weight, mono, align, alpha) {
  var w = unitWidth(s, weight || 400, mono) * size;
  obstacle(align === 'center' ? x - w / 2 : x, y - size, w, size * 1.3, 1, alpha);
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
  var na = nameAlpha(a, alpha);
  NOTE = g === ctx;
  boxNames(m, a, ox, oy, function (s, x, y, color) { text(s, x, y, fs, color, na, 600); });
  NOTE = false;
}
// The name of each container and region, at its screen point. In a map that has a nested
// map or a port, a name whose box starts at the left of the screen moves with the screen
// edge, STICK px from it, but it stays in its box. Thus the screen edge does not cut it.
// Such a map is never drawn from an image (`isLeaf`), thus the name does not jump when the
// camera stops.
var STICK = 14;
function boxNames(m, a, ox, oy, each) {
  var leaf = isLeaf(m), fs = labelSize(a);
  function at(s, b) {
    var x = ox + a * (b[0] + 13);
    return leaf || x >= STICK ? x : Math.max(x, Math.min(STICK, ox + a * (b[0] + b[2] - 13) - unitWidth(s, 600) * fs));
  }
  m.boxes.forEach(function (b) { each(b.n, at(b.n, b.b), oy + a * (b.b[1] + 19), C['--ink-3']); });
  m.regions.forEach(function (b, i) { var s = (i + 1) + '  ' + b.n; each(s, at(s, b.b), oy + a * (b.b[1] + 20), C['--ink-2']); });
}
// The view gives the alpha and the color of each flow (`viewFlow`). A group has one color,
// one evidence state and one alpha, in steps of 1/16. A flow with the plain value goes into
// the group of its layer and its evidence (`_pk`), with no new key text.
function drawFlows(g, list, a, ox, oy, alpha, arrows) {
  if (alpha <= 0.02 || !list.length) return;
  var groups = new Map(), width = clamp(1.3 * a, 0.6, 2), head = clamp(7 * a, 3, 8);
  function add(f, color, al) {
    var q = Math.round(al * 16) / 16, key = color + '|' + f.ev + '|' + q, e = groups.get(key);
    if (q <= 0) return;
    if (!e) { e = {color: color, ev: f.ev, alpha: q, list: []}; groups.set(key, e); }
    e.list.push(f);
  }
  list.forEach(function (f) {
    if (!f.p.length) return;
    var v = viewFlow(f);
    if (!VIEW_AIM) STATS.flows++;
    if (v.a === 1 && v.u === 1 && v.color === null) {
      var key = f._pk || (f._pk = f.l + '|' + f.ev), e = groups.get(key);
      if (!e) { e = {color: flowColor(f, null), ev: f.ev, alpha: 1, list: []}; groups.set(key, e); }
      e.list.push(f);
      return;
    }
    add(f, flowColor(f, v.color), v.a * v.u);
    if (v.u < 1) add(f, flowColor(f, v.from), v.a * (1 - v.u));
  });
  groups.forEach(function (e) {
    g.globalAlpha = alpha * e.alpha; g.strokeStyle = e.color; g.lineWidth = width;
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
  alpha = labelAlpha(a, alpha);
  if (!hasLabels(fs, alpha)) return;
  // The plate fits the text. The text stops at 13 px, so a plate of the label box would
  // grow past the text and cover the routes.
  var bg = new Batch(true);
  plates(list, a, ox, oy, fs, function (px, py, pw, ph, f) {
    var fa = alpha * flowShown(f);
    if (fa <= 0.02) return;
    bg.rect(C['--map'], fa * 0.9, px, py, pw, ph, 3);
    obstacle(px, py, pw, ph, 1, fa);
  });
  bg.flush(ctx);
  list.forEach(function (f) {
    if (!f.lb) return;
    text(f.a, ox + a * (f.lb[0] + f.lb[2] / 2), oy + a * (f.lb[1] + f.lb[3] / 2) + fs * 0.36, fs, C['--ink-2'], alpha * flowShown(f), 500, false, 'center');
  });
}

// The screen box of the plate of each flow label with a font size of `fs`.
function plates(list, a, ox, oy, fs, each) {
  var ph = fs * 1.5;
  list.forEach(function (f) {
    if (!f.lb) return;
    var pw = unitWidth(f.a, 500) * fs + 6;
    each(ox + a * (f.lb[0] + f.lb[2] / 2) - pw / 2, oy + a * (f.lb[1] + f.lb[3] / 2) - ph / 2, pw, ph, f);
  });
}

// ---- cards ------------------------------------------------------------------------
// The corner radius of a card of the screen size w x h. A small card has square corners.
function cardCorner(w, h) { return w > 60 ? clamp(h * 0.1, 2, 8) : 0; }
// The view gives the alpha and the marks of the card (`viewCard`).
function cardBox(c, x, y, w, h, alpha) {
  STATS.cards++;
  var v = viewCard(c), t = cardShow(h), k = colors(c), r = cardCorner(w, h);
  alpha *= v.a;
  if (t < 1) FILL.rect(k.mark, alpha * (1 - t), x, y, w, h, 0);
  viewMarksAt(c, v, x, y, w, h, alpha);
  if (t <= 0) return;
  if (c.child) { BACK.rect(C['--line-2'], alpha * t, x + 4, y + 4, w, h, r); viewBack(v, x, y, w, h, r, alpha * t); }
  FILL.rect(k.fill, alpha * t, x, y, w, h, r);
  LINE.rect(k.line, alpha * t, x, y, w, h, r, 1, c.k === 'actor' ? 'a' : '');
}
// ---- a card that opens a map -----------------------------------------------------
function drawOpening(c, a, ox, oy, alpha) {
  var x = ox + a * c.b[0], y = oy + a * c.b[1], w = a * c.b[2], h = a * c.b[3];
  if (x > W || y > H || x + w < 0 || y + h < 0) return;
  STATS.cards++;
  var o = openness(c), pv = smooth(PREVIEW0, PREVIEW1, w), k = colors(c), r = clamp(h * 0.06, 2, 10), g = ctx, v = viewCard(c), va = v.a;
  // A quiet card is quiet also in its preview. The nested map has its own view when it is open.
  alpha *= va + (1 - va) * o;
  g.setLineDash([]);
  if (o < 1) { g.globalAlpha = alpha * (1 - o); g.fillStyle = C['--line-2']; g.beginPath(); rr(g, x + 4, y + 4, w, h, r); g.fill(); }
  g.beginPath(); rr(g, x, y, w, h, r);
  g.globalAlpha = alpha; g.fillStyle = C['--map']; g.fill();
  if (o < 1) { g.globalAlpha = alpha * (1 - o); g.fillStyle = k.fill; g.fill(); }
  g.globalAlpha = alpha; g.strokeStyle = o > 0.5 ? C['--ink-3'] : k.line; g.lineWidth = 1 + 0.4 * o; g.stroke();
  var u = titleSize(h), pad = inset(h), n = c.child.cards.length;
  var more = {s: counted(n, 'card') + ' in this map', alpha: o};
  // A boundary flow can go through an open card, but not through its text.
  NOTE = CHAIN.indexOf(c) >= 0;
  if (!NOTE) obstacle(x, y, w, h, 1, alpha);
  title(c, x + pad, y + Math.max(2, h * 0.06), w - 2 * pad, u, alpha, more);
  if (c.side) {
    var s = c.side;
    details(c, ox + a * s[0], oy + a * s[1], a * s[2], a * s[3], alpha * (1 - 0.4 * o), titleRaw(h));
  }
  NOTE = false;
  viewOpening(c, v, x, y, w, h, r, alpha, o);
  drawMap(c.child, alpha * pv, o);
}

// ---- a map --------------------------------------------------------------------
function drawMap(m, alpha, open) {
  if (alpha <= 0.01) return;
  var v = view(m), a = v.a, ox = v.ox, oy = v.oy, mw = m.size[0] * a, mh = m.size[1] * a;
  if (ox > W || oy > H || ox + mw < 0 || oy + mh < 0) return;
  var big = m.cards.length >= BIG, marks = big && m.maxH * a < NAME_H && m.maxW * a < PREVIEW0;
  // Also ask for the map image in a frame of marks, which has free time to make it. While
  // the zoom goes in, in the last quarter step of zoom before the marks end, the images fade
  // in over the marks, where the frame is not expensive. In the other frames of marks, the
  // marks image is less work than the images.
  var near = !marks || (zoomingIn() && m.maxH * a >= NAME_H * Math.pow(2, -MARKS_OVER * MAP_STEP));
  var whole = big ? imageLayer(m, a, !sharp && open >= 1, near) : null, full = whole && layerFull(whole);
  if (marks) {
    // The marks image stays current also under a full image layer, for the frames after it.
    var img = marksImage(m, a);
    if (full) img = null;
    if (img || full) {
      if (img) { ctx.globalAlpha = alpha; ctx.drawImage(img.canvas, ox, oy, mw, mh); STATS.image++; viewMarks(m, ox, oy, mw, mh, alpha); }
      if (whole) drawLayer(whole, ox, oy, mw, mh, alpha);
      STATS.cards += m.cards.length; obstacle(ox, oy, mw, mh, 1, alpha);
      viewOver(m, a, ox, oy, alpha);
      return;
    }
  }
  var x0 = -ox / a, y0 = -oy / a, x1 = (W - ox) / a, y1 = (H - oy) / a;
  // An image layer at its full alpha replaces the normal drawing. While it fades, the frame
  // draws the normal drawing and the images over it.
  if (full) {
    drawLayer(whole, ox, oy, mw, mh, alpha);
    STATS.cards += mapObstacles(m, a, ox, oy, [x0, y0, x1, y1], alpha); viewOver(m, a, ox, oy, alpha); return;
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
    obstacle(x, y, w, h, 1, alpha * c._v.a);
    if (hasText(h)) texts.push(c);
  }
  flushCards(ctx);
  if (open > 0.3) drawLabels(flows, a, ox, oy, alpha * smooth(0.3, 0.8, open));
  texts.forEach(function (c) { cardText(c, ox + a * c.b[0], oy + a * c.b[1], a * c.b[2], a * c.b[3], alpha * c._v.a); });
  drawTags();
  opening.forEach(function (c) { drawOpening(c, a, ox, oy, alpha); });
  if (whole) drawLayer(whole, ox, oy, mw, mh, alpha);
  viewOver(m, a, ox, oy, alpha);
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
  return [Math.max(r[0], inset), Math.max(r[1], HEAD_H + inset), Math.min(r[0] + r[2], W - inset), Math.min(r[1] + r[3], H - inset)];
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
// line of its portal, so that its flow fades out (`fadeOf`). A second port of the same map
// in the same direction gives no line: its line has the same key, and a spare line with that
// key would fade out the line of the first port in the same frame.
function portalsOf(chain) {
  var out = [], seen = {}, at = new Map();
  for (var i = chain.length - 1; i >= 0; i--) {
    var m = chain[i].child;
    (m.ports || []).forEach(function (p) {
      var key = p.x + '|' + p.d;
      if (seen[key] && (!FADE.size || seen[key] === m)) return;
      var nb = neighbour(chain, i, p.x);
      if (!nb) return;
      if (seen[key]) {
        var s = at.get(nb);
        if (s && FADE.has(lineKey(nb, p, m))) s.lines.push({p: p, m: m, open: chain[i], spare: true});
        return;
      }
      seen[key] = m;
      var t = at.get(nb);
      if (!t) {
        var r = screenBox(nb);
        if (boxOnScreen(r)) return;
        var where = whereOf(nb.map);
        t = portalPlace({nb: nb, where: where, h: P_H, w: portalWidth(nb.id, where), lines: []}, r, screenBox(sibling(chain, nb)));
        at.set(nb, t); out.push(t);
      }
      t.lines.push({p: p, m: m, open: chain[i]});
    });
  }
  return dodge(apart(portalFades(out)));
}
// Tell if a part of the screen box r is on the screen. A neighbour has a portal only when
// no part of its card is on the screen. The target `show` of each portal is thus 1, and a
// portal that is not in the list fades out (`portalFades`). The `show` changes by time
// only. When the camera stops, each portal is fully shown or it fades out fully. It does
// not stay partly shown. `onScreen` below is a different test, for a point.
function boxOnScreen(r) { return r[0] + r[2] > 0 && r[1] + r[3] > HEAD_H && r[0] < W && r[1] < H; }
// The open card in the map of a neighbour.
function sibling(chain, nb) {
  for (var j = 0; j < chain.length; j++) if (chain[j].map === nb.map) return chain[j];
  return chain[0];
}
// The second line of a portal: the map of the neighbour.
function whereOf(m) { return 'in ' + (m.id ? m.id.split('/').pop() : DATA.name); }
// The portals are in a band at each screen edge. The camera fit keeps the cards of a map
// out of these bands (`gutters`, `fitBox`). Thus a portal does not cover a card of the
// open map. P_TOP and P_BOTTOM are the middle of a portal at the top and at the bottom,
// from the screen edge. The top row is below the path, and the bottom row is above the
// help line (`drawHelp`).
// On a touch screen, the target of a portal is TARGET pixels high: 2 times P_PAD pixels
// more than its drawing (`drawPortals`). In the top row and in the bottom row, the added
// part is between the drawing and the screen edge. Thus the target does not go into the
// cards of the maps at the fit. At the left and the right, the target has P_PAD pixels
// above and below the drawing. The gap between two portals is 2 times P_PAD, thus the
// targets do not overlap. The top row is P_LOW pixels lower,
// below the larger path, and the bottom band of the fit is P_LOW pixels larger. Thus the
// fit puts the middle of a map at the same height as on a screen with no touch. The drawing
// of a portal does not become larger. A larger drawing in the bottom row covers cards of
// the map above at the fit (C5 in docs/design/nested-canvas.md).
var P_H = 34, P_EDGE = 20, P_PAD = Math.max(0, (TARGET - P_H) / 2), P_GAP = Math.max(6, 2 * P_PAD), P_LOW = TOUCH ? 8 : 0;
var P_TOP0 = 84 + P_LOW, P_TOP = P_TOP0, P_BOTTOM = 52, P_MAX = 150, P_WIDEST = 0;
// The middle of a portal in the bottom row, and the range of the middle of portal `t` along
// the top or the bottom edge.
function bottomRow() { return Math.max(P_TOP, H - P_BOTTOM); }
function rowRange(t) { return [P_EDGE + t.w / 2, W - P_EDGE - t.w / 2]; }
function portalSpan(idUnit, whereUnit) { return Math.max(TARGET, Math.min(Math.max(idUnit * 12, whereUnit * 10.5) + 30, P_MAX)); }
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
  return {x: side <= 0.12 * W ? side : 0, top: P_TOP + P_H / 2 + P_GAP, bottom: P_BOTTOM + P_H / 2 + P_GAP + P_LOW};
}
// The place of a portal: the middle of its neighbour, moved into the screen. A portal that
// touches the left or the right band is on that side (`side` -1 or 1). Else it is at the
// top or the bottom (`side` 0). When a portal is wider than the side band (on a narrow
// screen), it is at the top or the bottom. Then the row is the top row if the neighbour is
// above the middle of the open card `o` in its map. A camera move does not change this.
// With no `o` (a portal that fades out), the portal stays at its side or in its row. The
// row comes from its place before its move off the boxes of the maps (`y0` of `dodge`).
// `along` is the place along the edge before the portals move apart. Its order does not
// change while the camera moves, thus the stacks below do not jump.
function portalPlace(t, r, o) {
  var cx = r[0] + r[2] / 2, cy = r[1] + r[3] / 2, ends = rowRange(t), x0 = ends[0], x1 = ends[1];
  var band = gutters().x >= P_EDGE + t.w + P_GAP, bottom = bottomRow();
  var top = o ? cy < o[1] + o[3] / 2 : (t.y0 === undefined ? t.y : t.y0) < bottom;
  if (o) t.side = !band ? 0 : cx <= x0 ? -1 : cx >= x1 ? 1 : 0;
  t.x = t.side < 0 ? x0 : t.side > 0 ? x1 : clamp(cx, x0, x1);
  t.y = !t.side && (!band || !o) ? (top ? P_TOP : bottom) : clamp(cy, P_TOP, bottom);
  t.along = t.side ? cy : cx;
  return t;
}
function order(a, b) { return a < b ? -1 : a > b ? 1 : 0; }
// Portals on the same edge must not cover each other. Each one moves along its edge only
// as far as necessary. A portal that comes into view pushes the others gradually (`room`).
function apart(list) {
  list.sort(function (a, b) { return a.along - b.along || order(a.nb.id, b.nb.id) || order(a.where, b.where); });
  var low = H - P_BOTTOM;
  [-1, 1].forEach(function (side) {
    stack(list.filter(function (t) { return t.side === side; }), 'y', function () { return P_H + P_GAP; }, P_TOP, low);
  });
  [P_TOP, bottomRow()].forEach(function (row) {
    var line = list.filter(function (t) { return !t.side && t.y === row; }), ends = rowEnds(list, row);
    stack(line, 'x', function (a, b) { return (a.w + b.w) / 2 + P_GAP; }, ends[0], ends[1]);
  });
  return list;
}
// The part of the gap that two portals keep: the smaller `room` of the two. `room` goes
// from 0 to 1 by time while a portal fades in, and back to 0 while it fades out
// (`portalFades`). Thus only a portal that fades can cover a part of a different portal.
// Each portal on an edge can push a portal after it, not only the next one. A push is the
// part `kept` of the full push, and a portal moves by the largest of these pushes. Thus
// the places change continuously and slowly. While a portal fades in, it pushes the others
// gradually. While it fades out, they move back gradually. When it goes, nothing jumps.
function kept(a, b) { return Math.min(a.room, b.room); }
// Push each portal after the ones before it (dir 1), or before the ones after it (dir -1).
function push(line, key, gap, dir) {
  var n = line.length;
  for (var u = 1; u < n; u++) {
    var t = line[dir > 0 ? u : n - 1 - u], most = 0;
    for (var v = 0; v < u; v++) {
      var o = line[dir > 0 ? v : n - 1 - v];
      most = Math.max(most, (dir * (o[key] - t[key]) + gap(o, t)) * kept(o, t));
    }
    t[key] += dir * most;
  }
}
// Push each portal after the ones before it, then move the stack back from the far end.
// The limit at the start can push two portals into one place. Thus push them one more time.
function stack(line, key, gap, lo, hi) {
  function half(t) { return key === 'x' ? t.w / 2 : 0; }
  push(line, key, gap, 1);
  line.forEach(function (t) { t[key] = Math.min(t[key], hi - half(t)); });
  push(line, key, gap, -1);
  line.forEach(function (t) { t[key] = Math.max(t[key], lo + half(t)); });
  push(line, key, gap, 1);
}
// The free part of a top or a bottom row. A side portal near the row takes its corner.
// The corner becomes free gradually while that portal moves away from the row, or while
// it fades out (`room`).
function rowEnds(list, row) {
  var lo = P_EDGE, hi = W - P_EDGE;
  list.forEach(function (s) {
    if (!s.side) return;
    var keep = (1 - smooth(P_H + P_GAP, 2 * (P_H + P_GAP), Math.abs(s.y - row))) * s.room, w = (s.w + P_GAP) * keep;
    if (s.side < 0) lo = Math.max(lo, P_EDGE + w); else hi = Math.min(hi, W - P_EDGE - w);
  });
  return [lo, hi];
}

// ---- boundary flows ---------------------------------------------------------------
// The screen boxes that cover a boundary flow, as x0, y0, x1, y1, a weight and an opacity:
// each card that a frame draws, the text of each open card, each flow label, each portal,
// the path and the help line. A clear path goes into no box with a weight of HARD or more.
// The weight is 1, but the weight of a portal is its `show`. The opacity is the opacity of
// the drawing of the box. The layer of the lines (`layerClose`) removes the part of a line
// under a box with that opacity. The array is used again in each frame, so its size does
// not grow.
var OBST = [], NOBST = 0, HARD = 0.5, OB = 6;
function obstacle(x, y, w, h, weight, alpha) {
  if (w <= 0 || h <= 0 || x > W || y > H || x + w < 0 || y + h < 0) return;
  OBST[NOBST++] = x; OBST[NOBST++] = y; OBST[NOBST++] = x + w; OBST[NOBST++] = y + h;
  OBST[NOBST++] = weight === undefined ? 1 : weight; OBST[NOBST++] = alpha === undefined ? 1 : clamp(alpha, 0, 1);
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
function onScreen(p) { return p[0] >= 1 && p[0] <= W - 1 && p[1] >= HEAD_H + 1 && p[1] <= H - 1; }
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
// jump when the point goes out of the range.
function slide(lo, hi, v, out) { return v < (lo + hi) / 2 ? lo + Math.min(out, (hi - lo) / 2) : hi - Math.min(out, (hi - lo) / 2); }
function legs(pts, q, pr, across) {
  var cx = (pr[0] + pr[2]) / 2, cy = (pr[1] + pr[3]) / 2;
  var outX = Math.max(pr[0] - q[0], q[0] - pr[2], 0), outY = Math.max(pr[1] - q[1], q[1] - pr[3], 0), x, y;
  if (across && !outY) pts.push([q[0] < cx ? pr[0] : pr[2], q[1]]);
  else if (!across && !outX) pts.push([q[0], q[1] < cy ? pr[1] : pr[3]]);
  else if (across) { x = slide(pr[0], pr[2], q[0], outY); pts.push([x, q[1]], [x, q[1] < cy ? pr[1] : pr[3]]); }
  else { y = slide(pr[1], pr[3], q[1], outX); pts.push([q[0], y], [q[0] < cx ? pr[0] : pr[2], y]); }
}
// One path from the gutter point `from` on side s: around the frame (at the gutter `e`) in
// the direction `step` to side `side`, and then to the portal. The path is clear (`ok`)
// when each point is on the screen, and no segment after the first goes into `f` or into a
// box. A path that is not clear can still fade out under the boxes.
function aroundTo(a, from, f, e, s, side, step, pr, across) {
  var pts = [a, from], k = s, n = 0;
  while (k !== side && n++ < 4) { pts.push(cornerOf(e, step > 0 ? k : (k + 3) % 4)); k = (k + step + 4) % 4; }
  var q = onSide(e, side, (pr[0] + pr[2]) / 2, (pr[1] + pr[3]) / 2);
  pts.push(q);
  legs(pts, q, pr, across);
  pts = straight(pts);
  pts.ok = true;
  for (var i = 1; i < pts.length && pts.ok; i++) {
    if (!onScreen(pts[i]) || (i > 1 && (!clear(pts[i - 1], pts[i]) || into(pts[i - 1], pts[i], f)))) pts.ok = false;
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
// of the last segments. It gives each of these 16 paths (`all`), its cost, and if it is
// clear (`clear`). A path is clear when its first segment is on the screen and goes into no
// box, and `aroundTo` finds the other segments clear. `best` is the index of the shortest
// clear path, or -1. Give null when the port has no `fp`.
var GUTTER = 16, RING = 4;
function boundaryPath(t, l) {
  var p = l.p, fp = p.fp;
  if (!fp || p.f === undefined) return null;
  var v = view(l.m), r = screenBox(l.open), G = GUTTER, R = RING;
  var f = onScreenEdges(r, R + 1), e = onScreenEdges([r[0] - G, r[1] - G, r[2] + 2 * G, r[3] + 2 * G], R);
  var a = [v.ox + v.a * fp[0][0], v.oy + v.a * fp[0][1]], dx = fp[1][0] - fp[0][0], dy = fp[1][1] - fp[0][1];
  var s = dy < 0 ? 0 : dx > 0 ? 1 : dy > 0 ? 2 : 3, from = onSide(e, s, a[0], a[1]);
  var first = onScreen(a) && onScreen(from) && clear(a, from);
  var pr = t.box, all = [], costs = [], ok = [], best = -1;
  for (var side = 0; side < 4; side++) {
    for (var c = 0; c < 4; c++) {
      var pts = aroundTo(a, from, f, e, s, side, c < 2 ? 1 : -1, pr, c % 2 === 0), k = pathCost(pts), good = first && pts.ok;
      if (good && (best < 0 || k < costs[best])) best = all.length;
      all.push(pts); costs.push(k); ok.push(good);
    }
  }
  return {all: all, costs: costs, clear: ok, best: best, port: onSide([r[0], r[1], r[0] + r[2], r[1] + r[3]], s, a[0], a[1])};
}

function drawBoundary(t, l) {
  var key = lineKey(t.nb, l.p, l.m), b = boundaryPath(t, l), paths = fadeOf(key, b, t, l);
  if (!paths.length) return;
  var v = boundaryView(l), most = 0;
  paths.forEach(function (one) {
    var p = one.pts.slice(), alpha = t.show * one.v * v.a;
    if (alpha <= 0.01) return;
    if (l.p.d === 'in') p.reverse();
    layerHold(p, 10);
    most = Math.max(most, alpha);
    LINKS.push({id: t.nb.id, d: l.p.d, points: p, key: key + '#' + one.i, alpha: alpha});
    boundaryLine(p, v.color, alpha * v.u);
    if (v.from) boundaryLine(p, v.from, alpha * (1 - v.u));
  });
  if (most <= 0) return;
  // The port: a small circle on the frame of the open card.
  layerHold([b.port], 6);
  ctx.globalAlpha = most * 0.9; ctx.fillStyle = C['--map']; ctx.beginPath(); ctx.arc(b.port[0], b.port[1], 3.5, 0, 2 * Math.PI); ctx.fill(); ctx.stroke();
}
var HITS = [], LINKS = [];
// The lines come first, in the layer of the lines (`layerOpen`). The boxes cover them, and
// the portals are drawn after them. Thus no line goes over a card, a text or a portal.
function drawPortals(list, path) {
  obstacle.apply(null, pathPlate(path));
  obstacle.apply(null, helpPlate());
  obstacle(0, 0, W, HEAD_H, 1, 1);
  list.forEach(function (t) {
    t.box = [t.x - t.w / 2, t.y - t.h / 2, t.x + t.w / 2, t.y + t.h / 2];
    obstacle(t.box[0], t.box[1], t.w, t.h, t.show, t.show);
  });
  LUSED = list.length > 0 || FADE.size > 0;
  if (LUSED) {
    var screen = ctx;
    ctx = layerOpen(screen);
    try {
      list.forEach(function (t) { t.lines.forEach(function (l) { drawBoundary(t, l); }); });
      fadeLeft(drawBoundary);
    } finally { ctx = screen; }
    layerClose();
  }
  fadeEnd();
  list.forEach(function (t) {
    var w = t.w, h = t.h, x = t.box[0], y = t.box[1];
    var sc = 0.85 + 0.15 * t.show;
    ctx.save(); ctx.translate(t.x, t.y); ctx.scale(sc, sc); ctx.translate(-t.x, -t.y);
    ctx.globalAlpha = t.show; ctx.fillStyle = C['--raised']; ctx.strokeStyle = C['--ink-3']; ctx.lineWidth = 1.2;
    ctx.beginPath(); rr(ctx, x, y, w, h, h / 2); ctx.fill(); ctx.stroke();
    text(fit(t.nb.id, 12, w - 20, 600), t.x, y + h / 2 - 2, 12, C['--ink'], t.show, 600, false, 'center');
    text(fit(t.where, 10.5, w - 20, 400), t.x, y + h / 2 + 11, 10.5, C['--ink-3'], t.show, 400, false, 'center');
    ctx.restore();
    var out = t.side ? P_PAD : t.y < H / 2 ? 2 * P_PAD : 0;
    HITS.push({x: x, y: y - out, w: w, h: h + 2 * P_PAD, box: [x, y, w, h], kind: 'portal', id: t.nb.id, map: t.nb.map.id, show: t.show, go: function () { flyTo(worldBox(t.nb), 0.3); }});
  });
}

// ---- the path, the help line and the frame readout ---------------------------
// The parts of the path and the width of its plate. The text of a part is 220 px wide or
// less. When the path is wider than the screen, the widest texts become narrower (`cap`).
function pathParts(chain) {
  var parts = [{label: DATA.name || 'map', m: TOP}].concat(chain.map(function (c) { return {label: c.id, m: c.child}; }));
  var level = 'level ' + chain.length, total = 12 + 32 * parts.length - 16 + unitWidth(level, 400) * 11.5 + 20;
  var ws = parts.map(function (p) { return Math.min(unitWidth(p.label, 600) * 12.5, 220); }), c = cap(ws, W - 24 - total);
  parts.forEach(function (p, i) { p.w = Math.max(TARGET, Math.min(ws[i], c) + 16); total += p.w - 16; });
  return {parts: parts, level: level, total: total};
}
// The largest width c, 40 or more, so that the widths, each made c or less, fit in `room`.
function cap(widths, room) {
  var list = widths.slice().sort(function (u, v) { return u - v; }), used = 0;
  for (var i = 0; i < list.length; i++) {
    var c = (room - used) / (list.length - i);
    if (list[i] > c) return Math.max(40, c);
    used += list[i];
  }
  return Infinity;
}
// The screen box x, y, w, h of the plate of the path. A part of the path is PATH_H high.
var PATH_H = Math.max(30, TARGET);
function pathPlate(path) { return [12, HEAD_H + 10, path.total, PATH_H + 8]; }
// A plate with round ends, under the path or the help line.
function plate(b, alpha) {
  ctx.globalAlpha = alpha; ctx.fillStyle = C['--raised']; ctx.strokeStyle = C['--line-2']; ctx.lineWidth = 1; ctx.setLineDash([]);
  ctx.beginPath(); rr(ctx, b[0], b[1], b[2], b[3], b[3] / 2); ctx.fill(); ctx.stroke();
}
function drawPath(path) {
  var parts = path.parts, level = path.level, x = 22, y = HEAD_H + 14, h = PATH_H, fs = 12.5, gap = 10, base = y + h / 2 + 4.5;
  plate(pathPlate(path), 0.96);
  parts.forEach(function (p, i) {
    var last = i === parts.length - 1;
    if (i) { text('/', x + 1, base + 0.5, 13, C['--ink-3'], 1); x += gap + 6; }
    if (last) { ctx.globalAlpha = 1; ctx.fillStyle = C['--ink']; ctx.beginPath(); rr(ctx, x, y + 2, p.w, h - 4, (h - 4) / 2); ctx.fill(); }
    text(fit(p.label, fs, p.w - 16, 600), x + p.w / 2, base, fs, last ? C['--raised'] : C['--ink'], 1, 600, false, 'center');
    if (!last) HITS.push({x: x, y: y, w: p.w, h: h, kind: 'path', id: p.m.id, go: function () { flyTo(frameOf(p.m), FIT); }});
    x += p.w;
  });
  text(level, x + 12, base, 11.5, C['--ink-3'], 1);
}
// The help line has one line on a plate at the bottom left of the screen, below the bottom
// row of the portals. On a touch screen, it gives the touch inputs. Else it is the first
// text of HELP that fits the screen width. A text that does not fit becomes shorter with
// '...'. The line changes only when the screen width or the fonts change (`HELP_MEMO`).
var HELP = ['Wheel or pinch: zoom · drag: move · double-click a card: go in · Esc: go out · F: fit · Tab: next card',
  'Wheel or pinch: zoom · drag: move · double-click a card: go in · Esc: go out · F: fit',
  'Wheel: zoom · drag: move · double-click a card: go in · Esc: go out', 'Wheel: zoom · drag: move · double-click: go in'];
var HELP_TOUCH = 'Pinch: zoom · drag: move · tap: select · tap again: go in', HELP_FS = 11.5, HELP_MEMO = null;
function helpLine() {
  if (HELP_MEMO && HELP_MEMO.w === W && HELP_MEMO.t === TEXTS) return HELP_MEMO.line;
  var room = W - 48, line = TOUCH ? HELP_TOUCH : HELP.filter(function (s) { return unitWidth(s, 400) * HELP_FS <= room; })[0];
  line = fit(line || HELP[HELP.length - 1], HELP_FS, room, 400);
  HELP_MEMO = {w: W, t: TEXTS, line: line};
  return line;
}
// The screen box x, y, w, h of the plate of the help line.
function helpPlate() { return [12, H - 30, unitWidth(helpLine(), 400) * HELP_FS + 20, 22]; }
function drawHelp() {
  var b = helpPlate();
  plate(b, 0.9);
  text(helpLine(), b[0] + 10, b[1] + 15, HELP_FS, C['--ink-3'], 1);
}
var FRAMES = [];
function drawHud(began, half) {
  var now = performance.now();
  FRAMES.push(now);
  while (FRAMES.length && now - FRAMES[0] > 1000) FRAMES.shift();
  var s = FRAMES.length + ' fps · draw ' + (now - began).toFixed(1) + ' ms · ' + (half ? 'half' : 'full') +
    ' · ' + STATS.cards + ' cards · ' + STATS.image + ' images';
  ctx.globalAlpha = 0.95; ctx.fillStyle = C['--raised']; ctx.fillRect(W - 330, HEAD_H + 10, 320, 26);
  text(s, W - 320, HEAD_H + 27, 12, C['--ink'], 1, 400, true);
}
"""
