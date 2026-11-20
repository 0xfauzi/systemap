"""The Sequences view of the atlas page: the list, the route on the map, the bar and the keys.

`atlas_script` joins the script of this part after the details part (`atlas_details`). The
rules are the section "The other views: the rules" of docs/design/atlas.md, and the study
(docs/design/atlas/study-script.html, `pickSeq`, `stepTo` and `stepper`):

- The view shows only when a map of the tree has sequences (`sq` in the page data, from
  `canvas_sequences`). Then the header has the button Sequences (`atlas_header`).
- The list at the left gives the sequences, each with its count of steps. When more than
  one map has sequences, the list has one group for each map, in tree order. On a narrow
  screen the list is a row of names under the headline. After the list, the entry points
  of the map with no sequence (`ne` in `atlas_data`). The list scrolls, and a shadow at
  its top or bottom shows that more names are there. The entry points are not in the
  scroll: they stay on the screen under the list.
- The headline gives the count of steps and the entry point of the sequence, also on a
  phone. The list is under the headline at its height (`--ask-b`).
- A sequence is a layer of its map with only the flows of its steps (`layerFlags` in
  `atlas_view`, with the ID "q:" and the index of the sequence). The label of each line
  has the numbers of its steps before the artifact (`seqLabel`). A label is on its line or
  beside it and touching it. A label with no such place at rest shows only at its step and
  after it, as in the design study (`seatsOf` in `atlas_lines`). The cards that no step uses are quiet. The
  other maps keep the layer of the Map view. A choice moves the camera to the fit of the
  map of the sequence, with the list at the left and the bar at the bottom free.
- The bar at the bottom has the two forms (On the map, As a diagram), the step count, a dot
  for each step, the sentence of the step and the step controls. At the start no step
  shows: the bar gives "Whole route". Next goes to the next step, and Done after the last
  step goes back to the whole route.
- The step state. The current step is the light of the map (`lightSource` in `atlas_lit`):
  its flow gets the color of its kind and draws one time, and its cards and its acting
  cards get the outline of the ink. Earlier steps are dark (`--ink-2`). Later steps are
  faint (LATER_A). The other cards and lines do not go back. A pointer on a card or a line
  gives the usual light, and the step state shows again when the pointer goes.
- The tags of the cards, as on the canvas page: ACTS on an acting card of the current step,
  MEASURES on its measurement card, and START on the first card of the sequence (`seqTag`).
  The live region also gives the acting and the measurement cards of the step.
- A step with no flow (`f` is -1) has no line. The bar gives "This step has no flow" and its
  acting cards, and these cards get the outline of the ink.
- When the cards of the step are not fully on the free part of the screen, the camera moves
  to them at the same zoom, or at a smaller zoom when they do not fit (`stepCamera`). On a
  phone the zoom stays at 0.5 or more. When the two cards do not fit at that zoom, the
  target card of the step is fully in view. When
  the new sentence makes the bar taller and the bar then covers the frame of the map that
  was fully above it, the camera goes to the fit again (`frameBottom`).
- The bar. On a wide screen the bar is in the width at the right of the list, so that it
  does not cover the list or the entry points. With the details open, it is between the
  list and the details, and the sentence has its own row. On a middle screen with the
  details open, it is in the width at the left of the details, and the list is above it.
  Its inner width is the width of the study (780 px). On a phone the dots stay on the row
  of the step count for each count of steps: they get smaller when the row has no space for
  them at their full size.
- The left and right arrow keys change the step, also while a button has the keyboard
  focus. In this view they do not pan the map. The live region gives the sequence at
  a choice and the step at a change.
- The diagram form (`BOARD`) has the same step state.

The diagram form. The rule is the section "The other views: the rules" of docs/design/atlas.md, and the study
(docs/design/atlas/study-script.html, `drawSeq`): one column for each card and one row for
each step, with the step state of the map form. The current step has the color of the kind
of its flow, earlier steps are dark, and later steps are faint. Each row is a button: a
click, Enter or Space goes to that step. A step with no flow has its number in the column
of its first acting card and the words "No flow". Each label of a row has a plate in the
color of the ground below it, at full opacity (`boardPlate`). Thus a lifeline does not go
through the label of a faint later step.

The diagram has a scale of BOARD_MIN or more, so that its text can be read. Above BOARD_MIN,
the full diagram with its margins is in its part of the screen, and that part does not
scroll. When the diagram is larger than its part of the screen at BOARD_MIN (a phone), that
part scrolls, and a change of the step scrolls the row of the current step into view
(`boardShow`).

The diagram is SVG, not canvas: it does not zoom (docs/design/atlas.md, "The architecture").
The script makes it with DOM functions. It sets the color of a kind with the style object
(`--k`), not with a style attribute. It draws the diagram again at a change of the
sequence, of the step and of the screen size. While the diagram shows, the canvas draws
only the ground (`draw` in `atlas_input`).
"""

from __future__ import annotations

HTML = (
    '<nav class="rail" id="atlas-rail" aria-label="Sequences"><div class="rail__list" '
    'id="atlas-rail-list"></div><div class="rail__ne" id="atlas-rail-ne"></div></nav>'
    '<div class="stepper" id="atlas-step" role="group" aria-label="Steps of the sequence">'
    '<div class="forms" role="group" aria-label="Form">'
    '<button type="button" data-form="map" aria-pressed="true">On the map</button>'
    '<button type="button" data-form="diagram" aria-pressed="false">As a diagram</button></div>'
    '<span class="n" id="atlas-step-n">Whole route</span>'
    '<div class="dots2" id="atlas-step-dots" aria-hidden="true"></div>'
    '<p id="atlas-step-p"></p>'
    '<div class="nav"><button type="button" id="atlas-step-prev" aria-label="Previous step" '
    'title="Previous step (Left arrow)" disabled>←</button>'
    '<button type="button" class="go" id="atlas-step-next">Start</button></div></div>'
)

# From the study, with the fixed header of the atlas page (48 px over the stage) and the
# fonts of the product.
CSS = """
.rail{position:fixed;left:max(24px,env(safe-area-inset-left,0px));top:280px;bottom:74px;width:292px;overflow:hidden;display:none;
flex-direction:column;gap:1px;z-index:2}
body[data-mode="seq"] .rail{display:flex}
.rail__list{display:flex;flex-direction:column;gap:1px;flex:0 1 auto;min-height:0;overflow:auto;scrollbar-width:thin;overscroll-behavior:contain;
background:linear-gradient(var(--map) 30%,transparent) top/100% 28px no-repeat local,linear-gradient(transparent,var(--map) 70%) bottom/100% 28px no-repeat local,
linear-gradient(var(--line-2),transparent) top/100% 10px no-repeat scroll,linear-gradient(transparent,var(--line-2)) bottom/100% 10px no-repeat scroll}
.rail button{display:flex;justify-content:space-between;gap:12px;align-items:baseline;text-align:left;padding:7px 10px;margin-left:-10px;
border-radius:8px;color:var(--ink-2);transition:background .12s,color .12s;flex:none}
.rail button:hover{background:var(--tint);color:var(--ink)}
.rail button[aria-current="true"]{color:var(--ink);font-weight:600;background:var(--tint)}
.rail button i{font:500 10.5px/1 var(--fm);font-style:normal;color:var(--ink-3);font-variant-numeric:tabular-nums;flex:none}
.rail__g{margin:14px 0 4px;font:500 10.5px/1 var(--fm);letter-spacing:.09em;text-transform:uppercase;color:var(--ink-3)}
.rail__g:first-child{margin-top:0}
.rail__ne{margin-top:14px;padding-top:10px;border-top:1px solid var(--line);flex:none;max-height:40%;overflow:auto;scrollbar-width:thin;
color:var(--ink-3);font-size:12px;line-height:1.45}
.rail__ne:empty{display:none}
.rail__ne h2{margin:0 0 6px;display:flex;justify-content:space-between;gap:12px;font:500 10.5px/1.3 var(--fm);letter-spacing:.09em;
text-transform:uppercase;color:var(--ink-3)}
.rail__ne ul{margin:0;padding:0;list-style:none;display:grid;gap:3px}
.rail__ne code{font:400 11px/1.4 var(--fm);color:var(--ink-2);overflow-wrap:anywhere}
.rail__ne p{margin:0}
.stepper{position:fixed;left:50%;bottom:max(22px,env(safe-area-inset-bottom,0px));transform:translateX(-50%);width:min(808px,calc(100% - 32px));
box-sizing:border-box;display:none;align-items:center;gap:12px;padding:10px 12px 10px 14px;border-radius:14px;background:var(--surface);
border:1px solid var(--line);box-shadow:var(--shadow);z-index:2}
body[data-mode="seq"] .stepper{display:flex}
body[data-mode="seq"] .say{bottom:calc(var(--bar-h,62px) + max(34px,env(safe-area-inset-bottom,0px)))}
body[data-mode="seq"] .key,body[data-mode="seq"] .note,body[data-mode="seq"] .tabs{display:none}
.stepper .n{font:500 11px/1 var(--fm);color:var(--ink-3);white-space:nowrap;font-variant-numeric:tabular-nums;flex:none}
.stepper p{margin:0;flex:1;min-width:0;color:var(--ink);line-height:1.4}
.stepper p small{display:block;color:var(--ink-3);font-size:12px}
.stepper .nav{display:flex;gap:4px;flex:none}
.stepper button{height:32px;min-width:32px;padding:0 10px;border-radius:9px;border:1px solid var(--line-2);color:var(--ink-2);font-weight:500;
transition:background .12s,color .12s,transform .12s}
.stepper button:hover:not(:disabled){background:var(--tint);color:var(--ink)}
.stepper button:disabled{opacity:.4;cursor:default}
.stepper button.go{background:var(--ink);color:var(--surface);border-color:var(--ink)}
.stepper button.go:hover:not(:disabled){background:var(--ink);color:var(--surface);transform:translateY(-1px)}
.forms{display:flex;padding:2px;border:1px solid var(--line);border-radius:9px;background:var(--map);flex:none}
.stepper .forms button{height:26px;min-width:0;padding:0 9px;border:0;border-radius:7px;color:var(--ink-3);font-size:12px}
.stepper .forms button[aria-pressed="true"]{background:var(--surface);color:var(--ink);box-shadow:0 1px 2px rgba(29,27,23,.12)}
.dots2{display:flex;gap:4px;flex:none}
.dots2 i{width:6px;height:6px;border-radius:50%;background:var(--line-2);transition:background .16s,transform .16s}
.dots2 i.was{background:var(--ink-2)}
.dots2 i.now{background:var(--ink);transform:scale(1.35)}
body[data-mode="seq"][data-form="diagram"] #canvas{visibility:hidden}
body[data-mode="seq"][data-form="diagram"] .zoom{display:none}
@media (min-width:1181px){
body[data-mode="seq"] .stepper{left:calc(50% + 166px);width:min(808px,calc(100% - 364px))}
body.open[data-mode="seq"] .stepper{left:calc(50% - 24px);width:min(808px,calc(100% - 744px));flex-wrap:wrap}
body.open[data-mode="seq"] .stepper p{flex-basis:100%;order:3}
}
@media (min-width:721px) and (max-width:1180px){
body.open[data-mode="seq"] .stepper{left:calc((100% - 380px) / 2);width:min(808px,calc(100% - 412px))}
body[data-mode="seq"] .rail{top:calc(var(--ask-b,248px) + 24px);bottom:calc(var(--bar-h,62px) + 84px)}
body.open[data-mode="seq"] .stepper{flex-wrap:wrap}body.open[data-mode="seq"] .stepper p{flex-basis:100%;order:3}
body[data-mode="seq"] .zoom{bottom:calc(var(--bar-h,62px) + 36px)}
}
@media (max-width:720px){
.rail{top:calc(var(--ask-b,146px) + 14px);bottom:auto;left:16px;right:16px;width:auto;flex-direction:row;gap:6px;overflow-x:auto;overflow-y:hidden;
padding-bottom:4px;scrollbar-width:thin}
.rail__list{flex-direction:row;gap:6px;flex:none;overflow:visible;background:none}
body[data-mode="seq"] .ask__n{display:block;margin-top:4px}
.rail button{margin:0;border:1px solid var(--line);background:var(--surface);white-space:nowrap}
.rail button:hover,.rail button[aria-current="true"]{background:linear-gradient(var(--tint),var(--tint)),var(--surface)}
.rail__g{display:none}
.rail__ne{margin:0;flex:none;max-width:260px;max-height:none;padding:6px 10px;border:1px solid var(--line);border-radius:8px;background:var(--surface)}
.rail__ne ul{display:block}.rail__ne li{display:inline}.rail__ne li+li::before{content:", "}
.stepper{flex-wrap:wrap}.stepper p{flex-basis:100%;order:3}
.dots2{flex:1 1 0;min-width:0;align-items:center}.dots2 i{flex:0 1 6px;min-width:2px;height:auto;aspect-ratio:1}
body[data-mode="seq"] .zoom{display:none}
}
@media (pointer:coarse){.stepper .nav button{height:44px;min-width:44px}.rail button{min-height:44px;align-items:center}}
"""

SEQ = r"""
// ---- the Sequences view: the state -----------------------------------------------------
var SEQ_MAPS = ORDER.filter(function (m) { return m.sq && m.sq.length; });
var SEQ = {m: null, k: 0, step: -1, form: 'map', first: null, nums: null, tagKey: '', tags: null}, LATER_A = 0.4;
var RAIL = document.getElementById('atlas-rail'), RAIL_LIST = document.getElementById('atlas-rail-list'), RAIL_NE = document.getElementById('atlas-rail-ne');
var BAR = document.getElementById('atlas-step'), BAR_N = document.getElementById('atlas-step-n'), BAR_DOTS = document.getElementById('atlas-step-dots');
var BAR_P = document.getElementById('atlas-step-p'), BAR_PREV = document.getElementById('atlas-step-prev'), BAR_NEXT = document.getElementById('atlas-step-next');
// True when element e has a box on the page. A fixed element has no offsetParent.
function shownEl(e) { return !!e && e.getClientRects().length > 0; }
function seqJ() { return SEQ.m ? SEQ.m.sq[SEQ.k] : null; }
function seqShown() { return VIEW.mode === 'seq' && !!SEQ.m; }
// The flow of step k of the sequence on show, or null.
function stepFlow(k) { var j = seqJ(), st = j && j.s[k]; return st && st.f >= 0 ? SEQ.m.flows[st.f] || null : null; }
// The step numbers of each flow of sequence k of map m, from 1.
function seqNums(m, k) {
  var memo = m._sn || (m._sn = []);
  if (memo[k]) return memo[k];
  var out = Object.create(null);
  m.sq[k].s.forEach(function (st, n) { if (st.f >= 0 && m.flows[st.f]) (out[st.f] = out[st.f] || []).push(n + 1); });
  memo[k] = out;
  return out;
}
// The label of line e in the layer `id`: the step numbers before the artifact in a sequence.
function seqLabel(m, id, e) {
  if (id.slice(0, 2) !== 'q:') return;
  var n = seqNums(m, +id.slice(2))[e.f.i];
  if (n) e.s = n.join(', ') + ' ' + e.s;
}
// The headline of the view: the kind, the name of the sequence, and its counts.
function seqHead() {
  var j = seqJ(), n = counted(j.s.length, 'step');
  if (j.en) n += ' · starts at ' + j.en;
  if (j.dr) n += ' · agent draft, source review necessary';
  return {k: 'Sequence', q: j.n, n: n};
}
function seqWords() {
  var j = seqJ();
  return 'Sequence: ' + j.n + '. ' + counted(j.s.length, 'step') + '.' + (j.en ? ' Entry point: ' + j.en + '.' : '') +
    (j.dr ? ' Agent draft. Source review necessary.' : '') + ' Map: ' + mapName(SEQ.m) + '.';
}
// True when the lines of map m show the step state in this frame: the map shows the
// sequence, a step is current, and no pointer gives a different light.
function stepping(m) {
  if (!seqShown() || SEQ.m !== m || SEQ.step < 0 || SEQ.form !== 'map' || shownLayer(m) !== 'q:' + SEQ.k) return false;
  return !(LIGHT.key && !LIGHT.step && LIGHT.m === m);
}
// The step state of the line of flow i: 'now', 'was' (an earlier step) or 'later'. A flow
// with two steps has the state of its first step, except at its own steps.
function stepState(m, i) {
  if (!stepping(m)) return '';
  var j = seqJ(), first = SEQ.first[i];
  if (first === undefined) return '';
  if (j.s[SEQ.step].f === i) return 'now';
  return first < SEQ.step ? 'was' : 'later';
}
// The light of the current step: its flow and its cards (`lightSource` in `atlas_lit`).
function stepSource(m) {
  if (!seqShown() || SEQ.m !== m || SEQ.step < 0 || SEQ.form !== 'map') return null;
  var st = seqJ().s[SEQ.step], f = stepFlow(SEQ.step);
  return {m: m, c: null, f: f, step: 'q' + m.oi + ':' + SEQ.k + ':' + SEQ.step, cards: (st.a || []).concat(st.me || [])};
}

// The tag of card c in the Sequences view, as on the canvas page: 'acts' for an acting card
// of the current step, 'measures' for its measurement card, and 'start' for the first card
// of the sequence (the recorded start `st`, else the first acting card or the source of the
// first flow). Else ''.
function seqTag(c) {
  var m = c.map;
  if (!seqShown() || SEQ.m !== m || SEQ.form !== 'map' || shownLayer(m) !== 'q:' + SEQ.k) return '';
  var key = SEQ.k + ':' + SEQ.step;
  if (SEQ.tagKey !== key) { SEQ.tagKey = key; SEQ.tags = seqTags(m, seqJ(), SEQ.step); }
  return SEQ.tags[c.id] || '';
}
function seqTags(m, j, n) {
  var out = Object.create(null), cur = n >= 0 ? j.s[n] : null, start = seqStart(m, j);
  if (cur) {
    (cur.me || []).forEach(function (id) { out[id] = 'measures'; });
    (cur.a || []).forEach(function (id) { out[id] = 'acts'; });
  }
  if (start && !out[start]) out[start] = 'start';
  return out;
}
function seqStart(m, j) {
  if (j.st && m.byId[j.st]) return j.st;
  var first = j.s[0], f = first && first.f >= 0 ? m.flows[first.f] : null;
  return first ? ((first.a || [])[0] || (f ? f.s : '')) : '';
}

// ---- the list ---------------------------------------------------------------------------
function railWrite() {
  if (!RAIL_LIST) return;
  var out = [];
  SEQ_MAPS.forEach(function (m) {
    if (SEQ_MAPS.length > 1) out.push(el('p', {'class': 'rail__g'}, mapName(m)));
    m.sq.forEach(function (j, k) {
      var b = el('button', {type: 'button', 'data-m': m.oi, 'data-k': k, 'aria-current': 'false'}, el('span', null, j.n), el('i', {'aria-hidden': 'true'}, String(j.s.length)),
        el('span', {'class': 'sr-only'}, ', ' + counted(j.s.length, 'step')));
      b.addEventListener('click', function () { seqChoose(m, k, true); });
      out.push(b);
    });
  });
  RAIL_LIST.replaceChildren.apply(RAIL_LIST, out);
}
function railSync() {
  if (!RAIL_LIST) return;
  Array.prototype.forEach.call(RAIL_LIST.querySelectorAll('button'), function (b) {
    b.setAttribute('aria-current', SEQ.m && +b.getAttribute('data-m') === SEQ.m.oi && +b.getAttribute('data-k') === SEQ.k ? 'true' : 'false');
  });
  var ne = SEQ.m && SEQ.m.ne;
  if (!ne || !ne.t) { RAIL_NE.replaceChildren(); return; }
  var left = ne.t - ne.c;
  if (!left) { RAIL_NE.replaceChildren(el('p', null, (ne.t === 1 ? 'The entry point' : 'All ' + ne.t + ' entry points') + ' of this map ' + (ne.t === 1 ? 'has' : 'have') + ' a sequence.')); return; }
  RAIL_NE.replaceChildren(el('h2', null, 'Entry points with no sequence', el('span', null, left + ' of ' + ne.t)),
    el('ul', null, ne.x.map(function (x) { return el('li', null, el('code', null, x)); }), ne.mo ? el('li', null, 'and ' + ne.mo + ' more') : null));
}

// ---- the bar -----------------------------------------------------------------------------
// The acting cards and the measurement cards of step st for the live region.
function roleWords(st) {
  return ((st.a || []).length ? ' Acts: ' + st.a.join(', ') + '.' : '') + ((st.me || []).length ? ' Measures: ' + st.me.join(', ') + '.' : '');
}
function cardNames(ids) { return ids.length ? ids.join(', ') : 'no card'; }
function barWrite() {
  if (!BAR || !SEQ.m) return;
  var j = seqJ(), n = SEQ.step, st = n >= 0 ? j.s[n] : null, last = n === j.s.length - 1;
  Array.prototype.forEach.call(BAR.querySelectorAll('[data-form]'), function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-form') === SEQ.form)); });
  BAR_N.textContent = st ? 'Step ' + (n + 1) + ' of ' + j.s.length : 'Whole route';
  BAR_DOTS.replaceChildren.apply(BAR_DOTS, j.s.map(function (x, i) { return el('i', {'class': i < n ? 'was' : i === n ? 'now' : null}); }));
  var words = st ? [st.y || 'This step has no sentence.'] : [j.s.length ? 'The map shows the ' + counted(j.s.length, 'step') + ' of this sequence, with a number on each line.' : 'This sequence has no steps.'];
  if (st && !stepFlow(n)) words.push(el('small', null, 'This step has no flow. Its cards: ' + cardNames((st.a || []).concat(st.me || [])) + '.'));
  BAR_P.replaceChildren.apply(BAR_P, words);
  BAR_PREV.disabled = n < 0;
  BAR_NEXT.disabled = !j.s.length;
  BAR_NEXT.replaceChildren(); addChild(BAR_NEXT, [st ? (last ? 'Done' : 'Next') : 'Start', last ? null : el('span', {'aria-hidden': 'true'}, ' →')]);
  BAR_NEXT.setAttribute('aria-label', st ? (last ? 'Done: show the whole route' : 'Next step') : 'Start at step 1');
  BAR_NEXT.title = BAR_NEXT.getAttribute('aria-label') + (st && last ? '' : ' (Right arrow)');
  barHeight();
}
// The height of the bar for the reading line over it (`--bar-h`), and the bottom of the
// headline for the list under it (`--ask-b`). The page sets them again at a change of size.
function barHeight() { if (BAR) document.documentElement.style.setProperty('--bar-h', BAR.offsetHeight + 'px'); }
// The headline changes its text a short time after a choice (`headSync`). When its new
// height moves the list in that time, the fit of the map or the diagram is made again.
var ASK_BOX = document.getElementById('atlas-ask'), ASK_B = -1, FIT_AT = -Infinity;
function askBottom() {
  if (!ASK_BOX) return false;
  var b = Math.round(ASK_BOX.getBoundingClientRect().bottom);
  if (b === ASK_B) return false;
  ASK_B = b; document.documentElement.style.setProperty('--ask-b', b + 'px');
  return true;
}
function askMoved() {
  if (!askBottom() || !seqShown() || performance.now() - FIT_AT > 1000) return;
  if (SEQ.form === 'diagram') boardDraw(); else fitSeq();
}
if (window.ResizeObserver) {
  if (BAR) new ResizeObserver(barHeight).observe(BAR);
  if (ASK_BOX) new ResizeObserver(askMoved).observe(ASK_BOX);
}
// The free part of the screen in this view: under the headline or the list, over the bar,
// and at the right of the list on a wide screen.
function seqFree() {
  askBottom();
  var top = HEAD_H + 16, bottom = H - 16, left = 16;
  if (shownEl(BAR)) bottom = BAR.getBoundingClientRect().top - 12;
  if (shownEl(RAIL)) {
    var r = RAIL.getBoundingClientRect();
    if (W > WIDE) left = r.right + 14; else top = r.bottom + 10;
  }
  return {x0: left, y0: top, x1: W - 16 - sideRight(SEQ.m), y1: bottom};
}

// ---- the choice and the steps ------------------------------------------------------------
// The state of the view that a change starts from, for the fade of the lines (`layerAt`).
function viewNow() { return {mode: VIEW.mode, layer: VIEW.layer, q: SEQ.m, k: SEQ.k}; }
function seqChanged(from) {
  VIEW.swap = reduced() || !from ? null : {from: from, t0: performance.now()};
  VIEW.epoch++;
  headSync(!!from); relabel(currentMap()); viewTouch();
}
// Show sequence k of map m. `camera` moves the camera to the fit of its map.
function seqChoose(m, k, camera) {
  var from = viewNow(), same = SEQ.m === m && SEQ.k === k;
  SEQ.m = m; SEQ.k = k; SEQ.step = -1; SEQ.first = Object.create(null); SEQ.tagKey = '';
  m.sq[k].s.forEach(function (st, n) { if (st.f >= 0 && SEQ.first[st.f] === undefined) SEQ.first[st.f] = n; });
  HOT = {c: null, f: null, from: ''}; PIN = null;
  railSync(); barWrite();
  if (!same) seqChanged(from);
  if (SEQ.form === 'diagram') boardDraw();
  if (camera && SEQ.form === 'map') fitSeq();
  say(seqWords());
}
function fitSeq() { FIT_AT = performance.now(); flyTo(frameOf(SEQ.m), FIT); SAID_MAP = SEQ.m; }
// Go to step n: -1 is the whole route. The value stays from -1 to the last step.
function stepTo(n) {
  var j = seqJ();
  if (!j) return;
  n = clamp(n, -1, j.s.length - 1);
  if (n === SEQ.step) return;
  var fb = frameBottom(), was = seqFree().y1;
  SEQ.step = n; HOT = {c: null, f: null, from: ''}; PIN = null;
  VIEW.epoch++; barWrite(); speak(); lightMoved();
  if (SEQ.form === 'diagram') boardDraw();
  else if (fb !== null && fb <= was + 1 && fb > seqFree().y1 + 1) fitSeq();
  else if (n >= 0) stepCamera();
  var st = n >= 0 ? j.s[n] : null, f = stepFlow(n);
  say(st ? 'Step ' + (n + 1) + ' of ' + j.s.length + ': ' + (f ? f.s + ' to ' + f.t + ', ' + f.a + '. ' : 'No flow. ') + (st.y || 'This step has no sentence.') + roleWords(st) : 'Whole route of ' + j.n + '.');
}
// The bottom of the frame of the map of the sequence on the screen, or null while the camera
// moves or is in a different map, and on a phone, where the fit shows only a part of the map. When a taller bar covers a frame that was fully above
// the old bar, the step makes the fit again (`stepTo`).
function frameBottom() {
  if (W <= WIDE || flight || currentMap() !== SEQ.m || SEQ.form !== 'map') return null;
  var b = frameOf(SEQ.m);
  return (b[1] + b[3] - cam.y) * cam.k;
}
// The cards of step n: the two cards of its flow, or its acting and measurement cards.
function stepCards(n) {
  var st = seqJ().s[n], f = stepFlow(n), m = SEQ.m;
  return (f ? [f.s, f.t] : (st.a || []).concat(st.me || [])).map(function (id) { return m.byId[id]; }).filter(Boolean);
}
// Move the camera when the cards of the current step are not fully in the free part of the
// screen: at the same zoom, or at a smaller zoom when they do not fit. On a phone the zoom
// stays at 0.5 or more, as at the fit (`mapFit`), so that the text stays readable. When the
// two cards do not fit at that zoom, the camera goes to the middle of the step and moves so
// that the last card of the step (the target of the flow) is fully in view.
function stepCamera() {
  var list = stepCards(SEQ.step);
  if (!list.length || currentMap() !== SEQ.m) return;
  var box = list.map(worldBox).reduce(union), g = seqFree(), k = cam.k, sx = (box[0] - cam.x) * k, sy = (box[1] - cam.y) * k;
  if (sx >= g.x0 && sy >= g.y0 && sx + box[2] * k <= g.x1 && sy + box[3] * k <= g.y1) return;
  var fw = Math.max(1, g.x1 - g.x0), fh = Math.max(1, g.y1 - g.y0), lo = W > WIDE ? KMIN : 0.5 / SEQ.m.T.s;
  if (box[2] * k > fw || box[3] * k > fh) k = clamp(Math.min(fw * 0.9 / box[2], fh * 0.9 / box[3]), KMIN, KMAX);
  var cx = box[0] + box[2] / 2, cy = box[1] + box[3] / 2;
  if (k < lo) {
    var t = worldBox(list[list.length - 1]);
    k = lo; cx = viewAround(cx, t[0], t[2], fw / k); cy = viewAround(cy, t[1], t[3], fh / k);
  }
  fly({x: cx - (g.x0 + g.x1) / 2 / k, y: cy - (g.y0 + g.y1) / 2 / k, k: k});
}
// The centre c of a view of the size v, moved so that the part from a of the size s is in
// the view with a margin of 16 or less.
function viewAround(c, a, s, v) { var m = Math.min(16, Math.max(0, (v - s) / 2)); return clamp(c, a + s + m - v / 2, a - m + v / 2); }
function setForm(form) {
  if (form === SEQ.form) return;
  SEQ.form = form; document.body.setAttribute('data-form', form);
  cv.tabIndex = form === 'diagram' ? -1 : 0;
  barWrite(); lightMoved(); VIEW.epoch++;
  if (form === 'diagram') { select(null, {keep: true}); boardDraw(); say('Sequence diagram of ' + seqJ().n + '.'); }
  else { fitSeq(); say('The sequence on the map.'); }
}

// ---- the views -----------------------------------------------------------------------------
var VIEW_BTNS = Array.prototype.slice.call(document.querySelectorAll('#atlas-head [data-mode]'));
// Show the view `mode`: 'map', 'seq', 'states' (`atlas_states`) or 'focus' (`atlas_focus`) or
// 'history' (`atlas_history`).
// The selection, the pin and the pointed item go.
function setMode(mode) {
  if (mode === VIEW.mode || (mode === 'seq' && !SEQ_MAPS.length) || (mode === 'states' && !SM_MAPS.length) || (mode === 'focus' && !FC_MAPS.length) || (mode === 'history' && !HS_DATA)) return false;
  var from = viewNow();
  select(null, {keep: true});
  if (VIEW.mode === 'states') smHide();
  if (VIEW.mode === 'focus') fcHide();
  if (VIEW.mode === 'history') hsHide();
  HOT = {c: null, f: null, from: ''}; PIN = null; FOCUS = null;
  VIEW.mode = mode; document.body.setAttribute('data-mode', mode);
  VIEW_BTNS.forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-mode') === mode)); });
  if (mode === 'seq') {
    var m = currentMap();
    if (!SEQ.m || (SEQ.m !== m && SEQ_MAPS.indexOf(m) >= 0)) seqChoose(SEQ_MAPS.indexOf(m) >= 0 ? m : SEQ_MAPS[0], 0, false);
    else { railSync(); barWrite(); say(seqWords()); }
    cv.tabIndex = SEQ.form === 'diagram' ? -1 : 0;
    if (SEQ.form === 'diagram') boardDraw(); else fitSeq();
  } else if (mode === 'states') {
    cv.tabIndex = -1;
    smShow();
  } else if (mode === 'focus') {
    var from2 = FC_FROM;
    FC_FROM = null;
    fcShow(from2);
  } else if (mode === 'history') {
    hsShow();
  } else {
    cv.tabIndex = 0;
    fitCurrent();
    say('Map view. ' + layerWords(currentMap()));
  }
  if (mode !== 'states' && mode !== 'focus' && mode !== 'history') speak();
  lightMoved(); seqChanged(from);
  return true;
}
VIEW_BTNS.forEach(function (b) { b.addEventListener('click', function () { setMode(b.getAttribute('data-mode')); }); });
if (BAR) {
  Array.prototype.forEach.call(BAR.querySelectorAll('[data-form]'), function (b) { b.addEventListener('click', function () { setForm(b.getAttribute('data-form')); }); });
  BAR_PREV.addEventListener('click', function () { stepTo(SEQ.step - 1); });
  BAR_NEXT.addEventListener('click', function () { var j = seqJ(); stepTo(SEQ.step === j.s.length - 1 ? -1 : SEQ.step + 1); });
}
// The left and right arrow keys of the view (`atlas_input`): give true for a step key.
function seqKey(e) {
  if (VIEW.mode !== 'seq' || (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight')) return false;
  stepTo(SEQ.step + (e.key === 'ArrowRight' ? 1 : -1));
  return true;
}
if (SEQ_MAPS.length) railWrite();
// The state of the view for the tests.
function seqState() {
  var j = seqJ();
  return {mode: VIEW.mode, form: SEQ.form, map: SEQ.m ? SEQ.m.id : null, k: SEQ.k, id: j ? j.id : null, step: SEQ.step, n: j ? j.s.length : 0,
    layer: SEQ.m ? shownLayer(SEQ.m) : null, bar: BAR ? {n: BAR_N.textContent, p: BAR_P.textContent, next: BAR_NEXT.textContent, prev: !BAR_PREV.disabled,
      box: BAR.getBoundingClientRect().toJSON()} : null,
    rail: RAIL_LIST ? Array.prototype.map.call(RAIL_LIST.querySelectorAll('button'), function (b) { return {text: b.textContent, on: b.getAttribute('aria-current') === 'true'}; }) : [],
    railBox: RAIL ? RAIL.getBoundingClientRect().toJSON() : null, ne: RAIL_NE ? RAIL_NE.textContent : '',
    states: SEQ.m ? SEQ.m.flows.map(function (f) { return stepState(SEQ.m, f.i); }) : [], free: seqFree(),
    zoom: SEQ.m ? cam.k * SEQ.m.T.s : 0};
}
"""

BOARD_HTML = (
    '<div id="atlas-board" class="board" role="group" aria-label="Sequence diagram">'
    '<svg id="atlas-bsvg"><g id="atlas-bworld"></g></svg></div>'
)

BOARD_CSS = """
.board{position:fixed;left:var(--board-x,0px);top:var(--board-y,0px);width:var(--board-w,100%);height:var(--board-h,100%);display:none;
overflow:auto;overscroll-behavior:contain;scrollbar-width:thin;z-index:1}
.board svg{display:block}
body[data-mode="seq"][data-form="diagram"] .board{display:block}
.board .qrow{cursor:pointer;outline:none}
.board .qrow rect{fill:transparent}
.board .qrow:hover rect{fill:var(--tint)}
.board .qrow:focus-visible rect{fill:var(--tint);stroke:var(--focus);stroke-width:2}
.qlife{stroke:var(--line-2);stroke-width:1}
.qplate{fill:var(--map);pointer-events:none}
:root[data-inside] .board{--map:var(--inside)}
.board .fnode rect{fill:var(--card);stroke:var(--line-2);stroke-width:1}
.board .fnode text{font:600 13px/1 var(--fs);fill:var(--ink);text-anchor:middle}
.qbead circle{fill:var(--map);stroke:var(--ink-3);stroke-width:1}
.sedge{transition:opacity .2s;pointer-events:none}
.sedge path.wire{fill:none;stroke:var(--wire);stroke-width:1.3}
.sedge polygon{fill:var(--ink-3)}
.sedge text{font:500 12px/1 var(--fs);fill:var(--ink-2);text-anchor:middle;paint-order:stroke;stroke:var(--map);stroke-width:6px;stroke-linejoin:round}
.sedge text.start{text-anchor:start}
.sedge .qbead text{font:600 10.5px/1 var(--fm);fill:var(--ink-2);text-anchor:middle;stroke:none}
.sedge.done path.wire{stroke:var(--ink-2);stroke-width:1.6}
.sedge.done polygon{fill:var(--ink-2)}
.sedge.lit path.wire{stroke:var(--k,var(--ink));stroke-width:2.2}
.sedge.lit polygon{fill:var(--k,var(--ink))}
.sedge.lit text{fill:var(--ink)}
.sedge.lit .qbead circle{fill:var(--k,var(--ink));stroke:var(--k,var(--ink))}
.sedge.lit .qbead text{fill:var(--surface)}
.stepping .sedge:not(.lit):not(.done){opacity:.38}
"""

BOARD = r"""
// ---- the Sequences view: the diagram ---------------------------------------------------
var BOARD = document.getElementById('atlas-board'), BSVG = document.getElementById('atlas-bsvg'), BWORLD = document.getElementById('atlas-bworld'), SVG_NS = 'http://www.w3.org/2000/svg';
// The smallest scale of the diagram. At this scale a card name is 9.75 px high and a flow
// label 9 px. When the diagram is larger than its part of the screen at this scale, that
// part scrolls (a phone), and a change of the step scrolls the current row into view.
var BOARD_MIN = 0.75;
function sv(tag, attrs, parent, text) {
  var e = document.createElementNS(SVG_NS, tag);
  for (var k in attrs) if (attrs[k] !== null && attrs[k] !== undefined) e.setAttribute(k, attrs[k]);
  if (text !== undefined) e.textContent = text;
  if (parent) parent.appendChild(e);
  return e;
}
// The cards of the diagram in the order of their first step: the two ends of each flow,
// or the acting and measurement cards of a step with no flow.
function boardParts(m, j) {
  var parts = [];
  j.s.forEach(function (st) {
    var f = st.f >= 0 ? m.flows[st.f] : null;
    (f ? [f.s, f.t] : (st.a || []).concat(st.me || [])).forEach(function (id) { if (m.byId[id] && parts.indexOf(id) < 0) parts.push(id); });
  });
  return parts;
}
// The words of a row for a screen reader.
function rowWords(m, j, i) {
  var st = j.s[i], f = st.f >= 0 ? m.flows[st.f] : null;
  return 'Step ' + (i + 1) + ' of ' + j.s.length + ': ' + (f ? f.s + ' to ' + f.t + ', ' + f.a + '.' : 'no flow.') + (st.y ? ' ' + st.y : '');
}
function boardDraw() {
  if (!BWORLD || !seqShown()) return;
  var m = SEQ.m, j = seqJ(), parts = boardParts(m, j), wide = W > 1180, had = BOARD.contains(document.activeElement) ? document.activeElement.getAttribute('data-step') : null;
  BWORLD.replaceChildren(); BWORLD.setAttribute('class', SEQ.step >= 0 ? 'stepping' : '');
  var NW = 150, NH = 40, RH = 56, TOPY = 86, CW = Math.max(120, Math.min(210, 1000 / Math.max(1, parts.length)));
  var bw = Math.max(0, parts.length - 1) * CW + NW, bh = TOPY + j.s.length * RH + 10, g = seqFree();
  // A wide screen: at the right of the list. A middle screen: at the right of the list and
  // under the headline. A phone: under the row of the list.
  var left = W > WIDE ? Math.max(g.x0, wide ? 350 : 0) : 16, top = wide ? HEAD_H + 40 : W > WIDE ? ASK_EL.getBoundingClientRect().bottom + 16 : g.y0 + 8;
  var aw = Math.max(1, W - left - (W > WIDE ? 30 : 16)), ah = Math.max(1, g.y1 - top - 8);
  // The scale includes the margins of the content (12 at each side, 4 at the bottom), so that
  // the diagram scrolls only at BOARD_MIN. The 1 px keeps the rounded size in the box.
  var k = Math.max(BOARD_MIN, Math.min(1.2, (aw - 1) / (bw + 24), (ah - 1) / (bh + 4)));
  var tx = Math.max(12 * k, (aw - bw * k) / 2), ty = Math.max(0, (ah - bh * k) / 2);
  boardBox(left, top, aw, ah, Math.max(aw, tx + (bw + 12) * k), Math.max(ah, ty + (bh + 4) * k));
  BWORLD.setAttribute('transform', 'translate(' + tx + ' ' + ty + ') scale(' + k + ')');
  function X(id) { var i = parts.indexOf(id); return NW / 2 + Math.max(0, i) * CW; }
  BOARD.scale = k;
  parts.forEach(function (id) {
    var c = m.byId[id], x = X(id), w = Math.min(NW, CW - 14), ng = sv('g', {'class': 'fnode'}, BWORLD), n = Math.floor((w - 16) / 7.6);
    sv('path', {d: 'M' + x + ' ' + NH + 'V' + bh, 'class': 'qlife'}, BWORLD);
    sv('rect', {x: x - w / 2, y: 0, width: w, height: NH, rx: c.k === 'actor' ? NH / 2 : 9}, ng);
    sv('text', {x: x, y: NH / 2 + 4.5}, ng, id.length * 7.6 > w - 10 ? id.slice(0, n) + '...' : id);
  });
  j.s.forEach(function (st, i) {
    var f = st.f >= 0 ? m.flows[st.f] || null : null, y = TOPY + i * RH, cls = i === SEQ.step ? ' lit' : i < SEQ.step ? ' done' : '';
    var row = sv('g', {'class': 'qrow', role: 'button', tabindex: '0', 'data-step': i, 'aria-label': rowWords(m, j, i), 'aria-current': i === SEQ.step ? 'step' : null}, BWORLD);
    sv('rect', {x: -10, y: y - RH / 2 + 4, width: bw + 20, height: RH - 8, rx: 8}, row);
    var eg = sv('g', {'class': 'sedge' + cls, 'aria-hidden': 'true'}, BWORLD), x1 = X(boardX(m, st, parts));
    if (f) eg.style.setProperty('--k', 'var(' + (KIND[f.k] || '--ink-2') + ')');
    if (f) {
      var x2 = X(f.t), dir = x2 >= x1 ? 1 : -1;
      sv('path', {d: 'M' + (x1 + dir * 11) + ' ' + y + 'H' + (x2 - dir * 9), 'class': 'wire'}, eg);
      sv('polygon', {points: [x2 - dir, y, x2 - dir * 10, y - 4.4, x2 - dir * 10, y + 4.4].join(' ')}, eg);
      boardPlate(sv('text', {x: (x1 + x2) / 2, y: y - 9}, eg, shortText(f.a)), eg, 0.5);
    } else boardPlate(sv('text', {x: x1 + 18, y: y + 4, 'class': 'start'}, eg, 'No flow'), eg, 0);
    var bead = sv('g', {'class': 'qbead'}, eg);
    sv('circle', {cx: x1, cy: y, r: 10}, bead); sv('text', {x: x1, y: y + 3.6}, bead, String(i + 1));
  });
  if (had !== null) { var back = BWORLD.querySelector('[data-step="' + had + '"]'); if (back) back.focus({preventScroll: true}); }
  if (SEQ.step >= 0) boardShow(tx + X(boardX(m, j.s[SEQ.step], parts)) * k, ty + (TOPY + SEQ.step * RH) * k, RH * k);
}
// A plate in the color of the ground under the label t of the group eg of a row. The plate
// is not in the group, so that it keeps its full opacity when the row is faint: a lifeline
// does not go through the label of a later step. `at` is the anchor of the text: 0.5 for the
// middle, 0 for the start.
function boardPlate(t, eg, at) {
  var w = 0;
  try { w = t.getComputedTextLength(); } catch (e) { w = 0; }
  if (!(w > 0)) w = t.textContent.length * 6.6;
  var x = +t.getAttribute('x') - w * at, y = +t.getAttribute('y');
  BWORLD.insertBefore(sv('rect', {x: x - 4, y: y - 12, width: w + 8, height: 16, rx: 3, 'class': 'qplate'}), eg);
}
// The part of the screen of the diagram (x, y, w, h) and the size of its content (cw, ch).
function boardBox(x, y, w, h, cw, ch) {
  [['--board-x', x], ['--board-y', y], ['--board-w', w], ['--board-h', h]].forEach(function (v) { BOARD.style.setProperty(v[0], v[1] + 'px'); });
  BSVG.setAttribute('width', Math.ceil(cw)); BSVG.setAttribute('height', Math.ceil(ch));
}
// The column of the bead of a step: the source of its flow, or its first acting card.
function boardX(m, st, parts) {
  var f = st.f >= 0 ? m.flows[st.f] : null;
  return f ? f.s : (st.a || [])[0] || (st.me || [])[0] || parts[0];
}
// Scroll the diagram when the row of the current step (at x, y, of height h in the content)
// is not fully in view.
function boardShow(x, y, h) {
  var vw = BOARD.clientWidth, vh = BOARD.clientHeight;
  if (y - h / 2 < BOARD.scrollTop || y + h / 2 > BOARD.scrollTop + vh) BOARD.scrollTop = Math.max(0, y - vh / 2);
  if (x - 20 < BOARD.scrollLeft || x + 20 > BOARD.scrollLeft + vw) BOARD.scrollLeft = Math.max(0, x - vw / 3);
}
if (BWORLD) {
  BWORLD.addEventListener('click', function (e) { var r = e.target.closest ? e.target.closest('[data-step]') : null; if (r) stepTo(+r.getAttribute('data-step')); });
  BWORLD.addEventListener('keydown', function (e) {
    var r = e.target.closest ? e.target.closest('[data-step]') : null;
    if (r && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); stepTo(+r.getAttribute('data-step')); }
  });
}
function boardOn() { return seqShown() && SEQ.form === 'diagram'; }
// The rows of the diagram for the tests: the class of the edge of each row, and its box.
function boardState() {
  if (!BWORLD) return null;
  var edges = BWORLD.querySelectorAll('.sedge'), rows = BWORLD.querySelectorAll('.qrow');
  var view = BOARD.getBoundingClientRect().toJSON();
  return {on: boardOn() && getComputedStyle(BOARD).display !== 'none', cls: BWORLD.getAttribute('class'), k: BOARD.scale || 0, view: view,
    scroll: [BOARD.scrollWidth, BOARD.scrollHeight, BOARD.clientWidth, BOARD.clientHeight],
    texts: Array.prototype.map.call(BWORLD.querySelectorAll('.fnode text, .sedge > text'), function (t) { return parseFloat(getComputedStyle(t).fontSize) * (BOARD.scale || 0); }),
    nodes: Array.prototype.map.call(BWORLD.querySelectorAll('.fnode'), function (n) { return {text: n.textContent, box: n.getBoundingClientRect().toJSON()}; }),
    rows: Array.prototype.map.call(rows, function (r, i) {
      var e = edges[i];
      return {label: r.getAttribute('aria-label'), current: r.getAttribute('aria-current'), cls: e.getAttribute('class'), k: e.style.getPropertyValue('--k'),
        opacity: getComputedStyle(e).opacity, text: e.textContent, box: r.getBoundingClientRect().toJSON()};
    })};
}
"""
