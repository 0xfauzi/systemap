"""The finish of the canvas page: the dot grid, the legend, and the dot of a step.

These parts come from DESIGN.md. The linked page had them, and the canvas page did not.

- The dot grid. The ground of the map has one dot at each 24 units of the top map, in the
  color `--grid`. The dots follow the camera, so a reader sees a move of the map also in an
  empty area. The cell on the screen stays from 16 px to 32 px: it divides by 2 each time
  the zoom doubles, and the dots of the smaller cell fade in. Thus a deep zoom makes no
  large pattern. The page draws the grid as two pattern fills in each frame, and it keeps
  the pattern of each cell size.
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
"""

from __future__ import annotations

FINISH = r"""
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
  gridFill(pitch, d, color, 1);
  // While the camera moves, a frame draws only the larger cell: a pattern fill of the screen is not free.
  if (sharp) gridFill(pitch / 2, d, color, smooth(GRID_MIN * 1.25, GRID_MIN * 2, pitch));
}

// The legend: the kinds of the flows that the Map view shows in the current map, and their count.
var LEGEND = {key: '', kinds: [], n: 0, box: null, full: false}, LEG_FS = 11.5;
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
  var count = counted(LEGEND.n, 'flow'), cw = unitWidth(count, 600, true) * LEG_FS, help = helpPlate(), right = panelLeft(), room = right - 36 - help[0] - help[2];
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
  text(counted(LEGEND.n, 'flow'), x, y, LEG_FS, C['--ink-2'], 1, 600, true);
}

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
