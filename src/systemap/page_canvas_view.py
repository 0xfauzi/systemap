"""The view part of the canvas renderer: the views, the layer filter and the header.

`page_canvas` joins this part after the scene part (`page_canvas_scene`). The design is
the section "Views" of docs/design/nested-canvas.md. Map, Sequences and Changes are views
of the same canvas. They are not navigation: a view change does not move the camera.

The view state is `VIEW`: `mode` ("map", "sequences" or "changes"), `layer` (a layer ID
or "all") and `epoch`, which grows by 1 at each change. The marks image and the map
images of a large map have the epoch in their key (`page_canvas_image`). Thus a frame
never shows an image of a different view.

The seam. Each view part puts its functions in `VIEWS[mode]`: `card(c)`, `flow(f)`,
`over(m, a, ox, oy, alpha)`, `enter(from)`, `leave(to)`, `frame()`, `band(fresh)`,
`box()`, `facts(c)`, `say(m)`, `words()` and `here(m)`. All of them are optional.

- `card(c)` gives null for the usual card, or `{a, ring, tag, back, note}`: the alpha of
  the card (0 to 1), and four marks, each null or an object. `ring` is
  `{c: color, w: width, d: dash}`: a line 3 px outside the card. `tag` is
  `{s: text, c: color, t: text color, o: {c: color, d: dash}}`: a small plate at the top
  right of the card. Its text color is --map when `t` is not given, and `o` is an optional
  outline. `back` is `{c: color, w: width}`: a line around the back card of a card that
  opens a map. `note` has the keys of `tag`: a plate on the lower edge of the back card at
  the right. It shows only when the card is wider than the plate. A part must not change an
  object after it gives it.
- `flow(f)` gives null for the usual flow, or `{a, color}`. A color of null is the layer
  color of the flow. `f.map` is the map of the flow. `FLOW_OFF` is a flow that the view
  does not show. A boundary flow from a portal has the values of the flows that it stands
  for (`boundaryView` in `page_canvas_fade`).
- `over(m, a, ox, oy, alpha)` draws after the cards of map m, for example a route. `a`,
  `ox` and `oy` are the `view(m)` of the map, and `alpha` includes the fade of the view.
- `enter(from)` and `leave(to)` occur at a change of the mode.
- `frame()` occurs at the start of each frame (`viewFrame`), after the fade of each mode.
- `facts(c)` and `say(m)` give the words of the current view for a card in the list of the
  tree and for a map in the live region (`viewFacts`, `viewSay`). After a change of the
  mode, the list of the tree is written again when one of the two modes has `facts`.
- `words()` gives the words of the view for the live region after a change to the view,
  in place of the name and the `say` of the current map. Empty words keep those.
- `here(m)` occurs when the label of the canvas gives the current map m (`relabel`): when
  the camera stops, and at a change of the view.
- `band(fresh)` gives the height of a bar of the view under the header, for example the
  toolbar of the Sequences view. With `fresh`, the part measures the bar again. The top
  band of the screen (`HEAD_H`) is the header and the bar of each view, multiplied by the
  fade of its view (`headBand`). Thus the band grows and shrinks with the fade. A camera
  target that a view part calculates uses the band at the end of the fade (`headAim`).
  `barShow` and `barBand` show, hide and measure a bar.
- `box()` gives the element of the bar of the view. When that element has the keyboard
  focus at a change of the mode, the focus goes to the button of the new view. Thus the
  focus does not go to the body of the page when the bar goes.

The drawing calls the seam only for the cards and the flows that a frame draws:
`viewCard(c)` and `viewFlow(f)`. They give the values that the screen shows. When a value
of a card or a flow changes, it fades: it changes by VIEW_MAX or less in one frame, and by
1 in VIEW_MS or more. A mark (a ring, a tag or a back line) fades out, and then the new
mark fades in. A card or a flow that the frame before did not draw starts at its value.
With reduced motion, a value changes in one frame. The values of a card are kept on the
card, so a frame calls the part of the view one time for each card and each flow that it
draws (`STATS.hooks`). In the Map view with all layers, a card or a flow that has the plain
value keeps it with no call (`VIEW_IDLE`), except an actor card with an open port, which
has a mark in the Map view (`page_canvas_ports`). Thus the seam adds almost no work to a
frame of the default view. The marks image of a large map has the values of the view. After a
view change, the frame draws the new image, and the old image over it with an opacity that
goes from 1 to 0 (`viewMarks`). An image gets the values with no fade (`viewAim`), in one
object for each card and flow, so that an image makes no new objects.

A tag goes up when the name of its card and the tag do not fit side by side. Thus a tag
does not cover the name of a narrow card (`drawTag`).

The Map view. A layer shows only its flows (`e` of the layer in the canvas data). A card
that no flow of the layer touches and that is not a subject of the layer (`l` of the card)
is quiet: it has the alpha QUIET. These are the rules of `paint` in
`schematic_relations.py`. A map that does not have the layer shows no flow, and its cards
that are not subjects are quiet. The flags of each map are calculated one time for each
layer (`layerFlags`), when the map is first drawn with that layer. The layer applies only
in the Map view, as on the linked page. A layer button in a different view goes to the
Map view with that layer.

The header (`canvas_header`). The view buttons and the layer buttons set the view. The
layer buttons are a toolbar: the arrow keys, Home and End move the keyboard focus between
them, and Enter, Space or a click selects the layer. The keys of
the camera do not operate while the keyboard focus is in the header, in a text field, in
a select or in a dialog (`ownKeys`). The live region gives the new view or layer, and the
label of the canvas gives them when they are not Map and All (`viewLabel`).
"""

from __future__ import annotations

VIEW_PART = r"""
// ---- the views and the layers ------------------------------------------------------
var VIEW = {mode: 'map', layer: 'all', epoch: 0}, VIEWS = Object.create(null), MODES = ['map', 'sequences', 'changes'];
var MODE_NAMES = {map: 'Map', sequences: 'Sequences', changes: 'Changes'};
var VIEW_MS = 160, VIEW_MAX = 0.2, VIEW_STEP = 1, VIEW_LAST = 0, VIEW_AT = 0, VIEW_FADING = false, VIEW_AIM = 0, VIEW_LOG = null;
var VIEW_SHOW = {map: 1, sequences: 0, changes: 0}, QUIET = 0.32, VIEW_IDLE = true;
var PLAIN = {a: 1, ring: null, tag: null, back: null, note: null}, PLAIN_FLOW = {a: 1, color: null};
var HEAD_EL = document.getElementById('canvas-head'), HEAD_H = 0, HEAD_BASE = 0;
// The layers of all maps: the name and the question of each layer ID.
var LAYER_OF = Object.create(null);
ORDER.forEach(function (m) { (m.layers || []).forEach(function (l) { if (!LAYER_OF[l.id]) LAYER_OF[l.id] = l; }); });
// The flags of a layer in a map: the flows that it shows, and the quiet cards.
function layerFlags(m, id) {
  var memo = m._lf || (m._lf = Object.create(null));
  if (memo[id]) return memo[id];
  var lay = null, flow = new Uint8Array(m.flows.length), quiet = new Uint8Array(m.cards.length), touched = Object.create(null);
  (m.layers || []).forEach(function (l) { if (l.id === id) lay = l; });
  (lay ? lay.e : []).forEach(function (i) {
    var f = m.flows[i];
    if (f) { flow[i] = 1; touched[f.s] = true; touched[f.t] = true; }
  });
  if (id !== 'structure') m.cards.forEach(function (c, i) { if (!touched[c.id] && (c.l || []).indexOf(id) < 0) quiet[i] = 1; });
  memo[id] = {flow: flow, quiet: quiet};
  return memo[id];
}
// A quiet card of a layer, and a flow that a view does not show (`FLOW_OFF`, also for the
// other views).
var MAP_QUIET = {a: QUIET, ring: null, tag: null, back: null, note: null}, FLOW_OFF = {a: 0, color: null};
VIEWS.map = {
  card: function (c) { return VIEW.layer !== 'all' && layerFlags(c.map, VIEW.layer).quiet[c.i] ? MAP_QUIET : null; },
  flow: function (f) { return VIEW.layer !== 'all' && !layerFlags(f.map, VIEW.layer).flow[f.i] ? FLOW_OFF : null; }
};

// ---- the seam --------------------------------------------------------------------
function cardAim(c) { var v = VIEWS[VIEW.mode]; return (v && v.card && v.card(c)) || PLAIN; }
function flowAim(f) { var v = VIEWS[VIEW.mode]; return (v && v.flow && v.flow(f)) || PLAIN_FLOW; }
// The key of the marks of a card. A part does not change a mark after it gives it, so the
// key of each mark is made one time.
function partKey(o) { return o ? o._k || (o._k = JSON.stringify(o)) : ''; }
function markKey(t) {
  return t.ring || t.tag || t.back || t.note ? partKey(t.ring) + '|' + partKey(t.tag) + '|' + partKey(t.back) + '|' + partKey(t.note) : '';
}
// The values of card c that the screen shows in this frame: `a`, the marks `ring`, `tag`,
// `back` and `note`, and the alpha `d` of the marks. While an image is drawn (VIEW_AIM), the
// values of the view, with no fade, in one object for each card (`_va`).
function viewCard(c) {
  if (VIEW_AIM) {
    var aim = cardAim(c), o = c._va || (c._va = {d: 1});
    o.a = aim.a; o.ring = aim.ring; o.tag = aim.tag; o.back = aim.back; o.note = aim.note || null;
    return o;
  }
  if (c._vAt === drawn) return c._v;
  // In the Map view with all layers, the value of each card is the plain value. A card that
  // has the plain value keeps it, with no call of the view part (`VIEW_IDLE`). A card with
  // the mark of an open port (`_pm`, `page_canvas_ports`) has a mark in that view too.
  var v = c._v;
  if (VIEW_IDLE && v && v.a === 1 && v.d === 0 && v.key === '' && !c._pm) {
    c._vAt = drawn;
    if (VIEW_LOG && VIEW_LOG.cur) VIEW_LOG.cur.cards.push([c.map.oi, c.i, 1, 0]);
    return v;
  }
  STATS.hooks++;
  var t = cardAim(c), fresh = !v || c._vAt !== drawn - 1, key = markKey(t);
  if (!v) v = c._v = {a: 1, ring: null, tag: null, back: null, note: null, d: 0, key: ''};
  c._vAt = drawn;
  if (fresh || (key !== v.key && v.d <= 0)) { v.key = key; v.ring = t.ring; v.tag = t.tag; v.back = t.back; v.note = t.note || null; if (!fresh) v.d = 0; }
  var to = key && key === v.key ? 1 : 0;
  v.a = fresh ? t.a : approach(v.a, t.a, VIEW_STEP);
  v.d = fresh ? to : approach(v.d, to, VIEW_STEP);
  if (v.a !== t.a || v.d !== to || v.key !== key) VIEW_FADING = true;
  if (VIEW_LOG && VIEW_LOG.cur) VIEW_LOG.cur.cards.push([c.map.oi, c.i, v.a, v.d]);
  return v;
}
// The values of flow f that the screen shows: `a`, `color` (null for the layer color),
// and while the color changes (`u` below 1), the old color `from` with the part 1 - `u`.
function viewFlow(f) {
  if (VIEW_AIM) { var aim = flowAim(f), o = f._va || (f._va = {from: null, u: 1}); o.a = aim.a; o.color = aim.color || null; return o; }
  if (f._vAt === drawn) return f._v;
  var v = f._v;
  if (VIEW_IDLE && v && v.a === 1 && v.u === 1 && v.color === null) {
    f._vAt = drawn;
    if (VIEW_LOG && VIEW_LOG.cur) VIEW_LOG.cur.flows.push([f.map.oi, f.i, 1]);
    return v;
  }
  STATS.hooks++;
  var t = flowAim(f), fresh = !v || f._vAt !== drawn - 1, color = t.color || null;
  if (!v) v = f._v = {a: 1, color: null, from: null, u: 1};
  f._vAt = drawn;
  if (fresh) { v.a = t.a; v.color = color; v.from = null; v.u = 1; }
  else {
    // A new color: the shown color becomes the old color. During a color fade, the part
    // that is larger stays, and a change back to the old color reverses the fade.
    if (color !== v.color) {
      if (v.u < 1 && color === v.from) { v.from = v.color; v.u = 1 - v.u; }
      else { if (v.u >= 0.5) v.from = v.color; v.u = 0; }
      v.color = color;
    }
    v.a = approach(v.a, t.a, VIEW_STEP);
    v.u = approach(v.u, 1, VIEW_STEP);
  }
  if (v.a !== t.a || v.u < 1) VIEW_FADING = true;
  if (VIEW_LOG && VIEW_LOG.cur) VIEW_LOG.cur.flows.push([f.map.oi, f.i, v.a]);
  return v;
}
// The alpha of flow f in this frame, after `viewFlow` (the labels use it).
function flowShown(f) { return VIEW_AIM ? flowAim(f).a : f._vAt === drawn ? f._v.a : 1; }
// The color of a flow, for a color of the view or for the layer color.
function flowColor(f, color) { return color ? C[color] || color : C['--l-' + f.l] || C['--flow']; }
// Draw the parts of the views after the cards of map m. A view that fades out still draws.
function viewOver(m, a, ox, oy, alpha) {
  MODES.forEach(function (mode) {
    var v = VIEWS[mode], s = VIEW_SHOW[mode];
    if (v && v.over && s > 0.01) v.over(m, a, ox, oy, alpha * s);
  });
}
// The step of the fades in this frame, and the fade of each mode. `draw` calls it first.
// The time of the step starts at the last frame, or at the last change of the view when it
// is later (`viewTouch`). Thus a change by 1 takes VIEW_MS or more from the input.
function viewFrame() {
  var now = performance.now(), dt = VIEW_LAST ? now - Math.max(VIEW_LAST, VIEW_AT) : Infinity;
  VIEW_LAST = now; VIEW_FADING = false; STATS.hooks = 0; STATS.flows = 0;
  VIEW_IDLE = VIEW.mode === 'map' && VIEW.layer === 'all';
  VIEW_STEP = reduced() ? 1 : Math.min(VIEW_MAX, dt / VIEW_MS);
  MODES.forEach(function (mode) {
    var to = mode === VIEW.mode ? 1 : 0;
    VIEW_SHOW[mode] = approach(VIEW_SHOW[mode], to, VIEW_STEP);
    if (VIEW_SHOW[mode] !== to) VIEW_FADING = true;
  });
  MODES.forEach(function (mode) { var v = VIEWS[mode]; if (v && v.frame) v.frame(); });
  headBand(false);
  if (VIEW_LOG) {
    VIEW_LOG.cur = {at: now, show: Object.assign({}, VIEW_SHOW), cards: [], flows: [], marks: []};
    VIEW_LOG.frames.push(VIEW_LOG.cur);
  }
}
// A view part calls this when its values change without `setView`, for example at a new
// step of a sequence. It also asks for a frame.
function viewTouch() { VIEW_AT = performance.now(); request(); }
// Draw a function with the values of the view and no fade, for an image.
function viewAim(f) { VIEW_AIM++; try { return f(); } finally { VIEW_AIM--; } }

// ---- the marks of the views --------------------------------------------------------
// The tags of the cards of a frame, after the texts of their map (`drawTags`): a list of
// [values, x, y, w, h, alpha]. The ring goes into the line batch of the cards, and the back
// line into the batch of the back cards. An image draws its tags with the text of its
// cards (`imageParts`).
var MARKS_OF = [];
function markColor(m) { return C[m.c] || m.c; }
// The ring of a card: a line 3 px outside the card. The back line: a line around the back
// card of a card that opens a map.
function ringRect(b, ring, al, x, y, w, h, r) { b.rect(markColor(ring), al, x - 3, y - 3, w + 6, h + 6, r + 3, ring.w || 2, ring.d); }
function backRect(b, back, al, x, y, w, h, r) { b.rect(markColor(back), al, x + 4, y + 4, w, h, r, back.w || 1.5); }
function viewBack(v, x, y, w, h, r, alpha) { if (v.back && v.d > 0) backRect(BACK_LINE, v.back, alpha * v.d, x, y, w, h, r); }
function viewMarksAt(c, v, x, y, w, h, alpha) {
  if (v.d <= 0) return;
  if (v.ring) ringRect(LINE, v.ring, alpha * v.d, x, y, w, h, cardCorner(w, h));
  if ((v.tag || v.note) && !VIEW_AIM && hasText(h)) MARKS_OF.push([v, x, y, w, h, alpha, c]);
}
// The tag at the top right of the card and the note on the lower edge of its back card.
// Each one fades in with the width of the card, from the width of its plate. When the name
// of card c and the tag do not fit side by side, the tag goes up, until its lower edge is on
// the top edge of the card. Thus the tag does not cover the name. The move follows the
// width of the card.
function drawTag(v, x, y, w, h, alpha, c) {
  var fs = clamp(h * 0.16, 8, 11), al = alpha * v.d * cardShow(h), th = fs * 1.6;
  if (al <= 0.02) return;
  [[v.tag, y - th / 2], [v.note, y + h + 4 - th / 2]].forEach(function (e, i) {
    if (!e[0]) return;
    var pw = unitWidth(e[0].s, 600) * fs + 10, room = smooth(pw, pw + 2 * fs, w), top = e[1];
    if (!i && c) {
      var need = 2 * inset(h) + unitWidth(c.id, 600) * titleSize(h) + pw + 8;
      top -= (1 - smooth(need, need + 2 * fs, w)) * th / 2;
    }
    if (room > 0.02) markPlate(e[0], x + w - pw - 4, top, pw, th, fs, al * room);
  });
}
function markPlate(t, x, y, w, h, fs, al) {
  ctx.globalAlpha = al; ctx.fillStyle = markColor(t); ctx.setLineDash([]); ctx.beginPath(); rr(ctx, x, y, w, h, h / 2); ctx.fill();
  if (t.o) { ctx.strokeStyle = markColor(t.o); ctx.lineWidth = 1; ctx.setLineDash(DASH[t.o.d || '']); ctx.stroke(); ctx.setLineDash([]); }
  text(t.s, x + w / 2, y + h / 2 + fs * 0.36, fs, C[t.t || '--map'], al, 600, false, 'center');
  obstacle(x, y, w, h, 1, al);
}
function drawTags() {
  MARKS_OF.forEach(function (e) { drawTag(e[0], e[1], e[2], e[3], e[4], e[5], e[6]); });
  MARKS_OF = [];
}
// The marks of a card c that opens a map, drawn at once: the back line while the card is
// closed, the ring and the tag.
var OPEN_MARKS = null;
function viewOpening(c, v, x, y, w, h, r, alpha, o) {
  if (v.d <= 0 || !(v.ring || v.tag || v.back || v.note)) return;
  var b = OPEN_MARKS || (OPEN_MARKS = new Batch(false));
  if (v.back && o < 1) backRect(b, v.back, alpha * v.d * (1 - o), x, y, w, h, r);
  if (v.ring) ringRect(b, v.ring, alpha * v.d, x, y, w, h, r);
  b.flush(ctx); ctx.setLineDash([]);
  if (v.tag || v.note) drawTag(v, x, y, w, h, alpha, c);
}
// The marks image of a large map after a view change: the new image, and the old image
// over it, with an opacity that goes from 1 to 0. The images are opaque. Thus the two give
// the blend of the two views. A second change during the blend first draws the blend into
// the old image.
function viewKeep(m, old) {
  if (m.img0 && m._mt < 1) {
    var g = m.img0.canvas.getContext('2d');
    g.globalAlpha = m._mt; g.drawImage(old.canvas, 0, 0, m.img0.canvas.width, m.img0.canvas.height); g.globalAlpha = 1;
  } else m.img0 = old;
  m._mt = 0; m._mtAt = -1;
}
function viewMarks(m, ox, oy, mw, mh, alpha) {
  if (!m.img0) return;
  if (m._mtAt !== drawn) { m._mt = approach(m._mt, 1, VIEW_STEP); m._mtAt = drawn; }
  if (VIEW_LOG && VIEW_LOG.cur) VIEW_LOG.cur.marks.push([m.oi, m._mt, VIEW.epoch]);
  if (m._mt >= 1) { m.img0 = null; return; }
  VIEW_FADING = true;
  ctx.globalAlpha = alpha * (1 - m._mt); ctx.drawImage(m.img0.canvas, ox, oy, mw, mh); STATS.image++;
}

// ---- the header --------------------------------------------------------------------
function headButtons(sel) { return HEAD_EL ? Array.prototype.slice.call(HEAD_EL.querySelectorAll(sel)) : []; }
var VIEW_BTNS = headButtons('[data-view]'), LAYER_BTNS = headButtons('[data-layer]');
var LAYER_SELECT = document.getElementById('canvas-layer');
// The height of the header. It is constant for a screen (`measure` reads it).
function headMeasure() {
  HEAD_BASE = HEAD_EL ? HEAD_EL.getBoundingClientRect().height : 0;
  if (HEAD_EL) {
    HEAD_EL.removeAttribute('data-fit'); HEAD_EL.removeAttribute('data-menu');
    if (HEAD_EL.scrollWidth > HEAD_EL.clientWidth + 1) HEAD_EL.setAttribute('data-fit', '1');
    if (HEAD_EL.scrollWidth > HEAD_EL.clientWidth + 1) HEAD_EL.setAttribute('data-fit', '2');
    if (HEAD_EL.scrollWidth > HEAD_EL.clientWidth + 1) HEAD_EL.setAttribute('data-menu', '');
  }
  headBand(true);
}
// The top band: the header, and the bar of each view with the fade of its view (`band`).
function headBand(fresh, show) {
  var b = 0;
  show = show || VIEW_SHOW;
  MODES.forEach(function (mode) { var v = VIEWS[mode]; if (v && v.band) b += v.band(fresh) * show[mode]; });
  HEAD_H = HEAD_BASE + b; P_TOP = P_TOP0 + HEAD_H;
}
// Calculate a camera target with the top band of the current view at the end of its fade.
// Thus a target that a view change starts does not go under the bar of the new view. The
// next frame calculates the band of the fade again (`viewFrame`).
function headAim(f) {
  var show = {};
  MODES.forEach(function (mode) { show[mode] = mode === VIEW.mode ? 1 : 0; });
  headBand(false, show);
  try { f(); } finally { headBand(false); }
}
// Show or hide the bar of a view part. The bar comes into the page, and the read of its box
// makes the browser give it its style before the fade starts. When it goes, it goes out of
// the page after its fade (the CSS transition of 160 ms), unless the view `mode` starts
// again before that time.
function barShow(el, on, mode) {
  if (!el) return;
  clearTimeout(el._bt);
  if (on) { el.hidden = false; el.getBoundingClientRect(); el.classList.add('on'); return; }
  el.classList.remove('on');
  if (reduced()) el.hidden = true;
  else el._bt = setTimeout(function () { if (VIEW.mode !== mode) el.hidden = true; }, VIEW_MS + 10);
}
// The height of a bar in the record `s` (`s.h`). A hidden bar keeps the last height.
function barBand(el, s, fresh) {
  if (el && (fresh || !s.h) && !el.hidden) s.h = el.getBoundingClientRect().height;
  return s.h || 0;
}
function layerName(id) { return id === 'all' ? 'All' : LAYER_OF[id] ? LAYER_OF[id].n : id; }
function layerQuestion(id) { return id === 'all' ? 'Which flows connect the components?' : LAYER_OF[id] ? LAYER_OF[id].q : ''; }
// The words of the view for the label of the canvas: none for the Map view with All.
function viewLabel() {
  if (VIEW.mode !== 'map') return ' View: ' + MODE_NAMES[VIEW.mode] + '.';
  return VIEW.layer === 'all' ? '' : ' Layer: ' + layerName(VIEW.layer) + '.';
}
// The words for the live region after a change of the view or the layer.
function viewWords(modeChanged) {
  var m = currentMap(), n = 0;
  if (VIEW.mode !== 'map') {
    var v = VIEWS[VIEW.mode], own = v && v.words ? v.words() : '';
    return 'View: ' + MODE_NAMES[VIEW.mode] + '. ' + (own || 'Map: ' + mapName(m) + '.' + viewSay(m));
  }
  if (VIEW.layer === 'all') n = m.flows.length;
  else { var fl = layerFlags(m, VIEW.layer).flow; for (var i = 0; i < fl.length; i++) n += fl[i]; }
  return (modeChanged ? 'View: Map. ' : '') + (VIEW.layer === 'all' ? 'All layers. ' : 'Layer: ' + layerName(VIEW.layer) + '. ') +
    layerQuestion(VIEW.layer) + ' The current map shows ' + n + ' of ' + counted(m.flows.length, 'flow') + '.';
}
// The words of the current view for card c in the list of the tree, and for map m in the
// live region (`facts` and `say` of the view part).
function viewFacts(c) { var v = VIEWS[VIEW.mode]; return v && v.facts ? v.facts(c) : ''; }
function viewSay(m) { var v = VIEWS[VIEW.mode]; return v && v.say ? v.say(m) : ''; }
// The current map is m (`relabel`): each view part with `here` gets it.
var HERE_HOOKS = [];
function viewHere(m) {
  MODES.forEach(function (mode) { var v = VIEWS[mode]; if (v && v.here) v.here(m); });
  HERE_HOOKS.forEach(function (f) { f(m); });
}
function headSync() {
  VIEW_BTNS.forEach(function (b) {
    var mode = b.getAttribute('data-view');
    b.hidden = !VIEWS[mode];
    b.setAttribute('aria-pressed', mode === VIEW.mode ? 'true' : 'false');
  });
  LAYER_BTNS.forEach(function (b) {
    var on = b.getAttribute('data-layer') === VIEW.layer;
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
    b.tabIndex = on ? 0 : -1;
  });
  if (LAYER_SELECT) LAYER_SELECT.value = VIEW.layer;
}
// Set the view. An unknown mode or layer keeps the current one. Give true for a change.
function setView(mode, layer) {
  mode = MODES.indexOf(mode) >= 0 ? mode : VIEW.mode;
  layer = layer === undefined || layer === null ? VIEW.layer : layer === 'all' || LAYER_OF[layer] ? layer : VIEW.layer;
  if (mode === VIEW.mode && layer === VIEW.layer) return false;
  var was = VIEW.mode, held = document.activeElement, box = VIEWS[was] && VIEWS[was].box ? VIEWS[was].box() : null;
  if (mode !== was && VIEWS[was] && VIEWS[was].leave) VIEWS[was].leave(mode);
  VIEW.mode = mode; VIEW.layer = layer; VIEW.epoch++;
  if (mode !== was && VIEWS[mode] && VIEWS[mode].enter) VIEWS[mode].enter(was);
  if (mode !== was && TREE_MS !== null && ((VIEWS[was] && VIEWS[was].facts) || (VIEWS[mode] && VIEWS[mode].facts))) buildTree();
  headSync();
  // The bar of the old view goes. When it has the keyboard focus, the focus goes to the
  // button of the new view, not to the body of the page.
  if (mode !== was && box && held && box.contains(held)) {
    var to = VIEW_BTNS.filter(function (b) { return b.getAttribute('data-view') === mode && !b.hidden; })[0];
    (to || cv).focus();
  }
  say(viewWords(mode !== was));
  relabel(SAID_MAP || currentMap());
  viewTouch();
  return true;
}
VIEW_BTNS.forEach(function (b) { b.addEventListener('click', function () { setView(b.getAttribute('data-view')); }); });
LAYER_BTNS.forEach(function (b, i) {
  b.addEventListener('click', function () { setView('map', b.getAttribute('data-layer')); });
  b.addEventListener('keydown', function (e) {
    var n = LAYER_BTNS.length, j = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? (i + 1) % n
      : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? (i + n - 1) % n : e.key === 'Home' ? 0 : e.key === 'End' ? n - 1 : -1;
    if (j < 0) return;
    // The keys only move the keyboard focus. Enter, Space and a click select the layer.
    e.preventDefault();
    LAYER_BTNS.forEach(function (o, x) { o.tabIndex = x === j ? 0 : -1; });
    LAYER_BTNS[j].focus();
  });
});
if (LAYER_SELECT) LAYER_SELECT.addEventListener('change', function () { setView('map', LAYER_SELECT.value); });
// True when a key belongs to the element that has it: a control of the header, a text
// field, a select, a button, or an open dialog. Then the camera keys do not operate.
function ownKeys(e) {
  var t = e.target, tag = t && t.tagName;
  if (document.querySelector('dialog[open]')) return true;
  if (!t || !t.closest || t === cv) return false;
  if ((HEAD_EL && HEAD_EL.contains(t)) || t.closest('dialog, [role="dialog"], [data-own-keys]')) return true;
  return tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA' || tag === 'BUTTON' || !!t.isContentEditable;
}
// The state of the view for the tests: the mode, the layer, the epoch and the fade of each
// mode.
function viewState() {
  return {mode: VIEW.mode, layer: VIEW.layer, epoch: VIEW.epoch, show: Object.assign({}, VIEW_SHOW),
    fading: VIEW_FADING, head: HEAD_H, hooks: STATS.hooks, flows: STATS.flows, cards: STATS.cards};
}
"""
