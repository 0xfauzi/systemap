"""The Sequences view of the canvas page: its toolbar, the route and the step camera.

The design is the section "Views" of docs/design/nested-canvas.md. The view part
(`page_canvas_view`) has the seam: this part puts its functions in `VIEWS.sequences`. It
registers only when a map of the tree has sequences (`sq` in the canvas data, from
`canvas_sequences`). Else the header hides the view button.

The toolbar. It is a bar under the header, and it shows only in the Sequences view. It
has the words of the linked page (`page_sequences.toolbar`): the sequence chooser, Whole
route and Steps, Start at step 1, Previous, Next and End sequence. The chooser opens a
listbox. The sequences of the current map come first, then the sequences of the other maps
in tree order, in one group for each map. In the listbox, the arrow keys, Home, End and a
letter move the keyboard focus, Enter or Space selects, Escape closes the list, and Tab
closes it and goes on. The arrow keys move between the controls of the toolbar. The keys
of the toolbar do not move the camera (`ownKeys`). The page gives no new key for the
steps: the arrow keys move the camera on the canvas. The bar is part of the top band of
the screen (`band`), so the fit and the path stay below it.

The route. A choice moves the camera to the fit of the map of the sequence. In that map,
the flows of the route have their layer colors and their arrowheads, and each step has its
number at the label of its flow. The other flows and cards of that map have a low alpha,
SEQ_FLOW_DIM and QUIET. The first card of the route has the tag START. In the Steps
mode, the flow of the step is wider, the acting components have the tag ACTS and the
measurement components have the tag MEASURES. The flows of the later steps have the alpha
0.4. The other maps do not change. A step whose component is an actor for a card of a
parent map stays in the nested map: the page does not connect it to the portal.

The camera of a step. In the Steps mode, Previous and Next move the camera to the two
cards of the flow of the step, or to its acting components when the step names no one
flow (`f` is -1). The camera does not move when the cards are in the free box and their
names show. It moves at the same zoom when that is sufficient. The live region gives
"Step k of n:" and the sentence of the step.

Each change fades. The seam fades the values of the cards and the flows. The step numbers
and the wide line fade in this part, with the step of the view (VIEW_STEP): 0.2 or less in
one frame, and 1 in 160 ms or more. They show when the cards of the map show names. That
part follows the zoom, also with the step of the view (`seqZoom`). Thus the flight of a step
does not make a mark appear at one time. With reduced motion, each change and each camera
move occur at one time. A frame draws the route only for the map of the sequence, when that
map is on the screen. The work of a frame for this part is one table read for each drawn
card and flow, and the steps of the route.

The keyboard focus. When the focused button of the toolbar becomes hidden or disabled (Start
at step 1, End sequence, or Next at the last step), the focus goes to the button of the next
action (`seqFocus`). It does not go to the body of the page. When the toolbar has the focus
at a change of the view, the focus goes to the button of the new view (`box` and `setView`).

The camera target has the full band of the toolbar, also during the fade in (`headAim`).
The band is measured again at each change of the bar, because the Steps bar can have more
rows than the Whole route bar. The zoom of a step stays in KMIN to KMAX, also on a very low
screen.
"""

from __future__ import annotations

from systemap.page_icons import icon

HTML = (
    '<div class="cseq cview" id="cseq" role="toolbar" aria-label="Sequence" hidden>'
    '<span class="cseq__label" id="cseq-label">Sequence</span>'
    '<div class="cseq__choose"><button type="button" class="cseq__pick" id="cseq-pick" '
    'aria-haspopup="listbox" aria-expanded="false" aria-controls="cseq-list" '
    'aria-labelledby="cseq-label cseq-pick"><span class="cseq__name">No sequence</span>'
    f'{icon("down")}</button><div class="cseq__list" id="cseq-list" role="listbox" '
    'aria-labelledby="cseq-label" hidden></div></div>'
    '<div class="cseq__seg" role="group" aria-label="Show">'
    '<button type="button" id="cseq-whole" aria-pressed="true">Whole route</button>'
    '<button type="button" id="cseq-steps" aria-pressed="false">Steps</button></div>'
    '<span class="cseq__tb" id="cseq-wholebar">'
    '<button type="button" class="cseq__btn cseq__btn--primary" id="cseq-start">'
    "Start at step 1</button></span>"
    '<span class="cseq__tb" id="cseq-stepbar" hidden>'
    '<button type="button" class="cseq__btn" id="cseq-prev">Previous</button>'
    '<span class="cseq__count" id="cseq-count"></span>'
    '<button type="button" class="cseq__btn cseq__btn--primary" id="cseq-next">Next</button>'
    '<button type="button" class="cseq__btn" id="cseq-end">End sequence</button>'
    "</span></div>"
)

# The bar is in the header element, but it is fixed under it: 48 px, and 56 px on a touch
# screen (`canvas_header`). Outside the Sequences view, the bar is hidden. It fades in and
# out in 160 ms (`cview` in `canvas_header`).
CSS = """
.cbar .cseq{position:fixed;left:0;right:0;top:48px;z-index:4;box-sizing:border-box;
display:flex;flex-wrap:wrap;align-items:center;gap:6px 8px;padding:8px 16px;
border-bottom:1px solid var(--line);background:var(--surface)}
.cbar .cseq[hidden]{display:none}
.cseq__label{color:var(--ink-3)}
.cseq__choose{position:relative;flex:0 1 320px;min-width:140px}
.cbar .cseq__pick{width:100%;display:flex;align-items:center;gap:8px;padding:0 8px 0 12px;
border-color:var(--line-2);background:var(--map);color:var(--ink);font-weight:500;
text-align:left}
.cseq__name{flex:1;min-width:0;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
.cseq__seg{display:flex;flex:none;gap:2px}
.cbar .cseq__seg button{padding:0 12px}
.cseq__tb{display:flex;flex:none;align-items:center;gap:8px}
.cseq__tb[hidden]{display:none}
.cbar .cseq__btn{padding:0 12px;border-color:var(--line-2);white-space:nowrap}
.cbar .cseq__btn--primary{border-color:var(--ink);background:var(--ink);color:var(--map);
font-weight:600}
.cbar .cseq__btn--primary:hover{background:var(--ink);color:var(--map)}
.cbar .cseq__btn:disabled{cursor:default;opacity:.5}
.cseq__count{font:12px var(--fm);color:var(--ink-2);white-space:nowrap}
.cseq__list{position:fixed;z-index:6;box-sizing:border-box;display:flex;flex-direction:column;
gap:2px;padding:6px;overflow:auto;border:1px solid var(--line-2);border-radius:10px;
background:var(--surface);box-shadow:0 14px 40px color-mix(in srgb,#000 40%,transparent)}
.cseq__list[hidden]{display:none}
.cseq__group{padding:8px 8px 4px;font:600 11px/16px var(--fm);letter-spacing:.06em;
color:var(--ink-2)}
.cseq__opt{display:flex;flex-direction:column;justify-content:center;gap:2px;min-height:44px;
box-sizing:border-box;padding:4px 10px;border:1px solid transparent;border-radius:8px;
color:var(--ink-2);cursor:pointer}
.cseq__opt:hover{background:var(--raised);color:var(--ink)}
.cseq__opt[aria-selected="true"]{border-color:var(--accent);background:var(--card);
color:var(--ink)}
.cseq__opt:focus-visible{outline:2px solid var(--ink);outline-offset:-2px}
.cseq__opt-name{font:13px/18px var(--fs)}
.cseq__opt[aria-selected="true"] .cseq__opt-name{font-weight:600}
.cseq__opt-meta{font:12px/16px var(--fm);color:var(--ink-2)}
.cseq__opt-name,.cseq__opt-meta{overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
@media (pointer:coarse){.cbar .cseq{top:56px;padding:6px 8px}}
@media (max-width:820px){.cseq__label{display:none}.cseq__choose{flex:1 1 180px}}
"""

SEQ_PART = r"""
// ---- the Sequences view ------------------------------------------------------------
var SEQ_MAPS = ORDER.filter(function (m) { return m.sq && m.sq.length; });
var SEQ = {m: null, j: null, k: -1, steps: false, s: 0}, SEQ_CARDS = Object.create(null), SEQ_FLOWS = Object.create(null);
var SEQ_FLOW_DIM = 0.16, SEQ_LATER = 0.4;
var SEQ_FLOW_OFF = {a: SEQ_FLOW_DIM, color: null}, SEQ_FLOW_LATER = {a: SEQ_LATER, color: null};
// The marks of the route that this part draws: the step numbers and the wide line of the
// step. Each has its map, its flow, its alpha `a` and its target `to`.
var SEQ_MARKS = [], SEQ_AT = -1, SEQ_BAR = document.getElementById('cseq'), SEQ_BAND = {h: 0}, SEQ_LOG = null;
// The part of the route marks that the zoom shows (`seqZoom`), for each map.
var SEQ_ZOOM = new Map();
function seqEl(id) { return document.getElementById('cseq-' + id); }
var SEQ_PICK = seqEl('pick'), SEQ_LIST = seqEl('list'), SEQ_NAME = SEQ_PICK ? SEQ_PICK.querySelector('.cseq__name') : null;
function seqStart(j) {
  var first = j.s[0], f = first && first.f >= 0 ? SEQ.m.flows[first.f] : null;
  return first ? ((first.a || [])[0] || (f ? f.s : '')) : '';
}
// The kind of the line of step k: the whole route, a step before the current step, the
// current step, or a later step.
function seqKind(k) { return !SEQ.steps ? 'route' : k < SEQ.s ? 'was' : k > SEQ.s ? 'later' : 'now'; }
var SEQ_RANK = {now: 3, route: 3, was: 2, later: 1};
// The values of the cards and the flows of the route, and the marks of the route, after a
// change. A part gives a new object for each change (`page_canvas_view`).
function seqValues() {
  var cards = Object.create(null), flows = Object.create(null), j = SEQ.j, m = SEQ.m, want = [];
  if (j) {
    var kinds = Object.create(null), cur = SEQ.steps ? j.s[SEQ.s] : null, tags = Object.create(null);
    j.s.forEach(function (st, k) {
      var f = st.f >= 0 ? m.flows[st.f] : null;
      (st.a || []).concat(st.me || []).forEach(function (id) { cards[id] = null; });
      if (!f) return;
      cards[f.s] = null; cards[f.t] = null;
      var kind = seqKind(k);
      if (!kinds[st.f] || SEQ_RANK[kind] > SEQ_RANK[kinds[st.f]]) kinds[st.f] = kind;
    });
    Object.keys(kinds).forEach(function (i) { flows[i] = kinds[i] === 'later' ? SEQ_FLOW_LATER : null; });
    if (cur) {
      (cur.me || []).forEach(function (id) { tags[id] = {s: 'MEASURES', c: '--ink-2'}; });
      (cur.a || []).forEach(function (id) { tags[id] = {s: 'ACTS', c: '--accent'}; });
    }
    var start = seqStart(j);
    if (start && !tags[start]) tags[start] = {s: 'START', c: '--ink-2'};
    Object.keys(tags).forEach(function (id) { cards[id] = {a: 1, ring: null, tag: tags[id], back: null}; });
    // One number for each step. The steps on one flow stand side by side.
    var on = Object.create(null);
    j.s.forEach(function (st, k) {
      if (st.f < 0 || !m.flows[st.f]) return;
      var at = on[st.f] = (on[st.f] || 0) + 1;
      want.push({key: m.oi + ':n:' + k + ':' + seqKind(k), m: m, f: m.flows[st.f], n: k + 1, x: at - 1, kind: seqKind(k)});
    });
    if (cur && cur.f >= 0 && m.flows[cur.f]) want.push({key: m.oi + ':w:' + cur.f, m: m, f: m.flows[cur.f], kind: 'wide'});
  }
  SEQ_CARDS = cards; SEQ_FLOWS = flows;
  var keep = Object.create(null), now = reduced();
  want.forEach(function (e) { keep[e.key] = e; });
  SEQ_MARKS.forEach(function (e) { if (!keep[e.key]) e.to = 0; else { keep[e.key].a = e.a; e.gone = true; } });
  SEQ_MARKS = SEQ_MARKS.filter(function (e) { return !e.gone; });
  want.forEach(function (e) { if (e.a === undefined) e.a = now ? 1 : 0; e.to = 1; SEQ_MARKS.push(e); });
  if (now) SEQ_MARKS = SEQ_MARKS.filter(function (e) { return e.to > 0; });
}
// A change of the sequence, of the mode or of the step: new values, new images of a large
// map (the epoch of the view), and a frame.
function seqChanged() { seqValues(); VIEW.epoch++; seqSync(); viewTouch(); }
// The fade of the marks of the route, one time in each frame.
function seqAdvance() {
  if (SEQ_AT === drawn) return;
  SEQ_AT = drawn;
  SEQ_MARKS = SEQ_MARKS.filter(function (e) {
    e.a = approach(e.a, e.to, VIEW_STEP);
    if (e.a !== e.to) VIEW_FADING = true;
    return e.a > 0 || e.to > 0;
  });
}
// The marks show when the cards of the map show names (`cardShow`). That part follows the
// zoom, but it changes by VIEW_STEP or less in one frame. Thus a fast camera move, for
// example the flight to a step, does not make a mark appear at one time. A map that the
// frame before did not draw starts at the value of its zoom.
function seqZoom(m, a) {
  var to = cardShow(m.maxH * a), z = SEQ_ZOOM.get(m);
  if (!z || z.at < drawn - 1) z = {v: to, at: drawn};
  else if (z.at !== drawn) z = {v: approach(z.v, to, VIEW_STEP), at: drawn};
  SEQ_ZOOM.set(m, z);
  if (z.v !== to) VIEW_FADING = true;
  return z.v;
}
function seqCircle(x, y, r, fill, line, al) {
  ctx.globalAlpha = al; ctx.setLineDash([]); ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fillStyle = fill; ctx.fill();
  if (line) { ctx.strokeStyle = line; ctx.lineWidth = 1; ctx.stroke(); }
}
var SEQ_PILL = {route: ['--accent', null, '--map'], now: ['--accent', null, '--map'], was: ['--map', '--ink-2', '--ink'], later: ['--map', '--line-2', '--ink-3']};
// Draw the marks of the route of map m. They show when the cards of the map show names.
function seqDraw(m, a, ox, oy, alpha) {
  // `alpha` has the fade of the view. A mark shows with the smaller of that fade and its own
  // fade, so that two fades at one time do not make a larger step.
  var vs = VIEW_SHOW.sequences, show = (vs > 0 ? alpha / vs : 0) * seqZoom(m, a), fs = labelSize(a), r = clamp(fs * 0.8, 7, 10), labels = hasLabels(fs, labelAlpha(a, 1));
  var log = SEQ_LOG ? {at: performance.now(), map: m.id, marks: []} : null;
  if (show > 0.02) {
    SEQ_MARKS.forEach(function (e) {
      if (e.m !== m || e.kind !== 'wide') return;
      var al = show * Math.min(vs, e.a), f = e.f, n = f.p.length;
      if (al <= 0.02 || n < 2) return;
      ctx.globalAlpha = al; ctx.strokeStyle = flowColor(f, null); ctx.lineWidth = clamp(2.6 * a, 1.6, 3.2); ctx.setLineDash([]);
      ctx.beginPath(); cutLine(ctx, f.p, ox, oy, a); ctx.stroke();
      // The label of the flow stays over the wide line, as it is over the usual line.
      drawLabels([f], a, ox, oy, al);
      if (log) log.marks.push({kind: 'wide', f: f.i, a: al});
    });
    SEQ_MARKS.forEach(function (e) {
      if (e.m !== m || e.kind === 'wide' || !e.f.lb) return;
      var al = show * Math.min(vs, e.a), lb = e.f.lb, pw = labels ? unitWidth(e.f.a, 500) * fs + 6 : 0;
      var y = oy + a * (lb[1] + lb[3] / 2), x = ox + a * (lb[0] + lb[2] / 2) - pw / 2 - r - 2 - e.x * (2 * r + 3), k = SEQ_PILL[e.kind];
      if (log) log.marks.push({kind: e.kind, f: e.f.i, n: e.n, a: al, x: x, y: y, r: r});
      if (al <= 0.02 || x + r < 0 || y + r < 0 || x - r > W || y - r > H) return;
      seqCircle(x, y, r, C[k[0]], k[1] ? C[k[1]] : null, al);
      text(String(e.n), x, y + r * 0.4, Math.max(MIN_TEXT, r * 1.1), C[k[2]], al, 700, true, 'center');
      obstacle(x - r, y - r, 2 * r, 2 * r, 1, al);
    });
  }
  if (log) SEQ_LOG.push(log);
}

// ---- the camera of a sequence and of a step -------------------------------------------
function seqUnion(list) {
  return list.reduce(function (b, c) { var w = worldBox(c); return b ? union(b, w) : w; }, null);
}
// The cards that the camera shows for step k: the two cards of its flow, or its acting
// components, or its measurement components.
function stepCards(k) {
  var st = SEQ.j.s[k], m = SEQ.m, f = st.f >= 0 ? m.flows[st.f] : null;
  function of(ids) { return (ids || []).map(function (id) { return m.byId[id]; }).filter(Boolean); }
  var list = f ? of([f.s, f.t]) : of(st.a);
  return list.length ? list : of(st.me);
}
// Move the camera to the cards of the current step. The camera does not move when the
// cards are in the free box and their names show, and it keeps its zoom when the cards fit
// at that zoom with their names.
function stepCamera() {
  var list = stepCards(SEQ.s), box = seqUnion(list);
  if (!box) { flyGoal(goalOf(SEQ.m, null, null)); return; }
  var g = gutters(), x0 = g.x + 8, y0 = g.top + 8, x1 = W - g.x - 8, y1 = H - g.bottom - 8, k = cam.k;
  var high = Math.max.apply(null, list.map(function (c) { return worldBox(c)[3]; }));
  var low = Math.min.apply(null, list.map(function (c) { return worldBox(c)[3]; }));
  var sx = (box[0] - cam.x) * k, sy = (box[1] - cam.y) * k, named = low * k >= NAME_H + 4;
  if (named && sx >= x0 && sy >= y0 && sx + box[2] * k <= x1 && sy + box[3] * k <= y1) return;
  if (!(named && box[2] * k <= x1 - x0 && box[3] * k <= y1 - y0)) {
    // A free box of 0 px or less (a very low screen) does not give a zoom of 0 or less.
    k = Math.min(fitBox(box, 0.2).k, Math.max(120 / high, (NAME_H + 8) / low));
    k = clamp(Math.min(k, Math.max(1, x1 - x0) / box[2], Math.max(1, y1 - y0) / box[3]), KMIN, KMAX);
  }
  fly({x: box[0] + box[2] / 2 - (x0 + x1) / 2 / k, y: box[1] + box[3] / 2 - (y0 + y1) / 2 / k, k: k});
}

// ---- the choice, the modes and the steps ----------------------------------------------
function seqWords() {
  var j = SEQ.j, n = j.s.length, st = j.s[SEQ.s];
  if (SEQ.steps) return 'Step ' + (SEQ.s + 1) + ' of ' + n + ': ' + (st.y || 'This step has no sentence.');
  return 'Sequence: ' + j.n + '. Whole route, ' + counted(n, 'step') + '.' + (j.en ? ' Entry point: ' + j.en + '.' : '') +
    (j.dr ? ' Agent draft. Source review necessary.' : '') + ' Map: ' + mapName(SEQ.m) + '.';
}
// Move the camera: to the fit of the map for the whole route, and to the cards of the step
// in the Steps mode. The target has the full top band of the view (`headAim`). The words of
// the sequence or of the step are the words of the live region. Thus the live region does
// not give the map again when the camera stops in it (`tell`).
function seqCamera() {
  headAim(function () { if (SEQ.steps) stepCamera(); else flyGoal(goalOf(SEQ.m, null, null)); });
  SAID_MAP = SEQ.m;
}
// Show sequence k of map m. `camera` is true to move the camera: to the fit of the map for
// the whole route, and to the cards of the first step in the Steps mode.
function seqChoose(m, k, camera) {
  SEQ.m = m; SEQ.j = m.sq[k]; SEQ.k = k; SEQ.s = 0;
  if (!SEQ.j.s.length) SEQ.steps = false;
  seqChanged();
  if (camera) seqCamera();
  say((SEQ.steps ? 'Sequence: ' + SEQ.j.n + '. Map: ' + mapName(m) + '. ' : '') + seqWords());
}
function seqMode(steps, s, camera) {
  if (!SEQ.j) return;
  SEQ.steps = steps && SEQ.j.s.length > 0; SEQ.s = clamp(s, 0, Math.max(0, SEQ.j.s.length - 1));
  seqChanged();
  if (camera) seqCamera();
  say(seqWords());
}
function seqStep(d) { if (SEQ.j && SEQ.steps) { var s = SEQ.s + d; if (s >= 0 && s < SEQ.j.s.length) seqMode(true, s, true); } }
// When the focused control of the toolbar becomes hidden or disabled, the keyboard focus
// goes to the control that does the next action: Next after Start at step 1, Start at step 1
// after End sequence, Previous after the last step, and Next after the first step.
var SEQ_NEXT_FOCUS = {start: 'next', end: 'start', next: 'prev', prev: 'next'};
function seqFocus(was) {
  if (!was || !SEQ_BAR.contains(was) || (!was.disabled && was.offsetParent)) return;
  var to = seqEl(SEQ_NEXT_FOCUS[(was.id || '').replace('cseq-', '')] || 'steps');
  if (to && (to.disabled || !to.offsetParent)) to = seqEl('end');
  if (to && !to.disabled && to.offsetParent) to.focus();
}
function seqSync() {
  var j = SEQ.j, n = j ? j.s.length : 0, steps = !!j && SEQ.steps, was = document.activeElement;
  if (SEQ_NAME) SEQ_NAME.textContent = j ? j.n : 'No sequence';
  seqEl('whole').setAttribute('aria-pressed', steps ? 'false' : 'true');
  seqEl('steps').setAttribute('aria-pressed', steps ? 'true' : 'false');
  seqEl('wholebar').hidden = steps; seqEl('stepbar').hidden = !steps;
  seqEl('whole').disabled = !j; seqEl('steps').disabled = !n; seqEl('start').disabled = !n;
  seqEl('count').textContent = steps ? 'Step ' + (SEQ.s + 1) + ' of ' + n : '';
  seqEl('prev').disabled = !steps || SEQ.s <= 0; seqEl('next').disabled = !steps || SEQ.s >= n - 1;
  // The Steps bar and the Whole route bar can have a different number of rows. Thus the
  // height of the band is measured again.
  barBand(SEQ_BAR, SEQ_BAND, true);
  seqFocus(was);
}

// ---- the chooser: a button that opens the listbox of the sequences ---------------------
function seqOptions() { return Array.prototype.slice.call(SEQ_LIST.querySelectorAll('[role="option"]')); }
function seqExpand(on) { SEQ_LIST.hidden = !on; SEQ_PICK.setAttribute('aria-expanded', on ? 'true' : 'false'); }
function seqShut(back) { if (SEQ_LIST.hidden) return; seqExpand(false); if (back) SEQ_PICK.focus(); }
function seqShow(o) { if (o) { o.focus(); o.scrollIntoView({block: 'nearest'}); } }
// The sequences of the current map first, then the other maps in tree order.
function seqGroups() {
  var m = currentMap();
  return SEQ_MAPS.indexOf(m) < 0 ? SEQ_MAPS : [m].concat(SEQ_MAPS.filter(function (x) { return x !== m; }));
}
function seqOpen() {
  var r = SEQ_PICK.getBoundingClientRect(), s = SEQ_LIST.style, out = [];
  seqGroups().forEach(function (m) {
    out.push('<div role="group" aria-label="Map: ' + esc(mapName(m)) + '"><div class="cseq__group" aria-hidden="true">' + esc(mapName(m)) + '<\/div>');
    m.sq.forEach(function (j, k) {
      var on = SEQ.m === m && SEQ.k === k, meta = (j.en ? j.en + ' · ' : '') + counted(j.s.length, 'step') + (j.dr ? ' · Agent draft' : '');
      out.push('<div role="option" class="cseq__opt" tabindex="-1" data-m="' + m.oi + '" data-k="' + k + '" aria-selected="' + on + '">' +
        '<span class="cseq__opt-name">' + esc(j.n) + '<\/span><span class="cseq__opt-meta">' + esc(meta) + '<\/span><\/div>');
    });
    out.push('<\/div>');
  });
  SEQ_LIST.innerHTML = out.join('');
  s.width = Math.min(Math.max(r.width, 360), window.innerWidth - 16) + 'px';
  s.left = Math.max(8, Math.min(r.left, window.innerWidth - 8 - parseFloat(s.width))) + 'px';
  s.top = r.bottom + 6 + 'px'; s.maxHeight = Math.max(120, window.innerHeight - r.bottom - 22) + 'px';
  seqExpand(true);
  var opts = seqOptions();
  seqShow(opts.filter(function (o) { return o.getAttribute('aria-selected') === 'true'; })[0] || opts[0]);
}
function seqPick(o) {
  seqShut(true);
  var m = ORDER[+o.getAttribute('data-m')], k = +o.getAttribute('data-k');
  if (m !== SEQ.m || k !== SEQ.k) seqChoose(m, k, true);
}
// The keys of the listbox. They do not go to the canvas or the page.
function seqListKey(e) {
  var opts = seqOptions(), i = opts.indexOf(document.activeElement), key = e.key;
  var to = {ArrowDown: Math.min(i + 1, opts.length - 1), ArrowUp: Math.max(i - 1, 0), Home: 0, End: opts.length - 1}[key];
  e.stopPropagation();
  if (key === 'Tab') { seqShut(false); return; }
  if (key === 'Escape') { e.preventDefault(); seqShut(true); return; }
  if ((key === 'Enter' || key === ' ') && i >= 0) { e.preventDefault(); seqPick(opts[i]); return; }
  if (to === undefined && key.length === 1) {
    // A letter: the next sequence whose name starts with it.
    for (var n = 1; n <= opts.length && to === undefined; n++) {
      var x = (i + n) % opts.length;
      if (opts[x].textContent.charAt(0).toLowerCase() === key.toLowerCase()) to = x;
    }
  }
  if (to === undefined) return;
  e.preventDefault(); seqShow(opts[to]);
}
// The arrow keys move between the controls of the toolbar.
function seqBarKey(e) {
  if ((e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') || SEQ_LIST.contains(e.target)) return;
  var list = Array.prototype.slice.call(SEQ_BAR.querySelectorAll('button')).filter(function (b) { return !b.disabled && b.offsetParent; });
  var i = list.indexOf(e.target);
  if (i < 0) return;
  e.preventDefault();
  list[(i + (e.key === 'ArrowRight' ? 1 : list.length - 1)) % list.length].focus();
}

// ---- the registration -----------------------------------------------------------------
function seqWire() {
  SEQ_PICK.addEventListener('click', function () { if (SEQ_LIST.hidden) seqOpen(); else seqShut(false); });
  SEQ_PICK.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); e.stopPropagation(); seqOpen(); }
  });
  SEQ_LIST.addEventListener('click', function (e) { var o = e.target.closest('[role="option"]'); if (o) seqPick(o); });
  SEQ_LIST.addEventListener('keydown', seqListKey);
  SEQ_LIST.addEventListener('focusout', function (e) { if (e.relatedTarget && !SEQ_LIST.parentNode.contains(e.relatedTarget)) seqShut(false); });
  document.addEventListener('pointerdown', function (e) { if (!SEQ_LIST.parentNode.contains(e.target)) seqShut(false); });
  window.addEventListener('resize', function () { seqShut(false); });
  SEQ_BAR.addEventListener('keydown', seqBarKey);
  function on(id, f) { seqEl(id).addEventListener('click', f); }
  on('whole', function () { seqMode(false, SEQ.s, true); });
  on('steps', function () { seqMode(true, SEQ.s, true); });
  on('start', function () { seqMode(true, 0, true); });
  on('prev', function () { seqStep(-1); });
  on('next', function () { seqStep(1); });
  on('end', function () { seqMode(false, SEQ.s, true); });
}
if (SEQ_MAPS.length && SEQ_BAR && SEQ_PICK && SEQ_LIST) {
  seqWire();
  VIEWS.sequences = {
    card: function (c) {
      if (c.map !== SEQ.m) return null;
      var v = SEQ_CARDS[c.id];
      return v === undefined ? MAP_QUIET : v;
    },
    flow: function (f) {
      if (f.map !== SEQ.m) return null;
      var v = SEQ_FLOWS[f.i];
      return v === undefined ? SEQ_FLOW_OFF : v;
    },
    over: function (m, a, ox, oy, alpha) { seqAdvance(); if (m === SEQ.m || SEQ_MARKS.length) seqDraw(m, a, ox, oy, alpha); },
    // A view change does not move the camera. When the current map has sequences and
    // the sequence on show is of a different map, the first sequence of the current map
    // shows.
    enter: function () {
      var m = currentMap();
      if (!SEQ.j || (SEQ.m !== m && m.sq && m.sq.length)) seqChoose(SEQ_MAPS.indexOf(m) >= 0 ? m : SEQ_MAPS[0], 0, false);
      // The bar comes into the page, and its height is measured before the fade starts.
      barShow(SEQ_BAR, true); barBand(SEQ_BAR, SEQ_BAND, true);
    },
    // The words of the view for the live region: the words of the sequence (`viewWords`).
    words: function () { return SEQ.j ? seqWords() : ''; },
    leave: function () { seqShut(false); barShow(SEQ_BAR, false, 'sequences'); },
    // The height of the bar. A hidden bar keeps the last height.
    band: function (fresh) { return barBand(SEQ_BAR, SEQ_BAND, fresh); },
    box: function () { return SEQ_BAR; }
  };
  seqSync();
}
// The state of the Sequences view for the tests: the sequence, the mode, the step, the
// flows and the cards of the route, and the marks of the last frames (`seqLog`).
function seqState() {
  var j = SEQ.j;
  return {map: SEQ.m ? SEQ.m.id : null, id: j ? j.id : null, steps: SEQ.steps, s: SEQ.s, n: j ? j.s.length : 0,
    flows: Object.keys(SEQ_FLOWS).map(Number).sort(function (x, y) { return x - y; }),
    cards: Object.keys(SEQ_CARDS).sort(), band: SEQ_BAND.h, marks: SEQ_MARKS.length};
}
"""
