"""Navigation and display controls for the map page."""

SCRIPT = r"""
(function(){
  var svg=document.getElementById('schematic');
  if(!svg || !svg.workspace){return;}
  var A=svg.systemap, X=svg.workspace, pick=document.getElementById('scheme');
  var W=window.systemapWorkspace, context=document.getElementById('map-context'), previous='';
  var roleKey=document.getElementById('map-roles'), previousRoles='';
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
    roleKey.hidden=!A.state.journey || svg.dataset.plane==='flat';
    var roleHtml=step ? '<span class="acting">Acting components: '
      +esc((step.acts || []).join(', ') || 'none named')+'</span>'
      +'<span class="measurement">Measurement components: '
      +esc((step.measures || []).join(', ') || 'none named')+'</span>' : '';
    if(previousRoles!==roleHtml){roleKey.innerHTML=roleHtml;previousRoles=roleHtml;}
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

PROJECTION_SCRIPT = r"""
(function(){
  var svg=document.getElementById('schematic');
  if(!svg || !svg.systemap || !svg.dataset.flatBox){return;}
  var A=svg.systemap, W=window.systemapWorkspace;
  var scene=svg.querySelector('.projection'), unit=Math.sqrt(3)/2;
  var mix=0, frame=0, destination=0, flat=svg.dataset.flatBox.split(/\s+/).map(Number);
  var iso=svg.dataset.isoBox.split(/\s+/).map(Number);
  var texts=Array.prototype.slice.call(scene.querySelectorAll('text'));
  texts.forEach(function(t){t.dataset.sourceText=t.textContent;});
  var nodes=Array.prototype.slice.call(scene.querySelectorAll('.node'));
  var regions=(A.detail._meta.regions || []).slice(), summaries=[];
  function ungrouped(id,label,parts){
    if(!parts.length){return;}
    var actorBoxes=parts.map(function(n){var b=n.querySelector('.node__box');
      return ['x','y','width','height'].map(function(k){return +b.getAttribute(k);});});
    var left=Math.min.apply(null,actorBoxes.map(function(b){return b[0];}));
    var top=Math.min.apply(null,actorBoxes.map(function(b){return b[1];}));
    var right=Math.max.apply(null,actorBoxes.map(function(b){return b[0]+b[2];}));
    var bottom=Math.max.apply(null,actorBoxes.map(function(b){return b[1]+b[3];}));
    regions.push({id:id,label:label,box:[left,top,right-left,bottom-top],
      ids:parts.map(function(n){return n.dataset.id;})});
  }
  var grouped={};regions.forEach(function(r){r.ids.forEach(function(id){grouped[id]=true;});});
  ungrouped('_actors','External components',nodes.filter(function(n){
    return !grouped[n.dataset.id] && n.dataset.kind==='actor';}));
  ungrouped('_other','Other components',nodes.filter(function(n){
    return !grouped[n.dataset.id] && n.dataset.kind!=='actor';}));
  regions.forEach(function(r){
    var ns='http://www.w3.org/2000/svg', group=document.createElementNS(ns,'g');
    group.setAttribute('class','region-summary');group.setAttribute('role','button');
    group.setAttribute('tabindex','0');
    group.setAttribute('aria-label',r.label+', '+r.ids.length+' components');
    var box=document.createElementNS(ns,'rect'), title=document.createElementNS(ns,'text');
    var count=document.createElementNS(ns,'text'), facts=document.createElementNS(ns,'text');
    title.textContent=r.label;count.textContent=r.ids.length+' components';
    var modules={};r.ids.forEach(function(id){var source=W.sources[id];if(!source){return;}
      source.modules.forEach(function(m){modules[m.id]=true;});});
    var connections=A.edges.filter(function(e){return r.ids.indexOf(e.from)>=0
      || r.ids.indexOf(e.to)>=0;}).length;
    facts.textContent=connections+' flows / '+Object.keys(modules).length+' modules';
    group.appendChild(box);group.appendChild(title);group.appendChild(count);group.appendChild(facts);
    scene.appendChild(group);
    function open(){
      if(r.id==='_actors' || r.id==='_other'){A.view.frameGroup(r.ids);}
      else{A.view.frameRegion(r.id);}
    }
    group.addEventListener('click',function(e){e.stopPropagation();open();});
    group.addEventListener('keydown',function(e){
      if(e.key==='Enter' || e.key===' '){e.preventDefault();open();}
    });
    summaries.push({region:r,group:group,box:box,title:title,count:count,facts:facts});
  });
  function matrix(p){return [1+(unit-1)*p,p/2,-unit*p,1-p/2];}
  function reduced(){return document.documentElement.dataset.reduceMotion==='true'
    || window.matchMedia('(prefers-reduced-motion: reduce)').matches;}
  function apply(p){
    mix=p;
    var m=matrix(p), determinant=m[0]*m[3]-m[1]*m[2];
    scene.setAttribute('transform','matrix('+m.join(' ')+' 0 0)');
    svg.dataset.projection=String(unit*p);
    svg.dataset.plane=p===0 ? 'flat' : 'isometric';
    svg.setAttribute('viewBox',flat.map(function(v,k){return v+(iso[k]-v)*p;}).join(' '));
    texts.forEach(function(t){
      var x=+t.dataset.flatX+(+t.dataset.isoX-+t.dataset.flatX)*p;
      var y=+t.dataset.flatY+(+t.dataset.isoY-+t.dataset.flatY)*p;
      t.setAttribute('x','0');t.setAttribute('y','0');
      t.setAttribute('transform','translate('+x+' '+y+') matrix('
        +[m[3]/determinant,-m[1]/determinant,-m[2]/determinant,m[0]/determinant,0,0].join(' ')+')');
      t.setAttribute('style',p===0 ? t.dataset.flatStyle : t.dataset.isoStyle);
    });
  }
  function labels(){
    if(document.getElementById('spatialmap').hidden){return;}
    var scale=(scene.parentNode.getAttribute('transform') || '').match(/scale\(([^)]+)\)/);
    var screen=svg.getScreenCTM();if(!screen || !(screen.a>0)){return;}
    var zoom=screen.a*(scale ? +scale[1] : 1);
    var m=matrix(mix), det=m[0]*m[3]-m[1]*m[2];
    function place(full){
      var boxes=[];
      nodes.forEach(function(n){
        var box=n.querySelector('.node__box');
        var x=+box.getAttribute('x')+ +box.getAttribute('width')/2;
        var y=+box.getAttribute('y')+ +box.getAttribute('height')/2;
        var rise=mix*(n.classList.contains('acts') ? 18 : n.classList.contains('meas') ? 10
          : n.classList.contains('sel') ? 6 : 0)/zoom;
        n.querySelector('.node__plate').style.transform='translate('+(-rise)+'px,'+(-rise)+'px)';
        x-=rise;y-=rise;
        var names=Array.prototype.slice.call(n.querySelectorAll('[data-caption]'));
        var jobs=Array.prototype.slice.call(n.querySelectorAll('[data-description]'));
        var lines=full ? names.concat(jobs) : names;
        jobs.forEach(function(t){t.style.display=full ? '' : 'none';});
        lines.forEach(function(t,k){
          t.style.fontSize=12/zoom+'px';t.style.textAnchor='middle';
          t.setAttribute('x','0');t.setAttribute('y',String((15*(k-(lines.length-1)/2)+4)/zoom));
          t.setAttribute('transform','translate('+x+' '+y+') matrix('
            +[m[3]/det,-m[1]/det,-m[2]/det,m[0]/det,0,0].join(' ')+')');
        });
        if((A.state.focus || A.state.journey) && !n.classList.contains('dim')){
          var viewport=svg.getBoundingClientRect();
          var width=Math.max.apply(null,lines.map(function(t){
            return t.getBoundingClientRect().width;}));
          var center=lines[0].getBoundingClientRect();center=(center.left+center.right)/2;
          var shift=Math.max(viewport.left+8+width/2,
            Math.min(viewport.right-8-width/2,center))-center;
          lines.forEach(function(t){t.setAttribute('transform',t.getAttribute('transform')
            +' translate('+shift/zoom+' 0)');});
        }
        lines.forEach(function(t){boxes.push({node:n,rect:t.getBoundingClientRect()});});
      });
      return boxes;
    }
    function collide(boxes){
      return boxes.some(function(a,i){return boxes.slice(i+1).some(function(b){
        return a.node!==b.node && a.rect.left<b.rect.right && a.rect.right>b.rect.left
          && a.rect.top<b.rect.bottom && a.rect.bottom>b.rect.top;
      });});
    }
    var full=!collide(place(true)), names=!full && collide(place(false));
    var focusDetail=names && !!(A.state.focus || A.state.journey);
    function relevant(boxes){
      return boxes.filter(function(b){return !b.node.classList.contains('dim');});
    }
    if(focusDetail){full=!collide(relevant(place(true)));}
    var overview=focusDetail ? !full && collide(relevant(place(false))) : names;
    svg.classList.toggle('detail-focus',focusDetail);
    svg.dataset.detail=full ? 'functions' : 'names';
    svg.classList.toggle('overview',overview);
    summaries.forEach(function(s){
      var b=s.region.box;
      s.group.setAttribute('transform','translate('+(b[0]+b[2]/2)+' '+(b[1]+b[3]/2)+') matrix('
        +[m[3]/det,-m[1]/det,-m[2]/det,m[0]/det,0,0].join(' ')+')');
      s.title.setAttribute('style','font:500 '+12/zoom
        +'px var(--fs);fill:var(--ink);text-anchor:middle');
      s.count.setAttribute('style','font:'+12/zoom
        +'px var(--fs);fill:var(--ink-2);text-anchor:middle');
      s.facts.setAttribute('style','font:'+12/zoom
        +'px var(--fs);fill:var(--ink-2);text-anchor:middle');
      s.title.setAttribute('y',String(-12/zoom));s.count.setAttribute('y',String(5/zoom));
      s.facts.setAttribute('y',String(22/zoom));
      var width=Math.max(s.title.getBBox().width,s.count.getBBox().width,
        s.facts.getBBox().width)+24/zoom;
      s.box.setAttribute('x',String(-width/2));s.box.setAttribute('y',String(-32/zoom));
      s.box.setAttribute('width',String(width));s.box.setAttribute('height',String(64/zoom));
      s.box.setAttribute('rx',String(6/zoom));
    });
    if(overview){
      var viewport=svg.getBoundingClientRect(), placed=[];
      summaries.map(function(s){return {summary:s,rect:s.group.getBoundingClientRect()};})
        .sort(function(a,b){return a.rect.top-b.rect.top || a.rect.left-b.rect.left;})
        .forEach(function(item){
          var r=item.rect, x=Math.max(viewport.left+8,Math.min(viewport.right-8-r.width,r.left));
          var y=r.top, hits;
          do{
            hits=placed.filter(function(b){return x<b.right+6 && x+r.width>b.left-6
              && y<b.bottom+6 && y+r.height>b.top-6;});
            if(hits.length){y=Math.max.apply(null,hits.map(function(b){return b.bottom+6;}));}
          }while(hits.length);
          item.summary.group.setAttribute('transform',item.summary.group.getAttribute('transform')
            +' translate('+((x-r.left)/zoom)+' '+((y-r.top)/zoom)+')');
          placed.push({left:x,right:x+r.width,top:y,bottom:y+r.height});
        });
    }
    texts.filter(function(t){return !t.closest('.node');}).forEach(function(t){
      t.style.fontSize=12/zoom+'px';
    });
    Array.prototype.forEach.call(scene.querySelectorAll('.boundary'),function(b){
      var lines=Array.prototype.slice.call(b.querySelectorAll('text'));
      var width=+b.querySelector('rect').getAttribute('width')-26, row=0;
      lines.forEach(function(t){
        var x=+lines[0].dataset.flatX,y=+lines[0].dataset.flatY;
        var chunks=[], chunk='';
        t.dataset.sourceText.split(/\s+/).forEach(function(word){
          t.textContent=(chunk ? chunk+' ' : '')+word;
          if(chunk && t.getBBox().width>width){chunks.push(chunk);chunk=word;}
          else{chunk=t.textContent;}
        });
        if(chunk){chunks.push(chunk);}
        t.textContent='';t.setAttribute('x','0');t.setAttribute('y','0');
        chunks.forEach(function(line){
          var span=document.createElementNS('http://www.w3.org/2000/svg','tspan');
          span.setAttribute('x','0');span.setAttribute('y',String(15*row++/zoom));
          span.textContent=line+' ';t.appendChild(span);
        });
        t.setAttribute('transform','translate('+x+' '+y+') matrix('
          +[m[3]/det,-m[1]/det,-m[2]/det,m[0]/det,0,0].join(' ')+')');
      });
    });
    var obstacles=Array.prototype.slice.call(scene.querySelectorAll('.node text,.boundary text'))
      .filter(function(t){var n=t.closest('.node');
        return t.style.display!=='none' && !(focusDetail && n && n.classList.contains('dim'));})
      .map(function(t){return t.getBoundingClientRect();});
    Array.prototype.forEach.call(scene.querySelectorAll('.zone__h'),function(h){
      var lines=h.querySelectorAll('text');
      if(lines.length>1){lines[0].style.display='none';}
      var t=lines[lines.length-1];
      var x=+t.dataset.flatX+(+t.dataset.isoX-+t.dataset.flatX)*mix;
      var y=+t.dataset.flatY+(+t.dataset.isoY-+t.dataset.flatY)*mix;
      var transform='translate('+x+' '+y+') matrix('
        +[m[3]/det,-m[1]/det,-m[2]/det,m[0]/det,0,0].join(' ')+')';
      t.setAttribute('x','0');t.setAttribute('y','0');t.setAttribute('transform',transform);
      var rect=t.getBoundingClientRect(), shift=0, hits;
      do{
        hits=obstacles.filter(function(b){return rect.left<b.right+4 && rect.right>b.left-4
          && rect.top+shift<b.bottom+4 && rect.bottom+shift>b.top-4;});
        if(hits.length){
          shift=Math.min.apply(null,hits.map(function(b){return b.top-4-rect.bottom;}));
        }
      }while(hits.length);
      t.setAttribute('transform',transform+' translate(0 '+shift/zoom+')');
      obstacles.push(t.getBoundingClientRect());
    });
    Array.prototype.forEach.call(scene.querySelectorAll('.flowlbl'),function(group){
      var lines=Array.prototype.slice.call(group.querySelectorAll('text'));
      if(!lines.length){return;}
      var t=lines[0],x=+t.dataset.flatX+(+t.dataset.isoX-+t.dataset.flatX)*mix;
      var y=+t.dataset.flatY+(+t.dataset.isoY-+t.dataset.flatY)*mix;
      lines.forEach(function(line,k){
        line.setAttribute('x','0');line.setAttribute('y',String(15*k/zoom));
        line.setAttribute('transform','translate('+x+' '+y+') matrix('
          +[m[3]/det,-m[1]/det,-m[2]/det,m[0]/det,0,0].join(' ')+')');
      });
    });
    var hint=document.getElementById('map-detail');
    hint.textContent=overview ? 'Region overview. Select a region to see its components.'
      : mix===1 && A.state.journey
        ? 'Plate height shows sequence roles. Read the component names in the step data.'
      : full ? 'Select a component or flow to read its source evidence.'
        : 'Zoom to read component descriptions.';
  }
  function project(target){
    destination=target;
    if(frame){cancelAnimationFrame(frame);frame=0;}
    var start=mix, stamp=0, before=A.view.snapshot();
    var old=matrix(start), det=old[0]*old[3]-old[1]*old[2];
    var vb=svg.viewBox.baseVal, x=(vb.x+vb.width/2-before.tx)/before.k;
    var y=(vb.y+vb.height/2-before.ty)/before.k;
    var anchor=[(old[3]*x-old[2]*y)/det,(-old[1]*x+old[0]*y)/det];
    var zoom=A.view.zoom(), fitted=A.view.isFit();
    function tick(now){
      if(!stamp){stamp=now;}
      var u=reduced() ? 1 : Math.min(1,(now-stamp)/480);
      var eased=u*u*(3-2*u), p=start+(target-start)*eased;
      apply(p);
      var m=matrix(p), box=svg.viewBox.baseVal, k=zoom/svg.getScreenCTM().a;
      var pos={k:k,tx:box.x+box.width/2-k*(m[0]*anchor[0]+m[2]*anchor[1]),
        ty:box.y+box.height/2-k*(m[1]*anchor[0]+m[3]*anchor[1])};
      if(A.state.journey){A.view.frameJourney(A.state.journey,true);}
      else{A.view.restore(fitted ? {k:1,tx:0,ty:0} : pos,true,true);}
      frame=u<1 ? requestAnimationFrame(tick) : 0;
      if(u===1){
        svg.dispatchEvent(new CustomEvent('systemap:projection'));
      }
    }
    if(reduced()){tick(1);}else{frame=requestAnimationFrame(tick);}
  }
  document.getElementById('view-isometric').addEventListener('click',function(){project(1);});
  document.getElementById('view-map').addEventListener('click',function(){project(0);});
  ['systemap:view','systemap:view-resize','systemap:select','systemap:clear','systemap:workspace']
    .forEach(function(name){
    svg.addEventListener(name,labels);
  });
  window.addEventListener('resize',labels);
  var motion=document.getElementById('reduce-motion');
  motion.addEventListener('change',function(){if(frame && reduced()){project(destination);}});
  window.matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change',function(){
    if(frame && reduced()){project(destination);}
  });
  labels();
})();
"""
