"""Full-screen steps: one sequence step at a time, with the map that follows the step.

The overlay takes the map drawing while it is open and gives it back when it
closes. The left and right arrow keys go to the previous or next step, W shows
the whole route, and Escape closes the overlay. F opens it from the Sequences view.
"""

CSS = r"""
/* ---- full-screen steps ----------------------------------------------------- */
.present{position:fixed;inset:0;z-index:45;overflow:hidden;color:var(--ink);
background-color:var(--map);background-image:radial-gradient(var(--grid) 1px,transparent 1px);
background-size:24px 24px}
body.present-open{overflow:hidden}
.present__map{position:absolute;left:0;right:0;top:0;bottom:200px}
.present__map .stage{width:100%;height:100%}
.present__bar{position:absolute;left:0;right:0;top:0;height:64px;display:flex;align-items:center;
gap:14px;padding:0 28px;background:linear-gradient(var(--map) 40%,transparent);
pointer-events:none}
.present__bar>*{pointer-events:auto}
.present__mark{width:20px;height:20px;flex:none}
.present__mark path{fill:none;stroke:var(--ink);stroke-width:44;stroke-linecap:round;
stroke-linejoin:round}
.present__mark circle{fill:var(--brand)}
.present__title{font:500 15px/1 var(--fs);color:var(--ink);white-space:nowrap}
.present__entry{font:12px/1 var(--fm);color:var(--ink-3);white-space:nowrap}
.present__gap{flex:1}
.present__key{display:flex;align-items:center;gap:8px;font:12px/1 var(--fs);color:var(--ink-3);
white-space:nowrap}
.present__key+.present__key{margin-left:12px}
.present kbd{color:var(--ink-2);padding:1px 6px}
.present__close{margin-left:12px;height:32px;min-height:32px;padding:0 12px;display:flex;
align-items:center;gap:8px;border:1px solid var(--line-2);border-radius:6px;background:var(--map);
color:var(--ink-2);font:13px var(--fs)}
.present__cap{position:absolute;left:0;right:0;bottom:0;height:200px;box-sizing:border-box;
padding:26px 28px 24px;border-top:1px solid var(--line);background:var(--surface);display:grid;
grid-template-columns:132px minmax(0,1fr) 300px;gap:0 32px}
.present__num{display:flex;flex-direction:column;gap:2px}
.present__big{font:600 64px/64px var(--fm);color:var(--accent);letter-spacing:-.04em}
.present__of{font:13px/18px var(--fm);color:var(--ink-3)}
.present__text{display:flex;flex-direction:column;gap:12px;min-width:0}
.present .present__head{margin:0;display:flex;flex-wrap:wrap;align-items:center;gap:10px;
font:14px/20px var(--fm);color:var(--ink-2)}
.present__head i{font-style:normal;color:var(--ink-3)}
.present__head b{color:var(--accent);font-weight:600}
:root[data-theme="light"] .present__head b{background:var(--hl);padding:0 3px;border-radius:2px}
.present__head .seq-tag{margin-left:8px}
.present__head code{font:13px/18px var(--fm);color:var(--ink)}
.present .present__say{margin:0;max-width:860px;font:400 24px/34px var(--fs);color:var(--ink);
letter-spacing:-.005em;overflow-wrap:anywhere}
.present__nav{display:flex;flex-direction:column;gap:16px;justify-content:space-between}
.present__prog{display:grid;grid-template-columns:repeat(var(--n,1),1fr);gap:6px;padding-top:8px}
.present__prog i{height:4px;border-radius:2px;background:var(--line-2)}
.present__prog i.was{background:var(--ink-2)}
.present__prog i.now{background:var(--accent)}
.present__btns{display:grid;grid-template-columns:1fr 1.4fr;gap:8px}
.present__btns button{height:44px;min-height:44px;border:1px solid var(--line-2);border-radius:8px;
background:transparent;color:var(--ink-2);font:14px var(--fs);white-space:nowrap;overflow:hidden;
text-overflow:ellipsis;padding:0 12px}
.present__btns .present__next{border-color:var(--ink);background:var(--ink);color:var(--bg);
font-weight:600}
.present__btns .present__next:hover{background:var(--ink);color:var(--bg);opacity:.9}
@media(max-width:820px){.present__map{bottom:300px}.present__cap{height:300px;
grid-template-columns:72px minmax(0,1fr);padding:16px;gap:8px 16px}
.present__nav{grid-column:1/-1}.present__big{font-size:40px;line-height:40px}
.present__say{font-size:17px!important;line-height:25px!important}.present__key{display:none}
.present__bar{padding:0 16px}.present__entry,.present__gap{display:none}
.present__title{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis}}
"""

SCRIPT = r"""
(function(){
  var svg = document.getElementById('schematic');
  function byId(id){ return document.getElementById(id); }
  var fullBtn = byId('jfull'), box = byId('present'), mapBox = byId('presentmap');
  var stage = byId('stage'), home = stage && stage.parentNode;
  if(!svg || !svg.systemap || !svg.page || !svg.page.sequence || !box || !mapBox || !home){
    if(fullBtn){ fullBtn.hidden = true; }
    return;
  }
  var A = svg.systemap, P = svg.page, S = P.sequence, W = window.systemapWorkspace || {};
  var title = byId('presenttitle'), entry = byId('presententry'), num = byId('presentn');
  var of = byId('presentof'), head = byId('presenthead'), say = byId('presentsay');
  var prog = byId('presentprog'), prevB = byId('presentprev'), nextB = byId('presentnext');
  var closeB = byId('presentclose'), ARROW = ' → ';
  var open = false, opener = null, before = null, held = [], wentFull = false, resizing = 0;
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function meta(k){ return ((W.sequences || {}).journeys || [])[k] || {}; }
  function roles(st){
    var h = '';
    if((st.acts || []).length){ h += '<span class="seq-tag seq-tag--acts">ACTS</span><code>'
      + esc(st.acts.join(', ')) + '</code>'; }
    if((st.measures || []).length){ h += '<span class="seq-tag seq-tag--meas">MEASURES</span>'
      + '<code>' + esc(st.measures.join(', ')) + '</code>'; }
    return h;
  }
  function caption(){
    var x = S.state(), j = A.journeys[x.j];
    if(!open || !j){ return; }
    var n = j.steps.length, whole = x.view !== 'steps', st = j.steps[x.s];
    title.textContent = j.label;
    entry.textContent = meta(x.j).entry || '';
    num.textContent = whole ? String(n) : String(x.s + 1);
    of.textContent = whole ? (n === 1 ? 'step' : 'steps') : 'of ' + n + ' steps';
    if(whole || !st){
      head.innerHTML = '<b>Whole route</b>';
      say.textContent = 'Press the right arrow key to start at step 1.';
    } else {
      var e = A.edges[st.edge] || {from:'', to:'', art:''};
      head.innerHTML = '<span>' + esc(e.from + ARROW + e.to) + '</span><i>·</i><b>'
        + esc(e.art) + '</b>' + roles(st);
      say.textContent = st.say;
    }
    prog.style.setProperty('--n', String(Math.max(1, n)));
    var cells = '';
    for(var k = 0; k < n; k++){
      cells += '<i class="' + (whole || k < x.s ? 'was' : (k === x.s ? 'now' : '')) + '"></i>'; }
    prog.innerHTML = cells;
    prevB.disabled = whole || x.s === 0;
    var after = !whole && x.s < n - 1 ? A.edges[j.steps[x.s + 1].edge] : null;
    nextB.textContent = whole ? 'Start at step 1'
      : (after ? 'Next: ' + after.art : (x.s < n - 1 ? 'Next' : 'Whole route'));
  }
  function hold(){
    Array.prototype.slice.call(document.body.children).forEach(function(n){
      if(n === box || n.tagName === 'SCRIPT' || n.tagName === 'STYLE'){ return; }
      held.push({node:n, inert:n.hasAttribute('inert')});
      n.setAttribute('inert', '');
    });
  }
  function release(){
    held.forEach(function(h){ if(!h.inert){ h.node.removeAttribute('inert'); } });
    held = [];
  }
  function go(view, s){
    var x = S.state(), from = x.view;
    S.go(view, s, view === 'steps' ? (from === 'steps' ? 'keep' : 'frame') : 'fit');
  }
  function step(d){
    var x = S.state(), j = A.journeys[x.j];
    if(!j){ return; }
    if(x.view !== 'steps'){ if(d > 0 && j.steps.length){ go('steps', 0); } return; }
    var s = x.s + d;
    if(s >= 0 && s < j.steps.length){ go('steps', s); }
    else if(s >= j.steps.length){ go('whole', x.s); }
  }
  function openPresent(){
    if(open || !P.journey.active()){ return; }
    var x = S.state(), j = A.journeys[x.j];
    if(!j || !j.steps.length){ return; }
    opener = document.activeElement;
    before = A.view.snapshot();
    open = true;
    mapBox.appendChild(stage);
    box.hidden = false;
    document.body.classList.add('present-open');
    hold();
    S.presenting(true);
    S.go('steps', x.view === 'steps' ? x.s : 0, 'frame');
    if(closeB){ closeB.focus({preventScroll:true}); }
    try {
      if(box.requestFullscreen && !document.fullscreenElement){
        var asked = box.requestFullscreen();
        if(asked && asked.then){ asked.then(function(){ wentFull = true; }, function(){}); }
      }
    } catch(_x){}
  }
  function closePresent(quiet){
    if(!open){ return; }
    open = false;
    try {
      if(document.fullscreenElement === box && document.exitFullscreen){
        var left = document.exitFullscreen();
        if(left && left.then){ left.then(null, function(){}); }
      }
    } catch(_x){}
    wentFull = false;
    home.appendChild(stage);
    box.hidden = true;
    document.body.classList.remove('present-open');
    release();
    S.presenting(false);
    if(quiet !== true && P.journey.active()){
      var x = S.state();
      A.view.restore(before, true);
      S.go(x.view, x.s, x.view === 'steps' ? 'keep' : 'fit');
    }
    var back = opener && opener.isConnected !== false ? opener : fullBtn;
    if(back && back.focus){ back.focus({preventScroll:true}); }
    opener = null;
  }
  S.closePresent = closePresent;
  S.on(caption);
  if(fullBtn){ fullBtn.addEventListener('click', openPresent); }
  if(closeB){ closeB.addEventListener('click', function(){ closePresent(); }); }
  if(prevB){ prevB.addEventListener('click', function(){ step(-1); }); }
  if(nextB){ nextB.addEventListener('click', function(){ step(1); }); }
  // A click in the map selects nothing while the overlay is open; a drag still moves the map.
  box.addEventListener('click', function(e){
    if(svg.contains(e.target)){ e.stopPropagation(); e.preventDefault(); }
  }, true);
  document.addEventListener('fullscreenchange', function(){
    if(document.fullscreenElement === box){ wentFull = true; return; }
    if(open && wentFull){ closePresent(); }
  });
  window.addEventListener('resize', function(){
    if(!open || resizing){ return; }
    resizing = requestAnimationFrame(function(){
      resizing = 0;
      var x = S.state();
      if(open){ S.go(x.view, x.s, x.view === 'steps' ? 'frame' : 'fit'); }
    });
  });
  function typing(t){
    var tag = t && t.tagName;
    return tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA'
      || !!(t && t.isContentEditable);
  }
  function trap(e){
    var list = Array.prototype.slice.call(box.querySelectorAll('button')).filter(function(b){
      return !b.disabled && !b.hidden; });
    if(!list.length){ return; }
    var i = list.indexOf(document.activeElement);
    var to = e.shiftKey ? (i <= 0 ? list.length - 1 : i - 1) : (i + 1) % list.length;
    list[to].focus();
    e.preventDefault();
  }
  document.addEventListener('keydown', function(e){
    if(e.altKey || e.ctrlKey || e.metaKey){ return; }
    var k = e.key.toLowerCase();
    if(!open){
      var sheet = byId('keys');
      if(k === 'f' && P.mode() === 'trace' && P.journey.active() && !typing(e.target)
        && !(sheet && !sheet.hidden)){ openPresent(); e.preventDefault(); }
      return;
    }
    if(e.key === 'Tab'){ trap(e); return; }
    if(e.key === 'Escape' || k === 'f'){ closePresent(); }
    else if(e.key === 'ArrowRight'){ step(1); }
    else if(e.key === 'ArrowLeft'){ step(-1); }
    else if(k === 'w'){ go('whole', S.state().s); }
    else { return; }
    e.preventDefault();
  });
})();
"""


def html() -> str:
    """Give the full-screen steps overlay. It stays hidden until the reader opens it."""
    return (
        '<div class="present" id="present" role="dialog" aria-modal="true" '
        'aria-label="Sequence in full screen" hidden>'
        '<div class="present__map" id="presentmap"></div>'
        '<div class="present__bar">'
        '<svg class="present__mark" viewBox="0 0 512 512" aria-hidden="true">'
        '<path d="M380,132 H172 V256 H340 V380 H132"/><circle cx="380" cy="132" r="44"/>'
        '<circle cx="132" cy="380" r="44"/></svg>'
        '<span class="present__title" id="presenttitle"></span>'
        '<span class="present__entry" id="presententry"></span>'
        '<span class="present__gap"></span>'
        '<span class="present__key"><kbd>←</kbd><kbd>→</kbd>Step</span>'
        '<span class="present__key"><kbd>W</kbd>Whole route</span>'
        '<button type="button" class="present__close" id="presentclose">Close'
        "<kbd>Esc</kbd></button></div>"
        '<section class="present__cap" aria-live="polite" aria-label="Step">'
        '<div class="present__num"><span class="present__big" id="presentn"></span>'
        '<span class="present__of" id="presentof"></span></div>'
        '<div class="present__text"><p class="present__head" id="presenthead"></p>'
        '<p class="present__say" id="presentsay"></p></div>'
        '<div class="present__nav"><div class="present__prog" id="presentprog" '
        'aria-hidden="true"></div><div class="present__btns">'
        '<button type="button" id="presentprev">Previous</button>'
        '<button type="button" class="present__next" id="presentnext">Next</button>'
        "</div></div></section></div>"
    )
