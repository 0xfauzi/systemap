"""The input part of the atlas renderer: the camera, the frames, the input and the start.

`atlas_script` joins this part last. It is a fork of the input part of the canvas page
(`page_canvas`), with the camera rules of docs/design/atlas.md:

- The fit of a map. The headline is beside the map or above it. The page uses the
  position that gives the larger map: beside when the screen is wider than 1180 px and
  the fit beside the headline is as large as the fit below it (`fitBox`). A map at the fit
  has a scale of 1.6 or less.
- Phone. On a screen of 720 px or less, the map opens at a scale of 0.5 or more, at its
  top left part. The Fit control still shows the whole map.
- The details. While the details of a selected card are open on a wide screen, the fit
  of the map of the card keeps the width of the details free (`sideRight` in
  `atlas_details`).
- Pan, zoom and pinch. The wheel and a pinch zoom at the pointer, and a drag moves the
  map. A double-click with a mouse goes into the map that a card opens. A click or a tap
  selects a card or pins a line (`clickAt` and `tapAt` in `atlas_keys`). Esc closes the
  details or goes out one level, F fits the current map, + and - zoom, and the arrow keys
  move the map. In the Sequences view, the left and right arrow keys change the step
  (`seqKey` in `atlas_sequences`). Esc, F, + and - also operate while a button has the keyboard focus. The zoom control at the bottom left has the same functions and the
  readout of the scale.
- Pointing. A move of a mouse or a pen over the canvas points at the card or the line
  under it (`point` in `atlas_lit`). A card comes before a line.
- The Sequences view. The fit keeps the list of the sequences and the step bar free
  (`seqRoom`). While the diagram form shows, the canvas draws only the ground.
- The States view (`atlas_states`). The canvas draws only the ground, the arrow keys, Home,
  End and Esc are the keys of the view (`smKey`), and the map keys do not operate.
- The Focus view (`atlas_focus`). The canvas draws only the ground, the arrow keys, Home and
  Esc are the keys of the view (`fcKey`), and the map keys do not operate.
- The History view (`atlas_history`). The canvas draws only the ground, the arrow keys,
  Home, End and Esc are the keys of the view (`hsKey`), and the map keys do not operate.
- Frames. As on the canvas page: an input event asks for one frame. While the camera
  moves, the canvas has half of the device resolution. STILL_MS after the last move, the
  script draws one frame at full resolution (`atlas_image`). A change of the light draws one
  frame at half of the device resolution, and the next frame at full resolution.

`window.systemapCanvas` gives the camera and the state to the tests and the measurement
scripts, with the names of the canvas page where the function is the same. It changes
nothing on the page.
"""

from __future__ import annotations

INPUT = r"""
// ---- the camera ---------------------------------------------------------------
var FIT = 0.04, WIDE = 720, ASK_EL = document.getElementById('atlas-ask');
// The fit of a box. The frame of a map (`frameOf`) has the rule of the headline. `whole`
// shows the whole map also on a phone.
function mapFit(b, whole) {
  var m = b.m, Hs = H - HEAD_H, wide = W > WIDE, right = 24 + sideRight(m), g = seqRoom(), bottom = g.bottom, lo = g.left;
  function fitK(left, top) { return Math.min((W - left - right) / b[2], (Hs - top - bottom) / b[3], 1.6 / m.T.s); }
  // `kBeside` and `kAbove` are the two fits for the tests: beside the headline (0 when the
  // screen is too narrow) and below it.
  var kBeside = W - right > 1180 ? fitK(330, 26) : 0, kAbove = fitK(lo, wide ? 112 : g.top);
  var beside = kBeside > 0 && kBeside >= fitK(lo, 112), top = beside ? 26 : wide ? 112 : g.top, left = beside ? 330 : lo;
  var k = clamp(fitK(left, top), KMIN, KMAX);
  if (!wide && k * m.T.s < 0.5 && !whole) {
    k = 0.5 / m.T.s;
    return {x: b[0] - 14 / k, y: b[1] - (HEAD_H + top) / k, k: k, beside: beside, kBeside: kBeside, kAbove: kAbove};
  }
  var free = Hs - top - bottom - b[3] * k, lift = beside ? free / 2 : Math.min(free / 2, 10);
  return {x: b[0] + b[2] / 2 - (left + (W - left - right) / 2) / k, y: b[1] - (HEAD_H + top + lift) / k, k: k, beside: beside, kBeside: kBeside, kAbove: kAbove};
}
// The room of the fit in the Sequences view (`atlas_sequences`): the list at the left of a
// wide screen or under the headline of a phone, and the bar at the bottom.
function seqRoom() {
  if (VIEW.mode !== 'seq') return {left: 20, top: 96 + tabStrip(), bottom: 30};
  askBottom();
  var bar = BAR ? BAR.offsetHeight + 34 : 30, rail = shownEl(RAIL) ? RAIL.getBoundingClientRect() : null;
  if (W > WIDE) return {left: rail ? rail.right + 14 : 20, top: 96, bottom: bar};
  return {left: 20, top: rail ? rail.bottom - HEAD_H + 10 : 96, bottom: bar};
}
// On a phone the layer tabs are a strip under the header (`atlas_css`): give its height.
function tabStrip() {
  var t = W > WIDE ? null : document.getElementById('atlas-tabs');
  return t && getComputedStyle(t).position === 'fixed' ? t.offsetHeight : 0;
}
function fitBox(b, pad, whole) {
  if (b.m) return mapFit(b, whole);
  pad = pad === undefined ? 0.2 : pad;
  var Hs = H - HEAD_H, k = clamp(Math.min(W * (1 - 2 * pad) / b[2], Hs * (1 - 2 * pad) / b[3]), KMIN, KMAX);
  return {x: b[0] + b[2] / 2 - W / 2 / k, y: b[1] + b[3] / 2 - (HEAD_H + Hs / 2) / k, k: k};
}
var flight = null;
function stopFlight() { if (flight) { cancelAnimationFrame(flight.raf); flight = null; } }
// A flight to a box keeps the box. Thus a change of the screen size can fit it again. The
// fit of a map also puts the headline beside the map or above it.
function flyTo(box, pad, whole) {
  var to = fitBox(box, pad, whole);
  if (box.m && ASK_EL) ASK_EL.classList.toggle('beside', !!to.beside);
  fly({x: to.x, y: to.y, k: to.k});
  if (flight) { flight.box = box; flight.pad = pad; flight.whole = whole; }
}
// The scale moves in log space. The middle of the screen moves at one rate in the inverse
// of the scale, so a move with a large change of zoom does not rush at one end.
function fly(to, ms) {
  stopFlight();
  if (reduced()) { cam = to; moved(); return; }
  var from = camCopy(), Hs = H - HEAD_H;
  var c0 = [from.x + W / 2 / from.k, from.y + (HEAD_H + Hs / 2) / from.k], c1 = [to.x + W / 2 / to.k, to.y + (HEAD_H + Hs / 2) / to.k];
  var big = Math.abs(Math.log(to.k / from.k));
  ms = ms || 320 + Math.min(520, big * 190);
  var t0 = performance.now();
  function step(now) {
    var t = clamp((now - t0) / ms, 0, 1), e = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
    var k = from.k * Math.pow(to.k / from.k, e), w = big > 0.05 ? (1 / from.k - 1 / k) / (1 / from.k - 1 / to.k) : e;
    var cx = c0[0] + (c1[0] - c0[0]) * w, cy = c0[1] + (c1[1] - c0[1]) * w;
    cam = {x: cx - W / 2 / k, y: cy - (HEAD_H + Hs / 2) / k, k: k};
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
function middle() { return [W / 2, HEAD_H + (H - HEAD_H) / 2]; }
function zoomed(f) {
  var k = clamp(cam.k * f, KMIN, KMAX), p = middle(), cx = cam.x + p[0] / cam.k, cy = cam.y + p[1] / cam.k;
  return {x: cx - p[0] / k, y: cy - p[1] / k, k: k};
}

// ---- frames -------------------------------------------------------------------
var pending = false, sharp = true, stillTimer = 0, CHAIN = [], drawn = 0, LOG = null, MOVED_AT = -Infinity, SHOWN_MAP = null;
// A change of the light (`atlas_lit`) draws one frame at the moving resolution, as a camera
// move does: a full frame at rest costs about 4 times the time of a moving frame. Thus the
// lit paths come to the screen in the next frame. The frame after it is a full frame at
// rest again (`draw`), so that the map is soft for one frame only. LIGHT_MOVE is true for
// that one frame: then the text does not fade and no stored image is made.
var LIGHT_MOVE = false;
function lightMoved() {
  if (!sharp) { request(); return; }
  sharp = false; LIGHT_MOVE = true;
  clearTimeout(stillTimer);
  stillStop();
  request();
}
// After the one frame of a change of the light: the next frame is a full frame at rest.
function lightSharp() {
  if (!LIGHT_MOVE) return;
  LIGHT_MOVE = false; sharp = true;
  request();
}
function moved(now) {
  sharp = false; LIGHT_MOVE = false; MOVED_AT = performance.now();
  clearTimeout(stillTimer);
  stillTimer = setTimeout(function () { sharp = true; if (!flight) { stillStart(); settled(); } }, STILL_MS);
  stillStop();
  if (now) draw(); else request();
}
function request() {
  if (pending) return;
  pending = true;
  requestAnimationFrame(function () { pending = false; if (STILL) STILL.want = true; else draw(); });
}
function draw() {
  viewFrame(); speedFrame();
  var began = performance.now(), d = dpr() * (sharp ? 1 : 0.5);
  var bw = Math.max(1, Math.round(W * d)), bh = Math.max(1, Math.round(H * d)), el = frameCanvas();
  if (el.width !== bw || el.height !== bh) { el.width = bw; el.height = bh; }
  ctx.setTransform(d, 0, 0, d, 0, 0); ctx.globalAlpha = 1; ctx.fillStyle = C['--map']; ctx.fillRect(0, 0, W, H);
  drawGrid();
  STATS.cards = 0; STATS.image = 0;
  if (WORDS.size > 20000) WORDS.clear();
  CHAIN = focusChain();
  if (SEL && SEL.map !== currentMap()) select(null, {keep: true});
  litFrame();
  // The diagram form of a sequence (`atlas_sequences`) and the board of the States view
  // (`atlas_states`) and of the Focus view (`atlas_focus`) cover the map: only the ground
  // draws.
  if (!boardOn() && VIEW.mode !== 'states' && VIEW.mode !== 'focus' && VIEW.mode !== 'history') { drawMap(TOP, 1, 1); drawFocus(); }
  speakLater();
  if (!sharp && !LIGHT_MOVE) makeImages(began);
  if (HUD) drawHud(began, !sharp);
  frameShown();
  drawn++;
  var m = currentMap();
  if (m !== SHOWN_MAP) { SHOWN_MAP = m; headSync(true); mapChanged(m); }
  if (SIDE_ON) sideSync();
  zoomShown();
  if (LOG) LOG.push({at: began, ms: performance.now() - began, sharp: sharp, hide: HIDE, images: LAYERS});
  if (SPEED_FADING || VIEW_FADING) fadeLater();
  lightSharp();
}
var fadeTimer = 0, FADE_WAIT = 50;
function fadeLater() {
  var n = drawn;
  clearTimeout(fadeTimer);
  if (performance.now() - MOVED_AT >= FADE_WAIT) request();
  else fadeTimer = setTimeout(function () { if (drawn === n) request(); }, FADE_WAIT);
}
var FRAMES = [];
function drawHud(began, half) {
  var now = performance.now();
  FRAMES.push(now);
  while (FRAMES.length && now - FRAMES[0] > 1000) FRAMES.shift();
  var s = FRAMES.length + ' fps · draw ' + (now - began).toFixed(1) + ' ms · ' + (half ? 'half' : 'full') +
    ' · ' + STATS.cards + ' cards · ' + STATS.image + ' images';
  ctx.globalAlpha = 0.95; ctx.fillStyle = C['--surface']; ctx.fillRect(W - 330, HEAD_H + 10, 320, 26);
  text(s, W - 320, HEAD_H + 27, 12, C['--ink'], 1, 400, true);
}
function hashOf(id) { return id ? '#' + id.split('/').map(encodeURIComponent).join('/') : ''; }
function currentMap() { return CHAIN.length ? CHAIN[CHAIN.length - 1].child : TOP; }
// When the camera stops: the hash and the label of the canvas name the current map
// (`tell`). A hash that names a card of the current map stays.
function settled() {
  var m = currentMap(), want = hashOf(m.id), hc = hashCard(hashId());
  tell(m);
  afterFlight();
  if (hc && hc.map === m) want = location.hash;
  if (want !== location.hash && (want || location.hash)) setHash(want);
}

// ---- input --------------------------------------------------------------------------
function local(e) { var r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; }
// The deepest card under a screen point. The camera goes through a card whose nested map
// has the screen (`deepOf`) when the point is in the frame of that map.
function pick(px, py) {
  var m = TOP, found = null;
  for (var d = 0; d <= DEEPEST; d++) {
    var v = view(m), lx = (px - v.ox) / v.a, ly = (py - v.oy) / v.a, near = m.cardIndex.query(lx, ly, lx, ly, []), hit = null;
    for (var i = 0; i < near.length && !hit; i++) {
      var b = near[i].b;
      if (lx >= b[0] && lx <= b[0] + b[2] && ly >= b[1] && ly <= b[1] + b[3]) hit = near[i];
    }
    if (!hit) {
      var into = null;
      m.cards.forEach(function (c) {
        if (into || !c.child || deepOf(c) < 0.5) return;
        var f = frameOf(c.child), wx = cam.x + px / cam.k, wy = cam.y + py / cam.k;
        if (wx >= f[0] && wx <= f[0] + f[2] && wy >= f[1] && wy <= f[1] + f[3]) into = c;
      });
      if (!into) return found;
      m = into.child; continue;
    }
    found = hit;
    if (!hit.child || deepOf(hit) < 0.5) return found;
    m = hit.child;
  }
  return found;
}
function pickClosed(px, py) { var c = pick(px, py); return c && !(c.child && deepOf(c) >= 0.5) ? c : null; }
function enter(px, py) {
  var c = pickClosed(px, py);
  if (c && c.child) dive(c);
}
function goOut() {
  var n = CHAIN.length;
  focusOut();
  flyTo(n > 1 ? frameOf(CHAIN[n - 2].child) : topFrame(), FIT);
}
function fitCurrent(whole) { flyTo(frameOf(currentMap()), FIT, whole); }
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
  if (!pts.has(e.pointerId)) {
    var at = local(e), c = e.pointerType === 'touch' ? null : pickHere(at[0], at[1]), f = c || e.pointerType === 'touch' ? null : pickLine(at[0], at[1]);
    cv.classList.toggle('over', !TOUCH && !!(c || f));
    if (e.pointerType !== 'touch') point(c, f, 'pointer');
    return;
  }
  var prev = pts.get(e.pointerId), p = local(e);
  pts.set(e.pointerId, p);
  if (pts.size === 2) {
    var other = null;
    pts.forEach(function (v, id) { if (id !== e.pointerId) other = v; });
    // The world point at the middle of the old two points goes to the middle of the new
    // two points. Thus the point between the fingers stays under the fingers.
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
  else if (pts.size === 1 && !drag) pts.forEach(function (v) { drag = {x: v[0], y: v[1], cx: cam.x, cy: cam.y}; });
  if (!was || didMove || e.type === 'pointercancel') return;
  if (e.pointerType === 'touch') tapAt(p[0], p[1]); else clickAt(p[0], p[1], e.pointerType === 'mouse');
}
cv.addEventListener('pointerup', up);
cv.addEventListener('pointercancel', up);
cv.addEventListener('pointerleave', function () { cv.classList.remove('over'); if (HOT.from === 'pointer') point(null, null, ''); });
cv.addEventListener('dblclick', function (e) { var p = local(e); if (kind === 'mouse') enter(p[0], p[1]); });
// Esc, F, + and - also operate while a button of the page has the keyboard focus, as in the
// design study. The arrow keys of a button stay with the button (`ownKeys`).
var PAGE_KEYS = {Escape: true, f: true, F: true, '+': true, '=': true, '-': true};
window.addEventListener('keydown', function (e) {
  // In the Sequences view the left and right arrow keys change the step (`seqKey`), also
  // while a button has the keyboard focus.
  // In the States view the arrow keys, Home and End move the keyboard focus through the
  // states and the transitions, and Esc removes the light (`smKey`). The map keys do not
  // operate.
  var stepKey = VIEW.mode === 'seq' && (e.key === 'ArrowLeft' || e.key === 'ArrowRight');
  // In the Focus view the arrow keys and Home move the keyboard focus through the cards, and
  // Esc removes the light (`fcKey`).
  // In the History view the arrow keys, Home and End move the keyboard focus through the
  // names and the cells, and Esc removes the kept reading line (`hsKey`).
  var smK = (VIEW.mode === 'states' && e.key in SM_KEYS) || (VIEW.mode === 'focus' && e.key in FC_KEYS) || (VIEW.mode === 'history' && e.key in HS_KEYS);
  if (e.ctrlKey || e.metaKey || e.altKey || ownKeys(e, !!PAGE_KEYS[e.key] || stepKey || smK)) return;
  if (stepKey) { e.preventDefault(); seqKey(e); return; }
  if (VIEW.mode === 'states') { if (smK && smKey(e)) e.preventDefault(); return; }
  if (VIEW.mode === 'focus') { if (smK && fcKey(e)) e.preventDefault(); return; }
  if (VIEW.mode === 'history') { if (smK && hsKey(e)) e.preventDefault(); return; }
  var step = 80 / cam.k, keys = {
    Escape: escapeKey, f: function () { fitCurrent(); }, F: function () { fitCurrent(); },
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
function button(id, f) { var b = document.getElementById(id); if (b) b.addEventListener('click', f); }
button('atlas-zo', function () { fly(zoomed(0.8), 200); });
button('atlas-zi', function () { fly(zoomed(1.25), 200); });
button('atlas-zf', function () { fitCurrent(true); });
window.addEventListener('hashchange', function () { goTo(hashGoal()); });
function measure() {
  var r = cv.getBoundingClientRect();
  W = Math.max(1, r.width); H = Math.max(1, r.height);
  HEAD_H = HEAD_EL ? HEAD_EL.getBoundingClientRect().height : 0;
}
// After a change of the screen size, a camera at the fit of the open map fits that map
// again. Each other camera keeps the world point at the middle of the screen. On a phone
// with the details open, the selected card goes above the sheet (`showAbove`), as after a
// selection on a phone.
function atFit(m) {
  var f = fitBox(frameOf(m), FIT);
  return Math.abs(cam.k / f.k - 1) < 1e-3 && Math.abs(cam.x - f.x) * cam.k < 1 && Math.abs(cam.y - f.y) * cam.k < 1;
}
window.addEventListener('resize', function () {
  var m = currentMap(), fitted = !flight && atFit(m), w = W, h = H, cx = cam.x + W / 2 / cam.k, cy = cam.y + H / 2 / cam.k;
  var aim = flight && flight.box ? flight : null;
  measure();
  if (SIDE_ON && SEL && SEL.map === m && W <= WIDE) showAbove(SEL);
  else if (aim) flyTo(aim.box, aim.pad, aim.whole);
  else if (fitted) { var f = fitBox(frameOf(m), FIT); ASK_EL.classList.toggle('beside', !!f.beside); cam = {x: f.x, y: f.y, k: f.k}; }
  else if (!flight) {
    var k = clamp(cam.k * Math.min(W / w, H / h), KMIN, KMAX);
    cam = {x: cx - W / 2 / k, y: cy - H / 2 / k, k: k};
  }
  barHeight();
  if (boardOn()) boardDraw();
  if (smOn()) smDraw();
  if (fcOn()) fcDraw();
  if (hsOn()) hsDraw();
  request();
});
new MutationObserver(function () { readColors(); request(); })
  .observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
if (window.matchMedia) {
  var scheme = matchMedia('(prefers-color-scheme: light)');
  if (scheme.addEventListener) scheme.addEventListener('change', function () { readColors(); request(); });
}
// The page font is in the page as data. When it is loaded, the measured word widths and the
// places of the labels are not correct (TEXTS is in their key).
function fontLoaded() { textChanged(); request(); }
if (document.fonts && document.fonts.load) {
  Promise.all([document.fonts.load(font(400, 12)), document.fonts.load(font(600, 12)), document.fonts.load(font(500, 12))]).then(fontLoaded, function () { /* the system font stays */ });
}

// ---- start ----------------------------------------------------------------------------
measure(); readColors();
// A hash of a card selects the card when the first camera stops (`goTo`, `settled`).
var start = hashGoal();
if (start.card) AFTER = start.card;
var first = fitBox(start.box, start.pad);
if (start.box.m) ASK_EL.classList.toggle('beside', !!first.beside);
cam = {x: first.x, y: first.y, k: first.k};
CHAIN = focusChain(); headSync(false);
draw(); settled();
requestAnimationFrame(function () { setTimeout(buildTree, 0); });
// The screen boxes of the labels at rest of map m in the layer of the frame.
function restLabels(m) {
  var v = view(m), s = seatsOf(m, shownLayer(m), v.a);
  return s ? s.list.map(function (x) { return {s: x.e.s, f: x.e.f.i, x: v.ox + v.a * x.x, y: v.oy + v.a * x.y, hide: !!x.hide}; }) : [];
}
function linesState(id) {
  var m = MAPS[id], L = linesOf(m, shownLayer(m));
  return {n: L.n, dense: L.dense, rest: L.rest, ends: L.ends, labels: L.dense ? [] : restLabels(m),
    lanes: L.list.map(function (e) { return {f: e.f.i, q: e.q}; })};
}
window.systemapCanvas = {
  ready: performance.now(),
  get treeMs() { return TREE_MS; },
  camera: camCopy,
  view: function (c) { stopFlight(); cam = {x: c.x, y: c.y, k: c.k}; moved(true); },
  fit: function (id, whole) { var f = fitBox(frameOf(id ? MAPS[id] : TOP), FIT, whole); return {x: f.x, y: f.y, k: f.k, beside: !!f.beside, kBeside: f.kBeside, kAbove: f.kAbove}; },
  frame: function (id) { var b = frameOf(id ? MAPS[id] : TOP); return [(b[0] - cam.x) * cam.k, (b[1] - cam.y) * cam.k, b[2] * cam.k, b[3] * cam.k]; },
  box: function (mapId, cardId) { var c = MAPS[mapId] && MAPS[mapId].byId[cardId]; return c ? screenBox(c) : null; },
  boxes: function (mapId) { return MAPS[mapId].cards.map(function (c) { return {id: c.id, b: screenBox(c), k: c.k}; }); },
  chain: function () { return CHAIN.map(function (c) { return c.child.id; }); },
  // How far the nested map of each card of the chain takes the screen (`deepOf`).
  deep: function () { return CHAIN.map(deepOf); },
  current: function () { return currentMap().id; },
  maps: function () { return ORDER.map(function (m) { return {id: m.id, depth: m.depth, cards: m.cards.length, opens: m.cards.filter(function (c) { return c.child; }).map(function (c) { return c.child.id; })}; }); },
  openBox: function () {
    var b = null;
    TOP.cards.forEach(function (c) {
      if (!c.child) return;
      var w = worldBox(c);
      b = b ? [Math.min(b[0], w[0]), Math.min(b[1], w[1]), Math.max(b[0] + b[2], w[0] + w[2]) - Math.min(b[0], w[0]),
        Math.max(b[1] + b[3], w[1] + w[3]) - Math.min(b[1], w[1])] : w;
    });
    return fitBox(b || topFrame(), 0.04);
  },
  deepFit: function () {
    var m = TOP, c;
    while ((c = m.cards.filter(function (x) { return x.child; })[0])) m = c.child;
    var f = m === TOP ? fitBox(worldBox(TOP.cards[TOP.cards.length >> 1]), 0.2) : fitBox(frameOf(m), FIT, true);
    return {x: f.x, y: f.y, k: f.k};
  },
  record: function () { LOG = []; },
  recorded: function () { var l = LOG || []; LOG = null; return l; },
  texts: function () { TLOG = []; draw(); var l = TLOG; TLOG = null; return l; },
  // The texts and the geometry of one frame (`DLOG` in `atlas_draw`).
  drawn: function () { TLOG = []; DLOG = []; draw(); var o = {texts: TLOG, marks: DLOG}; TLOG = null; DLOG = null; return o; },
  keys: keyState,
  // The light, the reading line and the details (`atlas_lit`, `atlas_details`).
  lit: function () {
    return {key: LIGHT.key, map: LIGHT.m ? LIGHT.m.id : null, focus: LIGHT.focus, step: !!LIGHT.step, dim: DIM, shown: LIT_SHOWN,
      flows: LIGHT.flows ? Array.prototype.reduce.call(LIGHT.flows, function (o, v, i) { if (v) o.push(i); return o; }, []) : [],
      cards: LIGHT.cards ? Object.keys(LIGHT.cards) : [], pin: PIN ? PIN.i : null, hot: HOT.c ? HOT.c.id : HOT.f ? HOT.f.i : null, from: HOT.from};
  },
  say: function () { return {on: SAY.classList.contains('on'), text: SAY.textContent, live: SAY.getAttribute('aria-live')}; },
  side: function () { var r = SIDE.getBoundingClientRect(); return {on: SIDE_ON, hidden: SIDE.hidden, sel: SEL ? {map: SEL.map.id, id: SEL.id} : null, box: [r.left, r.top, r.width, r.height], top: SIDE.offsetTop}; },
  select: function (mapId, cardId) { var c = MAPS[mapId] && MAPS[mapId].byId[cardId]; if (c) act(c, false); return !!c; },
  pointAt: function (mapId, cardId, flow) {
    var m = MAPS[mapId];
    if (flow !== undefined && flow !== null) point(null, m.flows[flow], 'pointer'); else point(cardId ? m.byId[cardId] : null, null, 'pointer');
  },
  // The screen points of the line of flow i of a map, in the layer of the frame.
  line: function (mapId, i) { var m = MAPS[mapId], e = lineOf(m, i), v = view(m); return e ? e.d.map(function (p) { return [v.ox + v.a * p[0], v.oy + v.a * p[1]]; }) : null; },
  tabOrder: function (id) { return tabOrder(MAPS[id]).map(function (x) { return isFlow(x) ? {f: x.i} : {id: x.id}; }); },
  order: function (id) { return readingOrder(MAPS[id]).map(function (c) { return c.id; }); },
  stats: function () { return {cards: STATS.cards, image: STATS.image, flows: STATS.flows, drawn: drawn, width: (sharp || !STILL_CV ? cv : STILL_CV).width, sharp: sharp, fading: SPEED_FADING || VIEW_FADING, swap: SWAP_A}; },
  viewState: viewState,
  // The Sequences view (`atlas_sequences`).
  seq: function () { return {view: seqState(), board: boardState()}; },
  mode: setMode,
  choose: function (mapId, k) { var m = MAPS[mapId]; if (m && m.sq && m.sq[k]) seqChoose(m, k, true); return !!(m && m.sq && m.sq[k]); },
  step: stepTo,
  form: setForm,
  // The States view (`atlas_states`).
  states: smState2,
  machine: function (mapId, k) { var m = MAPS[mapId]; if (m && m.sm && m.sm[k]) smChoose(m, k); return !!(m && m.sm && m.sm[k]); },
  // The Focus view (`atlas_focus`).
  focus: fcState,
  focusOn: function (mapId, id) { var m = MAPS[mapId]; if (m && m.byId[id] && fcDegree(m)[id]) fcChoose(m, id); return !!(m && m.byId[id] && fcDegree(m)[id]); },
  // The History view (`atlas_history`).
  history: hsState,
  setLayer: setLayer,
  // The parity parts: the tools of the header (`atlas_tools`), Find (`atlas_find`) and the
  // marks of a map (`atlas_marks`).
  tools: toolsState,
  theme: themeSet,
  get find() { return FIND; },
  marks: markState,
  hash: function () { return location.hash; },
  // The lines of a map in the layer of the frame: the count, the busy layer values, the
  // labels at rest (screen points) and the laned points of each line (`atlas_lines`).
  lines: linesState,
  // The quiet value of each card of a map in the last frame.
  quiet: function (id) { return MAPS[id].cards.map(function (c) { return {id: c.id, q: quietAim(c)}; }); },
  grid: function () { return {patterns: GRID.made.size, pitch: GRID_PITCH * cam.k / Math.pow(2, Math.floor(Math.log(GRID_PITCH * cam.k / GRID_MIN) / Math.LN2)), r: GRID_R}; }
};
"""
