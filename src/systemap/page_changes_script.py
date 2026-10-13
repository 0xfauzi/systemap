"""The Changes view script: the ordered reveal, Hold B, the panel and the selection.

It runs after the shell scripts and reads the change map (`svg#changemap`,
its API `changemap.systemap` and the `_meta.change` marks in its detail) and
`window.systemapWorkspace` (the comparison). The panel
text uses only these records. A flow is marked when it touches a component
with changed source and has no source review. A sequence step is marked when
an end of its flow has changed source."""

# A page without a comparison has no change map. This script only sets the title.
EMPTY_SCRIPT = r"""
(function(){
  var main = document.getElementById('schematic');
  var P = main && main.page, view = document.getElementById('change');
  if(!P || !view){ return; }
  document.addEventListener('systemap:mode', function(e){
    if(e.detail && e.detail.mode === 'change'){
      P.setTitle('CHANGES', 'This page has no revision comparison');
      view.classList.add('chg-titled');
    }
  });
})();
"""

SCRIPT = r"""
(function(){
  var C = document.getElementById('changemap');
  var panel = document.getElementById('change-panel');
  var main = document.getElementById('schematic');
  var P = main && main.page;
  if(!C || !C.systemap || !panel){ return; }
  var M = C.systemap, D = M.detail, META = D._meta || {}, EDGES = M.edges;
  var W = window.systemapWorkspace || {};
  var CMP = W.comparison || {parts:{}, adjacent:[], unparsed:[]};
  var CH = META.change || {cards:{}, lost:[]};
  var MARK = CH.cards || {}, LOST = CH.lost || [];
  var body = document.body;
  function byId(id){ return document.getElementById(id); }
  function all(sel, root){
    return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function reduced(){
    return document.documentElement.dataset.reduceMotion === 'true';
  }
  function names(list){
    return list.length < 2 ? list.join('') : list.slice(0, -1).join(', ') + ' and '
      + list[list.length - 1];
  }
  function ids(mark){
    return Object.keys(D).filter(function(id){ return id !== '_meta' && MARK[id] === mark; });
  }
  var SOURCE = ids('changed'), TESTS = ids('tests'), IMPORTS = ids('imports');
  var REGIONS = META.regions || [], RANK = {};
  REGIONS.forEach(function(r, k){ (r.ids || []).forEach(function(id){ RANK[id] = k; }); });
  function rank(id){ return RANK[id] === undefined ? REGIONS.length : RANK[id]; }
  function touches(i, list){
    var e = EDGES[i]; return !!e && (list.indexOf(e.from) >= 0 || list.indexOf(e.to) >= 0);
  }
  // A recorded source review has source references and a review digest. Source references
  // without a review digest are not a recorded review.
  function referenced(i){ return (EDGES[i].source_refs || []).length > 0; }
  function recorded(i){ return referenced(i) && !!EDGES[i].review_digest; }
  function undigested(i){ return referenced(i) && !EDGES[i].review_digest; }
  function lostOf(id){ return LOST.filter(function(i){ return touches(i, [id]); }); }

  // ---- the panel: summary, flows, sequences ------------------------------
  function where(){
    var labels = [];
    SOURCE.forEach(function(id){
      var r = REGIONS[RANK[id]];
      if(r && labels.indexOf(r.label) < 0){ labels.push(r.label); }
    });
    return labels.length ? 'The change is in ' + names(labels) + '.' : '';
  }
  function flowsSentence(){
    if(!SOURCE.length){ return ''; }
    if(!LOST.length){ return 'Each of their flows has a source review or connects to an actor.'; }
    return 'A source review is necessary for ' + LOST.length + ' of their flows.';
  }
  function dash(pattern){
    return '<svg width="22" height="4" viewBox="0 0 22 4" aria-hidden="true"><line x1="0" y1="2" '
      + 'x2="22" y2="2" style="stroke:var(--change);stroke-width:2;stroke-dasharray:' + pattern
      + '"/></svg>';
  }
  function edgeButton(i){
    var e = EDGES[i];
    return '<button type="button" class="chg-edge" data-change-edge="' + i + '">' + esc(e.art)
      + '</button> to ' + esc(e.to);
  }
  function support(list){
    var why = [];
    if(list.some(function(i){ return EDGES[i].import_present; })){ why.push('an import'); }
    if(list.some(function(i){ return EDGES[i].shared_module; })){ why.push('a shared module'); }
    if(list.some(function(i){ return EDGES[i].mechanism; })){ why.push('a configured mechanism'); }
    return why.length ? names(why).replace(/ and /, ' or ') : 'structural evidence';
  }
  function flowRow(pattern, list, word){
    if(!list.length){ return ''; }
    var one = list.length === 1;
    var h = dash(pattern) + '<span>' + list.length + (one ? ' is ' : ' are ') + word + ': ';
    if(word === 'structural'){
      h += support(list) + ' supports ' + (one ? 'it' : 'them') + '.';
    } else {
      h += 'no import supports ' + (one ? 'it' : 'them') + '. '
        + list.slice(0, 4).map(edgeButton).join(', ')
        + (list.length > 4 ? ' and ' + (list.length - 4) + ' more' : '') + '.';
    }
    return h + '</span>';
  }
  function flowsSection(){
    var sec = byId('chg-flows');
    if(!sec || !SOURCE.length){ return; }
    var structural = LOST.filter(function(i){ return EDGES[i].evidence === 'structural'; });
    var declared = LOST.filter(function(i){ return EDGES[i].evidence === 'declared'; });
    var old = LOST.filter(recorded).length;
    var h = '<div class="chg-sec__h"><h3 class="chg-cap">FLOWS TO EXAMINE</h3>'
      + '<span class="chg-sec__n">' + LOST.length + '</span></div>';
    if(!LOST.length){
      h += '<p class="chg-text">Each flow of a component with changed source has a source '
        + 'review or connects to an actor.</p>';
    } else {
      h += '<div class="chg-flowrows">' + flowRow('3 3', structural, 'structural')
        + flowRow('8 5', declared, 'declared') + '</div>';
      var bare = LOST.filter(undigested).length, of = ' of ' + LOST.length;
      h += '<p class="chg-foot">' + (old ? (old === LOST.length ? (LOST.length === 1
        ? 'This flow has' : 'All ' + LOST.length + ' have') : old + of + ' have')
        + ' a recorded source review that does not agree with the stored source. ' : '')
        + (bare ? bare + of + (bare === 1 ? ' has' : ' have')
          + ' source references but no review digest. ' : '')
        + (old ? 'Do a new source review.' : 'Do a source review.') + '</p>';
    }
    sec.innerHTML = h; sec.hidden = false;
  }
  function seqSection(){
    var sec = byId('chg-seqs'), J = M.journeys || [];
    if(!sec || !J.length || !SOURCE.length){ return; }
    var rows = [];
    J.forEach(function(j, k){
      var steps = [];
      j.steps.forEach(function(st, s){ if(touches(st.edge, SOURCE)){ steps.push(s); } });
      if(steps.length){ rows.push({j:j, k:k, steps:steps}); }
    });
    rows.sort(function(a, b){ return b.steps.length - a.steps.length || a.k - b.k; });
    var h = '<div class="chg-sec__h"><h3 class="chg-cap">SEQUENCES WITH A CHANGED STEP</h3>'
      + '<span class="chg-sec__n">' + rows.length + ' of ' + J.length + '</span></div>';
    rows.forEach(function(r){
      h += '<button type="button" class="chg-seq" data-journey="' + r.k
        + '" data-journey-step="' + r.steps[0] + '" aria-pressed="false"><span>' + esc(r.j.label)
        + '</span><span class="chg-seq__steps">' + (r.steps.length === 1 ? 'step ' : 'steps ')
        + r.steps.map(function(s){ return s + 1; }).join(', ') + '</span></button>';
    });
    h += '<p class="chg-foot">' + (rows.length ? 'The list marks a step if an end of its flow '
      + 'has changed source.' : 'No sequence step has a flow to a component with changed source.')
      + '</p>';
    sec.innerHTML = h; sec.hidden = false;
  }
  function cards(){
    all('[data-change-card]', panel).forEach(function(card){
      var id = card.dataset.changeCard, mine = lostOf(id), old = mine.filter(recorded).length;
      var bare = mine.filter(undigested).length, none = mine.length - old - bare;
      var note = card.querySelector('.chg-card__note');
      var flag = card.querySelector('.chg-card__flag');
      if(!mine.length){ return; }
      flag.hidden = false;
      note.hidden = false;
      note.textContent = (old
        ? old + (old === 1 ? ' flow has' : ' flows have') + ' a recorded source review that does '
          + 'not agree with this source. ' : '')
        + (bare ? bare + (bare === 1 ? ' flow has' : ' flows have')
          + ' source references but no review digest. ' : '')
        + (none ? none + (none === 1 ? ' flow has' : ' flows have') + ' no source review. ' : '')
        + 'Do a new source review.';
    });
  }
  function summary(){
    var p = byId('chg-summary');
    if(!p){ return; }
    var w = where(), f = flowsSentence();
    p.querySelector('[data-chg-where]').textContent = w ? w + ' ' : '';
    p.querySelector('[data-chg-flows]').textContent = f ? ' ' + f : '';
  }

  // ---- the source changes of the selected component ----------------------
  // The `types` bucket holds each type declaration. The facts give its category.
  var KIND = {operations:'functions', types:'types', refusals:'exceptions',
    constants:'constants'};
  var CATEGORY = {type_alias:'type alias'};
  function named(surface, kind, name){
    var found = kind === 'types' ? (surface.categories || {})[name] : null;
    return found && found.length ? name + ' (' + found.map(function(c){
      return CATEGORY[c] || c; }).join(', ') + ')' : name;
  }
  var ACTION = {added:'Added', removed:'Removed', changed:'Changed'};
  function sourceChanges(id){
    var record = (CMP.parts || {})[id], h = '<h4 class="chg-h4">Source changes</h4>';
    if(!record){ return h + '<p>' + ((CMP.adjacent || []).indexOf(id) >= 0
      ? 'This component imports changed source. Examine possible effects.'
      : 'The comparison has no source changes for this component.') + '</p>'; }
    var surface = record.surface || {}, count = 0;
    if(record.modules.length){
      h += '<p>Changed source modules: <code>' + esc(record.modules.join(', ')) + '</code>.</p>'; }
    ['added', 'removed', 'changed'].forEach(function(action){
      Object.keys(surface[action] || {}).forEach(function(kind){
        var list = surface[action][kind]; if(!list.length){ return; } count += list.length;
        h += '<p><b>' + ACTION[action] + ' ' + esc(KIND[kind] || kind) + '</b>: <code>'
          + esc(list.map(function(n){ return named(surface, kind, n); }).join(', '))
          + '</code>.</p>';
      });
    });
    var tests = 0;
    ['added', 'removed'].forEach(function(action){
      var list = surface['tests_' + action] || []; if(!list.length){ return; }
      tests += list.length;
      h += '<details class="chg-tests"><summary><b>Tests ' + action + '</b> (' + list.length
        + ')</summary><p><code>' + esc(list.join(', ')) + '</code></p></details>';
    });
    if(tests){ h += '<p>A test name does not show test coverage.</p>'; }
    count += tests;
    if(!count){ h += '<p>The comparison found no difference in public names or tests. '
      + 'The source files can contain other changes.</p>'; }
    record.modules.filter(function(m){ return (CMP.unparsed || []).indexOf(m) >= 0; })
      .forEach(function(m){ h += '<p class="source-unknown">systemap could not parse the source '
        + 'differences for <code>' + esc(m) + '</code>. Do the comparison again after you '
        + 'correct the source or extractor error.</p>'; });
    Object.keys(record.unknown || {}).forEach(function(m){
      Object.keys(record.unknown[m]).forEach(function(revision){
        record.unknown[m][revision].forEach(function(issue){
          h += '<p class="source-unknown">Unknown ' + esc(revision) + ' surface for <code>'
            + esc(m) + '</code>: ' + esc(issue.reason || 'systemap could not read the source.')
            + (issue.line === undefined ? '' : ' (line ' + esc(issue.line)
              + (issue.column == null ? '' : ', column ' + esc(issue.column)) + ')') + '.</p>';
        }); }); });
    return h;
  }
  // The rules for a component with changed source: the change must keep them.
  function rulesOf(id){
    if(MARK[id] !== 'changed'){ return ''; }
    var h = '';
    (META.rules || []).forEach(function(r){
      if((r.ids || []).indexOf(id) >= 0){
        h += '<p class="rule-row"><b>' + r.n + '</b>' + esc(r.text) + '</p>'; }
    });
    return h ? '<h4 class="chg-h4">Rules for this component</h4>' + h : '';
  }
  var TAG = {changed:'CHANGED', tests:'TESTS', imports:'IMPORTS'};
  var SAYS = {changed:'changed source', tests:'only tests changed',
    imports:'imports changed source'};
  function flowCard(i){
    // The selected flow: its artifact, its ends and its evidence, as the change map has them.
    var e = EDGES[i], card = document.createElement('article');
    card.setAttribute('class', 'chg-card chg-flowpick'); card.setAttribute('id', 'chg-flow');
    card.setAttribute('data-relationship', '');
    card.innerHTML = '<h4 class="chg-h4">Selected flow</h4><p class="chg-flowpick__art"><b>'
      + esc(e.art) + '</b> ' + esc(e.from) + ' to ' + esc(e.to) + '</p><p class="chg-card__note">'
      + 'Evidence state: ' + esc(M.evidenceLabel(e.evidence)) + '.</p><p class="chg-card__note">'
      + esc(e.evidence_says || '') + '</p>'
      + (LOST.indexOf(i) >= 0 && recorded(i) ? '<p class="chg-card__note">The recorded source '
        + 'review does not agree with the stored source. Do a new source review.</p>' : '')
      + (LOST.indexOf(i) >= 0 && undigested(i) ? '<p class="chg-card__note">The flow has source '
        + 'references but no review digest. Do a source review.</p>' : '');
    return card;
  }
  function showSelection(id, edge){
    var parts = byId('chg-parts');
    ['chg-pick', 'chg-flow'].forEach(function(name){
      var old = byId(name); if(old){ old.parentNode.removeChild(old); } });
    if(parts){ parts.classList.toggle('chg-picked', !!id); }
    all('[data-change-card]', panel).forEach(function(card){
      var on = card.dataset.changeCard === id;
      card.setAttribute('aria-current', on ? 'true' : 'false');
      card.querySelector('.chg-card__head').setAttribute('aria-pressed', on ? 'true' : 'false');
      var detail = card.querySelector('.chg-card__detail');
      detail.hidden = !on; detail.innerHTML = on ? sourceChanges(id) + rulesOf(id) : '';
      detail.classList.toggle('comparison-source', on);
      if(on && card.scrollIntoView){ card.scrollIntoView({block:'nearest'}); }
    });
    var first = null;
    if(id && parts && !panel.querySelector('[data-change-card="' + id + '"]')){
      first = parts.insertBefore(pickCard(id), parts.firstChild); }
    // The selected flow goes first, above the card of its component.
    if(parts && EDGES[edge]){ first = parts.insertBefore(flowCard(edge), parts.firstChild); }
    if(first && first.scrollIntoView){ first.scrollIntoView({block:'nearest'}); }
  }
  function pickCard(id){
    var mark = MARK[id], d = D[id] || {};
    var card = document.createElement('article');
    card.setAttribute('class', 'chg-card'); card.setAttribute('id', 'chg-pick');
    card.setAttribute('aria-current', 'true');
    card.innerHTML = '<div class="chg-card__head"><span class="chg-tag chg-tag--'
      + (TAG[mark] ? mark : 'none') + '">' + (TAG[mark] || 'NO CHANGE') + '</span><b>'
      + esc(id) + '</b></div><p class="chg-card__note">' + esc(d.plain || '') + '</p>'
      + '<div class="chg-card__detail comparison-source">' + sourceChanges(id) + rulesOf(id)
      + '</div>';
    return card;
  }

  // ---- the legend and the readout of the change map ---------------------
  // The shell draws them in #map-legend and #map-context through these hooks.
  function lg(swatch, label){
    return '<span class="lg">' + swatch + esc(label) + '</span>'; }
  function legendHtml(){
    var h = '';
    if(SOURCE.length){ h += lg('<span class="chg-tag chg-tag--changed">CHANGED</span>',
      'Source changed'); }
    if(TESTS.length){ h += lg('<span class="chg-tag chg-tag--tests">TESTS</span>',
      'Only tests changed'); }
    if(IMPORTS.length){ h += lg('<span class="chg-tag chg-tag--imports">IMPORTS</span>',
      'Imports changed source'); }
    if(LOST.length){ h += lg('<i class="lg__line--chg"></i>', 'No source review'); }
    return h;
  }
  function plural(n, word){ return n + ' ' + word + (n === 1 ? '' : 's'); }
  function readoutText(){
    var st = M.state, e = EDGES[st.edge];
    if(e){ return e.art + ' · ' + e.from + ' → ' + e.to + ' · ' + M.evidenceLabel(e.evidence); }
    if(st.focus){
      var mark = MARK[st.focus];
      return st.focus + ' · ' + (SAYS[mark] || 'no source change')
        + (mark === 'changed' && lostOf(st.focus).length ? ' · source review necessary' : '');
    }
    if(holding){ return 'change marks hidden'; }
    var out = [];
    if(SOURCE.length){ out.push(SOURCE.length + ' changed'); }
    if(TESTS.length){ out.push(TESTS.length + ' tests'); }
    if(IMPORTS.length){ out.push(IMPORTS.length + ' imports'); }
    out.push(plural(LOST.length, 'flow'));
    return out.join(' · ');
  }
  function inView(){ return !!P && P.mode() === 'change'; }
  if(P){
    P.legendFor.unshift(function(){ return inView() ? legendHtml() : null; });
    P.readoutFor.unshift(function(){ return inView() ? readoutText() : null; });
  }
  function sync(){ if(P && P.syncFrame){ window.requestAnimationFrame(P.syncFrame); } }

  // ---- the ordered reveal and Hold B -------------------------------------
  // Rings 160 ms, then the flows 400 ms, then the tags 160 ms, region 1
  // first. A flow with a recorded source review starts solid; the reveal
  // changes it to its evidence dash and to the change color.
  var STAGGER = 30, RING = 160, LINE = 400, TAGS = 160;
  var revealed = false, revealTimer = 0, holding = false;
  var nodes = all('.node[data-change]', C);
  var flows = all('.flow[data-change="lost"]', C);
  flows.forEach(function(p){
    var i = +p.dataset.edge, dashes = (p.getAttribute('stroke-dasharray') || '').trim();
    if(!recorded(i) || !dashes){ return; }
    var sum = dashes.split(/[\s,]+/).reduce(function(a, b){ return a + (+b || 0); }, 0);
    p.setAttribute('data-chg-recorded', '');
    p.style.setProperty('--chg-solid', sum + ' 0');
  });
  function lastRank(list, of){
    return list.reduce(function(m, x){ return Math.max(m, of(x)); }, 0); }
  function flowRank(p){
    var e = EDGES[+p.dataset.edge];
    var ends = [e.from, e.to].filter(function(id){ return SOURCE.indexOf(id) >= 0; });
    return Math.min.apply(null, ends.map(rank));
  }
  function nodeRank(n){ return rank(n.dataset.id); }
  function finishReveal(){
    if(revealTimer){ clearTimeout(revealTimer); revealTimer = 0; }
    C.classList.remove('chg-base', 'chg-reveal');
  }
  function reveal(){
    if(revealed){ return; }
    revealed = true;
    if(reduced() || holding){ finishReveal(); return; }
    var ringEnd = RING + STAGGER * lastRank(nodes, nodeRank);
    var lineEnd = ringEnd + LINE + STAGGER * lastRank(flows, flowRank);
    nodes.forEach(function(n){
      n.style.setProperty('--chg-d', STAGGER * nodeRank(n) + 'ms');
      var tag = n.querySelector('.chg-tag');
      if(tag){ tag.style.setProperty('--chg-d', lineEnd + STAGGER * nodeRank(n) + 'ms'); }
    });
    flows.forEach(function(p){
      p.style.setProperty('--chg-d', ringEnd + STAGGER * flowRank(p) + 'ms'); });
    void C.getBoundingClientRect();
    C.classList.add('chg-reveal');
    C.classList.remove('chg-base');
    revealTimer = setTimeout(finishReveal, lineEnd + TAGS + STAGGER * (REGIONS.length + 1));
  }
  C.classList.add('chg-base');
  var holdBtn = byId('chg-hold');
  function hold(on){
    if(on === holding){ return; }
    holding = on;
    if(on && !revealed){ revealed = true; }
    finishReveal();
    C.classList.toggle('chg-held', on);
    if(holdBtn){ holdBtn.setAttribute('aria-pressed', on ? 'true' : 'false'); }
    sync();
  }
  function typing(t){
    var tag = t && t.tagName;
    return tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA' ||
      !!(t && t.isContentEditable);
  }
  document.addEventListener('keydown', function(e){
    if(body.dataset.mode !== 'change' || e.altKey || e.ctrlKey || e.metaKey || typing(e.target)){
      return; }
    if(e.key === 'b' || e.key === 'B'){ e.preventDefault(); hold(true); }
  });
  document.addEventListener('keyup', function(e){
    if(e.key === 'b' || e.key === 'B'){ hold(false); }
  });
  window.addEventListener('blur', function(){ hold(false); });
  if(holdBtn){
    holdBtn.addEventListener('pointerdown', function(e){
      if(holdBtn.setPointerCapture){ try { holdBtn.setPointerCapture(e.pointerId); } catch(_x){} }
      hold(true);
    });
    ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(function(name){
      holdBtn.addEventListener(name, function(){ hold(false); }); });
    holdBtn.addEventListener('keydown', function(e){
      if(e.key === ' ' || e.key === 'Enter'){ e.preventDefault(); hold(true); } });
    holdBtn.addEventListener('keyup', function(e){
      if(e.key === ' ' || e.key === 'Enter'){ hold(false); } });
  }
  function opened(){
    window.requestAnimationFrame(function(){
      // The map was hidden: draw the view again so the zoom readout has its scale.
      M.view.restore(M.view.snapshot(), true);
      reveal(); sync();
    });
  }
  document.addEventListener('systemap:mode', function(e){
    if(e.detail && e.detail.mode === 'change'){ opened(); } else { hold(false); }
  });
  if(body.dataset.mode === 'change'){ opened(); }

  // ---- selection: the change map and the panel ---------------------------
  // A selection keeps the view, so the whole change stays in sight.
  var keep = null;
  function remember(){ keep = M.view.snapshot(); }
  ['click', 'keydown'].forEach(function(n){ C.addEventListener(n, remember, true); });
  C.addEventListener('systemap:select', function(e){
    if(keep){ M.view.restore(keep, true); keep = null; }
    showSelection(e.detail.id, e.detail.edge); sync();
  });
  C.addEventListener('systemap:clear', function(){ keep = null; showSelection(''); sync(); });
  panel.addEventListener('click', function(e){
    var go = e.target.closest && e.target.closest('[data-change-go]');
    if(go){ e.preventDefault();
      remember();
      if(M.state.focus === go.dataset.changeGo){ M.clear(); }
      else { M.select(go.dataset.changeGo); }
      return; }
    var edge = e.target.closest && e.target.closest('[data-change-edge]');
    if(edge){ e.preventDefault(); remember(); M.inspectFlow(+edge.dataset.changeEdge); }
  });
  window.addEventListener('keydown', function(e){
    if(e.key !== 'Escape' || body.dataset.mode !== 'change' || !M.state.focus){ return; }
    var t = e.target;
    if(typing(t) || (t && t.closest && t.closest('#palette, #submap, #keys, #present'))){ return; }
    M.clear(); M.view.back(); e.preventDefault(); e.stopPropagation();
  }, true);

  summary(); cards(); flowsSection(); seqSection(); sync();
})();
"""
