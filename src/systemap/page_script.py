"""Map selection, sequence controls and source records."""

JS = r"""
(function(){
  var svg = document.getElementById('schematic');
  if(!svg || !svg.systemap){ return; }
  var A = svg.systemap;
  var panel = document.getElementById('panel');
  var drawer = document.getElementById('drawer');
  var stage = document.getElementById('stage');
  var lstrip = document.getElementById('lstrip');
  var LAY = {};
  A.layers.forEach(function(l){ LAY[l.id] = l; });
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function all(sel, root){
    return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function reduced(){
    return document.documentElement.dataset.reduceMotion === 'true' ||
      !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  // ---- the strip above the map: the active layer and what it touches ----
  function layerStrip(){
    if(!lstrip || cur.j >= 0){ return; }
    var L = A.state.layer, h = '';
    if(L === 'all'){
      h += '<span class="lstrip__l">All layers</span>';
      h += '<span class="lstrip__q">All flows. Each flow has the color of its layer.</span>';
      h += '<span class="lstrip__row">';
      A.layers.forEach(function(l){
        h += '<button type="button" data-pick="' + esc(l.id) + '" title="' + esc(l.question)
           + '" style="border-bottom:2px solid ' + l.colour + '">' + esc(l.label) + '</button>';
      });
      h += '</span>';
    } else {
      var l = LAY[L], list = A.layerIds(L);
      // The count says what the header says: the cards that are code, then
      // the actors the reading touches, named apart.
      var actors = list.filter(function(id){ return A.detail[id].kind === 'actor'; }).length;
      var comps = list.length - actors;
      var counted = comps + ' component' + (comps === 1 ? '' : 's')
        + (actors ? ' and ' + actors + ' actor' + (actors === 1 ? '' : 's') : '');
      h += '<span class="lstrip__l" style="--c:' + l.colour + '"><i></i>' + esc(l.label)
         + ' layer</span>';
      h += '<span class="lstrip__q">' + esc(l.question) + '</span>';
      h += '<span class="lstrip__s">' + esc(l.sub) + '. ' + counted + '. Select one.</span>';
      h += '<details class="lstrip-members"><summary>Components in this layer</summary>'
         + '<span class="lstrip__row">';
      list.forEach(function(id){
        h += '<button type="button" data-go="' + esc(id) + '">' + esc(id) + '</button>'; });
      h += '</span></details>';
    }
    lstrip.innerHTML = h;
    all('[data-go]', lstrip).forEach(function(b){
      b.addEventListener('click', function(){ A.select(b.dataset.go); });
    });
    all('[data-pick]', lstrip).forEach(function(b){
      b.addEventListener('click', function(){ setLayer(b.dataset.pick); });
    });
  }

  // ---- layer switch -----------------------------------------------------
  var layerBtns = all('[data-layer-btn]');
  var layerSelect = document.getElementById('layer-select');
  function setLayer(id){
    A.setLayer(id);
    layerBtns.forEach(function(b){
      b.setAttribute('aria-pressed', b.dataset.layerBtn === id ? 'true' : 'false'); });
    if(layerSelect){ layerSelect.value = id; }
    layerStrip();
    if(A.state.focus){ frameBeside(A.state.focus); }
    svg.dispatchEvent(new CustomEvent('systemap:workspace'));
  }
  layerBtns.forEach(function(b){
    b.addEventListener('click', function(){ setLayer(b.dataset.layerBtn); }); });
  if(layerSelect){ layerSelect.addEventListener('change', function(){
    setLayer(layerSelect.value);
  }); }

  // ---- the drawer: opens on selection, docks away from the node ---------
  function cover(){
    // What the drawer lays over the map: its box and its side, or nothing
    // when it is hidden or sits below the map (the narrow layout).
    if(!drawer || drawer.hidden){ return null; }
    var d = drawer.getBoundingClientRect(), s = svg.getBoundingClientRect();
    if(d.right <= s.left || d.left >= s.right || d.bottom <= s.top || d.top >= s.bottom){
      return null;
    }
    return {rect:d, side:drawer.dataset.dock};
  }
  var frameVersion = 0, restoringView = false;
  function frameBeside(id, instant){
    // Frame the selected components after the inspector layout.
    var version = frameVersion;
    window.requestAnimationFrame(function(){
      if(A.state.focus === id && version === frameVersion){ A.view.frameFocus(cover(), instant); }
    });
  }
  function openDrawer(id, instant){
    // The figure has already framed the lit set in the visible map; the
    // card's position in that view picks the side. The drawer then covers
    // that side, so the lit set is framed again into the part it leaves.
    if(!drawer){ return; }
    frameVersion++;
    drawer.dataset.dock = A.view.fracOf(id) > 0.6 ? 'left' : 'right';
    drawer.hidden = false;
    if(empty){ empty.hidden = true; }
    reveal();
    if(!restoringView){ frameBeside(id, instant); }
  }
  function closeDrawer(){ frameVersion++; if(drawer){ drawer.hidden = true; } visibility(); }
  function reveal(){
    if(document.body.dataset.view === 'reading' && window.innerWidth <= 1050 && drawer){
      drawer.scrollIntoView({block:'start'});
      var heading = panel.querySelector('h3');
      if(heading){heading.setAttribute('tabindex','-1');heading.focus({preventScroll:true});}
      return;
    }
    // The page scrolls so the map is on screen; the map itself has moved.
    if(!stage){ return; }
    var s = stage.getBoundingClientRect();
    if(s.top < 0 || s.top > window.innerHeight - 200){
      document.getElementById('map').scrollIntoView({block:'start'});
    }
  }
  var closeBtn = document.getElementById('drawerclose');
  if(closeBtn){ closeBtn.addEventListener('click', function(){
    if(cur.j >= 0){ backToJourney(); } else { A.clear(); }
  }); }

  // ---- zoom: Fit and 100% are the named states; + and - step by 1.25 ----
  var zoomBtns = all('[data-zoom]'), zpct = document.getElementById('zpct');
  zoomBtns.forEach(function(b){
    b.addEventListener('click', function(){
      var z = b.dataset.zoom;
      if(z === 'fit'){ A.view.fit(); }
      else if(z === 'actual'){ A.view.actual(); }
      else { A.view.zoomBy(z === 'in' ? 1.25 : 1 / 1.25); }
    });
  });
  function showZoom(zoom, fit){
    zoomBtns.forEach(function(b){
      if(b.dataset.zoom === 'fit'){ b.setAttribute('aria-pressed', fit ? 'true' : 'false'); }
      if(b.dataset.zoom === 'actual'){
        b.setAttribute('aria-pressed', Math.abs(zoom - 1) < 0.01 ? 'true' : 'false'); }
    });
    if(zpct){ zpct.textContent = Math.round(zoom * 100) + '%'; }
  }
  svg.addEventListener('systemap:view', function(e){ showZoom(e.detail.zoom, e.detail.fit); });

  // ---- journeys ---------------------------------------------------------
  var sel = document.getElementById('journey');
  var prev = document.getElementById('jprev'), next = document.getElementById('jnext');
  var count = document.getElementById('jcount');
  var strip = document.getElementById('strip');
  var stripN = document.getElementById('stripn'), stripSay = document.getElementById('stripsay');
  var stripMeas = document.getElementById('stripmeas');
  var stripFoot = document.getElementById('stripfoot');
  var cur = {j:-1, s:0};
  var beforeJourney = null, journeyView = null;
  var returnBtn = document.getElementById('jreturn'), endBtn = document.getElementById('jend');
  function mapState(){
    return {focus:A.state.focus, edge:A.state.edge, layer:A.state.layer,
      view:A.view.snapshot(), mode:mode};
  }
  function restoreMap(saved){
    restoringView = true;
    A.setJourney(null);
    if(saved){
      setLayer(saved.layer);
      if(saved.focus){ A.select(saved.focus, saved.edge); } else { A.clear(); }
      A.view.restore(saved.view, true);
    } else { A.clear(); }
    restoringView = false;
  }
  function journeyStrip(j){
    // The strip during a journey: every step as the edge it traces, the
    // current one lit, each one a jump. The sentence lives under the map.
    if(!lstrip){ return; }
    var h = '<span class="lstrip__l" style="--c:var(--accent)"><i></i>sequence</span>'
          + '<span class="lstrip__q">' + esc(j.label) + '</span><span class="lstrip__row">';
    j.steps.forEach(function(s, k){
      var e = A.edges[s.edge] || {from:'', to:'', art:''};
      h += '<button type="button" class="' + (k === cur.s ? 'on' : '') + '" data-step="' + k
         + '" title="' + esc(e.art) + '"><b>' + (k + 1) + '</b>' + esc(e.from) + '<i>to</i>'
         + esc(e.to) + '</button>';
    });
    lstrip.innerHTML = h + '</span>';
    all('[data-step]', lstrip).forEach(function(b){
      b.addEventListener('click', function(){ cur.s = +b.dataset.step; showStep(); });
    });
  }
  function footOf(j, step){
    // Where the walk begins, what backs the step the reader is on, and a
    // word when an agent wrote the walk and nobody has confirmed it.
    var parts = [];
    if(j.starts){ parts.push('starts at <b>' + esc(j.starts) + '</b>'); }
    var e = A.edges[step.edge];
    if(e && e.evidence_says){ parts.push(esc(e.evidence_says)); }
    if(j.drafted){
      parts.push('<span class="draft">Agent draft. Source review necessary.</span>');
    }
    return parts.join(' &middot; ');
  }
  function showStep(){
    var j = A.journeys[cur.j];
    if(!j){ return; }
    var step = j.steps[cur.s];
    A.setJourney(null); closeDrawer();
    var edge = A.edges[step.edge];
    if(edge){ setLayer(edge.layer); }
    journeyStrip(j);
    if(strip){
      strip.hidden = false;
      stripN.textContent = (cur.s + 1) + ' / ' + j.steps.length;
      stripSay.textContent = step.say;
      var m = step.measures || [];
      stripMeas.textContent = m.length ? 'Measurement components: ' + m.join(', ')
        : 'No measurement component for this step';
      stripMeas.classList.toggle('none', !m.length);
      stripFoot.innerHTML = footOf(j, step);
    }
    visibility();
    svg.dispatchEvent(new CustomEvent('systemap:workspace'));
    all('[data-journey]').forEach(function(b){
      b.setAttribute('aria-pressed', +b.dataset.journey === cur.j ? 'true' : 'false');
    });
    if(count){ count.textContent = (cur.s + 1) + '/' + j.steps.length; }
    if(prev){ prev.disabled = cur.s === 0; }
    if(next){ next.disabled = cur.s >= j.steps.length - 1; }
    // Frame after the controls and inspector have their final layout.
    A.setJourney(step);
    journeyView = {layer:A.state.layer, view:A.view.snapshot()};
  }
  function backToJourney(){
    if(cur.j < 0){ return; }
    var saved = journeyView;
    showStep();
    if(saved){ setLayer(saved.layer); A.view.restore(saved.view, true); journeyView = saved; }
  }
  function endJourney(restoreMode){
    var saved = beforeJourney;
    cur.j = -1; cur.s = 0;
    beforeJourney = null; journeyView = null;
    if(strip){ strip.hidden = true; }
    if(count){ count.textContent = ''; }
    if(prev){ prev.disabled = true; }
    if(next){ next.disabled = true; }
    if(sel){ sel.value = ''; }
    all('[data-journey]').forEach(function(b){ b.setAttribute('aria-pressed', 'false'); });
    restoreMap(saved);
    if(saved && restoreMode !== false){ setMode(saved.mode); }
    layerStrip(); visibility();
    svg.dispatchEvent(new CustomEvent('systemap:workspace'));
  }
  function startJourney(k){
    if(!A.journeys[k] || !A.journeys[k].steps.length){ return; }
    if(cur.j < 0){ beforeJourney = mapState(); }
    setMode('trace');
    cur.j = k; cur.s = 0;
    if(sel){ sel.value = String(k); }
    var question = document.getElementById('activity-question');
    var map = document.getElementById('map');
    if(question){ question.textContent = A.journeys[k].label; }
    if(map){ map.scrollIntoView({block:'start'}); }
    showStep();
  }
  if(sel){ sel.addEventListener('change', function(){
    if(sel.value === ''){ endJourney(); }
    else { startJourney(+sel.value); }
  }); }
  function stepBy(d){
    var j = A.journeys[cur.j];
    if(!j){ return false; }
    var s = cur.s + d;
    if(s < 0 || s >= j.steps.length){ return true; }
    cur.s = s; showStep();
    return true;
  }
  if(prev){ prev.addEventListener('click', function(){ stepBy(-1); }); }
  if(next){ next.addEventListener('click', function(){ stepBy(1); }); }

  // ---- the map inside a card, in place -----------------------------------
  // The figure says which card to open (its button in the panel, a
  // double-click on the card, Enter on it a second time); the page lays the
  // sub-map's page over itself in a frame, under a breadcrumb, and hands
  // the focus back to the card when the overlay closes.
  var submap = document.getElementById('submap');
  var submapFrame = document.getElementById('submapframe');
  var submapCrumb = document.getElementById('submapcrumb');
  var submapClose = document.getElementById('submapclose');
  var submapOpener = null;
  var inertBefore = [];
  function holdBackground(){
    var child = submap, parent = child.parentNode;
    while(parent && child !== document.body){
      Array.prototype.slice.call(parent.children).forEach(function(n){
        if(n === child || n.tagName === 'SCRIPT' || n.tagName === 'STYLE'){ return; }
        inertBefore.push({node:n, inert:n.hasAttribute('inert')});
        n.setAttribute('inert', '');
      });
      child = parent; parent = parent.parentNode;
    }
  }
  function openSubmap(e){
    var d = e.detail || {};
    if(!submap || !d.href || !submap.hidden){ return; }
    submapOpener = d.opener || document.activeElement || nodeOf(d.id);
    submapCrumb.textContent = (submap.dataset.here || '') + ' > ' + d.id
      + (d.name !== d.id ? ' > ' + d.name : '');
    submapFrame.title = d.name + ' inside ' + d.id;
    if(submapFrame.getAttribute('src') !== d.href){ submapFrame.setAttribute('src', d.href); }
    submap.hidden = false;
    holdBackground();
    document.body.classList.add('submap-open');
    submapClose.focus();
  }
  function closeSubmap(){
    if(!submap || submap.hidden){ return false; }
    submap.hidden = true;
    submapFrame.setAttribute('src', 'about:blank');
    document.body.classList.remove('submap-open');
    inertBefore.forEach(function(saved){
      if(!saved.inert){ saved.node.removeAttribute('inert'); }
    });
    inertBefore = [];
    if(submapOpener && submapOpener.isConnected !== false){
      submapOpener.focus({preventScroll:true});
    }
    submapOpener = null;
    return true;
  }
  svg.addEventListener('systemap:open', openSubmap);
  if(submapClose){ submapClose.addEventListener('click', closeSubmap); }

  // ---- the scheme -------------------------------------------------------
  // The head script stamped the root before the first paint; the picker
  // shows that, and a change restamps the root, keeps the pick in this
  // browser when it can, and follows into the map inside a card.
  var pick = document.getElementById('scheme');
  function scheme(){ return document.documentElement.getAttribute('data-theme') || ''; }
  function stampFrame(){
    try {
      var d = submapFrame && submapFrame.contentDocument;
      if(d && d.documentElement){
        d.documentElement.setAttribute('data-theme', scheme());
        d.documentElement.dataset.reduceMotion = String(reduced());
      }
    } catch(e){}
  }
  function setScheme(name){
    document.documentElement.setAttribute('data-theme', name);
    if(pick){ pick.value = name; }
    try { localStorage.setItem('systemap-theme', name); } catch(e){}
    stampFrame();
  }
  if(pick){
    pick.value = scheme() || pick.value;
    pick.addEventListener('change', function(){ setScheme(pick.value); });
  }
  if(submapFrame){ submapFrame.addEventListener('load', stampFrame); }

  // The native preference always wins. The page control can also stop motion.
  var motionPick = document.getElementById('reduce-motion');
  var motionMedia = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)');
  var motionOff = false;
  try { motionOff = localStorage.getItem('systemap-reduce-motion') === 'true'; } catch(e){}
  function motionPreference(){
    var nativeOff = !!(motionMedia && motionMedia.matches), off = nativeOff || motionOff;
    document.documentElement.dataset.reduceMotion = String(off);
    if(motionPick){ motionPick.checked = off; motionPick.disabled = nativeOff; }
    A.setMotion(!off); stampFrame();
  }
  if(motionPick){ motionPick.addEventListener('change', function(){
    motionOff = motionPick.checked;
    try { localStorage.setItem('systemap-reduce-motion', String(motionOff)); } catch(e){}
    motionPreference();
  }); }
  if(motionMedia && motionMedia.addEventListener){
    motionMedia.addEventListener('change', motionPreference);
  }
  motionPreference();

  // ---- keyboard ---------------------------------------------------------
  // The page from the keyboard: Tab moves across the cards in reading
  // order (they are written in that order and each takes focus), Enter on
  // a card opens its panel, Escape closes it and clears the selection, the
  // left and right arrows switch layers, or step the journey while one
  // is on. A control that takes arrows itself (the journey select) keeps
  // them.
  function stepLayer(d){
    var ids = layerBtns.map(function(b){ return b.dataset.layerBtn; });
    if(!ids.length){ return; }
    var i = ids.indexOf(A.state.layer);
    setLayer(ids[(i + d + ids.length) % ids.length]);
  }
  document.addEventListener('keydown', function(e){
    var t = e.target, tag = t && t.tagName;
    if(e.key === 'Escape'){
      // The map inside a card closes first, and the selection under it stays.
      if(closeSubmap()){ e.preventDefault(); return; }
    }
    if(submap && !submap.hidden){ return; }
    if(tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA' ||
      (t && t.isContentEditable) || (t && t.closest && t.closest('[role="textbox"]'))){ return; }
    if((e.key === '/' && !e.altKey && !e.ctrlKey && !e.metaKey) ||
      (e.key.toLowerCase() === 'k' && (e.ctrlKey || e.metaKey) && !e.altKey)){
      var search = document.getElementById('partsearch');
      if(search){
        var section = document.getElementById('components');
        if(section){ section.hidden = false; }
        var details = search.closest('details');
        if(details){ details.open = true; }
        search.focus(); e.preventDefault();
      }
      return;
    }
    if(e.altKey || e.ctrlKey || e.metaKey){ return; }
    if(e.key === 'Escape'){
      if(cur.j >= 0){ endJourney(); e.preventDefault(); return; }
      A.clear();
      A.view.back();
      e.preventDefault();
    } else if(e.key === 'ArrowRight' || e.key === 'ArrowLeft'){
      var d = e.key === 'ArrowRight' ? 1 : -1;
      if(cur.j >= 0){ if(stepBy(d)){ e.preventDefault(); } }
      else { stepLayer(d); e.preventDefault(); }
    }
  });

  svg.addEventListener('systemap:flow', function(e){ setLayer(A.edges[e.detail.edge].layer); });
  var opened = '';
  svg.addEventListener('systemap:select', function(e){
    var id = e.detail.id;
    opened = id;
    openDrawer(id);
    if(location.hash !== '#' + id){ history.replaceState(null, '', '#' + id); }
  });
  svg.addEventListener('systemap:clear', function(){
    closeDrawer();
    if(location.hash){ history.replaceState(null, '', location.pathname + location.search); }
    // Focus that was in the drawer, or nowhere, goes back to the card the
    // drawer was about, so the keyboard reader is where they left off.
    var active = document.activeElement, node = opened && nodeOf(opened);
    opened = '';
    if(node && (!active || active === document.body || active.isConnected === false
        || (drawer && drawer.contains(active)))){
      node.focus({preventScroll:true});
    }
    if(cur.j >= 0 && !A.state.journey){ backToJourney(); }
  });
  function nodeOf(id){
    return all('.node', svg).filter(function(n){ return n.dataset.id === id; })[0] || null;
  }
  all('.ix[data-go], .gv[data-go]').forEach(function(b){
    b.addEventListener('click', function(){
      A.select(b.dataset.go);
      document.getElementById('map').scrollIntoView({
        behavior:reduced() ? 'auto' : 'smooth', block:'start'});
    });
  });
  window.addEventListener('resize', function(){
    showZoom(A.view.zoom(), A.view.isFit());
    // A held focus is framed again for the new window, in place.
    if(A.state.focus && drawer && !drawer.hidden){ frameBeside(A.state.focus, true); }
  });

  // Reference sections and the inspector share the same map state.
  var W = window.systemapWorkspace;
  var mode = 'understand', reviewFilter = 'open', reviewPick = -1;
  var empty = document.getElementById('inspector-empty');
  var sourceDetail = document.getElementById('source-detail');
  var reviewDetail = document.getElementById('review-detail');
  function visibility(){
    if(empty){ empty.hidden = !!A.state.focus || cur.j >= 0 || mode === 'review'; }
    if(reviewDetail){ reviewDetail.hidden = mode !== 'review'; }
    if(strip){ strip.hidden = cur.j < 0; }
    if(returnBtn){ returnBtn.hidden = cur.j < 0 || !A.state.focus; }
    if(endBtn){ endBtn.hidden = cur.j < 0; }
  }
  function setMode(name){
    mode = name;
    document.body.dataset.mode = name;
    all('button[data-mode]').forEach(function(b){
      b.setAttribute('aria-pressed', b.dataset.mode === name ? 'true' : 'false');
    });
    [['components','understand'],['journeyindex','trace'],['reviewindex','review']]
      .forEach(function(pair){
        var section = document.getElementById(pair[0]);
        if(section){ section.hidden = name !== pair[1]; }
      });
    var label = document.getElementById('activity-label');
    if(label){ label.textContent = {
      understand:'System components', trace:'Operation sequence', review:'Examine a change'
    }[name]; }
    var question = document.getElementById('activity-question');
    if(question){ question.textContent = {
      understand:'What are the components and their connections?',
      trace:'What are the operation steps?', review:'What changed at this revision?'
    }[name]; }
    if(name === 'review'){ renderReview(); }
    document.getElementById('change') &&
      (document.getElementById('change').hidden = name !== 'review');
    visibility();
    svg.dispatchEvent(new CustomEvent('systemap:workspace'));
  }
  all('button[data-mode]').forEach(function(b){
    b.addEventListener('click', function(){ setMode(b.dataset.mode); });
  });
  all('.header-links a').forEach(function(a){
    a.addEventListener('click', function(){
      if(a.getAttribute('href') === '#components'){ setMode('understand'); }
      if(a.getAttribute('href') === '#invariants'){
        document.getElementById('invariants').setAttribute('open','');
      }
      if(a.getAttribute('href') === '#review'){ setMode('review'); }
    });
  });
  function bindJourneys(root){
    all('[data-journey]', root).forEach(function(b){
      b.addEventListener('click', function(){
        startJourney(+b.dataset.journey);
      });
    });
  }
  bindJourneys(document.getElementById('journeyindex'));
  if(endBtn){ endBtn.addEventListener('click', function(){ endJourney(); }); }
  if(returnBtn){ returnBtn.addEventListener('click', backToJourney); }
  var reset = document.getElementById('resetmap');
  if(reset){ reset.addEventListener('click', function(){ A.view.fit(); }); }
  function searchParts(){
    var search = document.getElementById('partsearch');
    if(!search){ return; }
    var q = search.value.trim().toLowerCase();
    var found = 0, entries = all('.ix[data-go]');
    entries.forEach(function(b){
      var d = A.detail[b.dataset.go], s = W && W.sources[b.dataset.go];
      var fields = [['Component name',d.id],['Function',d.does],['Function',d.plain || '']];
      if(s){
        s.claims.forEach(function(m){ fields.push(['Claimed module',m]); });
        s.modules.forEach(function(m){ fields.push(['Module',m.id],['Source path',m.file]); });
      }
      var matches = fields.filter(function(field){
        return String(field[1] || '').toLowerCase().indexOf(q) >= 0;
      });
      b.hidden = !matches.length;
      var explanation = b.querySelector('.ix__match');
      if(!explanation){
        explanation = document.createElement('small');
        explanation.setAttribute('class', 'ix__match'); b.appendChild(explanation);
      }
      explanation.hidden = !q;
      explanation.textContent = q && matches.length ? matches[0].join(': ') : '';
      if(!b.hidden){ found++; }
    });
    all('.ixgroup').forEach(function(g){
      g.hidden = all('.ix', g).every(function(b){ return b.hidden; });
    });
    var disclosure = document.getElementById('partlist-disclosure');
    if(disclosure && q){ disclosure.open = true; }
    var status = document.getElementById('searchcount');
    if(status){ status.textContent = found + ' of ' + entries.length + ' components'; }
    var emptySearch = document.getElementById('searchempty');
    if(emptySearch){ emptySearch.hidden = found !== 0; }
  }
  var partSearch = document.getElementById('partsearch');
  if(partSearch){ partSearch.addEventListener('input', searchParts); }
  searchParts();
  function moduleRecords(s){
    return s.modules.map(function(m){
      var surface = (m.public_names || []).map(function(n){
        return n.name + ' (' + n.kind + ')'
          + (n.reexport_of ? ', re-exported from ' + n.reexport_of : '');
      });
      var unknown = (m.unknown || []).map(function(problem){
        var text = typeof problem === 'string' ? problem
          : (problem.line ? 'Line ' + problem.line + ', column ' + problem.column + ': ' : '')
            + (problem.reason || 'The fact could not be read.');
        return '<p class="source-unknown">Unknown fact: ' + esc(text) + '</p>';
      }).join('');
      return '<details class="module-record"><summary>' + esc(m.id) + '</summary>'
        + '<p class="file">' + esc(m.file || 'Source path not recorded') + '</p><p>'
        + esc(m.docstring || 'No module description was recorded.') + '</p>'
        + '<p>Public names in this module: '
        + esc((surface.length ? surface : m.names).join(', ') || 'none recorded') + '</p>'
        + '<p>Imports: ' + esc(m.imports.join(', ') || 'none recorded') + '</p>'
        + '<p>Imported by: ' + esc((m.imported_by || []).join(', ') || 'none recorded') + '</p>'
        + '<p>External imports: ' + esc((m.external || []).join(', ') || 'none recorded') + '</p>'
        + unknown
        + '<p>Tests with imports of this module: '
        + esc(m.tests.join(', ') || 'none recorded') + '. References do not prove coverage.</p>'
        + '</details>';
    }).join('') || '<p>The source data has no modules for this component card.</p>';
  }
  function sourceRows(id){
    if(!sourceDetail || !W){ return; }
    var d = A.detail[id], s = W.sources[id], h = '';
    h += '<section class="source-section"><h3>Rules for this component</h3>';
    (d.rules || []).forEach(function(n){
      var r = A.detail._meta.rules.filter(function(r){ return r.n === n; })[0];
      h += '<div class="rule-row"><b>' + n + '</b>'
         + esc(r ? r.text : 'Rule not recorded') + '</div>';
    });
    h += d.rules.length ? '' : '<p>The model has no rules for this component.</p>';
    h += '</section><section class="source-section"><h3>Sequences with this component</h3>';
    var count = 0;
    A.journeys.forEach(function(j, k){
      var touches = j.steps.some(function(step){
        var e = A.edges[step.edge];
        return (e && (e.from === id || e.to === id)) ||
          step.acts.indexOf(id) >= 0 || step.measures.indexOf(id) >= 0;
      });
      if(touches){ count++; h += '<button type="button" class="journey-choice" data-journey="'
        + k + '">' + esc(j.label) + '<small>' + esc(j.starts || 'Entry label not supplied')
         + '</small></button>'; }
    });
    h += count ? '' : '<p>The model has no sequence with this component.</p>';
    if(d.kind !== 'actor'){
      h += '</section><section class="source-section"><h3>Source evidence</h3>'
        + (s.unresolved_claims || []).map(function(claim){
          return '<p class="source-unknown">The source data has no source for this module claim: '
            + '<code>' + esc(claim) + '</code>.</p>';
        }).join('')
        + '<details class="source-records"><summary>Source records</summary>'
        + '<p>Module claims in the model: <code>'
        + esc(s.claims.join(', ') || 'none') + '</code>.</p>'
        + (s.symbol_claims || []).map(function(claim){
          return '<p>Public name in the model: <code>' + esc(claim.module + ':' + claim.name)
            + '</code>.</p>';
        }).join('')
        + moduleRecords(s);
      h += '<h3>Entry points</h3><p>An entry point is where a program can start.</p>';
      h += s.points.map(function(p){ return '<p><code>' + esc(p) + '</code></p>'; }).join('')
        || '<p>No entry points were extracted for these modules.</p>';
      h += '</details>';
    }
    sourceDetail.innerHTML = h + '</section>';
    all('[data-neighbour]', sourceDetail).forEach(function(b){
      b.addEventListener('mouseenter', function(){ A.peek(+b.dataset.flow); });
      b.addEventListener('focus', function(){ A.peek(+b.dataset.flow); });
      b.addEventListener('click', function(){ A.select(b.dataset.neighbour); });
    });
    bindJourneys(sourceDetail);
  }
  function reviewCards(line){
    return Object.keys(W.sources).filter(function(id){
      // Match identifiers as tokens, including hyphenated or dotted card names.
      var safe = id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      return new RegExp('(^|[^A-Za-z0-9_.-])' + safe + '($|[^A-Za-z0-9_.-])').test(line);
    });
  }
  function pickReview(k){
    reviewPick = k;
    var item = W.review[reviewFilter][k];
    if(!item){ return; }
    var label = reviewFilter === 'open' ? 'Decision to make' : 'Recorded decision';
    var h = '<p>' + esc(label)
      + '</p><h2>' + esc(item.kind) + '</h2><div class="review-line">'
         + esc(item.line) + '</div>'
      + '<p>' + esc(item.means) + '</p><p>' + esc(item.why) + '</p>';
    if(item.reasons.length){
      h += '<h3>Answer explanation</h3>' + item.reasons.map(function(r){
        return '<p class="review-reason">' + esc(r) + '</p>';
      }).join('');
    } else { h += '<h3>What to do</h3><p>' + esc(item.do) + '</p>'; }
    h += '<div class="review-cards">' + reviewCards(item.line).map(function(id){
      return '<button type="button" data-inspect="' + esc(id) + '">Examine ' + esc(id)
         + '</button>';
    }).join('') + '</div><p>Keep the finding text unchanged when you record an answer in '
      + '<code>[judgement] answered</code>. Run <code>systemap judgement</code> against the '
      + 'working tree before you make a decision.</p>';
    reviewDetail.innerHTML = h;
    all('[data-inspect]', reviewDetail).forEach(function(b){
      b.addEventListener('click', function(){ A.select(b.dataset.inspect); });
    });
    all('[data-review-item]').forEach(function(b){
      b.setAttribute('aria-pressed', +b.dataset.reviewItem === k ? 'true' : 'false');
    });
  }
  function renderReview(){
    if(!W){ return; }
    var items = W.review[reviewFilter];
    document.getElementById('reviewlist').innerHTML = items.map(function(item, k){
      return '<button type="button" class="review-choice" data-review-item="' + k
        + '" aria-pressed="false">' + esc(item.kind) + '<small>' + esc(item.line)
         + '</small></button>';
    }).join('') || '<p>' + (reviewFilter === 'open' ? 'This map has no findings without answers. '
      + 'A person must still examine the map claims.'
      : 'These findings have no applicable stored answers.') + '</p>';
    all('[data-review-item]').forEach(function(b){
      b.addEventListener('click', function(){
        A.clear(); pickReview(+b.dataset.reviewItem); visibility();
      });
    });
    reviewDetail.innerHTML = '<h2>Read the decisions.</h2>'
      + '<p>Select a finding to read its explanation and the necessary action. '
      + 'Answered findings contain the recorded explanation. Jev audits and checks of the working '
      + 'tree are separate commands.</p>';
    if(items.length){ pickReview(Math.max(0, Math.min(reviewPick, items.length - 1))); }
  }
  all('[data-review-filter]').forEach(function(b){
    b.addEventListener('click', function(){
      reviewFilter = b.dataset.reviewFilter; reviewPick = -1;
      all('[data-review-filter]').forEach(function(x){
        x.setAttribute('aria-pressed', x.dataset.reviewFilter === reviewFilter ? 'true' : 'false');
      });
      A.clear(); renderReview(); visibility();
    });
  });
  all('[data-copy]').forEach(function(b){
    b.addEventListener('click', function(){
      var status = document.getElementById('copystatus');
      if(!navigator.clipboard || !navigator.clipboard.writeText){
        status.textContent = 'No clipboard access. Select and copy the command text.'; return;
      }
      navigator.clipboard.writeText(b.dataset.copy).then(function(){
        status.textContent = 'Copied: ' + b.dataset.copy;
      }, function(){ status.textContent = 'Copy failed. Select and copy the command text.'; });
    });
  });
  svg.addEventListener('systemap:select', function(e){
    document.getElementById('linkstatus').textContent = '';
    sourceRows(e.detail.id); visibility();
    all('.ix[data-go]').forEach(function(b){
      b.setAttribute('aria-current', b.dataset.go === e.detail.id ? 'true' : 'false');
    });
  });
  svg.addEventListener('systemap:clear', function(){
    if(sourceDetail){ sourceDetail.innerHTML = ''; }
    visibility();
    all('.ix[data-go]').forEach(function(b){ b.removeAttribute('aria-current'); });
  });

  function comparisonRows(id){
    var comparison = W.comparison, record = comparison.parts[id], h = '<h4>Source changes</h4>';
    if(!record){ return h + '<p>' + (comparison.adjacent.indexOf(id) >= 0
      ? 'This component imports changed source. Examine possible effects.'
      : 'The comparison has no source changes for this component.') + '</p>'; }
    var surface = record.surface || {}, count = 0;
    h += '<p>Changed source modules: <code>' + esc(record.modules.join(', ')) + '</code>.</p>';
    ['added','removed','changed'].forEach(function(action){
      Object.keys(surface[action] || {}).forEach(function(kind){
        var names = surface[action][kind]; if(!names.length){ return; } count += names.length;
        h += '<p><b>' + esc(action.charAt(0).toUpperCase() + action.slice(1) + ' ' + kind)
          + '</b>: <code>' + esc(names.join(', ')) + '</code>.</p>';
      });
    });
    ['added','removed'].forEach(function(action){
      var names = surface['tests_' + action] || []; if(!names.length){ return; }
      count += names.length; h += '<p><b>Test references ' + action + '</b>: <code>'
        + esc(names.join(', ')) + '</code>. Test references do not show test coverage.</p>';
    });
    if(!count){ h += '<p>No differences in recorded public names or test references were found. '
      + 'The source files can contain other changes.</p>'; }
    record.modules.filter(function(m){ return comparison.unparsed.indexOf(m) >= 0; })
      .forEach(function(m){ h += '<p class="source-unknown">Source differences could not be parsed '
        + 'for <code>' + esc(m) + '</code>. Do the comparison again after you correct the source '
        + 'or extractor error.</p>'; });
    Object.keys(record.unknown || {}).forEach(function(m){
      Object.keys(record.unknown[m]).forEach(function(revision){
        record.unknown[m][revision].forEach(function(issue){
          h += '<p class="source-unknown">Unknown ' + esc(revision) + ' surface for <code>'
            + esc(m) + '</code>: ' + esc(issue.reason || 'The source could not be read.')
            + (issue.line === undefined ? '' : ' (line ' + esc(issue.line)
              + (issue.column == null ? '' : ', column ' + esc(issue.column)) + ')') + '.</p>';
        }); }); });
    return h;
  }
  var comparisonMap = document.getElementById('changemap');
  var comparisonPanel = document.getElementById('change-panel');
  if(W && comparisonMap && comparisonPanel){
    comparisonMap.addEventListener('systemap:select', function(e){
      var section = document.createElement('section');
      section.setAttribute('class', 'source-section comparison-source');
      section.innerHTML = comparisonRows(e.detail.id); comparisonPanel.appendChild(section);
    });
  }
  svg.workspace = {
    state:function(){return {mode:mode,j:cur.j,s:cur.s};},
    trace:startJourney,
    traceStep:function(k){
      var journey = A.journeys[cur.j];
      if(journey && Number.isInteger(k) && k >= 0 && k < journey.steps.length){
        cur.s=k;showStep();
      }
    },
    inspect:function(id){if(cur.j < 0){setMode('understand');}A.select(id);},
    inspectFlow:function(edge,id){A.inspectFlow(edge,id);},
    returnToJourney:backToJourney,
    endJourney:endJourney
  };
  setLayer(A.layers.length ? A.layers[0].id : 'all');
  showZoom(A.view.zoom(), A.view.isFit());
  if(A.state.focus){ openDrawer(A.state.focus, true); sourceRows(A.state.focus); }
  setMode('understand');
  visibility();
})();
"""
