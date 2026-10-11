"""Navigation and display controls for the map page."""

SCRIPT = r"""
(function(){
  var svg=document.getElementById('schematic');
  if(!svg || !svg.workspace){return;}
  var A=svg.systemap, X=svg.workspace, pick=document.getElementById('scheme');
  var W=window.systemapWorkspace, context=document.getElementById('map-context'), previous='';
  var themeMenu=document.getElementById('theme-menu');
  function all(selector){return Array.prototype.slice.call(document.querySelectorAll(selector));}
  function esc(s){return String(s).replace(/[&<>"]/g,function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function metric(label,value){return '<div><dt>'+label+'</dt><dd>'+value+'</dd></div>';}
  function information(state,layer){
    var ids=A.layerIds(A.state.layer), edges=A.edges.filter(function(e,i){
      var reading=A.detail._meta.readings[A.state.layer];
      return A.state.layer==='all' || reading && reading.edges.indexOf(i)>=0;
    });
    var title=layer ? layer.label : 'All layers', text='', roles='';
    var step=state.j>=0 ? A.journeys[state.j].steps[state.s] : null;
    var edge=A.state.edge>=0 ? A.edges[A.state.edge]
      : !A.state.focus && step ? A.edges[step.edge] : null;
    if(A.state.focus){
      var d=A.detail[A.state.focus];ids=[d.id];edges=d.edges.map(function(i){return A.edges[i];});
      title=d.id;text=d.does;
    }else if(step){
      ids=(step.acts || []).concat(step.measures || [],edge ? [edge.from,edge.to] : []);
      title=A.journeys[state.j].label;
      roles='Acting components: '+((step.acts || []).join(', ') || 'none named')
        +'. Measurement components: '+((step.measures || []).join(', ') || 'none named')+'.';
    }
    if(edge){title=edge.from+' to '+edge.to+': '+edge.art;edges=[edge];text=edge.say;
      if(!step){ids=[edge.from,edge.to];}}
    var modules={},points={},evidence={},sequences=0;
    ids.forEach(function(id){var source=W.sources[id];if(!source){return;}
      source.modules.forEach(function(m){modules[m.id]=true;});
      source.points.forEach(function(p){points[p]=true;});});
    A.journeys.forEach(function(j){if(j.steps.some(function(s){var e=A.edges[s.edge];
      return (s.acts || []).concat(s.measures || [],e ? [e.from,e.to] : [])
        .some(function(id){return ids.indexOf(id)>=0;});})){sequences++;}});
    edges.forEach(function(e){evidence[e.evidence]=(evidence[e.evidence] || 0)+1;});
    var html='<h3>'+esc(title)+'</h3><dl>'+metric('Source modules',Object.keys(modules).length)
      +metric('Entry points',Object.keys(points).length)+metric('Flows',edges.length)
      +metric('Sequences',sequences)+'</dl>'+(text ? '<p>'+esc(text)+'</p>' : '')
      +(roles ? '<p>'+esc(roles)+'</p>' : '');
    if(edges.length){html+='<p class="context-evidence">Evidence states: '
      +Object.keys(evidence).map(function(k){return evidence[k]+' '+A.evidenceLabel(k);})
        .map(esc).join(' / ')+'.</p>';}
    if(html!==previous){
      context.innerHTML=html;previous=html;
      svg.dispatchEvent(new CustomEvent('systemap:view-resize',
        {detail:{zoom:A.view.zoom(),fit:A.view.isFit()}}));
    }
  }
  function theme(){
    var name=document.documentElement.dataset.theme;
    all('[data-scheme]').forEach(function(b){
      b.setAttribute('aria-pressed',String(b.dataset.scheme===name));
    });
  }
  all('[data-scheme]').forEach(function(b){
    b.addEventListener('click',function(){
      pick.value=b.dataset.scheme;
      pick.dispatchEvent(new Event('change',{bubbles:true}));
      themeMenu.open=false;
    });
  });
  pick.addEventListener('change',theme);
  theme();
  function sync(){
    var state=X.state();
    document.body.dataset.sequence=String(state.j>=0);
    var layer=A.layers.filter(function(l){return l.id===A.state.layer;})[0];
    document.getElementById('layer-current').textContent=layer ? layer.label : 'All layers';
    document.getElementById('review').hidden=state.mode!=='review';
    information(state,layer);
    document.getElementById('zpct').textContent=Math.round(A.view.zoom()*100)+'%';
  }
  all('button[data-mode]').forEach(function(b){
    b.addEventListener('click',function(){document.body.dataset.browse='true';});
  });
  document.getElementById('browser-close').addEventListener('click',function(){
    document.body.dataset.browse='false';
    var active=document.querySelector('.browser-tabs [aria-pressed="true"]');
    if(active){active.focus({preventScroll:true});}
  });
  all('.journey-choice,.ix').forEach(function(b){
    b.addEventListener('click',function(){document.body.dataset.browse='false';});
  });
  all('[data-layer-btn]').forEach(function(b){
    b.addEventListener('click',function(){document.querySelector('.layer-menu').open=false;});
  });
  ['systemap:workspace','systemap:select','systemap:clear','systemap:view','systemap:view-resize']
    .forEach(function(name){
    svg.addEventListener(name,sync);
  });
  sync();
})();
"""
