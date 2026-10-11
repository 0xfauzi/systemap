"""Motion and small controls for the map page: the mark, the keyboard sheet and layer changes.

Each motion runs one time and shows direction or order. With reduced motion,
the page shows the final state at once."""

CSS = r"""
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
