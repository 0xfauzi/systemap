"""Motion, surface and small controls for the map page.

The mark, the keyboard sheet, layer changes, the map surface, card depth and
the glow of a selection. Each motion runs one time and shows direction or
order. With reduced motion, the page shows the final state at once."""

# A fine grain on the map surface: light specks on Ink, dark specks on Paper.
# The noise is static. Its alpha comes from the red channel of the noise.
_GRAIN = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E"
    "%3Cfilter id='g'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2' "
    "stitchTiles='stitch'/%3E%3CfeColorMatrix values='0 0 0 0 {c} 0 0 0 0 {c} 0 0 0 0 {c} "
    "{a} 0 0 0 0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23g)'/%3E"
    "%3C/svg%3E"
)
_GRID = "radial-gradient(var(--grid) 1px,transparent 1px)"

SURFACE_CSS = (
    "/* ---- the map surface: a fine grain under the dot grid, a soft edge --------- */\n"
    f'.map{{background-image:url("{_GRAIN.format(c=1, a=".07")}"),{_GRID};'
    "background-size:160px 160px,24px 24px}\n"
    f':root[data-theme="light"] .map{{background-image:url("{_GRAIN.format(c=0, a=".06")}"),'
    f"{_GRID}}}\n"
    '.mapwrap::after{content:"";position:absolute;inset:0;pointer-events:none;'
    "background:radial-gradient(130% 110% at 50% 42%,transparent 62%,"
    "color-mix(in srgb,#000 24%,transparent))}\n"
    ':root[data-theme="light"] .mapwrap::after{background:radial-gradient(130% 110% at 50% 42%,'
    "transparent 62%,color-mix(in srgb,#3a2e14 7%,transparent))}\n"
)


CSS = r"""
/* ---- card depth: a shade under each card, a lift on hover ----------------- */
/* The shade is a copy of the card shape with no blur: a blur on every card
   made panning slower (bench/jev/README.md). Only the selection has a blur. */
.node__shade{fill:#000;fill-opacity:.42;stroke:none;transform:translateY(1.6px);
transition:transform .16s ease-out,fill-opacity .16s ease-out}
.node:not(.dim):not(.quiet):hover .node__shade{transform:translateY(3.2px);fill-opacity:.5}
:root[data-theme="light"] .node__shade{fill:#4a3c20;fill-opacity:.13}
:root[data-theme="light"] .node:not(.dim):not(.quiet):hover .node__shade{fill-opacity:.18}
#schematic .node.sel .node__box,#schematic .node.acts .node__box{
filter:drop-shadow(0 0 5px color-mix(in srgb,var(--accent) 55%,transparent))}
:root[data-theme="light"] #schematic :is(.node.sel,.node.acts) .node__box{
filter:drop-shadow(0 0 6px var(--hl))}
/* ---- a selected line and the current step line glow --------------------- */
#schematic .flow.hot,#schematic .seq-line--now,#schematic .seq-line--route{
filter:drop-shadow(0 0 2.5px color-mix(in srgb,var(--accent) 60%,transparent))}
:root[data-theme="light"] #schematic :is(.flow.hot,.seq-line--now,.seq-line--route){
filter:drop-shadow(0 0 3px var(--hl))}

/* ---- a card under the pointer shows its lines and the cards at their ends -- */
#schematic .flow,#schematic .flowlbl{transition:stroke-opacity .14s ease-out,opacity .14s ease-out,
stroke-width .14s ease-out}
#schematic.card-peek .flow:not(.card-lit){stroke-opacity:.18}
#schematic.card-peek .flow.card-lit{stroke-width:2.2}
#schematic.card-peek .flowlbl:not(.card-lit){opacity:.25}
#schematic.card-peek .node:not(.card-lit):not(.quiet):not(.dim){opacity:.6}

/* ---- the cards come in one time, in reading order ----------------------- */
@keyframes card-in{from{opacity:0;transform:translateY(5px)}}
@media (prefers-reduced-motion:no-preference){
html:not([data-reduce-motion="true"]) #schematic.cards-in .node{
animation:card-in .32s cubic-bezier(.2,.7,.2,1) backwards;animation-delay:var(--in,0ms)}
html:not([data-reduce-motion="true"]).scheme-fade :is(body,body *){
transition:background-color .24s,color .24s,border-color .24s,fill .24s,stroke .24s!important}
}

/* ---- the mark draws one time: the route, then its two ends --------------- */
@keyframes mark-draw{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}
@keyframes mark-dot{from{opacity:0;transform:scale(.4)}to{opacity:1;transform:none}}
.mark__path{stroke-dasharray:1 1;stroke-dashoffset:0}
.mark__dot{transform-box:fill-box;transform-origin:center}
@media (prefers-reduced-motion:no-preference){
html:not([data-reduce-motion="true"]) .mark__path{
animation:mark-draw .6s cubic-bezier(.45,0,.25,1) both}
html:not([data-reduce-motion="true"]) .mark__dot{animation:mark-dot .16s ease-out .6s both}
}

/* ---- the keyboard sheet ---------------------------------------------------- */
.keys{position:fixed;inset:0;z-index:40;display:flex;align-items:center;justify-content:center;
padding:16px;background:color-mix(in srgb,var(--bg) 72%,transparent)}
.keys[hidden]{display:none}
.keys__box{box-sizing:border-box;width:min(340px,100%);max-height:calc(100vh - 32px);overflow:auto;
display:flex;flex-direction:column;gap:10px;padding:16px;border:1px solid var(--line-2);
border-radius:10px;background:var(--surface);color:var(--ink);
box-shadow:0 16px 48px rgba(0,0,0,.28);outline:none}
.keys__head{display:flex;justify-content:space-between;align-items:center;gap:12px}
.keys__title{margin:0;font:600 15px/20px var(--fs);color:var(--ink)}
.keys__note{margin:0;font:13px/19px var(--fs);color:var(--ink-2)}
.keys__list{display:grid;grid-template-columns:auto minmax(0,1fr);gap:5px 10px;align-items:center;
margin:6px 0 0;font:12px/16px var(--fs)}
.keys__list dt{justify-self:start;margin:0}
.keys__list dd{margin:0;color:var(--ink-2)}
.keys__list kbd{display:inline-block;font:11px/16px var(--fm);color:var(--ink);background:none;
border:1px solid var(--line-2);border-bottom-width:2px;border-radius:4px;padding:0 6px}
.keys .keys__close{height:28px;min-height:0;padding:0 10px;border:1px solid var(--line-2);
border-radius:6px;background:none;color:var(--ink-2);font:12px var(--fs);cursor:pointer}
.keys .keys__close:hover{color:var(--ink);background:var(--raised)}
.keys .keys__close:focus-visible{outline:2px solid var(--ink);outline-offset:3px}
@keyframes keys-in{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:no-preference){
html:not([data-reduce-motion="true"]) .keys:not([hidden]) .keys__box{
animation:keys-in .12s ease-out}
}
"""

SCRIPT = r"""
(function(){
  var svg = document.getElementById('schematic');
  var A = svg && svg.systemap;
  function reduced(){
    return document.documentElement.dataset.reduceMotion === 'true' ||
      !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  // ---- a new layer draws its lines in model order ----------------------
  // Each line draws from source to target in 300 ms. The next line starts
  // 60 ms later, or sooner, so that the layer is complete in 600 ms.
  if(A && A.drawLines){
    svg.addEventListener('systemap:layer', function(){
      // A sequence step has its own cue: the dot on the step flow.
      if(reduced() || A.state.journey || A.state.edge >= 0
        || document.body.dataset.mode === 'trace'){ return; }
      var list = Array.prototype.slice.call(svg.querySelectorAll('.flow'))
        .filter(function(p){
          return !p.classList.contains('off') && !p.classList.contains('fg-hide'); })
        .map(function(p){ return +p.dataset.edge; })
        .sort(function(a, b){ return a - b; });
      if(!list.length){ return; }
      var stagger = list.length > 1 ? Math.min(60, 300 / (list.length - 1)) : 0;
      A.drawLines(list, {each:300, stagger:stagger, labels:true});
    });
  }

  // ---- a shade under each card ------------------------------------------
  ['schematic', 'changemap'].forEach(function(id){
    var map = document.getElementById(id);
    if(!map){ return; }
    Array.prototype.slice.call(map.querySelectorAll('.node__box')).forEach(function(box){
      var shade = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      ['x', 'y', 'width', 'height', 'rx'].forEach(function(a){
        shade.setAttribute(a, box.getAttribute(a)); });
      shade.setAttribute('class', 'node__shade');
      shade.setAttribute('aria-hidden', 'true');
      box.parentNode.insertBefore(shade, box);
    });
  });

  // ---- the cards come in one time, in reading order ----------------------
  // At most 360 ms from the first card to the last. The class goes when the
  // last card is in, so a later layer change does not run it again.
  if(svg && !reduced()){
    var cards = Array.prototype.slice.call(svg.querySelectorAll('.node'));
    var step = cards.length > 1 ? Math.min(18, 360 / (cards.length - 1)) : 0;
    cards.forEach(function(n, k){ n.style.setProperty('--in', Math.round(k * step) + 'ms'); });
    svg.classList.add('cards-in');
    setTimeout(function(){ svg.classList.remove('cards-in'); }, 360 + 340);
  }

  // ---- a card under the pointer shows its lines --------------------------
  // After 120 ms on a card, with no selection and no sequence: its lines,
  // their labels and the cards at their other ends stay, the other lines
  // fade and the other cards go a little dim. Leaving the card ends it.
  // A drag of the map does not start it.
  if(svg && A){
    var hoverWait = 0, lit = [];
    function unlight(){
      clearTimeout(hoverWait);
      svg.classList.remove('card-peek');
      lit.forEach(function(n){ n.classList.remove('card-lit'); });
      lit = [];
    }
    function mark(n){ n.classList.add('card-lit'); lit.push(n); }
    function light(card){
      unlight();
      var ends = {};
      ends[card.dataset.id] = true;
      (A.detail[card.dataset.id].edges || []).forEach(function(i){
        Array.prototype.slice.call(svg.querySelectorAll('[data-edge="' + i + '"]'))
          .forEach(function(n){
            if(n.classList.contains('flow') && n.classList.contains('off')){ return; }
            if(n.classList.contains('flow')){ ends[A.edges[i].from] = ends[A.edges[i].to] = true; }
            mark(n);
          });
      });
      if(!lit.some(function(n){ return n.classList.contains('flow'); })){ return; }
      Array.prototype.slice.call(svg.querySelectorAll('.node')).forEach(function(n){
        if(ends[n.dataset.id]){ mark(n); } });
      svg.classList.add('card-peek');
    }
    svg.addEventListener('pointerdown', unlight);
    svg.addEventListener('pointerover', function(e){
      var card = e.target && e.target.closest ? e.target.closest('.node') : null;
      if(!card || !A.detail[card.dataset.id] || A.state.focus || A.state.journey
        || A.state.edge >= 0 || svg.classList.contains('panning')){ return; }
      clearTimeout(hoverWait);
      hoverWait = setTimeout(function(){ light(card); }, 120);
    });
    svg.addEventListener('pointerout', function(e){
      var card = e.target && e.target.closest ? e.target.closest('.node') : null;
      if(card && !(e.relatedTarget && card.contains(e.relatedTarget))){ unlight(); }
    });
    ['systemap:select', 'systemap:layer', 'systemap:step', 'systemap:mode'].forEach(
      function(name){ svg.addEventListener(name, unlight); });
  }

  // ---- a theme change fades the colors in 240 ms -------------------------
  if(svg){
    var fade = 0;
    svg.addEventListener('systemap:scheme', function(){
      if(reduced()){ return; }
      var root = document.documentElement;
      root.classList.add('scheme-fade');
      clearTimeout(fade);
      fade = setTimeout(function(){ root.classList.remove('scheme-fade'); }, 280);
    });
  }

  // ---- the keyboard sheet: ? opens it, Escape closes it ----------------
  var sheet = document.getElementById('keys');
  if(!sheet){ return; }
  var closer = sheet.querySelector('[data-keys-close]'), opener = null;
  var layerKey = sheet.querySelector('[data-keys-layers]');
  var count = document.querySelectorAll('[data-layer-btn]').length;
  if(layerKey && count > 1){ layerKey.textContent = '1 to ' + Math.min(count, 9); }
  function open(from){
    if(!sheet.hidden){ return; }
    opener = from || document.activeElement;
    var menu = opener && opener.closest ? opener.closest('details') : null;
    if(menu){ menu.open = false; opener = menu.querySelector('summary') || opener; }
    sheet.hidden = false;
    if(closer){ closer.focus(); }
  }
  function close(){
    if(sheet.hidden){ return; }
    sheet.hidden = true;
    var back = opener;
    opener = null;
    if(back && back !== document.body && back.focus && back.isConnected !== false){ back.focus(); }
    else if(document.activeElement && sheet.contains(document.activeElement)){
      document.activeElement.blur();
    }
  }
  function typing(t){
    return !!(t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName || '')));
  }
  window.addEventListener('keydown', function(e){
    if(!sheet.hidden){
      // The sheet is modal: page keys do not work under it.
      if(e.key === 'Escape'){ e.preventDefault(); close(); }
      else if(e.key === 'Tab'){ e.preventDefault(); if(closer){ closer.focus(); } }
      e.stopImmediatePropagation();
      return;
    }
    if(e.key === '?' && !e.ctrlKey && !e.metaKey && !e.altKey && !typing(e.target)){
      e.preventDefault(); e.stopImmediatePropagation(); open();
    }
  }, true);
  if(closer){ closer.addEventListener('click', close); }
  sheet.addEventListener('click', function(e){ if(e.target === sheet){ close(); } });
  var button = document.getElementById('keys-open');
  if(button){ button.addEventListener('click', function(){ open(button); }); }
})();
"""

_KEYS: tuple[tuple[str, str], ...] = (
    ("/", "Find a component"),
    ("1 to 6", "Select a layer"),
    ("← →", "Previous or next step"),
    ("W", "Whole route"),
    ("F", "Full screen"),
    ("B", "Hold to show the base"),
    ("R", "Read: open the panel"),
    ("T", "Text view"),
    ("Esc", "Previous view"),
)


def _key(key: str) -> str:
    if key == "← →":
        return (
            '<kbd><span aria-hidden="true">← →</span>'
            '<span class="sr-only">Left arrow and right arrow</span></kbd>'
        )
    if key == "1 to 6":
        return f"<kbd data-keys-layers>{key}</kbd>"
    return f"<kbd>{key}</kbd>"


def keys_sheet() -> str:
    """Give the keyboard sheet. The page shows it for the ? key.

    The sheet is a modal dialog. The ? key and the Keyboard keys menu item
    open it. Escape and its Close button close it and return the focus."""
    rows = "".join(f"<dt>{_key(key)}</dt><dd>{text}</dd>" for key, text in _KEYS)
    return (
        '<div class="keys" id="keys" hidden>'
        '<div class="keys__box" role="dialog" aria-modal="true" aria-labelledby="keys-title">'
        '<div class="keys__head"><h2 class="keys__title" id="keys-title">Keyboard keys</h2>'
        '<button type="button" class="keys__close" data-keys-close>Close</button></div>'
        '<p class="keys__note">Press ? to open this list.</p>'
        f'<dl class="keys__list">{rows}</dl>'
        "</div></div>"
    )
