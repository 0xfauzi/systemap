"""Flow selection and source records in the inspector."""

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
  var ids = {}, out = [];
  EDGES.forEach(function(e, i){ if(edgeIn(i, L)){ ids[e.from] = true; ids[e.to] = true; } });
  Object.keys(DETAIL).forEach(function(id){
    if(id !== '_meta' && (ids[id] || subjectOf(id, L))){ out.push(id); } });
  return out;
}
flows.forEach(function(p){
  p.dataset.stroke = p.getAttribute('stroke');
  p.dataset.marker = p.getAttribute('marker-end');
});
function recolour(i, colour, selected){
  var p = flowOf[i], lbl = labelOf[i];
  if(!p){ return; }
  p.setAttribute('stroke', selected ? PAL.accent : (colour || p.dataset.stroke));
  p.setAttribute('marker-end', selected ? 'url(#' + svg.id + '-m-selected)'
    : (colour ? 'url(#' + svg.id + '-m-' + state.layer + ')' : p.dataset.marker));
  var t = lbl && lbl.querySelector('text');
  if(t){ t.style.fill = selected ? PAL.accent : (colour || ''); }
}
function selectedEdge(){
  return state.edge >= 0 ? state.edge : (state.journey ? state.journey.edge : -1);
}
var trace = null, motionEdge = -1;
function syncMotion(i){
  var next = !reduced() && i >= 0 && flowOf[i] ? i : -1;
  if(next === motionEdge){ return; }
  if(trace && trace.parentNode){ trace.parentNode.removeChild(trace); }
  trace = null;
  flows.forEach(function(p){ p.classList.remove('moving'); });
  motionEdge = next;
  if(next < 0){ return; }
  var p = flowOf[next];
  if(p.hasAttribute('stroke-dasharray')){
    p.classList.add('moving');
  } else {
    trace = el('path', {'class':'flowtrace moving', 'data-edge':next,
      d:p.getAttribute('d'), 'aria-hidden':'true'});
    p.parentNode.appendChild(trace);
  }
}
function paint(){
  var f = state.focus, j = state.journey, L = state.layer, chosen = selectedEdge();
  var lit = litSet(), near = lit ? lit.ids : {}, jset = {};
  if(j){
    (j.acts || []).concat(j.measures || []).forEach(function(id){ jset[id] = true; });
  }
  var e = EDGES[chosen];
  if(e){ jset[e.from] = true; jset[e.to] = true; }
  var derived = !!(LAYER_AT[L] && LAYER_AT[L].derived) && L !== 'structure';
  var inLayer = {};
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
      setCls(labelOf[i], {off:!hot && !preview, hot:hot, dim:false, peek:preview});
      labelOf[i].setAttribute('aria-pressed', hot ? 'true' : 'false');
    }
    recolour(i, derived && on ? LCOL[L] : '', hot);
  });
  nodes.forEach(function(n){
    var id = n.dataset.id;
    var subject = L !== 'all' && L !== 'structure' && subjectOf(id, L);
    n.style.setProperty('--subject', subject ? LCOL[L] : '');
    n.setAttribute('aria-pressed', id === f ? 'true' : 'false');
    setCls(n, {sel:id === f, dim:f ? !near[id] : (j ? !jset[id] : false),
      quiet:!f && !j && L !== 'all' && !inLayer[id] && !subjectOf(id, L), subject:subject,
      endpoint:!!(e && (id === e.from || id === e.to)),
      acts:!!(j && (j.acts || []).indexOf(id) >= 0),
      meas:!!(j && (j.measures || []).indexOf(id) >= 0)});
  });
  svg.classList.toggle('focused', !!f);
  syncMotion(chosen);
}

// ---- the inspector -------------------------------------------------------
function endpointButton(id, role){
  var d = DETAIL[id];
  return '<button type="button" class="systemap-f__endpoint" data-endpoint="' + esc(id)
    + '"><small>' + role + '</small><code>' + esc(id) + '</code><span>'
    + esc(d ? d.plain : '') + '</span></button>';
}
function evidenceLabel(state){
  return state === 'observed' ? 'source review recorded' : state;
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
    return 'The source references identify this source revision. The flow agrees with its recorded '
      + 'review digest. This is a source review claim. There is no record of program execution.';
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
  return '<h4>Selected flow</h4><p class="systemap-f__artifact">' + esc(e.art)
    + '</p><div class="systemap-f__endpoints">' + endpointButton(e.from, 'From')
    + endpointButton(e.to, 'To') + '</div><p class="systemap-f__metadata">'
    + esc(layer ? layer.label : e.layer) + ' <span class="systemap-f__state '
    + esc(e.evidence) + '" data-evidence-state="'+esc(e.evidence)+'">'
    + esc(evidenceLabel(e.evidence)) + '</span></p>'
    + '<p class="systemap-f__say" data-say>'
    + esc(e.say || 'The model has no explanation for this flow.') + '</p>'
    + '<p class="systemap-f__evidence" data-evidence>' + esc(e.evidence_says || '') + '</p>'
    + '<p class="systemap-f__reason">' + esc(evidenceReason(e)) + '</p>' + evidenceReview(e);
}
function flowChoice(i){
  var e = EDGES[i];
  return '<button type="button" class="systemap-f__flow-choice" data-inspect-edge="' + i
    + '" data-evidence-state="' + esc(e.evidence) + '" aria-pressed="'
    + (i === state.edge ? 'true' : 'false') + '"><b>' + esc(e.art)
    + '</b><span>' + esc(e.from) + ' to ' + esc(e.to) + '</span><small>'
    + esc(evidenceLabel(e.evidence)) + '</small></button>';
}
function flowChoices(d){
  if(!(d.edges || []).length){ return '<p>No flow for this component</p>'; }
  return LAYERS.map(function(layer){
    var edges = (d.edges || []).filter(function(i){ return EDGES[i].layer === layer.id; });
    if(!edges.length){ return ''; }
    return '<section class="systemap-f__flow-group" data-flow-layer="' + esc(layer.id)
      + '"><h4>' + esc(layer.label) + '</h4>' + edges.map(flowChoice).join('') + '</section>';
  }).join('');
}
function partDetails(d){
  var h = '<details class="systemap-f__details"><summary>Component details</summary>'
    + '<p class="systemap-f__does">' + esc(d.does) + '</p>';
  if(d.interface){ h += '<p class="systemap-f__iface">Interface: ' + esc(d.interface) + '</p>'; }
  if(d.kind !== 'actor'){
    h += '<p class="systemap-f__entry">Entry point: <b>'
      + (d.entry ? esc(d.entry) + (d.entry_module ? ' (' + esc(d.entry_module) + ')' : '')
        : 'The component has no entry name.') + '</b></p>';
  }
  if(d.modules && d.modules.length){
    h += '<p>Claimed modules</p><ul class="systemap-f__modules">'
      + d.modules.map(function(m){ return '<li><code>' + esc(m) + '</code></li>'; }).join('')
      + '</ul>';
  }
  (d.rules || []).forEach(function(n){
    h += '<p class="systemap-f__rule"><b>' + n + '</b> ' + esc(RULES[n] || '') + '</p>';
  });
  return h + '</details>';
}
function describe(d){
  var h = '<div class="systemap-f"><h3 class="systemap-f__code">' + esc(d.id) + '</h3>'
    + '<p class="systemap-f__plain">' + esc(d.plain || '') + '</p>'
    + '<p class="systemap-f__kind">' + esc(d.kind)
    + (d.calls_model ? ', calls a model' : '') + (d.region ? ' in ' + esc(d.region) : '') + '</p>';
  if(d.note){ h += '<p class="systemap-f__note"><b>Note</b> ' + esc(d.note) + '</p>'; }
  if(d.map){
    h += '<p class="systemap-f__opens">Map inside: <b>' + esc(d.map.name)
      + (d.map.cards ? ' (' + d.map.cards + ' cards)' : '') + '</b></p>';
    if(d.map.href){
      if(d.map.preview){
        h += '<div class="systemap-f__preview" inert>' + d.map.preview + '</div>';
      }
      h += '<button type="button" class="systemap-f__open" data-open-map="' + esc(d.id)
        + '">Open map</button>';
    }
  }
  h += '<section class="systemap-f__relationship" data-relationship>'
    + relationshipHtml(state.edge) + '</section>';
  h += '<details class="systemap-f__connections" open><summary>Connected components</summary>'
    + '<div class="systemap-f__flow-list">' + flowChoices(d) + '</div></details>';
  return h + partDetails(d) + '</div>';
}
function peek(i){
  if(!EDGES[i]){ return; }
  state.peek = i;
  paint();
}
function unpeek(){
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
  var d = DETAIL[cid];
  return !!(d && d.map && d.map.href);
}
function openMap(cid, opener){
  if(!opensPage(cid)){ return; }
  var m = DETAIL[cid].map;
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
  var d = DETAIL[cid];
  if(!d || cid === '_meta'){ return; }
  var e = EDGES[edge];
  state.focus = cid; state.peek = -1;
  state.edge = e && (e.from === cid || e.to === cid) ? +edge : -1;
  paint(); frameFocus(null, !booted);
  if(panel){
    var focusKey = panelFocusKey();
    var previous = panel.querySelector('.systemap-f__connections');
    var expanded = previous ? previous.open : true;
    panel.innerHTML = describe(d); panel.classList.add('on'); bindPanel();
    var connections = panel.querySelector('.systemap-f__connections');
    if(connections){ connections.open = expanded; }
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
    var target = ev.target.closest('[data-endpoint], [data-inspect-edge], [data-open-map]');
    if(!target){ return; }
    ev.preventDefault();
    if(target.dataset.endpoint){
      select(target.dataset.endpoint, state.edge >= 0 ? state.edge : state.peek);
    }
    else if(target.dataset.openMap){ openMap(target.dataset.openMap, target); }
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
  if(reduced() && anim){ cancelAnimationFrame(anim); anim = 0; apply(goal); }
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
    fit: function(){ userView({k:1, tx:0, ty:0}); },
    actual: function(){ var c = centre(); zoomAt(1 / (base() * goal.k), c.x, c.y); },
    zoomBy: function(f){ var c = centre(); zoomAt(f, c.x, c.y); },
    zoom: function(){ return base() * goal.k; },
    isFit: function(){ return isFit(); },
    snapshot: viewSnapshot,
    restore: function(v, instant, preserve){
      if(!v || !Number.isFinite(v.k) || v.k <= 0
        || !Number.isFinite(v.tx) || !Number.isFinite(v.ty)){ return false; }
      if(!preserve){framed = false; saved = null;}
      lastFrame = null;
      setView(viewPosition(v), instant);
      return true;
    },
    frameFocus: frameFocus,
    frameJourney: frameJourney,
    frameRegion: frameRegion,
    frameGroup: function(ids){
      var box=unionBox(ids,[]);
      if(box){frameRect(box,visibleArea(null));}
    },
    frame: function(){ return lastFrame; },
    visibleArea: visibleArea,
    fracOf: fracOf,
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
  if(id && DETAIL[id] && id !== '_meta'){
    report('');if(id !== state.focus){select(id);}return;
  }
  if(!id || document.getElementById(id)){report('');return;}
  report('No component or page section has this link. Find a component by name or use Show all.');
}
window.addEventListener('hashchange', openHash);
paint();
openHash();
booted = true;
"""
