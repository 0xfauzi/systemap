"""The renderer script of the canvas page: the camera, the frames and the input.

The canvas page (`canvas_page`) has one script element with `SCRIPT`. It joins the
scene part (`page_canvas_scene`), the drawing part (`page_canvas_draw`) and the part in
this module. The page CSP (`page_csp`) gets the digest of that element.

Camera. The wheel and the pinch zoom at the pointer, and a drag moves the map. A
double-click, or a tap, goes into the card under the pointer. Esc goes out one level, F
fits the current map, and + and - zoom at the middle of the screen. The arrow keys move
the map. A camera move changes the scale in log space, and it goes out and back in when
the two views are far apart. With `prefers-reduced-motion`, or with the page setting
Reduce motion, each move occurs at one time.

Frames. An input event asks for one frame (`requestAnimationFrame`). While the camera
moves, the canvas has half of the device resolution. STILL_MS after the last move, the
script draws one frame at full resolution.

The URL hash holds the camera target: the ID of the open map, for example
`#Gateway/Routes`. A link with a hash opens the canvas at that map. When the camera
stops, the script writes the hash of the current map with `history.replaceState`.

`?hud` shows a frame readout at the top right: the frames in the last second, the time
of the last draw, the resolution, and the count of drawn cards and images. A person can
use it to measure on a real device. `window.systemapCanvas` gives the camera and the
state to the tests and the measurement scripts. It changes nothing on the page.
"""

from __future__ import annotations

from systemap.page_canvas_draw import DRAW
from systemap.page_canvas_scene import SCENE

CSS = """
html,body{margin:0;height:100%;overflow:hidden;background:var(--map)}
#canvas{position:fixed;inset:0;width:100%;height:100%;display:block;touch-action:none;
outline:none;cursor:grab}
#canvas.drag{cursor:grabbing}
#canvas:focus-visible{box-shadow:inset 0 0 0 2px var(--accent)}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);
white-space:nowrap}
"""

_INPUT = r"""
// ---- the camera ---------------------------------------------------------------
// The camera that fits a world box in the screen. It keeps the bands of the portals free.
function fitBox(b, pad) {
  pad = pad === undefined ? 0.06 : pad;
  var g = gutters(), sx = Math.max(W * pad, g.x), top = Math.max(48 + (H - 56) * pad, g.top), bottom = Math.max(8 + (H - 56) * pad, g.bottom);
  var k = clamp(Math.min(Math.max(1, W - 2 * sx) / b[2], Math.max(1, H - top - bottom) / b[3]), KMIN, KMAX);
  return {x: b[0] + b[2] / 2 - W / 2 / k, y: b[1] + b[3] / 2 - (top + H - bottom) / 2 / k, k: k};
}
var flight = null;
function stopFlight() { if (flight) { cancelAnimationFrame(flight.raf); flight = null; } }
function flyTo(box, pad) { fly(fitBox(box, pad)); }
// The scale moves in log space. When the two views are far apart, the path goes out and
// back in, so that the reader sees where the camera goes.
function fly(to, ms) {
  stopFlight();
  if (reduced()) { cam = to; moved(); return; }
  var from = {x: cam.x, y: cam.y, k: cam.k};
  var cx0 = from.x + W / 2 / from.k, cy0 = from.y + H / 2 / from.k, cx1 = to.x + W / 2 / to.k, cy1 = to.y + H / 2 / to.k;
  var dist = Math.hypot(cx1 - cx0, cy1 - cy0) * Math.min(from.k, to.k) / Math.max(W, H);
  var dip = Math.log(1 + dist) * 1.1, l0 = Math.log(from.k), l1 = Math.log(to.k);
  ms = ms || clamp(450 + 200 * (Math.abs(l1 - l0) + dip), 450, 1500);
  var t0 = performance.now();
  function step(now) {
    var t = clamp((now - t0) / ms, 0, 1), e = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
    var k = Math.exp(l0 + (l1 - l0) * e - dip * Math.sin(Math.PI * e));
    var cx = cx0 + (cx1 - cx0) * e, cy = cy0 + (cy1 - cy0) * e;
    cam = {x: cx - W / 2 / k, y: cy - H / 2 / k, k: k};
    moved(true);
    if (t < 1) flight.raf = requestAnimationFrame(step); else flight = null;
  }
  flight = {raf: requestAnimationFrame(step)};
}
function zoomAt(px, py, f) {
  var wx = cam.x + px / cam.k, wy = cam.y + py / cam.k, k = clamp(cam.k * f, KMIN, KMAX);
  cam = {x: wx - px / k, y: wy - py / k, k: k};
  moved();
}
function topFrame() { return frameOf(TOP); }
// The camera after a zoom by `f` at the middle of the screen, in the zoom limits.
function zoomed(f) {
  var k = clamp(cam.k * f, KMIN, KMAX), cx = cam.x + W / 2 / cam.k, cy = cam.y + H / 2 / cam.k;
  return {x: cx - W / 2 / k, y: cy - H / 2 / k, k: k};
}

// ---- frames -------------------------------------------------------------------
var pending = false, sharp = true, stillTimer = 0, CHAIN = [], drawn = 0;
// A camera change: draw at half resolution now, and at full resolution when it stops.
function moved(now) {
  sharp = false;
  clearTimeout(stillTimer);
  stillTimer = setTimeout(function () { sharp = true; if (!flight) { draw(); settled(); } }, STILL_MS);
  if (now) draw(); else request();
}
function request() { if (!pending) { pending = true; requestAnimationFrame(function () { pending = false; draw(); }); } }
function draw() {
  var began = performance.now(), d = (window.devicePixelRatio || 1) * (sharp ? 1 : 0.5);
  var bw = Math.max(1, Math.round(W * d)), bh = Math.max(1, Math.round(H * d));
  if (cv.width !== bw || cv.height !== bh) { cv.width = bw; cv.height = bh; }
  ctx.setTransform(d, 0, 0, d, 0, 0); ctx.globalAlpha = 1; ctx.fillStyle = C['--map']; ctx.fillRect(0, 0, W, H);
  STATS.cards = 0; STATS.image = 0; HITS = []; LINKS = []; NOBST = 0;
  if (WORDS.size > 20000) WORDS.clear();
  CHAIN = focusChain();
  var portals = portalsOf(CHAIN);
  drawMap(TOP, 1, 1);
  drawRings(CHAIN);
  drawPortals(portals, CHAIN);
  drawPath(CHAIN);
  drawHelp();
  if (HUD) drawHud(began, !sharp);
  drawn++;
}
function hashOf(id) { return id ? '#' + id.split('/').map(encodeURIComponent).join('/') : ''; }
function hashMap() {
  var id = '';
  try { id = decodeURIComponent(location.hash.slice(1)); } catch (e) { id = ''; }
  return id && MAPS[id] && MAPS[id].T ? MAPS[id] : null;
}
function currentMap() { return CHAIN.length ? CHAIN[CHAIN.length - 1].child : TOP; }
// When the camera stops: the hash and the label of the canvas name the current map.
function settled() {
  var m = currentMap(), names = [DATA.name].concat(CHAIN.map(function (c) { return c.id; }));
  cv.setAttribute('aria-label', 'System map: ' + names.join(' / ') + '. Level ' + CHAIN.length + '.');
  var want = hashOf(m.id);
  if (want !== location.hash && (want || location.hash)) {
    try { history.replaceState(null, '', want || location.pathname + location.search); } catch (e) { /* a file page can refuse it */ }
  }
}

// ---- input --------------------------------------------------------------------------
function local(e) { var r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; }
// The deepest card under a screen point that the reader can go into.
function pick(px, py) {
  var m = TOP, found = null;
  for (var d = 0; d <= DEEPEST; d++) {
    var v = view(m), lx = (px - v.ox) / v.a, ly = (py - v.oy) / v.a, near = m.cardIndex.query(lx, ly, lx, ly, []), hit = null;
    for (var i = 0; i < near.length && !hit; i++) {
      var b = near[i].b;
      if (lx >= b[0] && lx <= b[0] + b[2] && ly >= b[1] && ly <= b[1] + b[3]) hit = near[i];
    }
    if (!hit) return found;
    found = hit;
    if (!hit.child || openness(hit) < 0.5) return found;
    m = hit.child;
  }
  return found;
}
function enter(px, py) {
  var c = pick(px, py);
  if (!c) return;
  if (c.child && openness(c) < 0.5) flyTo(frameOf(c.child), 0.06);
  else if (!c.child) flyTo(worldBox(c), 0.2);
}
function goOut() {
  var n = CHAIN.length;
  flyTo(n > 1 ? frameOf(CHAIN[n - 2].child) : topFrame(), 0.06);
}
function fitCurrent() { flyTo(frameOf(currentMap()), 0.06); }
function hitAt(px, py) {
  for (var i = HITS.length - 1; i >= 0; i--) {
    var h = HITS[i];
    if (px >= h.x && px <= h.x + h.w && py >= h.y && py <= h.y + h.h) return h;
  }
  return null;
}
var pts = new Map(), drag = null, didMove = false;
cv.addEventListener('wheel', function (e) {
  e.preventDefault(); stopFlight();
  var p = local(e), dy = e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? H : 1);
  zoomAt(p[0], p[1], Math.exp(-dy * (e.ctrlKey ? 0.01 : 0.0018)));
}, {passive: false});
cv.addEventListener('pointerdown', function (e) {
  stopFlight(); cv.focus({preventScroll: true});
  var p = local(e);
  pts.set(e.pointerId, p); didMove = false;
  drag = {x: p[0], y: p[1], cx: cam.x, cy: cam.y};
  try { cv.setPointerCapture(e.pointerId); } catch (err) { /* no capture */ }
});
cv.addEventListener('pointermove', function (e) {
  if (!pts.has(e.pointerId)) { cv.style.cursor = hitAt(local(e)[0], local(e)[1]) ? 'pointer' : ''; return; }
  var prev = pts.get(e.pointerId), p = local(e);
  pts.set(e.pointerId, p);
  if (pts.size === 2) {
    var other = null;
    pts.forEach(function (v, id) { if (id !== e.pointerId) other = v; });
    var f = Math.hypot(p[0] - other[0], p[1] - other[1]) / (Math.hypot(prev[0] - other[0], prev[1] - other[1]) || 1);
    didMove = true; drag = null;
    zoomAt((p[0] + other[0]) / 2, (p[1] + other[1]) / 2, f);
    return;
  }
  if (!drag) return;
  var dx = p[0] - drag.x, dy = p[1] - drag.y;
  if (Math.abs(dx) + Math.abs(dy) > 4) { didMove = true; cv.classList.add('drag'); }
  if (!didMove) return;
  cam = {x: drag.cx - dx / cam.k, y: drag.cy - dy / cam.k, k: cam.k};
  moved();
});
function up(e) {
  var was = pts.has(e.pointerId), p = local(e);
  pts.delete(e.pointerId);
  if (!pts.size) { drag = null; cv.classList.remove('drag'); }
  if (!was || didMove || e.type === 'pointercancel') return;
  var h = hitAt(p[0], p[1]);
  if (h) { h.go(); return; }
  if (e.pointerType === 'touch') enter(p[0], p[1]);
}
cv.addEventListener('pointerup', up);
cv.addEventListener('pointercancel', up);
cv.addEventListener('dblclick', function (e) { var p = local(e); if (!hitAt(p[0], p[1])) enter(p[0], p[1]); });
window.addEventListener('keydown', function (e) {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  var step = 80 / cam.k, keys = {
    Escape: goOut, f: fitCurrent, F: fitCurrent,
    '+': function () { fly(zoomed(1.6), 260); },
    '-': function () { fly(zoomed(1 / 1.6), 260); },
    ArrowLeft: function () { cam = {x: cam.x - step, y: cam.y, k: cam.k}; moved(); },
    ArrowRight: function () { cam = {x: cam.x + step, y: cam.y, k: cam.k}; moved(); },
    ArrowUp: function () { cam = {x: cam.x, y: cam.y - step, k: cam.k}; moved(); },
    ArrowDown: function () { cam = {x: cam.x, y: cam.y + step, k: cam.k}; moved(); }
  };
  keys['='] = keys['+'];
  if (!keys[e.key]) return;
  e.preventDefault(); keys[e.key]();
});
window.addEventListener('hashchange', function () { var m = hashMap(); flyTo(m ? frameOf(m) : topFrame(), 0.06); });
function measure() { var r = cv.getBoundingClientRect(); W = Math.max(1, r.width); H = Math.max(1, r.height); }
window.addEventListener('resize', function () { measure(); request(); });
new MutationObserver(function () { readColors(); request(); })
  .observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
if (window.matchMedia) {
  var scheme = matchMedia('(prefers-color-scheme: light)');
  if (scheme.addEventListener) scheme.addEventListener('change', function () { readColors(); request(); });
}
// The page font is in the page as data. The canvas starts its load at the first text. When
// it is loaded, the measured word widths and the wrapped lines are not correct.
function fontLoaded() { textChanged(); ORDER.forEach(function (m) { m.cards.forEach(function (c) { c._wrap = null; }); }); request(); }
if (document.fonts && document.fonts.load) {
  Promise.all([document.fonts.load(font(400, 12)), document.fonts.load(font(600, 12))]).then(fontLoaded, function () { /* the system font stays */ });
}

// ---- start ----------------------------------------------------------------------------
measure(); readColors();
var start = hashMap();
cam = fitBox(start ? frameOf(start) : topFrame(), 0.06);
draw(); settled();
window.systemapCanvas = {
  ready: performance.now(),
  camera: function () { return {x: cam.x, y: cam.y, k: cam.k}; },
  // Set the camera as a move does, and draw the frame now.
  view: function (c) { stopFlight(); cam = {x: c.x, y: c.y, k: c.k}; moved(true); },
  fit: function (id) { return fitBox(id ? frameOf(MAPS[id]) : topFrame(), 0.06); },
  cardFit: function (mapId, cardId) { return fitBox(worldBox(MAPS[mapId].byId[cardId]), 0.12); },
  box: function (mapId, cardId) { var c = MAPS[mapId] && MAPS[mapId].byId[cardId]; return c ? screenBox(c) : null; },
  chain: function () { return CHAIN.map(function (c) { return c.child.id; }); },
  hits: function () { return HITS.map(function (h) { return {kind: h.kind, id: h.id, x: h.x, y: h.y, w: h.w, h: h.h}; }); },
  // The boundary flows from the portals in the last frame: the screen points of each path.
  links: function () { return LINKS; },
  // The screen boxes of the cards of a map.
  boxes: function (mapId) { return MAPS[mapId].cards.map(function (c) { return {id: c.id, b: screenBox(c)}; }); },
  maps: function () { return ORDER.map(function (m) { return {id: m.id, depth: m.depth, cards: m.cards.length, opens: m.cards.filter(function (c) { return c.child; }).map(function (c) { return c.child.id; })}; }); },
  // The camera on the cards of the top map that open a map (the measurement all-open).
  openBox: function () {
    var b = null;
    TOP.cards.forEach(function (c) {
      if (!c.child) return;
      var w = worldBox(c);
      b = b ? [Math.min(b[0], w[0]), Math.min(b[1], w[1]), Math.max(b[0] + b[2], w[0] + w[2]) - Math.min(b[0], w[0]),
        Math.max(b[1] + b[3], w[1] + w[3]) - Math.min(b[1], w[1])] : w;
    });
    return fitBox(b || topFrame(), 0.06);
  },
  // The camera on the deepest map below the first card that opens a map, or on the
  // middle card of a map without such a card (the measurement dive).
  deepFit: function () {
    var m = TOP, c;
    while ((c = m.cards.filter(function (x) { return x.child; })[0])) m = c.child;
    return m === TOP ? fitBox(worldBox(TOP.cards[TOP.cards.length >> 1]), 0.2) : fitBox(frameOf(m), 0.06);
  },
  moving: function () { return !!flight || !sharp; },
  stats: function () { return {cards: STATS.cards, image: STATS.image, drawn: drawn, width: cv.width, sharp: sharp}; }
};
"""

SCRIPT = "(function(){\n'use strict';\n" + SCENE + DRAW + _INPUT + "})();\n"

# The page embeds the script in a script element. "</" would end the element.
if "</" in SCRIPT:  # pragma: no cover - a guard for a change of the script text
    raise ValueError("The canvas script must not contain the text </.")
