"""An accessible reading view of the same authored parts and exact flows."""

CSS = r"""
.atlas{padding:1rem 0;min-width:0}
.fit-overview{width:36px;height:24px;vertical-align:middle;margin-right:.35rem}
@media(max-width:640px){.fit-overview{display:none}}
.atlas h2{font-size:18px;margin:.4rem 0 .8rem}.atlas h3{font-size:14px;margin:1.3rem 0 .5rem}
.atlas-intro{max-width:72ch;font-size:13px}
.reading-parts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.5rem}
.atlas-part{display:block;width:100%;text-align:left;padding:.8rem;min-width:0}
.atlas-part code{display:block;font-size:13px;font-weight:600}.atlas-part span{display:block;
font-size:13px;color:var(--ink-2);margin:.3rem 0;overflow-wrap:anywhere}
.atlas-part small{font-size:12px;color:var(--ink-2)}
.atlas-part[aria-pressed="true"]{border-color:var(--accent);background:var(--raised)}
.reading-flow{border-top:1px solid var(--line);padding:1rem 0;min-width:0}
.reading-flow h3{font-family:var(--fm);font-size:13px;margin:0 0 .4rem}
.reading-flow p{font-size:13px;max-width:72ch}.reading-meta{font-size:12px;color:var(--ink-2)}
.reading-flow[data-evidence="declared"] .reading-meta,
.reading-flow[data-evidence="structural"] .reading-meta{color:var(--warn)}
.reading-flow[aria-current="true"]{background:var(--raised)}
.reading-actions{display:flex;flex-wrap:wrap;gap:.4rem;font-size:12px}
.atlas-sequence{list-style:none;padding:0;margin:1rem 0}
.atlas-step{display:block;width:100%;text-align:left;min-height:44px;margin:.5rem 0;padding:.8rem}
.atlas-step strong{display:block;font-size:14px;font-weight:600}
.atlas-step span,.atlas-step small{display:block;font-size:13px;margin:.3rem 0;color:var(--ink-2)}
.atlas-step[aria-current="step"]{border-color:var(--accent);background:var(--raised)}
.step-finding{font-size:12px}.step-finding code{display:block;overflow-wrap:anywhere}
@media(max-width:640px){.reading-parts{grid-template-columns:minmax(0,1fr)}}
"""

SCRIPT = r"""
(function(){
  var svg=document.getElementById('schematic'),root=document.getElementById('atlas');
  if(!svg || !root || !svg.systemap){return;}
  var A=svg.systemap,X=svg.workspace,W=window.systemapWorkspace;
  var drawing=document.getElementById('spatialmap'),mapButton=document.getElementById('view-map');
  var readingButton=document.getElementById('view-reading');
  function esc(s){return String(s).replace(/[&<>"]/g,function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function layerName(id){
    var layer=A.layers.filter(function(l){return l.id===id;})[0];return layer ? layer.label : id;
  }
  function part(id){
    var d=A.detail[id];
    return '<button type="button" class="atlas-part" data-part="'+esc(id)+'" '
      +'aria-pressed="'+(A.state.focus===id)+'"><code>'+esc(id)+'</code><span>'
      +esc(d.plain || d.does)+'</span><small>'+esc(d.kind)
      +(d.note ? ' / note available in inspector' : '')
      +(d.map ? ' / contains '+esc(d.map.name) : '')+'</small></button>';
  }
  function flow(e,i){
    return '<article class="reading-flow" data-evidence="'+esc(e.evidence)+'" aria-current="'
      +(A.state.edge===i)+'"><h3>'+esc(e.from)+' to '+esc(e.to)+'</h3>'
      +'<p>'+esc(e.art)+'</p><div class="reading-meta">'+esc(layerName(e.layer))+' / '
      +esc(A.evidenceLabel(e.evidence))+'</div><p>'
      +esc(e.say || 'No explanation is authored for this flow.')
      +'</p><p class="reading-meta">'+esc(e.evidence_says)+'</p><div class="reading-actions">'
      +'<button type="button" data-flow="'+i+'">Inspect flow '+(i+1)+'</button>'
      +'<button type="button" data-flow="'+i+'" data-endpoint="'+esc(e.from)+'">Inspect '
      +esc(e.from)+'</button><button type="button" data-flow="'+i+'" data-endpoint="'
      +esc(e.to)+'">Follow to '+esc(e.to)+'</button></div></article>';
  }
  function visible(i){
    var l=A.state.layer,reading=A.detail._meta.readings[l];
    return l==='all' || !!(reading && reading.edges.indexOf(i)>=0);
  }
  function overview(){
    var h='<h2>Read the system</h2><p class="atlas-intro">The same authored parts and flows, '
      +'at text size. Inspect a flow to read its exact evidence beside the map.</p>';
    var grouped={};
    W.regions.forEach(function(r){
      h+='<section><h3>'+esc(r.label)+'</h3><div class="reading-parts">';
      r.ids.forEach(function(id){grouped[id]=true;h+=part(id);});h+='</div></section>';
    });
    var rest=Object.keys(A.detail).filter(function(id){return id!=='_meta' && !grouped[id];});
    if(rest.length){h+='<section><h3>Outside or ungrouped parts</h3><div class="reading-parts">'
      +rest.map(part).join('')+'</div></section>';}
    h+='<section><h2>Exact relationships</h2>';
    var count=0;
    A.edges.forEach(function(e,i){if(visible(i)){h+=flow(e,i);count++;}});
    return h+(count ? '' : '<p>No flows belong to this layer.</p>')+'</section>';
  }
  function stepParts(s,e){
    return (s.acts || []).concat(s.measures || [],e ? [e.from,e.to] : [])
      .filter(function(id,i,ids){return ids.indexOf(id)===i;});
  }
  function relatedFindings(ids){
    return W.review.open.filter(function(f){return f.parts.some(function(id){
      return ids.indexOf(id)>=0;});});
  }
  function operation(j,k){
    return '<h2>'+esc(j.label)+'</h2><p class="atlas-intro">An authored sequence, '
      +'not a recorded execution. '+(j.starts ? 'Starts at '+esc(j.starts)+'.' :
      'No starting entry point is named in the model.')+(j.drafted ?
      ' Written by an agent; not yet confirmed.' : '')+'</p><ol class="atlas-sequence">'
      +j.steps.map(function(s,i){
        var e=A.edges[s.edge];
        return '<li><button type="button" class="atlas-step" data-trace-step="'+i
          +'" aria-current="'+(i===k ? 'step' : 'false')+'"><strong>Step '+(i+1)+': '
          +esc(s.say)+'</strong><span>'+esc(e ? e.from+' to '+e.to+': '+e.art :
          'The authored flow was not found.')+'</span><small>Acts: '
          +esc((s.acts || []).join(', ') || 'not named')+'. Measures: '
          +esc((s.measures || []).join(', ') || 'none named')+'.</small><small>'
          +esc(e ? layerName(e.layer)+' / '+A.evidenceLabel(e.evidence)+': '+e.evidence_says :
          'No evidence recorded')+'</small></button></li>';
      }).join('')+'</ol>';
  }
  function stepEvidence(j,k){
    var s=j.steps[k],e=A.edges[s.edge],ids=stepParts(s,e),rules={};
    var h='<section class="source-section"><h3>Responsible parts</h3><div class="review-cards">';
    ids.forEach(function(id){if(!A.detail[id]){return;}
      h+='<button type="button" data-step-part="'+esc(id)+'">Inspect '+esc(id)+'</button>';
      A.detail[id].rules.forEach(function(n){rules[n]=true;});});
    h+='</div><h3>Rules to preserve</h3>';
    A.detail._meta.rules.forEach(function(r){if(rules[r.n]){
      h+='<p class="rule-row"><b>'+r.n+'</b>'+esc(r.text)+'</p>';}});
    if(!Object.keys(rules).length){h+='<p>No governing rules are authored for these parts.</p>';}
    relatedFindings(ids).forEach(function(f){h+='<details class="step-finding"><summary>'
      +esc(f.kind)+'</summary><code>'+esc(f.line)+'</code><p>'+esc(f.means)+'</p><p>'
      +esc(f.why)+'</p><p>'+esc(f.do)+'</p></details>';});
    var box=document.getElementById('step-evidence');if(box){box.innerHTML=h+'</section>';}
  }
  function render(){
    var state=X.state();
    if(state.j>=0){stepEvidence(A.journeys[state.j],state.s);}
    if(root.hidden){return;}
    var focus=document.activeElement;
    var key=focus && root.contains(focus) ?
      ['data-part','data-flow','data-endpoint','data-trace-step'].map(function(a){
        return [a,focus.getAttribute(a)];})
        .filter(function(pair){return pair[1]!==null;}) : null;
    root.innerHTML=(state.j>=0 ? operation(A.journeys[state.j],state.s) : '')+overview();
    if(key){var buttons=Array.prototype.slice.call(root.querySelectorAll('button'));
      var restored=buttons.filter(function(b){return key.every(function(pair){
        return b.getAttribute(pair[0])===pair[1];});})[0];
      if(restored){restored.focus({preventScroll:true});}}
  }
  function setView(reading){
    root.hidden=!reading;drawing.hidden=reading;
    mapButton.setAttribute('aria-pressed',String(!reading));
    readingButton.setAttribute('aria-pressed',String(reading));
    document.body.dataset.view=reading ? 'reading' : 'map';render();
    if(!reading){svg.dispatchEvent(new CustomEvent('systemap:view-resize'));}
  }
  mapButton.addEventListener('click',function(){setView(false);});
  readingButton.addEventListener('click',function(){setView(true);});
  root.addEventListener('click',function(event){
    var b=event.target.closest('button');if(!b){return;}
    if(b.hasAttribute('data-flow')){A.selectEdge(+b.dataset.flow,b.dataset.endpoint);}
    else if(b.dataset.part){X.inspect(b.dataset.part);}
    else if(b.hasAttribute('data-trace-step')){X.traceStep(+b.dataset.traceStep);}
  });
  document.getElementById('step-evidence').addEventListener('click',function(event){
    var b=event.target.closest('[data-step-part]');if(b){X.inspect(b.dataset.stepPart);}
  });
  ['systemap:select','systemap:clear','systemap:workspace','systemap:flow'].forEach(function(name){
    svg.addEventListener(name,render);});
  var vb=svg.getAttribute('viewBox').split(/\s+/).map(Number);
  document.getElementById('stage').style.setProperty('aspect-ratio',vb[2]+'/'+vb[3]);
  var fitButton=document.querySelector('[data-zoom="fit"]');
  var ns='http://www.w3.org/2000/svg',mini=document.createElementNS(ns,'svg');
  mini.setAttribute('class','fit-overview');mini.setAttribute('viewBox',vb.join(' '));
  mini.setAttribute('aria-hidden','true');
  Array.prototype.forEach.call(svg.querySelectorAll('.node__box'),function(box){
    var mark=document.createElementNS(ns,'rect');
    ['x','y','width','height'].forEach(function(a){mark.setAttribute(a,box.getAttribute(a));});
    mark.setAttribute('fill','var(--ink-3)');mini.appendChild(mark);
  });
  var windowMark=document.createElementNS(ns,'rect');
  windowMark.setAttribute('fill','none');windowMark.setAttribute('stroke','var(--accent)');
  windowMark.setAttribute('stroke-width','20');mini.appendChild(windowMark);
  fitButton.insertBefore(mini,fitButton.firstChild);
  fitButton.setAttribute('title','Part positions and the visible map area. Fit the complete map.');
  function overviewWindow(){
    if(drawing.hidden){return;}
    var area=A.view.visibleArea(null),view=A.view.snapshot();
    windowMark.setAttribute('x',(area.x-view.tx)/view.k);
    windowMark.setAttribute('y',(area.y-view.ty)/view.k);
    windowMark.setAttribute('width',area.w/view.k);
    windowMark.setAttribute('height',area.h/view.k);
  }
  svg.addEventListener('systemap:view',overviewWindow);
  window.addEventListener('resize',overviewWindow);
  window.addEventListener('scroll',overviewWindow,{passive:true});
  setView(false);
  overviewWindow();
})();
"""
