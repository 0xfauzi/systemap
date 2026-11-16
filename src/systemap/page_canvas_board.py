"""The boards of the canvas page: a sequence as a diagram, and a state machine.

This is a prototype (docs/design/views.md). A board is a diagram that is not the map. It
shows items of the same model in a different form, on the same canvas, with the fonts,
the colors and the plates of the map. A board covers the map below the header. The path,
the caption and the help line stay over it. While a board shows, the wheel and a drag do
not move the map, and a click on empty space of the board selects no card.

- The sequence board. In the Sequences view, the toolbar has "On the map" and "As a
  diagram". The diagram gives one column for each component of the sequence, in the order
  of the steps, and one row for each step: a line from the source to the target, with the
  step number and the artifact. The line of a step has the color and the alpha that the
  route has on the map (`seqKind`). A click on a row shows that step.
- The state board. The States view shows one state machine of a map (`sm` in the canvas
  data, from `canvas_states`): one box for each state, in the columns of `states.layout`,
  and one line for each transition, with its label. A first state has a dashed border. A
  click selects a state or a transition. The caption gives the cause of the selected
  transition. The Details panel gives the same items as a list with buttons, and for a
  transition, "Show the flow on the map" and "Show the sequence". Thus a transition, a flow
  and a step of a sequence are one item in three views.

The States view registers only when a map of the tree has a state machine. Else the header
hides its button. The board fades in and out with the step of the view. The Details panel
is the form of a board for a keyboard and for a screen reader: the canvas drawing has no
elements. When the panel is open at the right of a wide screen, a board uses the space at
the left of the panel.
"""

from __future__ import annotations

HTML = (
    '<div class="cst cview" id="cst" role="toolbar" aria-label="State machine" hidden>'
    '<label for="cst-pick">State machine</label><select id="cst-pick"></select>'
    '<span class="cst__count" id="cst-count"></span></div>'
)

CSS = """
.cbar .cst{position:fixed;left:0;right:0;top:48px;z-index:4;box-sizing:border-box;
display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;padding:8px 16px;
border-bottom:1px solid var(--line);background:var(--surface)}
.cbar .cst[hidden]{display:none}
.cst label{font:600 11px/16px var(--fm);letter-spacing:.08em;text-transform:uppercase;
color:var(--ink-3)}
.cbar .cst select{height:30px}
.cbar .cst select{max-width:min(360px,100%);padding:0 8px;border-color:var(--line-2);
background:var(--map);color:var(--ink)}
.cst__count{font:12px var(--fm);color:var(--ink-2)}
.cbar .cseq__form{display:flex;flex:none;gap:2px}
.cbar .cseq__form button{padding:0 12px}
@media (pointer:coarse){.cbar .cst{top:56px;padding:6px 8px}}
"""

BOARD = r"""
// ---- the boards (page_canvas_board) ------------------------------------------------------
// BOARD.a is the part of the board that shows. BOARD.draw is the board of the last frame
// that had one, so that it can fade out.
var BOARD = {a: 0, draw: null}, ST_MAPS = ORDER.filter(function (m) { return m.sm && m.sm.length; });
var ST = {m: ST_MAPS[0] || null, k: 0, tr: -1, st: -1}, ST_BAR = document.getElementById('cst'), ST_BAND = {h: 0};
function boardWant() {
  if (VIEW.mode === 'states' && ST.m) return stateBoard;
  if (VIEW.mode === 'sequences' && SEQ.form === 'diagram' && SEQ.j) return seqBoard;
  return null;
}
function boardOn() { return BOARD.a > 0.5; }
// The free box of a board, and the scale and the origin that fit a drawing of bw x bh.
// When the Details panel is open at the right of a wide screen, the box ends before the panel.
var BOARD_PANEL = document.getElementById('cdetails');
function boardFit(bw, bh) {
  var x0 = 24, y0 = HEAD_H + PATH_H + 34, x1 = W - 24, y1 = H - 48;
  if (BOARD_PANEL && !BOARD_PANEL.hidden && BOARD_PANEL.classList.contains('on') && W > 900) x1 = Math.min(x1, BOARD_PANEL.getBoundingClientRect().left - 16);
  var k = clamp(Math.min((x1 - x0) / bw, (y1 - y0) / bh), 0.3, 1.3);
  return {k: k, x: (x0 + x1) / 2 - bw * k / 2, y: Math.max(y0, (y0 + y1) / 2 - bh * k / 2)};
}
function boardHit(x, y, w, h, go, kind) { HITS.push({x: x, y: y, w: w, h: h, kind: kind || 'board-item', id: '', go: go, show: 1}); }
function drawBoard() {
  var want = boardWant(), to = want ? 1 : 0;
  if (want) BOARD.draw = want;
  BOARD.a = approach(BOARD.a, to, VIEW_STEP);
  if (BOARD.a !== to) VIEW_FADING = true;
  if (BOARD.a <= 0.01 || !BOARD.draw) return;
  ctx.globalAlpha = BOARD.a; ctx.fillStyle = C['--map']; ctx.fillRect(0, HEAD_H, W, H - HEAD_H);
  // A click on empty space of the board does nothing. It selects no card of the map.
  if (boardOn()) HITS.push({x: 0, y: HEAD_H, w: W, h: H - HEAD_H, kind: 'board', id: '', go: function () {}, show: 1});
  BOARD.draw(BOARD.a);
}
function boardLine(x1, y1, x2, y2, color, width, alpha) {
  ctx.globalAlpha = alpha; ctx.strokeStyle = color; ctx.lineWidth = width; ctx.setLineDash([]); ctx.lineCap = 'round';
  ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
}
function boardHead(x, y, an, size, color, alpha) {
  ctx.globalAlpha = alpha; ctx.fillStyle = color; ctx.beginPath(); arrowHead(ctx, x, y, x - Math.cos(an), y - Math.sin(an), size); ctx.fill();
}
function boardBox(x, y, w, h, r, fill, line, width, dash, alpha) {
  ctx.globalAlpha = alpha; ctx.setLineDash(dash || []); ctx.beginPath(); rr(ctx, x, y, w, h, r);
  ctx.fillStyle = fill; ctx.fill(); ctx.strokeStyle = line; ctx.lineWidth = width; ctx.stroke(); ctx.setLineDash([]);
}

// ---- the sequence board ----------------------------------------------------------------
function seqParts(m, j) {
  var out = [];
  j.s.forEach(function (st) {
    var f = st.f >= 0 ? m.flows[st.f] : null;
    (f ? [f.s, f.t] : st.a || []).forEach(function (id) { if (out.indexOf(id) < 0 && m.byId[id]) out.push(id); });
  });
  return out;
}
var SQ_COL = 176, SQ_CARD = 148, SQ_ROW = 56, SQ_TOP = 78;
function seqBoard(alpha) {
  var m = SEQ.m, j = SEQ.j, parts = seqParts(m, j), n = j.s.length;
  var bw = Math.max(1, parts.length - 1) * SQ_COL + SQ_CARD, bh = SQ_TOP + n * SQ_ROW + 10, v = boardFit(bw, bh), k = v.k;
  function X(id) { return v.x + (SQ_CARD / 2 + Math.max(0, parts.indexOf(id)) * SQ_COL) * k; }
  parts.forEach(function (id) {
    var c = m.byId[id], x = X(id), w = SQ_CARD * k, h = 40 * k, actor = c.k === 'actor';
    ctx.globalAlpha = alpha * 0.9; ctx.strokeStyle = C['--line-2']; ctx.lineWidth = 1; ctx.setLineDash([3, 4]);
    ctx.beginPath(); ctx.moveTo(x, v.y + h); ctx.lineTo(x, v.y + bh * k); ctx.stroke(); ctx.setLineDash([]);
    boardBox(x - w / 2, v.y, w, h, 8 * k, actor ? C['--actor'] : C['--card'], C['--card-line'], 1.1, actor ? [4, 3] : null, alpha);
    text(fit(id, 12.5 * k, w - 12, 600), x, v.y + h / 2 + 4.5 * k, 12.5 * k, C['--ink'], alpha, 600, false, 'center');
    if (boardOn()) boardHit(x - w / 2, v.y, w, h, function () { select(c); });
  });
  j.s.forEach(function (st, i) {
    var f = st.f >= 0 ? m.flows[st.f] : null, y = v.y + (SQ_TOP + i * SQ_ROW + 22) * k, kind = seqKind(i), now = kind === 'now';
    var al = alpha * (kind === 'later' ? 0.42 : kind === 'was' ? 0.7 : 1), r = 9 * k;
    if (f) {
      var x1 = X(f.s), x2 = X(f.t), dir = x2 >= x1 ? 1 : -1, color = now ? C['--accent'] : flowColor(f, null), w = (now ? 3 : 1.7) * Math.max(0.8, k);
      boardLine(x1 + dir * r, y, x2 - dir * 5 * k, y, color, w, al);
      boardHead(x2 - dir * 1.5, y, dir > 0 ? 0 : Math.PI, 9 * k, color, al);
      text(f.a, (x1 + x2) / 2, y - 8 * k, 12 * k, C['--ink'], al, now ? 700 : 400, false, 'center');
      ctx.globalAlpha = al; ctx.beginPath(); ctx.arc(x1, y, r, 0, Math.PI * 2);
      ctx.fillStyle = now ? C['--accent'] : C['--map']; ctx.fill(); ctx.strokeStyle = C['--card-line']; ctx.lineWidth = 1; ctx.stroke();
      text(String(i + 1), x1, y + 3.6 * k, Math.max(MIN_TEXT, 10.5 * k), now ? C['--on-accent'] : C['--ink'], al, 700, true, 'center');
    } else {
      var x = X((st.a || [])[0]), s = (i + 1) + ' · no flow';
      boardBox(x - 56 * k, y - 12 * k, 112 * k, 24 * k, 12 * k, C['--map'], now ? C['--accent'] : C['--card-line'], now ? 2.5 : 1.1, null, al);
      text(s, x, y + 4 * k, 11.5 * k, C['--ink'], al, 400, false, 'center');
    }
    if (boardOn()) boardHit(v.x, y - SQ_ROW * k / 2, bw * k, SQ_ROW * k, function () { seqMode(true, i, false); });
  });
}
function seqFormSync() {
  var a = document.getElementById('cseq-onmap'), b = document.getElementById('cseq-diagram');
  if (a) a.setAttribute('aria-pressed', String(SEQ.form !== 'diagram'));
  if (b) b.setAttribute('aria-pressed', String(SEQ.form === 'diagram'));
}
function seqForm(form) {
  SEQ.form = form; seqFormSync(); viewTouch();
  say(form === 'diagram' ? 'The sequence shows as a diagram.' : 'The sequence shows on the map.');
}
SEQ.form = 'map';
['onmap', 'diagram'].forEach(function (id) {
  var b = document.getElementById('cseq-' + id);
  if (b) b.addEventListener('click', function () { seqForm(id === 'diagram' ? 'diagram' : 'map'); });
});
seqFormSync();

// ---- the state board -------------------------------------------------------------------
var SM_W = 190, SM_H = 62, SM_COL = 330, SM_ROW = 176;
function machine() { return ST.m ? ST.m.sm[ST.k] : null; }
// The middle of each state in board units, and the size of the board.
function stateSpots(mc) {
  var rows = {}, cols = 0, most = 1;
  mc.st.forEach(function (s) { rows[s.c] = Math.max(rows[s.c] || 0, s.r + 1); cols = Math.max(cols, s.c + 1); });
  Object.keys(rows).forEach(function (c) { most = Math.max(most, rows[c]); });
  var bh = (most - 1) * SM_ROW + SM_H + 40;
  return {w: (cols - 1) * SM_COL + SM_W, h: bh, at: mc.st.map(function (s) {
    return [SM_W / 2 + s.c * SM_COL, SM_H / 2 + 20 + s.r * SM_ROW];
  })};
}
// The point where the line from the middle of a box to a point leaves the box.
function boxEdge(c, to, w, h) {
  var dx = to[0] - c[0], dy = to[1] - c[1], t = 1 / Math.max(Math.abs(dx) / (w / 2), Math.abs(dy) / (h / 2), 1e-6);
  return [c[0] + dx * t, c[1] + dy * t];
}
function stateBoard(alpha) {
  var mc = machine();
  if (!mc) return;
  var sp = stateSpots(mc), v = boardFit(sp.w, sp.h), k = v.k;
  function P(p) { return [v.x + p[0] * k, v.y + p[1] * k]; }
  mc.tr.forEach(function (t, i) {
    var a = P(sp.at[t.a]), b = P(sp.at[t.b]), on = ST.tr === i, dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy) || 1;
    // The line bends to its right. Thus two transitions between the same two states, one in each direction, do not cover each other.
    var nx = -dy / len, ny = dx / len, bend = 34 * k, c = [(a[0] + b[0]) / 2 + nx * bend, (a[1] + b[1]) / 2 + ny * bend];
    var p0 = boxEdge(a, c, SM_W * k + 4, SM_H * k + 4), p1 = boxEdge(b, c, SM_W * k + 8, SM_H * k + 8), color = on ? C['--accent'] : C['--ink-2'];
    ctx.globalAlpha = alpha; ctx.strokeStyle = color; ctx.lineWidth = on ? 3 : 1.6; ctx.setLineDash([]); ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(p0[0], p0[1]); ctx.quadraticCurveTo(c[0], c[1], p1[0], p1[1]); ctx.stroke();
    boardHead(p1[0], p1[1], Math.atan2(p1[1] - c[1], p1[0] - c[0]), 10 * Math.max(0.8, k), color, alpha);
    var fs = 12 * k, pw = unitWidth(t.l, on ? 700 : 500) * fs + 12, up = Math.abs(dy) / len;
    // The label of a line that goes up or down is at the side of the line, away from the opposite line.
    var mid = [(p0[0] + 2 * c[0] + p1[0]) / 4 + nx * up * (pw / 2 + 6), (p0[1] + 2 * c[1] + p1[1]) / 4];
    ctx.globalAlpha = alpha * 0.94; ctx.fillStyle = C['--map']; ctx.beginPath(); rr(ctx, mid[0] - pw / 2, mid[1] - fs * 0.9, pw, fs * 1.8, 4); ctx.fill();
    text(t.l, mid[0], mid[1] + fs * 0.36, fs, C['--ink'], alpha, on ? 700 : 500, false, 'center');
    if (boardOn()) boardHit(mid[0] - pw / 2 - 6, mid[1] - fs * 0.9 - 6, pw + 12, fs * 1.8 + 12, function () { stSelect(i, -1); });
  });
  mc.st.forEach(function (s, i) {
    var p = P(sp.at[i]), w = SM_W * k, h = SM_H * k, on = ST.st === i, sym = (s.sym || '').split('.').slice(-2).join('.');
    boardBox(p[0] - w / 2, p[1] - h / 2, w, h, h / 2, C['--card'], on ? C['--accent'] : C['--card-line'], on ? 3 : 1.2, s.first && !on ? [5, 4] : null, alpha);
    text(s.id, p[0], p[1] + (sym ? -1 : 5) * k, 14.5 * k, C['--ink'], alpha, 700, true, 'center');
    if (sym) text(fit(sym, 10.5 * k, w - 20, 400, true), p[0], p[1] + 17 * k, 10.5 * k, C['--ink-3'], alpha, 400, true, 'center');
    if (boardOn()) boardHit(p[0] - w / 2, p[1] - h / 2, w, h, function () { stSelect(-1, i); });
  });
}
function stSelect(tr, st) {
  ST.tr = tr === ST.tr ? -1 : tr; ST.st = st === ST.st ? -1 : st;
  var mc = machine(), t = mc.tr[ST.tr], s = mc.st[ST.st];
  say(t ? 'Transition from ' + mc.st[t.a].id + ' to ' + mc.st[t.b].id + ': ' + t.l + '. ' + (t.c || '') : s ? 'State ' + s.id + '. ' + (s.y || '') : stWords());
  stChanged();
}
function stChanged() { viewTouch(); HERE_HOOKS.forEach(function (f) { f(currentMap()); }); }
function stWords() {
  var mc = machine();
  return mc ? 'State machine: ' + mc.n + '. ' + counted(mc.st.length, 'state') + ' and ' + counted(mc.tr.length, 'transition') + '.' : '';
}
function stSync() {
  var pick = document.getElementById('cst-pick'), count = document.getElementById('cst-count'), mc = machine();
  if (!pick || !mc) return;
  if (!pick.options.length) ST_MAPS.forEach(function (m) {
    m.sm.forEach(function (x, k) { pick.appendChild(el('option', {value: m.oi + ':' + k}, (ST_MAPS.length > 1 ? mapName(m) + ': ' : '') + x.n)); });
  });
  pick.value = ST.m.oi + ':' + ST.k;
  count.textContent = counted(mc.st.length, 'state') + ' · ' + counted(mc.tr.length, 'transition') + ' · component ' + mc.of;
}
// The text of the Details panel: the selected transition or state, or the lists of the machine.
function stNodes() {
  var mc = machine(), m = ST.m, t = mc.tr[ST.tr], s = mc.st[ST.st], out = [el('h3', {tabindex: '-1'}, mc.n), el('p', null, 'State machine. Component: ' + mc.of + '. Map: ' + mapName(m) + '.')];
  if (t) {
    var f = t.f >= 0 ? m.flows[t.f] : null, q = t.q >= 0 && m.sq ? m.sq[t.q] : null;
    out.push(el('h4', null, 'TRANSITION'), el('p', null, el('b', null, mc.st[t.a].id + ' to ' + mc.st[t.b].id), ': ' + t.l + '.'),
      t.c ? el('p', null, t.c) : null, t.src ? el('p', null, 'Source: ', el('code', null, t.src), '.') : null,
      el('h4', null, 'THE SAME CHANGE IN THE OTHER VIEWS'),
      f ? el('p', null, el('button', {type: 'button', 'data-sm': 'flow'}, 'Show the flow on the map: ' + f.s + ' to ' + f.t + ', ' + f.a)) : el('p', null, 'No flow of the map causes this transition.'),
      q ? el('p', null, el('button', {type: 'button', 'data-sm': 'seq'}, 'Show the sequence: ' + q.n)) : null,
      el('p', null, el('button', {type: 'button', 'data-sm': 'all'}, 'All states and transitions')));
    return out;
  }
  if (s) {
    out.push(el('h4', null, 'STATE'), el('p', null, el('b', null, s.id), s.first ? '. A first state.' : '.'), s.y ? el('p', null, s.y) : null,
      s.sym ? el('p', null, 'Source symbol: ', el('code', null, s.sym), '.') : null,
      el('p', null, el('button', {type: 'button', 'data-sm': 'all'}, 'All states and transitions')));
    return out;
  }
  out.push(el('h4', null, 'STATES (' + mc.st.length + ')'), el('ul', null, mc.st.map(function (x, i) {
    return el('li', null, el('button', {type: 'button', 'data-sm': 'st', 'data-i': i}, x.id + (x.first ? ' (first state)' : '')));
  })), el('h4', null, 'TRANSITIONS (' + mc.tr.length + ')'), el('ul', null, mc.tr.map(function (x, i) {
    return el('li', null, el('button', {type: 'button', 'data-sm': 'tr', 'data-i': i}, mc.st[x.a].id + ' to ' + mc.st[x.b].id + ': ' + x.l));
  })), el('h4', null, 'FINDINGS (' + (mc.fd || []).length + ')'),
  (mc.fd || []).length ? (mc.fd || []).map(function (x) { return el('p', null, x); }) : el('p', null, 'Each state has a transition in and a transition out.'));
  return out;
}
function stClick(e) {
  var b = e.target.closest ? e.target.closest('[data-sm]') : null;
  if (!b || VIEW.mode !== 'states') return;
  var what = b.getAttribute('data-sm'), i = +b.getAttribute('data-i'), mc = machine(), t = mc.tr[ST.tr], m = ST.m;
  if (what === 'st') stSelect(-1, i);
  else if (what === 'tr') stSelect(i, -1);
  else if (what === 'all') { ST.tr = -1; ST.st = -1; stChanged(); }
  else if (what === 'flow' && t && t.f >= 0) { var f = m.flows[t.f]; setView('map'); viewFlowOn(f); flyGoal(goalOf(m, null, f)); }
  else if (what === 'seq' && t && t.q >= 0 && VIEWS.sequences) { seqChoose(m, t.q, false); setView('sequences'); }
}
if (ST_MAPS.length && ST_BAR) {
  var stBody = document.getElementById('cdet-body'), stPick = document.getElementById('cst-pick');
  if (stBody) stBody.addEventListener('click', stClick);
  if (stPick) stPick.addEventListener('change', function () {
    var v = stPick.value.split(':'); ST.m = ORDER[+v[0]]; ST.k = +v[1]; ST.tr = -1; ST.st = -1; stSync(); say(stWords()); stChanged();
  });
  VIEWS.states = {
    enter: function () {
      var m = currentMap();
      if (ST.m !== m && m.sm && m.sm.length) { ST.m = m; ST.k = 0; ST.tr = -1; ST.st = -1; }
      stSync(); barShow(ST_BAR, true); barBand(ST_BAR, ST_BAND, true);
    },
    leave: function () { barShow(ST_BAR, false, 'states'); },
    band: function (fresh) { return barBand(ST_BAR, ST_BAND, fresh); },
    box: function () { return ST_BAR; },
    words: stWords,
    caption: function () {
      var mc = machine(), t = mc && mc.tr[ST.tr], s = mc && mc.st[ST.st];
      if (t) return {k: mc.st[t.a].id + ' to ' + mc.st[t.b].id, s: t.c || t.l};
      if (s) return {k: s.id, s: s.y || 'A state of ' + mc.n + '.'};
      return mc ? {k: mc.n, s: 'Which states can this item have, and what causes each change?'} : null;
    },
    panel: function () {
      var mc = machine();
      return mc ? {key: 's' + ST.m.oi + ':' + ST.k + ':' + ST.tr + ':' + ST.st, nodes: stNodes} : null;
    }
  };
}
// The boards for the tests: the part that shows, the form of the sequence, and the state
// machine with its selection.
function boardState() {
  var mc = machine();
  return {a: BOARD.a, form: SEQ.form, machine: mc ? mc.id : null, tr: ST.tr, st: ST.st, band: ST_BAND.h};
}
"""
