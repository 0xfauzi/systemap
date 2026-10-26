"""Viewport controls and flow selection for map pages and figures."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from systemap.schematic_labels import LABEL_JS
from systemap.schematic_relations import RELATION_JS
from systemap.theme import Palette

# JSON keeps these characters in a string without an escape. Python
# str.splitlines and some JavaScript parsers read them as the end of a line.
_LINE_ENDS = {"\u2028": "\\u2028", "\u2029": "\\u2029", "\u0085": "\\u0085"}


def line_safe(text: str) -> str:
    """Escape U+2028, U+2029 and U+0085 in JSON text or in JavaScript string text.

    The escape gives the same character to `JSON.parse` and to the script. Thus each
    line of the script stays one line. If a page compacts the script by lines, the
    script stays correct."""
    for char, escape in _LINE_ENDS.items():
        text = text.replace(char, escape)
    return text


def interactive_script(
    t: dict[str, Any], svg_id: str, panel_id: str, detail_json: str, variables: bool = False
) -> str:
    """Make the script for map selection and viewport controls.

    Selection shows the connected cards in the selected layer. Only a selected
    flow or a preview has a thicker line. The inspector lists the flows that a
    component receives and sends. The viewport
    controls zoom and movement. Selection and sequence steps frame the
    selected components in the visible area. `view.frameFocus(cover)`
    uses the area outside the inspector. A double-click on a region label
    frames that region.

    The map page and document figures use this same script. The page adds
    layer and sequence controls through `svg.systemap`. The interface
    `svg.systemap.view` gives fit, 100%, step, back and framing data.

    The script contains the detail JSON as a string for `JSON.parse`. In an
    object literal, the key `__proto__` sets the prototype. `JSON.parse` makes a
    property of the object. Escaping `</` prevents artifact
    text from closing the script. Escaping `<!--` prevents a change to the
    end of the script by artifact text. With `variables`, colors use CSS tokens
    instead of literal values. The page uses `variables`, so the inspector
    then gives sequence buttons and leaves room for the drawer Clear button.
    `line_safe` escapes the characters that can end a line of the script."""
    return (
        "<script>(function(){\n"
        f"var DETAIL = JSON.parse({_detail_text(detail_json)});\n"
        f"var PAL = {_palette(t, variables)};\n"
        f"var svg = document.getElementById({json.dumps(svg_id)});\n"
        f"var panel = document.getElementById({json.dumps(panel_id)});\n"
        f"var PAGE = {json.dumps(variables)};\n" + _INTERACTIVE_JS + "})();</script>"
    )


def page_maps_script(t: dict[str, Any], maps: Sequence[tuple[str, str, str]]) -> str:
    """Make one script for all maps of the map page.

    Each item of `maps` gives the SVG ID, the panel ID and the detail JSON of one map.
    The script contains the code of `interactive_script` one time, in a function. It
    calls this function one time for each map, in the sequence of `maps`. Thus a page
    with a change map does not contain two copies of the code. The colors use CSS
    tokens, as with `variables`.

    The detail of the first map is in the script one time. The detail of each other
    map is the detail of the first map with a set of changes (`_changes`). If the
    changes cannot give the same JSON, the script contains the full detail of that map.
    Each call parses its own copy, so no two maps share an object."""
    first = _audit_free(maps[0][2]) if maps else {}
    calls = [_call(first, svg_id, panel_id, detail) for svg_id, panel_id, detail in maps]
    changes = any(call.startswith("show(changed(") for call in calls)
    return (
        "<script>(function(){\n"
        f"var PAL = {_palette(t, True)};\n"
        "var PAGE = true;\n"
        f"var FIRST = {_js_text(first)};\n"
        + (_CHANGES_JS if changes else "")
        + "function show(DETAIL, svgId, panelId){\n"
        "var svg = document.getElementById(svgId);\n"
        "var panel = document.getElementById(panelId);\n"
        + _INTERACTIVE_JS
        + "}\n"
        + "".join(calls)
        + "})();</script>"
    )


# Puts the changes of one map into a parsed copy of the detail of the first map. A
# property definition, not an assignment, so that a key such as `__proto__` stays a
# record and does not set the prototype.
_CHANGES_JS = r"""
function changed(c){
  var d = JSON.parse(FIRST);
  function put(o, k, v){
    Object.defineProperty(o, k, {value:v, writable:true, enumerable:true, configurable:true});
  }
  Object.keys(c.records).forEach(function(k){
    var r = c.records[k];
    Object.keys(r).forEach(function(f){ put(d[k], f, r[f]); });
  });
  Object.keys(c.values).forEach(function(k){ put(d, k, c.values[k]); });
  return d;
}
"""


def _call(first: dict[str, Any], svg_id: str, panel_id: str, detail_json: str) -> str:
    """Give the call of `show` for one map: with the first detail, changes or full data."""
    ids = f"{json.dumps(svg_id)}, {json.dumps(panel_id)}"
    detail = _audit_free(detail_json)
    if _same_json(detail, first):
        return f"show(JSON.parse(FIRST), {ids});\n"
    changes = _changes(first, detail)
    if changes is not None:
        return f"show(changed(JSON.parse({_js_text(changes)})), {ids});\n"
    return f"show(JSON.parse({_js_text(detail)}), {ids});\n"


def _changes(first: dict[str, Any], other: dict[str, Any]) -> dict[str, Any] | None:
    """Give the changes that make `first` into `other`, or None.

    `records` gives new values and new fields of a record. `values` gives new values of
    keys. The changes do not add or remove a key, and do not remove a field. Thus such a
    difference gives None. The sequence of the records must be the same, because the
    script reads the records in their sequence. The sequence of the fields in a record
    can be different, because the script reads a field by its name. The function applies
    the changes and compares the result with `other`. A difference gives None."""
    if list(first) != list(other):
        return None
    records: dict[str, Any] = {}
    values: dict[str, Any] = {}
    for key, value in other.items():
        fields = _new_fields(first[key], value)
        if fields is None:
            values[key] = value
        elif fields:
            records[key] = fields
    result = dict(first)
    for key, fields in records.items():
        result[key] = {**first[key], **fields}
    result.update(values)
    if json.dumps(result, sort_keys=True) != json.dumps(other, sort_keys=True):
        return None
    return {"records": records, "values": values}


def _new_fields(old: object, value: object) -> dict[str, Any] | None:
    """Give the new and changed fields of a record, or None for a full new value.

    The same values give an empty table. A value that is not a record, or a record that
    does not have all fields of `old`, gives None if it is not the same value."""
    if not (isinstance(value, dict) and isinstance(old, dict) and set(old) <= set(value)):
        return {} if _same_json(value, old) else None
    return {f: v for f, v in value.items() if f not in old or not _same_json(v, old[f])}


def _same_json(a: object, b: object) -> bool:
    return _compact_json(a) == _compact_json(b)


def _compact_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _audit_free(detail_json: str) -> dict[str, Any]:
    """Give the detail without the layout audit (label boxes, card boxes and paths).

    The layout audit is for the checks. The script does not use it."""
    parsed: dict[str, Any] = json.loads(detail_json)
    meta = dict(parsed.get("_meta") or {})
    meta.pop("labels", None)
    meta.pop("cards", None)
    meta.pop("paths", None)
    parsed["_meta"] = meta
    return parsed


def _js_text(value: object) -> str:
    """Give the JSON of `value` as the text of a JavaScript string for `JSON.parse`.

    In an object literal, the key `__proto__` sets the prototype. `JSON.parse` makes a
    property of the object. Escaping `</` prevents artifact text from closing the
    script. Escaping `<!--` prevents a change to the end of the script by artifact text."""
    data = json.dumps(_compact_json(value), ensure_ascii=False)
    return line_safe(data.replace("</", "<\\/").replace("<!--", "\\u003c!--"))


def _detail_text(detail_json: str) -> str:
    """Give the detail JSON, without the layout audit, as the text of a JavaScript string."""
    return _js_text(_audit_free(detail_json))


def _palette(t: dict[str, Any], variables: bool) -> str:
    return json.dumps({key: Palette(t, variables)[key] for key in ("ink", "accent")})


_VIEW_JS = r"""
if(!svg){ return; }
// A table of model IDs has no prototype. Thus an ID such as `__proto__`,
// `constructor` or `toString` does not read or change an object prototype.
function table(){ return Object.create(null); }
function recordOf(id){
  // The record of a component, or null. `_meta` and prototype properties are not records.
  return id !== '_meta' && Object.prototype.hasOwnProperty.call(DETAIL, id) ? DETAIL[id] : null;
}
var META = DETAIL._meta || {};
var LAYERS = META.layers || [];
var EDGES = META.edges || [];
var RULES = table(), RULE_LEVEL = table(), ATEXT = META.assurance_text || {};
(META.rules || []).forEach(function(r){ RULES[r.n] = r.text; RULE_LEVEL[r.n] = r.assurance; });
// Layer colors come from the theme.
var LCOL = table(), LAYER_AT = table();
LAYERS.forEach(function(l){ LCOL[l.id] = l.colour; LAYER_AT[l.id] = l; });
// Which edges and which cards each reading shows, decided in Python
// (systemap.model.reading) and carried in the detail, so the page's layer
// switch and a figure of one layer read the same table.
var READINGS = META.readings || {};
var IN_READING = table(), SUBJECT_OF = table();
Object.keys(READINGS).forEach(function(L){
  IN_READING[L] = table(); SUBJECT_OF[L] = table();
  (READINGS[L].edges || []).forEach(function(i){ IN_READING[L][i] = true; });
  (READINGS[L].subjects || []).forEach(function(id){ SUBJECT_OF[L][id] = true; });
});
var NS = 'http://www.w3.org/2000/svg';
function esc(s){ return String(s).replace(/[&<>"]/g, function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
var nodes = Array.prototype.slice.call(svg.querySelectorAll('.node'));
var flows = Array.prototype.slice.call(svg.querySelectorAll('.flow'));
var labels = Array.prototype.slice.call(svg.querySelectorAll('.flowlbl'));
var nodeOf = table(), labelOf = table(), flowOf = table();
nodes.forEach(function(n){ nodeOf[n.dataset.id] = n; });
labels.forEach(function(l){ labelOf[l.dataset.edge] = l; });
flows.forEach(function(p){ flowOf[p.dataset.edge] = p; });
var state = {focus:'', layer:'all', journey:null, edge:-1, peek:-1, motion:true};

// ---- what a focus lights ----------------------------------------------------
// The focused card, the edges of it the reading shows, and their other
// ends: one set, read from the readings table, that the dimming, the
// tags and the framing all use, so what is framed is exactly what is lit.
function focusEdges(f, L){
  var d = recordOf(f), all = d && d.edges || [];
  if(L === 'structure'){ return []; }
  return all.filter(function(i){ return edgeIn(i, L); });
}
function litSet(){
  var f = state.focus;
  if(!f || !recordOf(f)){ return null; }
  var chosen = selectedEdge();
  var ids = table();
  var edges = chosen >= 0 ? [chosen] : (state.journey ? [] : focusEdges(f, state.layer));
  ids[f] = true;
  edges.forEach(function(i){ ids[EDGES[i].from] = true; ids[EDGES[i].to] = true; });
  return {id:f, ids:ids, edges:edges};
}

function setCls(el, map){
  for(var k in map){ if(map.hasOwnProperty(k)){ el.classList.toggle(k, !!map[k]); } }
}
function boxOf(n){
  var r = n.querySelector('.node__box');
  return {x:+r.getAttribute('x'), y:+r.getAttribute('y'),
    w:+r.getAttribute('width'), h:+r.getAttribute('height')};
}
function el(name, attrs, text){
  var e = document.createElementNS(NS, name);
  for(var k in attrs){ if(attrs.hasOwnProperty(k)){ e.setAttribute(k, attrs[k]); } }
  if(text !== undefined){ e.textContent = text; }
  return e;
}

// ---- the viewport ---------------------------------------------------------
// The drawing sits in <g class="view" transform="translate(tx ty) scale(k)">.
// (tx, ty, k) are in viewBox units, so a drawing point p lands at k*p + t in
// the viewBox and every box or path read from the figure stays in drawing
// units. `base` is the CSS pixels the browser gives one viewBox unit; the
// zoom the reader sees is base*k, and Fit (the whole map across the column)
// is k = 1, t = 0. Wheel and pinch zoom about the pointer, a drag pans, a
// selection or a journey step frames its neighbourhood in the part of the
// figure the reader can see (the figure's box clipped to the window, less
// whatever the page lays over it), and Escape (in the page around this
// script) returns to the view before the framing began.
var view = svg.querySelector('.view');
var VB = svg.viewBox.baseVal;
var ZMIN = 0.4, ZMAX = 2.5, ZCAP = 1.4, FRAME_PAD = 28, ANIM_MS = 300;
// Fit on the page: the drawn map (`data-fit`, drawing units) whole in the part of
// the map frame that the page does not cover, FIT_PAD screen pixels from its edges.
// A figure keeps k = 1, t = 0: its viewBox.
var FIT = (svg.getAttribute('data-fit') || '').split(' ').map(Number), FIT_PAD = 8, FIT_MAX = 1.5;
// `fitted`: the last Fit view. `cur`: what is drawn now, mid-animation included.
// `goal`: where the view is heading. `saved`: the view before the current framing
// chain. `framed`: the view on screen is one a frame() set. `lastFrame`: {rect,
// area, k}, what the last framing fitted where. `stillQueue`: work that waits
// until the camera stops.
var fitted = null, cur = {k:1, tx:0, ty:0}, goal = {k:1, tx:0, ty:0};
var saved = null, framed = false, lastFrame = null;
var anim = 0, booted = false, dragged = false, stillQueue = [];
function flushStill(){
  var q = stillQueue;
  stillQueue = [];
  q.forEach(function(fn){ fn(true); });
}
function bezier(x1, y1, x2, y2){
  // The CSS cubic-bezier timing curve, as a function of progress 0 to 1.
  function at(a, b, t){ return ((1 - 3 * b + 3 * a) * t + (3 * b - 6 * a)) * t * t + 3 * a * t; }
  return function(u){
    var t = u;
    for(var k = 0; k < 8; k++){
      var d = ((3 - 9 * x2 + 9 * x1) * t + (6 * x2 - 12 * x1)) * t + 3 * x1;
      if(Math.abs(d) < 1e-6){ break; }
      t = Math.min(1, Math.max(0, t - (at(x1, x2, t) - u) / d));
    }
    return at(y1, y2, t);
  };
}
var easeCamera = bezier(.45, 0, .25, 1);
function whenStill(fn){
  // A line draws after the camera stops. The argument tells if it waited.
  if(anim){ stillQueue.push(fn); } else { fn(false); }
}
function base(){ var m = svg.getScreenCTM(); return m && m.a ? m.a : 1; }
function reduced(){
  // The page setting decides when the page has one. A figure without the
  // setting follows the system setting.
  var set = document.documentElement.dataset.reduceMotion;
  if(!state.motion || set === 'true'){ return true; }
  return !set && !!(window.matchMedia
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
}
function fitView(){
  var a = PAGE && FIT[2] > 0 ? visibleArea(null, true) : null, b = base();
  var p = FIT_PAD / b, k = a ? Math.min(FIT_MAX / b, (a.w - 2 * p) / FIT[2],
    (a.h - 2 * p) / FIT[3]) : 0;
  if(!(k > 0)){ return {k:1, tx:0, ty:0}; }
  return {k:k, tx:a.x + a.w / 2 - k * (FIT[0] + FIT[2] / 2),
    ty:a.y + a.h / 2 - k * (FIT[1] + FIT[3] / 2)};
}
function isFit(v){
  v = v || goal;
  var f = fitted || {k:1, tx:0, ty:0};
  return Math.abs(v.k / f.k - 1) < 1e-3 && Math.abs(v.tx - f.tx) < 0.5
    && Math.abs(v.ty - f.ty) < 0.5;
}
function fit(instant){
  framed = false; saved = null;
  fitted = fitView();
  setView(fitted, instant, fitted.k);
}
function centre(){ return {x:VB.x + VB.width / 2, y:VB.y + VB.height / 2}; }
function toVb(clientX, clientY){
  // A client point in viewBox units.
  var m = svg.getScreenCTM();
  if(!m){ return centre(); }
  var q = new DOMPoint(clientX, clientY).matrixTransform(m.inverse());
  return {x:q.x, y:q.y};
}
function clampView(v, kmin){
  // The zoom stays between ZMIN and ZMAX, except that the zoom on screen
  // and the zoom a framing asks for (kmin) are always allowed: Fit on a
  // column so narrow that Fit is under ZMIN, and a lit set too large for
  // the visible area at ZMIN, which is fitted whole rather than cropped
  // (zooming out from there is a no-op, never a jump in). A fifth of the
  // viewport always holds drawing, so the map cannot be dragged out of sight.
  var b = base(), lo = Math.min(Math.min(ZMIN, b) / b, goal.k), hi = ZMAX / b;
  if(kmin !== undefined){ lo = Math.min(lo, kmin); }
  var k = Math.min(hi, Math.max(lo, v.k));
  var mx = VB.width * 0.2, my = VB.height * 0.2;
  var tx = Math.min(VB.x + VB.width - mx - k * VB.x,
    Math.max(VB.x + mx - k * (VB.x + VB.width), v.tx));
  var ty = Math.min(VB.y + VB.height - my - k * VB.y,
    Math.max(VB.y + my - k * (VB.y + VB.height), v.ty));
  return {k:k, tx:tx, ty:ty};
}
function apply(v){
  cur = v;
  if(view){
    view.setAttribute('transform', 'translate(' + v.tx.toFixed(2) + ' ' + v.ty.toFixed(2)
      + ') scale(' + v.k.toFixed(4) + ')');
  }
  svg.dispatchEvent(new CustomEvent('systemap:view',
    {detail:{zoom:base() * v.k, fit:isFit(v)}, bubbles:true}));
}
function setView(v, instant, kmin){
  goal = clampView(v, kmin);
  if(anim){ cancelAnimationFrame(anim); anim = 0; }
  if(instant || !booted || reduced()){ apply(goal); flushStill(); return; }
  var from = cur, to = goal, t0 = 0;
  function tick(now){
    // 300 ms, ease-in-out: the camera moves to the step and stops.
    if(!t0){ t0 = now; }
    var u = Math.min(1, (now - t0) / ANIM_MS);
    var e = u === 1 ? 1 : easeCamera(u);
    apply({k:from.k + (to.k - from.k) * e, tx:from.tx + (to.tx - from.tx) * e,
      ty:from.ty + (to.ty - from.ty) * e});
    anim = u < 1 ? requestAnimationFrame(tick) : 0;
    if(!anim){ flushStill(); }
  }
  anim = requestAnimationFrame(tick);
}
function userView(v, instant){
  // The reader moved the view: it is theirs now, and there is nothing to
  // go back to until the next framing.
  framed = false; saved = null;
  setView(v, instant);
}
function zoomAt(f, cx, cy, instant){
  // Zoom by f about the viewBox point (cx, cy): the drawing point under it
  // stays under it, even when the zoom is clamped.
  var k = clampView({k:goal.k * f, tx:goal.tx, ty:goal.ty}).k, g = k / goal.k;
  userView({k:k, tx:cx - g * (cx - goal.tx), ty:cy - g * (cy - goal.ty)}, instant);
}
function aboveFoot(t, bt, one){
  // On the page, the legend and the readout lie over the foot of the map.
  // A framing keeps the selection 8 px above them, as a sequence step does.
  // Fit (`one`) keeps the map above one line of them: a legend that wraps on
  // a narrow window does not change Fit from one layer to the next.
  var top = bt;
  (PAGE ? ['map-legend', 'map-context'] : []).forEach(function(id){
    var n = document.getElementById(id), b = n && !n.hidden && n.getBoundingClientRect
      ? n.getBoundingClientRect() : null;
    var edge = b ? (one ? b.bottom - 24 : b.top - 8) : top;
    if(b && b.height > 0 && b.top > (t + bt) / 2 && edge < top){ top = edge; }
  });
  return top;
}
function visibleArea(cover, fitting){
  // The part of the figure the reader can see, in viewBox units: the
  // figure's box on screen clipped to the window (not for Fit), less
  // the box the page lays over one side of it (`cover`: {rect, side}, the
  // drawer), or the whole viewBox where the figure has no box yet. A figure
  // wholly off screen is framed in its own box: the page scrolls it into view.
  var whole = {x:VB.x, y:VB.y, w:VB.width, h:VB.height};
  var s = svg.getBoundingClientRect ? svg.getBoundingClientRect() : null;
  if(!s || !(s.width > 0) || !(s.height > 0)){ return whole; }
  var ww = window.innerWidth || s.right, wh = window.innerHeight || s.bottom;
  var l = Math.max(s.left, 0), t = Math.max(s.top, 0);
  var r = Math.min(s.right, ww), bt = Math.min(s.bottom, wh);
  if(fitting || r - l < 40 || bt - t < 40){ l = s.left; t = s.top; r = s.right; bt = s.bottom; }
  if(cover && cover.rect && cover.rect.width > 0
    && cover.rect.left < r && cover.rect.right > l
    && cover.rect.top < bt && cover.rect.bottom > t){
    if(cover.side === 'left'){ l = Math.max(l, cover.rect.right + 12); }
    else { r = Math.min(r, cover.rect.left - 12); }
  }
  bt = aboveFoot(t, bt, fitting);
  var p = toVb(l, t), q = toVb(r, bt);
  // `meet` can leave unused space inside the CSS box. The native SVG
  // clips at the viewBox, so that space cannot hold framed content.
  var x = Math.max(VB.x, p.x), y = Math.max(VB.y, p.y);
  var right = Math.min(VB.x + VB.width, q.x);
  var bottom = Math.min(VB.y + VB.height, q.y);
  return {x:x, y:y, w:Math.max(0, right - x), h:Math.max(0, bottom - y)};
}
function frameRect(r, area, instant){
  // Fit the drawing rect r into `area` (viewBox units; the whole viewBox
  // when null) at the largest zoom that shows all of it, capped at ZCAP,
  // its centre on the area's centre. A rect larger than the area at ZMIN
  // is fitted whole, never cropped. The first framing in a chain remembers
  // the view it left.
  area = area || {x:VB.x, y:VB.y, w:VB.width, h:VB.height};
  if(!(area.w > 0) || !(area.h > 0)){ return; }
  var b = base();
  var k = Math.min(ZCAP / b, area.w / r.w, area.h / r.h);
  var cx = area.x + area.w / 2, cy = area.y + area.h / 2;
  if(!framed){ saved = goal; framed = true; }
  lastFrame = {rect:r, area:area, k:k};
  setView({k:k, tx:cx - k * (r.x + r.w / 2), ty:cy - k * (r.y + r.h / 2)}, instant, k);
}
function unionBox(ids, edgeIdx){
  // The rect around some cards and the edges between them, in drawing units.
  var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  function add(x, y, w, h){
    x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x + w); y1 = Math.max(y1, y + h);
  }
  ids.forEach(function(id){
    if(nodeOf[id]){ var b = boxOf(nodeOf[id]); add(b.x, b.y, b.w, b.h); } });
  (edgeIdx || []).forEach(function(i){
    var p = flowOf[i];
    if(!p || !p.getBBox){ return; }
    var bb = p.getBBox();
    if(bb.width || bb.height){ add(bb.x, bb.y, bb.width, bb.height); }
  });
  if(x0 === Infinity){ return null; }
  return {x:x0 - FRAME_PAD, y:y0 - FRAME_PAD, w:x1 - x0 + 2 * FRAME_PAD, h:y1 - y0 + 2 * FRAME_PAD};
}
function frameFocus(cover, instant){
  // What the focus lights (litSet: the card, the edges the reading shows,
  // their other ends), framed in the visible area less `cover`.
  var lit = litSet();
  if(!lit){ return; }
  var r = unionBox(Object.keys(lit.ids), lit.edges);
  if(r){ frameRect(r, visibleArea(cover), instant); }
}
function frameJourney(step, instant){
  // The step's acting and measuring components and the edge it traces,
  // framed in the visible area; the page closes its drawer for a journey.
  var ids = (step.acts || []).concat(step.measures || []), edges = [];
  if(step.edge >= 0 && EDGES[step.edge]){
    ids.push(EDGES[step.edge].from); ids.push(EDGES[step.edge].to); edges.push(step.edge);
  }
  var r = unionBox(ids, edges);
  if(r){ frameRect(r, visibleArea(null), instant); }
}
function frameRegion(id){
  var box = null;
  (META.regions || []).forEach(function(z){ if(z.id === id && z.box){ box = z.box; } });
  if(!box){ return; }
  frameRect({x:box[0] - 12, y:box[1] - 12, w:box[2] + 24, h:box[3] + 24}, visibleArea(null));
}
function back(){
  // The view before the framing chain began; nothing if the reader has
  // moved the view since.
  if(!saved){ return; }
  var v = saved;
  saved = null; framed = false;
  setView(v);
}

// Wheel (and trackpad pinch, which arrives as ctrl+wheel) zooms about the
// pointer. A drag pans; under 4px of movement it is a click and the cards
// keep it. Two touches pinch.
svg.addEventListener('wheel', function(e){
  e.preventDefault();
  var d = e.deltaY;
  if(e.deltaMode === 1){ d *= 16; } else if(e.deltaMode === 2){ d *= 400; }
  var f = Math.max(0.5, Math.min(2, Math.exp(-d * (e.ctrlKey ? 0.01 : 0.0022))));
  var c = toVb(e.clientX, e.clientY);
  zoomAt(f, c.x, c.y, true);
}, {passive:false});
var ptrs = {}, drag = null, pinch = null;
function ptrList(){ return Object.keys(ptrs).map(function(k){ return ptrs[k]; }); }
function dist(a, b){ return Math.hypot(a.x - b.x, a.y - b.y); }
function startDrag(p){ drag = {x:p.x, y:p.y, tx:goal.tx, ty:goal.ty, moved:false}; }
svg.addEventListener('pointerdown', function(e){
  if(e.pointerType === 'mouse' && e.button !== 0){ return; }
  dragged = false;
  ptrs[e.pointerId] = {x:e.clientX, y:e.clientY};
  var list = ptrList();
  if(list.length === 1){ pinch = null; startDrag(list[0]); }
  else if(list.length === 2){
    drag = null;
    var m = toVb((list[0].x + list[1].x) / 2, (list[0].y + list[1].y) / 2);
    pinch = {d:dist(list[0], list[1]), k:goal.k,
      px:(m.x - goal.tx) / goal.k, py:(m.y - goal.ty) / goal.k};
  }
});
svg.addEventListener('pointermove', function(e){
  if(!ptrs[e.pointerId]){ return; }
  ptrs[e.pointerId] = {x:e.clientX, y:e.clientY};
  var list = ptrList();
  if(pinch && list.length >= 2){
    var m = toVb((list[0].x + list[1].x) / 2, (list[0].y + list[1].y) / 2);
    var k = clampView({k:pinch.k * dist(list[0], list[1]) / pinch.d, tx:0, ty:0}).k;
    dragged = true;
    userView({k:k, tx:m.x - k * pinch.px, ty:m.y - k * pinch.py}, true);
  } else if(drag){
    var dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if(!drag.moved){
      if(Math.hypot(dx, dy) < 4){ return; }
      drag.moved = true;
      svg.classList.add('panning');
      if(svg.setPointerCapture){ try { svg.setPointerCapture(e.pointerId); } catch(_x){} }
    }
    var b = base();
    userView({k:goal.k, tx:drag.tx + dx / b, ty:drag.ty + dy / b}, true);
  }
});
function endPointer(e){
  if(!ptrs[e.pointerId]){ return; }
  delete ptrs[e.pointerId];
  if(drag && drag.moved){ dragged = true; }
  drag = null; pinch = null;
  svg.classList.remove('panning');
  var list = ptrList();
  if(list.length === 1){ startDrag(list[0]); drag.moved = true; }
}
svg.addEventListener('pointerup', endPointer);
svg.addEventListener('pointercancel', endPointer);
// A click that ends a drag is not a click: nothing under the pointer hears it.
svg.addEventListener('click', function(e){
  if(dragged){ dragged = false; e.preventDefault(); e.stopImmediatePropagation(); }
}, true);
Array.prototype.slice.call(svg.querySelectorAll('[data-zone]')).forEach(function(z){
  z.addEventListener('dblclick', function(e){ e.preventDefault(); frameRegion(z.dataset.zone); });
});
// The page opens at Fit. The panel, the window, the title and the legend change the
// map frame: a view at Fit stays at Fit, and the zoom readout gets the new zoom.
if(PAGE){ fit(true); }
if(PAGE && window.ResizeObserver){
  var sizes = new ResizeObserver(function(){
    if(!anim){ if(isFit()){ fit(true); } else { apply(goal); } }
  });
  [svg, document.getElementById('map-legend')].forEach(function(n){ if(n){ sizes.observe(n); } });
}

"""

_INTERACTIVE_JS = _VIEW_JS + RELATION_JS + LABEL_JS
