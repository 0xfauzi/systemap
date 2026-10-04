"""Exact relationship selection and the inspector, using the stored scene data."""

RELATION_JS = r"""// ---- the readings ---------------------------------------------------------
// A kind layer shows the edges of its kind and hides the rest. A derived
// reading (Structure, System context, Agents) is computed from the
// endpoints, in Python, and read from the table above; on the page the
// rest are dimmed, not hidden, and the edges shown are painted in the
// reading's own hue.
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
    var hot = chosen >= 0 ? i === chosen : !!(lit && lit.edges.indexOf(i) >= 0);
    var vis = on || hot || derived || i === state.peek;
    var m = {off:!vis, hot:hot, dim:vis && !hot && (!!f || !!j || (derived && !on)),
      peek:i === state.peek};
    setCls(p, m);
    if(labelOf[i]){
      setCls(labelOf[i], m);
      labelOf[i].setAttribute('aria-pressed', i === chosen ? 'true' : 'false');
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

// ---- the relationship wheel --------------------------------------------
function wrapName(id){
  var parts = id.match(/[A-Z]+[a-z0-9]*|[a-z0-9]+/g) || [id];
  var lines = [], cur = '';
  parts.forEach(function(p){
    if(cur && (cur + p).length > 10){ lines.push(cur); cur = p; } else { cur += p; }
  });
  if(cur){ lines.push(cur); }
  return lines;
}
function wheelLayout(cid){
  // Spokes grouped by layer in LAYERS order, clockwise from the top, with a
  // half-slot of daylight between groups. Mirrored in check_layout.py.
  var d = DETAIL[cid];
  var idx = (d.edges || []).slice();
  idx.sort(function(a, b){ return (LORD[EDGES[a].layer] - LORD[EDGES[b].layer]) || (a - b); });
  var groups = 0, prev = null;
  idx.forEach(function(i){ if(EDGES[i].layer !== prev){ groups++; prev = EDGES[i].layer; } });
  var gap = groups > 1 ? 0.5 : 0;
  var step = 360 / (idx.length + gap * groups);
  var W = 400, H = 400, cx = 200, cy = 200, R = 118;
  var hw = Math.max(34, cid.length * 3.7 + 12), hh = 15;
  var spokes = [], a = -90; prev = null;
  idx.forEach(function(i){
    var e = EDGES[i];
    if(prev !== null && e.layer !== prev){ a += gap * step; }
    prev = e.layer;
    var th = a * Math.PI / 180; a += step;
    var ux = Math.cos(th), uy = Math.sin(th);
    var r0 = Math.min(hw / Math.max(Math.abs(ux), 1e-6), hh / Math.max(Math.abs(uy), 1e-6)) + 8;
    var other = e.from === cid ? e.to : e.from;
    var deg = th * 180 / Math.PI;
    spokes.push({i:i, e:e, other:other, out:(e.from === cid), ux:ux, uy:uy, r0:r0,
      deg:deg, verb:(e.from === cid ? e.out : e['in']), colour:LCOL[e.layer],
      lines:wrapName(other)});
  });
  return {W:W, H:H, cx:cx, cy:cy, R:R, hw:hw, hh:hh, spokes:spokes};
}
function wheelExtent(w){
  // The box the wheel actually occupies: the centre, plus every name label,
  // estimated at 6.6px per glyph. The viewBox is fitted to it so a component
  // with one spoke does not sit in a square of dead space.
  var x0 = w.cx - w.hw, y0 = w.cy - w.hh, x1 = w.cx + w.hw, y1 = w.cy + w.hh;
  w.spokes.forEach(function(s){
    var ex = w.cx + (w.R + 9) * s.ux, ey = w.cy + (w.R + 9) * s.uy;
    var n = s.lines.length, lw = 0;
    s.lines.forEach(function(l){ lw = Math.max(lw, l.length * 6.6); });
    var left, top;
    if(Math.abs(s.ux) < 0.35){
      left = ex - lw / 2; top = (s.uy < 0 ? ey - 4 - (n - 1) * 13 : ey + 12) - 10;
    } else {
      left = s.ux > 0 ? ex + 2 : ex - 2 - lw; top = ey + 4 - (n - 1) * 6.5 - 10;
    }
    x0 = Math.min(x0, left); y0 = Math.min(y0, top);
    x1 = Math.max(x1, left + lw); y1 = Math.max(y1, top + n * 13);
  });
  var pad = 8;
  if(!w.spokes.length){ x0 = w.cx - 100; x1 = w.cx + 100; y0 = w.cy - 44; }
  return {x:x0 - pad, y:y0 - pad, w:x1 - x0 + 2 * pad, h:y1 - y0 + 2 * pad};
}
function wheelSvg(cid){
  var w = wheelLayout(cid);
  var box = wheelExtent(w);
  var h = '<svg viewBox="' + box.x.toFixed(1) + ' ' + box.y.toFixed(1) + ' ' + box.w.toFixed(1)
        + ' ' + box.h.toFixed(1) + '" style="max-width:' + box.w.toFixed(0) + 'px" role="group" '
        + 'aria-label="relationship wheel of ' + esc(cid) + '">';
  h += '<defs>';
  LAYERS.forEach(function(l){
    h += '<marker id="wm-' + esc(l.id) + '" viewBox="0 0 8 8" refX="7" refY="4" '
       + 'markerUnits="userSpaceOnUse" markerWidth="9" markerHeight="9" '
       + 'orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" fill="' + l.colour
       + '"/></marker>';
  });
  h += '</defs>';
  if(!w.spokes.length){
    h += '<text class="systemap-w__empty" x="' + w.cx + '" y="' + (w.cy - 30) + '">'
       + 'no flow touches this yet</text>';
  }
  w.spokes.forEach(function(s){
    var x0 = w.cx + s.r0 * s.ux, y0 = w.cy + s.r0 * s.uy;
    var x1 = w.cx + w.R * s.ux, y1 = w.cy + w.R * s.uy;
    var rm = (s.r0 + w.R) / 2, mx = w.cx + rm * s.ux, my = w.cy + rm * s.uy;
    var rot = s.ux < 0 ? s.deg + 180 : s.deg;
    var marker = (s.out ? ' marker-end' : ' marker-start') + '="url(#wm-' + esc(s.e.layer) + ')"';
    var ends = ' x1="' + x0.toFixed(1) + '" y1="' + y0.toFixed(1) + '" x2="' + x1.toFixed(1)
             + '" y2="' + y1.toFixed(1) + '"';
    h += '<g class="systemap-w__spoke" data-edge="' + s.i + '" data-go="' + esc(s.other)
       + '" tabindex="0" role="button" aria-label="'
       + esc('Inspect ' + s.e.art + ': ' + s.e.from + ' to ' + s.e.to + ', '
         + s.e.layer + ', ' + evidenceLabel(s.e.evidence)) + '" aria-pressed="'
         + (s.i === state.edge ? 'true' : 'false') + '">';
    h += '<line class="systemap-w__hit"' + ends + '/>';
    // The wheel preserves each unreviewed evidence state's pattern.
    var dash = s.e.evidence === 'declared' ? ' stroke-dasharray="6 4"' :
      s.e.evidence === 'structural' ? ' stroke-dasharray="3 4"' : '';
    h += '<line class="systemap-w__line"' + ends + ' stroke="' + s.colour + '"' + marker + dash
       + '/>';
    h += '<text class="systemap-w__verb" x="' + mx.toFixed(1) + '" y="' + (my + 4).toFixed(1)
       + '" fill="' + s.colour + '" transform="rotate(' + rot.toFixed(1) + ' ' + mx.toFixed(1)
       + ' ' + my.toFixed(1) + ')">' + esc(s.verb) + '</text>';
    var ex = w.cx + (w.R + 9) * s.ux, ey = w.cy + (w.R + 9) * s.uy;
    var n = s.lines.length, anchor, lx, first;
    if(Math.abs(s.ux) < 0.35){
      anchor = 'middle'; lx = ex;
      first = s.uy < 0 ? ey - 4 - (n - 1) * 13 : ey + 12;
    } else {
      anchor = s.ux > 0 ? 'start' : 'end'; lx = ex + (s.ux > 0 ? 2 : -2);
      first = ey + 4 - (n - 1) * 6.5;
    }
    h += '<text class="systemap-w__name" text-anchor="' + anchor + '">';
    s.lines.forEach(function(line, k){
      h += '<tspan x="' + lx.toFixed(1) + '" y="' + (first + k * 13).toFixed(1) + '">'
         + esc(line) + '</tspan>';
    });
    h += '</text></g>';
  });
  h += '<g class="systemap-w__centre"><rect x="' + (w.cx - w.hw) + '" y="' + (w.cy - w.hh)
     + '" width="' + (2 * w.hw) + '" height="' + (2 * w.hh) + '" rx="5"/>';
  h += '<text x="' + w.cx + '" y="' + (w.cy + 4) + '">' + esc(cid) + '</text></g>';
  h += '</svg>';
  return h;
}

// ---- the inspector -------------------------------------------------------
function endpointButton(id, role){
  var d = DETAIL[id];
  return '<button type="button" class="systemap-f__endpoint" data-endpoint="' + esc(id)
    + '"><small>' + role + '</small><code>' + esc(id) + '</code><span>'
    + esc(d ? d.plain : '') + '</span></button>';
}
function evidenceLabel(state){
  return state === 'observed' ? 'source reviewed' : state;
}
function evidenceReason(e){
  if(e.evidence === 'external'){
    return 'This relationship crosses the code boundary. Extracted imports cannot verify it.';
  }
  if(e.evidence === 'declared'){
    return 'This flow is authored without supporting structural evidence. Its direction and '
      + 'artifact still need source review. A judgement answer does not change the flow evidence.';
  }
  if(e.evidence === 'observed'){
    return 'Source references resolve at this snapshot, and the flow matches its recorded '
      + 'review digest. This records a source review claim. Execution has not been recorded.';
  }
  var support=[];
  if(e.import_present){support.push('An import joins the parts.');}
  if(e.shared_module){support.push('The parts share a module.');}
  if(e.mechanism){support.push('The authored flow names the configured mechanism "'
    +e.mechanism+'".');}
  return support.join(' ')+' These facts show a possible connection. Direction and artifact '
    +'still need source review.';
}
function evidenceReview(e){
  var h='',refs=e.source_refs || [],unresolved=e.unresolved_refs || [];
  if(e.claim_changed){
    h+='<p class="systemap-f__review-warning" data-claim-changed>Source review pending. '
      +'The recorded review digest is missing or does not match this flow and its explanation.</p>';
  }
  if(unresolved.length){
    h+='<div class="systemap-f__review-warning" data-unresolved-refs><p>Source review pending. '
      +'These references do not resolve at this source snapshot.</p><ul>'
      +unresolved.map(function(ref){return '<li><code>'+esc(ref)+'</code></li>';}).join('')
      +'</ul></div>';
  }
  if(refs.length){
    h+='<details class="systemap-f__refs"><summary>Cited source ('+refs.length+')</summary>'
      +'<p>A source digest identifies the source text recorded at review.</p><ul>'
      +refs.map(function(ref){return '<li><code>'+esc(ref)+'</code></li>';}).join('')+'</ul>';
    if(e.review_digest){h+='<p>Recorded flow review digest: <code>'+esc(e.review_digest)
      +'</code></p>';}
    h+='</details>';
  }
  return h;
}
function relationshipHtml(i){
  var e = EDGES[i];
  if(!e){ return '<p class="systemap-f__hint">Select a route label or a connected part '
    + 'below to inspect its exact relationship.</p>'; }
  var layer = LAYER_AT[e.layer];
  return '<h4>Selected relationship</h4><p class="systemap-f__artifact">' + esc(e.art)
    + '</p><div class="systemap-f__endpoints">' + endpointButton(e.from, 'From')
    + endpointButton(e.to, 'To') + '</div><p class="systemap-f__metadata">'
    + esc(layer ? layer.label : e.layer) + ' <span class="systemap-f__state '
    + esc(e.evidence) + '" data-evidence-state="'+esc(e.evidence)+'">'
    + esc(evidenceLabel(e.evidence)) + '</span></p>'
    + '<p class="systemap-f__say" data-say>'
    + esc(e.say || 'No authored explanation is recorded for this relationship.') + '</p>'
    + '<p class="systemap-f__evidence" data-evidence>' + esc(e.evidence_says || '') + '</p>'
    + '<p class="systemap-f__reason">' + esc(evidenceReason(e)) + '</p>' + evidenceReview(e);
}
function flowChoices(d){
  return (d.edges || []).map(function(i){
    var e = EDGES[i], layer = LAYER_AT[e.layer];
    return '<button type="button" class="systemap-f__flow-choice" data-inspect-edge="' + i
      + '" aria-pressed="' + (i === state.edge ? 'true' : 'false') + '"><b>' + esc(e.art)
      + '</b><span>' + esc(e.from) + ' to ' + esc(e.to) + '</span><small>'
      + esc(layer ? layer.label : e.layer) + ' / ' + esc(evidenceLabel(e.evidence))
      + '</small></button>';
  }).join('');
}
function partDetails(d){
  var h = '<details class="systemap-f__details"><summary>Part details</summary>'
    + '<p class="systemap-f__does">' + esc(d.does) + '</p>';
  if(d.interface){ h += '<p class="systemap-f__iface">Interface: ' + esc(d.interface) + '</p>'; }
  if(d.kind !== 'actor'){
    h += '<p class="systemap-f__entry">Entry: <b>'
      + (d.entry ? esc(d.entry) + (d.entry_module ? ' (' + esc(d.entry_module) + ')' : '')
        : 'No entry point is named for this part') + '</b></p>';
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
    + relationshipHtml(state.edge >= 0 ? state.edge : state.peek) + '</section>';
  h += '<details class="systemap-f__connections" open><summary>Connected parts</summary>'
    + '<div class="systemap-f__wheel">' + wheelSvg(d.id) + '</div>'
    + '<div class="systemap-f__flow-list">' + flowChoices(d) + '</div></details>';
  return h + partDetails(d) + '</div>';
}
function updateRelationship(){
  if(!panel){ return; }
  var section = panel.querySelector('[data-relationship]');
  if(section){ section.innerHTML = relationshipHtml(state.edge >= 0 ? state.edge : state.peek); }
  Array.prototype.slice.call(panel.querySelectorAll('.systemap-w__spoke')).forEach(function(s){
    var i = +s.dataset.edge;
    s.classList.toggle('peek', i === state.peek || i === state.edge);
    s.setAttribute('aria-pressed', i === state.edge ? 'true' : 'false');
  });
}
function peek(i){
  if(!EDGES[i]){ return; }
  state.peek = i;
  paint(); updateRelationship();
}
function unpeek(){
  state.peek = -1;
  paint(); updateRelationship();
}
function edgesBetween(a, b){
  return EDGES.map(function(e, i){
    return (e.from === a && e.to === b) || (e.from === b && e.to === a) ? i : -1;
  }).filter(function(i){ return i >= 0; });
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
  Array.prototype.slice.call(panel.querySelectorAll('.systemap-w__spoke')).forEach(function(s){
    s.addEventListener('mouseenter', function(){ peek(+s.dataset.edge); });
    s.addEventListener('focus', function(){ peek(+s.dataset.edge); });
    s.addEventListener('mouseleave', unpeek);
  });
}
function panelFocusKey(){
  var active = document.activeElement;
  if(!panel || !active || !panel.contains(active)){ return null; }
  var attributes = ['data-endpoint', 'data-inspect-edge', 'data-edge', 'data-open-map'];
  for(var i = 0; i < attributes.length; i++){
    var value = active.getAttribute(attributes[i]);
    if(value !== null){ return {attribute:attributes[i], value:value}; }
  }
  return {attribute:'', value:''};
}
function restorePanelFocus(key){
  if(!key){ return; }
  var candidates = Array.prototype.slice.call(panel.querySelectorAll(
    '[data-endpoint], [data-inspect-edge], .systemap-w__spoke, [data-open-map]'));
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
    var target = ev.target.closest('[data-endpoint], [data-inspect-edge], '
      + '.systemap-w__spoke, [data-open-map]');
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
  n.addEventListener('mouseenter', function(){
    if(!state.focus || n.dataset.id === state.focus){ return; }
    var candidates = edgesBetween(state.focus, n.dataset.id);
    if(candidates.length === 1){ peek(candidates[0]); }
  });
  n.addEventListener('mouseleave', function(){ if(state.focus){ unpeek(); } });
});
labels.forEach(function(label){
  label.addEventListener('click', function(e){
    e.stopPropagation(); inspectFlow(+label.dataset.edge);
  });
  label.addEventListener('keydown', function(e){
    if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); inspectFlow(+label.dataset.edge); }
  });
});
svg.addEventListener('click', function(e){
  if(!e.target.closest('.node, .flowlbl')){ clearAll(); }
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
  setLayer: function(id){ state.layer = id; state.peek = -1; paint(); },
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
  catch(_e){report('The part link could not be read. Find a part by name or use Fit.');return;}
  if(id && DETAIL[id] && id !== '_meta'){
    report('');if(id !== state.focus){select(id);}return;
  }
  if(!id || document.getElementById(id)){report('');return;}
  report('No part or page section matches this link. Find a part by name or use Fit.');
}
window.addEventListener('hashchange', openHash);
openHash();
booted = true;
"""
