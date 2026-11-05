"""The drawing part of the canvas renderer: maps, cards, flows, rings, portals and the path.

`page_canvas` joins this part after the scene part (`page_canvas_scene`). The part
follows the rules of the section "Performance" of docs/design/nested-canvas.md:

- It paints with the 2D API of a `<canvas>` element. It makes no SVG element.
- It draws only the cards and the flows that the box index of a map gives for the screen.
- It puts the boxes of one style in one path (`Batch`), and it draws no text below 7 px.
- When the cards of a large map are marks only, it draws the map into an image one time
  for each zoom step, and it uses that image in each frame (`marksImage`).

Level of detail. The screen size of a card selects what the card shows: a mark in its
layer color, then the name, then the card text, the description and the fact row, and
then the lists of flows and modules. Each step fades in as the card grows. A card that
opens a map shows the preview of that map in the same positions. Between OPEN0 and
OPEN1 of the screen width, the card changes into the frame of the map.

Rings and portals. They come from the camera at each frame. A ring is the frame of an
open map that is larger than the screen. A portal is a neighbour of an open map that is
not on the screen. The deepest map that has a port to a neighbour gives its portal, and
its boundary flow is drawn one time, from the portal.
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
var BACK = new Batch(true), FILL = new Batch(true), LINE = new Batch(false);
function q(size) { return Math.round(size * 2) / 2; }
function colors(c) {
  if (c._c && c._c.e === EPOCH) return c._c;
  var s = c.s || 'built', actor = c.k === 'actor';
  var line = actor ? C['--card-line'] : C['--card-' + s + '-line'], mark = line;
  (c.l || []).forEach(function (l) { if (mark === line && C['--l-' + l] && l !== 'system') mark = C['--l-' + l]; });
  c._c = {e: EPOCH, fill: actor ? C['--actor'] : C['--card-' + s], line: line, mark: mark};
  return c._c;
}
function text(s, x, y, size, color, alpha, weight, mono, align) {
  if (size < MIN_TEXT || alpha <= 0.02 || !s) return;
  ctx.globalAlpha = alpha; ctx.fillStyle = color; ctx.font = font(weight || 400, size, mono);
  ctx.textAlign = align || 'left'; ctx.fillText(s, x, y);
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
  var fs = q(clamp(10.5 * a, 0, 13));
  if (!labels || fs < MIN_TEXT) return;
  m.boxes.forEach(function (b) {
    text(b.n, ox + a * (b.b[0] + 13), oy + a * (b.b[1] + 19), fs, C['--ink-3'], alpha, 600);
  });
  m.regions.forEach(function (b, i) {
    text((i + 1) + '  ' + b.n, ox + a * (b.b[0] + 13), oy + a * (b.b[1] + 20), fs, C['--ink-2'], alpha, 600);
  });
}
function drawFlows(g, m, list, a, ox, oy, alpha, arrows) {
  if (alpha <= 0.02 || !list.length) return;
  var groups = new Map(), width = clamp(1.3 * a, 0.6, 2), head = clamp(7 * a, 3, 8);
  list.forEach(function (f) {
    var fade = m.fade[f.i] || 0;
    if (fade >= 0.98 || !f.p.length) return;
    var key = f.l + '|' + f.ev + '|' + Math.round((1 - fade) * 8), e = groups.get(key);
    if (!e) { e = {color: C['--l-' + f.l] || C['--flow'], ev: f.ev, alpha: alpha * Math.round((1 - fade) * 8) / 8, list: []}; groups.set(key, e); }
    e.list.push(f);
  });
  groups.forEach(function (e) {
    g.globalAlpha = e.alpha; g.strokeStyle = e.color; g.lineWidth = width;
    g.setLineDash(e.ev === 'structural' ? DASH.s : e.ev === 'declared' ? DASH.d : DASH['']);
    g.beginPath();
    // A route has right angles. Thus a point cut to the target keeps each segment on its line.
    var b = bounds(g), bx = b[0] + CUT, by = b[1] + CUT;
    e.list.forEach(function (f) {
      var p = f.p;
      g.moveTo(clamp(ox + a * p[0][0], -CUT, bx), clamp(oy + a * p[0][1], -CUT, by));
      for (var i = 1; i < p.length; i++) g.lineTo(clamp(ox + a * p[i][0], -CUT, bx), clamp(oy + a * p[i][1], -CUT, by));
    });
    g.stroke();
    if (!arrows) return;
    g.setLineDash([]); g.fillStyle = e.color; g.beginPath();
    e.list.forEach(function (f) {
      var p = f.p, n = p.length;
      if (n < 2) return;
      var x2 = ox + a * p[n - 1][0], y2 = oy + a * p[n - 1][1], an = Math.atan2(y2 - (oy + a * p[n - 2][1]), x2 - (ox + a * p[n - 2][0]));
      g.moveTo(x2, y2);
      g.lineTo(x2 - head * Math.cos(an - 0.45), y2 - head * Math.sin(an - 0.45));
      g.lineTo(x2 - head * Math.cos(an + 0.45), y2 - head * Math.sin(an + 0.45));
    });
    g.fill();
  });
}
function drawLabels(m, list, a, ox, oy, alpha) {
  var fs = q(clamp(10.5 * a, 0, 13));
  if (fs < 8 || alpha <= 0.05) return;
  var bg = new Batch(true);
  list.forEach(function (f) {
    if (f.lb && !(m.fade[f.i] > 0.5)) bg.rect(C['--map'], alpha * 0.9, ox + a * f.lb[0] - 3, oy + a * f.lb[1], a * f.lb[2] + 6, a * f.lb[3], 3);
  });
  bg.flush(ctx);
  list.forEach(function (f) {
    if (!f.lb || m.fade[f.i] > 0.5) return;
    text(f.a, ox + a * (f.lb[0] + f.lb[2] / 2), oy + a * (f.lb[1] + f.lb[3] / 2) + fs * 0.36, fs, C['--ink-2'], alpha, 500, false, 'center');
  });
}

// ---- the image of the marks of a large map -------------------------------------------
// One image for each half step of zoom (a factor of 1.41). A pan uses the same image.
function marksImage(m, a) {
  var z = Math.round(Math.log2(a) * 2) / 2, s = Math.pow(2, z) * (window.devicePixelRatio || 1), key = EPOCH + '|' + z;
  if (m.img && m.img.key === key) return m.img;
  var w = Math.ceil(m.size[0] * s), h = Math.ceil(m.size[1] * s);
  if (w < 1 || h < 1 || w > 4096 || h > 4096) return null;
  var c = m.img ? m.img.canvas : document.createElement('canvas'), g;
  c.width = w; c.height = h; g = c.getContext('2d');
  g.fillStyle = C['--map']; g.fillRect(0, 0, w, h);
  drawBoxes(g, m, s, 0, 0, 1, false);
  drawFlows(g, m, m.flows, s, 0, 0, 0.7, false);
  var marks = new Batch(true);
  m.cards.forEach(function (card) {
    marks.rect(colors(card).mark, 1, s * card.b[0], s * card.b[1], s * card.b[2], s * card.b[3], 0);
  });
  marks.flush(g);
  m.img = {canvas: c, key: key};
  return m.img;
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
  details(c, x + pad, top, w - 2 * pad, y + h - pad * 0.6 - top, t, u);
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
  title(c, x + pad, y + Math.max(2, h * 0.06), w - 2 * pad, u, alpha, more);
  if (c.side) {
    var s = c.side;
    details(c, ox + a * s[0], oy + a * s[1], a * s[2], a * s[3], alpha * (1 - 0.4 * o), u);
  }
  drawMap(c.child, alpha * pv, o);
}

// ---- a map --------------------------------------------------------------------
function drawMap(m, alpha, open) {
  if (alpha <= 0.01) return;
  var v = view(m), a = v.a, ox = v.ox, oy = v.oy, mw = m.size[0] * a, mh = m.size[1] * a;
  if (ox > W || oy > H || ox + mw < 0 || oy + mh < 0) return;
  if (m.cards.length >= BIG && m.maxH * a < MARK_H - 6 && m.maxW * a < PREVIEW0) {
    var img = marksImage(m, a);
    if (img) { ctx.globalAlpha = alpha; ctx.drawImage(img.canvas, ox, oy, mw, mh); STATS.image++; STATS.cards += m.cards.length; return; }
  }
  var x0 = -ox / a, y0 = -oy / a, x1 = (W - ox) / a, y1 = (H - oy) / a;
  drawBoxes(ctx, m, a, ox, oy, alpha * (0.4 + 0.6 * open), open > 0.5);
  var flows = m.flowIndex.query(x0, y0, x1, y1, []);
  drawFlows(ctx, m, flows, a, ox, oy, alpha * (0.35 + 0.65 * open), m.maxH * a > 14);
  var cards = m.cardIndex.query(x0, y0, x1, y1, []), opening = [], texts = [];
  for (var i = 0; i < cards.length; i++) {
    var c = cards[i], b = c.b, x = ox + a * b[0], y = oy + a * b[1], w = a * b[2], h = a * b[3];
    if (x > W || y > H || x + w < 0 || y + h < 0) continue;
    if (c.child && w >= PREVIEW0) { opening.push(c); continue; }
    cardBox(c, x, y, w, h, alpha);
    if (h >= MARK_H - 4) texts.push(c);
  }
  BACK.flush(ctx); FILL.flush(ctx); LINE.flush(ctx);
  if (open > 0.3) drawLabels(m, flows, a, ox, oy, alpha * smooth(0.3, 0.8, open));
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
function drawRings(chain) {
  ctx.setLineDash([]);
  chain.forEach(function (c, i) {
    var r = screenBox(c), over = Math.max(-r[0], -r[1], r[0] + r[2] - W, r[1] + r[3] - H), al = smooth(0, 120, over);
    if (al <= 0.01) return;
    var inset = 6 + (chain.length - 1 - i) * 6, x0 = Math.max(r[0], inset), y0 = Math.max(r[1], inset);
    var x1 = Math.min(r[0] + r[2], W - inset), y1 = Math.min(r[1] + r[3], H - inset);
    if (x1 <= x0 || y1 <= y0) return;
    ctx.globalAlpha = al * (0.3 + 0.5 * (i + 1) / chain.length); ctx.strokeStyle = C['--ink-3']; ctx.lineWidth = 1.2;
    ctx.beginPath(); rr(ctx, x0, y0, x1 - x0, y1 - y0, 14); ctx.stroke();
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
function onScreen(r) { return r[0] < W && r[1] < H && r[0] + r[2] > 0 && r[1] + r[3] > 0; }
function portalsOf(chain) {
  var out = [], seen = {};
  ORDER.forEach(function (m) { if (m._fade) { m.fade = {}; m._fade = false; } });
  for (var i = chain.length - 1; i >= 0; i--) {
    var m = chain[i].child;
    (m.ports || []).forEach(function (p) {
      var key = p.x + '|' + p.d;
      if (seen[key]) return;
      var nb = neighbour(chain, i, p.x);
      if (!nb) return;
      seen[key] = true;
      var r = screenBox(nb), mg = 30, off = Math.max(mg - (r[0] + r[2]), mg - (r[1] + r[3]), r[0] - (W - mg), r[1] - (H - mg));
      var show = smooth(0, 160, off);
      if (show <= 0.01) return;
      var inner = p.i !== undefined ? m.byId[p.i] : null, where = 'in ' + (nb.map.id ? nb.map.id.split('/').pop() : DATA.name);
      if (inner && !onScreen(screenBox(inner))) inner = null;
      if (p.f !== undefined && inner) { m.fade[p.f] = show; m._fade = true; }
      out.push({p: p, nb: nb, m: m, inner: inner, show: show, where: where, h: 34,
        w: Math.max(unitWidth(p.x, 600) * 12, unitWidth(where, 400) * 10.5) + 30,
        x: clamp(r[0] + r[2] / 2, 96, W - 96), y: clamp(r[1] + r[3] / 2, 84, H - 64)});
    });
  }
  return apart(out);
}
// Two portals at the same screen edge must not cover each other.
function apart(list) {
  list.sort(function (a, b) { return a.y - b.y || a.x - b.x; });
  for (var i = 1; i < list.length; i++) for (var j = 0; j < i; j++) {
    var a = list[j], b = list[i];
    if (Math.abs(a.x - b.x) < (a.w + b.w) / 2 + 6 && Math.abs(a.y - b.y) < 40) b.y = a.y + 40 > H - 40 ? a.y - 40 : a.y + 40;
  }
  return list;
}
function edgePoint(r, px, py) {
  var cx = r[0] + r[2] / 2, cy = r[1] + r[3] / 2, dx = px - cx, dy = py - cy;
  var s = Math.min(Math.abs(r[2] / 2 / (dx || 1e-9)), Math.abs(r[3] / 2 / (dy || 1e-9)));
  return [cx + dx * s, cy + dy * s];
}
var HITS = [];
function drawPortals(list) {
  list.forEach(function (t) {
    var w = t.w, h = t.h, x = t.x - w / 2, y = t.y - h / 2, color = C['--l-' + flowLayer(t)] || C['--flow'];
    if (t.inner) {
      var ir = screenBox(t.inner), e = edgePoint(ir, t.x, t.y), s = edgePoint([x, y, w, h], e[0], e[1]);
      var from = t.p.d === 'in' ? s : e, to = t.p.d === 'in' ? e : s, an = Math.atan2(to[1] - from[1], to[0] - from[0]);
      ctx.globalAlpha = t.show * 0.9; ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.setLineDash(DASH.p);
      ctx.beginPath(); ctx.moveTo(from[0], from[1]); ctx.lineTo(to[0], to[1]); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = color; ctx.beginPath(); ctx.moveTo(to[0], to[1]);
      ctx.lineTo(to[0] - 8 * Math.cos(an - 0.45), to[1] - 8 * Math.sin(an - 0.45));
      ctx.lineTo(to[0] - 8 * Math.cos(an + 0.45), to[1] - 8 * Math.sin(an + 0.45)); ctx.fill();
    }
    var sc = 0.85 + 0.15 * t.show;
    ctx.save(); ctx.translate(t.x, t.y); ctx.scale(sc, sc); ctx.translate(-t.x, -t.y);
    ctx.globalAlpha = t.show; ctx.fillStyle = C['--raised']; ctx.strokeStyle = C['--ink-3']; ctx.lineWidth = 1.2;
    ctx.beginPath(); rr(ctx, x, y, w, h, h / 2); ctx.fill(); ctx.stroke();
    text(t.p.x, t.x, y + 15, 12, C['--ink'], t.show, 600, false, 'center');
    text(t.where, t.x, y + 28, 10.5, C['--ink-3'], t.show, 400, false, 'center');
    ctx.restore();
    HITS.push({x: x, y: y, w: w, h: h, kind: 'portal', id: t.p.x, go: function () { flyTo(worldBox(t.nb), 0.3); }});
  });
}
function flowLayer(t) {
  if (t.p.f !== undefined && t.m.flows[t.p.f]) return t.m.flows[t.p.f].l;
  var up = t.m.owner && t.m.owner.map, f = up && (t.p.pf || []).length ? up.flows[t.p.pf[0]] : null;
  return f ? f.l : '';
}

// ---- the path, the help line and the frame readout ---------------------------
function drawPath(chain) {
  var parts = [{label: DATA.name || 'map', m: TOP}].concat(chain.map(function (c) { return {label: c.id, m: c.child}; }));
  var x = 22, y = 14, h = 30, fs = 12.5, gap = 10, total = 12;
  parts.forEach(function (p, i) { p.w = Math.min(unitWidth(p.label, 600) * fs, 220) + 16; total += p.w + (i ? gap + 6 : 0); });
  var level = 'level ' + chain.length;
  total += unitWidth(level, 400) * 11.5 + 20;
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
var HELP = 'Wheel or pinch: zoom · drag: move · double-click a card: go in · Esc: go out · F: fit';
function drawHelp() {
  text(HELP, 18, H - 16, 11.5, C['--ink-3'], 0.9);
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
