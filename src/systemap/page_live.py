"""The page script of `systemap live`: it loads the page again for each new version.

Only `systemap live` adds this script. The page that `systemap render` writes does not
change. Before the load, the script keeps the view of the reader in the session
storage of the browser: the view, the layer, the selected component or flow, the
sequence and its step, and the camera of the map and of the change map. After the load,
the script puts the view back. A component, a flow or a sequence that the new page does
not have stays clear.

The script reads the events of the server at `/events`. It loads the page again only
for a `rendered` event with a version number that is more than the number of the page.
If the connection breaks, the script closes it and does nothing more. If the command
cannot render a version, the script shows a notice with the first line of the error.
"""

from __future__ import annotations

import html
import json

from systemap import page_csp

# The session storage key of the saved view.
VIEW_KEY = "systemap-live-view"
NOTICE_ID = "live-notice"

SCRIPT = r"""
(function(){
  if(window.parent !== window || !window.EventSource){ return; }
  var svg = document.getElementById('schematic');
  var A = svg && svg.systemap, P = svg && svg.page;
  var C = document.getElementById('changemap'), M = C && C.systemap;
  var MODES = ['understand', 'trace', 'change'];
  function edgeKey(map, i){
    var e = map.edges[i];
    return e ? {from:e.from, to:e.to, art:e.art, id:e.id} : null;
  }
  function edgeAt(map, key){
    if(!key){ return -1; }
    for(var i = 0; i < map.edges.length; i++){
      var e = map.edges[i];
      if(e.from === key.from && e.to === key.to && e.art === key.art
        && (!key.id || e.id === key.id)){ return i; }
    }
    return -1;
  }
  function has(table, key){ return Object.prototype.hasOwnProperty.call(table, key); }
  function camera(map){ return map.view.isFit() ? null : map.view.snapshot(); }
  function journeyAt(id){
    for(var k = 0; k < A.journeys.length; k++){ if(A.journeys[k].id === id){ return k; } }
    return -1;
  }
  function viewOf(){
    var at = P.journey.state(), j = A.journeys[at.j];
    return {path:location.pathname, mode:P.mode(), layer:A.state.layer, focus:A.state.focus,
      edge:edgeKey(A, A.state.edge), camera:camera(A),
      journey:j ? {id:j.id, s:at.s, view:at.view} : null,
      change:M ? {focus:M.state.focus, edge:edgeKey(M, M.state.edge), camera:camera(M)} : null};
  }
  function save(){
    if(!A || !P){ return; }
    try { sessionStorage.setItem(KEY, JSON.stringify(viewOf())); } catch(e){}
  }
  function saved(){
    var raw = null;
    try { raw = sessionStorage.getItem(KEY); sessionStorage.removeItem(KEY); }
    catch(e){ return null; }
    try { return JSON.parse(raw); } catch(e){ return null; }
  }
  function putMode(v){
    var k = v.journey ? journeyAt(v.journey.id) : -1;
    if(v.mode === 'trace' && k >= 0){
      P.journey.route(k);
      if(v.journey.view === 'steps'){ P.sequence.go('steps', v.journey.s, 'keep'); }
    } else if(MODES.indexOf(v.mode) >= 0 && v.mode !== P.mode()){ P.setMode(v.mode); }
  }
  function putFocus(map, focus, edge){
    // A saved flow that the new page does not have gives no selection, not its component.
    var i = edgeAt(map, edge);
    var known = !!focus && focus !== '_meta' && has(map.detail, focus);
    if(known && (!edge || i >= 0)){ map.select(focus, i); }
    else if(map.state.focus){ map.clear(); }
  }
  function putCamera(map, view){
    if(view){ map.view.restore(view, true); } else if(!map.view.isFit()){ map.view.fit(true); }
  }
  function restore(){
    var v = saved();
    if(!v || v.path !== location.pathname || !A || !P){ return; }
    // A saved sequence that the new page does not have gives the Map view with no selection.
    // The Sequences view always shows a sequence, so it cannot open without a selection.
    var gone = v.mode === 'trace' && !!v.journey && journeyAt(v.journey.id) < 0;
    P.restoring(true);
    try {
      if(v.layer === 'all' || has(A.detail._meta.readings, v.layer)){ P.setLayer(v.layer); }
      if(!gone){ putMode(v); }
      putFocus(A, gone ? '' : v.focus, gone ? null : v.edge);
      if(M && v.change){ putFocus(M, v.change.focus, v.change.edge); }
    } finally { P.restoring(false); }
    // The page frames a selection in the next frame. The camera comes after that framing.
    window.requestAnimationFrame(function(){
      P.restoring(true);
      try {
        putCamera(A, v.camera);
        if(M && v.change){ putCamera(M, v.change.camera); }
      } finally { P.restoring(false); }
    });
  }
  function notice(text){
    var n = document.getElementById(NOTICE);
    if(!n){
      n = document.createElement('div');
      n.id = NOTICE;
      n.setAttribute('role', 'status');
      n.setAttribute('style', 'position:fixed;left:16px;bottom:16px;z-index:60;'
        + 'max-width:min(560px,calc(100vw - 32px));padding:8px 12px;border-radius:6px;'
        + 'border:1px solid var(--line-2,#888);background:var(--raised,#fff);'
        + 'color:var(--ink,#111);font:13px/1.4 var(--fs,sans-serif)');
      document.body.appendChild(n);
    }
    n.textContent = 'The map is not updated: ' + String(text).split('\n')[0];
  }
  restore();
  var source = new EventSource('/events');
  source.addEventListener('rendered', function(e){
    var d = {};
    try { d = JSON.parse(e.data); } catch(_x){}
    if(d.version > VERSION){ save(); source.close(); location.reload(); }
  });
  // A version that the command cannot render gives a server event with the name error.
  // A broken connection gives an error event without data: the command stopped, so the
  // script stops too.
  source.addEventListener('error', function(e){
    if(typeof e.data !== 'string'){ source.close(); return; }
    var d = {};
    try { d = JSON.parse(e.data); } catch(_x){}
    if(d.text){ notice(d.text); }
  });
})();
"""


def _body(version: int) -> str:
    head = (
        f"var VERSION = {int(version)}, KEY = {json.dumps(VIEW_KEY)}, "
        f"NOTICE = {json.dumps(NOTICE_ID)};"
    )
    body = SCRIPT.replace("(function(){\n", "(function(){\n" + head + "\n", 1)
    return body.replace("</", "<\\/")


def script(version: int) -> str:
    """Give the script element for a page of the version number `version`."""
    return "<script>" + _body(version) + "</script>"


def with_script(page: str, version: int) -> str:
    """Put the script before the end of the body of a page.

    If the page has a Content-Security-Policy, the policy also permits this script and
    its connection to the server (`page_csp.with_live_script`)."""
    end = page.rfind("</body>")
    added = page + script(version) if end < 0 else page[:end] + script(version) + page[end:]
    return page_csp.with_live_script(added, _body(version))


def notice_page(title: str, lines: list[str]) -> str:
    """Give a small page with a title and text lines. The caller adds the script."""
    text = "".join(f"<p>{html.escape(line)}</p>" for line in lines)
    return page_csp.with_policy(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(title)}</title><style>:root{{color-scheme:light dark}}"
        "body{font:15px/1.5 system-ui,sans-serif;margin:40px auto;max-width:640px;"
        "padding:0 16px}p{white-space:pre-wrap}</style></head>"
        f"<body><h1>{html.escape(title)}</h1>{text}</body></html>\n"
    )


def waiting_page() -> str:
    """Give the page before the command has rendered the first version."""
    return notice_page(
        "systemap live map",
        [
            "systemap renders the map of the working tree. When the map is complete, "
            "this page shows it."
        ],
    )


def error_page(text: str) -> str:
    """Give the page if the command cannot render the first version."""
    return notice_page(
        "systemap live map",
        [
            "systemap could not render the map of the working tree.",
            text,
            "Correct the error. When systemap renders the map, this page shows it.",
        ],
    )
