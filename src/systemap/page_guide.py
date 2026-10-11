"""The guide for a first visit and the Read panel for the Map view.

The guide has up to five steps: the system boundary, the parts, the data,
the control and one operation. Each step selects a layer, or starts the
first sequence. The Read panel lists the same steps and a section about the
selected layer. Other scripts can give that section through `svg.page.readers`.
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
        '<p class="guide__note">The guide opens on the first visit only. Read opens it '
        "again.</p></section>"
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
.read{display:flex;flex-direction:column;gap:18px}
.read__head{display:flex;justify-content:space-between;align-items:baseline}
.read__kicker,.read__count{font:600 11px/16px var(--fm);letter-spacing:.08em;color:var(--ink-3)}
.read__count{font-weight:400;letter-spacing:0;font-size:12px}
.read__steps{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:6px}
.read__step{width:100%;display:grid;grid-template-columns:24px minmax(0,1fr) auto;gap:2px 10px;
align-items:baseline;padding:11px 14px;border:1px solid var(--line);border-radius:8px;
background:transparent;text-align:left;color:var(--ink-2);font-size:13px}
.read__step b{font:600 11px var(--fm);color:var(--ink-3)}
.read__step span{font:500 14px/20px var(--fs);color:var(--ink)}
.read__step small{font:12px var(--fs);color:var(--ink-3)}
.read__step[aria-current="true"]{border-color:var(--accent);background:var(--raised)}
.read__step[aria-current="true"] b{color:var(--accent)}
.read__step p{grid-column:2/-1;margin:6px 0 0;font:13px/20px var(--fs);color:var(--ink-2)}
.read__section h3{margin:0 0 6px;font:600 11px/16px var(--fm);letter-spacing:.08em;
color:var(--ink-3)}
.read__q{margin:0 0 10px;font:500 17px/24px var(--fs);color:var(--ink)}
.read__rows{display:grid;grid-template-columns:auto minmax(0,1fr);gap:10px 16px;margin:0}
.read__rows dt{font:600 13px/20px var(--fm);color:var(--ink)}
.read__rows dd{margin:0;font:13px/20px var(--fs);color:var(--ink-2)}
.read__flows{list-style:none;margin:0;padding:0;display:flex;flex-direction:column}
.read__flow{width:100%;display:grid;grid-template-columns:18px minmax(0,1fr) auto;gap:10px;
align-items:center;padding:7px 4px;border:0;border-bottom:1px solid var(--line);border-radius:0;
background:transparent;text-align:left;min-height:36px}
.read__flow:hover{background:var(--raised)}
.read__flow i{display:block;border-top:2px solid var(--c,var(--ink-3))}
.read__flow i.dash{border-top-style:dashed}
.read__flow span{font:13px/18px var(--fs);color:var(--ink)}
.read__flow small{font:12px var(--fm);color:var(--ink-3);white-space:nowrap}
.read__note{margin:0;font:12px/18px var(--fs);color:var(--ink-3)}
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

  // ---- the Read panel --------------------------------------------------------
  function edgesOf(L){
    var out = [];
    A.edges.forEach(function(e, i){
      var reading = A.detail._meta.readings[L];
      if(L === 'all' || (reading && reading.edges.indexOf(i) >= 0)){ out.push(i); }
    });
    return out;
  }
  function besideNote(L){
    var on = {}, any = false;
    (A.besideEdges || []).forEach(function(i){ on[i] = true; });
    edgesOf(L).forEach(function(i){ if(on[i]){ any = true; } });
    return any ? '<p class="read__note">Labels that do not fit on a line are in this list. '
      + 'Point to a line to read its label.</p>' : '';
  }
  function series(list){
    return list.length < 2 ? list.join('')
      : list.slice(0, -1).join(', ') + ' and ' + list[list.length - 1];
  }
  function boundary(L){
    if(L !== 'system'){ return null; }
    var actors = {}, order = [];
    edgesOf(L).forEach(function(i){
      var e = A.edges[i];
      [[e.from, 'sends'], [e.to, 'gets']].forEach(function(end){
        var d = A.detail[end[0]];
        if(!d || d.kind !== 'actor'){ return; }
        if(!actors[end[0]]){ actors[end[0]] = {sends:[], gets:[]}; order.push(end[0]); }
        var list = actors[end[0]][end[1]];
        if(list.indexOf(e.art) < 0){ list.push(e.art); }
      });
    });
    if(!order.length){ return null; }
    var h = '<section class="read__section"><h3>WHAT CROSSES THE BOUNDARY</h3>'
      + '<dl class="read__rows">';
    order.forEach(function(id){
      var a = actors[id], text = [];
      if(a.gets.length){ text.push('Receives ' + series(a.gets) + '.'); }
      if(a.sends.length){ text.push('Sends ' + series(a.sends) + '.'); }
      h += '<dt>' + esc(id) + '</dt><dd>' + esc(text.join(' ')) + '</dd>';
    });
    return {html:h + '</dl>' + besideNote(L) + '</section>'};
  }
  function flowList(L){
    if(L === 'structure'){ return null; }
    var list = edgesOf(L);
    if(!list.length){ return null; }
    var label = L === 'all' ? 'ALL LAYERS' : String(LAY[L] ? LAY[L].label : L).toUpperCase();
    var h = '<section class="read__section"><div class="read__head"><h3>' + esc(label)
      + '</h3><span class="read__count">' + list.length + ' flow' + (list.length === 1 ? '' : 's')
      + '</span></div><ul class="read__flows">';
    list.forEach(function(i){
      var e = A.edges[i], l = LAY[e.layer];
      var dash = e.evidence === 'structural' || e.evidence === 'declared' ? ' class="dash"' : '';
      h += '<li><button type="button" class="read__flow" data-read-edge="' + i + '"><i' + dash
        + ' style="--c:' + esc(l ? l.colour : 'var(--ink-3)') + '"></i><span>' + esc(e.art)
        + '</span><small>' + esc(e.from) + ' → ' + esc(e.to) + '</small></button></li>';
    });
    return {html:h + '</ul>' + besideNote(L) + '</section>', bind:function(root){
      Array.prototype.slice.call(root.querySelectorAll('[data-read-edge]')).forEach(function(b){
        var i = +b.dataset.readEdge;
        b.addEventListener('mouseenter', function(){ A.peek(i); });
        b.addEventListener('focus', function(){ A.peek(i); });
        b.addEventListener('mouseleave', function(){ A.peek(-1); });
        b.addEventListener('click', function(){ A.inspectFlow(i); });
      });
    }};
  }
  function section(L){
    var own = P.readers || [], readers = own.concat([boundary, flowList]);
    for(var k = 0; k < readers.length; k++){
      var out = readers[k](L);
      // A layer with its own section (board 2) shows it without the guide.
      if(out){ out.own = k < own.length; return out; }
    }
    return {html:'<section class="read__section"><p class="read__q">'
      + esc(LAY[L] ? LAY[L].question : '') + '</p></section>'};
  }
  function render(){
    if(!read || read.hidden){ return; }
    var L = A.state.layer, h = '<div class="read">', sec = section(L);
    if(STEPS.length && !sec.own){
      var at = -1;
      STEPS.forEach(function(s, k){ if(s.layer === L && at < 0){ at = k; } });
      h += '<div class="read__head"><span class="read__kicker">READ THE MAP</span>'
        + '<span class="read__count">' + (at >= 0 ? (at + 1) + ' / ' : '') + STEPS.length
        + '</span></div><ol class="read__steps">';
      STEPS.forEach(function(s, k){
        var on = k === at;
        h += '<li><button type="button" class="read__step" data-guide="' + k + '" aria-current="'
          + on + '"><b>' + (k + 1 < 10 ? '0' : '') + (k + 1) + '</b><span>' + esc(s.title)
          + '</span><small>' + esc(s.layer ? (LAY[s.layer] ? LAY[s.layer].label : s.layer)
          : 'Sequence') + '</small>' + (on ? '<p>' + esc(s.text) + '</p>' : '') + '</button></li>';
      });
      h += '</ol>';
    }
    read.innerHTML = h + sec.html + '</div>';
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
    card.hidden = false; renderCard(); clearOfCard();
  }
  render();
})();
"""
