"""The phone layout: the regions grid, the layer choice and one sequence step at a time.

A window of 640 pixels or less shows these parts. Wider windows hide them and
keep the map page unchanged. The script sets `body[data-phone]` to the phone
state: `grid` (the regions grid), `map` (the map at a region or the full map),
`step` (one sequence step with a small map), `full` (the full map during a
sequence), `index` (the list of sequences) or `change` (the Changes view).
"""

from __future__ import annotations

import html as html_mod

from systemap.model import Meaning, Model

CSS = r"""
.phone-head,.phone-body,.phone-full{display:none}
@media (max-width:640px){
/* ---- header: mark, name, revision, settings; the views below it --------- */
.bar{height:auto;min-height:53px;flex-wrap:wrap;column-gap:10px;row-gap:0;padding:0 16px;
  border-bottom:0;background:linear-gradient(var(--surface) 0 52px,var(--line) 52px 53px,
  var(--bg) 53px)}
.brand{height:52px}.mark{width:20px;height:20px}
.project{flex:1 1 auto;min-width:0;height:52px;align-items:center;gap:10px}
.project-name{overflow:hidden;text-overflow:ellipsis}
.snap-at{margin-left:auto;position:static}
.snap__pop{position:fixed;left:16px;right:16px;top:56px;width:auto}
.bar__space,#panel-toggle,#keys-open,.bar__div{display:none}
.bar .tool,.bar .find{width:40px;height:40px;min-height:40px;border:0;background:none}
.bar .views{order:9;flex:0 0 100%;margin:11px 0 0;display:grid;
  grid-template-columns:repeat(3,minmax(0,1fr));gap:0;border:1px solid var(--line-2);
  border-radius:8px;overflow:hidden}
.bar .views button{height:40px;min-height:40px;padding:0;border:0;border-radius:0;
  justify-content:center;font-size:14px;color:var(--ink-2);background:transparent}
.bar .views button+button{border-left:1px solid var(--line-2)}
.bar .views button[aria-pressed="true"]{background:var(--card);color:var(--ink);font-weight:500;
  border-color:var(--line-2)}

/* ---- the map frame and the panel in phone states --------------------------- */
body[data-phone] .main{display:block;height:auto;min-height:0;padding:0 16px 16px}
body[data-phone="grid"] .main{display:none}
body[data-phone] .map{height:calc(100svh - 184px);min-height:300px;margin-top:12px;
  border:1px solid var(--line);border-radius:10px}
body[data-phone="change"] .map{height:calc(100svh - 134px)}
body[data-phone="map"][data-panel="open"] .map,
body[data-phone="change"][data-panel="open"] .map{height:46svh;min-height:260px}
/* One step fills the screen: the map takes the height that the step and its buttons leave. */
body[data-phone="step"]{display:flex;flex-direction:column}
body[data-phone="step"] .main{flex:1;display:flex;flex-direction:column;padding-bottom:0}
body[data-phone="step"] .map,body[data-phone="step"][data-panel] .map{flex:1;height:auto;
  min-height:160px}
body[data-phone="index"] .map,body[data-phone="panel"] .map{display:none}
body[data-phone] .mapbar,body[data-phone] .trace-controls,body[data-phone] .guide,
body[data-phone] .map>.readout,body[data-phone="step"] .zoom,
body[data-phone="step"] .map-legend{display:none}
body[data-phone] .mapwrap{inset:0}
body[data-phone="step"] #schematic .seq-callout{display:none}
body[data-phone] .zoom{top:8px;right:8px}
body[data-phone] .zoom button{height:32px;min-height:32px;min-width:32px}
body[data-phone] #zpct{width:46px}
body[data-phone] .map-legend{left:8px;bottom:8px;max-width:calc(100% - 16px);gap:2px 12px;
  font-size:11px;padding:2px 6px}
body[data-phone] .change-controls{position:static;height:auto;min-height:52px;flex-wrap:wrap;
  padding:8px 12px;gap:6px;border-radius:10px 10px 0 0}
body[data-phone] .change-view{position:relative;inset:auto;flex:1 1 auto;min-height:0}
body[data-phone="change"] .zoom{display:none}
body[data-phone] .change-view .stage{inset:0}
body[data-phone] .change-empty{margin:0;padding:20px 16px}
body[data-phone="change"][data-compare="false"] .map{height:auto;min-height:0}
body[data-phone="change"][data-compare="false"] .change-view{position:static}
body[data-phone="step"] .readpanel,body[data-phone="full"] .readpanel{display:none}
body[data-phone] .readpanel,body[data-phone][data-panel="open"] .readpanel{position:static;
  width:auto;height:auto;min-height:0;overflow:visible;padding:16px 0 24px;border:0;
  background:transparent;box-shadow:none}
body[data-phone="index"] .readpanel{padding-top:12px}
body[data-phone] .journey-index,body[data-phone] #seqbody,body[data-phone] .seq-all{flex:none;
  max-height:none;min-height:0;overflow:visible}
body[data-phone] .seq-all{-webkit-mask-image:none;mask-image:none}
body[data-phone] .seq-all li:last-child{padding-bottom:0}

/* ---- phone parts ---------------------------------------------------------- */
body[data-phone] .phone-head{display:flex;flex-direction:column;gap:10px;padding:10px 16px 0}
body[data-phone="change"] .phone-head{display:none}
.phone-pick,.phone-seq,.phone-bar{display:none}
body[data-phone="grid"] .phone-pick{display:flex}
body[data-phone="step"] .phone-seq,body[data-phone="index"] .phone-seq{display:block}
body[data-phone="map"] .phone-bar,body[data-phone="full"] .phone-bar{display:flex}
.phone-pick{flex-direction:column;gap:10px}
.phone-select{width:100%;height:44px;padding:0 12px;border:1px solid var(--line-2);
  border-radius:8px;background:var(--card);color:var(--ink);font:15px var(--fs)}
.phone-seq .seq-choose__btn{height:44px;border-radius:8px;font-size:15px}
.phone-question{margin:2px 0 0;font:17px/24px var(--fs);color:var(--ink)}
.phone-bar{align-items:center;gap:10px;height:40px}
.phone-bar button{height:40px;min-height:40px;padding:0 14px;border:1px solid var(--line-2);
  border-radius:8px;background:transparent;color:var(--ink);font-size:14px;flex:none}
.phone-bar__title{min-width:0;margin:0;font:600 11px/16px var(--fm);letter-spacing:.08em;
  color:var(--ink-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
body[data-phone] .phone-body{display:block}
.phone-home,.phone-step{display:none}
body[data-phone="grid"] .phone-home{display:block}
body[data-phone="step"] .phone-step{display:flex}
.phone-full{position:absolute;right:8px;top:8px;z-index:8;height:32px;min-height:32px;
  padding:0 10px;border:1px solid var(--line-2);border-radius:6px;background:var(--surface);
  color:var(--ink-2);font:12px var(--fs)}
body[data-phone="step"] .phone-full{display:inline-flex;align-items:center}

/* ---- the regions grid ---------------------------------------------------- */
.phone-grid{margin:12px 16px 0;display:grid;grid-template-columns:104px repeat(2,minmax(0,1fr));
  grid-auto-rows:minmax(112px,auto);gap:8px}
.phone-grid--inside{grid-template-columns:repeat(2,minmax(0,1fr))}
.phone-grid button{height:auto;min-height:0;margin:0;text-align:left;font-weight:400}
.phone-out{display:flex;flex-direction:column;gap:4px;align-items:stretch;padding:10px 8px;
  border:1px solid var(--line-2);border-radius:8px;background:transparent;color:var(--ink)}
.phone-out__k,.phone-region__name{font:600 10px/14px var(--fm);letter-spacing:.06em;
  color:var(--ink-3);overflow-wrap:anywhere}
.phone-actors{margin-top:6px;display:flex;flex-direction:column;gap:10px}
.phone-actor{padding:6px 5px;border:1px dashed var(--card-line);border-radius:5px;
  font:600 12px/16px var(--fm);color:var(--ink);overflow-wrap:anywhere}
.phone-actor.dim{font-weight:400;color:var(--ink-3)}
.phone-out__n{margin-top:auto;padding-top:8px;font:12px/16px var(--fs);color:var(--ink-3)}
.phone-region{display:flex;flex-direction:column;gap:3px;align-items:stretch;
  justify-content:flex-start;padding:9px 7px 1px;border:1px dashed var(--region);border-radius:8px;
  background:var(--card);color:var(--ink)}
.phone-region__head{display:flex;justify-content:space-between;align-items:center;gap:2px}
.phone-region__name{color:var(--ink-2)}
.phone-badge{flex:none;min-width:20px;padding:0 6px;border:1px solid var(--ink-3);
  border-radius:9px;font:600 12px/18px var(--fm);color:var(--ink);text-align:center}
.phone-badge--top{border-color:var(--ink);background:var(--ink);color:var(--bg)}
.phone-badge--none{color:var(--ink-3);border-color:var(--line-2)}
.phone-name{font:12px/17px var(--fm);color:var(--ink-3);overflow-wrap:anywhere}
.phone-name.on{font-weight:600;color:var(--ink)}
.phone-grid button:hover{background:var(--raised)}
.phone-note{display:flex;align-items:center;justify-content:center;padding:10px;
  border:1px dashed var(--line);border-radius:8px;font:12px/17px var(--fs);color:var(--ink-3);
  text-align:center}
.phone-note--row{grid-column:1/-1;min-height:0}
.phone-after{margin:12px 16px 0;display:flex;flex-direction:column;gap:10px}
.phone-hint{margin:0;font:13px/19px var(--fs);color:var(--ink-2)}
.phone-open{height:44px;min-height:44px;border:1px solid var(--line-2);border-radius:8px;
  background:transparent;color:var(--ink);font:15px var(--fs)}
.phone-list{margin:16px 16px 0;padding:14px 0 28px;border-top:1px solid var(--line);
  display:flex;flex-direction:column;gap:10px}
.phone-list:empty{display:none}
.phone-list__head{display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.phone-list h2{margin:0;font:600 11px/16px var(--fm);letter-spacing:.08em;color:var(--ink-3)}
.phone-list__n{font:12px var(--fm);color:var(--ink-3)}
.phone-rows{display:grid;grid-template-columns:92px minmax(0,1fr);gap:10px 12px;margin:0;
  font:14px/20px var(--fs);color:var(--ink-2)}
.phone-rows dt{font:600 13px/20px var(--fm);color:var(--ink);overflow-wrap:anywhere}
.phone-rows dd{margin:0}
.phone-flows{list-style:none;margin:0;padding:0}
.phone-flow{width:100%;min-height:44px;display:grid;grid-template-columns:18px minmax(0,1fr);
  gap:2px 10px;align-items:center;padding:8px 0;border:0;border-bottom:1px solid var(--line);
  border-radius:0;background:transparent;text-align:left}
.phone-flow i{display:block;border-top:2px solid var(--c,var(--ink-3))}
.phone-flow i.dash{border-top-style:dashed}
.phone-flow span{font:14px/20px var(--fs);color:var(--ink)}
.phone-flow small{grid-column:2;font:12px/16px var(--fm);color:var(--ink-3)}

/* ---- one sequence step --------------------------------------------------- */
.phone-step{flex-direction:column;padding-bottom:max(16px,env(safe-area-inset-bottom))}
.phone-call{margin:12px 16px 0;padding:12px 14px;border:1px solid var(--accent);
  border-radius:10px;background:var(--card);display:flex;flex-direction:column;gap:6px}
.phone-call__head{display:flex;align-items:center;gap:8px;min-width:0}
.phone-call__n{flex:none;width:22px;height:22px;border-radius:50%;background:var(--accent);
  color:var(--on-accent);display:inline-flex;align-items:center;justify-content:center;
  font:700 12px/1 var(--fm)}
.phone-call__art{min-width:0;font:600 15px/20px var(--fs);color:var(--accent);
  overflow-wrap:anywhere}
:root[data-theme="light"] .phone-call__art{box-shadow:inset 0 -6px 0 var(--hl)}
.phone-call__ends{margin-left:auto;flex:none;max-width:50%;font:12px/16px var(--fm);
  color:var(--ink-3);text-align:right;overflow-wrap:anywhere}
.phone-call__say{margin:0;font:15px/22px var(--fs);color:var(--ink)}
.phone-call__roles{display:flex;flex-wrap:wrap;align-items:center;gap:6px;font:13px/20px var(--fm);
  color:var(--ink)}
.phone-call__roles:empty{display:none}
.phone-tag{font:700 10px/16px var(--fm);letter-spacing:.06em;padding:0 6px;border-radius:3px;
  border:1px solid var(--accent);background:var(--accent);color:var(--on-accent)}
.phone-tag--meas{margin-left:10px;border-color:var(--steel);background:transparent;
  color:var(--steel)}
.phone-tag--meas:first-child{margin-left:0}
.phone-steps{margin:12px 16px 0;display:grid;grid-auto-flow:column;
  grid-auto-columns:minmax(44px,1fr);gap:6px;overflow-x:auto}
.phone-steps button{height:44px;min-height:44px;padding:0;border:1px solid var(--line-2);
  border-radius:8px;background:transparent;color:var(--ink-3);font:600 14px var(--fm)}
.phone-steps button.done{border-color:var(--ink-2);color:var(--ink)}
.phone-steps button[aria-current="step"]{border-color:var(--accent);background:var(--accent);
  color:var(--on-accent);font-weight:700}
.phone-move{margin:10px 16px 0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.phone-move button{height:48px;min-height:48px;border:1px solid var(--line-2);border-radius:8px;
  background:transparent;color:var(--ink-2);font:15px var(--fs)}
.phone-move .primary{border-color:var(--ink);background:var(--ink);color:var(--bg);
  font-weight:600}
.phone-move .primary:hover{background:var(--ink);color:var(--bg);opacity:.9}
.phone-move button:disabled{opacity:.45}
}
"""

SCRIPT = r"""
(function(){
  var svg = document.getElementById('schematic');
  if(!svg || !svg.systemap || !svg.page){ return; }
  var A = svg.systemap, P = svg.page, W = window.systemapWorkspace || {};
  var META = A.detail._meta || {}, body = document.body;
  function byId(id){ return document.getElementById(id); }
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function all(sel, root){
    return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  var media = window.matchMedia ? window.matchMedia('(max-width: 640px)') : null;
  function phone(){ return !!(media && media.matches); }
  var head = byId('phone-head'), main = document.querySelector('main.main'), map = byId('map');
  var fullBtn = byId('phone-full');
  if(head && main && main.parentNode){ main.parentNode.insertBefore(head, main); }
  if(fullBtn && map){ map.appendChild(fullBtn); }
  var layerPick = byId('phone-layer'), question = byId('phone-question');
  var backBtn = byId('phone-back'), barTitle = byId('phone-title');
  var seqBox = byId('seqpick').parentNode;
  var grid = byId('phone-grid'), hint = byId('phone-hint'), list = byId('phone-list');
  var call = byId('phone-call'), stepNav = byId('phone-steps');
  var prevBtn = byId('phone-prev'), nextBtn = byId('phone-next');
  var LAY = {};
  A.layers.forEach(function(l){ LAY[l.id] = l; });
  var NODE = {};
  all('.node', svg).forEach(function(n){ NODE[n.dataset.id] = n; });
  // `opened` is the region on the map ('' for the grid, 'all' for the full map);
  // `full` shows the full map during a sequence.
  var opened = '', full = false, gridScroll = 0;

  // ---- geometry ------------------------------------------------------------
  function boxOf(id){
    var r = NODE[id] && NODE[id].querySelector('.node__box');
    if(!r){ return null; }
    return {x:+r.getAttribute('x'), y:+r.getAttribute('y'),
      w:+r.getAttribute('width'), h:+r.getAttribute('height')};
  }
  function byPlace(ids){
    return ids.filter(function(id){ return !!A.detail[id]; }).sort(function(a, b){
      var p = boxOf(a) || {x:0, y:0}, q = boxOf(b) || {x:0, y:0};
      return (Math.round(p.y / 24) - Math.round(q.y / 24)) || (p.x - q.x);
    });
  }
  function frameIds(ids, pad, edge){
    // Fit the cards (and the line of `edge`) in the map frame, as a framing of the
    // map script does, with `pad` drawing units around them.
    var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    function add(b){
      x0 = Math.min(x0, b.x); y0 = Math.min(y0, b.y);
      x1 = Math.max(x1, b.x + b.w); y1 = Math.max(y1, b.y + b.h);
    }
    ids.forEach(function(id){ var b = boxOf(id); if(b){ add(b); } });
    var line = edge >= 0 ? svg.querySelector('.flow[data-edge="' + edge + '"]') : null;
    if(line && line.getBBox){
      var bb = line.getBBox();
      if(bb.width || bb.height){ add({x:bb.x, y:bb.y, w:bb.width, h:bb.height}); }
    }
    var area = A.view.visibleArea(null), m = svg.getScreenCTM(), base = m && m.a ? m.a : 1;
    if(x0 === Infinity || !(area.w > 0) || !(area.h > 0)){ A.view.fit(); return; }
    var r = {x:x0 - pad, y:y0 - pad, w:x1 - x0 + 2 * pad, h:y1 - y0 + 2 * pad};
    var k = Math.min(1.4 / base, area.w / r.w, area.h / r.h);
    A.view.restore({k:k, tx:area.x + area.w / 2 - k * (r.x + r.w / 2),
      ty:area.y + area.h / 2 - k * (r.y + r.h / 2)});
  }

  // ---- what the layer shows --------------------------------------------------
  function edgesOf(L){
    if(L === 'all'){ return A.edges.map(function(_e, i){ return i; }); }
    var r = (META.readings || {})[L];
    return r ? r.edges.slice() : [];
  }
  function layerName(L){ return L === 'all' ? 'All layers' : (LAY[L] ? LAY[L].label : L); }
  function plural(n, word){ return n + ' ' + word + (n === 1 ? '' : 's'); }
  function fillLayers(){
    if(!layerPick){ return; }
    var ids = (W.tabs && W.tabs.length ? W.tabs : A.layers.map(function(l){ return l.id; }))
      .concat(['all']);
    layerPick.innerHTML = ids.map(function(L){
      var n = edgesOf(L).length;
      return '<option value="' + esc(L) + '">' + esc(layerName(L))
        + (n ? ' · ' + plural(n, 'flow') : '') + '</option>';
    }).join('');
  }
  function lit(L){
    var on = {};
    A.layerIds(L).forEach(function(id){ on[id] = true; });
    return on;
  }

  // ---- the regions grid -----------------------------------------------------------
  function places(){
    var regs = (META.regions || []).map(function(z, k){
      return {z:z, n:k + 1, y:z.box ? z.box[1] : k, x:z.box ? z.box[0] + z.box[2] / 2 : 0,
        w:z.box ? z.box[2] : 0};
    });
    if(!regs.length){ return {cells:[], rows:0}; }
    var x0 = Math.min.apply(null, regs.map(function(p){ return p.z.box ? p.z.box[0] : 0; }));
    var x1 = Math.max.apply(null, regs.map(function(p){
      return p.z.box ? p.z.box[0] + p.z.box[2] : 0; }));
    var mid = (x0 + x1) / 2;
    regs.forEach(function(p){ p.col = p.x < mid ? 0 : 1; p.span = p.w > (x1 - x0) * 0.6 ? 2 : 1; });
    var oneColumn = regs.every(function(p){ return p.span === 1 && p.col === regs[0].col; });
    var sorted = regs.slice().sort(function(a, b){ return (a.y - b.y) || (a.x - b.x); });
    var bands = [], taken = {};
    sorted.forEach(function(p, i){
      if(oneColumn){ p.col = i % 2; p.row = Math.floor(i / 2); return; }
      var band = 0;
      while(band < bands.length && Math.abs(bands[band] - p.y) > 60){ band++; }
      if(band === bands.length){ bands.push(p.y); }
      if(p.span === 2){ p.col = 0; }
      var r = band;
      while(taken[r + ':' + p.col] || (p.span === 2 && taken[r + ':1'])){ r++; }
      p.row = r;
      taken[r + ':' + p.col] = true;
      if(p.span === 2){ taken[r + ':1'] = true; }
    });
    var used = {};
    regs.forEach(function(p){ used[p.row] = true; });
    var order = Object.keys(used).map(Number).sort(function(a, b){ return a - b; });
    regs.forEach(function(p){ p.row = order.indexOf(p.row); });
    return {cells:regs, rows:order.length};
  }
  function freeCell(cells, rows){
    var taken = {};
    cells.forEach(function(p){
      taken[p.row + ':' + p.col] = true;
      if(p.span === 2){ taken[p.row + ':1'] = true; }
    });
    for(var r = 0; r < rows; r++){
      for(var c = 0; c < 2; c++){ if(!taken[r + ':' + c]){ return {row:r, col:c}; } }
    }
    return null;
  }
  function countWithin(ids, edges){
    var inside = {};
    ids.forEach(function(id){ inside[id] = true; });
    return edges.filter(function(i){
      var e = A.edges[i];
      return inside[e.from] || inside[e.to];
    }).length;
  }
  function regionCell(p, L, on, top, col0){
    var z = p.z, names = byPlace(z.ids || []), n = countWithin(names, edgesOf(L));
    var badge = L === 'structure' ? '' : '<span class="phone-badge'
      + (n && n === top ? ' phone-badge--top' : (n ? '' : ' phone-badge--none')) + '">' + n
      + '<span class="sr-only"> ' + (n === 1 ? 'flow' : 'flows') + '</span></span>';
    return '<button type="button" class="phone-region" data-phone-region="' + esc(z.id)
      + '" style="grid-row:' + (p.row + 1) + ';grid-column:' + (p.col + col0) + ' / span '
      + p.span + '"><span class="phone-region__head"><span class="phone-region__name">' + p.n
      + ' ' + esc(z.label) + '</span>' + badge + '</span>'
      + names.map(function(id){
        return '<span class="phone-name' + (on[id] ? ' on' : '') + '">' + esc(id) + '</span>';
      }).join('') + '</button>';
  }
  function actorsOf(){
    return byPlace(Object.keys(A.detail).filter(function(id){
      return id !== '_meta' && A.detail[id].kind === 'actor'; }));
  }
  function noteText(L){
    if(L === 'structure'){ return 'Each name identifies one component in the region.'; }
    if(L === 'system'){ return 'The number is the quantity of flows to or from an actor.'; }
    return 'The number is the quantity of flows in this layer to or from the region.';
  }
  function hintText(L){
    var open = 'Select a region to open it at a size you can read.';
    if(L === 'structure'){ return open; }
    if(L === 'system'){
      return open + ' Bright names identify components that connect to an actor.';
    }
    return open + ' Bright names identify components with a flow in this layer.';
  }
  function renderGrid(){
    if(!grid){ return; }
    var L = A.state.layer, on = lit(L), edges = edgesOf(L), place = places();
    var actors = actorsOf(), col0 = actors.length ? 2 : 1, cells = place.cells;
    var counts = cells.map(function(p){ return countWithin(p.z.ids || [], edges); });
    var top = Math.max.apply(null, [0].concat(counts));
    var free = freeCell(cells, place.rows), rows = place.rows + (free ? 0 : 1);
    var h = '';
    if(actors.length){
      h += '<button type="button" class="phone-out" data-phone-region="outside" '
        + 'style="grid-row:1 / span ' + Math.max(rows, 1) + ';grid-column:1">'
        + '<span class="phone-out__k">OUTSIDE</span><span class="phone-actors">'
        + actors.map(function(id){
          return '<span class="phone-actor' + (on[id] || L === 'structure' ? '' : ' dim') + '">'
            + esc(id) + '</span>';
        }).join('') + '</span><span class="phone-out__n">' + plural(actors.length, 'actor')
        + '</span></button>';
    }
    h += cells.map(function(p){ return regionCell(p, L, on, top, col0); }).join('');
    var note = '<div class="phone-note' + (free ? '' : ' phone-note--row') + '"'
      + (free ? ' style="grid-row:' + (free.row + 1) + ';grid-column:' + (free.col + col0) + '"'
        : '') + '>' + esc(noteText(L)) + '</div>';
    grid.className = 'phone-grid' + (actors.length ? '' : ' phone-grid--inside');
    grid.innerHTML = h + note;
    if(hint){ hint.textContent = hintText(L); }
  }

  // ---- the list under the grid -------------------------------------------------------
  function series(words){
    return words.length < 2 ? words.join('')
      : words.slice(0, -1).join(', ') + ' and ' + words[words.length - 1];
  }
  function boundaryRows(edges){
    var actors = {}, order = [];
    edges.forEach(function(i){
      var e = A.edges[i];
      [[e.from, 'sends'], [e.to, 'gets']].forEach(function(end){
        var d = A.detail[end[0]];
        if(!d || d.kind !== 'actor'){ return; }
        if(!actors[end[0]]){ actors[end[0]] = {sends:[], gets:[]}; order.push(end[0]); }
        var names = actors[end[0]][end[1]];
        if(names.indexOf(e.art) < 0){ names.push(e.art); }
      });
    });
    return order.map(function(id){
      var a = actors[id], text = [];
      if(a.gets.length){ text.push('Receives ' + series(a.gets) + '.'); }
      if(a.sends.length){ text.push('Sends ' + series(a.sends) + '.'); }
      return '<dt>' + esc(id) + '</dt><dd>' + esc(text.join(' ')) + '</dd>';
    }).join('');
  }
  function flowRows(edges){
    return edges.map(function(i){
      var e = A.edges[i], l = LAY[e.layer];
      var dash = e.evidence === 'structural' || e.evidence === 'declared' ? ' class="dash"' : '';
      return '<li><button type="button" class="phone-flow" data-phone-edge="' + i + '"><i'
        + dash + ' style="--c:' + esc(l ? l.colour : 'var(--ink-3)') + '"></i><span>'
        + esc(e.art) + '</span><small>' + esc(e.from) + ' → ' + esc(e.to)
        + '</small></button></li>';
    }).join('');
  }
  function renderList(){
    if(!list){ return; }
    var L = A.state.layer, edges = edgesOf(L);
    if(L === 'structure' || !edges.length){ list.innerHTML = ''; return; }
    var rows = L === 'system' ? boundaryRows(edges) : '';
    if(rows){
      list.innerHTML = '<h2>WHAT CROSSES THE BOUNDARY</h2><dl class="phone-rows">' + rows
        + '</dl>';
      return;
    }
    list.innerHTML = '<div class="phone-list__head"><h2>' + esc(layerName(L).toUpperCase())
      + '</h2><span class="phone-list__n">' + plural(edges.length, 'flow') + '</span></div>'
      + '<ul class="phone-flows">' + flowRows(edges) + '</ul>';
  }

  // ---- one sequence step --------------------------------------------------------------
  function roles(step){
    var h = '';
    if((step.acts || []).length){
      h += '<span class="phone-tag">ACTS</span>' + step.acts.map(esc).join(', ');
    }
    if((step.measures || []).length){
      h += '<span class="phone-tag phone-tag--meas">MEASURES</span>'
        + step.measures.map(esc).join(', ');
    }
    return h;
  }
  function renderStep(){
    var at = P.journey.state(), j = A.journeys[at.j];
    if(!j || !call){ return; }
    if(!j.steps.length){
      call.innerHTML = '<p class="phone-call__say">This sequence has no steps.</p>';
      if(stepNav){ stepNav.innerHTML = ''; }
      if(prevBtn){ prevBtn.disabled = true; }
      if(nextBtn){ nextBtn.disabled = true; }
      return;
    }
    var step = j.steps[at.s] || {}, e = A.edges[step.edge];
    call.innerHTML = '<div class="phone-call__head"><span class="phone-call__n">' + (at.s + 1)
      + '</span><span class="phone-call__art">' + esc(e ? e.art : 'Step ' + (at.s + 1))
      + '</span>' + (e ? '<span class="phone-call__ends">' + esc(e.from) + ' → ' + esc(e.to)
        + '</span>' : '') + '</div><p class="phone-call__say">' + esc(step.say || '')
      + '</p><div class="phone-call__roles">' + roles(step) + '</div>';
    if(stepNav){
      stepNav.innerHTML = j.steps.map(function(_s, k){
        return '<button type="button" data-phone-step="' + k + '" aria-label="Step ' + (k + 1)
          + '"' + (k === at.s ? ' aria-current="step"' : '') + (k < at.s ? ' class="done"' : '')
          + '>' + (k + 1) + '</button>';
      }).join('');
    }
    if(prevBtn){ prevBtn.disabled = at.s <= 0; }
    if(nextBtn){ nextBtn.disabled = at.s >= j.steps.length - 1; }
  }

  // ---- the phone state ------------------------------------------------------------
  function stateOf(){
    if(!phone()){ return ''; }
    var mode = P.mode(), focus = !!A.state.focus;
    if(mode === 'change'){ return 'change'; }
    if(mode === 'trace'){
      if(focus){ return 'map'; }
      if(!P.journey.active()){ return 'index'; }
      return full ? 'full' : 'step';
    }
    return focus || opened ? 'map' : 'grid';
  }
  function barText(){
    var mode = P.mode(), at = P.journey.state(), j = A.journeys[at.j];
    if(mode === 'trace' && j){
      return ['Show the step', 'STEP ' + (at.s + 1) + ' OF ' + j.steps.length];
    }
    var z = (META.regions || []).filter(function(r){ return r.id === opened; })[0];
    var k = (META.regions || []).indexOf(z);
    var title = z ? (k + 1) + ' ' + z.label : (opened === 'outside' ? 'OUTSIDE'
      : layerName(A.state.layer).toUpperCase());
    return ['All regions', title];
  }
  function placeChooser(on){
    // The sequence chooser is in the phone head on a phone, else in the Sequences toolbar.
    var to = byId(on ? 'phone-seq' : 'tracecontrols');
    if(seqBox.parentNode !== to){
      to.insertBefore(seqBox, on ? null : to.querySelector('.seq-seg')); }
  }
  function update(){
    var s = stateOf(), before = body.dataset.phone || '';
    placeChooser(!!s);
    if(s){ body.dataset.phone = s; } else { delete body.dataset.phone; }
    if(!s){ return false; }
    if(layerPick){ layerPick.value = A.state.layer; }
    if(question){
      var q = byId('layer-question');
      question.textContent = P.mode() === 'understand' && q ? q.textContent
        : (LAY[A.state.layer] ? LAY[A.state.layer].question : '');
    }
    if(s === 'map' || s === 'full'){
      var t = barText();
      if(backBtn){ backBtn.textContent = t[0]; }
      if(barTitle){ barTitle.textContent = t[1]; }
    }
    if(s === 'grid'){ renderGrid(); renderList(); }
    if(s === 'step' || s === 'index'){ renderStep(); }
    return before !== s;
  }
  function openRegion(id){
    gridScroll = window.scrollY || 0;
    opened = id || 'all';
    update();
    window.scrollTo(0, 0);
    if(id === 'outside'){ frameIds(actorsOf(), 24, -1); }
    else if(id){ A.view.frameRegion(id); }
    else { A.view.fit(); }
  }
  function toGrid(){
    opened = '';
    if(A.state.focus){ A.clear(); }
    update();
    window.scrollTo(0, gridScroll);
  }
  function frameStep(){
    // Board 8 frames the step closely: its two cards and the line between them.
    var st = A.state.journey, e = st ? A.edges[st.edge] : null;
    if(!st || st.whole || body.dataset.phone !== 'step'){ return; }
    var ids = (st.acts || []).concat(st.measures || []);
    if(e){ ids.push(e.from, e.to); }
    frameIds(ids, 10, e ? st.edge : -1);
  }
  function reframeStep(){
    if(P.journey.active() && A.state.journey){ A.setJourney(A.state.journey); frameStep(); }
  }
  function goStep(k){
    // One step, framed in the small map: the phone frame is too small to keep the zoom.
    var j = A.journeys[P.journey.state().j];
    if(!j || k < 0 || k >= j.steps.length){ return; }
    if(P.sequence && P.sequence.go){ P.sequence.go('steps', k, 'frame'); }
    else { P.journey.step(k); }
  }

  // ---- controls -----------------------------------------------------------------
  if(grid){ grid.addEventListener('click', function(e){
    var b = e.target.closest && e.target.closest('[data-phone-region]');
    if(b){ openRegion(b.dataset.phoneRegion); }
  }); }
  var openAll = byId('phone-open');
  if(openAll){ openAll.addEventListener('click', function(){ openRegion(''); }); }
  if(list){ list.addEventListener('click', function(e){
    var b = e.target.closest && e.target.closest('[data-phone-edge]');
    if(!b){ return; }
    gridScroll = window.scrollY || 0;
    opened = 'all';
    A.inspectFlow(+b.dataset.phoneEdge);
    window.scrollTo(0, 0);
  }); }
  if(layerPick){ layerPick.addEventListener('change', function(){
    if(P.mode() !== 'understand'){ P.setMode('understand'); }
    P.setLayer(layerPick.value);
  }); }
  if(backBtn){ backBtn.addEventListener('click', function(){
    var mode = P.mode();
    if(mode === 'trace'){
      full = false;
      if(A.state.focus){ P.journey.back(); } else { update(); reframeStep(); }
      return;
    }
    toGrid();
  }); }
  if(fullBtn){ fullBtn.addEventListener('click', function(){
    full = true; update(); window.scrollTo(0, 0); A.view.fit();
  }); }
  if(stepNav){ stepNav.addEventListener('click', function(e){
    var b = e.target.closest && e.target.closest('[data-phone-step]');
    if(b){ goStep(+b.dataset.phoneStep); }
  }); }
  if(prevBtn){ prevBtn.addEventListener('click', function(){
    goStep(P.journey.state().s - 1); }); }
  if(nextBtn){ nextBtn.addEventListener('click', function(){
    goStep(P.journey.state().s + 1); }); }
  // Map in the views, or Escape with nothing selected, goes back to the regions grid.
  all('.views [data-mode="understand"]').forEach(function(b){
    b.addEventListener('click', function(){
      if(phone() && (opened || A.state.focus)){ toGrid(); }
    });
  });
  document.addEventListener('keydown', function(e){
    if(e.key === 'Escape' && body.dataset.phone === 'map' && P.mode() === 'understand'
      && !A.state.focus && opened){ toGrid(); }
  });

  // ---- events from the shell, the map and the sequence script ------------------------
  // The phone shows one step at a time (board 8): the whole route view of a
  // sequence opens at its current step.
  svg.addEventListener('systemap:step', function(e){
    var d = e.detail || {}, changed = update(), j = A.journeys[d.j];
    if(phone() && d.view === 'whole' && !A.state.focus && j && j.steps.length){
      goStep(Math.max(0, P.journey.state().s));
      return;
    }
    renderStep();
    if(changed && body.dataset.phone === 'step'){ reframeStep(); } else { frameStep(); }
  });
  svg.addEventListener('systemap:mode', function(e){
    full = false;
    if(e.detail && e.detail.mode !== 'understand'){ opened = ''; }
    update();
  });
  ['systemap:layer', 'systemap:select', 'systemap:clear', 'systemap:panel',
    'systemap:workspace'].forEach(function(name){ svg.addEventListener(name, update); });
  function onMedia(){
    if(update() && body.dataset.phone === 'step'){ reframeStep(); }
  }
  if(media){
    if(media.addEventListener){ media.addEventListener('change', onMedia); }
    else if(media.addListener){ media.addListener(onMedia); }
  }
  fillLayers();
  update();
})();
"""


def _esc(text: object) -> str:
    return html_mod.escape(str(text), quote=True)


def html(model: Model, meaning: Meaning) -> str:
    """Give the phone parts of the page. Wide windows hide them.

    The script moves the head part above the map and fills the regions grid,
    the list and the step from the map data. It moves the sequence chooser of
    the Sequences toolbar into the head part."""
    del model, meaning
    return (
        '<div class="phone-head" id="phone-head">'
        '<div class="phone-pick"><label class="sr-only" for="phone-layer">Layer</label>'
        '<select class="phone-select" id="phone-layer"></select>'
        '<p class="phone-question" id="phone-question"></p></div>'
        '<div class="phone-seq" id="phone-seq"></div>'
        '<div class="phone-bar"><button type="button" id="phone-back">All regions</button>'
        '<p class="phone-bar__title" id="phone-title"></p></div></div>'
        '<button type="button" class="phone-full" id="phone-full">Full map</button>'
        '<div class="phone-body" id="phone-body">'
        '<div class="phone-home"><div class="phone-grid" id="phone-grid" role="group" '
        'aria-label="Regions"></div><div class="phone-after">'
        '<p class="phone-hint" id="phone-hint"></p>'
        '<button type="button" class="phone-open" id="phone-open">Open the full map</button></div>'
        '<section class="phone-list" id="phone-list"></section>'
        "</div>"
        '<section class="phone-step" id="phone-step" aria-label="Sequence step">'
        '<div class="phone-call" id="phone-call" aria-live="polite"></div>'
        '<nav class="phone-steps" id="phone-steps" aria-label="Steps"></nav>'
        '<div class="phone-move"><button type="button" id="phone-prev">Previous</button>'
        '<button type="button" class="primary" id="phone-next">Next</button></div>'
        "</section></div>"
    )
