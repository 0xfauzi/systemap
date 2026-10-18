"""Flow selection, motion cues and source records in the inspector."""

RELATION_JS = r"""// ---- the readings ---------------------------------------------------------
// The selected layer limits the paths. Component selection keeps only its
// flow paths. Flow selection and sequence steps keep only one path.
function edgeIn(i, L){
  if(L === 'all'){ return true; }
  return !!(IN_READING[L] && IN_READING[L][i]);
}
function subjectOf(id, L){
  // A card the reading is about even when no edge it shows touches it.
  return !!(SUBJECT_OF[L] && SUBJECT_OF[L][id]);
}
function layerIds(L){
  var ids = table(), out = [];
  EDGES.forEach(function(e, i){ if(edgeIn(i, L)){ ids[e.from] = true; ids[e.to] = true; } });
  Object.keys(DETAIL).forEach(function(id){
    if(id !== '_meta' && (ids[id] || subjectOf(id, L))){ out.push(id); } });
  return out;
}
function after(node){
  // The sibling after a node, or null: the place for a new sibling.
  var kids = node.parentNode.childNodes, k = Array.prototype.indexOf.call(kids, node);
  return kids[k + 1] || null;
}
// Each card gets a highlight fill under its text and a ring outside it with
// a gap: the fill marks the selection, the ring keyboard focus and preview.
nodes.forEach(function(n){
  var box = n.querySelector('.node__box');
  if(!box){ return; }
  var b = boxOf(n), rx = +(box.getAttribute('rx') || 4);
  box.parentNode.insertBefore(el('rect', {'class':'node__hl', x:b.x + 1.5, y:b.y + 1.5,
    width:Math.max(0, b.w - 3), height:Math.max(0, b.h - 3), rx:Math.max(0, rx - 1.5),
    'aria-hidden':'true'}), after(box));
  n.appendChild(el('rect', {'class':'node__halo', x:b.x - 4, y:b.y - 4, width:b.w + 8,
    height:b.h + 8, rx:rx + 4, 'aria-hidden':'true'}));
});
// Each label stands on a chip of the map ground, so the line stops at it.
labels.forEach(function(l){
  var hit = l.querySelector('.flowlbl__hit');
  if(!hit){ return; }
  l.insertBefore(el('rect', {'class':'flowlbl__chip', x:+hit.getAttribute('x'),
    y:+hit.getAttribute('y') + 3.5, width:+hit.getAttribute('width'),
    height:Math.max(0, +hit.getAttribute('height') - 7), rx:4, 'aria-hidden':'true'}),
    after(hit));
});
// A label that the router could not seat on its own line stays off the map
// at rest (rule 2: the panel list names it). It shows on preview, on
// selection and for the flows of a selected component.
function pointsOf(d){
  var n = (d || '').match(/-?[0-9]+(?:[.][0-9]+)?/g) || [], out = [];
  for(var k = 0; k + 1 < n.length; k += 2){ out.push({x:+n[k], y:+n[k + 1]}); }
  return out;
}
function nearBox(a, b, r, pad){
  // True if the segment from a to b passes within pad of the box r. The
  // router draws only horizontal and vertical runs, so the box of the
  // segment is the segment.
  return Math.max(a.x, b.x) >= r.x - pad && Math.min(a.x, b.x) <= r.x + r.w + pad
    && Math.max(a.y, b.y) >= r.y - pad && Math.min(a.y, b.y) <= r.y + r.h + pad;
}
function besideLine(l){
  var hit = l.querySelector('.flowlbl__hit'), p = flowOf[l.dataset.edge];
  if(!hit || !p){ return false; }
  var r = {x:+hit.getAttribute('x'), y:+hit.getAttribute('y') + 6,
    w:+hit.getAttribute('width'), h:Math.max(0, +hit.getAttribute('height') - 12)};
  var pts = pointsOf(p.getAttribute('d'));
  if(!(r.w > 0) || pts.length < 2){ return false; }
  for(var k = 0; k + 1 < pts.length; k++){
    if(nearBox(pts[k], pts[k + 1], r, 4)){ return false; }
  }
  return true;
}
var besideOf = {}, besideEdges = [];
labels.forEach(function(l){
  if(besideLine(l)){
    l.classList.add('beside'); besideOf[l.dataset.edge] = true; besideEdges.push(+l.dataset.edge);
  }
});
besideEdges.sort(function(a, b){ return a - b; });
function selectedEdge(){
  return state.edge >= 0 ? state.edge : (state.journey ? state.journey.edge : -1);
}

// ---- the motion ------------------------------------------------------------
// Motion shows direction and order, one time. A dot moves one time along
// the selected flow and then its label shows. The flows of a selected card
// draw again from source to target. Reduced motion shows the end state.
function later(fn){
  // After the page lays out the panel and the camera stops.
  requestAnimationFrame(function(){ requestAnimationFrame(function(){ whenStill(fn); }); });
}
var reveals = 0;
function unreveal(p){
  var r = p._reveal;
  if(!r){ return; }
  p._reveal = null;
  try { r.anim.cancel(); } catch(_x){}
  if(r.trace){
    if(r.trace.parentNode){ r.trace.parentNode.removeChild(r.trace); }
  } else { p.removeAttribute('mask'); }
  if(r.mask.parentNode){ r.mask.parentNode.removeChild(r.mask); }
  if(r.label){ r.label.classList.remove('cueing'); }
}
function traceOf(p){
  // A thicker copy of the line, with the same color and dash, that draws
  // over the line. It has no arrowhead and takes no pointer input.
  var t = el('path', {'class':'flowtrace', d:p.getAttribute('d'), fill:'none',
    stroke:p.getAttribute('stroke'), 'stroke-linecap':'round', 'aria-hidden':'true'});
  var dash = p.getAttribute('stroke-dasharray');
  if(dash){ t.setAttribute('stroke-dasharray', dash); }
  p.parentNode.insertBefore(t, after(p));
  return t;
}
function fadeTrace(p, a){
  // The trace goes in 160 ms after it completes. The line stays as it was.
  var r = p._reveal;
  if(!r || r.anim !== a){ return; }
  if(!r.trace || !r.trace.animate){ unreveal(p); return; }
  r.anim = r.trace.animate([{opacity:1}, {opacity:0}], {duration:160, fill:'both'});
  r.anim.onfinish = function(){ if(p._reveal === r){ unreveal(p); } };
}
function drawLines(list, opt){
  // Draw each line from its source to its target. A mask uncovers the line,
  // so its dash pattern and its arrowhead do not change. With `over`, a
  // thicker trace draws over the line that stays. Returns the count.
  opt = opt || {};
  var defs = svg.querySelector('defs'), count = 0;
  if(reduced() || !defs){ return 0; }
  var each = opt.each || 300, stagger = opt.stagger || 0, delay = opt.delay || 0, pad = 12;
  list.forEach(function(i){
    var p = flowOf[i];
    if(!p || !p.animate || !p.getTotalLength || p.classList.contains('off')){ return; }
    var len = p.getTotalLength(), b = p.getBBox();
    if(!(len > 0)){ return; }
    unreveal(p);
    var id = svg.id + '-reveal-' + (++reveals);
    var m = el('mask', {id:id, maskUnits:'userSpaceOnUse', x:b.x - pad, y:b.y - pad,
      width:b.width + 2 * pad, height:b.height + 2 * pad});
    var s = el('path', {d:p.getAttribute('d'), fill:'none', stroke:'#fff', 'stroke-width':pad,
      'stroke-linecap':'square', 'stroke-linejoin':'round',
      'stroke-dasharray':len + ' ' + len, 'stroke-dashoffset':len});
    m.appendChild(s);
    defs.appendChild(m);
    var trace = opt.over ? traceOf(p) : null;
    (trace || p).setAttribute('mask', 'url(#' + id + ')');
    var lbl = opt.labels ? labelOf[i] : null;
    if(lbl){ lbl.classList.add('cueing'); }
    var a = s.animate([{strokeDashoffset:len}, {strokeDashoffset:0}],
      {duration:each, delay:delay + count * stagger, easing:'cubic-bezier(.3,0,.2,1)',
        fill:'both'});
    p._reveal = {mask:m, anim:a, label:lbl, trace:trace};
    a.onfinish = trace ? function(){ fadeTrace(p, a); }
      : function(){ if(p._reveal && p._reveal.anim === a){ unreveal(p); } };
    count++;
  });
  return count;
}
function stopReveals(){ flows.forEach(unreveal); }
var cue = {edge:-1, token:0, dot:null, label:null};
function stopCue(){
  cue.token++;
  if(cue.dot && cue.dot.parentNode){ cue.dot.parentNode.removeChild(cue.dot); }
  if(cue.label){ cue.label.classList.remove('cueing'); }
  cue.dot = null; cue.label = null;
}
function runCue(i){
  // One dot from the source to the target in 600 ms, ease-in-out. It is
  // the only direction cue on the map, and it does not repeat.
  var p = flowOf[i];
  if(!p || !p.animate || !p.getTotalLength){ return; }
  var len = p.getTotalLength();
  if(!(len > 0)){ return; }
  var frames = [], n = Math.max(2, Math.min(64, Math.ceil(len / 16)));
  for(var k = 0; k <= n; k++){
    var q = p.getPointAtLength(len * k / n);
    frames.push({transform:'translate(' + q.x.toFixed(1) + 'px,' + q.y.toFixed(1) + 'px)',
      offset:k / n});
  }
  var dot = el('circle', {'class':'flowdot moving', cx:0, cy:0, r:5, 'aria-hidden':'true'});
  p.parentNode.appendChild(dot);
  cue.dot = dot; cue.label = labelOf[i] || null;
  if(cue.label){ cue.label.classList.add('cueing'); }
  // The dot shows at the source in 120 ms, moves for 600 ms and goes in
  // 120 ms. The label shows when the dot arrives.
  var token = cue.token;
  var move = dot.animate(frames, {duration:600, delay:120, easing:'cubic-bezier(.45,0,.25,1)',
    fill:'both'});
  var fade = dot.animate([{opacity:0}, {opacity:1, offset:1 / 7}, {opacity:1, offset:6 / 7},
    {opacity:0}], {duration:840, fill:'both'});
  move.onfinish = function(){
    if(token === cue.token && cue.label){ cue.label.classList.remove('cueing'); cue.label = null; }
  };
  fade.onfinish = function(){ if(token === cue.token){ stopCue(); } };
}
function syncCue(i){
  var next = booted && !reduced() && i >= 0 && flowOf[i] ? i : -1;
  if(next === cue.edge){ return; }
  stopCue();
  cue.edge = next;
  if(next < 0){ return; }
  var token = cue.token;
  later(function(){ if(token === cue.token){ runCue(next); } });
}
var drawnFocus = '';
function syncDraw(f, chosen, lit){
  // A new card selection draws its flows again, after the other parts dim.
  if(f === drawnFocus){ return; }
  drawnFocus = f;
  if(!f || chosen >= 0 || !lit || !lit.edges.length || !booted || reduced()){ return; }
  var edges = lit.edges.slice();
  later(function(waited){
    if(state.focus === f && selectedEdge() < 0){
      drawLines(edges, {each:240, delay:waited ? 0 : 160, over:true});
    }
  });
}
var underlay = null;
function syncUnderlay(i){
  // The halo under the selected or current line. No state changes the color of a
  // line: the line keeps the hue of its flow kind and the dash of its evidence.
  var p = flowOf[i];
  if(!p){
    if(underlay && underlay.parentNode){ underlay.parentNode.removeChild(underlay); }
    return;
  }
  if(!underlay){ underlay = el('path', {'class':'flowhl', 'aria-hidden':'true'}); }
  underlay.setAttribute('d', p.getAttribute('d'));
  underlay.setAttribute('data-edge', i);
  p.parentNode.insertBefore(underlay, p);
}

// ---- the paint ------------------------------------------------------------
function paint(){
  var f = state.focus, j = state.journey, L = state.layer, chosen = selectedEdge();
  var lit = litSet(), near = lit ? lit.ids : table(), jset = table();
  if(j){
    (j.acts || []).concat(j.measures || []).forEach(function(id){ jset[id] = true; });
  }
  var e = EDGES[chosen], pe = EDGES[state.peek];
  if(e){ jset[e.from] = true; jset[e.to] = true; }
  var inLayer = table();
  EDGES.forEach(function(e, i){
    if(edgeIn(i, L)){ inLayer[e.from] = true; inLayer[e.to] = true; } });
  flows.forEach(function(p){
    var i = +p.dataset.edge, on = edgeIn(i, L);
    var hot = i === chosen, preview = i === state.peek;
    var vis = chosen >= 0 ? hot : (j ? false : (lit ? lit.edges.indexOf(i) >= 0 : on));
    vis = vis || preview;
    setCls(p, {off:!vis, hot:hot, dim:false, peek:preview});
    p.setAttribute('tabindex', vis ? '0' : '-1');
    p.setAttribute('aria-pressed', hot ? 'true' : 'false');
    if(labelOf[i]){
      // A line that the reading draws shows its label on the line. A label
      // beside its line shows only for a preview or the selected flow: the
      // panel lists it in all other states (board rule 2).
      var shown = vis && (!besideOf[i] || hot || preview);
      setCls(labelOf[i], {off:!shown, hot:hot, dim:false, peek:preview});
      labelOf[i].setAttribute('aria-pressed', hot ? 'true' : 'false');
    }
  });
  nodes.forEach(function(n){
    var id = n.dataset.id;
    var subject = L !== 'all' && L !== 'structure' && subjectOf(id, L);
    n.style.setProperty('--subject', subject ? LCOL[L] : '');
    n.setAttribute('aria-pressed', id === f ? 'true' : 'false');
    setCls(n, {sel:id === f, dim:f ? !near[id] : (j ? !jset[id] : false),
      quiet:!f && !j && L !== 'all' && !inLayer[id] && !subjectOf(id, L), subject:subject,
      endpoint:!!(e && (id === e.from || id === e.to)),
      peekend:!!(pe && (id === pe.from || id === pe.to)),
      acts:!!(j && (j.acts || []).indexOf(id) >= 0),
      meas:!!(j && (j.measures || []).indexOf(id) >= 0)});
  });
  svg.classList.toggle('focused', !!f);
  svg.classList.toggle('peeking', !!pe);
  syncUnderlay(chosen);
  syncCue(chosen);
  syncDraw(f, chosen, lit);
}

// ---- the inspector -------------------------------------------------------
function swatch(e){
  // A short line in the color of the flow kind with the dash of its evidence.
  return '<i class="systemap-f__swatch" data-dash="' + esc(e.evidence) + '" style="--c:'
    + esc(LCOL[e.layer] || PAL.ink) + '" aria-hidden="true"></i>';
}
function heading(label, count){
  return '<div class="systemap-f__label-row"><h4 class="systemap-f__label">' + label + '</h4>'
    + (count === undefined ? '' : '<span class="systemap-f__count">' + count + '</span>')
    + '</div>';
}
function endpointButton(id, role){
  var d = recordOf(id);
  return '<button type="button" class="systemap-f__endpoint" data-endpoint="' + esc(id)
    + '"><small>' + role + '</small><code>' + esc(id) + '</code><span>'
    + esc(d ? d.plain : '') + '</span></button>';
}
function assuranceRow(a){
  // The assurance level and the freshness of a claim (`assurance.py`), with its text.
  if(!a){ return ''; }
  return '<p class="systemap-f__assurance" data-level="' + esc(a.level) + '" data-freshness="'
    + esc(a.freshness) + '"><b>' + esc(a.level) + ' · ' + esc(a.freshness) + '</b> '
    + esc((ATEXT[a.level] || '') + ' ' + (ATEXT[a.basis] || '')) + '</p>';
}
function evidenceLabel(state){
  return state === 'observed' ? 'current source review' : state;
}
function evidenceReason(e){
  if(e.evidence === 'external'){
    return 'This flow crosses the code boundary. Imports cannot show its direction or artifact.';
  }
  if(e.evidence === 'declared'){
    return 'This flow has no structural evidence. Source review of its direction and '
      + 'artifact is necessary. A judgement answer does not change the flow evidence.';
  }
  if(e.evidence === 'observed'){
    return 'The map records a source review for this flow. Its source records still agree with '
      + 'the code at this revision, and the flow agrees with the recorded review digest. '
      + 'There is no record of program execution.';
  }
  var support=[];
  if(e.import_present){support.push('An import connects the components.');}
  if(e.shared_module){support.push('Both components have a claim for the same module.');}
  if(e.mechanism){support.push('The model names the configured mechanism "'
    +e.mechanism+'".');}
  return support.join(' ')+' These facts show a possible connection. Source review of direction '
    +'and artifact is necessary.';
}
function evidenceReview(e){
  var h='',refs=e.source_refs || [],unresolved=e.unresolved_refs || [];
  if(e.claim_changed){
    h+='<p class="systemap-f__review-warning" data-claim-changed>Source review necessary. '
      +'The recorded review digest is missing or different from the flow claim digest.</p>';
  }
  if(unresolved.length){
    h+='<div class="systemap-f__review-warning" data-unresolved-refs><p>Source review necessary. '
      +'These references do not identify source at this revision.</p><ul>'
      +unresolved.map(function(ref){return '<li><code>'+esc(ref)+'</code></li>';}).join('')
      +'</ul></div>';
  }
  if(refs.length){
    h+='<details class="systemap-f__refs"><summary>Source references ('+refs.length+')</summary>'
      +'<p>A source digest identifies the source text for a source review.</p><ul>'
      +refs.map(function(ref){return '<li><code>'+esc(ref)+'</code></li>';}).join('')+'</ul>';
    if(e.review_digest){h+='<p>Recorded flow review digest: <code>'+esc(e.review_digest)
      +'</code></p>';}
    h+='</details>';
  }
  return h;
}
function relationshipHtml(i){
  var e = EDGES[i];
  if(!e){ return '<p class="systemap-f__hint">Select a flow path or a flow from the list.</p>'; }
  var layer = LAYER_AT[e.layer];
  return heading('Selected flow') + '<p class="systemap-f__artifact">' + swatch(e) + esc(e.art)
    + '</p><div class="systemap-f__endpoints">' + endpointButton(e.from, 'From')
    + endpointButton(e.to, 'To') + '</div><p class="systemap-f__metadata"><span>'
    + esc(layer ? layer.label : e.layer) + '</span><span class="systemap-f__state '
    + esc(e.evidence) + '" data-evidence-state="'+esc(e.evidence)+'">'
    + esc(evidenceLabel(e.evidence)) + '</span></p>'
    + '<p class="systemap-f__say" data-say>'
    + esc(e.say || 'The model has no explanation for this flow.') + '</p>'
    + '<p class="systemap-f__evidence" data-evidence>' + esc(e.evidence_says || '') + '</p>'
    + '<p class="systemap-f__reason">' + esc(evidenceReason(e)) + '</p>'
    + assuranceRow(e.assurance) + evidenceReview(e);
}
function flowChoice(i, out){
  var e = EDGES[i];
  return '<button type="button" class="systemap-f__flow-choice" data-inspect-edge="' + i
    + '" data-evidence-state="' + esc(e.evidence) + '" aria-pressed="'
    + (i === state.edge ? 'true' : 'false') + '">' + swatch(e) + '<b>' + esc(e.art)
    + '</b><span class="systemap-f__route">' + (out ? 'to ' + esc(e.to) : 'from ' + esc(e.from))
    + '</span><small class="systemap-f__sr">' + esc(evidenceLabel(e.evidence))
    + '</small></button>';
}
function flowGroup(label, dir, list){
  if(!list.length){ return ''; }
  return '<section class="systemap-f__flow-group" data-flow-direction="' + dir + '">'
    + heading(label, list.length)
    + list.map(function(i){ return flowChoice(i, dir === 'out'); }).join('') + '</section>';
}
function flowChoices(d){
  var edges = d.edges || [];
  if(!edges.length){ return '<p class="systemap-f__hint">The component has no flow.</p>'; }
  return flowGroup('Receives', 'in', edges.filter(function(i){ return EDGES[i].to === d.id; }))
    + flowGroup('Sends', 'out', edges.filter(function(i){ return EDGES[i].from === d.id; }));
}
function touches(step, id){
  var e = EDGES[step.edge];
  return !!(e && (e.from === id || e.to === id)) || (step.acts || []).indexOf(id) >= 0
    || (step.measures || []).indexOf(id) >= 0;
}
function sequenceRows(d){
  // One row for each sequence with a step that this component acts in,
  // measures, or sends or receives the artifact of. The page starts the
  // sequence at the first of these steps.
  var rows = (META.journeys || []).map(function(j, k){
    var steps = [];
    (j.steps || []).forEach(function(s, n){ if(touches(s, d.id)){ steps.push(n + 1); } });
    if(!steps.length){ return ''; }
    var inner = '<span>' + esc(j.label) + '</span><span class="systemap-f__steps">'
      + (steps.length === 1 ? 'step ' : 'steps ') + steps.join(', ') + '</span>';
    if(!PAGE){ return '<div class="systemap-f__seq">' + inner + '</div>'; }
    return '<button type="button" class="systemap-f__seq" data-journey="' + k
      + '" data-journey-step="' + (steps[0] - 1) + '">' + inner + '</button>';
  }).join('');
  return rows ? '<section class="systemap-f__section">' + heading('In sequences') + rows
    + '</section>' : '';
}
function madeOf(d){
  var mods = d.modules || [];
  if(!mods.length && !d.interface){ return ''; }
  return '<section class="systemap-f__section">' + heading('Made of')
    + (mods.length ? '<div class="systemap-f__chips">' + mods.map(function(m){
      return '<code class="systemap-f__chip">' + esc(m) + '</code>'; }).join('') + '</div>' : '')
    + (d.interface ? '<p class="systemap-f__iface">' + esc(d.interface) + '</p>' : '')
    + '</section>';
}
function rulesOf(d){
  var rules = d.rules || [];
  if(!rules.length){ return ''; }
  return '<section class="systemap-f__section">' + heading('Rules')
    + '<div class="systemap-f__rules">' + rules.map(function(n){
      return '<b>' + n + '</b><span>' + esc(RULES[n] || '') + assuranceRow(RULE_LEVEL[n])
        + '</span>'; }).join('')
    + '</div></section>';
}
function partDetails(d){
  var h = '<details class="systemap-f__details"><summary>Component details</summary>'
    + '<p class="systemap-f__kind">Kind: ' + esc(d.kind)
    + (d.calls_model ? '. This component calls a model.' : '') + '</p>';
  if(d.kind !== 'actor'){
    h += '<p class="systemap-f__entry">Entry point: <b>'
      + (d.entry ? esc(d.entry) + (d.entry_module ? ' (' + esc(d.entry_module) + ')' : '')
        : 'The component has no entry name.') + '</b></p>';
  }
  return h + '</details>';
}
function mapInside(d){
  if(!d.map){ return ''; }
  var h = '<p class="systemap-f__opens">Map inside: <b>' + esc(d.map.name)
    + (d.map.cards ? ' (' + d.map.cards + ' cards)' : '') + '</b></p>';
  if(d.map.href){
    if(d.map.preview){ h += '<div class="systemap-f__preview" inert>' + d.map.preview + '</div>'; }
    h += '<button type="button" class="systemap-f__open" data-open-map="' + esc(d.id)
      + '">Open map</button>';
  }
  return h;
}
function regionLabel(id){
  var out = '';
  (META.regions || []).forEach(function(r, k){ if(r.id === id){ out = (k + 1) + ' ' + r.label; } });
  return out;
}
function describe(d){
  // The head row names the kind and the region. On the page, the drawer
  // has its own Clear button at the right of this row.
  var region = regionLabel(d.region);
  var h = '<div class="systemap-f"><div class="systemap-f__head' + (PAGE ? ' systemap-f__head--room'
    : '') + '"><p class="systemap-f__eyebrow">' + (d.kind === 'actor' ? 'Actor' : 'Component')
    + (region ? ' &middot; ' + esc(region) : '') + '</p>'
    + (PAGE ? '' : '<button type="button" class="systemap-f__clear" data-clear>Clear</button>')
    + '</div><div class="systemap-f__title"><h3 class="systemap-f__code">' + esc(d.id)
    + '</h3><p class="systemap-f__plain">' + esc(d.plain || '') + '</p></div>';
  h += '<section class="systemap-f__relationship" data-relationship'
    + (EDGES[state.edge] ? '' : ' hidden') + '>' + relationshipHtml(state.edge) + '</section>';
  if(d.does){ h += '<p class="systemap-f__does">' + esc(d.does) + '</p>'; }
  h += assuranceRow(d.assurance);
  if(d.note){ h += '<p class="systemap-f__note"><b>Note</b> ' + esc(d.note) + '</p>'; }
  h += mapInside(d) + '<div class="systemap-f__connections"><div class="systemap-f__flow-list">'
    + flowChoices(d) + '</div></div>';
  return h + sequenceRows(d) + madeOf(d) + rulesOf(d) + partDetails(d) + '</div>';
}
function peek(i){
  if(!EDGES[i]){ unpeek(); return; }
  if(state.peek === i){ return; }
  state.peek = i;
  paint();
}
function unpeek(){
  if(state.peek < 0){ return; }
  state.peek = -1;
  paint();
}
function previewLeave(ev){
  var next = ev.relatedTarget && ev.relatedTarget.closest
    ? ev.relatedTarget.closest('.flow, .flowlbl, [data-inspect-edge]') : null;
  var current = ev.currentTarget;
  var i = +(current.dataset.inspectEdge || current.dataset.edge);
  if(next && +(next.dataset.inspectEdge || next.dataset.edge) === i){ return; }
  unpeek();
}
function bindPreview(control, i){
  control.addEventListener('mouseenter', function(){ peek(i); });
  control.addEventListener('focus', function(){ peek(i); });
  control.addEventListener('mouseleave', previewLeave);
  control.addEventListener('blur', unpeek);
}
function opensPage(cid){
  var d = recordOf(cid);
  return !!(d && d.map && d.map.href);
}
function openMap(cid, opener){
  if(!opensPage(cid)){ return; }
  var m = recordOf(cid).map;
  svg.dispatchEvent(new CustomEvent('systemap:open',
    {detail:{id:cid, name:m.name, href:m.href, cards:m.cards, opener:opener}, bubbles:true}));
}
function bindPanel(){
  if(!panel){ return; }
  Array.prototype.slice.call(panel.querySelectorAll('[data-inspect-edge]')).forEach(function(s){
    bindPreview(s, +s.dataset.inspectEdge);
  });
}
function panelFocusKey(){
  var active = document.activeElement;
  if(!panel || !active || !panel.contains(active)){ return null; }
  var attributes = ['data-endpoint', 'data-inspect-edge', 'data-open-map'];
  for(var i = 0; i < attributes.length; i++){
    var value = active.getAttribute(attributes[i]);
    if(value !== null){ return {attribute:attributes[i], value:value}; }
  }
  return {attribute:'', value:''};
}
function restorePanelFocus(key){
  if(!key){ return; }
  var candidates = Array.prototype.slice.call(panel.querySelectorAll(
    '[data-endpoint], [data-inspect-edge], [data-open-map]'));
  var target = candidates.filter(function(control){
    return control.getAttribute(key.attribute) === key.value;
  })[0];
  if(!target){
    target = panel.querySelector('.systemap-f__code');
    if(target){ target.setAttribute('tabindex', '-1'); }
  }
  if(target){ target.focus({preventScroll:true}); }
}
function select(cid, edge){
  var d = recordOf(cid);
  if(!d){ return; }
  var e = EDGES[edge];
  state.focus = cid; state.peek = -1;
  state.edge = e && (e.from === cid || e.to === cid) ? +edge : -1;
  paint(); frameFocus(null, !booted);
  if(panel){
    var focusKey = panelFocusKey();
    panel.innerHTML = describe(d); panel.classList.add('on'); bindPanel();
    restorePanelFocus(focusKey);
  }
  svg.dispatchEvent(new CustomEvent('systemap:select',
    {detail:{id:cid, edge:state.edge}, bubbles:true}));
}
function inspectFlow(i, endpoint){
  var e = EDGES[i];
  if(!e){ return; }
  var id = endpoint || state.focus;
  if(id !== e.from && id !== e.to){ id = e.from; }
  select(id, i);
  svg.dispatchEvent(new CustomEvent('systemap:flow', {detail:{edge:i, id:id}, bubbles:true}));
}
if(panel){
  function panelAction(ev){
    var target = ev.target.closest(
      '[data-endpoint], [data-inspect-edge], [data-open-map], [data-clear]');
    if(!target){ return; }
    ev.preventDefault();
    if(target.dataset.endpoint){
      select(target.dataset.endpoint, state.edge >= 0 ? state.edge : state.peek);
    }
    else if(target.dataset.openMap){ openMap(target.dataset.openMap, target); }
    else if(target.hasAttribute('data-clear')){ clearAll(); }
    else { inspectFlow(+(target.dataset.inspectEdge || target.dataset.edge)); }
  }
  panel.addEventListener('click', panelAction);
  panel.addEventListener('keydown', function(ev){
    if(ev.key === 'Enter' || ev.key === ' '){ panelAction(ev); }
  });
}
function clearAll(){
  state.focus = ''; state.journey = null; state.peek = -1; state.edge = -1;
  paint();
  if(panel){ panel.innerHTML = ''; panel.classList.remove('on'); }
  svg.dispatchEvent(new CustomEvent('systemap:clear', {bubbles:true}));
}
nodes.forEach(function(n){
  n.addEventListener('click', function(e){ e.stopPropagation(); select(n.dataset.id); });
  n.addEventListener('dblclick', function(e){
    if(opensPage(n.dataset.id)){ e.preventDefault(); openMap(n.dataset.id, n); }
  });
  n.addEventListener('keydown', function(e){
    if(e.key === 'Enter' && state.focus === n.dataset.id && opensPage(n.dataset.id)){
      e.preventDefault(); openMap(n.dataset.id, n); return;
    }
    if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); select(n.dataset.id); }
  });
});
flows.concat(labels).forEach(function(label){
  bindPreview(label, +label.dataset.edge);
  label.addEventListener('click', function(e){
    e.stopPropagation(); inspectFlow(+label.dataset.edge);
  });
  label.addEventListener('keydown', function(e){
    if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); inspectFlow(+label.dataset.edge); }
  });
});
svg.addEventListener('click', function(e){
  if(!e.target.closest('.node, .flow, .flowlbl')){ clearAll(); }
});
function setMotion(enabled){
  state.motion = !!enabled;
  if(reduced()){
    if(anim){ cancelAnimationFrame(anim); anim = 0; apply(goal); flushStill(); }
    stopReveals();
  }
  paint();
}
var motionPreference = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)');
if(motionPreference && motionPreference.addEventListener){
  motionPreference.addEventListener('change', function(){ setMotion(state.motion); });
}
svg.systemap = {
  evidenceLabel: evidenceLabel,
  select: select,
  inspectFlow: inspectFlow,
  selectEdge: inspectFlow,
  clear: clearAll,
  peek: peek,
  unpeek: unpeek,
  drawLines: drawLines,
  besideEdges: besideEdges,
  setMotion: setMotion,
  state: state,
  setLayer: function(id){
    state.layer = id; state.peek = -1;
    if(state.edge >= 0 && !edgeIn(state.edge, id)){
      select(state.focus);
      state.peek = -1;
    }
    paint();
  },
  layerIds: layerIds,
  setJourney: function(step){
    state.focus = ''; state.edge = -1; state.peek = -1;
    state.journey = step;
    paint();
    if(step){ frameJourney(step, !booted); }
    if(panel){ panel.innerHTML = ''; panel.classList.remove('on'); }
  },
  view: {
    fit: function(instant){ fit(instant); },
    actual: function(){ var c = centre(); zoomAt(1 / (base() * goal.k), c.x, c.y); },
    zoomBy: function(f){ var c = centre(); zoomAt(f, c.x, c.y); },
    zoom: function(){ return base() * goal.k; },
    isFit: function(){ return isFit(); },
    snapshot: function(){ return {k:goal.k, tx:goal.tx, ty:goal.ty}; },
    restore: function(v, instant){
      if(!v || !Number.isFinite(v.k) || v.k <= 0
        || !Number.isFinite(v.tx) || !Number.isFinite(v.ty)){ return false; }
      framed = false; saved = null; lastFrame = null;
      setView({k:v.k, tx:v.tx, ty:v.ty}, instant);
      return true;
    },
    frameFocus: frameFocus,
    frameRegion: frameRegion,
    frame: function(){ return lastFrame; },
    visibleArea: visibleArea,
    whenStill: whenStill,
    back: back
  },
  edges: EDGES,
  layers: LAYERS,
  journeys: META.journeys || [],
  detail: DETAIL
};
svg.systemapSelect = select;
svg.systemapClear = clearAll;
function openHash(){
  var id, status = document.getElementById('linkstatus');
  function report(text){if(status){status.textContent = text;}}
  try { id = decodeURIComponent((location.hash || '').slice(1)); }
  catch(_e){report('Cannot read this link. Find a component by name or use Show all.');return;}
  if(id && recordOf(id)){
    report('');if(id !== state.focus){select(id);}return;
  }
  if(!id || document.getElementById(id)){report('');return;}
  report('No component or page section has this link. Find a component by name or use Show all.');
}
window.addEventListener('hashchange', openHash);
svg.setAttribute('data-live', '');
paint();
openHash();
booted = true;
"""
