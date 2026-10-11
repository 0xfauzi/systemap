"""The legend and the readout on the map. Both count only what the map draws."""

SCRIPT = r"""
(function(){
  var svg = document.getElementById('schematic');
  if(!svg || !svg.systemap || !svg.page){ return; }
  var A = svg.systemap, P = svg.page;
  var readout = document.getElementById('map-context'),
    legend = document.getElementById('map-legend');
  var LAY = {};
  A.layers.forEach(function(l){ LAY[l.id] = l; });
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function plural(n, word){ return n + ' ' + word + (n === 1 ? '' : 's'); }
  function shown(){
    // The flows the map draws now: the reading, or the lit flows of a selection.
    var L = A.state.layer, reading = A.detail._meta.readings[L];
    if(A.state.edge >= 0){ return [A.state.edge]; }
    if(A.state.focus){
      return (A.detail[A.state.focus].edges || []).filter(function(i){
        return L === 'all' || (reading && reading.edges.indexOf(i) >= 0); });
    }
    var out = [];
    A.edges.forEach(function(_e, i){
      if(L === 'all' || (reading && reading.edges.indexOf(i) >= 0)){ out.push(i); } });
    return L === 'structure' ? [] : out;
  }
  function firstSentence(text){
    var m = String(text || '').match(/^[^.]*\./);
    return m ? m[0] : String(text || '');
  }
  function defaultReadout(){
    if(A.state.edge >= 0){
      var e = A.edges[A.state.edge];
      return e.art + ' · ' + e.from + ' → ' + e.to + ' · ' + A.evidenceLabel(e.evidence);
    }
    if(A.state.focus){
      var d = A.detail[A.state.focus];
      return d.id + ' · ' + firstSentence(d.does);
    }
    var L = A.state.layer, ids = A.layerIds(L), regions = (A.detail._meta.regions || []).length;
    if(L === 'structure'){
      var parts = Object.keys(A.detail).filter(function(id){
        return id !== '_meta' && A.detail[id].kind !== 'actor'; }).length;
      return plural(parts, 'component') + (regions ? ' · ' + plural(regions, 'region') : '');
    }
    var actors = ids.filter(function(id){ return A.detail[id].kind === 'actor'; }).length;
    return plural(shown().length, 'flow') + (actors ? ' · ' + plural(actors, 'actor') : '');
  }
  function first(hooks){
    for(var k = 0; k < hooks.length; k++){ var out = hooks[k](); if(out){ return out; } }
    return null;
  }
  function swatch(cls, style, label){
    return '<span class="lg"><i class="' + cls + '"' + (style ? ' style="' + style + '"' : '')
      + '></i>' + esc(label) + '</span>';
  }
  function defaultLegend(){
    var kinds = [], dashed = false, h = '';
    shown().forEach(function(i){
      var e = A.edges[i];
      if(kinds.indexOf(e.layer) < 0){ kinds.push(e.layer); }
      if(e.evidence === 'structural' || e.evidence === 'declared'){ dashed = true; }
    });
    A.layers.forEach(function(l){
      if(kinds.indexOf(l.id) >= 0){ h += swatch('lg__line', '--c:' + l.colour, l.label); } });
    if(dashed){ h += swatch('lg__line lg__line--dash', '', 'No source review'); }
    var ids = A.state.focus ? [] : A.layerIds(A.state.layer);
    if(ids.some(function(id){ return A.detail[id].kind === 'actor'; })){
      h += swatch('lg__card lg__card--actor', '', 'Actor'); }
    var shownCards = '.node:not(.quiet):not(.dim) ';
    if(svg.querySelector(shownCards + '.node__map')){
      h += swatch('lg__card lg__card--map', '', 'Opens a map: double-click the card'); }
    if(svg.querySelector(shownCards + '.node__note')){
      h += swatch('lg__dot', '', 'Has a note in Details'); }
    var quiet = svg.querySelector('.node.quiet, .node.dim');
    if(quiet){ h += swatch('lg__card lg__card--quiet', '', A.state.focus
      ? 'Not connected to the selection' : 'No flow in this view'); }
    return h;
  }
  function besideCount(){
    // Labels that have no seat on their own line: board rule 2 puts them in the
    // panel list. The map script marks them.
    if(!A.besideEdges || A.state.focus || A.state.journey){ return 0; }
    var on = {};
    A.besideEdges.forEach(function(i){ on[i] = true; });
    return shown().filter(function(i){ return on[i]; }).length;
  }
  if(readout){ readout.addEventListener('click', function(e){
    if(!e.target.closest('[data-open-read]')){ return; }
    P.openPanel();
    var list = document.querySelector('#inspector-empty .read__section');
    if(list){ list.scrollIntoView({block:'nearest'}); }
  }); }
  var lastReadout = '', lastLegend = '';
  function sync(){
    var other = P.mode && P.mode() === 'change';
    var hooked = first(P.readoutFor), custom = !!hooked;
    var text = hooked || (other ? '' : defaultReadout());
    var beside = custom ? 0 : besideCount();
    var key = text + '|' + beside;
    if(readout && key !== lastReadout){
      readout.innerHTML = '<span>' + esc(text) + '</span>' + (beside
        ? '<button type="button" class="readout__more" data-open-read>' + plural(beside, 'label')
          + (beside === 1 ? ' is' : ' are') + ' in the list</button>' : '');
      lastReadout = key;
    }
    var html = first(P.legendFor);
    if(html === null){ html = other ? '' : defaultLegend(); }
    if(legend && html !== lastLegend){ legend.innerHTML = html; lastLegend = html; }
    if(legend){ legend.hidden = !html; }
    if(readout){ readout.hidden = !text; }
  }
  ['systemap:workspace', 'systemap:select', 'systemap:clear', 'systemap:layer',
    'systemap:mode', 'systemap:step', 'systemap:flow'].forEach(function(name){
    svg.addEventListener(name, function(){ window.requestAnimationFrame(sync); });
  });
  P.syncFrame = sync;
  sync();
})();
"""
