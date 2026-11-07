"""The Find dialog of the canvas page: one search field for all maps of the tree.

The design is the section "Search" of docs/design/nested-canvas.md: Ctrl K stays, and a
result in a different map moves the camera to that card. The dialog is the dialog of the
map page (`page_palette.html` and `page_palette.CSS`). The canvas page adds CSS to it
(`CSS`): on a touch screen, the Close button and the rows are 44 x 44 px or more. The match
code and the code of the list and of the dialog are the same text as on the map page
(`page_palette.MATCH` and `page_palette.LIST`), with one change (`LIST`): the text for no
result is an option that is not available, because the list has the role listbox. The
ranking is the ranking of step 8 of docs/design/nested-parts.md (`RANK`): the group "Other
maps" comes after the groups of the current map, it shows 8 rows or fewer, and its rows
give the actors and the flows after the internal components. The name of that group does
not show all its rows.

The results come from the canvas data (`DATA.maps`) when the dialog opens. Thus the page
has no other data for the search. These are the groups:

- Views and Layers, when the view part of the page is there (`setView`). A layer result
  shows the Map view with that layer.
- Components and Flows: the cards and the flows of the current map. The key of a card is
  its map ID and its card ID, because a card ID is unique only in one map. The card text
  is the plain text or the `does` text, cut to TEXT_CHARACTERS characters.
- Sequences and Steps, when the Sequences view of the page is there (`sq` in the canvas
  data and `seqChoose`). The sequences of the current map come first.
- Actions: fit the current map, and go to the top map.
- Other maps: the cards and the flows of the other maps, in tree order, with the hint
  "in <map ID>" ("in <system name>" for the top map).

The result of a card writes the URL hash of the card, moves the camera to the card and,
when the camera stops, selects it (`select` in `page_canvas_touch`). The live region then
gives the card and its map. The result of a card that opens a map moves the camera into
that map. The result of a flow moves the camera to its two cards. A card of a map that has
no area has no place on the canvas: the camera does not move, and the live region tells
it. With reduced motion, the camera move occurs at one time.

Ctrl K, Cmd K and / open the dialog, and the Find button of the header when it is there.
Escape closes it, and the keyboard focus goes back to the element that had it. While the
dialog is open, no key goes to the camera: the dialog stops each key event. The dialog
adds no work to a frame of the canvas.
"""

from __future__ import annotations

import json

from systemap import page_icons, page_palette
from systemap.page_icons import icon

# The card text of a result is cut to this number of characters (`PLAIN_CHARACTERS` of
# step 8).
TEXT_CHARACTERS = 60

HTML = page_palette.html()

# The dialog CSS of the map page, the icon CSS, and the base text of the dialog: the
# canvas page has no rule for `hidden`, no page font rule and no button rule. The Close button shows its word
# "Close" on each screen, not the key Esc. Thus its visible text is its name (the rule
# label-content-name-mismatch of axe-core). The foot of the dialog gives the key Esc.
# On a touch screen and on a narrow screen, the Close button and each row are 44 x 44 px or
# more (C5 of docs/design/nested-canvas.md).
CSS = (
    page_icons.CSS
    + page_palette.CSS
    + ".pal[hidden]{display:none}.pal{font-family:var(--fs);color:var(--ink)}"
    ".pal button{font:inherit;color:var(--ink-2);cursor:pointer}"
    ".pal .pal__x kbd{display:none}.pal .pal__x span{display:inline;font-size:13px}"
    "@media (pointer:coarse),(max-width:640px){.pal .pal__x{min-width:44px;min-height:44px;"
    "padding:0 4px}.pal .pal__o{height:44px}}"
)

_GLYPHS = ("map", "route", "change", "fit", "zoom-out")

# The ranking of step 8 (origin/claude/nested-step-8, page_palette.py), with no change.
RANK = r"""  function rank(text){
    var tokens = text.split(/\s+/).filter(Boolean), groups = {};
    items.forEach(function(it){
      if(it.quiet && !tokens.length){ return; }
      var r = match(it, tokens);
      if(r){ (groups[it.g] = groups[it.g] || []).push(r); }
    });
    // A long group shows its best results. The text "rule" or "rules" shows all rules.
    // The group name of the other maps does not show all its rows. In the shown rows,
    // the actors come after the internal components.
    return ORDER.filter(function(g){ return groups[g]; }).map(function(g){
      var rows = groups[g].sort(function(a, b){ return (b.s - a.s) || (a.it.k - b.it.k); });
      var all = !tokens.length || (tokens.length === 1 && g !== 'Other maps' &&
        g.toLowerCase().indexOf(tokens[0]) === 0);
      var shown = rows.slice(0, all || !LIMIT[g] ? rows.length : LIMIT[g]);
      shown.sort(function(a, b){
        return (a.it.late - b.it.late) || (b.s - a.s) || (a.it.k - b.it.k); });
      return {g:g, best:rows[0].s, rows:shown};
    }).sort(function(a, b){
      // The results of the other maps come after the results of this map.
      var other = (a.g === 'Other maps') - (b.g === 'Other maps');
      return other || (b.best - a.best) || (ORDER.indexOf(a.g) - ORDER.indexOf(b.g));
    });
  }

"""

# The part of the canvas renderer. It has its own function scope, so its names (for
# example ORDER, the order of the groups) do not change the names of the other parts.
_HEAD = r"""
// ---- the Find dialog ------------------------------------------------------------
var FIND = null;
(function(){
  function byId(id){ return document.getElementById(id); }
  var box = byId('palette'), input = byId('pal-input'), list = byId('pal-list');
  var status = byId('pal-status'), button = byId('find-open'), ICONS = ICONS_JSON;
  if(!box || !input || !list){ return; }
  var items = [], shown = [], at = 0, opener = null, LANDING = 0, CUT = TEXT_CHARACTERS;
  var ORDER = ['Views', 'Layers', 'Components', 'Flows', 'Sequences', 'Steps', 'Actions',
    'Other maps'];
  var LIMIT = {Components:8, Flows:8, Steps:6, 'Other maps':8};
  // The list code of the map page (`page_palette.LIST`) calls `plural`.
  var plural = counted;
  function add(g, t, s, run, o){
    o = o || {};
    items.push({g:g, t:t, s:s || '', run:run, keys:o.keys || [], words:o.words || '',
      more:o.more || [], glyph:o.glyph || '<i></i>', quiet:!!o.quiet,
      hint:o.now ? 'Current' : o.hint || '', late:!!o.late,
      k:items.length});
  }
  function line(colour, dash){
    return '<i class="pal__line' + (dash ? ' dash' : '') + '"'
      + (colour ? ' style="--c:' + esc(colour) + '"' : '') + '></i>';
  }
  function badge(n){ return '<b class="pal__n">' + esc(n) + '</b>'; }
  function where(m){ return 'in ' + (m.id || DATA.name || 'the top map'); }
  function layerColour(id){ return 'var(--l-' + id + ')'; }
  function flowGlyph(f){ return line(layerColour(f.l), f.ev === 'structural' || f.ev === 'declared'); }

  // ---- the camera of a result ------------------------------------------------------
  // The live region gives the words when the camera stops: after the flight, and after the
  // frame that follows it. A new result stops the wait of the result before it.
  function land(done){
    var me = ++LANDING, n = drawn, frames = 0;
    (function wait(){
      if(me !== LANDING){ return; }
      if((flight || drawn === n) && frames++ < 900){ requestAnimationFrame(wait); return; }
      done();
    })();
  }
  // A map with no place has no owner card (`place`). Its path comes from its ID.
  function placed(m, what){
    if(m.T){ return true; }
    var path = [DATA.name || 'map'].concat(m.id ? m.id.split('/') : []).join(' / ');
    say('The map ' + path + ' has no area on the canvas. Thus the camera cannot go to '
      + what + '.');
    return false;
  }
  function goCard(m, c){
    if(!placed(m, 'the card ' + c.id)){ return; }
    setHash(hashOf(cardId(c)));
    flyGoal(goalOf(m, c, null));
    land(function(){
      if(c.child){
        SAID_MAP = c.child;
        say(openWords(c.child));
        return;
      }
      if(mapOpen(c)){ select(c); }
      SAID_MAP = c.map;
      say((SEL_C === c ? 'Selected: card ' : 'Card ') + c.id + '. Map: ' + mapName(m) + '.');
    });
  }
  function goFlow(m, f){
    if(!placed(m, 'the flow ' + f.a)){ return; }
    setHash(hashOf(m.id));
    flyGoal(goalOf(m, null, f));
    land(function(){
      SAID_MAP = m;
      say('Flow from ' + f.s + ' to ' + f.t + ': ' + f.a + '. Map: ' + mapName(m) + '.');
    });
  }

  // ---- the results -----------------------------------------------------------------
  // The Find part also operates without the view part (`page_canvas_view`): then it has no
  // Views, Layers, Sequences or Steps group.
  function views(){
    if(typeof setView !== 'function' || typeof VIEW !== 'object'){ return; }
    [['map', 'map', 'What are the components and their connections?'],
      ['sequences', 'route', 'Which steps make one operation?'],
      ['changes', 'change', 'What did this change touch?']].forEach(function(v){
      if(v[0] !== 'map' && !VIEWS[v[0]]){ return; }
      add('Views', MODE_NAMES[v[0]], v[2], function(){ setView(v[0]); },
        {glyph:ICONS[v[1]], now:VIEW.mode === v[0]});
    });
    add('Layers', 'All', layerQuestion('all'), function(){ setView('map', 'all'); },
      {glyph:line(''), now:VIEW.mode === 'map' && VIEW.layer === 'all'});
    Object.keys(LAYER_OF).forEach(function(id){
      var l = LAYER_OF[id];
      add('Layers', l.n, l.q || '', function(){ setView('map', id); },
        {glyph:line(layerColour(id)), now:VIEW.mode === 'map' && VIEW.layer === id});
    });
  }
  // The internal components of a map come before its actors.
  function cards(m){
    return m.cards.filter(function(c){ return c.k !== 'actor'; })
      .concat(m.cards.filter(function(c){ return c.k === 'actor'; }));
  }
  function glyphOf(c){ return '<i class="pal__card' + (c.k === 'actor' ? ' actor' : '') + '"></i>'; }
  function here(m){
    var lay = {};
    (m.layers || []).forEach(function(l){ lay[l.id] = l; });
    cards(m).forEach(function(c){
      add('Components', c.id, String(c.p || c.d || '').slice(0, CUT), function(){ goCard(m, c); },
        {quiet:true, words:(c.d || '') + ' ' + (c.p || ''), more:c.m || [], glyph:glyphOf(c)});
    });
    m.flows.forEach(function(f){
      var l = lay[f.l];
      add('Flows', f.a, f.s + ' → ' + f.t + (l ? ' · ' + l.n : ''), function(){ goFlow(m, f); },
        {quiet:true, words:f.s + ' ' + f.t, glyph:flowGlyph(f)});
    });
  }
  function other(m){
    var hint = where(m);
    cards(m).forEach(function(c){
      var actor = c.k === 'actor';
      add('Other maps', c.id, String(c.p || c.d || '').slice(0, CUT), function(){ goCard(m, c); },
        {quiet:true, late:actor, hint:hint, words:c.k + ' ' + m.id, glyph:glyphOf(c)});
    });
    m.flows.forEach(function(f){
      add('Other maps', f.a, f.s + ' → ' + f.t, function(){ goFlow(m, f); },
        {quiet:true, late:true, hint:hint, words:f.s + ' ' + f.t + ' ' + m.id, glyph:flowGlyph(f)});
    });
  }
  function sequences(maps){
    if(typeof seqChoose !== 'function' || typeof VIEWS !== 'object' || !VIEWS.sequences){ return; }
    maps.forEach(function(m, n){
      var hint = n ? where(m) : '';
      (m.sq || []).forEach(function(j, k){
        function show(steps, s){
          if(!placed(m, 'the sequence ' + j.n)){ return; }
          setView('sequences');
          seqChoose(m, k, !steps);
          if(steps){ seqMode(true, s, true); }
        }
        add('Sequences', j.n, counted(j.s.length, 'step') + (j.en ? ' · ' + j.en : ''),
          function(){ show(false, 0); }, {glyph:ICONS.route, hint:hint});
        j.s.forEach(function(st, s){
          var f = st.f >= 0 ? m.flows[st.f] : null;
          add('Steps', st.y || 'Step ' + (s + 1), j.n + ' · step ' + (s + 1),
            function(){ show(true, s); },
            {quiet:true, glyph:badge(s + 1), hint:hint, words:f ? f.a + ' ' + f.s + ' ' + f.t : ''});
        });
      });
    });
  }
  function actions(){
    add('Actions', 'Fit the current map', 'The camera shows all of the current map',
      function(){ fitCurrent(); }, {keys:['F'], glyph:ICONS.fit, words:'camera zoom'});
    add('Actions', 'Go to the top map', 'The camera shows all of the top map',
      function(){ setHash(''); flyTo(topFrame(), FIT); }, {glyph:ICONS['zoom-out'], words:'camera'});
  }
  // The results of the canvas data, with the current map first.
  function build(){
    var now = currentMap(), maps = [now].concat(DATA.maps.filter(function(m){ return m !== now; }));
    items = [];
    views(); here(now); sequences(maps); actions();
    maps.slice(1).forEach(other);
  }

"""

_TAIL = r"""
  // While the dialog is open, no key goes to the camera.
  box.addEventListener('keydown', function(e){ e.stopPropagation(); });
  if(button){ button.hidden = false; }
  FIND = {
    open:function(){ return !box.hidden; },
    // Make the results again, and give the time in ms and the count of results.
    build:function(){ var t0 = performance.now(); build(); return {ms:performance.now() - t0, n:items.length}; },
    // The groups and the rows that the text gives, for the tests.
    rank:function(text){
      build();
      return rank(String(text).trim().toLowerCase()).map(function(g){
        return {g:g.g, rows:g.rows.map(function(r){ return {t:r.it.t, s:r.it.s, hint:r.it.hint, late:r.it.late}; })};
      });
    },
    // Do the action of row n of the group g for the text, as Enter does. Give false when
    // there is no such row.
    run:function(text, g, n){
      build();
      var found = rank(String(text).trim().toLowerCase()).filter(function(x){ return x.g === g; })[0];
      var r = found && found.rows[n];
      if(r){ r.it.run(); }
      return !!r;
    }
  };
})();
if (window.systemapCanvas) window.systemapCanvas.find = FIND;
"""

# The list of the results has the role listbox. A listbox has only options and groups, thus
# the text for no result is an option that is not available (the rule aria-required-children
# of axe-core). The map page keeps its bytes: this change is only in the canvas page.
_NONE = 'list.innerHTML = h || \'<p class="pal__none">'
LIST = page_palette.LIST.replace(
    _NONE, 'list.innerHTML = h || \'<p class="pal__none" role="option" aria-disabled="true">'
)
if LIST == page_palette.LIST:  # pragma: no cover - a guard for a change of the list code
    raise ValueError("The list code of the map page has no text for no result.")

FIND = (
    (_HEAD + page_palette.MATCH + RANK + LIST + _TAIL)
    .replace("ICONS_JSON", json.dumps({name: icon(name) for name in _GLYPHS}))
    .replace("TEXT_CHARACTERS", str(TEXT_CHARACTERS))
)

# The page embeds the script in a script element. "</" would end the element.
FIND = FIND.replace("</", "<\\/")
