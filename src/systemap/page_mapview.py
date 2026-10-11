"""The Map view: the layer row, the title block and the zoom controls.

The Map view uses the design of the Sequences view. A row under the header
holds the layer control and the zoom controls. The layer control is the
segmented control of the Sequences toolbar. The title block gives a small
label with the layer name and its position, and then the question of the
layer.
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
/* ---- the Map view: the layer row --------------------------------------- */
body:not([data-mode="understand"]):not([data-mode="review"]) .layer-controls,
body[data-phone] .layer-controls{display:none}
.seq-seg button:focus-visible{outline-offset:-3px}
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

  eyebrow();
})();
"""
