"""Sequence controls: the whole route, one step at a time, the panel and the map marks.

`svg.page.journey` keeps its interface: `active`, `state`, `start`, `step`,
`stepBy`, `end` and `back`, and adds `route` for the whole route.
`svg.page.sequence` gives the full-screen script the current step, a way to go
to a step, and a notice after each change.
"""

from systemap.page_sequences import MARKS_JS

CONTROL_JS = r"""
var A = svg.systemap, P = svg.page, W = window.systemapWorkspace || {};
var D = W.sequences || {}, ARROW = ' → ';
var sel = byId('journey'), wholeBtn = byId('jwhole'), stepsBtn = byId('jsteps');
var wholeBar = byId('jwholebar'), stepBar = byId('jstepbar'), startBtn = byId('jstart');
var fullBtn = byId('jfull'), prev = byId('jprev'), next = byId('jnext'), count = byId('jcount');
var endBtn = byId('jend'), returnBtn = byId('jreturn'), index = byId('journeyindex');
var body = byId('seqbody'), strip = byId('strip'), stripN = byId('stripn');
var stripFoot = byId('stripfoot'), stripMeas = byId('stripmeas');
var cur = {j:-1, s:0, view:'whole'}, saved = null, seqView = null, prevMode = 'understand';
var presenting = false, listeners = [], lastJ = -1, revealToken = 0, left = null;

function J(){ return A.journeys[cur.j]; }
function meta(k){ return (D.journeys || [])[k] || {}; }
function edgeOf(st){ return st ? A.edges[st.edge] : null; }
function fromTo(e){ return e ? e.from + ARROW + e.to : ''; }
function plural(n, word){ return n + ' ' + word + (n === 1 ? '' : 's'); }
function press(b, on){ if(b){ b.setAttribute('aria-pressed', on ? 'true' : 'false'); } }
function mapState(){
  return {focus:A.state.focus, edge:A.state.edge, layer:A.state.layer, view:A.view.snapshot()};
}
function restoreMap(s){
  P.restoring(true);
  A.setJourney(null);
  if(s){
    P.setLayer(s.layer);
    if(s.focus){ A.select(s.focus, s.edge); } else { A.clear(); }
    A.view.restore(s.view, true);
  } else { A.clear(); }
  P.restoring(false);
}
function firstWithSteps(){
  for(var k = 0; k < A.journeys.length; k++){ if(A.journeys[k].steps.length){ return k; } }
  return A.journeys.length ? 0 : -1;
}

// ---- the toolbar and the title -------------------------------------------------
function syncBar(){
  var j = J(), n = j ? j.steps.length : 0, steps = cur.view === 'steps' && cur.j >= 0;
  if(sel && cur.j >= 0){ sel.value = String(cur.j); }
  press(wholeBtn, !steps); press(stepsBtn, steps);
  if(wholeBar){ wholeBar.hidden = steps; }
  if(stepBar){ stepBar.hidden = !steps; }
  [startBtn, stepsBtn, fullBtn].forEach(function(b){ if(b){ b.disabled = !n; } });
  if(count){ count.textContent = steps ? 'Step ' + (cur.s + 1) + ' of ' + n : ''; }
  if(prev){ prev.disabled = !steps || cur.s <= 0; }
  if(next){ next.disabled = !steps || cur.s >= n - 1; }
  if(returnBtn){ returnBtn.hidden = !(cur.j >= 0 && A.state.focus); }
}
function syncTitle(){
  var j = J();
  if(!j){ return; }
  var name = j.label.toUpperCase();
  if(cur.view === 'steps'){
    P.setTitle(name + ' · STEP ' + (cur.s + 1) + ' OF ' + j.steps.length,
      'What occurs at each step?');
  } else { P.setTitle(name + ' · WHOLE ROUTE', 'Which parts does this operation use?'); }
  var heading = byId('activity-question');
  if(heading){ heading.textContent = j.label; }
}

// ---- the panel -------------------------------------------------------------------
function headHtml(kicker, j, m){
  var entry = m.entry ? 'Entry point <code>' + esc(m.entry) + '</code>'
    : 'The model gives no entry point for this sequence.';
  return '<div class="seq-head">' + (kicker ? '<p class="seq-kicker">' + kicker + '</p>' : '')
    + '<h2 class="seq-title">' + esc(j.label) + '</h2><p class="seq-entry">' + entry + '</p>'
    + (j.drafted ? '<p class="seq-draft">Agent draft. Source review necessary.</p>' : '')
    + '</div>';
}
function routeHtml(j){
  if(!j.steps.length){ return '<p class="seq-note">This sequence has no steps.</p>'; }
  return '<ol class="seq-route">' + j.steps.map(function(st, k){
    var e = edgeOf(st);
    return '<li><button type="button" data-seq-step="' + k + '"><span class="seq-n">' + (k + 1)
      + '</span><span class="seq-ft">' + esc(fromTo(e)) + '</span><span class="seq-art">'
      + esc(e ? e.art : '') + '</span></button></li>';
  }).join('') + '</ol>';
}
function allHtml(){
  if(!A.journeys.length){ return ''; }
  return '<div class="seq-row seq-sec"><h3 class="seq-kicker">ALL SEQUENCES</h3>'
    + '<span class="seq-count">' + A.journeys.length + '</span></div>'
    + '<p class="seq-note seq-note--tight">The small map shows the regions that each sequence '
    + 'uses. The dot is the start.</p><ol class="seq-all">' + A.journeys.map(function(j, k){
      var m = meta(k), on = k === cur.j;
      return '<li><button type="button" class="seq-pick" data-journey="' + k
        + '" aria-pressed="' + on + '">' + (m.glyph || '<span></span>')
        + '<span class="seq-pick__text"><span class="seq-pick__label">' + esc(j.label)
        + '</span><span class="seq-pick__meta">' + (m.entry ? esc(m.entry) + ' · ' : '')
        + plural(j.steps.length, 'step') + '</span></span></button></li>';
    }).join('') + '</ol>';
}
function names(list){
  var code = list.map(function(n){ return '<code>' + esc(n) + '</code>'; });
  if(code.length < 2){ return code.join(''); }
  return code.slice(0, -1).join(', ') + ' or ' + code[code.length - 1];
}
function coverHtml(){
  var c = D.coverage || {}, h = '<div class="seq-cover"><div class="seq-row">'
    + '<h3 class="seq-kicker">ENTRY POINTS</h3>';
  if(!c.known){
    return h + '</div><p>The page has no source facts. It cannot count the entry points. '
      + 'Run <code>systemap refresh</code>.</p></div>';
  }
  if(!c.total){ return h + '</div><p>The source facts contain no entry points.</p></div>'; }
  h += '<span class="seq-count">' + c.covered + ' of ' + c.total
    + (c.covered === 1 ? ' has' : ' have') + ' a sequence</span></div>'
    + '<div class="seq-bar" style="--n:' + c.total + '" aria-hidden="true">';
  for(var k = 0; k < c.total; k++){ h += '<i' + (k < c.covered ? ' class="on"' : '') + '></i>'; }
  h += '</div>';
  if(!c.missing.length){ return h + '<p>Each entry point has a sequence.</p></div>'; }
  return h + '<p>No sequence starts at ' + names(c.missing)
    + (c.more ? ' and ' + c.more + ' more' : '')
    + '. Write one with <code>systemap journeys</code>.</p></div>';
}
function rolesHtml(st){
  var h = '';
  if((st.acts || []).length){ h += '<span class="seq-tag seq-tag--acts">ACTS</span><code>'
    + esc(st.acts.join(', ')) + '</code>'; }
  if((st.measures || []).length){ h += '<span class="seq-tag seq-tag--meas">MEASURES</span><code>'
    + esc(st.measures.join(', ')) + '</code>'; }
  return h ? '<span class="seq-roles">' + h + '</span>' : '';
}
function stepsHtml(j){
  var items = j.steps.map(function(st, k){
    var e = edgeOf(st), at = k < cur.s ? 'before' : (k > cur.s ? 'after' : 'now');
    var inner = '<span class="seq-n">' + (k + 1) + '</span><span class="seq-step__head">'
      + esc(fromTo(e) + (e ? ' · ' + e.art : '')) + '</span><span class="seq-step__say">'
      + esc(st.say) + '</span>';
    if(at === 'now'){
      return '<li><div class="seq-step" data-step="' + k + '" data-at="now" aria-current="step" '
        + 'tabindex="-1">' + inner + rolesHtml(st) + '</div></li>';
    }
    return '<li><button type="button" class="seq-step" data-step="' + k + '" data-at="' + at
      + '">' + inner + '</button></li>';
  }).join('');
  return '<div class="seq-row"><p class="seq-kicker">SEQUENCE</p><span class="seq-count">'
    + plural(j.steps.length, 'step') + '</span></div>' + headHtml('', j, meta(cur.j))
    + '<ol class="seq-steps">' + items + '</ol><div class="seq-key"><i class="now"></i>'
    + '<span>This step</span><i class="was"></i><span>Steps before this step</span>'
    + '<i class="later"></i><span>Steps after this step</span></div><p class="seq-note">The '
    + 'model gives the order of these steps. It is not a record of program execution.</p>';
}
function syncStrip(){
  var j = J(), st = j && cur.view === 'steps' ? j.steps[cur.s] : null;
  if(strip){ strip.hidden = !st; }
  if(!st){ return; }
  var e = edgeOf(st), parts = [], m = st.measures || [];
  if(j.starts){ parts.push('The sequence starts at ' + esc(j.starts) + '.'); }
  if(e && e.evidence_says){ parts.push(esc(e.evidence_says)); }
  if(j.drafted){ parts.push('Agent draft. Source review necessary.'); }
  if(stripN){ stripN.textContent = 'step ' + (cur.s + 1); }
  if(stripFoot){ stripFoot.innerHTML = parts.join(' '); }
  if(stripMeas){ stripMeas.textContent = m.length ? 'Measurement components: ' + m.join(', ')
    : 'No measurement component for this step.'; }
}
function focusKey(){
  var a = document.activeElement;
  if(!a || !body || !body.contains(a)){ return null; }
  var keys = ['data-step', 'data-seq-step', 'data-journey'];
  for(var k = 0; k < keys.length; k++){
    if(a.getAttribute(keys[k]) !== null){ return [keys[k], a.getAttribute(keys[k])]; } }
  return null;
}
function renderPanel(changed){
  if(!body){ return; }
  var key = focusKey(), list = body.querySelector('.seq-all'), top = list ? list.scrollTop : 0;
  var j = J();
  if(!A.journeys.length){ return; }
  if(index){ index.dataset.view = j ? cur.view : 'whole'; }
  body.innerHTML = !j ? allHtml() + coverHtml() : (cur.view === 'steps' ? stepsHtml(j)
    : headHtml('THE ROUTE IN ORDER', j, meta(cur.j)) + routeHtml(j) + allHtml() + coverHtml());
  list = body.querySelector('.seq-all');
  if(list){ list.scrollTop = top; }
  var mark = body.querySelector(cur.view === 'steps' ? '[aria-current="step"]'
    : '.seq-pick[aria-pressed="true"]');
  if(mark && mark.scrollIntoView && (changed || cur.view === 'steps') && index
    && !index.hidden){ mark.scrollIntoView({block:'nearest'}); }
  if(key){
    var again = body.querySelector('[' + key[0] + '="' + key[1] + '"]') || mark;
    if(again && again.focus){ again.focus({preventScroll:true}); }
  }
  syncStrip();
}

// ---- the map ---------------------------------------------------------------------
function markRoute(j, upto){
  // The cards of the route show at full strength. In full screen, only the
  // cards of the steps until the current step do.
  var ids = {};
  (j ? j.steps : []).forEach(function(st, k){
    if(upto >= 0 && k > upto){ return; }
    var e = edgeOf(st);
    (st.acts || []).concat(st.measures || []).forEach(function(id){ ids[id] = true; });
    if(e){ ids[e.from] = true; ids[e.to] = true; }
  });
  all('.node', svg).forEach(function(n){ n.classList.toggle('seq-route', !!ids[n.dataset.id]); });
}
function clearArea(){
  // The visible map less the band of the legend and the readout at its foot.
  var a = A.view.visibleArea(null), lg = document.getElementById('map-legend');
  var m = svg.getScreenCTM ? svg.getScreenCTM() : null;
  if(!a || !lg || !lg.offsetParent || !m){ return a; }
  var foot = lg.getBoundingClientRect().top - 8;
  var y = new DOMPoint(0, foot).matrixTransform(m.inverse()).y;
  return y > a.y + a.h / 2 && y < a.y + a.h ? {x:a.x, y:a.y, w:a.w, h:y - a.y} : a;
}
function drawingArea(){
  var a = clearArea(), v = A.view.snapshot();
  if(!a || !(a.w > 0) || !(v.k > 0)){ return null; }
  return {x:(a.x - v.tx) / v.k, y:(a.y - v.ty) / v.k, w:a.w / v.k, h:a.h / v.k};
}
function keepInView(rect, before){
  // The camera moves only when the step is not in view: a 300 ms pan at the same zoom.
  // It zooms out only when the step cannot fit at this zoom.
  A.view.restore(before, true);
  var area = clearArea(), v = before, m = 6;
  if(!rect || !area || !(area.w > 0)){ return; }
  if(VB){
    // Only the drawing can be in view: cut the rect at the drawing bounds.
    var cx0 = Math.max(rect.x, VB.x + m), cy0 = Math.max(rect.y, VB.y + m);
    rect = {x:cx0, y:cy0, w:Math.min(rect.x + rect.w, VB.x + VB.width - m) - cx0,
      h:Math.min(rect.y + rect.h, VB.y + VB.height - m) - cy0};
  }
  var x0 = v.k * rect.x + v.tx, y0 = v.k * rect.y + v.ty;
  var x1 = x0 + v.k * rect.w, y1 = y0 + v.k * rect.h;
  var l = area.x + m - 0.5, t = area.y + m - 0.5;
  var r = area.x + area.w - m + 0.5, b = area.y + area.h - m + 0.5;
  if(x0 >= l && y0 >= t && x1 <= r && y1 <= b){ return; }
  var k = Math.min(v.k, (area.w - 2 * m) / rect.w, (area.h - 2 * m) / rect.h);
  if(k < v.k){
    A.view.restore({k:k, tx:area.x + area.w / 2 - k * (rect.x + rect.w / 2),
      ty:area.y + area.h / 2 - k * (rect.y + rect.h / 2)}, false);
    return;
  }
  // The step fits at this zoom: the camera moves only the distance that puts it in view.
  function shift(lo, hi, a, z){ return lo < a ? a - lo : (hi > z ? z - hi : 0); }
  A.view.restore({k:v.k, tx:v.tx + shift(x0, x1, l, r), ty:v.ty + shift(y0, y1, t, b)}, false);
}
function reveal(note){
  // The note shows after the camera stops and the dot arrives (600 ms).
  var token = ++revealToken;
  if(!note){ return; }
  if(reduced()){ note.classList.remove('wait'); return; }
  function show(){ if(token === revealToken){ note.classList.remove('wait'); } }
  function wait(){ setTimeout(show, 600); }
  requestAnimationFrame(function(){ requestAnimationFrame(function(){
    if(A.view.whenStill){ A.view.whenStill(wait); } else { wait(); }
  }); });
}
function paintMap(camera){
  var j = J(), steps = cur.view === 'steps', st = steps ? j.steps[cur.s] : null;
  var before = A.view.snapshot(), area = camera === 'fit' ? null : drawingArea();
  if(st){
    var e = edgeOf(st);
    if(e && e.layer !== A.state.layer){ A.setJourney(null); P.setLayer(e.layer); }
  }
  A.setJourney(st || {acts:[], measures:[], edge:-1, say:'', whole:true});
  markRoute(j, presenting && st ? cur.s : -1);
  showMarks(true);
  var made = drawRoute({j:j, s:st ? cur.s : -1, present:presenting, area:area});
  if(camera === 'fit'){ A.view.restore(before, true); A.view.fit(); }
  else if(camera === 'frame' && st){ /* the framing of the step by setJourney stays */ }
  else if(camera === 'keep' && st){ keepInView(made.rect, before); }
  else { A.view.restore(camera === 'back' && seqView ? seqView : before, camera !== 'back'); }
  if(!st && camera === 'fit'){ drawInRoute(made); }
  reveal(made.note);
}

// ---- show a sequence -------------------------------------------------------------
function render(camera, changed){
  var j = J();
  if(!j){ return; }
  syncBar(); syncTitle(); renderPanel(changed); paintMap(camera);
  P.sync();
  var st = cur.view === 'steps' ? j.steps[cur.s] : null;
  svg.dispatchEvent(new CustomEvent('systemap:step', {bubbles:true, detail:{j:cur.j,
    s:st ? cur.s : -1, edge:st ? st.edge : -1, view:cur.view,
    route:j.steps.map(function(x){ return x.edge; })}}));
  svg.dispatchEvent(new CustomEvent('systemap:workspace'));
  listeners.forEach(function(fn){ fn(); });
}
function go(k, view, s, camera){
  var j = A.journeys[k];
  if(!j){ return; }
  if(!j.steps.length){ view = 'whole'; }
  var changed = cur.j !== k;
  if(cur.j < 0){
    saved = mapState();
    saved.mode = P.mode() === 'trace' ? prevMode : P.mode();
  }
  cur.j = k; lastJ = k; cur.view = view;
  cur.s = Math.max(0, Math.min(s || 0, j.steps.length - 1));
  if(P.mode() !== 'trace'){ P.setMode('trace'); }
  render(camera, changed);
}
function finish(restoreMode){
  var s = saved;
  // A sequence left for another view opens again at the same place.
  left = restoreMode ? null : {j:cur.j, s:cur.s, view:cur.view};
  saved = null; seqView = null; revealToken++;
  if(presenting && P.sequence.closePresent){ P.sequence.closePresent(true); }
  cur.j = -1; cur.view = 'whole'; cur.s = 0;
  clearMarks(); markRoute(null);
  restoreMap(s);
  syncBar(); renderPanel(false);
  if(s && restoreMode){ P.setMode(s.mode && s.mode !== 'trace' ? s.mode : 'understand'); }
  P.sync();
  svg.dispatchEvent(new CustomEvent('systemap:workspace'));
  listeners.forEach(function(fn){ fn(); });
}
function back(){
  // Back from a selected card to the sequence, with the camera of the sequence.
  if(cur.j < 0){ return; }
  render('back', false);
}
function end(how){
  // false: the shell leaves the view. No argument: one view back (Escape).
  if(how === false){ finish(false); return; }
  if(how === undefined && A.state.focus){ back(); return; }
  if(how === undefined && cur.view === 'steps'){ go(cur.j, 'whole', cur.s, 'fit'); return; }
  finish(true);
}
function stepBy(d){
  var j = J();
  if(!j){ return false; }
  if(cur.view !== 'steps'){
    if(d > 0 && j.steps.length){ go(cur.j, 'steps', 0, presenting ? 'frame' : 'keep'); }
    return true;
  }
  var s = cur.s + d;
  if(s >= 0 && s < j.steps.length){ go(cur.j, 'steps', s, 'keep'); }
  return true;
}

// ---- controls ----------------------------------------------------------------------
function on(node, fn){ if(node){ node.addEventListener('click', fn); } }
if(sel){ sel.addEventListener('change', function(){
  go(+sel.value, cur.view, 0, cur.view === 'steps' ? 'keep' : 'fit'); }); }
on(wholeBtn, function(){ go(cur.j, 'whole', cur.s, 'fit'); });
on(stepsBtn, function(){ go(cur.j, 'steps', cur.s, 'keep'); });
on(startBtn, function(){ go(cur.j, 'steps', 0, 'keep'); });
on(prev, function(){ stepBy(-1); });
on(next, function(){ stepBy(1); });
on(endBtn, function(){ go(cur.j, 'whole', cur.s, 'fit'); });
on(returnBtn, back);
if(index){ index.addEventListener('click', function(e){
  var b = e.target.closest && e.target.closest('[data-journey], [data-seq-step], [data-step]');
  if(!b || !index.contains(b)){ return; }
  e.stopPropagation();
  if(b.getAttribute('aria-current') === 'step'){ return; }
  if(b.hasAttribute('data-journey')){
    var k = +b.dataset.journey;
    go(k, 'whole', k === cur.j ? cur.s : 0, 'fit');
  } else { go(cur.j, 'steps', +(b.dataset.seqStep || b.dataset.step), 'keep'); }
}); }
svg.addEventListener('systemap:mode', function(e){
  var m = e.detail && e.detail.mode;
  if(m === 'trace' && cur.j < 0){
    var k = lastJ >= 0 ? lastJ : firstWithSteps(), at = left && left.j === k ? left : null;
    left = null;
    if(at && at.view === 'steps'){ go(k, 'steps', at.s, 'keep'); }
    else if(k >= 0){ go(k, 'whole', at ? at.s : 0, 'fit'); }
  }
  if(m && m !== 'trace'){ prevMode = m; }
});
svg.addEventListener('systemap:select', function(){
  if(cur.j < 0){ return; }
  markRoute(null); showMarks(false); syncBar();
});
svg.addEventListener('systemap:clear', syncBar);
svg.addEventListener('systemap:view', function(){
  // The view of the sequence, for the return from a selected card.
  if(cur.j >= 0 && !A.state.focus){ seqView = A.view.snapshot(); }
});
document.addEventListener('keydown', function(e){
  var sheet = byId('keys');
  if(e.altKey || e.ctrlKey || e.metaKey || cur.j < 0 || presenting || (sheet && !sheet.hidden)){
    return; }
  var t = e.target, tag = t && t.tagName;
  if(tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA'){ return; }
  if(e.key.toLowerCase() === 'w' && P.mode() === 'trace'){
    go(cur.j, 'whole', cur.s, 'fit'); e.preventDefault(); }
});

// ---- the legend and the readout --------------------------------------------------
function shownNow(){ return P.mode() === 'trace' && cur.j >= 0 && !A.state.focus; }
P.readoutFor.push(function(){
  if(!shownNow()){ return null; }
  var j = J(), m = meta(cur.j);
  if(cur.view === 'steps'){
    var e = edgeOf(j.steps[cur.s]);
    return (cur.s + 1) + ' · ' + fromTo(e) + (e ? ' · ' + e.art : '');
  }
  var parts = [plural(j.steps.length, 'step')];
  if(m.regions){ parts.push(plural(m.regions, 'region')); }
  if(m.actors){ parts.push(plural(m.actors, 'actor')); }
  return parts.join(' · ');
});
function lg(mark, text){ return '<span class="lg">' + mark + esc(text) + '</span>'; }
P.legendFor.push(function(){
  if(!shownNow()){ return null; }
  var j = J();
  if(cur.view !== 'steps'){
    return lg('<i class="seq-lg-line"></i>', 'Route') + lg('<i class="seq-lg-n">1</i>', 'Step')
      + lg('<i class="seq-tag seq-tag--start">START</i>', 'Entry point')
      + lg('<i class="seq-lg-quiet"></i>', 'Not in this sequence');
  }
  var st = j.steps[cur.s], h = lg('<i class="seq-lg-line seq-lg-line--now"></i>', 'This step');
  if(cur.s > 0){ h += lg('<i class="seq-lg-line seq-lg-line--was"></i>', 'Before'); }
  if(cur.s < j.steps.length - 1 && !presenting){
    h += lg('<i class="seq-lg-line seq-lg-line--later"></i>', 'After'); }
  if((st.acts || []).length){
    h += lg('<i class="seq-tag seq-tag--acts">ACTS</i>', 'Acting component'); }
  if((st.measures || []).length){
    h += lg('<i class="seq-tag seq-tag--meas">MEASURES</i>', 'Measurement component'); }
  return h;
});

// ---- the interfaces ----------------------------------------------------------------
P.journey = {
  active:function(){ return cur.j >= 0; },
  state:function(){ return {j:cur.j, s:cur.s, view:cur.view}; },
  start:function(k){ go(k, 'steps', 0, 'keep'); },
  route:function(k){ go(k, 'whole', 0, 'fit'); },
  step:function(k){
    var j = J();
    if(j && Number.isInteger(k) && k >= 0 && k < j.steps.length){ go(cur.j, 'steps', k, 'keep'); }
  },
  stepBy:stepBy,
  end:end,
  back:back
};
P.sequence = {
  state:function(){ return {j:cur.j, s:cur.s, view:cur.view}; },
  go:function(view, s, camera){ if(cur.j >= 0){ go(cur.j, view, s, camera); } },
  on:function(fn){ listeners.push(fn); },
  presenting:function(flag){ presenting = !!flag; },
  closePresent:null
};
renderPanel(false);
syncBar();
"""

SCRIPT = "(function(){\nvar svg = document.getElementById('schematic');\n" + (
    "if(!svg || !svg.systemap || !svg.page){ return; }\n" + MARKS_JS + CONTROL_JS + "})();\n"
)
