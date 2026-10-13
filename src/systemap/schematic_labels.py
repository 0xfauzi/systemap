"""Map labels that become larger when the map is small on the screen.

When the zoom is less than 100 percent, flow labels, region labels and
container labels become larger, so that they show at 11 px on the screen.
They do not become larger than the card descriptions: the SVG attribute
`data-grow` gives that limit. The layout sizes do not change, so
`systemap check` and `systemap place` give the same results.

A container label becomes larger from the top left corner of its container.
A region label becomes larger from the left edge of its region, at the middle
of its number ring. Each label stays in its box and keeps off cards, lines
and the step numbers and tags of a sequence. A flow label moves along the
nearest part of its own line to the nearest place where its text touches no
card, no other label and no line that it did not touch at its layout size.
A flow label with no such place shows only for a pointer, keyboard focus or
selection, as a label beside its line does. The readout counts these labels
with the labels beside their lines.
"""

LABEL_JS = r"""
// ---- labels that become larger on a small map ---------------------------------
var GROW = +svg.getAttribute('data-grow') || 1, BESIDE = besideEdges.slice();
var growKey = '', growSoon = 0, SEGS = [];
function hits(a, b, pad){
  return a.x < b.x + b.w + pad && b.x < a.x + a.w + pad && a.y < b.y + b.h + pad
    && b.y < a.y + a.h + pad;
}
function tf(g, s, x, y, dx, dy){
  // Scale g by s about the point (x, y), then move it by (dx, dy).
  if(s === 1 && !dx && !dy){ g.removeAttribute('transform'); return; }
  g.setAttribute('transform', 'matrix(' + s + ' 0 0 ' + s + ' ' + (x * (1 - s) + (dx || 0))
    .toFixed(2) + ' ' + (y * (1 - s) + (dy || 0)).toFixed(2) + ')');
}
// Each line as one box for each horizontal or vertical run.
flows.forEach(function(p){
  var pts = pointsOf(p.getAttribute('d'));
  for(var k = 1; k < pts.length; k++){
    var a = pts[k - 1], b = pts[k];
    SEGS.push({e:+p.dataset.edge, x:Math.min(a.x, b.x), y:Math.min(a.y, b.y),
      w:Math.abs(a.x - b.x), h:Math.abs(a.y - b.y)});
  }
});
function part(g, box, x, y, i){
  // A label: its layout box, its anchor (x, y) and the lines through it at layout size.
  var on = {};
  SEGS.forEach(function(q){ if(hits(q, box, 0)){ on[q.e] = true; } });
  return {g:g, box:box, x:x, y:y, i:i, base:on};
}
var HEADS = [].map.call(svg.querySelectorAll('.zone__h,.box__h'), function(g){
  var at = (g.getAttribute('data-at') || '').split(' '), b = g.getBBox();
  var h = part(g, {x:b.x, y:b.y, w:b.width, h:b.height}, +at[0], +at[1], -1);
  h.end = +at[0] + +at[2] - 6;
  return h;
}).filter(function(h){ return h.box.w > 0; });
var LABS = labels.map(function(l){
  // The anchor is the middle of the layout box. The box for collisions is the box
  // of the text, or the layout box where the text has no box.
  var r = l.querySelector('.flowlbl__hit'), i = +l.dataset.edge;
  var t = l.querySelector('text').getBBox();
  var box = {x:+r.getAttribute('x'), y:+r.getAttribute('y') + 6, w:+r.getAttribute('width'),
    h:+r.getAttribute('height') - 12}, x = box.x + box.w / 2, y = box.y + box.h / 2;
  if(t.width){ box = {x:t.x, y:t.y, w:t.width, h:t.height}; }
  var b = part(l, box, x, y, i), near = box.w / 2 + 8;
  // The run of its own line nearest to the label: under it, or beside it.
  SEGS.forEach(function(q){
    var d = Math.max(q.x - b.x, b.x - q.x - q.w, 0) + Math.max(q.y - b.y, b.y - q.y - q.h, 0);
    if(q.e === i && d < near){ near = d; b.own = q; }
  });
  return b;
});
function growth(){
  // The label scale for 11 px on the screen, in steps of 0.02.
  return Math.min(GROW, Math.max(1, Math.ceil(50 / (base() * cur.k) - 1e-6) / 50));
}
function free(r, ctx, b){
  return !ctx.cards.some(function(c){ return hits(r, c, 2); })
    && !ctx.taken.some(function(t){ return hits(r, t, 1); })
    && !ctx.segs.some(function(q){ return q.e !== b.i && !b.base[q.e] && hits(q, r, 0); });
}
function placeHead(h, s, ctx){
  // The largest scale up to s at which the label has room in its box.
  var t = s, r;
  for(;; t = Math.max(1, t - 0.04)){
    r = {x:h.x + (h.box.x - h.x) * t, y:h.y + (h.box.y - h.y) * t, w:h.box.w * t,
      h:h.box.h * t};
    if(t === 1 || (r.x + r.w <= h.end && free(r, ctx, h))){ break; }
  }
  tf(h.g, t, h.x, h.y);
  ctx.taken.push(r);
}
function placeLabel(b, s, ctx){
  // The nearest free place on the run of its own line, 2 units at a time.
  if(s === 1){ tf(b.g, 1); ctx.taken.push(b.box); return true; }
  var q = b.own, flat = q && !q.h, w = b.box.w * s, h = b.box.h * s;
  for(var n = 0; n <= 240; n = n > 0 ? -n : 2 - n){
    var dx = flat ? n : 0, dy = flat ? 0 : n;
    var r = {x:b.x + (b.box.x - b.x) * s + dx, y:b.y + (b.box.y - b.y) * s + dy, w:w, h:h};
    if(n && !(q && (flat ? r.x >= q.x + 4 && r.x + w <= q.x + q.w - 4
      : r.y >= q.y + 4 && r.y + h <= q.y + q.h - 4))){ continue; }
    if(free(r, ctx, b)){
      ctx.taken.push(r);
      tf(b.g, s, b.x, b.y, dx, dy);
      return true;
    }
  }
  tf(b.g, s, b.x, b.y);
  return false;
}
// The boxes of the sequence marks, in drawing units, and their text for the key. A pan or
// a zoom does not change these boxes. A change to a mark, to the attributes of the page
// root or the body, or to the loaded fonts can change them. Then the stored boxes go, and
// the next relabel call reads the boxes again. Without MutationObserver, each call reads.
var markGroup = null, markWatch = null, markStore = null;
function forgetMarks(){ markStore = null; }
function watchMarks(g){
  if(g === markGroup){ return; }
  markGroup = g; forgetMarks();
  if(markWatch){ markWatch.disconnect(); markWatch = null; }
  if(!g || typeof MutationObserver !== 'function'){ return; }
  markWatch = new MutationObserver(forgetMarks);
  markWatch.observe(g, {subtree:true, childList:true, attributes:true, characterData:true});
  [document.documentElement, document.body].forEach(function(n){
    if(n){ markWatch.observe(n, {attributes:true}); } });
}
if(document.fonts && document.fonts.addEventListener){
  document.fonts.addEventListener('loadingdone', forgetMarks); }
function markBoxes(g){
  watchMarks(g);
  if(markWatch && markWatch.takeRecords().length){ forgetMarks(); }
  if(markStore){ return markStore; }
  var m = view.getScreenCTM(), k = m ? Math.hypot(m.a, m.b) : 0, boxes = [];
  [].forEach.call(g ? g.childNodes : [], function(c){
    var r = c.getBoundingClientRect();
    if(k && r.width){ boxes.push({x:(r.left - m.e) / k, y:(r.top - m.f) / k,
      w:r.width / k, h:r.height / k}); }
  });
  var out = {boxes:boxes, text:boxes.map(function(r){ return [r.x, r.y, r.w, r.h].map(
    function(v){ return v.toFixed(1); }).join(','); }).join(';')};
  // A map with no screen transform has no boxes to keep.
  if(markWatch && k){ markStore = out; }
  return out;
}
function relabel(){
  growSoon = 0;
  var L = state.layer, s = growth(), j = state.journey, g = svg.querySelector('.seq-marks');
  // The step numbers, tags and notes of a sequence, in drawing units. The key contains
  // their boxes. Thus relabel calculates the labels again when a mark moves or changes.
  var marks = j ? markBoxes(g) : {boxes:[], text:''};
  var key = L + s + svg.classList.contains('fg-on') + (j ? (j.whole ? 'w' : j.edge) : '')
    + marks.text;
  if(key === growKey){ return; }
  growKey = key;
  function on(i){ return edgeIn(i, L) && !flowOf[i].classList.contains('fg-hide'); }
  var ctx = {taken:marks.boxes.slice(), cards:nodes.map(boxOf),
    segs:SEGS.filter(function(q){ return on(q.e); })};
  var crowd = BESIDE.slice();
  HEADS.forEach(function(h){ placeHead(h, s, ctx); });
  LABS.forEach(function(b){
    if(BESIDE.indexOf(b.i) >= 0 || !on(b.i)){ tf(b.g, s, b.x, b.y); }
    else if(!placeLabel(b, s, ctx)){ crowd.push(b.i); }
  });
  // The paint and the readout change only when the list changes.
  if(crowd.length === besideEdges.length && crowd.every(function(i){ return besideOf[i]; })){
    return; }
  for(var e in besideOf){ delete besideOf[e]; }
  besideEdges.length = 0;
  crowd.forEach(function(i){ besideOf[i] = true; besideEdges.push(i); });
  paint();
  if(svg.page && svg.page.syncFrame){ svg.page.syncFrame(); }
}
['systemap:view', 'systemap:layer', 'systemap:workspace'].forEach(function(name){
  svg.addEventListener(name, function(){
    if(!growSoon){ growSoon = requestAnimationFrame(relabel); } });
});
relabel();
"""
