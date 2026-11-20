"""The finish of the canvas page: the dot grid, the legend, and the dot of a step.

These parts come from DESIGN.md. The linked page had them, and the canvas page did not.
The part also has the round corners of the flow lines (`cutLine`), the halo of a flow label
(`labelHalo`), the letter spacing of the uppercase names (`spaced`), the stronger border of
the card under the pointer (`hoverAt`), and the low contrast of the other flows after a
selection.

- The dot grid. The ground of the map has one dot at each 24 units of the top map, in the
  color `--grid`. The dots follow the camera, so a reader sees a move of the map also in an
  empty area. The cell on the screen stays from 16 px to 32 px: it divides by 2 each time
  the zoom doubles, and the dots of the smaller cell fade in. Thus a deep zoom makes no
  large pattern. The page draws the grid as two pattern fills in each frame, and it keeps
  the pattern of each cell size. While the camera moves, a frame draws only the larger
  cell, from a tile of cells at a scale of 1 (`GRID_TILE_PART`, also on the atlas page).
- The legend. A plate at the bottom right gives one line sample and the name for each flow
  kind that the current map shows in the Map view, and the count of the flows. When the
  plate does not fit at the right of the help line, it gives only the count. With the
  Details panel open at the right, the plate is at the left of the panel. When that does
  not fit, it does not show. A board has no legend.
- The dot of a step. In the Steps mode of the Sequences view, on the map, a dot goes one
  time along the flow of the new step, from its source to its target: 120 ms to show, 600
  ms to move, 120 ms to go. It starts 350 ms after the step, when the camera has moved. A
  motion shows a direction or an order, and it occurs one time. With reduced motion, the
  dot does not show.
- The labels at rest. In the Map view, a flow label shows at rest only when the path of no
  other flow of the layer goes through its box (`restClear`). The other labels show when
  their map has a selected card, or when the pointer is on a card at one end of their flow
  (`restShown`). The legend gives the count of these labels and the action that shows
  them (`restWords`). A2 and A3 of `bench/jev/README.md` give the measured values.
"""

from __future__ import annotations

# The dot grid of a frame while the camera moves. The atlas page (`atlas_draw`) and the canvas
# page use this part.
GRID_TILE_PART = r"""
// ---- the dot grid of a moving frame (page_canvas_finish) -----------------------------
// A pattern fill at a scale that is not 1 costs much time, because the browser samples the
// pattern at each pixel. The dive of a map of 400 cards at 4 times CPU slowdown failed its
// frame limit for this cause. Thus a frame while the camera moves fills the grid from a tile
// of GRID_TILE by GRID_TILE cells in device pixels, at a scale of 1. A dot of the tile is on
// the exact dot nearest to the middle of the screen. The other dots are 4 device pixels or
// less from their exact places on a screen of 1,440 px. `dot(g, x, y)` draws one dot of
// the tile. The page keeps the last GRID_TILES tiles, so that a dive makes few new tiles:
// with 16 cells in a tile, a new tile in each frame kept the dive over its limit.
var GRID_TILE = 8, GRID_TILES = 72, TILES = new Map();
function tileFill(pitch, d, key, dot, ox, oy, top) {
  var t = Math.max(4, Math.round(GRID_TILE * pitch * d)), k = key + '|' + t, p = TILES.get(k);
  if (p === undefined) {
    if (TILES.size >= GRID_TILES) TILES.delete(TILES.keys().next().value);
    var cvs = document.createElement('canvas'), g = cvs.getContext('2d');
    cvs.width = cvs.height = t;
    for (var i = 0; i < GRID_TILE; i++) {
      for (var j = 0; j < GRID_TILE; j++) dot(g, Math.round(i * t / GRID_TILE), Math.round(j * t / GRID_TILE));
    }
    p = ctx.createPattern(cvs, 'repeat'); TILES.set(k, p || null);
  }
  if (!p || !p.setTransform) return;
  var x = ox + Math.round((W / 2 - ox) / pitch) * pitch, y = oy + Math.round((H / 2 - oy) / pitch) * pitch;
  p.setTransform(new DOMMatrix([1 / d, 0, 0, 1 / d, Math.round(x * d) / d, Math.round(y * d) / d]));
  ctx.fillStyle = p; ctx.fillRect(0, top, W, H - top);
}
"""

FINISH = (
    GRID_TILE_PART
    + r"""
// ---- the finish (page_canvas_finish): the dot grid, the legend and the dot of a step ----
var GRID = {made: new Map(), color: ''}, GRID_PITCH = 24, GRID_MIN = 16;
// The pattern of one dot in a cell of `size` device pixels. The sizes are in a small range,
// so the patterns are kept.
function gridPattern(size, color, r) {
  if (GRID.color !== color) { GRID.made.clear(); GRID.color = color; }
  var key = size + ':' + r, p = GRID.made.get(key);
  if (p === undefined) {
    var cvs = document.createElement('canvas'), g = cvs.getContext('2d');
    cvs.width = cvs.height = size; g.fillStyle = color; g.fillRect(0, 0, r, r);
    p = ctx.createPattern(cvs, 'repeat'); GRID.made.set(key, p || null);
  }
  return p;
}
function gridFill(pitch, d, color, alpha) {
  if (alpha <= 0.02) return;
  var size = Math.max(4, Math.round(pitch * d)), p = gridPattern(size, color, Math.max(1, Math.round(d)));
  if (!p || !p.setTransform) return;
  // One cell is `pitch` CSS pixels. A dot is at the origin of the top map.
  var s = pitch / size;
  p.setTransform(new DOMMatrix([s, 0, 0, s, -cam.x * cam.k, -cam.y * cam.k]));
  ctx.globalAlpha = alpha; ctx.fillStyle = p; ctx.fillRect(0, HEAD_H, W, H - HEAD_H);
}
// The cell on the screen stays from GRID_MIN to 2 times GRID_MIN pixels at each zoom: the
// cell divides by 2 each time the zoom doubles. The dots of the smaller cell fade in while
// the cell grows, so the grid does not change at one time. A cell is never larger than 2
// times GRID_MIN device pixels times the pixel ratio, so a deep zoom makes no large pattern.
function drawGrid() {
  var raw = GRID_PITCH * cam.k;
  if (!(raw > 0) || !window.DOMMatrix) return;
  var pitch = raw / Math.pow(2, Math.floor(Math.log(raw / GRID_MIN) / Math.LN2));
  var d = dpr() * (sharp ? 1 : 0.5), color = C['--grid'] || C['--line'];
  // While the camera moves, a frame draws only the larger cell: a pattern fill of the screen is not free.
  if (!sharp) {
    var r = Math.max(1, Math.round(d));
    ctx.globalAlpha = 1;
    tileFill(pitch, d, color + r, function (g, x, y) { g.fillStyle = color; g.fillRect(x, y, r, r); }, -cam.x * cam.k, -cam.y * cam.k, HEAD_H);
    return;
  }
  gridFill(pitch, d, color, 1);
  gridFill(pitch / 2, d, color, smooth(GRID_MIN * 1.25, GRID_MIN * 2, pitch));
}

// The legend: the kinds of the flows that the Map view shows in the current map, and their count.
var LEGEND = {key: '', kinds: [], n: 0, box: null, full: false, count: ''}, LEG_FS = 11.5;
function legendRead(m) {
  var key = m.oi + '|' + VIEW.layer;
  if (LEGEND.key === key) return;
  var seen = {}, kinds = [], n = 0, fl = VIEW.layer === 'all' ? null : layerFlags(m, VIEW.layer).flow;
  m.flows.forEach(function (f, i) {
    if (fl && !fl[i]) return;
    n++;
    if (!seen[f.l]) { seen[f.l] = true; kinds.push(f.l); }
  });
  LEGEND.key = key; LEGEND.kinds = kinds; LEGEND.n = n;
}
// True when the Details panel shows. `panelLeft` is its left edge when it is at the right of a wide screen, else the screen width.
function panelOn() { return !!BOARD_PANEL && !BOARD_PANEL.hidden && BOARD_PANEL.classList.contains('on'); }
function panelLeft() { return panelOn() && W > 900 ? BOARD_PANEL.getBoundingClientRect().left : W; }
function legendLay() {
  LEGEND.box = null;
  if (VIEW.mode !== 'map' || boardOn()) return;
  legendRead(currentMap());
  var more = restWords(currentMap()), count = LEGEND.count = counted(LEGEND.n, 'flow') + (more ? ' \u00b7 ' + more : ''), cw = unitWidth(count, 600, true) * LEG_FS, help = helpPlate(), right = panelLeft(), room = right - 36 - help[0] - help[2];
  var kw = LEGEND.kinds.reduce(function (w, id) { return w + 22 + unitWidth(layerName(id), 400) * LEG_FS + 14; }, 0);
  LEGEND.full = LEGEND.kinds.length > 0 && kw + cw + 24 <= room;
  var w = (LEGEND.full ? kw : 0) + cw + 24;
  if (w > room) return;
  LEGEND.box = [right - 12 - w, H - 30, w, 22];
  obstacle(LEGEND.box[0], LEGEND.box[1], w, 22, 1, 1);
}
function drawLegend() {
  var b = LEGEND.box;
  if (!b) return;
  plate(b, 0.9);
  var x = b[0] + 12, y = b[1] + 15;
  if (LEGEND.full) LEGEND.kinds.forEach(function (id) {
    ctx.globalAlpha = 1; ctx.strokeStyle = C['--l-' + id] || C['--flow']; ctx.lineWidth = 2; ctx.setLineDash([]);
    ctx.beginPath(); ctx.moveTo(x, y - 4); ctx.lineTo(x + 16, y - 4); ctx.stroke();
    text(layerName(id), x + 22, y, LEG_FS, C['--ink-2'], 1);
    x += 22 + unitWidth(layerName(id), 400) * LEG_FS + 14;
  });
  text(LEGEND.count, x, y, LEG_FS, C['--ink-2'], 1, 600, true);
}

// ---- lines, labels and the pointer -------------------------------------------------------
// A line of segments with right angles, cut to the target. A point cut to the target keeps
// each segment on its line. Each corner is round: its radius is 5 units of the map, 8 px or
// less, and half of the shorter of its two segments or less.
function cutLine(g, p, ox, oy, a) {
  var b = bounds(g), bx = b[0] + CUT, by = b[1] + CUT, n = p.length, most = clamp(5 * a, 0, 8);
  function X(i) { return clamp(ox + a * p[i][0], -CUT, bx); }
  function Y(i) { return clamp(oy + a * p[i][1], -CUT, by); }
  function len(i) { return Math.abs(X(i) - X(i - 1)) + Math.abs(Y(i) - Y(i - 1)); }
  g.moveTo(X(0), Y(0));
  for (var i = 1; i < n - 1; i++) g.arcTo(X(i), Y(i), X(i + 1), Y(i + 1), Math.min(most, len(i) / 2, len(i + 1) / 2));
  g.lineTo(X(n - 1), Y(n - 1));
}
// The halo of a flow label: the text in the color of the map, with a wide line, under the
// text. It removes the lines behind the letters and no more.
function labelHalo(s, x, y, size, alpha) {
  if (size < MIN_TEXT || alpha <= 0.02 || !s) return;
  ctx.globalAlpha = alpha; ctx.font = font(500, size); ctx.textAlign = 'center';
  ctx.strokeStyle = C['--map']; ctx.lineWidth = Math.max(3.5, size * 0.6); ctx.lineJoin = 'round'; ctx.setLineDash([]);
  ctx.strokeText(s, x, y);
}
// The letter spacing of the uppercase names, where the browser has it.
function spaced(g, px) { if ('letterSpacing' in g) g.letterSpacing = px ? px.toFixed(2) + 'px' : '0px'; }
// The card under the pointer of a mouse has a stronger border.
var HOVER_C = null;
function hoverAt(px, py) {
  var c = TOUCH || px === null || boardOn() ? null : pickClosed(px, py);
  if (c === HOVER_C) return;
  var was = HOVER_C;
  HOVER_C = c;
  // A stored image of a map has its labels. A hidden label of a flow of the card must show.
  if (VIEW.mode === 'map' && ((was && restHidden(was.map)) || (c && restHidden(c.map)))) { VIEW.epoch++; viewTouch(); }
  else request();
}
cv.addEventListener('pointerleave', function () { hoverAt(null, null); });
// The labels at rest (A2 and A3 of bench/jev/README.md). In the Map view, a label shows at
// rest only when the path of no other flow of the layer goes through its box. The other
// labels show when their map has a selected card, or when the pointer is on a card at one
// of their ends. `restClear` gives the flows of map m with such a free box, for the layer.
function restClear(m) {
  if (m._rk === VIEW.layer) return m._rc;
  var fl = VIEW.layer === 'all' ? null : layerFlags(m, VIEW.layer).flow, clear = [];
  var lines = m.flows.filter(function (f) { return f.p.length && (!fl || fl[f.i]); });
  lines.forEach(function (f) {
    if (!f.lb) return;
    var x0 = f.lb[0], y0 = f.lb[1], x1 = x0 + f.lb[2], y1 = y0 + f.lb[3];
    clear[f.i] = !lines.some(function (o) {
      if (o === f) return false;
      for (var k = 1; k < o.p.length; k++) {
        var a = o.p[k - 1], c = o.p[k];
        if (Math.min(a[0], c[0]) <= x1 && Math.max(a[0], c[0]) >= x0 && Math.min(a[1], c[1]) <= y1 && Math.max(a[1], c[1]) >= y0) return true;
      }
      return false;
    });
  });
  m._rk = VIEW.layer; m._rc = clear;
  m._rh = lines.filter(function (f) { return f.lb && !clear[f.i]; }).length;
  return clear;
}
// The count of the labels of map m that do not show at rest. With a selected card in the
// map, each label of a shown flow shows, so the count is 0.
function restHidden(m) { if (VIEW.mode !== 'map' || (SEL_C && SEL_C.map === m)) return 0; restClear(m); return m._rh; }
// The words of the legend for these labels.
function restWords(m) { var n = restHidden(m); return n ? (TOUCH ? 'select' : 'point at') + ' a card for ' + n + ' more ' + (n === 1 ? 'label' : 'labels') : ''; }
function restShown(f) {
  if (VIEW.mode !== 'map') return 1;
  var m = f.map, near = HOVER_C && HOVER_C.map === m && (f.s === HOVER_C.id || f.t === HOVER_C.id);
  var to = (SEL_C && SEL_C.map === m) || near || restClear(m)[f.i] ? 1 : 0;
  if (VIEW_AIM) return to;
  if (f._rAt !== drawn) {
    f._ra = f._rAt === drawn - 1 ? approach(f._ra, to, VIEW_STEP) : to;
    f._rAt = drawn;
    if (f._ra !== to) VIEW_FADING = true;
  }
  return f._ra;
}
// A new selection: the flows of the selected card stay, and the other flows and cards of its
// map go to low contrast (`VIEWS.map`). The images of a large map are made again.
SEL_HOOKS.push(function () { VIEW.epoch++; viewTouch(); });

// The dot of a step: one move along the route of the flow of the new step.
var DOT = {f: null, t0: 0, key: ''}, DOT_IN = 120, DOT_MOVE = 600, DOT_WAIT = 350;
function dotPoint(p, u) {
  var total = 0, i, d;
  for (i = 1; i < p.length; i++) total += Math.abs(p[i][0] - p[i - 1][0]) + Math.abs(p[i][1] - p[i - 1][1]);
  var want = total * u;
  for (i = 1; i < p.length; i++) {
    d = Math.abs(p[i][0] - p[i - 1][0]) + Math.abs(p[i][1] - p[i - 1][1]);
    if (want <= d || i === p.length - 1) { var t = d ? Math.min(1, want / d) : 0; return [p[i - 1][0] + (p[i][0] - p[i - 1][0]) * t, p[i - 1][1] + (p[i][1] - p[i - 1][1]) * t]; }
    want -= d;
  }
  return p[0];
}
function drawDot() {
  var f = DOT.f;
  if (!f || VIEW.mode !== 'sequences' || !SEQ.steps || boardOn()) { DOT.f = null; return; }
  var ms = performance.now() - DOT.t0, end = DOT_IN + DOT_MOVE + DOT_IN;
  if (ms >= end) { DOT.f = null; return; }
  VIEW_FADING = true;
  if (ms < 0) return;
  var t = clamp((ms - DOT_IN) / DOT_MOVE, 0, 1), u = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
  var al = Math.min(1, ms / DOT_IN, (end - ms) / DOT_IN), v = view(f.map), p = dotPoint(f.p, u), r = clamp(4.5 * v.a, 3.5, 7);
  ctx.globalAlpha = al; ctx.fillStyle = C['--accent']; ctx.beginPath(); ctx.arc(v.ox + v.a * p[0], v.oy + v.a * p[1], r, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = C['--map']; ctx.lineWidth = 1.5; ctx.stroke();
}
HERE_HOOKS.push(function () {
  var key = SEQ.j && SEQ.steps ? SEQ.m.oi + ':' + SEQ.k + ':' + SEQ.s : '';
  if (key === DOT.key) return;
  DOT.key = key;
  var st = key ? SEQ.j.s[SEQ.s] : null, f = st && st.f >= 0 ? SEQ.m.flows[st.f] : null;
  DOT.f = f && f.p.length > 1 && !reduced() ? f : null; DOT.t0 = performance.now() + DOT_WAIT;
  if (DOT.f) request();
});
// The finish for the tests: the grid cell in device pixels, the legend and the dot.
function finishState() {
  return {grid: GRID.made.size, legend: {box: LEGEND.box, kinds: LEGEND.box && LEGEND.full ? LEGEND.kinds.slice() : [], n: LEGEND.n}, dot: DOT.f ? DOT.f.i : -1};
}
"""
)
