"""The view part of the atlas renderer: the layers, the headline, the tabs and the key.

`atlas_script` joins this part after the scene part (`atlas_scene`). The rules are the
section "Map view: the rules" of docs/design/atlas.md. The parts that do not zoom are HTML
(`atlas_header`). This part writes them with DOM functions, not with HTML text.

The layer. `VIEW.layer` is a layer ID or "all". A map that does not have the layer shows
All (`layerOf`). The page opens with System context when that layer is the first layer of
the top map, and with All in the other cases (`canvas_header.first_layer`). A change of
the layer fades the lines out in SWAP_MS / 2 and the lines of the new layer in, in
SWAP_MS / 2 (`swapAlpha`). A card with no flow in the layer is quiet: it keeps a faint
outline (`quietOf`). Its change fades in VIEW_MS. With reduced motion, no value fades.

The headline is type on the ground: the path of the current map, the name of the layer,
the question of the layer and the counts. In a nested map, each part of the path is a
button that goes to that map, and the layer System context has the name Neighbours. The
tabs give the layers of the current map that have flows, Structure, and All, each with its
count of flows. The arrow keys, Home and End move the keyboard focus between the tabs.
The key at the bottom right gives the kinds of the lines of the current map in its layer.
The zoom readout gives the scale of the current map.
"""

from __future__ import annotations

VIEW_PART = r"""
// ---- the layer ---------------------------------------------------------------------
var SWAP_A = 1, VIEW = {mode: 'map', layer: 'all', epoch: 0, swap: null}, VIEW_MS = 160, SWAP_MS = 300, VIEW_STEP = 1, VIEW_LAST = 0, VIEW_FADING = false;
var HEAD_EL = document.getElementById('atlas-head'), HEAD_H = 0;
var LAYER_OF = Object.create(null);
ORDER.forEach(function (m) { (m.layers || []).forEach(function (l) { if (!LAYER_OF[l.id]) LAYER_OF[l.id] = l; }); });
if (TOP.layers && TOP.layers[0] && TOP.layers[0].id === 'system') VIEW.layer = 'system';
function hasLayer(m, id) { return id === 'all' || (m.layers || []).some(function (l) { return l.id === id; }); }
function layerOf(m, id) { id = id || VIEW.layer; return hasLayer(m, id) ? id : 'all'; }
// The flags of a layer in a map: the flows that it shows, and the quiet cards. A layer
// with no flow in the map has no quiet card.
function layerFlags(m, id) {
  var memo = m._lf || (m._lf = Object.create(null));
  if (memo[id]) return memo[id];
  var lay = null, flow = new Uint8Array(m.flows.length), quiet = new Uint8Array(m.cards.length), touched = Object.create(null), n = 0;
  (m.layers || []).forEach(function (l) { if (l.id === id) lay = l; });
  var list = id === 'all' ? m.flows.map(function (f, i) { return i; }) : lay ? lay.e : [];
  list.forEach(function (i) {
    var f = m.flows[i];
    if (f) { flow[i] = 1; n++; touched[f.s] = true; touched[f.t] = true; }
  });
  if (n) m.cards.forEach(function (c, i) { if (!touched[c.id]) quiet[i] = 1; });
  memo[id] = {flow: flow, quiet: quiet, n: n, used: touched};
  return memo[id];
}
// The layer that the lines of map m show in this frame: during the first half of a change,
// the old layer.
function shownLayer(m) {
  var s = VIEW.swap;
  return layerOf(m, s && performance.now() - s.t0 < SWAP_MS / 2 ? s.from : VIEW.layer);
}
// The alpha of the lines in this frame: it goes to 0 and back to 1 during a change.
function swapAlpha() {
  var s = VIEW.swap;
  if (!s) return 1;
  var t = (performance.now() - s.t0) / SWAP_MS;
  if (t >= 1) { VIEW.swap = null; VIEW.epoch++; return 1; }
  VIEW_FADING = true;
  return Math.abs(1 - 2 * t);
}
// The quiet value of card c in this frame: 0 for a card with a flow in the layer, 1 for a
// quiet card. It fades in VIEW_MS. A card that the frame before did not draw starts at
// its value. While an image is drawn (VIEW_AIM), the value of the layer with no fade.
var VIEW_AIM = 0;
function quietAim(c) { return layerFlags(c.map, shownLayer(c.map)).quiet[c.i]; }
function quietOf(c) {
  var to = quietAim(c);
  if (VIEW_AIM) return to;
  if (c._qAt === drawn) return c._q;
  c._q = c._qAt === drawn - 1 ? approach(c._q, to, VIEW_STEP) : to;
  c._qAt = drawn;
  if (c._q !== to) VIEW_FADING = true;
  return c._q;
}
function viewAim(f) { VIEW_AIM++; try { return f(); } finally { VIEW_AIM--; } }
function viewFrame() {
  var now = performance.now(), dt = VIEW_LAST ? now - VIEW_LAST : Infinity;
  VIEW_LAST = now; VIEW_FADING = false; STATS.flows = 0;
  VIEW_STEP = reduced() ? 1 : Math.min(0.2, dt / VIEW_MS);
  SWAP_A = swapAlpha();
}
function viewTouch() { request(); }
// Set the layer. An unknown layer keeps the current one. Give true for a change.
function setLayer(id) {
  if (!(id === 'all' || LAYER_OF[id]) || id === VIEW.layer) return false;
  VIEW.swap = reduced() ? null : {from: VIEW.layer, t0: performance.now()};
  VIEW.layer = id; VIEW.epoch++;
  headSync(true);
  say(layerWords(currentMap()));
  relabel(currentMap());
  viewTouch();
  return true;
}
function layerName(m, id) {
  if (id === 'all') return 'All';
  if (id === 'system' && m.owner) return 'Neighbours';
  return LAYER_OF[id] ? LAYER_OF[id].n : id;
}
function layerQuestion(m, id) {
  if (id === 'all') return 'Which flows connect the components?';
  if (id === 'system' && m.owner) return 'Which neighbours connect to ' + m.owner.id + '?';
  var own = null;
  (m.layers || []).forEach(function (l) { if (l.id === id) own = l; });
  return (own || LAYER_OF[id] || {q: ''}).q;
}
function layerWords(m) {
  var id = layerOf(m);
  return 'Layer: ' + layerName(m, id) + '. ' + layerQuestion(m, id) + ' ' + countWords(m, id) + '.';
}
function viewLabel() { return VIEW.layer === 'all' ? '' : ' Layer: ' + layerName(currentMap(), layerOf(currentMap())) + '.'; }

// ---- the headline, the tabs, the key and the zoom readout -------------------------------
var ASK = document.getElementById('atlas-ask'), ASK_K = document.getElementById('atlas-ask-k');
var ASK_Q = document.getElementById('atlas-ask-q'), ASK_N = document.getElementById('atlas-ask-n');
var TABS = document.getElementById('atlas-tabs'), KEY = document.getElementById('atlas-key'), ZOOM_V = document.getElementById('atlas-zv');
var SYNCED = '', ASK_TIMER = 0;
// The counts of the headline: the actors (neighbours in a nested map), the components (parts)
// and the flows of the layer, or the cards and the regions for a layer with no flow.
function countWords(m, id) {
  var lf = layerFlags(m, id), actors = 0, comps = 0;
  if (!lf.n) return counted(m.cards.length, 'card') + ' in ' + counted(m.regions.length, 'region');
  m.cards.forEach(function (c) { if (lf.used[c.id]) { if (c.k === 'actor') actors++; else comps++; } });
  return (actors ? counted(actors, m.owner ? 'neighbour' : 'actor') + ' · ' : '') + counted(comps, m.owner ? 'part' : 'component') + ' · ' + counted(lf.n, 'flow');
}
function pathButtons(m) {
  var chain = [];
  for (var x = m; x; x = x.owner ? x.owner.map : null) chain.unshift(x);
  var out = [];
  chain.forEach(function (x, i) {
    var name = x.owner ? x.owner.id : (DATA.name || 'map');
    if (i === chain.length - 1) { out.push(el('b', null, name)); return; }
    var b = el('button', {type: 'button', title: 'Go to this map'}, name);
    b.addEventListener('click', function () { flyTo(frameOf(x), FIT); });
    out.push(b, el('span', {'aria-hidden': 'true'}, '/'));
  });
  return out;
}
function tabsOf(m) {
  var out = [];
  (m.layers || []).forEach(function (l) {
    var n = layerFlags(m, l.id).n;
    if (n || l.id === 'structure') out.push({id: l.id, n: n});
  });
  out.push({id: 'all', n: m.flows.length});
  return out;
}
function writeTabs(m, id) {
  var list = tabsOf(m);
  TABS.replaceChildren.apply(TABS, list.map(function (t) {
    var on = t.id === id, b = el('button', {type: 'button', role: 'tab', class: 'tab', 'aria-selected': on ? 'true' : 'false', tabindex: on ? '0' : '-1', 'data-layer': t.id},
      layerName(m, t.id), t.n ? el('i', null, String(t.n)) : null);
    b.addEventListener('click', function () { setLayer(t.id); });
    b.addEventListener('keydown', function (e) {
      var all = Array.prototype.slice.call(TABS.querySelectorAll('[role="tab"]')), i = all.indexOf(b), n = all.length;
      var j = e.key === 'ArrowRight' ? (i + 1) % n : e.key === 'ArrowLeft' ? (i + n - 1) % n : e.key === 'Home' ? 0 : e.key === 'End' ? n - 1 : -1;
      if (j < 0) return;
      e.preventDefault();
      all.forEach(function (o, x) { o.tabIndex = x === j ? 0 : -1; });
      all[j].focus();
    });
    return b;
  }));
}
function writeKey(m, id) {
  var lf = layerFlags(m, id), seen = Object.create(null), out = [], order = Object.keys(KIND);
  m.flows.slice().sort(function (u, v) {
    var a = order.indexOf(u.k), b = order.indexOf(v.k);
    return (a < 0 ? 99 : a) - (b < 0 ? 99 : b) || u.i - v.i;
  }).forEach(function (f) {
    var i = f.i;
    if (!lf.flow[i] || seen[f.k]) return;
    seen[f.k] = true;
    var mark = el('i', {'aria-hidden': 'true'});
    mark.style.setProperty('--k', 'var(' + (KIND[f.k] || '--ink-2') + ')');
    out.push(el('span', null, mark, LAYER_OF[f.l] && f.l !== 'system' ? LAYER_OF[f.l].n : f.k));
  });
  KEY.replaceChildren.apply(KEY, out);
}
// Write the headline, the tabs and the key of the current map when they change. `soft`
// fades the headline out and in (a change of the layer or of the map).
function headSync(soft) {
  var m = currentMap(), id = layerOf(m), key = m.oi + '|' + id;
  if (key === SYNCED) return;
  var first = !SYNCED;
  SYNCED = key;
  writeTabs(m, id); writeKey(m, id);
  function words() {
    ASK_K.replaceChildren.apply(ASK_K, (m.owner ? pathButtons(m).concat([el('span', {'aria-hidden': 'true'}, '·')]) : []).concat([el('span', null, layerName(m, id))]));
    ASK_Q.textContent = layerQuestion(m, id);
    ASK_N.textContent = countWords(m, id);
    ASK.classList.remove('swap');
  }
  clearTimeout(ASK_TIMER);
  if (first || reduced() || !soft) { words(); return; }
  ASK.classList.add('swap');
  ASK_TIMER = setTimeout(words, 150);
}
function zoomShown() {
  var m = currentMap(), z = Math.round(cam.k * m.T.s * 100) + '%';
  if (ZOOM_V && ZOOM_V.textContent !== z) ZOOM_V.textContent = z;
}
// True when a key belongs to the element that has it: a control of the page, a text field
// or a dialog. Then the camera keys do not operate.
function ownKeys(e) {
  var t = e.target, tag = t && t.tagName;
  if (document.querySelector('dialog[open]')) return true;
  if (!t || !t.closest || t === cv) return false;
  if (t.closest('dialog, [role="dialog"], [data-own-keys]')) return true;
  return tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA' || tag === 'BUTTON' || !!t.isContentEditable;
}
function viewState() {
  var m = currentMap();
  return {mode: VIEW.mode, layer: VIEW.layer, shown: layerOf(m), epoch: VIEW.epoch, head: HEAD_H, fading: VIEW_FADING,
    kicker: ASK_K.textContent, question: ASK_Q.textContent, counts: ASK_N.textContent, beside: ASK.classList.contains('beside'),
    tabs: Array.prototype.map.call(TABS.querySelectorAll('[role="tab"]'), function (b) { return {id: b.getAttribute('data-layer'), text: b.textContent, on: b.getAttribute('aria-selected') === 'true'}; }),
    key: KEY.textContent, zoom: ZOOM_V ? ZOOM_V.textContent : ''};
}
"""
