"""The Find dialog of the atlas page: one search field for the cards, the flows and the sequences.

`atlas_script` joins this part after the tools part (`atlas_tools`). It is a fork of the
Find part of the canvas page (`page_canvas_find`), with the functions of the atlas renderer.
The dialog is the dialog of the map page (`page_palette.html`). The match code, the ranking,
the result helpers and the rows are the text of the canvas page (`page_palette.MATCH`,
`page_canvas_find.RANK`, `page_canvas_find.ITEMS` and `page_canvas_find.LIST`). Thus the
rows are made with DOM functions (`el` in `atlas_tree`), and no text of the page data goes
to an HTML parser.

The results come from the page data (`DATA.maps`) when the dialog opens:

- Views and Layers: the views of the header that the page has, and the layers of all maps.
- Components and Flows: the cards and the flows of the current map.
- Sequences and Steps: the sequences of all maps, with the current map first.
- Actions: fit the current map, and go to the top map.
- Other maps: the cards and the flows of the other maps, with the hint "in <map ID>".

The result of a card shows the Map view, writes the URL hash of the card, fits the map of
the card and, when the camera stops, selects the card (`goTo` in `atlas_tree`). A load with
that hash gives the same view. A card that opens a map moves the camera into that map. The result of a flow shows a layer with that
flow, moves the camera to its two cards and keeps its line lit (`pin` in `atlas_lit`). The
result of a sequence or a step shows the Sequences view at that sequence or step. The live
region gives the result when the camera stops.

Ctrl K, Cmd K and / open the dialog, and the Find button of the header. Esc closes it,
and the keyboard focus goes back to the element that had it. While the dialog is open, no
key goes to the map.
"""

from __future__ import annotations

import json

from systemap import page_canvas_find, page_icons, page_palette

# The hint of the field names the cards, the flows and the sequences, the words of the
# keyboard sheet (`atlas_tools.KEYS`). It is short, so that a phone of 390 px shows it all.
PLACEHOLDER = "Find a card, flow or sequence"
HTML = page_palette.html(PLACEHOLDER)

# The dialog CSS of the map page and the base text of the dialog. The Close button shows
# its word, so its visible text is its name. On a touch screen and on a narrow screen, the
# Close button and each row are 44 x 44 px or more.
CSS = (
    page_palette.CSS + ".pal[hidden]{display:none}.pal{font-family:var(--fs);color:var(--ink)}"
    ".pal button{font:inherit;color:var(--ink-2);cursor:pointer}"
    ".pal .pal__x kbd{display:none}.pal .pal__x span{display:inline;font-size:13px}"
    "@media (pointer:coarse),(max-width:640px){.pal .pal__x{min-width:44px;min-height:44px;"
    "padding:0 4px}.pal .pal__o{height:44px}}"
    "@media (prefers-reduced-motion:reduce){"
    'html:not([data-reduce-motion="true"]) .pal:not([hidden]),'
    'html:not([data-reduce-motion="true"]) .pal:not([hidden]) .pal__box{animation:none}}'
)

_GLYPHS = ("map", "route", "fit", "zoom-out")

_HEAD = r"""
// ---- the Find dialog (atlas_find) -------------------------------------------------------
var FIND = null;
// The list part of the dialog has its own functions with the names act and open.
function findViews() { return VIEW_BTNS.map(function (b) { return b.getAttribute('data-mode'); }); }
(function(){
  function byId(id){ return document.getElementById(id); }
  var box = byId('palette'), input = byId('pal-input'), list = byId('pal-list');
  var status = byId('pal-status'), button = byId('atlas-find'), ICONS = ICONS_JSON;
  if(!box || !input || !list){ return; }
  var items = [], shown = [], at = 0, opener = null, LANDING = 0, CUT = TEXT_CHARACTERS;
  var ORDER = ['Views', 'Layers', 'Components', 'Flows', 'Sequences', 'Steps', 'Actions',
    'Other maps'];
  var LIMIT = {Components:8, Flows:8, Steps:6, 'Other maps':8};
  var plural = counted;
"""

_BODY = r"""  // The line of a flow kind. Its color is set with the style object, not with a style
  // attribute. This declaration comes after the one of the result helpers, so it is the one
  // that the dialog uses.
  function line(colour, dash){
    return function(){
      var i = el('i', {'class':'pal__line' + (dash ? ' dash' : '')});
      if(colour){ i.style.setProperty('--c', colour); }
      return i;
    };
  }
  function where(m){ return 'in ' + (m.id || DATA.name || 'the top map'); }
  function flowGlyph(f){ return line('var(' + (KIND[f.k] || '--ink-2') + ')', f.ev === 'structural' || f.ev === 'declared'); }

  // ---- the camera of a result ------------------------------------------------------
  // The live region gives the words when the camera stops. A new result stops the wait of
  // the result before it.
  function land(done){
    var me = ++LANDING, n = drawn, frames = 0;
    (function wait(){
      if(me !== LANDING){ return; }
      if((flight || drawn === n) && frames++ < 900){ requestAnimationFrame(wait); return; }
      done();
    })();
  }
  function placed(m, what){
    if(m.T){ return true; }
    say('The map ' + mapName(m) + ' has no area on the canvas. Thus the camera cannot go to ' + what + '.');
    return false;
  }
  function mapView(){ if(VIEW.mode !== 'map'){ setMode('map'); } }
  function goCard(m, c){
    if(!placed(m, 'the card ' + c.id)){ return; }
    mapView();
    // The result of the card of a neighbour goes out to its card in the map above (`upCard`).
    var to = c.child ? c : upCard(c) || c, g = goalOf(to.map, to, null);
    setHash(hashOf(cardId(to)));
    goTo(g);
    land(function(){
      if(c.child){ SAID_MAP = c.child; say(openWords(c.child)); return; }
      if(SEL !== to){ select(to, {keep: W > WIDE}); }
      SAID_MAP = to.map;
      say('Selected: card ' + to.id + '. Map: ' + mapName(to.map) + '.');
    });
  }
  // A layer of map m that shows flow f: the current layer, the layer of the flow, or All.
  function showFlow(m, f){
    if(layerFlags(m, layerOf(m)).flow[f.i]){ return; }
    setLayer(LAYER_OF[f.l] && hasLayer(m, f.l) ? f.l : 'all');
  }
  function goFlow(m, f){
    if(!placed(m, 'the flow ' + f.a)){ return; }
    mapView();
    select(null, {keep: true});
    setHash(hashOf(m.id));
    showFlow(m, f);
    flyGoal(goalOf(m, null, f));
    land(function(){
      pin(f);
      SAID_MAP = m;
      say('Flow from ' + f.s + ' to ' + f.t + ': ' + f.a + '. Map: ' + mapName(m) + '.');
    });
  }

  // ---- the results -----------------------------------------------------------------
  function views(){
    var names = {map:['Map', 'map', 'What are the components and their connections?'],
      seq:['Sequences', 'route', 'Which steps make one operation?'],
      states:['States', 'map', 'Which states does a thing go through?'],
      focus:['Focus', 'map', 'What does one card give and receive?'],
      history:['History', 'map', 'Where did the system change, and when?']};
    findViews().forEach(function(mode){
      var v = names[mode];
      if(v){ add('Views', v[0], v[2], function(){ setMode(mode); }, {glyph:svgIcon(v[1]), now:VIEW.mode === mode}); }
    });
    var m = currentMap();
    add('Layers', 'All', layerQuestion(m, 'all'), function(){ mapView(); setLayer('all'); },
      {glyph:line(''), now:VIEW.mode === 'map' && layerOf(m) === 'all'});
    Object.keys(LAYER_OF).forEach(function(id){
      var l = LAYER_OF[id];
      add('Layers', l.n, l.q || '', function(){ mapView(); setLayer(id); },
        {glyph:line(''), now:VIEW.mode === 'map' && layerOf(m) === id});
    });
  }
  // The internal components of a map come before its actors.
  function cards(m){
    return m.cards.filter(function(c){ return c.k !== 'actor'; })
      .concat(m.cards.filter(function(c){ return c.k === 'actor'; }));
  }
  function glyphOf(c){
    return function(){ return el('i', {'class':'pal__card' + (c.k === 'actor' ? ' actor' : '')}); };
  }
  function here(m){
    cards(m).forEach(function(c){
      add('Components', c.id, String(c.p || c.d || '').slice(0, CUT), function(){ goCard(m, c); },
        {quiet:true, words:(c.d || '') + ' ' + (c.p || ''), more:c.m || [], glyph:glyphOf(c)});
    });
    m.flows.forEach(function(f){
      add('Flows', f.a, f.s + ' → ' + f.t, function(){ goFlow(m, f); },
        {quiet:true, words:f.s + ' ' + f.t + ' ' + (f.y || ''), glyph:flowGlyph(f)});
    });
  }
  function other(m){
    var hint = where(m);
    cards(m).forEach(function(c){
      add('Other maps', c.id, String(c.p || c.d || '').slice(0, CUT), function(){ goCard(m, c); },
        {quiet:true, late:c.k === 'actor', hint:hint, words:c.k + ' ' + m.id, glyph:glyphOf(c)});
    });
    m.flows.forEach(function(f){
      add('Other maps', f.a, f.s + ' → ' + f.t, function(){ goFlow(m, f); },
        {quiet:true, late:true, hint:hint, words:f.s + ' ' + f.t + ' ' + m.id, glyph:flowGlyph(f)});
    });
  }
  function sequences(maps){
    if(findViews().indexOf('seq') < 0){ return; }
    maps.forEach(function(m, n){
      var hint = n ? where(m) : '';
      (m.sq || []).forEach(function(j, k){
        function show(s){
          if(!placed(m, 'the sequence ' + j.n)){ return; }
          setMode('seq');
          seqChoose(m, k, true);
          if(s >= 0){ stepTo(s); }
        }
        add('Sequences', j.n, counted(j.s.length, 'step') + (j.en ? ' · ' + j.en : ''),
          function(){ show(-1); }, {glyph:svgIcon('route'), hint:hint});
        j.s.forEach(function(st, s){
          var f = st.f >= 0 ? m.flows[st.f] : null;
          add('Steps', st.y || 'Step ' + (s + 1), j.n + ' · step ' + (s + 1),
            function(){ show(s); },
            {quiet:true, glyph:badge(s + 1), hint:hint, words:f ? f.a + ' ' + f.s + ' ' + f.t : ''});
        });
      });
    });
  }
  function actions(){
    add('Actions', 'Fit the current map', 'The camera shows all of the current map',
      function(){ mapView(); fitCurrent(true); }, {keys:['F'], glyph:svgIcon('fit'), words:'camera zoom'});
    add('Actions', 'Go to the top map', 'The camera shows all of the top map',
      function(){ mapView(); setHash(''); flyTo(topFrame(), FIT); }, {glyph:svgIcon('zoom-out'), words:'camera'});
  }
  // The results of the page data, with the current map first.
  function build(){
    var now = currentMap(), maps = [now].concat(DATA.maps.filter(function(m){ return m !== now; }));
    items = [];
    views(); here(now); sequences(maps); actions();
    maps.slice(1).forEach(other);
  }

"""

_TAIL = r"""
  function ranked(text){ build(); return rank(String(text).trim().toLowerCase()); }
  // While the dialog is open, no key goes to the map.
  box.addEventListener('keydown', function(e){ e.stopPropagation(); });
  FIND = {
    open:function(){ return !box.hidden; },
    show:function(){ open(); },
    build:function(){ var t0 = performance.now(); build(); return {ms:performance.now() - t0, n:items.length}; },
    rank:function(text){
      return ranked(text).map(function(g){
        return {g:g.g, rows:g.rows.map(function(r){ return {t:r.it.t, s:r.it.s, hint:r.it.hint, late:r.it.late}; })};
      });
    },
    run:function(text, g, n){
      var found = ranked(text).filter(function(x){ return x.g === g; })[0];
      var r = found && found.rows[n];
      if(r){ r.it.run(); }
      return !!r;
    }
  };
})();
"""

FIND = (
    (
        _HEAD
        + page_canvas_find.ITEMS
        + _BODY
        + page_palette.MATCH
        + page_canvas_find.RANK
        + page_canvas_find.LIST
        + _TAIL
    )
    .replace("ICONS_JSON", json.dumps({name: page_icons.PATHS[name] for name in _GLYPHS}))
    .replace("TEXT_CHARACTERS", str(page_canvas_find.TEXT_CHARACTERS))
    .replace("</", "<\\/")
)
