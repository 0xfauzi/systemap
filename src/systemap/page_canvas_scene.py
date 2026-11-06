"""The scene part of the canvas renderer: placement, box indexes, colors and text.

The canvas page (`canvas_page`) runs one script. `page_canvas` joins this part, the
drawing part (`page_canvas_draw`) and the input part into that script. This part runs
first. It reads the canvas data (`canvas_data`) and calculates no layout of a map: each
box and each route point comes from the data.

Placement. The top map has its own coordinates. A map that a card opens goes into the
inner area of that card: below a header band, and to the right of (or below) a side
column for the text of the card. The scale fits the map in that area. Thus the preview
of a map and the open map have the same positions.

Index. Each map has a grid of its card boxes and its flow boxes. A frame queries only
the cells that the screen covers.

Colors. The script reads the theme tokens of the page one time, and again only when the
theme changes. Text. The script measures each word one time for each font and keeps the
wrapped lines of each card for each count of columns. The width of a text grows with the
font size, so the lines in a count of columns do not change with the size.
"""

from __future__ import annotations

SCENE = r"""
var DATA = JSON.parse(document.getElementById('canvas-data').textContent);
var cv = document.getElementById('canvas'), ctx = cv.getContext('2d', {alpha: false});
var Q = new URLSearchParams(location.search), HUD = Q.has('hud');
var MOTION = window.matchMedia ? matchMedia('(prefers-reduced-motion: reduce)') : null;
var W = 1, H = 1, cam = {x: 0, y: 0, k: 1};
// The parts of a card that opens a map, as parts of the card height.
var HEAD = 0.2, PAD = 0.06;
// The screen widths of a card, as parts of the screen width, over which the card
// changes into the frame of its map. At 1440 pixels, they are 302 and 562 pixels.
var OPEN0 = 0.21, OPEN1 = 0.39;
// The screen widths of a card over which the preview of its map comes into view.
var PREVIEW0 = 80, PREVIEW1 = 150;
// Below this screen height a card is a mark in its layer color.
var MARK_H = 22;
// No text below this size, in CSS pixels.
var MIN_TEXT = 7;
// While the camera moves, a card with a name below this size shows only its name.
var MOVE_TEXT = 10;
// A map with this count of cards or more can use one image for its marks.
var BIG = 100;
// The full resolution comes back this time after the camera stops.
var STILL_MS = 150;
var STATS = {cards: 0, image: 0};
function reduced() {
  return (MOTION && MOTION.matches) || document.documentElement.getAttribute('data-reduce-motion') === 'true';
}
// The device pixel ratio, the largest side of an image, and a copy of the camera.
function dpr() { return window.devicePixelRatio || 1; }
var IMG_MAX = 4096;
function camCopy() { return {x: cam.x, y: cam.y, k: cam.k}; }
function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
function smooth(a, b, v) { var t = clamp((v - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); }
// The value v moved toward `to` by `step` or less.
function approach(v, to, step) { return v < to ? Math.min(to, v + step) : Math.max(to, v - step); }

// ---- the index of boxes -------------------------------------------------
var STAMP = 0;
function Index(items, boxOf, w, h) {
  var n = clamp(Math.ceil(Math.sqrt(items.length / 2)), 1, 64);
  this.nx = n; this.ny = n; this.cw = Math.max(w, 1) / n; this.ch = Math.max(h, 1) / n;
  this.cells = [];
  for (var i = 0; i < n * n; i++) this.cells.push([]);
  for (var j = 0; j < items.length; j++) {
    var b = boxOf(items[j]);
    if (!b) continue;
    var x0 = this.col(b[0]), x1 = this.col(b[0] + b[2]), y0 = this.row(b[1]), y1 = this.row(b[1] + b[3]);
    for (var y = y0; y <= y1; y++) for (var x = x0; x <= x1; x++) this.cells[y * n + x].push(items[j]);
  }
}
Index.prototype.col = function (x) { return clamp(Math.floor(x / this.cw), 0, this.nx - 1); };
Index.prototype.row = function (y) { return clamp(Math.floor(y / this.ch), 0, this.ny - 1); };
// Give the items whose cells the local box x0, y0, x1, y1 covers, each one time.
Index.prototype.query = function (x0, y0, x1, y1, out) {
  var s = ++STAMP, c0 = this.col(x0), c1 = this.col(x1), r0 = this.row(y0), r1 = this.row(y1);
  for (var y = r0; y <= r1; y++) for (var x = c0; x <= c1; x++) {
    var cell = this.cells[y * this.nx + x];
    for (var i = 0; i < cell.length; i++) if (cell[i]._s !== s) { cell[i]._s = s; out.push(cell[i]); }
  }
  return out;
};

// ---- placement ------------------------------------------------------------
var MAPS = {}, ORDER = [];
DATA.maps.forEach(function (m) { MAPS[m.id] = m; });
var TOP = DATA.maps[0];
function pointsBox(p) {
  var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (var i = 0; i < p.length; i++) {
    x0 = Math.min(x0, p[i][0]); y0 = Math.min(y0, p[i][1]); x1 = Math.max(x1, p[i][0]); y1 = Math.max(y1, p[i][1]);
  }
  return p.length ? [x0, y0, x1 - x0, y1 - y0] : null;
}
// The inner area of a card that opens a map, and its side column, in the coordinates of
// the map of the card. The side column is at the left when the map is narrow, and below
// the map when the map is wide.
function layout(b, size) {
  var pad = b[3] * PAD, head = b[3] * HEAD;
  var ax = b[0] + pad, ay = b[1] + head, aw = b[2] - 2 * pad, ah = b[3] - head - pad;
  var s = Math.min(aw / size[0], ah / size[1]), mw = size[0] * s, mh = size[1] * s;
  var fx = aw - mw, fy = ah - mh;
  if (fx > aw * 0.25) return {s: s, at: [ax + fx, ay + fy / 2], side: [ax, ay, fx - pad, ah]};
  if (fy > ah * 0.3) return {s: s, at: [ax + fx / 2, ay], side: [ax, ay + mh + pad, aw, fy - pad]};
  return {s: s, at: [ax + fx / 2, ay + fy / 2], side: null};
}
function place(m, x, y, s, depth, owner) {
  m.T = {x: x, y: y, s: s}; m.depth = depth; m.owner = owner; m.byId = {};
  m.maxH = 0; m.maxW = 0; ORDER.push(m);
  m.cards.forEach(function (c) {
    c.map = m; c.ins = []; c.outs = []; m.byId[c.id] = c;
    m.maxH = Math.max(m.maxH, c.b[3]); m.maxW = Math.max(m.maxW, c.b[2]);
  });
  m.flows.forEach(function (f, i) {
    f.i = i; f.bb = pointsBox(f.p);
    if (m.byId[f.s]) m.byId[f.s].outs.push(f);
    if (m.byId[f.t]) m.byId[f.t].ins.push(f);
  });
  m.cardIndex = new Index(m.cards, function (c) { return c.b; }, m.size[0], m.size[1]);
  m.flowIndex = new Index(m.flows, function (f) { return f.bb; }, m.size[0], m.size[1]);
  m.cards.forEach(function (c) {
    var child = c.o !== undefined ? MAPS[c.o] : null;
    if (!child || child.T) return;
    var lay = layout(c.b, child.size);
    c.child = child; c.side = lay.side;
    place(child, x + s * lay.at[0], y + s * lay.at[1], s * lay.s, depth + 1, c);
  });
}
place(TOP, 0, 0, 1, 0, null);
// The world box of a map, and of a card.
function frameOf(m) { return [m.T.x, m.T.y, m.size[0] * m.T.s, m.size[1] * m.T.s]; }
function worldBox(c) { var T = c.map.T; return [T.x + T.s * c.b[0], T.y + T.s * c.b[1], T.s * c.b[2], T.s * c.b[3]]; }
// The scale from the coordinates of a map to the screen, and the screen point of its origin.
function view(m) { var k = cam.k; return {a: m.T.s * k, ox: (m.T.x - cam.x) * k, oy: (m.T.y - cam.y) * k}; }
function screenBox(c) { var v = view(c.map), b = c.b; return [v.ox + v.a * b[0], v.oy + v.a * b[1], v.a * b[2], v.a * b[3]]; }
function openness(c) { return c.child ? smooth(OPEN0 * W, OPEN1 * W, c.b[2] * c.map.T.s * cam.k) : 0; }
var DEEPEST = 0;
ORDER.forEach(function (m) { DEEPEST = Math.max(DEEPEST, m.depth); });
var KMIN = 0.05, KMAX = 64;
ORDER.forEach(function (m) { KMAX = Math.max(KMAX, 64 / m.T.s); });

// ---- the theme colors ---------------------------------------------------
var C = {}, FONT_UI = 'sans-serif', FONT_MONO = 'monospace', EPOCH = 0;
var TOKENS = ['--map', '--bg', '--card', '--card-line', '--actor', '--ink', '--ink-2', '--ink-3', '--flow',
  '--region', '--accent', '--line', '--line-2', '--raised', '--surface'];
function readColors() {
  var cs = getComputedStyle(document.documentElement);
  function v(name, other) { var x = cs.getPropertyValue(name).trim(); return x || other; }
  TOKENS.forEach(function (n) { C[n] = v(n, '#808080'); });
  ORDER.forEach(function (m) {
    m.flows.forEach(function (f) { C['--l-' + f.l] = v('--l-' + f.l, C['--flow']); });
    m.cards.forEach(function (c) { (c.l || []).forEach(function (l) { C['--l-' + l] = v('--l-' + l, C['--flow']); }); });
    m.cards.forEach(function (c) {
      var s = c.s || 'built';
      C['--card-' + s] = v('--card-' + s, C['--card']);
      C['--card-' + s + '-line'] = v('--card-' + s + '-line', C['--card-line']);
    });
    m.boxes.forEach(function (b) {
      C['--box-' + b.t] = v('--box-' + b.t, 'none'); C['--box-' + b.t + '-line'] = v('--box-' + b.t + '-line', C['--line-2']);
    });
  });
  FONT_UI = v('--fs', 'sans-serif'); FONT_MONO = v('--fm', 'monospace');
  EPOCH++; textChanged();
}

// ---- text -------------------------------------------------------------------
// The width of each word at 1 px, for each font. The width of a text grows with the
// font size, so one measure serves each size.
var WORDS = new Map(), TEXTS = 0;
// The fonts or the theme changed: the measured widths are not correct. TEXTS is in the
// key of each image that has text (page_canvas_draw), so such an image is made again.
function textChanged() { WORDS.clear(); P_WIDEST = 0; TEXTS++; }
function font(weight, size, mono) { return weight + ' ' + size + 'px ' + (mono ? FONT_MONO : FONT_UI); }
function unitWidth(word, weight, mono) {
  var key = weight + (mono ? 'm' : 's') + word, w = WORDS.get(key);
  if (w === undefined) { ctx.font = font(weight, 100, mono); w = ctx.measureText(word).width / 100; WORDS.set(key, w); }
  return w;
}
// Cut a text to fit `width` at `size`. Add three dots when the text is cut.
function fit(text, size, width, weight, mono) {
  if (unitWidth(text, weight, mono) * size <= width) return text;
  var dots = unitWidth('...', weight, mono) * size, lo = 0, hi = text.length;
  while (lo < hi) {
    var mid = (lo + hi + 1) >> 1;
    if (unitWidth(text.slice(0, mid), weight, mono) * size + dots <= width) lo = mid; else hi = mid - 1;
  }
  return lo ? text.slice(0, lo) + '...' : '';
}
// The lines of a text at a font size, in a count of columns, with a maximum count of
// lines. A column is half of the font size, so the lines in a count of columns are the
// same at each size. A card keeps the result for each text, count of columns and count of
// lines.
function wrap(c, name, text, size, cols, lines, weight) {
  var key = name + '|' + cols + '|' + lines, width = cols * size / 2;
  c._wrap = c._wrap || new Map();
  if (c._wrap.has(key)) return c._wrap.get(key);
  var words = String(text).split(/\s+/).filter(Boolean), out = [], cur = '', curW = 0, space = unitWidth(' ', weight) * size;
  var i = 0;
  for (; i < words.length; i++) {
    var ww = unitWidth(words[i], weight) * size;
    if (cur && curW + space + ww > width) {
      out.push(cur); cur = ''; curW = 0;
      if (out.length === lines) break;
    }
    cur = cur ? cur + ' ' + words[i] : words[i]; curW = cur === words[i] ? ww : curW + space + ww;
  }
  if (out.length < lines && cur) { out.push(cur); i = words.length; }
  for (var j = 0; j < out.length; j++) out[j] = fit(out[j], size, width, weight);
  if (i < words.length && out.length) out[out.length - 1] = fit(out[out.length - 1] + ' ...', size, width, weight);
  if (c._wrap.size > 64) c._wrap.clear();
  c._wrap.set(key, out);
  return out;
}
"""
