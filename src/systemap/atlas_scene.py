"""The scene part of the atlas renderer: the data, the placement, the box indexes, the colors.

The atlas page (`atlas_page`) runs one script. `atlas_script` joins this part and the other
`atlas_*` parts into it. This part runs first. It is a fork of the scene part of the canvas
page (`page_canvas_scene`), with the colors of the atlas (docs/design/atlas.md). It reads
the page data (`atlas_data`) and calculates no layout of a map: each box and each route
point comes from the data.

Placement. The top map has its own coordinates. A map that a card opens is a small picture
in the right part of that card, as in the design study (`layout`). The scale fits the map
in the height of the card. Thus the small picture of a map and the open map have the same
positions, and a zoom into the picture goes into the map. Each nested map keeps its place in
the coordinates of the map above (`L`). The zoom movement of `atlas_inside` moves that place
from the box of the card to `L` (`retree`).

Index. Each map has a grid of its card boxes and its flow boxes. A frame queries only the
cells that the screen covers.

Colors. The script reads the color tokens of the atlas one time, and again only when the
theme changes. Text. The script measures each word one time for each font.
"""

from __future__ import annotations

SCENE = r"""
var DATA = JSON.parse(document.getElementById('atlas-data').textContent);
var cv = document.getElementById('canvas'), ctx = cv.getContext('2d', {alpha: false});
var Q = new URLSearchParams(location.search), HUD = Q.has('hud');
var MOTION = window.matchMedia ? matchMedia('(prefers-reduced-motion: reduce)') : null;
var W = 1, H = 1, cam = {x: 0, y: 0, k: 1};
// The parts of a card that opens a map, as parts of the card height.
var HEAD = 0.2, PAD = 0.06;
// The screen widths of a card over which the small picture of its map comes into view.
var PREVIEW0 = 80, PREVIEW1 = 150;
// Below this screen height a card is a mark. From this height to NAME_H + 4, the mark
// changes into a card and the name of the card fades in (`cardShow`).
var NAME_H = 15;
// No text below this size, in CSS pixels.
var MIN_TEXT = 7;
// A map with this count of cards or more can use one image for its marks.
var BIG = 100;
// The full resolution comes back this time after the camera stops.
var STILL_MS = 150;
var TOUCH = !!(window.matchMedia && matchMedia('(pointer: coarse)').matches);
var STATS = {cards: 0, image: 0, flows: 0};
function reduced() {
  return (MOTION && MOTION.matches) || document.documentElement.getAttribute('data-reduce-motion') === 'true';
}
function dpr() { return window.devicePixelRatio || 1; }
var IMG_MAX = 4096;
function camCopy() { return {x: cam.x, y: cam.y, k: cam.k}; }
function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
function smooth(a, b, v) { var t = clamp((v - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); }
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
// MAPS and `byId` have no prototype. Thus a URL hash such as #constructor names no map.
var MAPS = Object.create(null), ORDER = [];
DATA.maps.forEach(function (m) { MAPS[m.id] = m; });
var TOP = DATA.maps[0];
function pointsBox(p) {
  var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (var i = 0; i < p.length; i++) {
    x0 = Math.min(x0, p[i][0]); y0 = Math.min(y0, p[i][1]); x1 = Math.max(x1, p[i][0]); y1 = Math.max(y1, p[i][1]);
  }
  // A lane moves a line by some units (`LANE` in atlas_lines). The box keeps a margin for it.
  return p.length ? [x0 - 12, y0 - 12, x1 - x0 + 24, y1 - y0 + 24] : null;
}
// The place of the map that a card opens, in the coordinates of the map of the card: a small
// picture in the right part of the card. Its scale makes it fit the height of the card, and
// it is 44 units wide or less (docs/design/atlas/study-script.html, `prepare`).
function layout(b, size) {
  var s = Math.min((b[3] - 12) / size[1], 44 / size[0]);
  return {s: s, at: [b[0] + b[2] - 9 - size[0] * s, b[1] + (b[3] - size[1] * s) / 2]};
}
function place(m, x, y, s, depth, owner) {
  m.T = {x: x, y: y, s: s}; m.depth = depth; m.owner = owner; m.byId = Object.create(null);
  m.maxH = 0; m.maxW = 0; m.oi = ORDER.length; ORDER.push(m);
  m.cards.forEach(function (c, i) {
    c.i = i; c.map = m; c.ins = []; c.outs = []; m.byId[c.id] = c;
    m.maxH = Math.max(m.maxH, c.b[3]); m.maxW = Math.max(m.maxW, c.b[2]);
  });
  m.flows.forEach(function (f, i) {
    f.i = i; f.map = m; f.bb = pointsBox(f.p);
    if (m.byId[f.s]) m.byId[f.s].outs.push(f);
    if (m.byId[f.t]) m.byId[f.t].ins.push(f);
  });
  m.cardIndex = new Index(m.cards, function (c) { return c.b; }, m.size[0], m.size[1]);
  m.flowIndex = new Index(m.flows, function (f) { return f.bb; }, m.size[0], m.size[1]);
  m.cards.forEach(function (c) {
    // A map with no area cannot have a place in a card. Thus the card does not open it.
    var child = c.o !== undefined ? MAPS[c.o] : null;
    if (!child || child.T || !(child.size[0] > 0 && child.size[1] > 0)) return;
    var lay = layout(c.b, child.size);
    c.child = child; child.L = {x: lay.at[0], y: lay.at[1], s: lay.s};
    place(child, x + s * lay.at[0], y + s * lay.at[1], s * lay.s, depth + 1, c);
  });
}
place(TOP, 0, 0, 1, 0, null);
// The world box of a map, and of a card.
// The frame of a map keeps its map (`m`): the fit of a map has the rule of the headline.
function frameOf(m) { var f = [m.T.x, m.T.y, m.size[0] * m.T.s, m.size[1] * m.T.s]; f.m = m; return f; }
function worldBox(c) { var T = c.map.T; return [T.x + T.s * c.b[0], T.y + T.s * c.b[1], T.s * c.b[2], T.s * c.b[3]]; }
// The scale from the coordinates of a map to the screen, and the screen point of its origin.
function view(m) { var k = cam.k; return {a: m.T.s * k, ox: (m.T.x - cam.x) * k, oy: (m.T.y - cam.y) * k}; }
function screenBox(c) { var v = view(c.map), b = c.b; return [v.ox + v.a * b[0], v.oy + v.a * b[1], v.a * b[2], v.a * b[3]]; }
var DEEPEST = 0;
ORDER.forEach(function (m) { DEEPEST = Math.max(DEEPEST, m.depth); });
var KMIN = 0.05, KMAX = 64;
ORDER.forEach(function (m) { KMAX = Math.max(KMAX, 64 / m.T.s); });

// ---- the colors ---------------------------------------------------------
// The tokens of the atlas (`atlas_css`). A flow kind has a color token (`KIND`). A kind
// without a token has the color --ink-2.
var C = {}, FONT_UI = 'sans-serif', FONT_MONO = 'monospace', EPOCH = 0;
var TOKENS = ['--map', '--bg', '--surface', '--card', '--line', '--line-2', '--ink', '--ink-2', '--ink-3', '--wire',
  '--tint', '--brand', '--halo', '--shade', '--focus', '--data', '--control', '--judge', '--context', '--tool', '--change', '--inside', '--ink-3-in'];
var KIND = {data: '--data', control: '--control', judge: '--judge', context: '--context', tool: '--tool'};
function kindColor(k) { return C[KIND[k] || '--ink-2']; }
function readColors() {
  // The tokens of the top map: the style of a nested map (`data-inside`) changes --ink-3.
  var root = document.documentElement, inside = root.hasAttribute('data-inside');
  if (inside) root.removeAttribute('data-inside');
  var cs = getComputedStyle(root);
  function v(name, other) { var x = cs.getPropertyValue(name).trim(); return x || other; }
  TOKENS.forEach(function (n) { C[n] = v(n, '#808080'); });
  // The ground of the top map. A nested map has the ground --inside (`groundSync`).
  C.mapTop = C['--map']; C.ink3Top = C['--ink-3'];
  if (inside) root.setAttribute('data-inside', '');
  FONT_UI = v('--fs', 'sans-serif'); FONT_MONO = v('--fm', 'monospace');
  EPOCH++; textChanged();
}

// ---- text -------------------------------------------------------------------
// The width of each word at 1 px, for each font. The width of a text grows with the
// font size, so one measure serves each size.
var WORDS = new Map(), TEXTS = 0;
// The fonts or the theme changed: the measured widths are not correct. TEXTS is in the
// key of each image that has text (atlas_image), so such an image is made again.
function textChanged() { WORDS.clear(); TEXTS++; }
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
"""
