"""The renderer script of the canvas page: the camera, the frames and the input.

The canvas page (`canvas_page`) has one script element with `SCRIPT`. It joins the
scene part (`page_canvas_scene`), the view part (`page_canvas_view`), the drawing part (`page_canvas_draw`), the text part
(`page_canvas_text`), the image part (`page_canvas_image`), the fade part
(`page_canvas_fade`), the touch part (`page_canvas_touch`), the keyboard part
(`page_canvas_keys`), the part of the tree list (`page_canvas_tree`), the Sequences view
(`page_canvas_sequences`), the Changes view (`page_canvas_changes`), the reader tools and
the Details panel (`page_canvas_details`), the marks of the open ports
(`page_canvas_ports`), the part in this module and the Find dialog (`page_canvas_find`).
The page CSP (`page_csp`) gets the digest
of that element.

Camera. The wheel and the pinch zoom at the pointer, and a drag moves the map. A
double-click with a mouse goes into the card under the pointer, and a click selects
it (`page_canvas_details`). A tap with a finger or a
pen selects the card, and a second tap on that card goes into it when it opens a map
(`tapAt` in `page_canvas_touch`). A tap on empty space removes the selection. A gesture
with two fingers is not a tap. Esc goes out one level, F fits the current map, and + and
- zoom at the middle of the screen. The arrow keys move the map. Tab and Shift+Tab move
the keyboard focus through the cards of the current map, and Enter goes into the focused
card or selects it (`page_canvas_keys`). A camera move changes the scale in log space,
and it goes out and back in when the two views are far apart. With
`prefers-reduced-motion`, or with the page setting
Reduce motion, each move occurs at one time.

Frames. An input event asks for one frame (`requestAnimationFrame`). While the camera
moves, the canvas has half of the device resolution. STILL_MS after the last move, the
script draws one frame at full resolution. A moving frame is on a second canvas over the
page canvas, and the last moving frame fades out over the full drawing (`stillStart` in
`page_canvas_image`). While a boundary flow, the text or an image layer fades, the script
asks for more frames (`fadeLater`).

The URL hash holds the camera target: the ID of the open map, for example
`#Gateway/Routes`, or the ID of a card in a map (`page_canvas_tree`). A link with a hash
opens the canvas at that map or card. When the camera stops, the script writes the hash
of the current map with `history.replaceState`. A hash that names a card of the current
map stays. In the Changes view, the view link of the current map (`#changes` or
`#Gateway/changes`, `linkedMap` in `page_canvas_tree`) also stays.

`?hud` shows a frame readout at the top right: the frames in the last second, the time
of the last draw, the resolution, and the count of drawn cards and images. A person can
use it to measure on a real device. `window.systemapCanvas` gives the camera and the
state to the tests and the measurement scripts. It changes nothing on the page.
"""

from __future__ import annotations

from systemap.page_canvas_changes import PART as CHANGES_PART
from systemap.page_canvas_details import DETAILS
from systemap.page_canvas_draw import DRAW
from systemap.page_canvas_fade import FADE
from systemap.page_canvas_find import FIND
from systemap.page_canvas_image import IMAGE
from systemap.page_canvas_keys import KEYS
from systemap.page_canvas_ports import PORTS
from systemap.page_canvas_scene import SCENE
from systemap.page_canvas_sequences import SEQ_PART
from systemap.page_canvas_text import TEXT
from systemap.page_canvas_touch import TOUCH_PART
from systemap.page_canvas_tree import CSS as TREE_CSS
from systemap.page_canvas_tree import TREE
from systemap.page_canvas_view import VIEW_PART

# The notice of `systemap live` (`page_live.NOTICE_ID`) is over the help line of the canvas,
# not on it. The notice has a style attribute, thus the rule has !important.
CSS = (
    """
html,body{margin:0;height:100%;overflow:hidden;background:var(--map)}
#canvas{position:fixed;inset:0;width:100%;height:100%;display:block;touch-action:none;
outline:none;cursor:grab}
#canvas.drag{cursor:grabbing}
#canvas:focus-visible{box-shadow:inset 0 0 0 2px var(--accent)}
#still{position:fixed;inset:0;width:100%;height:100%;display:block;pointer-events:none}
#still[hidden]{display:none}
#canvas:focus-visible+#still{box-shadow:inset 0 0 0 2px var(--accent)}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);
white-space:nowrap}
#live-notice{bottom:44px!important}
"""
    + TREE_CSS
)

_INPUT = r"""
// ---- the camera ---------------------------------------------------------------
// The camera that fits a world box in the screen. It keeps the bands of the header, the
// path, the portals and the help line free (`gutters`).
// `pad` is the margin at each side, as a part of the screen size below the header. The fit
// of a map has the margin FIT. Thus a wide map fills 92 % of the width of a phone screen.
// The middle of the box goes to the middle of the free box without the header band, and
// lower only as far as necessary to keep the box in the free box. Thus the header does not
// move the fit of a box that is not as high as the free box.
var FIT = 0.04;
function fitBox(b, pad) {
  pad = pad === undefined ? FIT : pad;
  var g = gutters(), sx = Math.max(W * pad, g.x), free = H - HEAD_H - 56;
  var top = Math.max(HEAD_H + 48 + free * pad, g.top), bottom = Math.max(8 + free * pad, g.bottom);
  var k = clamp(Math.min(Math.max(1, W - 2 * sx) / b[2], Math.max(1, H - top - bottom) / b[3]), KMIN, KMAX);
  var half = b[3] * k / 2, lo = top + half, hi = H - bottom - half, mid = (top - HEAD_H + H - bottom) / 2;
  mid = lo <= hi ? clamp(mid, lo, hi) : (top + H - bottom) / 2;
  return {x: b[0] + b[2] / 2 - W / 2 / k, y: b[1] + b[3] / 2 - mid / k, k: k};
}
var flight = null;
function stopFlight() { if (flight) { cancelAnimationFrame(flight.raf); flight = null; } }
// A flight to a box keeps the box. Thus a change of the screen size can fit it again.
function flyTo(box, pad) { fly(fitBox(box, pad)); if (flight) { flight.box = box; flight.pad = pad; } }
// The scale moves in log space. When the two views are far apart, the path goes out and
// back in, so that the reader sees where the camera goes.
function fly(to, ms) {
  stopFlight();
  if (reduced()) { cam = to; moved(); return; }
  var from = camCopy();
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
// A zoom by `f` at the screen point px, py. The world point at that point goes to the
// screen point qx, qy (by default px, py).
function zoomAt(px, py, f, qx, qy) {
  var wx = cam.x + px / cam.k, wy = cam.y + py / cam.k, k = clamp(cam.k * f, KMIN, KMAX);
  cam = {x: wx - (qx === undefined ? px : qx) / k, y: wy - (qy === undefined ? py : qy) / k, k: k};
  moved();
}
function topFrame() { return frameOf(TOP); }
// The camera after a zoom by `f` at the middle of the screen, in the zoom limits.
function zoomed(f) {
  var k = clamp(cam.k * f, KMIN, KMAX), cx = cam.x + W / 2 / cam.k, cy = cam.y + H / 2 / cam.k;
  return {x: cx - W / 2 / k, y: cy - H / 2 / k, k: k};
}

// ---- frames -------------------------------------------------------------------
var pending = false, sharp = true, stillTimer = 0, CHAIN = [], drawn = 0, LOG = null, MOVED_AT = -Infinity;
// A camera change: draw at half resolution now, and at full resolution when it stops.
function moved(now) {
  sharp = false; MOVED_AT = performance.now();
  clearTimeout(stillTimer);
  stillTimer = setTimeout(function () { sharp = true; if (!flight) { stillStart(); settled(); } }, STILL_MS);
  stillStop();
  if (now) draw(); else request();
}
// A request during the fade after a stop waits for the end of that fade (`stillFrame`).
function request() {
  if (pending) return;
  pending = true;
  requestAnimationFrame(function () { pending = false; if (STILL) STILL.want = true; else draw(); });
}
function draw() {
  speedFrame(); viewFrame();
  var began = performance.now(), d = dpr() * (sharp ? 1 : 0.5);
  var bw = Math.max(1, Math.round(W * d)), bh = Math.max(1, Math.round(H * d)), el = frameCanvas();
  if (el.width !== bw || el.height !== bh) { el.width = bw; el.height = bh; }
  ctx.setTransform(d, 0, 0, d, 0, 0); ctx.globalAlpha = 1; ctx.fillStyle = C['--map']; ctx.fillRect(0, 0, W, H);
  STATS.cards = 0; STATS.image = 0; HITS = []; LINKS = []; NOBST = 0;
  if (WORDS.size > 20000) WORDS.clear();
  CHAIN = focusChain();
  fadeFrame(); selFrame();
  drawMap(TOP, 1, 1);
  drawRings(CHAIN);
  drawSelected();
  // The portals keep off the boxes that the maps put in OBST (`dodge`).
  NMAP = NOBST;
  var portals = portalsOf(CHAIN), path = pathParts(CHAIN);
  drawPortals(portals, path);
  drawPlates(path);
  drawPath(path);
  drawHelp();
  drawFocus();
  if (!sharp) makeImages(began);
  if (HUD) drawHud(began, !sharp);
  frameShown();
  drawn++;
  if (LOG) LOG.push({at: began, ms: performance.now() - began, sharp: sharp, fine: sharp, hide: HIDE, images: LAYERS});
  if (FADING || SPEED_FADING || SEL_FADING || VIEW_FADING) fadeLater();
}
// A boundary flow that fades asks for more frames (`FADING`), and so does a fade of the image
// layer or of the text that MOVE_TEXT hides (`SPEED_FADING`), and so does the selection
// (`SEL_FADING`), and so does a change of the view (`VIEW_FADING`). While the camera moves, the moves give the frames. Thus, in the FADE_WAIT
// ms after a camera change, the script asks for a frame only when no frame comes in
// FADE_WAIT ms. Later, it asks for the next frame. A move that draws in its own animation
// frame (a flight, or `view`) thus gets no second draw in the same frame.
var fadeTimer = 0, FADE_WAIT = 50;
function fadeLater() {
  var n = drawn;
  clearTimeout(fadeTimer);
  if (performance.now() - MOVED_AT >= FADE_WAIT) request();
  else fadeTimer = setTimeout(function () { if (drawn === n) request(); }, FADE_WAIT);
}
function hashOf(id) { return id ? '#' + id.split('/').map(encodeURIComponent).join('/') : ''; }
function currentMap() { return CHAIN.length ? CHAIN[CHAIN.length - 1].child : TOP; }
// When the camera stops: the hash and the label of the canvas name the current map
// (`tell`). A hash that names a card of the current map stays.
function settled() {
  var m = currentMap(), want = hashOf(m.id), hc = hashCard(hashId());
  tell(m);
  if (hc && hc.map === m) want = location.hash;
  if (VIEW.mode === 'changes' && linkedMap(hashId()) === m) want = location.hash;
  if (want !== location.hash && (want || location.hash)) setHash(want);
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
// The card under a screen point, when it is not open. An open card is empty space: its map
// is on the screen.
function pickClosed(px, py) { var c = pick(px, py); return c && !(c.child && openness(c) >= 0.5) ? c : null; }
function enter(px, py) {
  var c = pickClosed(px, py);
  if (c) flyGoal(goalOf(c.map, c, null));
}
function goOut() {
  var n = CHAIN.length;
  focusOut();
  flyTo(n > 1 ? frameOf(CHAIN[n - 2].child) : topFrame(), FIT);
}
function fitCurrent() { flyTo(frameOf(currentMap()), FIT); }
function hitAt(px, py) {
  for (var i = HITS.length - 1; i >= 0; i--) {
    var h = HITS[i];
    if (px >= h.x && px <= h.x + h.w && py >= h.y && py <= h.y + h.h) return h;
  }
  return null;
}
// `multi` is true when the gesture has had two pointers. Such a gesture is not a tap.
// `kind` is the pointer type of the last pointer that went down.
var pts = new Map(), drag = null, didMove = false, multi = false, kind = 'mouse';
cv.addEventListener('wheel', function (e) {
  e.preventDefault(); stopFlight();
  var p = local(e), dy = e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? H : 1);
  zoomAt(p[0], p[1], Math.exp(-dy * (e.ctrlKey ? 0.01 : 0.0018)));
}, {passive: false});
cv.addEventListener('pointerdown', function (e) {
  stopFlight(); cv.focus({preventScroll: true});
  var p = local(e);
  pts.set(e.pointerId, p); didMove = false; multi = multi || pts.size > 1; kind = e.pointerType;
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
    // Each finger gives its own event. The world point at the middle of the old two points
    // goes to the middle of the new two points. Thus the point between the fingers stays
    // under the fingers.
    var f = Math.hypot(p[0] - other[0], p[1] - other[1]) / (Math.hypot(prev[0] - other[0], prev[1] - other[1]) || 1);
    didMove = true; drag = null;
    zoomAt((prev[0] + other[0]) / 2, (prev[1] + other[1]) / 2, f, (p[0] + other[0]) / 2, (p[1] + other[1]) / 2);
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
  var was = pts.has(e.pointerId) && !multi, p = local(e);
  pts.delete(e.pointerId);
  if (!pts.size) { drag = null; multi = false; cv.classList.remove('drag'); }
  // After a pinch, the pointer that stays down moves the map.
  else if (pts.size === 1 && !drag) pts.forEach(function (v) { drag = {x: v[0], y: v[1], cx: cam.x, cy: cam.y}; });
  if (!was || didMove || e.type === 'pointercancel') return;
  var h = hitAt(p[0], p[1]);
  if (h) { h.go(); return; }
  // A click with a mouse selects the card, for the Details panel. Only a tap goes in.
  // Only the main button selects: a right click or a middle click does not.
  if (e.pointerType !== 'mouse') tapAt(p[0], p[1]); else if (e.button === 0) select(pickClosed(p[0], p[1]));
}
cv.addEventListener('pointerup', up);
cv.addEventListener('pointercancel', up);
// Two taps can also give a double-click. Only a double-click with a mouse goes in.
cv.addEventListener('dblclick', function (e) { var p = local(e); if (kind === 'mouse' && !hitAt(p[0], p[1])) enter(p[0], p[1]); });
// The camera keys do not operate in a control of the header, a text field or a dialog (`ownKeys`).
window.addEventListener('keydown', function (e) {
  if (e.ctrlKey || e.metaKey || e.altKey || ownKeys(e)) return;
  var step = 80 / cam.k, keys = {
    Escape: goOut, f: fitCurrent, F: fitCurrent,
    '+': function () { fly(zoomed(1.6), 260); },
    '-': function () { fly(zoomed(1 / 1.6), 260); },
    ArrowLeft: function () { stopFlight(); cam = {x: cam.x - step, y: cam.y, k: cam.k}; moved(); },
    ArrowRight: function () { stopFlight(); cam = {x: cam.x + step, y: cam.y, k: cam.k}; moved(); },
    ArrowUp: function () { stopFlight(); cam = {x: cam.x, y: cam.y - step, k: cam.k}; moved(); },
    ArrowDown: function () { stopFlight(); cam = {x: cam.x, y: cam.y + step, k: cam.k}; moved(); }
  };
  keys['='] = keys['+'];
  if (!keys[e.key]) return;
  e.preventDefault(); keys[e.key]();
});
window.addEventListener('hashchange', function () { flyGoal(hashGoal()); });
function measure() { var r = cv.getBoundingClientRect(); W = Math.max(1, r.width); H = Math.max(1, r.height); headMeasure(); }
// After a change of the screen size (a phone that turns, for example), a camera at the fit
// of the open map fits that map again. Each other camera keeps the world point at the middle
// of the screen, and it shows all of the world box that was on the screen before.
function atFit(m) {
  var f = fitBox(frameOf(m), FIT);
  return Math.abs(cam.k / f.k - 1) < 1e-3 && Math.abs(cam.x - f.x) * cam.k < 1 && Math.abs(cam.y - f.y) * cam.k < 1;
}
window.addEventListener('resize', function () {
  var m = currentMap(), fitted = !flight && atFit(m), w = W, h = H, cx = cam.x + W / 2 / cam.k, cy = cam.y + H / 2 / cam.k;
  var aim = flight && flight.box ? flight : null;
  measure();
  // A flight to a box goes to the fit of that box on the new screen.
  if (aim) flyTo(aim.box, aim.pad);
  else if (fitted) cam = fitBox(frameOf(m), FIT);
  else if (!flight) {
    var k = clamp(cam.k * Math.min(W / w, H / h), KMIN, KMAX);
    cam = {x: cx - W / 2 / k, y: cy - H / 2 / k, k: k};
  }
  request();
});
new MutationObserver(function () { readColors(); request(); })
  .observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
if (window.matchMedia) {
  var scheme = matchMedia('(prefers-color-scheme: light)');
  if (scheme.addEventListener) scheme.addEventListener('change', function () { readColors(); request(); });
}
// The page font is in the page as data. The canvas starts its load at the first text. When
// it is loaded, the measured word widths and the wrapped lines are not correct.
function fontLoaded() {
  headMeasure(); textChanged(); ORDER.forEach(function (m) { m.cards.forEach(function (c) { c._wrap = null; }); }); request();
  var list = warmList();
  idle(function () { warm(list, 0); });
}
// The first text in a new font, and the first measure of a word, are slow. Thus, after the
// font is loaded, the script sets each font that the drawing can use, and it measures the
// name and the words of each card. It does this in the idle time of the page, in slices of
// WARM_MS.
var WARM_MS = 4;
function warmList() {
  var list = [], words = new Set();
  for (var s = MIN_TEXT; s <= 26; s += 0.5) {
    list.push(font(400, s), font(600, s));
    if (s <= 13) list.push(font(500, s));
    if (s <= 19) list.push(font(400, s, true));
  }
  ORDER.forEach(function (m) {
    m.cards.forEach(function (c) {
      list.push([c.id, 600]);
      (String(c.p || '') + ' ' + String(c.d || '')).split(/\s+/).forEach(function (w) { if (w) words.add(w); });
    });
  });
  words.forEach(function (w) { list.push([w, 400]); });
  return list;
}
function warm(list, at) {
  var t0 = performance.now();
  while (at < list.length && performance.now() - t0 < WARM_MS) {
    var x = list[at++];
    if (typeof x === 'string') { ctx.font = x; ctx.measureText('Ag'); } else unitWidth(x[0], x[1]);
  }
  if (at < list.length) idle(function () { warm(list, at); });
}
function idle(f) { if (window.requestIdleCallback) requestIdleCallback(f); else setTimeout(f, 0); }
if (document.fonts && document.fonts.load) {
  Promise.all([document.fonts.load(font(400, 12)), document.fonts.load(font(600, 12))]).then(fontLoaded, function () { /* the system font stays */ });
}

// ---- start ----------------------------------------------------------------------------
measure(); readColors(); headSync();
var start = hashGoal();
cam = fitBox(start.box, start.pad);
draw(); settled();
// The list of the tree is written after the first frame is on the screen.
requestAnimationFrame(function () { setTimeout(buildTree, 0); });
window.systemapCanvas = {
  ready: performance.now(),
  // The time in ms to write the list of the tree (`buildTree`), or null before the list is
  // written.
  get treeMs() { return TREE_MS; },
  camera: camCopy,
  // Set the camera as a move does, and draw the frame now.
  view: function (c) { stopFlight(); cam = {x: c.x, y: c.y, k: c.k}; moved(true); },
  fit: function (id) { return fitBox(id ? frameOf(MAPS[id]) : topFrame(), FIT); },
  // The screen box of the frame of a map.
  frame: function (id) { var b = frameOf(id ? MAPS[id] : TOP); return [(b[0] - cam.x) * cam.k, (b[1] - cam.y) * cam.k, b[2] * cam.k, b[3] * cam.k]; },
  box: function (mapId, cardId) { var c = MAPS[mapId] && MAPS[mapId].byId[cardId]; return c ? screenBox(c) : null; },
  chain: function () { return CHAIN.map(function (c) { return c.child.id; }); },
  // The selected card (`id` and `map`, or null), and each card that the frame draws as
  // selected, with its alpha.
  selected: function () {
    return {id: SEL_C ? SEL_C.id : null, map: SEL_C ? SEL_C.map.id : null,
      shown: SELS.map(function (e) { return {id: e.c.id, map: e.c.map.id, alpha: e.a}; })};
  },
  // The targets of the last frame. `box` is the drawn box of a portal when the target is larger.
  hits: function () { return HITS.map(function (h) { return {kind: h.kind, id: h.id, map: h.map, show: h.show, x: h.x, y: h.y, w: h.w, h: h.h, box: h.box}; }); },
  // The boundary flows from the portals in the last frame: the screen points of each path.
  links: function () { return LINKS; },
  // The layer of the boundary flows of the last frame, and the screen box that it put on
  // the screen, or null when the frame put no layer on the screen.
  layer: function () { return LUSED && LCLEAR ? {canvas: LAYER, box: LCLEAR} : null; },
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
    return fitBox(b || topFrame(), FIT);
  },
  // The camera on the deepest map below the first card that opens a map, or on the
  // middle card of a map without such a card (the measurement dive).
  deepFit: function () {
    var m = TOP, c;
    while ((c = m.cards.filter(function (x) { return x.child; })[0])) m = c.child;
    return m === TOP ? fitBox(worldBox(TOP.cards[TOP.cards.length >> 1]), 0.2) : fitBox(frameOf(m), FIT);
  },
  // The bands that the camera fit keeps free, the screen boxes x, y, w, h of the plates of
  // the path and the help line, and the text of the help line.
  layout: function () {
    return {gutters: gutters(), path: pathPlate(pathParts(CHAIN)), help: helpPlate(), line: helpLine()};
  },
  // The boxes of the maps in OBST of the last frame, as x0, y0, x1, y1 and the opacity:
  // the cards, the flow label plates and the texts. The portals keep off them (`dodge`).
  obstacles: function () {
    var out = [];
    for (var i = 0; i < NMAP; i += OB) out.push([OBST[i], OBST[i + 1], OBST[i + 2], OBST[i + 3], OBST[i + 5]]);
    return out;
  },
  // Start a record of each frame that the screen shows: its start, its draw time in ms,
  // `sharp`, `fine` (the full drawing at full resolution, with no part of the last moving
  // frame), HIDE, and for each large map with an image layer, the value of the layer (`v`)
  // and the part of each image in the result (`parts`). `recorded` gives the record and
  // stops it.
  record: function () { LOG = []; },
  recorded: function () { var l = LOG || []; LOG = null; return l; },
  // Draw the frame again, and give each text that it draws (`drawnText`).
  texts: function () { TLOG = []; draw(); var l = TLOG; TLOG = null; return l; },
  // The keyboard focus, the selected card and the ring (`keyState`), and the reading order
  // of the cards of a map.
  keys: keyState,
  order: function (id) { return readingOrder(MAPS[id]).map(function (c) { return c.id; }); },
  stats: function () { return {cards: STATS.cards, image: STATS.image, drawn: drawn, width: (sharp || !STILL_CV ? cv : STILL_CV).width, sharp: sharp}; },
  // The view: `viewState` gives the mode, the layer, the epoch, the fade of each mode, the
  // height of the header and the count of seam calls of the last frame (`page_canvas_view`).
  // `setView` sets the mode and the layer as the header does, and gives true for a change.
  // `viewLog` starts a record of the fade of each mode and the values of the cards and the
  // flows in each frame, and `viewLogged` gives it and stops it.
  viewState: viewState,
  setView: setView,
  viewLog: function () { VIEW_LOG = {frames: []}; },
  viewLogged: function () { var l = VIEW_LOG ? VIEW_LOG.frames : []; VIEW_LOG = null; return l; },
  // The Changes view (`page_canvas_changes`): `changes` gives the fade of the view, the text
  // of its bar, and the mark and the alpha of each card of a map. `viewLog` records the fade
  // of each view in each frame (`show`).
  changes: changeState,
  // The open ports (`page_canvas_ports`): the words, the tag and the alpha of the mark of
  // each marked card of a map.
  ports: portState,
  // The Sequences view (`page_canvas_sequences`): `seqState` gives the sequence, the mode,
  // the step and the flows and the cards of the route. `seqLog` starts a record of the
  // marks of the route in each frame, and `seqLogged` gives it and stops it.
  seqState: seqState,
  seqLog: function () { SEQ_LOG = []; },
  seqLogged: function () { var l = SEQ_LOG || []; SEQ_LOG = null; return l; }
};
"""

SCRIPT = (
    "(function(){\n'use strict';\n"
    + SCENE
    + VIEW_PART
    + DRAW
    + TEXT
    + IMAGE
    + FADE
    + TOUCH_PART
    + KEYS
    + TREE
    + SEQ_PART
    + CHANGES_PART
    + DETAILS
    + PORTS
    + _INPUT
    + FIND
    + "})();\n"
)

# The page embeds the script in a script element. "</" would end the element.
if "</" in SCRIPT:  # pragma: no cover - a guard for a change of the script text
    raise ValueError("The canvas script must not contain the text </.")
