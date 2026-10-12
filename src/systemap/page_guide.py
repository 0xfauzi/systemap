"""The guide for a first visit and the Details panel for the Map view.

The guide has up to five steps: the system boundary, the parts, the data,
the control and one operation. Each step selects a layer, or starts the
first sequence. The Details panel shows a section about the selected layer
first and the same steps after it. Other scripts give that section through
`svg.page.readers`.
"""

from __future__ import annotations

from typing import Any

from systemap.model import Meaning, Model, all_layers, reading

WORDS = ["No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"]


def _count(n: int, word: str) -> str:
    name = WORDS[n] if 0 <= n < len(WORDS) else str(n)
    return f"{name} {word}{'' if n == 1 else 's'}"


def _boundary(model: Model, meaning: Meaning) -> dict[str, str] | None:
    edges = reading(model, meaning, "system")[0]
    if not edges:
        return None
    actors = {c.id for c in model.components if c.kind == "actor"}
    parts = [c for c in model.components if c.kind != "actor"]
    touched = {e for i in edges for e in (model.flows[i].src, model.flows[i].dst)} - actors
    verb = "is" if len(actors) == 1 else "are"
    return {
        "layer": "system",
        "title": "The system boundary",
        "text": f"{_count(len(actors), 'actor')} {verb} outside the source code. "
        f"They connect to {len(touched)} of the {len(parts)} components. "
        "Each line is one flow. Its label names the artifact.",
    }


def _parts(model: Model) -> dict[str, str]:
    parts = [c for c in model.components if c.kind != "actor"]
    text = "Each card is one component. "
    if model.regions:
        text += (
            "A region contains components with related functions. "
            f"This map has {len(parts)} components in {len(model.regions)} regions."
        )
    else:
        text += f"This map has {len(parts)} components."
    return {"layer": "structure", "title": "The parts", "text": text}


def steps(model: Model, meaning: Meaning) -> list[dict[str, Any]]:
    """Give the guide steps that this map can show, in reading order."""
    ids = {layer.id for layer in all_layers(model, meaning)}
    out: list[dict[str, Any]] = []
    boundary = _boundary(model, meaning) if "system" in ids else None
    if boundary:
        out.append(boundary)
    out.append(_parts(model))
    if "data" in ids and reading(model, meaning, "data")[0]:
        out.append(
            {
                "layer": "data",
                "title": "The data",
                "text": "A data flow moves an artifact, for example a file or a record, from "
                "one component to a different component. The label on the line names "
                "the artifact.",
            }
        )
    if "control" in ids and reading(model, meaning, "control")[0]:
        out.append(
            {
                "layer": "control",
                "title": "The control",
                "text": "A control flow causes a different component to start work, for "
                "example with a command or a call.",
            }
        )
    started = [k for k, j in enumerate(meaning.journeys) if j.steps]
    if started:
        label = meaning.journeys[started[0]].label
        out.append(
            {
                "journey": started[0],
                "title": "An operation",
                "text": "A sequence shows the steps of one operation, in their order. "
                f"Start with this sequence: {label}.",
            }
        )
    return out[:5]


def card() -> str:
    """Give the first-visit guide card. The script fills it and shows it."""
    return (
        '<section class="guide" id="guide" aria-label="Guide" hidden>'
        '<div class="guide__top"><span class="guide__kicker">READ THE MAP</span>'
        '<span class="guide__count" id="guide-count"></span></div>'
        '<div class="guide__bar" id="guide-bar" aria-hidden="true"></div>'
        '<h3 class="guide__title" id="guide-title"></h3>'
        '<p class="guide__text" id="guide-text"></p>'
        '<div class="guide__actions"><button type="button" class="primary" id="guide-next">'
        'Next</button><button type="button" id="guide-close">Close</button></div>'
        '<p class="guide__note">The guide opens on the first visit only. The Details panel '
        "gives the same steps.</p></section>"
    )


CSS = r"""
.guide{position:absolute;right:24px;bottom:54px;width:340px;max-width:calc(100% - 48px);
z-index:6;box-sizing:border-box;padding:16px 18px;border:1px solid var(--line-2);border-radius:10px;
background:var(--surface);box-shadow:0 12px 32px color-mix(in srgb,#000 45%,transparent);
display:flex;flex-direction:column;gap:10px;animation:systemapguide .24s ease-out both}
:root[data-theme="light"] .guide{box-shadow:0 12px 32px color-mix(in srgb,#5a4a2a 18%,transparent)}
.guide__top{display:flex;justify-content:space-between;align-items:baseline}
.guide__kicker{font:600 11px/16px var(--fm);letter-spacing:.08em;color:var(--ink-3)}
.guide__count{font:12px var(--fm);color:var(--ink-3)}
.guide__bar{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:4px}
.guide__bar span{height:3px;border-radius:2px;background:var(--line-2);
transition:background .2s ease-out}
.guide__bar span.on{background:var(--ink)}
.guide__title{margin:0;font:600 17px/23px var(--fs);color:var(--ink)}
.guide__text{margin:0;font:14px/21px var(--fs);color:var(--ink-2)}
.guide__actions{display:flex;gap:8px;padding-top:4px}
.guide__actions button{height:36px;min-height:36px;padding:0 14px;font-size:13px;
border:1px solid var(--line-2);border-radius:6px;background:transparent;color:var(--ink-2)}
.guide__actions .primary{flex:1;border-color:var(--ink);background:var(--ink);color:var(--bg);
font-weight:600}
.guide__actions .primary:hover{background:var(--ink);color:var(--bg);opacity:.9}
.guide__note{margin:0;font:12px/17px var(--fs);color:var(--ink-3)}
@keyframes systemapguide{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.read{display:flex;flex-direction:column;gap:24px}
.read__guide{display:flex;flex-direction:column;gap:8px;padding-top:14px;
border-top:1px solid var(--line)}
.read__steps{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:2px}
.read__step{width:100%;height:30px;min-height:30px;padding:0 4px;display:grid;
grid-template-columns:20px minmax(0,1fr) auto;gap:10px;align-items:center;border:0;
border-radius:4px;background:transparent;text-align:left}
.read__step b{width:20px;height:20px;border:1px solid var(--line-2);border-radius:50%;
display:inline-flex;align-items:center;justify-content:center;font:600 11px/1 var(--fm);
color:var(--ink-3)}
.read__step[aria-current="true"] b{border:0;background:var(--accent);color:var(--on-accent)}
.read__step span{font:13px/18px var(--fs);color:var(--ink)}
.read__step small{font:12px var(--fs);color:var(--ink-3)}
.read__q{margin:0;font:500 17px/24px var(--fs);color:var(--ink)}
"""

SCRIPT = r"""
(function(){
  var svg = document.getElementById('schematic');
  if(!svg || !svg.systemap || !svg.page){ return; }
  var A = svg.systemap, P = svg.page, W = window.systemapWorkspace || {};
  var STEPS = W.guide || [], KEY = 'systemap-guide';
  function byId(id){ return document.getElementById(id); }
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  var LAY = {};
  A.layers.forEach(function(l){ LAY[l.id] = l; });
  var card = byId('guide'), read = byId('inspector-empty'), g = 0;

  // ---- the guide card -------------------------------------------------------
  function seen(){ try { return localStorage.getItem(KEY) === 'done'; } catch(e){ return true; } }
  function done(){ try { localStorage.setItem(KEY, 'done'); } catch(e){} }
  function apply(step){
    if(step.journey !== undefined){
      hideCard(); P.setMode('trace'); P.journey.start(step.journey); return;
    }
    if(P.mode() !== 'understand'){ P.setMode('understand'); }
    P.setLayer(step.layer);
  }
  function renderCard(){
    if(!card || !STEPS.length){ return; }
    var step = STEPS[g], nxt = STEPS[g + 1];
    byId('guide-count').textContent = (g + 1) + ' of ' + STEPS.length;
    byId('guide-bar').innerHTML = STEPS.map(function(_s, k){
      return '<span class="' + (k <= g ? 'on' : '') + '"></span>'; }).join('');
    byId('guide-title').textContent = step.title;
    byId('guide-text').textContent = step.text;
    byId('guide-next').textContent = nxt ? 'Next: ' + nxt.title
      : (step.journey !== undefined ? 'Start the sequence' : 'Close');
  }
  // ---- the map moves clear of the card (board 10) ---------------------------
  // The zoom stays. The map moves left until the card does not cover it, but
  // not past the left edge of the map frame. When the card closes, the map
  // goes back to Fit if the reader did not move it.
  var moved = null;
  function clearOfCard(){
    var view = svg.querySelector('.view');
    if(!card || card.hidden || !view || !A.view.isFit()){ return; }
    var m = view.getBoundingClientRect(), c = card.getBoundingClientRect();
    var frame = svg.getBoundingClientRect();
    if(m.bottom <= c.top || m.top >= c.bottom){ return; }
    var dx = Math.min(m.right - (c.left - 32), m.left - (frame.left + 24));
    var v = A.view.snapshot(), base = A.view.zoom() / v.k;
    if(!(dx > 0) || !(base > 0)){ return; }
    moved = {k:v.k, tx:v.tx - dx / base, ty:v.ty};
    A.view.restore(moved, true);
  }
  function hideCard(){
    if(card && !card.hidden){
      card.hidden = true;
      var v = A.view.snapshot();
      if(moved && Math.abs(v.tx - moved.tx) < 0.5 && Math.abs(v.ty - moved.ty) < 0.5
        && Math.abs(v.k - moved.k) < 1e-3){ A.view.fit(); }
      moved = null;
    }
    done();
  }
  function goTo(k){ g = k; renderCard(); apply(STEPS[g]); render(); }
  if(card){
    byId('guide-next').addEventListener('click', function(){
      if(g + 1 < STEPS.length){ goTo(g + 1); }
      else if(STEPS[g].journey !== undefined){ apply(STEPS[g]); }
      else { hideCard(); }
    });
    byId('guide-close').addEventListener('click', hideCard);
    card.addEventListener('keydown', function(e){
      if(e.key === 'Escape'){ hideCard(); e.stopPropagation(); }
    });
  }
  svg.addEventListener('systemap:mode', function(e){
    if(card && e.detail.mode !== 'understand'){ card.hidden = true; }
  });

  // ---- the Details panel -----------------------------------------------------
  // The section for the layer comes first: page_mapview and page_groups give
  // it through P.readers. The guide steps follow it as a short list.
  function section(L){
    var readers = P.readers || [];
    for(var k = 0; k < readers.length; k++){
      var out = readers[k](L);
      if(out){ return out; }
    }
    return {html:'<section class="read__section"><p class="read__q">'
      + esc(LAY[L] ? LAY[L].question : '') + '</p></section>'};
  }
  function guideHtml(L){
    var at = -1;
    STEPS.forEach(function(s, k){ if(s.layer === L && at < 0){ at = k; } });
    return '<section class="read__guide" aria-label="Guide"><div class="seq-row">'
      + '<h3 class="seq-kicker">READ THE MAP</h3><span class="seq-count">'
      + (at >= 0 ? (at + 1) + ' of ' : '') + STEPS.length + '</span></div>'
      + '<ol class="read__steps">' + STEPS.map(function(s, k){
        return '<li><button type="button" class="read__step" data-guide="' + k
          + '" aria-current="' + (k === at) + '"><b>' + (k + 1) + '</b><span>' + esc(s.title)
          + '</span><small>' + esc(s.layer ? (LAY[s.layer] ? LAY[s.layer].label : s.layer)
          : 'Sequence') + '</small></button></li>';
      }).join('') + '</ol></section>';
  }
  function render(){
    if(!read || read.hidden){ return; }
    var L = A.state.layer, sec = section(L);
    read.innerHTML = '<div class="read">' + sec.html + (STEPS.length ? guideHtml(L) : '')
      + '</div>';
    Array.prototype.slice.call(read.querySelectorAll('[data-guide]')).forEach(function(b){
      b.addEventListener('click', function(){ g = +b.dataset.guide; renderCard();
        apply(STEPS[g]); });
    });
    if(sec.bind){ sec.bind(read); }
  }
  ['systemap:layer', 'systemap:panel', 'systemap:mode', 'systemap:clear'].forEach(function(name){
    svg.addEventListener(name, render);
  });
  P.renderRead = render;
  if(card && STEPS.length && !seen() && P.mode() === 'understand'){
    // The map moves after the Map view opens the panel: the frame then has its width.
    card.hidden = false; renderCard(); P.afterBoot = clearOfCard;
  }
  render();
})();
"""
