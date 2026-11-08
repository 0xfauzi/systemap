"""The reader tools and the Details panel of the canvas page (step 5 of
docs/design/nested-canvas.md).

The canvas page gets the tools of the linked page (`page._tools`), so that it does not
lose information when it becomes the default page:

- Theme. The header shows the button of the scheme that is not in use. A click sets
  `data-theme` and keeps the scheme in this browser with the key of the linked page
  (`page.SCHEME_KEY`). The renderer reads the theme colors again only when `data-theme`
  changes (rule 4 of "Performance").
- Reduce motion. The button sets `data-reduce-motion` and keeps the setting with the key
  of the linked page (`page.MOTION_KEY`). Then each camera move and each fade occurs at one
  time (`reduced`). The system setting for reduced motion also applies.
- Keyboard keys. The ? key and the button open a sheet with the keys of the canvas page
  only (`KEYS`). The sheet is a modal dialog. Escape and its Close button close it.
- Source of this map. The button gives the commit of the facts (7 characters), or "commit
  not recorded". It opens the source records of the page: the unknown source information,
  the commit, the facts file and the model file (`canvas_header`).
- Details. The D key and the button open and close the Details panel. The panel gives the
  selected card: its kind and text, the map that it opens, the flows in and out with their
  evidence state and assurance, the sequences, the invariants and the import rules with
  their assurance, and the source records (`canvas_details`). A flow of the lists gives
  the flow. Without a selection, the panel gives the rules of the current map.

The panel is over the canvas. It does not change the bands of the fit. Thus the fit of a
map is the same with the panel open or closed. The panel fades in and out in 160 ms, and
at one time with reduced motion. Its text changes only at a change of the selection, of
the flow in the panel, or of the current map without a selection (`detSync`). Thus a
frame with no such change makes no DOM change, and the panel adds no work to a frame.

On a narrow screen, the tools of the header go into one Tools menu (`data-menu` in
`headMeasure`). On a touch screen, each target of the tools, of the menu and of the panel
is 44 x 44 px or more.
"""

from __future__ import annotations

import json

from systemap import page, page_motion
from systemap.evidence import READER_TEXT

# The keys of the canvas page. The F key fits the current map: the canvas page has no full
# screen.
KEYS: tuple[tuple[str, str], ...] = (
    ("<kbd data-mod-key>Ctrl K</kbd> <kbd>/</kbd>", "Find a component, flow, layer or action"),
    ("<kbd>Tab</kbd>", "Move the keyboard focus through the cards of the current map"),
    ("<kbd>Enter</kbd>", "Go into the card, or select it"),
    ("<kbd>Esc</kbd>", "Go out one level, or close"),
    (
        '<kbd><span aria-hidden="true">← ↑ → ↓</span><span class="sr-only">Arrow keys</span></kbd>',
        "Move the map",
    ),
    ("<kbd>+</kbd> <kbd>-</kbd>", "Zoom in or out"),
    ("<kbd>F</kbd>", "Fit the current map"),
    ("<kbd>D</kbd>", "Open or close the Details panel"),
    ("<kbd>?</kbd>", "Keyboard keys"),
)

KEYS_HTML = (
    '<div class="keys" id="keys" hidden>'
    '<div class="keys__box" role="dialog" aria-modal="true" aria-labelledby="keys-title">'
    '<div class="keys__head"><h2 class="keys__title" id="keys-title">Keyboard keys</h2>'
    '<button type="button" class="keys__close" data-keys-close>Close</button></div>'
    '<p class="keys__note">Press ? to open this list.</p>'
    '<dl class="keys__list">'
    + "".join(f"<dt>{key}</dt><dd>{text}</dd>" for key, text in KEYS)
    + "</dl></div></div>"
)

PANEL_HTML = (
    '<aside class="cdet cpop cview" id="cdetails" aria-labelledby="cdet-title" data-own-keys hidden>'
    '<div class="cdet__head"><h2 id="cdet-title" tabindex="-1">Details</h2>'
    '<button type="button" id="cdet-close">Close</button></div>'
    '<div id="cdet-body"></div></aside>'
)

HTML = PANEL_HTML + KEYS_HTML

# The tools of the header (`canvas_header`), the source records, the Tools menu on a narrow
# screen, the keyboard sheet of the linked page (`page_motion.KEYS_CSS`) and the panel.
CSS = (
    page_motion.KEYS_CSS
    + """
.cbar__tools{display:flex;flex:none;align-items:center;gap:2px}
.cbar__tools .cbar__snap{padding:0 8px;font:12px/1 var(--fm);white-space:nowrap}
.cbar__snap code{font:inherit;color:var(--ink)}
.cbar [data-scheme][aria-pressed="true"],.cbar .cbar__more,.cbar[data-menu] .cbar__tools{
display:none}
.cbar__tools .cbar__det{margin-left:6px}
.cbar[data-menu] .cbar__more{display:flex;align-items:center;justify-content:center;flex:none}
.cbar[data-menu] .cbar__views button{padding:0 6px}
.cbar[data-menu] .cbar__pick select{min-width:64px}
.cpop,.cbar[data-menu] .cbar__tools[data-open]{position:fixed;top:56px;right:8px;
box-sizing:border-box;border:1px solid var(--line-2);border-radius:10px;
background:var(--surface);color:var(--ink-2);font:13px/19px var(--fs);
box-shadow:0 16px 48px rgba(0,0,0,.28)}
.cbar[data-menu] .cbar__tools[data-open]{display:flex;flex-direction:column;
align-items:stretch;gap:4px;padding:8px}
.cbar[data-menu] .cbar__tools button{display:flex;align-items:center;gap:8px;margin:0;
padding:0 12px}
.cbar[data-menu] .cbar__tools button[aria-label]::after{content:attr(aria-label)}
.cbar[data-menu] .cbar__tools [data-scheme][aria-pressed="true"]{display:none}
.csnap__pop{z-index:6;width:min(400px,calc(100% - 16px));max-height:calc(100% - 72px);
overflow:auto;padding:12px 16px}
.csnap__pop[hidden]{display:none}
.cpop code{font:12px/18px var(--fm);color:var(--ink);overflow-wrap:anywhere}
.csnap__k,.cdet h4{margin:14px 0 4px;font:600 11px/16px var(--fs);letter-spacing:.06em;
color:var(--ink-3)}
.csnap__k{margin-top:0}
.cdet{z-index:3;bottom:8px;width:min(380px,calc(100% - 16px));overflow:auto;padding:0 16px 16px}
.cdet__head{position:sticky;top:0;display:flex;align-items:center;justify-content:space-between;
margin:0 -16px;padding:8px 16px;background:var(--surface)}
.cdet h2,.cdet h3{margin:0;font:600 15px/20px var(--fs);color:var(--ink);outline:none}
.cdet h3{margin-top:4px;overflow-wrap:anywhere}
.cdet p{margin:4px 0}
.cdet ul{margin:0;padding:0;list-style:none}
.cdet b{color:var(--ink);font-weight:600}
.cdet button{box-sizing:border-box;min-height:28px;margin:2px 0;padding:2px 8px;
border:1px solid var(--line-2);border-radius:6px;background:none;color:var(--ink);font:inherit;
text-align:left;cursor:pointer}
.cdet li button{display:block;width:100%}
.cdet button:hover{background:var(--raised)}
.cpop :focus-visible{outline:2px solid var(--ink);outline-offset:1px}
.cpop summary{min-height:28px;padding:4px 0;color:var(--ink);cursor:pointer}
.cdet details details{margin-left:12px}
.cdet__as{color:var(--ink-3)}
@media (max-width:600px){.cdet{top:auto;left:8px;width:auto;max-height:55%}}
@media (pointer:coarse){.cpop,.cbar[data-menu] .cbar__tools[data-open]{top:64px}
.cdet button,.cpop summary,.keys .keys__close{min-width:44px;min-height:44px;height:auto}}
@media (pointer:coarse) and (max-width:600px){.cdet{top:auto}}
"""
)

# The words for each evidence state of a flow (`evidence.READER_TEXT`).
_EVIDENCE = json.dumps(READER_TEXT, sort_keys=True)

DETAILS = r"""
// ---- the reader tools (page_canvas_details) -----------------------------------------
(function () {
  function byId(id) { return document.getElementById(id); }
  function all(sel) { return Array.prototype.slice.call(document.querySelectorAll(sel)); }
  var root = document.documentElement, tools = byId('canvas-tools'), more = byId('tools-open');
  function typing(t) { return !!(t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName || ''))); }
  // ---- the theme: the button of the other scheme shows ----------------------------
  function showScheme() {
    var s = root.getAttribute('data-theme');
    all('[data-scheme]').forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-scheme') === s ? 'true' : 'false'); });
  }
  all('[data-scheme]').forEach(function (b) {
    b.addEventListener('click', function () {
      var had = document.activeElement === b, name = b.getAttribute('data-scheme');
      root.setAttribute('data-theme', name);
      try { localStorage.setItem(SCHEME_KEY, name); } catch (e) { /* no storage */ }
      showScheme();
      var other = all('[data-scheme]').filter(function (x) { return x !== b; })[0];
      if (had && other) other.focus();
      say('Theme: ' + (b.getAttribute('aria-label') || name) + '.');
    });
  });
  showScheme();
  // ---- Reduce motion ---------------------------------------------------------------
  var motion = byId('reduce-motion');
  function showMotion() { if (motion) motion.setAttribute('aria-pressed', String(root.getAttribute('data-reduce-motion') === 'true')); }
  if (motion) motion.addEventListener('click', function () {
    var off = root.getAttribute('data-reduce-motion') !== 'true';
    root.setAttribute('data-reduce-motion', String(off));
    try { localStorage.setItem(MOTION_KEY, String(off)); } catch (e) { /* no storage */ }
    showMotion(); request();
    say('Reduce motion: ' + (off ? 'on' : 'off') + '.');
  });
  showMotion();
  // ---- a popup of the header: the source records and the Tools menu ------------------
  // Escape and a click out of the popup close it.
  function popup(button, box, open, close) {
    if (!button || !box) return;
    button.addEventListener('click', function () { if (button.getAttribute('aria-expanded') === 'true') close(); else open(); });
    box.addEventListener('keydown', function (e) { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(); button.focus(); } });
    button.addEventListener('keydown', function (e) { if (e.key === 'Escape' && button.getAttribute('aria-expanded') === 'true') { e.preventDefault(); e.stopPropagation(); close(); } });
    document.addEventListener('pointerdown', function (e) {
      if (button.getAttribute('aria-expanded') === 'true' && !box.contains(e.target) && !button.contains(e.target)) close();
    });
  }
  var snap = byId('snap'), pop = byId('snap-pop');
  function snapShow(on) { if (snap && pop) { pop.hidden = !on; snap.setAttribute('aria-expanded', String(on)); } }
  popup(snap, pop, function () { snapShow(true); }, function () { snapShow(false); });
  function menuShow(on) {
    if (!tools || !more) return;
    if (on) tools.setAttribute('data-open', ''); else { tools.removeAttribute('data-open'); snapShow(false); }
    more.setAttribute('aria-expanded', String(on));
  }
  popup(more, tools, function () { menuShow(true); var b = tools.querySelector('button:not([aria-pressed="true"][data-scheme])'); if (b) b.focus(); }, function () { menuShow(false); });
  // ---- the keyboard sheet: ? opens it, Escape closes it ----------------------------
  var sheet = byId('keys'), closer = sheet && sheet.querySelector('[data-keys-close]'), opener = null;
  function modal() { var p = byId('palette'); return !!(p && !p.hidden) || !!(sheet && !sheet.hidden); }
  function keysOpen(from) {
    if (!sheet || modal()) return;
    menuShow(false);
    opener = from || document.activeElement;
    sheet.hidden = false;
    if (closer) closer.focus();
  }
  function keysClose() {
    if (!sheet || sheet.hidden) return;
    sheet.hidden = true;
    var back = opener; opener = null;
    if (back && back.focus && back.isConnected !== false && !back.closest('[hidden]')) back.focus(); else if (more && more.offsetParent) more.focus(); else cv.focus();
  }
  if (sheet) {
    if (closer) closer.addEventListener('click', keysClose);
    sheet.addEventListener('click', function (e) { if (e.target === sheet) keysClose(); });
  }
  var keysBtn = byId('keys-open');
  if (keysBtn) keysBtn.addEventListener('click', function () { keysOpen(more && more.offsetParent ? more : keysBtn); });
  // The sheet is modal: the keys of the page do not operate under it.
  window.addEventListener('keydown', function (e) {
    if (sheet && !sheet.hidden) {
      if (e.key === 'Escape') { e.preventDefault(); keysClose(); }
      else if (e.key === 'Tab') { e.preventDefault(); if (closer) closer.focus(); }
      e.stopImmediatePropagation();
      return;
    }
    if (e.ctrlKey || e.metaKey || e.altKey || typing(e.target) || modal()) return;
    if (e.key === '?') { e.preventDefault(); e.stopImmediatePropagation(); keysOpen(); }
    else if (e.key === 'd' || e.key === 'D') { e.preventDefault(); e.stopImmediatePropagation(); detToggle(); }
  }, true);
  // ---- the Details panel -----------------------------------------------------------
  var panel = byId('cdetails'), body = byId('cdet-body'), title = byId('cdet-title'), toggle = byId('details-toggle');
  var ON = false, SHOWN = null, FLOW = null, BACK = null, EV = EVIDENCE_JSON, FF = DATA.maps[0].ff || 'the facts file';
  function list(xs) { return xs.length ? xs.map(function (x) { return '<code>' + esc(x) + '<\/code>'; }).join(', ') : 'none recorded'; }
  function level(o) { return o.as ? ' <span class="cdet__as">' + esc(o.as[0] + ' · ' + o.as[1]) + '<\/span>' : ''; }
  // The steps of the sequences of map m that `has` takes, as one line for each sequence.
  function steps(m, has) {
    var out = [];
    (m.sq || []).forEach(function (q) {
      var at = [];
      q.s.forEach(function (s, k) { if (has(s, m.flows[s.f])) at.push(k + 1); });
      if (at.length) out.push('<li>' + esc(q.n) + ': ' + (at.length === 1 ? 'step ' : 'steps ') + at.join(', ') + '.<\/li>');
    });
    return '<h4>SEQUENCES<\/h4>' + (out.length ? '<ul>' + out.join('') + '<\/ul>' : '<p>No sequence of this map has this item.<\/p>');
  }
  function rules(m, c) {
    var h = '';
    (m.iv || []).forEach(function (r) {
      if (!c || (r.g || []).indexOf(c.id) >= 0) h += '<li><b>' + r.n + '<\/b> ' + esc(r.t) + level(r) + '<\/li>';
    });
    (m.ir || []).forEach(function (r) {
      var s = r.s || [], t = r.t || [];
      if (!c || !s.length || s.indexOf(c.id) >= 0 || t.indexOf(c.id) >= 0) h += '<li>Import rule <code>' + esc(r.id) + '<\/code> ' + esc(r.k) + level(r) + '<\/li>';
    });
    return '<h4>RULES<\/h4>' + (h ? '<p>Each rule gives its assurance level and its freshness.<\/p><ul>' + h + '<\/ul>' : '<p>The model has no rules for ' + (c ? 'this card' : 'this map') + '.<\/p>');
  }
  function flowRow(f, other) {
    return '<li><button type="button" data-f="' + f.i + '">' + esc(f.a) + ' ' + other + '<\/button> <span class="cdet__as">' + esc(EV[f.ev] || f.ev) + '<\/span><\/li>';
  }
  function flows(name, fs, word, end) {
    return '<h4>' + name + ' (' + fs.length + ')<\/h4>' + (fs.length ? '<ul>' + fs.map(function (f) { return flowRow(f, word + ' ' + esc(f[end])); }).join('') + '<\/ul>' : '<p>None.<\/p>');
  }
  function fileOf(m, x) { return 'f' in x ? x.f : m.fr ? m.fr[0] + x.i.replace(/\./g, '/') + m.fr[1] : ''; }
  function nameOf(m, x) { return typeof x === 'number' ? m.md[x].i : x; }
  // The importers of module j: the modules of the table that import it, and `ib`.
  function importers(m, j) {
    var x = m.md[j], out = [];
    if (!x.ia) m.md.forEach(function (o, k) { if ((o.im || []).indexOf(j) >= 0) out.push(k); });
    return out.concat(x.ib || []).map(function (y) { return nameOf(m, y); });
  }
  function module(m, j) {
    var x = m.md[j], file = fileOf(m, x);
    return '<details><summary>' + esc(x.i) + '<\/summary><p>' + (file ? '<code>' + esc(file) + '<\/code>' : 'Source path not recorded') + '<\/p>'
      + '<p>Public names in this module: ' + (x.n ? x.n[0] : 0) + '. Tests with imports of this module: ' + (x.n ? x.n[1] : 0) + '.<\/p>'
      + '<p>Imports: ' + list((x.im || []).map(function (y) { return nameOf(m, y); })) + '.<\/p>'
      + '<p>Imported by: ' + list(importers(m, j)) + '.<\/p>'
      + '<p>External imports: ' + list(x.ex || []) + '.<\/p>'
      + (x.uk || []).map(function (u) { return '<p>Unknown fact: ' + esc(u) + '<\/p>'; }).join('') + '<\/details>';
  }
  function sources(m, c) {
    var r = (m.sr || {})[c.id] || {};
    return '<h4>SOURCE EVIDENCE<\/h4>'
      + (c.u || []).map(function (u) { return '<p>The source data has no source for this module claim: <code>' + esc(u) + '<\/code>.<\/p>'; }).join('')
      + '<details><summary>Source records<\/summary><p>Module claims in the model: ' + list(c.m || []) + '.<\/p>'
      + (r.sc || []).map(function (s) { return '<p>Public name in the model: <code>' + esc(s) + '<\/code>.<\/p>'; }).join('')
      + ((r.mo || []).map(function (j) { return module(m, j); }).join('') || '<p>The source data has no modules for this component card.<\/p>')
      + '<p>The facts file <code>' + esc(FF) + '<\/code> gives the module descriptions, the public names and the tests. References do not prove coverage.<\/p>'
      + '<p><b>Entry points.<\/b> An entry point is where a program can start.<\/p>'
      + ((r.pt || []).map(function (p) { return '<p><code>' + esc(p) + '<\/code><\/p>'; }).join('') || '<p>No entry points were extracted for these modules.<\/p>')
      + '<\/details>';
  }
  function cardHtml(c) {
    var m = c.map;
    return '<h3 tabindex="-1">' + esc(c.id) + '<\/h3><p>' + (c.k === 'actor' ? 'Actor' : 'Component') + '. Map: ' + esc(mapName(m)) + '.<\/p>'
      + (c.p ? '<p>' + esc(c.p) + '<\/p>' : '') + (c.d ? '<p>' + esc(c.d) + '<\/p>' : '')
      + (c.as ? '<p>Assurance level: ' + esc(c.as[0]) + '. Freshness: ' + esc(c.as[1]) + '.<\/p>' : '')
      + (c.child ? '<p><button type="button" data-go>Go into the map: ' + esc(sizeText(c.child)) + '<\/button><\/p>' : '')
      + flows('FLOWS IN', c.ins, 'from', 's') + flows('FLOWS OUT', c.outs, 'to', 't')
      + steps(m, function (s, f) { return (f && (f.s === c.id || f.t === c.id)) || (s.a || []).indexOf(c.id) >= 0 || (s.me || []).indexOf(c.id) >= 0; })
      + rules(m, c) + (c.k === 'actor' ? '' : sources(m, c));
  }
  function flowHtml(f) {
    var m = f.map;
    return '<h3 tabindex="-1">Flow: ' + esc(f.a) + '<\/h3><p>From <b>' + esc(f.s) + '<\/b> to <b>' + esc(f.t) + '<\/b>. Kind: ' + esc(f.k)
      + '. Layer: ' + esc(layerName(f.l)) + '.<\/p><p>Evidence: ' + esc(EV[f.ev] || f.ev) + '.<\/p>'
      + (f.as ? '<p>Assurance level: ' + esc(f.as[0]) + '. Freshness: ' + esc(f.as[1]) + '.<\/p>' : '')
      + steps(m, function (s) { return s.f === f.i; })
      + '<p><button type="button" data-show>Show the flow on the map<\/button><\/p>'
      + (BACK ? '<p><button type="button" data-back>Back to the card ' + esc(BACK.id) + '<\/button><\/p>' : '');
  }
  function mapHtml(m) {
    return '<h3 tabindex="-1">Map: ' + esc(mapName(m)) + '<\/h3><p>' + esc(sizeText(m)) + '.<\/p>'
      + '<p>Select a card to see its modules, its flows, its sequences and its rules.<\/p>' + rules(m, null);
  }
  // Write the panel when its subject changes: the flow of the panel, the selected card, or
  // the current map. An open panel with the same subject makes no DOM change.
  function detSync(focus) {
    if (!ON) return;
    var m = currentMap(), key = FLOW ? 'f' + FLOW.map.oi + ':' + FLOW.i : SEL_C ? 'c' + SEL_C.map.oi + ':' + SEL_C.i : 'm' + m.oi;
    if (key === SHOWN) return;
    SHOWN = key;
    body.innerHTML = FLOW ? flowHtml(FLOW) : SEL_C ? cardHtml(SEL_C) : mapHtml(m);
    if (focus) { var h = body.querySelector('h3'); if (h) h.focus({preventScroll: true}); }
  }
  function detShow(on, focus) {
    if (!panel || on === ON) return;
    ON = on; SHOWN = null;
    if (toggle) toggle.setAttribute('aria-pressed', String(on));
    clearTimeout(panel._dt);
    if (on) {
      FLOW = null; detSync();
      panel.hidden = false; panel.getBoundingClientRect(); panel.classList.add('on');
      if (focus) title.focus({preventScroll: true});
      return;
    }
    panel.classList.remove('on');
    if (reduced()) panel.hidden = true;
    else panel._dt = setTimeout(function () { if (!ON) panel.hidden = true; }, VIEW_MS + 10);
    if (focus && toggle) (toggle.offsetParent ? toggle : more && more.offsetParent ? more : cv).focus();
  }
  function detToggle() { menuShow(false); detShow(!ON, true); say('Details: ' + (ON ? 'open' : 'closed') + '.'); }
  if (toggle) toggle.addEventListener('click', detToggle);
  if (panel) {
    byId('cdet-close').addEventListener('click', function () { detShow(false, true); });
    panel.addEventListener('keydown', function (e) { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); detShow(false, true); } });
    body.addEventListener('click', function (e) {
      var b = e.target.closest ? e.target.closest('button') : null, c = SEL_C;
      if (!b) return;
      if (b.hasAttribute('data-f') && c) { BACK = c; FLOW = c.map.flows[+b.getAttribute('data-f')]; detSync(true); }
      else if (b.hasAttribute('data-back')) { FLOW = null; detSync(true); }
      else if (b.hasAttribute('data-show') && FLOW) flyGoal(goalOf(FLOW.map, null, FLOW));
      else if (b.hasAttribute('data-go') && c && c.child) flyGoal(goalOf(c.map, c, null));
    });
  }
  // A new selection shows its card, and a different current map shows that map.
  SEL_HOOKS.push(function () { FLOW = null; BACK = null; detSync(); });
  HERE_HOOKS.push(function () { if (!SEL_C && !FLOW) detSync(); });
})();
"""

# The page gets the part without the comment lines and the indentation. The part has no
# template literal, so no string continues on a second line.
DETAILS = "\n".join(
    line.strip()
    for line in DETAILS.split("\n")
    if line.strip() and not line.strip().startswith("//")
)
DETAILS = (
    DETAILS.replace("SCHEME_KEY", json.dumps(page.SCHEME_KEY))
    .replace("MOTION_KEY", json.dumps(page.MOTION_KEY))
    .replace("EVIDENCE_JSON", _EVIDENCE)
)
