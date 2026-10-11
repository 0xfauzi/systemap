"""The Find palette: one search field for views, layers, sequences, components, flows and actions.

Ctrl+K, Cmd+K, the / key and the Find button in the header open the palette.
It shows grouped results. A name that starts with the text, or a word in the
name that starts with the text, comes first. The arrow keys move the
selection, Enter does the action of the result and Escape closes the palette.
Each result shows its key when it has one. The palette calls the page
functions of the views, the layers, the sequences and the map selection.
"""

from __future__ import annotations

import json

from systemap.page_icons import icon


def html() -> str:
    """Give the palette. It stays hidden until the reader opens it."""
    return (
        '<div class="pal" id="palette" hidden>'
        '<div class="pal__box" role="dialog" aria-modal="true" aria-label="Find">'
        f'<div class="pal__field">{icon("search")}'
        '<input id="pal-input" type="text" role="combobox" aria-expanded="true" '
        'aria-controls="pal-list" aria-autocomplete="list" autocomplete="off" '
        'spellcheck="false" aria-label="Find" '
        'placeholder="Find a component, flow, layer or action">'
        '<button type="button" class="pal__x" id="pal-close" aria-label="Close">'
        "<kbd>Esc</kbd><span>Close</span></button></div>"
        '<div class="pal__list" id="pal-list" role="listbox" aria-label="Results"></div>'
        '<p class="pal__foot" aria-hidden="true"><span><kbd>↑</kbd><kbd>↓</kbd>Move</span>'
        "<span><kbd>Enter</kbd>Select</span><span><kbd>Esc</kbd>Close</span></p>"
        '<p class="sr-only" id="pal-status" role="status"></p></div></div>'
    )


CSS = r"""
/* ---- the Find palette ------------------------------------------------------ */
.pal{position:fixed;inset:0;z-index:50;display:flex;justify-content:center;align-items:flex-start;
padding:14vh 16px 16px;background:color-mix(in srgb,var(--bg) 60%,transparent)}
.pal__box{width:min(600px,100%);max-height:100%;display:flex;flex-direction:column;
border:1px solid var(--line-2);border-radius:10px;background:var(--surface);overflow:hidden;
box-shadow:0 24px 64px color-mix(in srgb,#000 45%,transparent)}
:root[data-theme="light"] .pal__box{box-shadow:0 24px 64px color-mix(in srgb,#5a4a2a 22%,
  transparent)}
.pal__field{display:flex;align-items:center;gap:10px;height:52px;padding:0 14px 0 16px;
border-bottom:1px solid var(--line);color:var(--ink-3)}
.pal__field input{flex:1;min-width:0;height:100%;border:0;background:transparent;color:var(--ink);
font:15px var(--fs);outline:none;padding:0}
.pal__field input::placeholder{color:var(--ink-3)}
.pal kbd{display:inline-block;min-width:20px;font:11px/16px var(--fm);color:var(--ink-2);
text-align:center;border:1px solid var(--line-2);border-bottom-width:2px;border-radius:4px;
padding:0 5px}
.pal__list{overflow:auto;max-height:min(420px,56vh);padding:6px;overscroll-behavior:contain}
.pal__g{margin:8px 10px 4px;font:600 11px/16px var(--fm);letter-spacing:.08em;color:var(--ink-3);
text-transform:uppercase}
.pal__o{display:grid;grid-template-columns:16px minmax(0,max-content) minmax(0,1fr) auto;
align-items:center;gap:10px;height:36px;padding:0 10px;border-radius:6px;color:var(--ink-2);
cursor:pointer}
.pal__o[aria-selected="true"]{background:var(--raised);color:var(--ink)}
.pal__t{font:13px/18px var(--fs);color:var(--ink);white-space:nowrap;overflow:hidden;
text-overflow:ellipsis}
.pal__t mark{background:none;color:inherit;font-weight:650}
.pal__s{font:12px/16px var(--fs);color:var(--ink-3);white-space:nowrap;overflow:hidden;
text-overflow:ellipsis}
.pal__k{display:flex;gap:4px;align-items:center;font:11px var(--fm);color:var(--ink-3)}
.pal__k span{margin-right:4px;letter-spacing:.04em}
.pal__o svg.icon{color:var(--ink-2)}
.pal__line{display:block;width:16px;border-top:2px solid var(--c,var(--ink-3))}
.pal__line.dash{border-top-style:dashed}
.pal__card{display:block;width:16px;height:11px;border:1px solid var(--card-line);border-radius:3px;
background:var(--card)}
.pal__card.actor{border-style:dashed;background:none}
.pal__n{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;
border:1px solid var(--line-2);border-radius:50%;font:600 9px/1 var(--fm);color:var(--ink-2)}
.pal__n.sq{border-radius:3px}
.pal__none{margin:18px 12px;font-size:13px;color:var(--ink-2)}
.pal__foot{display:flex;align-items:center;gap:16px;margin:0;padding:8px 14px;
border-top:1px solid var(--line);font:12px var(--fs);color:var(--ink-3)}
.pal__foot span{display:inline-flex;align-items:center;gap:4px}
.pal__x{height:auto;min-height:0;padding:0;border:0;background:none}
.pal__x:hover{background:none}
.pal__x span{display:none}
@keyframes pal-in{from{opacity:0;transform:translateY(-6px) scale(.985)}}
@keyframes pal-fade{from{opacity:0}}
html:not([data-reduce-motion="true"]) .pal:not([hidden]){animation:pal-fade .12s ease-out}
html:not([data-reduce-motion="true"]) .pal:not([hidden]) .pal__box{
animation:pal-in .16s cubic-bezier(.2,.7,.2,1)}
@media(max-width:640px){.pal{padding:8px}.pal__box{width:100%}.pal__foot{display:none}
.pal__list{max-height:calc(100svh - 80px)}.pal__o{height:44px}
.pal__x{min-height:44px;padding:0 4px;font-size:14px;color:var(--ink-2)}
.pal__x kbd,.pal__k kbd{display:none}.pal__x span{display:inline}}
"""

# The icons that the results use, by name. The script reads them as text.
_GLYPHS = ("map", "route", "change", "sun", "moon", "motion", "full", "full-exit", "panel", "help")

_SCRIPT = r"""
(function(){
  var svg = document.getElementById('schematic');
  if(!svg || !svg.systemap || !svg.page){ return; }
  var A = svg.systemap, P = svg.page, W = window.systemapWorkspace || {}, ICONS = ICONS_JSON;
  function byId(id){ return document.getElementById(id); }
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  var box = byId('palette'), input = byId('pal-input'), list = byId('pal-list');
  var status = byId('pal-status'), button = byId('find-open');
  if(!box || !input || !list){ return; }
  var items = [], shown = [], at = 0, opener = null;
  var ORDER = ['Views', 'Layers', 'Components', 'Flows', 'Sequences', 'Steps', 'Rules', 'Actions'];
  var LIMIT = {Components:8, Flows:8, Steps:6, Rules:6};
  function plural(n, word){ return n + ' ' + word + (n === 1 ? '' : 's'); }
  function press(id){ var b = byId(id); if(b){ b.click(); } }

  // ---- the results ----------------------------------------------------------
  // A quiet result shows only for a search text: the list with no text gives
  // the views, the layers, the sequences and the actions.
  function add(g, t, s, run, o){
    o = o || {};
    items.push({g:g, t:t, s:s || '', run:run, keys:o.keys || [], words:o.words || '',
      more:o.more || [], glyph:o.glyph || '<i></i>', quiet:!!o.quiet,
      hint:o.now ? 'Current' : o.hint || '',
      k:items.length});
  }
  function line(colour, dash){
    return '<i class="pal__line' + (dash ? ' dash' : '') + '"'
      + (colour ? ' style="--c:' + esc(colour) + '"' : '') + '></i>';
  }
  function badge(n, square){
    return '<b class="pal__n' + (square ? ' sq' : '') + '">' + n + '</b>'; }
  function views(LAY){
    [['understand', 'Map', 'map', 'What are the components and their connections?'],
      ['trace', 'Sequences', 'route', 'Which steps make one operation?'],
      ['change', 'Changes', 'change', 'What did this change touch?']].forEach(function(v){
      add('Views', v[1], v[3], function(){ P.setMode(v[0]); },
        {glyph:ICONS[v[2]], now:P.mode() === v[0]});
    });
    Array.prototype.slice.call(document.querySelectorAll('[data-layer-btn]')).forEach(
      function(b, k){
        var id = b.dataset.layerBtn, l = LAY[id];
        add('Layers', l ? l.label : 'All', b.getAttribute('title') || '', function(){
          if(P.mode() !== 'understand'){ P.setMode('understand'); }
          P.setLayer(id);
        }, {keys:k < 9 ? [String(k + 1)] : [], glyph:line(l && l.colour),
          now:P.mode() === 'understand' && A.state.layer === id});
      });
  }
  function parts(){
    var where = {};
    (W.regions || []).forEach(function(r){ r.ids.forEach(function(id){ where[id] = r.label; }); });
    Object.keys(A.detail).forEach(function(id){
      if(id === '_meta'){ return; }
      var d = A.detail[id], src = (W.sources || {})[id], region = where[id] || W.outside || '';
      add('Components', id, d.plain || d.does, function(){
        if(P.mode() === 'change'){ P.setMode('understand'); }
        svg.workspace.inspect(id);
      }, {quiet:true, words:d.does + ' ' + (d.plain || '') + ' ' + region, hint:region,
        more:src ? src.modules.map(function(m){ return m.id; }) : [],
        glyph:'<i class="pal__card' + (d.kind === 'actor' ? ' actor' : '') + '"></i>'});
    });
  }
  function flows(LAY){
    A.edges.forEach(function(e, i){
      var l = LAY[e.layer], dash = e.evidence === 'structural' || e.evidence === 'declared';
      add('Flows', e.art, e.from + ' → ' + e.to + (l ? ' · ' + l.label : ''), function(){
        if(P.mode() === 'change'){ P.setMode('understand'); }
        A.inspectFlow(i);
      }, {quiet:true, words:e.from + ' ' + e.to, glyph:line(l && l.colour, dash)});
    });
  }
  function sequences(){
    var meta = (W.sequences || {}).journeys || [];
    A.journeys.forEach(function(j, k){
      var m = meta[k] || {};
      add('Sequences', j.label, plural(j.steps.length, 'step') + (m.entry ? ' · ' + m.entry : ''),
        function(){ (P.journey.route || P.journey.start)(k); },
        {glyph:ICONS.route});
      j.steps.forEach(function(st, s){
        var e = A.edges[st.edge];
        add('Steps', st.say, j.label + ' · step ' + (s + 1), function(){
          if(P.journey.state().j !== k){ P.journey.start(k); }
          P.journey.step(s);
        }, {quiet:true, glyph:badge(s + 1), words:e ? e.art + ' ' + e.from + ' ' + e.to : ''});
      });
    });
  }
  function rules(){
    (A.detail._meta.rules || []).forEach(function(r){
      var gov = Object.keys(A.detail).filter(function(id){
        return id !== '_meta' && (A.detail[id].rules || []).indexOf(r.n) >= 0; });
      add('Rules', r.text, 'Rule ' + r.n + (gov.length ? ' · ' + gov.join(', ') : ''),
        function(){ P.showRule(r.n); },
        {quiet:true, words:gov.join(' '), glyph:badge(r.n, true)});
    });
  }
  function actions(){
    var root = document.documentElement, paper = root.getAttribute('data-theme') === 'light';
    var still = root.dataset.reduceMotion === 'true', full = P.isFull();
    add('Actions', paper ? 'Use the Ink theme' : 'Use the Paper theme', 'Theme', function(){
      press(paper ? 'scheme-dark' : 'scheme-light'); },
      {glyph:ICONS[paper ? 'moon' : 'sun'], words:'theme dark light'});
    add('Actions', still ? 'Allow motion' : 'Reduce motion',
      'Reduce motion is ' + (still ? 'on' : 'off'), function(){ press('reduce-motion'); },
      {glyph:ICONS.motion, words:'motion animation'});
    add('Actions', full ? 'Exit full screen' : 'Full screen', 'The map fills the screen',
      function(){ press('full-toggle'); }, {keys:['F'], glyph:ICONS[full ? 'full-exit' : 'full']});
    add('Actions', P.panelOpen() ? 'Close the details panel' : 'Open the details panel',
      'Details', function(){ press('panel-toggle'); },
      {keys:['D'], glyph:ICONS.panel, words:'panel'});
    add('Actions', 'Keyboard keys', 'The keys of this page', function(){ press('keys-open'); },
      {keys:['?'], glyph:ICONS.help, words:'help'});
  }
  function build(){
    var LAY = {};
    A.layers.forEach(function(l){ LAY[l.id] = l; });
    items = [];
    views(LAY); parts(); flows(LAY); sequences(); rules(); actions();
  }

  // ---- matching: the start of the name, the start of a word, then a part ------
  function wordStart(text, j){
    var a = text.charAt(j - 1), b = text.charAt(j);
    return !/[A-Za-z0-9]/.test(a) || (/[a-z]/.test(a) && /[A-Z]/.test(b));
  }
  function fuzzy(q, low){
    // The letters of the text in their order, near each other: a weak match,
    // for the name only. "chdet" finds ChangeDetector.
    var p = 0, first = -1, k = 0;
    for(; k < low.length && p < q.length; k++){
      if(low.charAt(k) === q.charAt(p)){ if(first < 0){ first = k; } p++; }
    }
    var span = k - first;
    return p === q.length && span <= 2 * q.length + 2
      ? {s:10 + Math.round(10 * q.length / span)} : {s:0};
  }
  function hit(q, text, loose){
    text = String(text);
    var low = text.toLowerCase(), i = low.indexOf(q);
    if(i === 0){ return {s:low.length === q.length ? 100 : 80, i:0}; }
    for(var j = i; j > 0; j = low.indexOf(q, j + 1)){
      if(wordStart(text, j)){ return {s:60, i:j}; }
    }
    if(i > 0){ return {s:40, i:i}; }
    return loose && q.length > 1 ? fuzzy(q, low) : {s:0};
  }
  function score(it, q){
    // The name counts most. The group name, such as Rules, counts next, so that
    // "rule" gives the rules first. The other text counts less.
    var best = hit(q, it.t, true), group = hit(q, it.g, false);
    best.name = true;
    if(group.s * 0.9 > best.s){ best = {s:group.s * 0.9}; }
    [it.s, it.words].concat(it.more).forEach(function(text, n){
      var h = hit(q, text, false);
      if(h.s * 0.6 > best.s){ best = {s:h.s * 0.6, module:n > 1 ? text : ''}; }
    });
    return best;
  }
  function match(it, tokens){
    var total = 0, first = null, module = '';
    for(var n = 0; n < tokens.length; n++){
      var r = score(it, tokens[n]);
      if(!r.s){ return null; }
      total += r.s;
      first = first || r;
      module = module || r.module || '';
    }
    return {it:it, s:total, first:first, q:tokens[0] || '', module:module};
  }
  function rank(text){
    var tokens = text.split(/\s+/).filter(Boolean), groups = {};
    items.forEach(function(it){
      if(it.quiet && !tokens.length){ return; }
      var r = match(it, tokens);
      if(r){ (groups[it.g] = groups[it.g] || []).push(r); }
    });
    // A long group shows its best results. The text "rule" or "rules" shows all rules.
    return ORDER.filter(function(g){ return groups[g]; }).map(function(g){
      var rows = groups[g].sort(function(a, b){ return (b.s - a.s) || (a.it.k - b.it.k); });
      var all = !tokens.length || (tokens.length === 1 && g.toLowerCase().indexOf(tokens[0]) === 0);
      return {g:g, best:rows[0].s, rows:all || !LIMIT[g] ? rows : rows.slice(0, LIMIT[g])};
    }).sort(function(a, b){
      return (b.best - a.best) || (ORDER.indexOf(a.g) - ORDER.indexOf(b.g));
    });
  }

  // ---- the list -------------------------------------------------------------
  function name(r){
    var t = r.it.t, f = r.first;
    if(!f || !f.name || f.i === undefined){ return esc(t); }
    var end = f.i + r.q.length;
    return esc(t.slice(0, f.i)) + '<mark>' + esc(t.slice(f.i, end)) + '</mark>' + esc(t.slice(end));
  }
  function row(r, k){
    return '<div class="pal__o" role="option" id="pal-o' + k + '" data-k="' + k
      + '" aria-selected="false">' + r.it.glyph + '<span class="pal__t">' + name(r)
      + '</span><span class="pal__s">' + esc(r.module ? 'Module: ' + r.module : r.it.s)
      + '</span><span class="pal__k">' + (r.it.hint ? '<span>' + esc(r.it.hint) + '</span>' : '')
      + r.it.keys.map(function(key){
        return '<kbd>' + esc(key) + '</kbd>'; }).join('') + '</span></div>';
  }
  function render(){
    var h = '';
    shown = [];
    rank(input.value.trim().toLowerCase()).forEach(function(g, n){
      h += '<div role="group" aria-labelledby="pal-g' + n + '"><p class="pal__g" id="pal-g' + n
        + '">' + esc(g.g) + '</p>';
      g.rows.forEach(function(r){ h += row(r, shown.length); shown.push(r.it); });
      h += '</div>';
    });
    list.innerHTML = h || '<p class="pal__none">No result has this text. Type a name, a function, '
      + 'a module or an action.</p>';
    move(0);
    if(status){ status.textContent = plural(shown.length, 'result'); }
  }
  function move(k, pointer){
    if(!shown.length){ input.removeAttribute('aria-activedescendant'); return; }
    at = (k + shown.length) % shown.length;
    Array.prototype.slice.call(list.querySelectorAll('[data-k]')).forEach(function(o){
      o.setAttribute('aria-selected', +o.dataset.k === at ? 'true' : 'false'); });
    input.setAttribute('aria-activedescendant', 'pal-o' + at);
    var o = byId('pal-o' + at);
    if(o && !pointer){ o.scrollIntoView({block:'nearest'}); }
  }

  // ---- open, close and act ----------------------------------------------------
  function open(){
    if(!box.hidden){ input.focus(); return; }
    opener = document.activeElement;
    build();
    input.value = '';
    box.hidden = false;
    if(button){ button.setAttribute('aria-expanded', 'true'); }
    render();
    input.focus();
  }
  function close(){
    if(box.hidden){ return; }
    box.hidden = true;
    if(button){ button.setAttribute('aria-expanded', 'false'); }
    var back = opener;
    opener = null;
    if(back && back !== document.body && back.focus && back.isConnected !== false){
      back.focus({preventScroll:true});
    } else { input.blur(); }
  }
  function act(k){
    var it = shown[k];
    if(!it){ return; }
    close();
    it.run();
  }
  input.addEventListener('input', render);
  input.addEventListener('keydown', function(e){
    if(e.key === 'ArrowDown'){ move(at + 1); }
    else if(e.key === 'ArrowUp'){ move(at - 1); }
    else if(e.key === 'Enter'){ act(at); }
    else if(e.key === 'Escape'){ close(); }
    else if(e.key !== 'Tab'){ return; }
    e.preventDefault();
    e.stopPropagation();
  });
  list.addEventListener('mousemove', function(e){
    var o = e.target.closest && e.target.closest('[data-k]');
    if(o && +o.dataset.k !== at){ move(+o.dataset.k, true); }
  });
  list.addEventListener('click', function(e){
    var o = e.target.closest && e.target.closest('[data-k]');
    if(o){ act(+o.dataset.k); }
  });
  box.addEventListener('mousedown', function(e){ if(e.target === box){ close(); } });
  if(byId('pal-close')){ byId('pal-close').addEventListener('click', close); }
  if(button){ button.addEventListener('click', open); }
  function typing(t){
    return !!(t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName || '')));
  }
  function covered(){
    return ['keys', 'present', 'submap'].some(function(id){
      var n = byId(id); return n && !n.hidden; });
  }
  // Ctrl+K or Cmd+K opens and closes the palette. The / key opens it.
  window.addEventListener('keydown', function(e){
    var k = (e.key || '').toLowerCase();
    if(covered()){ return; }
    if(k === 'k' && (e.ctrlKey || e.metaKey) && !e.altKey){
      if(box.hidden){ open(); } else { close(); }
    } else if(e.key === '/' && box.hidden && !e.ctrlKey && !e.metaKey && !e.altKey
      && !typing(e.target)){ open(); }
    else { return; }
    e.preventDefault();
    e.stopImmediatePropagation();
  }, true);
  if(typeof navigator !== 'undefined' && /Mac|iP(hone|ad|od)/.test(navigator.platform || '')){
    Array.prototype.slice.call(document.querySelectorAll('[data-mod-key]')).forEach(function(n){
      n.textContent = '⌘K'; });
  }
})();
"""

SCRIPT = _SCRIPT.replace(
    "ICONS_JSON", json.dumps({name: icon(name) for name in _GLYPHS}).replace("</", "<\\/")
)
