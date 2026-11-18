// The test page of the atlas gate (bench/jev/atlas_frames.py). It is the map renderer of the
// design study (docs/design/atlas/study-script.html) with three changes: it reads the canvas
// data object, a nested map can be in a card of a nested map to any depth, and the elements of a
// nested map are built only when the camera is near it. It is not product code.
(function () {
'use strict';
var D = JSON.parse(document.getElementById('data').textContent), NS = 'http://www.w3.org/2000/svg', RULE = __RULE__;
var KIND = {data: ['--data', 'Data'], control: ['--control', 'Control'], judge: ['--judge', 'Map review'], context: ['--context', 'Context'], tool: ['--tool', 'Tool']};
var svg = document.getElementById('map'), world = document.getElementById('world'), stage = document.getElementById('stage');
var dot = document.getElementById('dot'), cam = {x: 0, y: 0, k: 1}, cur = null, sel = null, hot = null, hotFlow = null, LANE = 4.5, started = false;
var REDUCE = matchMedia('(prefers-reduced-motion:reduce)').matches, W = 0, H = 0;
function el(tag, attrs, parent, text) { var e = document.createElementNS(NS, tag); for (var k in attrs) e.setAttribute(k, attrs[k]); if (text != null) e.textContent = text; if (parent) parent.appendChild(e); return e; }
function h(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
function plural(n, w) { return n + ' ' + w + (n === 1 ? '' : 's'); }
function kvar(f) { return 'var(' + (KIND[f.k] || KIND.data)[0] + ')'; }
function size() { var r = stage.getBoundingClientRect(); W = r.width; H = r.height; }

// ---- the maps: the top map, and each map that a card opens, to any depth -------------------
var MAPS = D.maps, TOP = MAPS[0], BY = {}, BUILT = [];
function prepare() {
  MAPS.forEach(function (m) {
    BY[m.id] = m; m.byId = {}; m.s = 1; m.ox = 0; m.oy = 0; m.host = null; m.up = null; m.kids = []; m.shown = []; m.g = null; m.t = 0;
    m.cards.forEach(function (c, i) { c.i = i; c.map = m; c.fl = []; m.byId[c.id] = c; });
    m.flows.forEach(function (f, i) { f.i = i; f.map = m; });
    m.layers = m.layers.concat([{id: 'all', n: 'All', q: 'Which flows connect the components?', e: m.flows.map(function (f) { return f.i; })}]);
    m.name = m.id ? m.id.split('/').pop() : D.name;
  });
  nest(TOP);
}
// A nested map sits in the right part of the card that opens it. Its scale makes it fit the card.
// The scale and the position are in the units of the top map, from the map above.
function nest(m) {
  m.cards.forEach(function (c) {
    var k = c.o && BY[c.o]; if (!k || k === m) return;
    var ls = Math.min((c.b[3] - 12) / k.size[1], 44 / k.size[0]);
    k.host = c; k.up = m; c.opens = k; m.kids.push(k);
    k.parts = k.cards.filter(function (x) { return x.k !== 'actor'; }).length;
    k.s = m.s * ls; k.ox = m.ox + m.s * (c.b[0] + c.b[2] - 9 - k.size[0] * ls); k.oy = m.oy + m.s * (c.b[1] + (c.b[3] - k.size[1] * ls) / 2);
    nest(k);
  });
}
// The small picture of a nested map that is not built: its cards, in one path.
function picture(c, g) {
  var k = c.opens, ls = k.s / c.map.s, x0 = (k.ox - c.map.ox) / c.map.s, y0 = (k.oy - c.map.oy) / c.map.s, d = '';
  k.cards.forEach(function (x) { if (x.k !== 'actor') d += 'M' + (x0 + x.b[0] * ls).toFixed(2) + ' ' + (y0 + x.b[1] * ls).toFixed(2) + 'h' + (x.b[2] * ls).toFixed(2) + 'v' + (x.b[3] * ls).toFixed(2) + 'h' + (-x.b[2] * ls).toFixed(2) + 'z'; });
  c.pic = el('path', {d: d, class: 'pic' + (k.g ? ' gone' : '')}, g);
}

function build(m) {
  var g = m.g = el('g', {class: 'lvl'}, world);
  BUILT.push(m);
  if (m.host && m.host.pic) m.host.pic.classList.add('gone');
  m.boxes.forEach(function (b) {
    var inside = m.cards.filter(function (c) { return c.b[0] >= b.b[0] && c.b[0] < b.b[0] + b.b[2] && c.b[1] >= b.b[1] && c.b[1] < b.b[1] + b.b[3]; });
    if (!inside.length) return;
    if (inside.every(function (c) { return c.k === 'actor'; })) {
      var first = Math.min.apply(null, inside.map(function (c) { return c.b[1]; }));
      if (!m.host) el('text', {x: Math.min.apply(null, inside.map(function (c) { return c.b[0]; })) + 6, y: first - 14, class: 'sysname'}, g, b.n);
      return;
    }
    el('rect', {x: b.b[0], y: b.b[1], width: b.b[2], height: b.b[3], rx: 16, class: 'sys'}, g);
    el('text', {x: b.b[0] + 20, y: b.b[1] + 30, class: 'sysname'}, g, b.n);
  });
  m.regions.forEach(function (r, i) {
    el('rect', {x: r.b[0] + 3, y: r.b[1] + 3, width: r.b[2] - 6, height: r.b[3] - 6, rx: 12, class: 'region'}, g);
    el('circle', {cx: r.b[0] + 17, cy: r.b[1] + 17, r: 7, class: 'rring'}, g);
    el('text', {x: r.b[0] + 17, y: r.b[1] + 20, 'text-anchor': 'middle', class: 'rnum'}, g, i + 1);
    el('text', {x: r.b[0] + 31, y: r.b[1] + 20.5, class: 'rname'}, g, r.n);
  });
  m.gFlows = el('g', {class: 'gflows'}, g); m.gCards = el('g', {}, g);
  m.cards.forEach(function (c) { card(m, c); });
  setLayer(m, m.mapLayer || 'all');
}
function card(m, c) {
  var b = c.b, actor = c.k === 'actor', rx = actor ? b[3] / 2 : 9, tx = b[0] + (actor ? 20 : 13);
  var cg = c.g = el('g', {class: 'card' + (actor ? ' actor' : '') + (c.opens ? ' host' : ''), tabindex: 0, role: 'button', 'aria-label': c.id + ', ' + c.p + (c.opens ? ', opens a map of ' + c.opens.parts + ' parts' : '')}, m.gCards);
  if (c.opens) el('rect', {x: b[0] + 4, y: b[1] + 4, width: b[2], height: b[3], rx: rx, class: 'under'}, cg);
  el('rect', {x: b[0] - 3, y: b[1] - 3, width: b[2] + 6, height: b[3] + 6, rx: rx + 3, class: 'ring'}, cg);
  el('rect', {x: b[0], y: b[1], width: b[2], height: b[3], rx: rx, class: 'box'}, cg);
  el('text', {x: tx, y: b[1] + b[3] / 2 - 1.5, class: 'nm'}, cg, c.id);
  el('text', {x: tx, y: b[1] + b[3] / 2 + 13, class: 'pl'}, cg, c.p);
  if (c.k !== 'actor' && c.k !== 'component') el('text', {x: b[0] + b[2] - 9, y: b[1] + 14, class: 'kind'}, cg, c.k);
  if (c.opens) picture(c, cg);
  cg.addEventListener('pointerenter', function (e) { if (e.pointerType !== 'touch') point(c, null); });
  cg.addEventListener('pointerleave', function () { point(null, null); });
  cg.addEventListener('focus', function () { point(c, null); });
  cg.addEventListener('blur', function () { point(null, null); });
  cg.addEventListener('click', function (e) { e.stopPropagation(); act(c); });
  cg.addEventListener('dblclick', function (e) { e.stopPropagation(); if (c.opens) go(fitCam(c.opens)); });
  cg.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); if (e.shiftKey && c.opens) go(fitCam(c.opens)); else act(c); } });
}
// Remove the elements of a map that the camera is far from, and of the maps in it.
function drop(m) {
  m.kids.forEach(function (k) { if (k.g) drop(k); });
  m.g.remove(); m.g = null; m.t = 0; BUILT.splice(BUILT.indexOf(m), 1);
  if (m.host && m.host.pic) m.host.pic.classList.remove('gone');
  if (sel && sel.map === m) sel = null;
  if (hot && hot.map === m) hot = null;
  if (hotFlow && hotFlow.map === m) hotFlow = null;
}
function act(c) {
  if (c.map.host && c.k === 'actor') { go(fitCam(c.map.up)); return; }
  sel = sel === c ? null : c; light();
}

// ---- the lines of a layer: parallel lanes, round corners, a casing at each crossing -------
function lanes(list) {
  [0, 1].forEach(function (ax) {
    var segs = [];
    list.forEach(function (f) {
      for (var i = 0; i + 1 < f.q.length; i++) {
        var a = f.q[i], b = f.q[i + 1];
        if (Math.abs(a[ax] - b[ax]) < 0.01 && Math.abs(a[1 - ax] - b[1 - ax]) > 1) segs.push({f: f, i: i, c: Math.round(a[ax] * 2) / 2, lo: Math.min(a[1 - ax], b[1 - ax]), hi: Math.max(a[1 - ax], b[1 - ax])});
      }
    });
    segs.sort(function (a, b) { return a.c - b.c || a.lo - b.lo; });
    var k = 0;
    while (k < segs.length) {
      var group = [segs[k]], hi = segs[k].hi, j = k + 1;
      while (j < segs.length && segs[j].c === segs[k].c && segs[j].lo < hi - 2) { group.push(segs[j]); hi = Math.max(hi, segs[j].hi); j++; }
      if (group.length > 1) {
        group.sort(function (a, b) { return a.f.i - b.f.i; });
        group.forEach(function (s, n) { var d = (n - (group.length - 1) / 2) * LANE; s.f.q[s.i][ax] += d; s.f.q[s.i + 1][ax] += d; });
      }
      k = j;
    }
  });
}
function pathOf(q) {
  var d = 'M' + q[0][0] + ' ' + q[0][1];
  for (var i = 1; i < q.length - 1; i++) {
    var a = q[i - 1], p = q[i], b = q[i + 1], la = Math.hypot(p[0] - a[0], p[1] - a[1]), lb = Math.hypot(b[0] - p[0], b[1] - p[1]), r = Math.min(7, la / 2, lb / 2);
    if (r < 0.5) { d += 'L' + p[0] + ' ' + p[1]; continue; }
    d += 'L' + (p[0] - (p[0] - a[0]) / la * r) + ' ' + (p[1] - (p[1] - a[1]) / la * r) + 'Q' + p[0] + ' ' + p[1] + ' ' + (p[0] + (b[0] - p[0]) / lb * r) + ' ' + (p[1] + (b[1] - p[1]) / lb * r);
  }
  var z = q[q.length - 1], y = q[q.length - 2], l = Math.hypot(z[0] - y[0], z[1] - y[1]) || 1;
  return d + 'L' + (z[0] - (z[0] - y[0]) / l * 5) + ' ' + (z[1] - (z[1] - y[1]) / l * 5);
}
function head(q) {
  var z = q[q.length - 1], y = q[q.length - 2], l = Math.hypot(z[0] - y[0], z[1] - y[1]) || 1, ux = (z[0] - y[0]) / l, uy = (z[1] - y[1]) / l, s = 7.5, w = 3.6;
  return [z[0], z[1], z[0] - ux * s - uy * w, z[1] - uy * s + ux * w, z[0] - ux * s + uy * w, z[1] - uy * s - ux * w].join(' ');
}
function seg(q, i) { return Math.abs(q[i + 1][0] - q[i][0]) + Math.abs(q[i + 1][1] - q[i][1]); }
function mid(q) { var i = Math.floor((q.length - 1) / 2); return {x: (q[i][0] + q[i + 1][0]) / 2, y: (q[i][1] + q[i + 1][1]) / 2}; }
function hits(b, list, skip) {
  for (var n = 0; n < list.length; n++) {
    if (list[n] === skip) continue;
    var q = list[n].q;
    for (var i = 0; i + 1 < q.length; i++) if (Math.min(q[i][0], q[i + 1][0]) <= b[2] && Math.max(q[i][0], q[i + 1][0]) >= b[0] && Math.min(q[i][1], q[i + 1][1]) <= b[3] && Math.max(q[i][1], q[i + 1][1]) >= b[1]) return true;
  }
  return false;
}
function over(a, b) { return a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1]; }
function short(a) { return a.length > 30 ? a.slice(0, 28).replace(/[ ,]+$/, '') + '…' : a; }
function walls(m) {
  return m.cards.map(function (c) { return [c.b[0] - 3, c.b[1] - 3, c.b[0] + c.b[2] + 3, c.b[1] + c.b[3] + 3]; })
    .concat(m.regions.map(function (r) { return [r.b[0], r.b[1] + 6, r.b[0] + 40 + r.n.length * 6.6, r.b[1] + 28]; }))
    .concat(m.boxes.map(function (b) { return [b.b[0] + 12, b.b[1] + 16, b.b[0] + 230, b.b[1] + 38]; }));
}
function seat(f, fs, wall, taken, lines) {
  var w = f.lbl.length * fs * 0.56 + 8, hh = fs * 1.35, best = null;
  var flat = function (i) { return Math.abs(f.q[i][1] - f.q[i + 1][1]) < 0.01; };
  var order = f.q.slice(0, -1).map(function (p, i) { return i; }).sort(function (a, b) { return (flat(b) - flat(a)) || seg(f.q, b) - seg(f.q, a); });
  order.forEach(function (i) {
    if (best) return;
    var a = f.q[i], b = f.q[i + 1], L = seg(f.q, i), need = (flat(i) ? w : hh) + 18;
    if (L < need) return;
    [0.5, 0.35, 0.65, 0.22, 0.78, 0.12, 0.88].forEach(function (t) {
      if (best) return;
      var cx = a[0] + (b[0] - a[0]) * t, cy = a[1] + (b[1] - a[1]) * t, box = [cx - w / 2, cy - hh / 2, cx + w / 2, cy + hh / 2];
      if (wall.some(function (c) { return over(box, c); }) || taken.some(function (o) { return over(box, o); })) return;
      if (!hits(box, lines, f)) best = {x: cx, y: cy, box: box};
    });
  });
  return best;
}
function put(f, at, fs) { f.tx.setAttribute('x', at.x); f.tx.setAttribute('y', at.y + fs * 0.34); f.tx.style.fontSize = fs + 'px'; }
// At rest a line has a label only if the label is on no card, on no name of a region and on no other
// label, and no other line goes through it.
function place(m) {
  if (!m.g) return;
  var list = m.shown, fs = m.fs = Math.min(15, 11 / (cam.k * m.s)), taken = [], wall = walls(m);
  list.slice().sort(function (a, b) { return a.len - b.len; }).forEach(function (f) {
    var best = seat(f, fs, wall, taken, list);
    f.rest = !!best; f.lab = best || mid(f.q);
    if (best) taken.push(best.box);
  });
  list.forEach(function (f) { put(f, f.lab, fs); f.tx.setAttribute('class', f.rest ? '' : 'rest0'); });
  relit(m);
}
function relit(m) {
  var lit = m.shown.filter(function (f) { return f.g.classList.contains('lit'); }), wall = walls(m);
  var taken = lit.filter(function (f) { return f.rest; }).map(function (f) { return f.lab.box; });
  lit.filter(function (f) { return !f.rest; }).forEach(function (f) {
    var at = seat(f, m.fs, wall, taken, lit) || seat(f, m.fs, wall, taken, []) || seat(f, m.fs, [], taken, []);
    if (!at) {
      var w = f.lbl.length * m.fs * 0.56 + 8, hh = m.fs * 1.35, c = mid(f.q), n = 0;
      at = {x: c.x, y: c.y, box: [c.x - w / 2, c.y - hh / 2, c.x + w / 2, c.y + hh / 2]};
      while (n++ < 6 && taken.some(function (o) { return over(at.box, o); })) { at.y -= hh; at.box[1] -= hh; at.box[3] -= hh; }
    }
    taken.push(at.box); put(f, at, m.fs);
  });
}
function setLayer(m, id) {
  var lay = m.layers.filter(function (l) { return l.id === id; })[0] || m.layers[m.layers.length - 1];
  m.layer = m.mapLayer = lay;
  m.shown = lay.e.map(function (i) { return m.flows[i]; });
  m.cards.forEach(function (c) { c.fl = []; });
  m.gFlows.textContent = '';
  m.shown.forEach(function (f) { f.q = f.p.map(function (p) { return [p[0], p[1]]; }); f.len = 0; m.byId[f.s].fl.push(f); m.byId[f.t].fl.push(f); });
  lanes(m.shown);
  m.shown.forEach(function (f) {
    for (var i = 0; i + 1 < f.q.length; i++) f.len += seg(f.q, i);
    var g = f.g = el('g', {class: 'flow'}, m.gFlows), d = pathOf(f.q);
    g.style.setProperty('--k', kvar(f));
    el('path', {d: d, class: 'case'}, g); f.w = el('path', {d: d, class: 'wire'}, g);
    el('circle', {cx: f.q[0][0], cy: f.q[0][1], r: 2}, g); el('polygon', {points: head(f.q)}, g);
    f.lbl = short(f.a);
    f.tx = el('text', {}, g, f.lbl);
    var hit = el('path', {d: d, class: 'hit'}, g);
    hit.addEventListener('pointerenter', function (e) { if (e.pointerType !== 'touch') point(null, f); });
    hit.addEventListener('pointerleave', function () { point(null, null); });
    hit.addEventListener('click', function (e) { e.stopPropagation(); point(null, f); });
  });
  var used = {}; m.shown.forEach(function (f) { used[f.s] = used[f.t] = 1; });
  m.g.classList.toggle('dense', m.shown.length > 48);
  m.used = used; m.none = !m.shown.length;
  m.cards.forEach(function (c) { c.g.classList.toggle('quiet', !m.none && !used[c.id]); });
  m.g.style.setProperty('--rest', Math.max(0.3, Math.min(1, 1.25 - m.shown.length / 56)).toFixed(2));
  m.g.style.setProperty('--ends', Math.max(0.75, Math.min(1, 1.25 - m.shown.length / 160)).toFixed(2));
  place(m);
  if (m === cur) { chrome(); light(); }
}

// ---- the headline, the tabs and the key of the map that the camera is in -------------------
var askTimer = 0;
function chrome() {
  var m = cur, lay = m.layer, tabs = document.getElementById('tabs'), ask = document.getElementById('ask');
  tabs.textContent = '';
  m.layers.forEach(function (l) {
    var t = h('button', 'tab', l.n); t.setAttribute('role', 'tab'); t.setAttribute('aria-selected', l === lay ? 'true' : 'false');
    if (l.e.length) t.appendChild(h('i', '', l.e.length));
    t.addEventListener('click', function () { setLayer(m, l.id); });
    tabs.appendChild(t);
  });
  var actors = m.cards.filter(function (c) { return c.k === 'actor' && m.used[c.id]; }).length, comps = Object.keys(m.used).length - actors;
  ask.classList.add('swap'); clearTimeout(askTimer);
  askTimer = setTimeout(function () {
    var k = document.getElementById('ask-k'), path = [], up = m.up;
    k.textContent = '';
    while (up) { path.unshift(up); up = up.up; }
    path.forEach(function (p) { var b = h('button', '', p.name); b.title = 'Go out (Esc)'; b.addEventListener('click', function () { go(fitCam(p)); }); k.appendChild(b); k.appendChild(h('span', '', '/')); });
    if (path.length) { k.appendChild(h('b', '', m.name)); k.appendChild(h('span', '', '·')); }
    k.appendChild(h('span', '', lay.n));
    document.getElementById('ask-q').textContent = lay.q;
    document.getElementById('ask-n').textContent = m.none ? plural(m.cards.length, 'card') + ' in ' + plural(m.regions.length, 'region')
      : (actors ? plural(actors, m.host ? 'neighbour' : 'actor') + ' · ' : '') + plural(comps, m.host ? 'part' : 'component') + ' · ' + plural(m.shown.length, 'flow');
    ask.classList.remove('swap');
  }, started ? 150 : 0);
  var kinds = {}; m.shown.forEach(function (f) { kinds[f.k] = 1; });
  var key = document.getElementById('key'); key.textContent = '';
  Object.keys(KIND).forEach(function (n) { if (!kinds[n]) return; var s = h('span'), i = h('i'); i.style.setProperty('--k', 'var(' + KIND[n][0] + ')'); s.appendChild(i); s.appendChild(document.createTextNode(KIND[n][1])); key.appendChild(s); });
}

// ---- pointing ----------------------------------------------------------------------------------
function point(c, f) {
  if ((c && c.map !== cur) || (f && f.map !== cur)) return;
  hot = c; hotFlow = f; light();
}
function light() {
  var m = cur, c = hot || (hotFlow ? null : (sel && sel.map === m ? sel : null)), f = hotFlow, on = {}, any = !!(c || f), ke = cam.k * m.s;
  m.shown.forEach(function (x) {
    var lit = f ? x === f : c ? (x.s === c.id || x.t === c.id) : false, was = x.g.classList.contains('lit');
    x.g.classList.toggle('lit', lit);
    if (lit) { on[x.s] = on[x.t] = 1; m.gFlows.appendChild(x.g); }
    if (lit && !was && !REDUCE) { var L = Math.ceil(x.len * ke) + 6; x.w.style.strokeDasharray = L; x.w.style.setProperty('--len', L); x.g.classList.remove('draw'); void x.w.getBoundingClientRect(); x.g.classList.add('draw'); }
    if (!lit) { x.g.classList.remove('draw'); x.w.style.strokeDasharray = ''; }
  });
  if (c) on[c.id] = 1;
  m.cards.forEach(function (x) { x.g.classList.toggle('lit', !!on[x.id]); x.g.classList.toggle('sel', x === sel); });
  var some = m.shown.some(function (x) { return x.g.classList.contains('lit'); });
  m.g.classList.toggle('focus', any && (some || !!f));
  if (m.fs) relit(m);
  speak(c, f);
}
function speak(c, f) {
  var say = document.getElementById('say'); say.textContent = '';
  if (f) {
    var b = h('b'); b.appendChild(document.createTextNode(f.s)); b.appendChild(h('span', 'arr', '→')); b.appendChild(document.createTextNode(f.t));
    var code = h('code', '', f.a); code.style.setProperty('--k', kvar(f));
    say.appendChild(b); say.appendChild(code);
  } else if (c && c !== sel) {
    var ins = c.fl.filter(function (x) { return x.t === c.id; }).length, outs = c.fl.length - ins;
    say.appendChild(h('b', '', c.id));
    var words = c.p + (c.fl.length ? ' · receives ' + ins + ', gives ' + outs : ' · no flow in this layer');
    if (c.opens) words += ' · double-click to see its ' + c.opens.parts + ' parts';
    say.appendChild(h('span', '', words));
  }
  say.classList.toggle('on', !!(f || (c && c !== sel)));
}

// ---- the camera, the maps near it, and the map that it is in -----------------------------------
var raf = 0, relabel = 0;
function smooth(a, b, v) { var t = Math.max(0, Math.min(1, (v - a) / (b - a))); return t * t * (3 - 2 * t); }
function screenOf(m) { return [(m.ox - cam.x) * cam.k, (m.oy - cam.y) * cam.k, m.size[0] * m.s * cam.k, m.size[1] * m.s * cam.k]; }
// The building rule: a nested map is built when its frame is RULE.build px wide or more and it is in
// the screen or in a margin of RULE.margin times the screen around it. It is removed when its frame is
// less than RULE.drop px wide or out of that area.
function near(m) {
  m.kids.forEach(function (k) {
    var r = screenOf(k), mx = W * RULE.margin, my = H * RULE.margin;
    var inside = r[0] < W + mx && r[0] + r[2] > -mx && r[1] < H + my && r[1] + r[3] > -my;
    if (!k.g && inside && r[2] >= RULE.build) build(k);
    else if (k.g && (!inside || r[2] < RULE.drop)) drop(k);
    if (k.g) near(k);
  });
}
function apply() {
  var step = 24 * Math.pow(2, -Math.round(Math.log2(Math.max(0.5, Math.min(2, cam.k))))) * cam.k; if (step < 14) step *= 2; if (step > 34) step /= 2;
  dot.setAttribute('width', step); dot.setAttribute('height', step); dot.setAttribute('patternTransform', 'translate(' + (-cam.x * cam.k % step) + ' ' + (-cam.y * cam.k % step) + ')');
  near(TOP);
  var into = TOP;
  BUILT.forEach(function (m) {
    var r = screenOf(m);
    m.g.setAttribute('transform', 'translate(' + r[0] + ' ' + r[1] + ') scale(' + cam.k * m.s + ')');
    m.g.classList.toggle('far', cam.k * m.s < 0.95);
    if (!m.host) return;
    // t is 0 when the nested map is a small picture in its card, and 1 when it has the screen.
    var t = smooth(0.16, 0.5, Math.max(r[2] / W, r[3] / H)), cx = r[0] + r[2] / 2, cy = r[1] + r[3] / 2;
    m.t = cx > 0 && cx < W && cy > 0 && cy < H ? t : 0;
    m.g.classList.toggle('thumb', t < 0.2);
    if (m.t > 0.5 && (into === TOP || depth(m) > depth(into))) into = m;
  });
  // The map above goes away as the nested map takes the screen.
  BUILT.forEach(function (m) {
    var deep = 0; m.kids.forEach(function (k) { if (k.g) deep = Math.max(deep, k.t); });
    m.g.style.opacity = deep > 0.02 ? String(1 - deep) : '';
    m.g.style.pointerEvents = deep > 0.5 ? 'none' : '';
    m.g.classList.toggle('hid', deep > 0.99);
  });
  if (into !== cur) { var old = cur; cur = into; if (old && old.g) old.g.classList.remove('focus'); hot = hotFlow = null; if (sel && sel.map !== cur) sel = null; chrome(); light(); }
  document.getElementById('zv').textContent = Math.round(cam.k * cur.s * 100) + '%';
  clearTimeout(relabel); relabel = setTimeout(function () { place(cur); }, 140);
}
function depth(m) { var n = 0; while (m.up) { n++; m = m.up; } return n; }
function frame(m) { return [m.ox, m.oy, m.size[0] * m.s, m.size[1] * m.s]; }
// The camera that fits a map under the headline, as fitMap of the study does.
function fitCam(m) {
  var wide = W > 720, right = 24, bottom = 30, b = frame(m);
  var fitK = function (left, top) { return Math.min((W - left - right) / b[2], (H - top - bottom) / b[3], 1.6 / m.s); };
  var beside = W - right > 1180 && fitK(330, 26) >= fitK(20, 112), top = beside ? 26 : wide ? 112 : 96, left = beside ? 330 : 20;
  document.getElementById('ask').classList.toggle('beside', beside);
  var k = fitK(left, top);
  if (!wide && k * m.s < 0.5) { k = 0.5 / m.s; return {k: k, x: b[0] - 14 / k, y: b[1] - top / k}; }
  var free = H - top - bottom - b[3] * k, lift = beside ? free / 2 : Math.min(free / 2, 10);
  return {k: k, x: b[0] + b[2] / 2 - (left + (W - left - right) / 2) / k, y: b[1] - (top + lift) / k};
}
function go(to, now) {
  cancelAnimationFrame(raf);
  if (now || REDUCE) { cam = to; apply(); return; }
  var from = {x: cam.x, y: cam.y, k: cam.k}, big = Math.abs(Math.log(to.k / from.k)), ms = 320 + Math.min(520, big * 190), t0 = performance.now();
  (function step(t) {
    var u = Math.min(1, (t - t0) / ms), e = u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2;
    cam = between(from, to, e); apply();
    if (u < 1) raf = requestAnimationFrame(step);
  })(t0);
}
// The camera at the part e of a move from `from` to `to`. A move with a large change of zoom goes at one
// rate in the logarithm of the zoom.
function between(from, to, e) {
  var k = from.k * Math.pow(to.k / from.k, e), big = Math.abs(Math.log(to.k / from.k));
  var fc = [from.x + W / 2 / from.k, from.y + H / 2 / from.k], tc = [to.x + W / 2 / to.k, to.y + H / 2 / to.k];
  var w = big > 0.05 ? (1 / from.k - 1 / k) / (1 / from.k - 1 / to.k) : e;
  return {k: k, x: fc[0] + (tc[0] - fc[0]) * w - W / 2 / k, y: fc[1] + (tc[1] - fc[1]) * w - H / 2 / k};
}
function zoomAt(px, py, f) { var k = Math.max(0.3, Math.min(1e7, cam.k * f)), wx = cam.x + px / cam.k, wy = cam.y + py / cam.k; cam = {k: k, x: wx - px / k, y: wy - py / k}; apply(); }
svg.addEventListener('wheel', function (e) { e.preventDefault(); cancelAnimationFrame(raf); var r = svg.getBoundingClientRect(); zoomAt(e.clientX - r.left, e.clientY - r.top, Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.0016))); }, {passive: false});
var drag = null, moved = false;
svg.addEventListener('pointerdown', function (e) { cancelAnimationFrame(raf); drag = {x: e.clientX, y: e.clientY, cx: cam.x, cy: cam.y}; moved = false; });
svg.addEventListener('pointermove', function (e) {
  if (!drag) return;
  var dx = e.clientX - drag.x, dy = e.clientY - drag.y;
  if (!moved && Math.hypot(dx, dy) < 4) return;
  if (!moved) { moved = true; svg.classList.add('drag'); try { svg.setPointerCapture(e.pointerId); } catch (err) { /* no capture */ } }
  cam = {x: drag.cx - dx / cam.k, y: drag.cy - dy / cam.k, k: cam.k}; apply();
});
function up() { drag = null; svg.classList.remove('drag'); }
svg.addEventListener('pointerup', up); svg.addEventListener('pointercancel', up);
svg.addEventListener('click', function () { if (!moved) { if (hotFlow) point(null, null); else if (sel) { sel = null; light(); } } });
document.getElementById('zi').addEventListener('click', function () { zoomAt(W / 2, H / 2, 1.25); });
document.getElementById('zo').addEventListener('click', function () { zoomAt(W / 2, H / 2, 0.8); });
document.getElementById('zf').addEventListener('click', function () { go(fitCam(cur)); });
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') { if (sel) { sel = null; light(); } else if (cur.up) go(fitCam(cur.up)); }
  if ((e.key === 'f' || e.key === 'F') && !e.metaKey && !e.ctrlKey) go(fitCam(cur));
});
addEventListener('resize', function () { size(); go(fitCam(cur), true); });

// ---- start ----------------------------------------------------------------------------------------
size(); prepare(); build(TOP); cur = TOP; go(fitCam(TOP), true); chrome(); light(); place(TOP);
started = true;
var READY = {built: performance.now(), painted: 0};
requestAnimationFrame(function () { setTimeout(function () { READY.painted = performance.now(); }, 0); });
// The interface of the measurement (bench/jev/atlas_frames.js).
window.atlas = {
  ready: READY,
  view: function (c) { cancelAnimationFrame(raf); cam = {x: c.x, y: c.y, k: c.k}; apply(); },
  fit: function (id) { return fitCam(BY[id]); },
  between: between,
  // The deepest map below the first card that opens a map.
  deep: function () { var m = TOP; while (m.kids.length) m = m.kids[0]; return m.id; },
  count: function () { return document.getElementsByTagNameNS(NS, '*').length; },
  built: function () { return BUILT.map(function (m) { return m.id; }); },
  current: function () { return cur.id; }
};
})();
