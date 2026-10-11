"""The Map view: the layer row, the title block, the zoom controls and the panel for a layer.

The Map view uses the design of the Sequences view. A row under the header
holds the layer control and the zoom controls. The layer control is the
segmented control of the Sequences toolbar. The title block gives a small
label with the layer name and its position, and then the question of the
layer. On a wide window the panel opens with the page. With no selection, it
shows the current layer in the card style of the sequence steps: one card for
each flow, actor or region. A pointer or keyboard focus on a flow card shows a
preview of that flow on the map. The title block and the panel fade in when
the layer changes. The text does not move.
"""

from __future__ import annotations

import html
from typing import Any

from systemap.page_map_icons import icon


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def toolbar(layers: list[Any]) -> str:
    """Give the layer row: the label and one segment for each layer, then All."""
    tabs = "".join(
        f'<button type="button" role="tab" data-layer-btn="{esc(layer.id)}" '
        f'aria-selected="false" aria-pressed="false" title="{esc(layer.question)}">'
        f"{esc(layer.label)}</button>"
        for layer in layers
    )
    return (
        '<div class="layer-controls" id="layercontrols">'
        '<span class="trace-controls__label" id="layer-label">Layer</span>'
        f'<div class="seq-seg layers" role="tablist" aria-labelledby="layer-label">{tabs}'
        '<button type="button" role="tab" data-layer-btn="all" aria-selected="false" '
        'aria-pressed="false" title="All flows of all layers">All</button></div></div>'
    )


def title(question: str) -> str:
    """Give the title block: the small label and the question."""
    return (
        '<div class="mapbar" id="mapbar"><p class="mapbar__label" id="mapbar-label" hidden></p>'
        f'<h2 class="question" id="layer-question">{esc(question)}</h2></div>'
    )


def zoom() -> str:
    """Give the zoom controls: zoom out, the zoom value, zoom in, and fit.

    The zoom value is a button. It sets the actual size, 100 percent."""
    return (
        '<div class="zoom" role="group" aria-label="Zoom"><div class="zoom__seg">'
        f'<button type="button" data-zoom="out" aria-label="Zoom out" title="Zoom out">'
        f"{icon('zoom-out')}</button>"
        '<button type="button" data-zoom="actual" id="zpct" aria-pressed="false" '
        'aria-label="Zoom to 100 percent" title="Actual size"></button>'
        f'<button type="button" data-zoom="in" aria-label="Zoom in" title="Zoom in">'
        f"{icon('zoom-in')}</button></div>"
        '<button type="button" data-zoom="fit" aria-pressed="true" aria-label="Fit" '
        f'title="Fit: show the full map">{icon("fit")}</button></div>'
    )


CSS = r"""
/* ---- the Map view: the layer row and the panel for a layer --------------- */
body:not([data-mode="understand"]):not([data-mode="review"]) .layer-controls,
body[data-phone] .layer-controls{display:none}
.seq-seg button:focus-visible{outline-offset:-3px}
.lay{display:flex;flex-direction:column;gap:14px}
.readpanel .lay-text{margin:0;font:13px/20px var(--fs);color:var(--ink-2)}
.lay-card{color:var(--ink-2)}
.lay-card .seq-step__head{color:var(--ink)}
.lay-card .seq-n{color:var(--ink-2)}
.lay-g{align-self:center;justify-self:center;width:16px;border-top:2px solid var(--c)}
.lay-g.dash{border-top-style:dashed}
.lay-g.actor{width:14px;height:10px;border:1px dashed var(--card-line);border-radius:2px}
"""

SCRIPT = r"""
(function(){
  var svg = document.getElementById('schematic');
  if(!svg || !svg.systemap || !svg.page){ return; }
  var A = svg.systemap, P = svg.page, W = window.systemapWorkspace || {};
  var META = A.detail._meta || {}, LAY = {}, TABS = W.tabs || [];
  A.layers.forEach(function(l){ LAY[l.id] = l; });
  function byId(id){ return document.getElementById(id); }
  function all(sel, root){
    return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function plural(n, word){ return n + ' ' + word + (n === 1 ? '' : 's'); }
  function reduced(){
    return document.documentElement.dataset.reduceMotion === 'true' ||
      !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }
  function mapMode(){ var m = P.mode(); return m === 'understand' || m === 'review'; }

  // ---- the title block: the layer name and its position ----------------------
  function eyebrow(){
    var L = A.state.layer, label = byId('mapbar-label');
    if(!label || !mapMode()){ return; }
    var k = TABS.indexOf(L);
    label.textContent = L === 'all' || k < 0 ? 'ALL LAYERS'
      : String(LAY[L] ? LAY[L].label : L).toUpperCase() + ' · LAYER ' + (k + 1) + ' OF '
        + TABS.length;
    label.hidden = false;
  }
  ['systemap:workspace', 'systemap:mode'].forEach(function(name){
    svg.addEventListener(name, eyebrow); });

  // ---- a layer change: the title block and the panel fade in -----------------
  svg.addEventListener('systemap:layer', function(){
    if(reduced() || !mapMode()){ return; }
    [byId('mapbar'), byId('inspector-empty')].forEach(function(n){
      if(n && n.animate){ n.animate([{opacity:.2}, {opacity:1}], {duration:180,
        easing:'ease-out'}); }
    });
  });

  // ---- the panel for a layer: one card for each flow, actor or region --------
  function edgesOf(L){
    var r = META.readings[L], out = [];
    A.edges.forEach(function(_e, i){
      if(L === 'all' || (r && r.edges.indexOf(i) >= 0)){ out.push(i); } });
    return out;
  }
  function firstSentence(text){
    var m = String(text || '').match(/^[^.]*\./);
    return m ? m[0] : String(text || '');
  }
  function series(list){
    return list.length < 2 ? list.join('')
      : list.slice(0, -1).join(', ') + ' and ' + list[list.length - 1];
  }
  function text(L){
    // The guide text of the layer, or else the description of the layer.
    var g = (W.guide || []).filter(function(s){ return s.layer === L; })[0];
    if(g){ return g.text; }
    var sub = L === 'all' ? 'all flows of all layers' : (LAY[L] ? LAY[L].sub : '');
    return sub ? sub.charAt(0).toUpperCase() + sub.slice(1) + '.' : '';
  }
  function head(L, count){
    var t = text(L);
    return '<div class="seq-row"><p class="seq-kicker">LAYER</p><span class="seq-count">'
      + count + '</span></div><div class="seq-head"><h2 class="seq-title">'
      + esc(L === 'all' ? 'All layers' : (LAY[L] ? LAY[L].label : L)) + '</h2></div>'
      + (t ? '<p class="lay-text">' + esc(t) + '</p>' : '');
  }
  function card(attr, glyph, top, say){
    return '<li><button type="button" class="seq-step lay-card" ' + attr + '>' + glyph
      + '<span class="seq-step__head">' + top + '</span>'
      + (say ? '<span class="seq-step__say">' + esc(say) + '</span>' : '') + '</button></li>';
  }
  function besideNote(list){
    var on = {};
    (A.besideEdges || []).forEach(function(i){ on[i] = true; });
    return list.some(function(i){ return on[i]; }) ? '<p class="seq-note">Labels that do not '
      + 'fit on a line are in this list. Point to a line to read its label.</p>' : '';
  }
  function flowCards(list){
    return list.map(function(i){
      var e = A.edges[i], l = LAY[e.layer];
      var dash = e.evidence === 'structural' || e.evidence === 'declared' ? ' dash' : '';
      return card('data-read-edge="' + i + '"', '<i class="lay-g' + dash + '" style="--c:'
        + esc(l ? l.colour : 'var(--ink-3)') + '"></i>',
        esc(e.from + ' → ' + e.to + ' · ' + e.art), firstSentence(e.say));
    }).join('');
  }
  function actorCards(list){
    var actors = {}, order = [];
    list.forEach(function(i){
      var e = A.edges[i];
      [[e.from, 'sends'], [e.to, 'gets']].forEach(function(end){
        var d = A.detail[end[0]];
        if(!d || d.kind !== 'actor'){ return; }
        if(!actors[end[0]]){ actors[end[0]] = {sends:[], gets:[]}; order.push(end[0]); }
        var arts = actors[end[0]][end[1]];
        if(arts.indexOf(e.art) < 0){ arts.push(e.art); }
      });
    });
    return order.map(function(id){
      var a = actors[id], say = [];
      if(a.gets.length){ say.push('Receives ' + series(a.gets) + '.'); }
      if(a.sends.length){ say.push('Sends ' + series(a.sends) + '.'); }
      return card('data-read-go="' + esc(id) + '"', '<i class="lay-g actor"></i>', esc(id),
        say.join(' '));
    }).join('');
  }
  function regionCards(){
    return (META.regions || []).map(function(r, k){
      return card('data-read-zone="' + esc(r.id) + '"', '<span class="seq-n">' + (k + 1)
        + '</span>', esc(r.label) + ' · ' + plural(r.ids.length, 'component'), r.ids.join(', '));
    }).join('');
  }
  function reader(L){
    if(!mapMode()){ return null; }
    var list = L === 'structure' ? [] : edgesOf(L), cards, count;
    if(L === 'structure'){
      var parts = Object.keys(A.detail).filter(function(id){
        return id !== '_meta' && A.detail[id].kind !== 'actor'; }).length;
      var n = (META.regions || []).length;
      cards = regionCards();
      count = plural(parts, 'component') + (n ? ' · ' + plural(n, 'region') : '');
    } else {
      var actors = A.layerIds(L).filter(function(id){
        return A.detail[id] && A.detail[id].kind === 'actor'; }).length;
      cards = L === 'system' ? actorCards(list) : flowCards(list);
      count = plural(list.length, 'flow') + (actors ? ' · ' + plural(actors, 'actor') : '');
    }
    return {html:'<section class="read__section lay" aria-label="Layer">' + head(L, count)
      + (cards ? '<ol class="seq-steps">' + cards + '</ol>'
        : '<p class="seq-note">This layer has no ' + (L === 'structure' ? 'regions' : 'flows')
          + '.</p>') + besideNote(list) + '</section>', bind:bind};
  }
  function bind(root){
    all('[data-read-edge]', root).forEach(function(b){
      var i = +b.dataset.readEdge;
      function off(){ if(A.unpeek){ A.unpeek(); } else { A.peek(-1); } }
      b.addEventListener('mouseenter', function(){ A.peek(i); });
      b.addEventListener('focus', function(){ A.peek(i); });
      b.addEventListener('mouseleave', off);
      b.addEventListener('blur', off);
      b.addEventListener('click', function(){ A.inspectFlow(i); });
    });
    all('[data-read-go]', root).forEach(function(b){
      b.addEventListener('click', function(){ A.select(b.dataset.readGo); }); });
    all('[data-read-zone]', root).forEach(function(b){
      b.addEventListener('click', function(){ A.view.frameRegion(b.dataset.readZone); }); });
  }
  P.readers.push(reader);

  // ---- the panel opens with the page on a wide window --------------------------
  if(window.innerWidth > 820 && P.mode() === 'understand'){ P.openPanel(); }
  eyebrow();
  if(P.renderRead){ P.renderRead(); }
})();
"""
