"""The page shell: views, layer tabs, the reading panel, search, keys and source records."""

JS = r"""
(function(){
  var svg = document.getElementById('schematic');
  if(!svg || !svg.systemap){ return; }
  var A = svg.systemap, W = window.systemapWorkspace || {};
  var body = document.body;
  function byId(id){ return document.getElementById(id); }
  var panel = byId('panel'), drawer = byId('drawer'), readpanel = byId('readpanel');
  var empty = byId('inspector-empty'), sourceDetail = byId('source-detail');
  var reviewDetail = byId('review-detail'), reference = byId('reference');
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
  function emit(name, detail){
    svg.dispatchEvent(new CustomEvent(name, {detail:detail || {}, bubbles:true}));
  }
  function show(node, on){ if(node){ node.hidden = !on; } }

  // The page API. The sequence script replaces `journey`; other scripts add
  // readers (the Read panel section for a layer), legends and readouts.
  var P = svg.page = {readers:[], legendFor:[], readoutFor:[], journey:{
    active:function(){ return false; }, state:function(){ return {j:-1, s:0}; },
    start:function(){}, step:function(){}, stepBy:function(){ return false; },
    end:function(){}, back:function(){}
  }};

  // ---- the panel ----------------------------------------------------------
  // The Map view keeps the panel closed until the reader selects something
  // or presses Read. The other views show their own panel.
  var mode = 'understand', readOpen = false, collapsed = false;
  var restoringView = false, frameVersion = 0, opened = '';
  var readBtn = byId('read-toggle');
  var hasChange = !!byId('changemap');
  function panelOpen(){
    if(mode === 'change'){ return hasChange && !collapsed; }
    if(mode !== 'understand' && mode !== 'review'){ return !collapsed; }
    if(mode === 'review'){ return !collapsed || !!A.state.focus; }
    return readOpen || !!A.state.focus;
  }
  function sections(){
    var open = panelOpen(), focus = !!A.state.focus;
    var before = body.dataset.panel;
    body.dataset.panel = open ? 'open' : 'closed';
    show(readpanel, open);
    show(empty, mode === 'understand' && !focus);
    show(drawer, focus && mode !== 'change');
    show(byId('journeyindex'), mode === 'trace' && !focus);
    show(reference, mode === 'review' && !focus);
    show(reviewDetail, mode === 'review' && !focus);
    show(byId('change-panel'), mode === 'change');
    if(readBtn){ readBtn.setAttribute('aria-pressed', open ? 'true' : 'false'); }
    if(before !== body.dataset.panel){
      emit('systemap:panel', {open:open});
      if(A.state.focus && !restoringView){ frameBeside(A.state.focus, true); }
    }
  }
  function frameBeside(id, instant){
    // Frame the selection after the panel has its final width.
    var version = ++frameVersion;
    window.requestAnimationFrame(function(){
      if(A.state.focus !== id || version !== frameVersion){ return; }
      // A narrow window lays the panel over the map: frame beside it.
      var over = window.innerWidth <= 820 && readpanel && !readpanel.hidden;
      A.view.frameFocus(over ? {rect:readpanel.getBoundingClientRect(), side:'right'} : null,
        instant);
    });
  }
  if(readBtn){ readBtn.addEventListener('click', function(){
    if(mode === 'understand'){
      if(panelOpen()){ readOpen = false; if(A.state.focus){ A.clear(); } }
      else { readOpen = true; }
    } else { collapsed = panelOpen(); if(!collapsed && A.state.focus){ A.clear(); } }
    sections();
  }); }

  // ---- the title on the map: layer tabs or the view name, and the question --
  var tabs = all('[data-layer-btn]');
  var layerSelect = byId('layer-select'), question = byId('layer-question');
  var mapLabel = byId('mapbar-label'), tablist = document.querySelector('.mapbar .layers');
  var ALL_QUESTION = 'Which flows connect the components?';
  function layerQuestion(id){
    return id === 'all' ? ALL_QUESTION : (LAY[id] ? LAY[id].question : ''); }
  function setTitle(label, text){
    if(mapLabel){ mapLabel.textContent = label || ''; mapLabel.hidden = !label; }
    if(tablist){ tablist.hidden = !!label; }
    if(question && text !== undefined){ question.textContent = text; }
  }
  function setLayer(id){
    var changed = A.state.layer !== id;
    A.setLayer(id);
    tabs.forEach(function(b){
      var on = b.dataset.layerBtn === id;
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
      b.setAttribute('aria-selected', on ? 'true' : 'false');
      b.tabIndex = on ? 0 : -1;
    });
    if(layerSelect){ layerSelect.value = id; }
    if(mode === 'understand' || mode === 'review'){ setTitle('', layerQuestion(id)); }
    if(A.state.focus && !restoringView){ frameBeside(A.state.focus); }
    if(changed){ emit('systemap:layer', {layer:id}); }
    emit('systemap:workspace');
  }
  tabs.forEach(function(b){ b.addEventListener('click', function(){
    if(mode === 'trace' || mode === 'change'){ setMode('understand'); }
    setLayer(b.dataset.layerBtn);
  }); });
  if(layerSelect){ layerSelect.addEventListener('change',
    function(){ setLayer(layerSelect.value); }); }

  // ---- zoom: Fit and 100% are the named states; + and - step by 1.25 ----
  // The buttons act on the map that the view shows: the change map in Changes.
  var zoomBtns = all('[data-zoom]'), zpct = byId('zpct'), changeMap = byId('changemap');
  function shownMap(){
    return mode === 'change' && changeMap && changeMap.systemap ? changeMap.systemap : A;
  }
  zoomBtns.forEach(function(b){
    b.addEventListener('click', function(){
      var z = b.dataset.zoom, M = shownMap();
      if(z === 'fit'){ M.view.fit(); }
      else if(z === 'actual'){ M.view.actual(); }
      else { M.view.zoomBy(z === 'in' ? 1.25 : 1 / 1.25); }
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
  [svg, changeMap].forEach(function(m){
    if(m){ m.addEventListener('systemap:view', function(e){
      if((m === svg) === (shownMap() === A)){ showZoom(e.detail.zoom, e.detail.fit); }
    }); }
  });

  // ---- views ---------------------------------------------------------------
  var TITLES = {trace:['SEQUENCES', 'Which steps make one operation?'],
    change:['CHANGES', 'What did this change touch?']};
  var more = byId('theme-menu');
  function setMode(name){
    if(name !== 'trace' && P.journey.active()){ P.journey.end(false); }
    mode = name;
    body.dataset.mode = name;
    body.dataset.compare = String(hasChange);
    all('button[data-mode]').forEach(function(b){
      var on = b.dataset.mode === name || (name === 'review' && b.dataset.mode === 'understand');
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    collapsed = false;
    if(TITLES[name]){ setTitle(TITLES[name][0], TITLES[name][1]); }
    else { setTitle('', layerQuestion(A.state.layer)); }
    var change = byId('change');
    show(change, name === 'change');
    show(byId('spatialmap'), name !== 'change');
    if(name === 'change' && A.state.focus){ A.clear(); }
    if(name === 'review'){ renderReview(); }
    if(more){ more.open = false; }
    var label = byId('activity-label');
    if(label){ label.textContent = {understand:'System components', trace:'Operation sequence',
      change:'Revision comparison', review:'Map records'}[name]; }
    var activity = byId('activity-question');
    if(activity){ activity.textContent = {
      understand:'What are the components and their connections?',
      trace:'What are the operation steps?', change:'What did this change touch?',
      review:'Which decisions and rules apply to this map?'}[name]; }
    sections();
    var M = shownMap();
    if(M && M.view){ showZoom(M.view.zoom(), M.view.isFit()); }
    emit('systemap:mode', {mode:name});
    emit('systemap:workspace');
  }
  all('button[data-mode]').forEach(function(b){
    b.addEventListener('click', function(){
      if(b.dataset.mode === mode && mode === 'review'){ setMode('understand'); return; }
      setMode(b.dataset.mode);
      // Reference shows the records, not a selection from an earlier view.
      if(b.dataset.mode === 'review' && A.state.focus){ A.clear(); }
    });
  });

  // ---- search: the Find field and its list of components ---------------------
  var find = byId('partsearch'), results = byId('components');
  function openFind(){ if(results){ results.hidden = false;
    } if(find){ find.setAttribute('aria-expanded', 'true'); } }
  function closeFind(){ if(results){ results.hidden = true;
    } if(find){ find.setAttribute('aria-expanded', 'false'); } }
  function visibleEntries(){ return all('.ix[data-go]',
    results).filter(function(b){ return !b.hidden; }); }
  function searchParts(){
    if(!find){ return; }
    var q = find.value.trim().toLowerCase();
    var found = 0, entries = all('.ix[data-go]');
    entries.forEach(function(b){
      var d = A.detail[b.dataset.go], s = W.sources && W.sources[b.dataset.go];
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
    var status = byId('searchcount');
    if(status){ status.textContent = found + ' of ' + entries.length + ' components'; }
    show(byId('searchempty'), found === 0);
  }
  if(find){
    find.addEventListener('focus', function(){ searchParts(); openFind(); });
    find.addEventListener('input', function(){ searchParts(); openFind(); });
    find.addEventListener('keydown', function(e){
      var list = visibleEntries();
      if(e.key === 'Escape'){ closeFind(); find.blur(); e.preventDefault(); e.stopPropagation(); }
      else if(e.key === 'ArrowDown' && list.length){ list[0].focus(); e.preventDefault(); }
      else if(e.key === 'Enter' && list.length){ list[0].click(); e.preventDefault(); }
    });
  }
  if(results){ results.addEventListener('keydown', function(e){
    var list = visibleEntries(), i = list.indexOf(document.activeElement);
    if(e.key === 'Escape'){ closeFind(); if(find){ find.focus(); } e.preventDefault();
      e.stopPropagation(); }
    else if(e.key === 'ArrowDown' && i >= 0 && i < list.length - 1){ list[i + 1].focus();
      e.preventDefault(); }
    else if(e.key === 'ArrowUp' && i > 0){ list[i - 1].focus(); e.preventDefault(); }
    else if(e.key === 'ArrowUp' && i === 0 && find){ find.focus(); e.preventDefault(); }
  }); }
  document.addEventListener('pointerdown', function(e){
    if(results && !results.hidden && !results.contains(e.target) && e.target !== find){
      closeFind(); }
    if(more && more.open && !more.contains(e.target)){ more.open = false; }
  });
  all('.ix[data-go], .gv[data-go]').forEach(function(b){
    b.addEventListener('click', function(){
      if(mode === 'change'){ setMode('understand'); }
      A.select(b.dataset.go);
      closeFind();
    });
  });
  searchParts();

  // ---- selection --------------------------------------------------------
  var closeBtn = byId('drawerclose');
  if(closeBtn){ closeBtn.addEventListener('click', function(){
    if(P.journey.active()){ P.journey.back(); } else { A.clear(); }
  }); }
  function nodeOf(id){
    return all('.node', svg).filter(function(n){ return n.dataset.id === id; })[0] || null;
  }
  svg.addEventListener('systemap:select', function(e){
    var id = e.detail.id;
    opened = id;
    var status = byId('linkstatus');
    if(status){ status.textContent = ''; }
    sourceRows(id);
    sections();
    if(!restoringView){ frameBeside(id); }
    if(location.hash !== '#' + id){ history.replaceState(null, '', '#' + id); }
    all('.ix[data-go]').forEach(function(b){
      b.setAttribute('aria-current', b.dataset.go === id ? 'true' : 'false');
    });
  });
  svg.addEventListener('systemap:clear', function(){
    if(sourceDetail){ sourceDetail.innerHTML = ''; }
    sections();
    if(location.hash){ history.replaceState(null, '', location.pathname + location.search); }
    all('.ix[data-go]').forEach(function(b){ b.removeAttribute('aria-current'); });
    // Focus that was in the panel, or nowhere, goes back to the card the
    // panel was about, so the keyboard reader is where they left off.
    var active = document.activeElement, node = opened && nodeOf(opened);
    opened = '';
    if(node && (!active || active === body || active.isConnected === false
        || (readpanel && readpanel.contains(active)))){
      node.focus({preventScroll:true});
    }
    if(P.journey.active() && !A.state.journey){ P.journey.back(); }
  });
  svg.addEventListener('systemap:flow', function(e){
    if(mode === 'understand' || mode === 'review'){ setLayer(A.edges[e.detail.edge].layer); }
  });
  // A sequence button anywhere in the panel starts that sequence.
  if(readpanel){ readpanel.addEventListener('click', function(e){
    var b = e.target.closest && e.target.closest('[data-journey]');
    if(!b || !readpanel.contains(b)){ return; }
    var k = +b.dataset.journey;
    if(P.journey.state().j !== k){ setMode('trace'); P.journey.start(k); }
    if(b.dataset.journeyStep !== undefined){ P.journey.step(+b.dataset.journeyStep); }
  }); }

  // ---- the map inside a card, in place -----------------------------------
  var submap = byId('submap'), submapFrame = byId('submapframe');
  var submapCrumb = byId('submapcrumb'), submapClose = byId('submapclose');
  var submapOpener = null, inertBefore = [];
  function holdBackground(){
    var child = submap, parent = child.parentNode;
    while(parent && child !== body){
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
    body.classList.add('submap-open');
    submapClose.focus();
  }
  function closeSubmap(){
    if(!submap || submap.hidden){ return false; }
    submap.hidden = true;
    submapFrame.setAttribute('src', 'about:blank');
    body.classList.remove('submap-open');
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
  // The head script stamped the root before the first paint; the buttons
  // show that, and a change restamps the root, keeps the pick in this
  // browser when it can, and follows into the map inside a card.
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
  function showScheme(){
    all('[data-scheme]').forEach(function(b){
      b.setAttribute('aria-pressed', b.dataset.scheme === scheme() ? 'true' : 'false');
    });
  }
  function setScheme(name){
    document.documentElement.setAttribute('data-theme', name);
    try { localStorage.setItem('systemap-theme', name); } catch(e){}
    showScheme(); stampFrame();
    emit('systemap:scheme', {scheme:name});
  }
  all('[data-scheme]').forEach(function(b){
    b.addEventListener('click', function(){ setScheme(b.dataset.scheme); });
  });
  showScheme();
  if(submapFrame){ submapFrame.addEventListener('load', stampFrame); }

  // The native preference always wins. The page control can also stop motion.
  var motionPick = byId('reduce-motion');
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
  // Tab moves across the cards in reading order, Enter on a card opens its
  // panel, Escape closes the newest thing, the left and right arrows switch
  // layers or step the sequence, 1 to 9 select a layer tab, R opens Read,
  // T changes the map and the text view, / finds a component.
  function stepLayer(d){
    var ids = tabs.map(function(b){ return b.dataset.layerBtn; });
    if(!ids.length){ return; }
    var i = ids.indexOf(A.state.layer);
    setLayer(ids[(i + d + ids.length) % ids.length]);
  }
  function overlayOpen(){
    return ['keys', 'present'].some(function(id){ var n = byId(id); return n && !n.hidden; });
  }
  function typing(t){
    var tag = t && t.tagName;
    return tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA' ||
      (t && t.isContentEditable) || !!(t && t.closest && t.closest('[role="textbox"]'));
  }
  function escape(e){
    if(more && more.open){ more.open = false; e.preventDefault(); return; }
    if(P.journey.active()){ P.journey.end(); e.preventDefault(); return; }
    if(A.state.focus){ A.clear(); A.view.back(); e.preventDefault(); return; }
    if(readOpen && mode === 'understand'){ readOpen = false; sections(); e.preventDefault();
      return; }
    if(mode === 'review'){ setMode('understand'); e.preventDefault(); return; }
    A.view.back();
  }
  function letter(e){
    var k = e.key.toLowerCase();
    if(k === 'r' && readBtn){ readBtn.click(); return true; }
    if(k === 't'){
      var target = byId(body.dataset.view === 'reading' ? 'view-map' : 'view-reading');
      if(target){ target.click(); }
      return true;
    }
    if(/^[1-9]$/.test(e.key) && mode !== 'trace'){
      var b = tabs[+e.key - 1];
      if(b){ b.click(); }
      return !!b;
    }
    return false;
  }
  document.addEventListener('keydown', function(e){
    if(e.key === 'Escape' && closeSubmap()){ e.preventDefault(); return; }
    if(submap && !submap.hidden){ return; }
    if(overlayOpen() || typing(e.target)){ return; }
    if((e.key === '/' && !e.altKey && !e.ctrlKey && !e.metaKey) ||
      (e.key.toLowerCase() === 'k' && (e.ctrlKey || e.metaKey) && !e.altKey)){
      if(find){ find.focus(); e.preventDefault(); }
      return;
    }
    if(e.altKey || e.ctrlKey || e.metaKey){ return; }
    if(e.key === 'Escape'){ escape(e); return; }
    if(e.key === 'ArrowRight' || e.key === 'ArrowLeft'){
      if(e.target && e.target.closest && e.target.closest('#readpanel')){ return; }
      var d = e.key === 'ArrowRight' ? 1 : -1;
      if(P.journey.active()){ if(P.journey.stepBy(d)){ e.preventDefault(); } }
      else if(mode === 'understand' || mode === 'review'){ stepLayer(d); e.preventDefault(); }
      return;
    }
    if(letter(e)){ e.preventDefault(); }
  });
  window.addEventListener('resize', function(){
    showZoom(A.view.zoom(), A.view.isFit());
    if(A.state.focus && panelOpen()){ frameBeside(A.state.focus, true); }
  });

  // ---- records for a selected component ----------------------------------
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
    if(!sourceDetail || !W.sources){ return; }
    var d = A.detail[id], s = W.sources[id], h = '';
    if(!d || d.kind === 'actor' || !s){ sourceDetail.innerHTML = ''; return; }
    h += '<section class="source-section"><h3>Source evidence</h3>'
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
      + moduleRecords(s)
      + '<h3>Entry points</h3><p>An entry point is where a program can start.</p>'
      + (s.points.map(function(p){ return '<p><code>' + esc(p) + '</code></p>'; }).join('')
        || '<p>No entry points were extracted for these modules.</p>')
      + '</details></section>';
    sourceDetail.innerHTML = h;
  }

  // ---- reference: decisions ----------------------------------------------
  var reviewFilter = 'open', reviewPick = -1;
  function reviewCards(line){
    return Object.keys(W.sources || {}).filter(function(id){
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
    var h = '<p class="review-kicker">' + esc(label)
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
    if(!W.review){ return; }
    var items = W.review[reviewFilter];
    byId('reviewlist').innerHTML = items.map(function(item, k){
      return '<button type="button" class="review-choice" data-review-item="' + k
        + '" aria-pressed="false">' + esc(item.kind) + '<small>' + esc(item.line)
         + '</small></button>';
    }).join('') || '<p>' + (reviewFilter === 'open' ? 'This map has no findings without answers. '
      + 'A person must still examine the map claims.'
      : 'These findings have no applicable stored answers.') + '</p>';
    all('[data-review-item]').forEach(function(b){
      b.addEventListener('click', function(){
        A.clear(); pickReview(+b.dataset.reviewItem); sections();
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
      A.clear(); renderReview(); sections();
    });
  });

  // ---- copy a command -------------------------------------------------------
  // The button says Copied for a short time; the status line says it too.
  document.addEventListener('click', function(e){
    var b = e.target.closest && e.target.closest('[data-copy]');
    if(!b){ return; }
    var status = byId('copystatus');
    function say(text){ if(status){ status.textContent = text; } }
    if(!navigator.clipboard || !navigator.clipboard.writeText){
      say('No clipboard access. Select and copy the command text.'); return;
    }
    navigator.clipboard.writeText(b.dataset.copy).then(function(){
      say('Copied: ' + b.dataset.copy);
      if(!b.dataset.label){ b.dataset.label = b.textContent; }
      b.textContent = 'Copied'; b.classList.add('copied');
      setTimeout(function(){ b.textContent = b.dataset.label; b.classList.remove('copied');
        }, 1500);
    }, function(){ say('Copy failed. Select and copy the command text.'); });
  });

  // ---- the page API --------------------------------------------------------
  P.setMode = setMode;
  P.mode = function(){ return mode; };
  P.setLayer = setLayer;
  P.setTitle = setTitle;
  P.openPanel = function(){ readOpen = true; collapsed = false; sections(); };
  P.closePanel = function(){ readOpen = false; collapsed = mode !== 'understand'; sections(); };
  P.panelOpen = panelOpen;
  P.sync = sections;
  P.frame = frameBeside;
  P.restoring = function(on){ restoringView = !!on; };
  svg.workspace = {
    state:function(){ var s = P.journey.state(); return {mode:mode, j:s.j, s:s.s}; },
    trace:function(k){ P.journey.start(k); },
    traceStep:function(k){ P.journey.step(k); },
    inspect:function(id){ if(!P.journey.active()){ setMode('understand'); } A.select(id); },
    inspectFlow:function(edge, id){ A.inspectFlow(edge, id); },
    returnToJourney:function(){ P.journey.back(); },
    endJourney:function(){ P.journey.end(); }
  };
  var first = (W.tabs && W.tabs[0]) || (A.layers.length ? A.layers[0].id : 'all');
  setLayer(first);
  showZoom(A.view.zoom(), A.view.isFit());
  if(A.state.focus){ opened = A.state.focus; sourceRows(A.state.focus); }
  setMode('understand');
})();
"""
