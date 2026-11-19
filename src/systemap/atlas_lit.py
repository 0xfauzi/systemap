"""The lit part of the atlas renderer: pointing, the lit paths and the reading line.

`atlas_script` joins this part after the drawing part (`atlas_draw`). The rules are the
section "Map view: the rules" of docs/design/atlas.md:

- Pointing at a card. The flows of the card in the layer of the frame are lit: each one
  gets the color of its kind and draws one time in the direction of the flow, from the
  source to the target, in DRAW_MS. Their labels show and do not cover each other
  (`litSeats`). A label covers no card name: with no free place, it draws below the
  cards. The other cards and lines go back. A card with no flow in the layer does not
  make the map go back.
- Pointing at a line. That flow is lit, and the reading line gives the source, the
  target, the artifact and the relation sentence of the model.
- The step of a sequence. With no pointed item, no pin and no selected card, the current
  step of the Sequences view is the light of its map (`stepSource` in `atlas_sequences`).
  It does not make the other cards and lines go back.
- The reading line is one line of text at the bottom of the map for the thing under the
  pointer, or for the item that has the keyboard focus. It is a polite live region.

The source of the light, in this order: the pointed card or line (`HOT`: the pointer, the
keyboard focus or a flow row of the details), the pinned line (`PIN`: a click, a tap or
Enter on a line), and the selected card (`SEL`). Only the current map has a light. The
light fades in and out in DIM_MS (`DIM`): the old lit paths stay while the light fades
out. With reduced motion, no line draws and no value fades.

The lit paths draw only in the normal drawing of the page canvas, not in a stored image.
"""

from __future__ import annotations

LIT = r"""
// ---- the light: the pointed item, the pinned line and the selected card ----------------
// HOT.from is 'pointer', 'key' or 'row'.
var HOT = {c: null, f: null, from: ''}, PIN = null, SEL = null;
var LIGHT = {key: '', m: null, c: null, f: null, flows: null, cards: null, n: 0, focus: false, t0: Object.create(null), seats: null};
var DIM = 0, DIM_MS = 200, DRAW_MS = 420, DIM_LAST = 0, LIT_SHOWN = 0;
var SAY = document.getElementById('atlas-say'), NOTE_EL = document.getElementById('atlas-note'), SAID_KEY = '';
function isFlow(x) { return !!x && !x.b; }
// The card or the flow that gives the light in this frame, in the current map.
function lightSource() {
  var m = currentMap();
  if (HOT.c && HOT.c.map === m) return {m: m, c: HOT.c, f: null};
  if (HOT.f && HOT.f.map === m) return {m: m, c: null, f: HOT.f};
  if (PIN && PIN.map === m) return {m: m, c: null, f: PIN};
  if (SEL && SEL.map === m) return {m: m, c: SEL, f: null};
  return stepSource(m) || {m: m, c: null, f: null};
}
// Calculate the light of this frame. A new light keeps the start time of each flow that was
// lit before, so that a flow draws one time.
function litFrame() {
  var s = lightSource(), id = shownLayer(s.m), now = performance.now(), dt = DIM_LAST ? now - DIM_LAST : Infinity;
  var key = s.step ? s.step : s.c ? 'c' + s.m.oi + ':' + s.c.i : s.f ? 'f' + s.m.oi + ':' + s.f.i : '';
  DIM_LAST = now;
  if (key) key += '|' + id;
  if (key !== LIGHT.key && key) LIGHT = newLight(s, id, key, now);
  else if (key !== LIGHT.key) {
    LIGHT.key = ''; LIGHT.focus = false; LIGHT.c = null; LIGHT.f = null;
  }
  var to = LIGHT.focus ? 1 : 0;
  DIM = reduced() ? to : approach(DIM, to, Math.min(0.25, dt / DIM_MS));
  if (DIM !== to) VIEW_FADING = true;
  if (!DIM && !LIGHT.key) LIGHT.m = null;
}
// A new light from the source s in the layer `id`. The light of a step of a sequence
// (`stepSource` in `atlas_sequences`) has `step`: it also lights the cards of the step, and
// the other cards and lines do not go back.
function newLight(s, id, key, now) {
  var fl = layerFlags(s.m, id).flow, flows = new Uint8Array(s.m.flows.length), cards = Object.create(null), n = 0, t0 = Object.create(null);
  s.m.flows.forEach(function (f, i) {
    if (!fl[i] || !(s.f ? f === s.f : !!s.c && (f.s === s.c.id || f.t === s.c.id))) return;
    flows[i] = 1; n++; cards[f.s] = true; cards[f.t] = true;
    t0[i] = LIGHT.m === s.m && LIGHT.focus && LIGHT.flows[i] ? LIGHT.t0[i] : reduced() ? -Infinity : now;
  });
  if (s.c) cards[s.c.id] = true;
  (s.cards || []).forEach(function (id) { if (s.m.byId[id]) cards[id] = true; });
  var many = Object.keys(cards).length;
  return {key: key, m: s.m, c: s.c, f: s.f, flows: flows, cards: cards, n: n, focus: n > 0 || (!!s.step && many > 0), step: !!s.step, t0: t0, seats: null};
}
// The light of map m in this frame, or null.
function litOf(m) { return LIGHT.m === m && (DIM > 0 || LIGHT.key) && (ctx === PAGE_CTX || ctx === STILL_CTX) && !VIEW_AIM ? LIGHT : null; }
// The part of lit flow i that is drawn: from 0 to 1, with an ease out.
function drawnPart(i) {
  var t = clamp((performance.now() - LIGHT.t0[i]) / DRAW_MS, 0, 1);
  if (t < 1) VIEW_FADING = true;
  return 1 - Math.pow(1 - t, 3);
}
// The factor of the alpha of a line or a card that the light makes go back.
function backLine(lit, i) { return lit && !lit.step && !lit.flows[i] ? 1 - 0.78 * DIM : 1; }
function backCard(lit, c) { return lit && !lit.step && !lit.cards[c.id] ? 1 - 0.66 * DIM : 1; }
// True when the card has the outline of the ink: it is pointed, selected, or at an end of
// a lit flow.
function inkCard(c) {
  if (VIEW_AIM) return false;
  var lit = litOf(c.map);
  return c === SEL || (HOT.c === c) || (!!lit && DIM > 0.5 && !!lit.cards[c.id]);
}

// ---- the lit lines -----------------------------------------------------------------
// Each lit line draws over its line at rest: a wide casing in the color of the ground, the
// wire in the color of its kind, and the dot and the arrowhead in that color. The wire
// draws from its source to its target with a dash that grows (`drawnPart`).
var LIT_CASE = 7, LIT_WIRE = 2;
function drawLit(m, L, a, ox, oy, alpha) {
  var lit = litOf(m);
  if (!lit || alpha * DIM <= 0.02) return;
  var cw = Math.min(LIT_CASE, LIT_CASE * a * 1.5), ww = clamp(LIT_WIRE * a * 1.5, 0.8, LIT_WIRE), al = alpha * DIM;
  var s = clamp(7.5 * a, 2.5, 9), w = s * 0.48, r = clamp(2 * a, 0.8, 2.6);
  ctx.lineJoin = 'round';
  L.list.forEach(function (e) {
    var i = e.f.i;
    if (!lit.flows[i]) return;
    var part = drawnPart(i), color = kindColor(e.f.k), len = e.len * a + 6;
    ctx.globalAlpha = al; ctx.setLineDash([]);
    ctx.beginPath(); cutLine(ctx, e.d, ox, oy, a);
    ctx.strokeStyle = C['--map']; ctx.lineWidth = cw; ctx.stroke();
    if (part < 1) { ctx.setLineDash([len, len]); ctx.lineDashOffset = len * (1 - part); }
    ctx.strokeStyle = color; ctx.lineWidth = ww; ctx.stroke();
    ctx.setLineDash([]); ctx.lineDashOffset = 0;
    var p = e.q, n = p.length, z = [ox + a * p[n - 1][0], oy + a * p[n - 1][1]], y = [ox + a * p[n - 2][0], oy + a * p[n - 2][1]];
    ctx.fillStyle = color; ctx.beginPath();
    ctx.arc(ox + a * p[0][0], oy + a * p[0][1], r, 0, 2 * Math.PI);
    if (part >= 1) arrowHead(ctx, z, y, s, w);
    ctx.fill();
    if (DLOG) logged({t: 'lit', f: i, k: e.f.k, color: color, alpha: al, casing: cw, wire: ww, part: part, dash: part < 1 ? [len, len * (1 - part)] : null,
      p: e.d.map(function (v) { return [ox + a * v[0], oy + a * v[1]]; })});
  });
  LIT_SHOWN = performance.now();
}
// The places of the labels of the lit lines of map m at the scale a. A lit line with a
// label at rest keeps that place. Each other lit line gets a place among the lit lines
// only: on its line, on no card, on no name and on no other label, and with no other lit
// line through it. Then without the lines, then near the line (`stacked`). The places are calculated
// again for a new light, a new layer or a new step of zoom, in the full drawing at rest.
function litSeats(m, id, a, lit) {
  var step = Math.floor(Math.log2(a) * 4), key = lit.key + '|' + step + '|' + TEXTS;
  if (lit.seats && (lit.seats.key === key || !sharp)) return lit.seats;
  var L = linesOf(m, id), rest = L.dense ? null : seatsOf(m, id, a), low = Math.pow(2, step / 4), fs = labelPx(low) / low;
  var list = L.list.filter(function (e) { return lit.flows[e.f.i]; }), wall = walls(m), taken = [], out = [], done = Object.create(null);
  if (rest) {
    fs = rest.fs;
    rest.list.forEach(function (s) { if (lit.flows[s.e.f.i]) { done[s.e.f.i] = true; out.push(s); taken.push(s.box); } });
  }
  list.slice().sort(function (u, v) { return u.len - v.len; }).forEach(function (e) {
    if (done[e.f.i]) return;
    var at = seat(e, fs, wall, taken, list) || seat(e, fs, wall, taken, []) || stacked(e, fs, taken, wall);
    taken.push(at.box); out.push({e: e, x: at.x, y: at.y, box: at.box, under: !!at.under});
  });
  lit.seats = {key: key, list: out, fs: fs};
  return lit.seats;
}
// A place near the middle of a part of the line, on no label of `taken` and on no box of
// `wall`: at the part, or one to three label heights above or below it. The longest part
// comes first. With no such place, the label is at the middle of the line, moved up while
// it covers a label of `taken`. When that place is on a card, the label draws below the
// cards (`under`), as in the design study. Thus a label never hides the name of a card.
function stacked(e, fs, taken, wall) {
  var q = e.q, w = unitWidth(e.s, 500) * fs + 8, hh = fs * 1.35, parts = [];
  function boxAt(x, y) { return [x - w / 2, y - hh / 2, x + w / 2, y + hh / 2]; }
  function free(b) { return !taken.some(function (o) { return over(b, o); }) && !wall.some(function (o) { return over(b, o); }); }
  for (var i = 0; i + 1 < q.length; i++) parts.push({x: (q[i][0] + q[i + 1][0]) / 2, y: (q[i][1] + q[i + 1][1]) / 2, l: segLen(q, i)});
  parts.sort(function (u, v) { return v.l - u.l; });
  var shifts = [0, -1, 1, -2, 2, -3, 3];
  for (var p = 0; p < parts.length; p++) {
    for (var k = 0; k < shifts.length; k++) {
      var y = parts[p].y + shifts[k] * hh, b = boxAt(parts[p].x, y);
      if (free(b)) return {x: parts[p].x, y: y, box: b};
    }
  }
  var j = Math.floor((q.length - 1) / 2), c = [(q[j][0] + q[j + 1][0]) / 2, (q[j][1] + q[j + 1][1]) / 2], box = boxAt(c[0], c[1]), n = 0;
  while (n++ < 6 && taken.some(function (o) { return over(box, o); })) { c[1] -= hh; box[1] -= hh; box[3] -= hh; }
  return {x: c[0], y: c[1], box: box, under: wall.some(function (o) { return over(box, o); })};
}
// The labels of the lit lines. `under` true draws the labels that draw below the cards, and
// false draws the other labels, over the cards.
function drawLitLabels(m, id, a, ox, oy, alpha, under) {
  var lit = litOf(m), fs = q(labelPx(a));
  if (!lit || !lit.focus || fs < textMin() || alpha * DIM <= 0.02) return;
  var seats = litSeats(m, id, a, lit);
  ctx.font = font(500, fs); ctx.textAlign = 'center'; ctx.lineJoin = 'round'; ctx.setLineDash([]);
  seats.list.forEach(function (s) {
    if (!!s.under !== under) return;
    var x = ox + a * s.x, y = oy + a * s.y + fs * 0.34;
    ctx.globalAlpha = alpha * DIM; ctx.strokeStyle = C['--map']; ctx.lineWidth = 5; ctx.strokeText(s.e.s, x, y);
    text(s.e.s, x, y, fs, C['--ink'], alpha * DIM, 500, false, 'center');
    if (DLOG) logged({t: 'litLabel', f: s.e.f.i, s: s.e.s, x: x, y: y, under: under, box: labelBox(s.box, a, ox, oy)});
  });
}
// The ring of the selected card: a wide ring in the color of the halo, and the outline of
// the ink.
function drawSelected(m, a, ox, oy, alpha) {
  if (!SEL || SEL.map !== m || alpha <= 0.02) return;
  var b = SEL.b, x = ox + a * b[0], y = oy + a * b[1], w = a * b[2], h = a * b[3], r = cardCorner(SEL, w, h);
  if (x > W || y > H || x + w < 0 || y + h < 0) return;
  ctx.globalAlpha = alpha; ctx.setLineDash([]);
  ctx.strokeStyle = C['--halo']; ctx.lineWidth = 5; ctx.beginPath(); rr(ctx, x - 3, y - 3, w + 6, h + 6, r + 3); ctx.stroke();
  ctx.strokeStyle = C['--ink']; ctx.lineWidth = 1.5; ctx.beginPath(); rr(ctx, x, y, w, h, r); ctx.stroke();
  logged({t: 'selected', id: SEL.id, b: [x, y, w, h]});
}

// ---- pointing --------------------------------------------------------------------
// The line of map m in the layer of the frame for flow i (`linesOf`).
function lineOf(m, i) {
  var L = linesOf(m, shownLayer(m));
  if (!L._by) { L._by = []; L.list.forEach(function (e) { L._by[e.f.i] = e; }); }
  return L._by[i] || null;
}
// The flow of the current map whose line is nearest to the screen point, in LINE_HIT
// pixels or less, or null.
var LINE_HIT = 6;
function pickLine(px, py) {
  var m = currentMap(), v = view(m), lx = (px - v.ox) / v.a, ly = (py - v.oy) / v.a, tol = LINE_HIT / v.a, best = null, bd = tol;
  var fl = layerFlags(m, shownLayer(m)).flow;
  m.flowIndex.query(lx - tol, ly - tol, lx + tol, ly + tol, []).forEach(function (f) {
    var e = fl[f.i] ? lineOf(m, f.i) : null;
    if (!e) return;
    for (var i = 0; i + 1 < e.q.length; i++) {
      var d = segDist(lx, ly, e.q[i], e.q[i + 1]);
      if (d <= bd) { bd = d; best = f; }
    }
  });
  return best;
}
function segDist(x, y, a, b) {
  var dx = b[0] - a[0], dy = b[1] - a[1], l = dx * dx + dy * dy, t = l ? clamp(((x - a[0]) * dx + (y - a[1]) * dy) / l, 0, 1) : 0;
  return Math.hypot(x - a[0] - t * dx, y - a[1] - t * dy);
}
// Point at card c or flow f (or at nothing) from the pointer, the keyboard or a row of the
// details. The reading line tells the new item.
function point(c, f, from) {
  if (HOT.c === c && HOT.f === f && (c || f ? HOT.from === from : true)) return;
  HOT = {c: c || null, f: f || null, from: c || f ? from : ''};
  SPEAK_DUE = true; lightMoved();
}
// The reading line and the note change in the animation frame after the frame that draws
// the new light. Thus the browser paints the lit paths first (`drawn` in `atlas_input`).
var SPEAK_DUE = false;
function speakLater() {
  if (!SPEAK_DUE) return;
  SPEAK_DUE = false;
  requestAnimationFrame(function () {
    if ((HOT.c || HOT.f) && NOTE_EL) NOTE_EL.classList.add('gone');
    speak();
  });
}
function pin(f) { PIN = f; speak(); lightMoved(); }

// ---- the reading line ----------------------------------------------------------------
// The count of the parts of the map that card c opens: its cards that are not actors.
function partsOf(c) { return c.child ? c.child.cards.filter(function (x) { return x.k !== 'actor'; }).length : 0; }
// The card of the map above that a neighbour of a nested map is, or null.
function upCard(c) { var o = c.map.owner; return o && c.k === 'actor' ? o.map.byId[c.id] || null : null; }
function flowsIn(c, id) {
  var fl = layerFlags(c.map, id).flow, ins = 0, outs = 0;
  c.ins.forEach(function (f) { if (fl[f.i]) ins++; });
  c.outs.forEach(function (f) { if (fl[f.i]) outs++; });
  return [ins, outs];
}
function cardSay(c, keyed) {
  var io = flowsIn(c, shownLayer(c.map)), words = c.p ? [c.p] : [];
  words.push(io[0] + io[1] ? 'receives ' + io[0] + ', gives ' + io[1] : 'no flow in this layer');
  if (c.child) words.push((keyed ? 'Shift+Enter shows' : 'double-click to see') + ' its ' + counted(partsOf(c), 'part'));
  if (upCard(c)) words.push('outside ' + c.map.owner.id + ', select it to go to it');
  return [el('b', null, c.id), el('span', null, words.join(' · '))];
}
function flowSay(f) {
  var code = el('code', null, f.a);
  code.style.setProperty('--k', 'var(' + (KIND[f.k] || '--ink-2') + ')');
  return [el('b', null, f.s, el('span', {'class': 'arr', 'aria-hidden': 'true'}, '→'), el('span', {'class': 'sr-only'}, ' to '), f.t), code, f.y ? el('span', null, f.y) : null];
}
// The words for a screen reader before the item of the keyboard focus: its place in the
// order of Tab.
function placeWords(x) {
  var list = tabOrder(x.map), n = list.indexOf(x) + 1;
  return el('span', {'class': 'sr-only'}, (isFlow(x) ? 'Line ' : 'Card ') + n + ' of ' + list.length + '. ');
}
// The item of the reading line: the pointed item, else the pinned line, in the current map,
// or null.
function sayItem() {
  var m = currentMap();
  if (HOT.c && HOT.c.map === m) return HOT.c;
  if (HOT.f && HOT.f.map === m) return HOT.f;
  return PIN && PIN.map === m ? PIN : null;
}
// Write the reading line for the pointed item, else for the pinned line, in the current map.
// A selected card has its details, so the reading line does not give it. The line changes
// only when its item changes.
function speak() {
  // The States view writes the reading line itself (`smSay` in `atlas_states`).
  if (!SAY || VIEW.mode === 'states' || VIEW.mode === 'focus' || VIEW.mode === 'history') return;
  var x = sayItem(), hot = !!x && (x === HOT.c || x === HOT.f), from = hot ? HOT.from : '';
  var key = x ? (isFlow(x) ? 'f' : 'c') + x.map.oi + ':' + x.i + from + shownLayer(x.map) : '';
  if (x && x === SEL && !isFlow(x)) key = '';
  if (key === SAID_KEY) return;
  SAID_KEY = key;
  if (!key) { SAY.classList.remove('on'); SAY.replaceChildren(); return; }
  var keyed = from === 'key';
  SAY.replaceChildren.apply(SAY, [keyed ? placeWords(x) : null].concat(isFlow(x) ? flowSay(x) : cardSay(x, keyed)).filter(Boolean));
  SAY.classList.add('on');
}
// When the camera goes into a different map: the pointed item of the map before is not
// pointed, and the reading line tells only an item of the new map.
function mapChanged(m) {
  if ((HOT.c && HOT.c.map !== m) || (HOT.f && HOT.f.map !== m)) HOT = {c: null, f: null, from: ''};
  speak();
}
"""
