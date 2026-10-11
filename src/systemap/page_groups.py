"""Flow groups: one line for all the flows between two regions of a busy layer.

A layer with more than `LIMIT` flows shows groups first. Each pair of regions
that exchange flows in the layer gets one neutral line. A badge on the line
gives the quantity of flows, and an arrowhead shows each direction. A
container that holds cards directly, such as the outside container, is one
region here. Flows inside one region stay as routes. When the reader selects
a group, the map shows the routes of the group in the colour of their kind,
and the other cards fade. The Read panel lists the groups. A control in the
panel shows all routes again.
"""

LIMIT = 20

CSS = r"""
#schematic .flow.fg-hide:not(.peek),#schematic .flowlbl.fg-hide:not(.peek){opacity:0;
visibility:hidden;pointer-events:none;transition:opacity .16s ease-out,visibility 0s linear .16s}
#schematic .node.fg-out:not(.quiet):not(.dim){opacity:.6}
#schematic:not(.fg-on) .fg-lines,#schematic:not(.fg-on) .fg-badges{display:none}
#schematic .fg-group.open,#schematic .fg-badge.open{display:none}
#schematic .fg-group{cursor:pointer;opacity:.8;transition:opacity .16s ease-out}
#schematic .fg-line{fill:none;stroke:var(--ink-3);stroke-width:var(--w,3);stroke-linejoin:round;
transition:stroke .12s ease-out,stroke-width .12s ease-out}
#schematic .fg-arrow{fill:var(--ink-3);stroke:none;transition:fill .12s ease-out}
#schematic .fg-hit{fill:none;stroke:transparent;stroke-width:18;pointer-events:stroke}
#schematic.fg-quiet .fg-group{opacity:.6}
#schematic.fg-peek .fg-group{opacity:.4}
#schematic .fg-group.hover{opacity:1}
#schematic .fg-group.hover .fg-line{stroke:var(--ink-2);stroke-width:calc(var(--w,3) + 1.5)}
#schematic .fg-group.hover .fg-arrow{fill:var(--ink-2)}
#schematic .fg-badge{cursor:pointer;outline:none}
#schematic .fg-badge__c{fill:var(--map);stroke:var(--ink-3);stroke-width:1.7;
transition:stroke .12s ease-out}
#schematic .fg-badge text{font:600 13.5px var(--fm);fill:var(--ink);text-anchor:middle;
dominant-baseline:central;pointer-events:none}
#schematic .fg-badge.hover .fg-badge__c{stroke:var(--ink)}
#schematic .fg-badge__ring{fill:none;stroke:var(--ink);stroke-width:2;display:none}
#schematic .fg-badge:focus-visible .fg-badge__ring{display:inline}
@media (prefers-reduced-motion:reduce){#schematic .fg-group,#schematic .fg-line,
#schematic .fg-arrow,#schematic .fg-badge__c{transition:none}}
html[data-reduce-motion="true"] #schematic :is(.fg-group,.fg-line,.fg-arrow,.fg-badge__c){
transition:none}
.lg__line.fg-lg__group{border-top:4px solid var(--ink-3);opacity:.7}
.lg__card.fg-lg__out{opacity:.6;background:var(--card)}

/* ---- the Read panel: the groups of the layer, in the style of the steps ------ */
.readpanel .fg-open{border:1px solid var(--accent);border-radius:8px;background:var(--hl-soft);
padding:12px;display:flex;flex-direction:column;gap:10px}
.readpanel :is(.fg-open__head,.fg-flow,.fg-row){width:100%;min-height:0;height:auto;padding:0;
border:0;border-radius:4px;background:none;text-align:left}
.readpanel .fg-open__head{display:grid;grid-template-columns:20px minmax(0,1fr);gap:10px;
align-items:center}
.readpanel :is(.fg-open__head,.fg-flow):hover{background:none}
.readpanel .fg-open__name{font:12px/20px var(--fm);color:var(--accent)}
:root[data-theme="light"] .readpanel .fg-open__name{justify-self:start;padding:0 3px;
border-radius:2px;background:var(--hl);color:var(--ink)}
.readpanel .fg-open__flows{list-style:none;margin:0;padding:0 0 0 30px;display:grid;
grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 14px}
.readpanel .fg-flow{display:flex;flex-direction:column;align-items:flex-start}
.readpanel .fg-flow:hover span{text-decoration:underline;text-underline-offset:3px}
.readpanel .fg-flow span{font:13px/18px var(--fs);color:var(--ink);overflow-wrap:anywhere}
.readpanel .fg-flow small{font:12px/16px var(--fm);color:var(--ink-3);overflow-wrap:anywhere}
.readpanel .fg-open__sum{margin:0;padding-left:30px;font:12px/16px var(--fs);color:var(--ink-3)}
.readpanel .fg-rows{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:2px}
.readpanel .fg-row{display:grid;grid-template-columns:20px auto minmax(0,1fr);gap:10px;
align-items:center;height:30px;padding:0 4px;color:var(--ink-3);font:12px/16px var(--fs)}
.readpanel .fg-row:hover{background:var(--raised)}
.readpanel :is(.fg-row,.fg-open__head) b{width:20px;height:20px;border:1px solid var(--line-2);
border-radius:50%;display:inline-flex;align-items:center;justify-content:center;
font:600 11px/1 var(--fm);color:var(--ink-2)}
.readpanel .fg-open__head b{border:0;background:var(--accent);color:var(--on-accent)}
.readpanel .fg-row__name{font:12px/16px var(--fm);color:var(--ink);white-space:nowrap}
.readpanel .fg-row__arts{min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.readpanel .fg-read__foot{display:flex;justify-content:space-between;align-items:center;gap:12px}
.readpanel .fg-read__all{flex:none;height:28px;min-height:28px;padding:0 10px;font-size:12px}
"""

SCRIPT = r"""
(function(){
  var svg = document.getElementById('schematic');
  if(!svg || !svg.systemap || !svg.page){ return; }
  var A = svg.systemap, P = svg.page, META = A.detail._meta || {};
  var view = svg.querySelector('.view');
  if(!view || !(META.regions || []).length){ return; }
  var NS = 'http://www.w3.org/2000/svg', LIMIT = __LIMIT__, LAY = {};
  A.layers.forEach(function(l){ LAY[l.id] = l; });
  function all(sel, root){
    return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function el(name, attrs, text){
    var e = document.createElementNS(NS, name);
    Object.keys(attrs || {}).forEach(function(k){ e.setAttribute(k, attrs[k]); });
    if(text !== undefined){ e.textContent = text; }
    return e;
  }
  function reduced(){
    return document.documentElement.dataset.reduceMotion === 'true' ||
      !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }
  function plural(n, word){ return n + ' ' + word + (n === 1 ? '' : 's'); }
  function flat(lists){ return [].concat.apply([], lists); }
  function bucket(list, keyOf){
    // The items of a list by key, and the keys in the order of their first item.
    var by = {}, order = [];
    list.forEach(function(i){
      var k = keyOf(i);
      if(!by[k]){ by[k] = []; order.push(k); }
      by[k].push(i);
    });
    return {by:by, order:order};
  }

  // ---- the places: each region, and each container that holds cards --------
  function rect(x, y, w, h){ return {x0:x, y0:y, x1:x + w, y1:y + h}; }
  function rectOf(r){ return rect(+r.getAttribute('x'), +r.getAttribute('y'),
    +r.getAttribute('width'), +r.getAttribute('height')); }
  function holds(a, b){
    return b.x0 >= a.x0 - .5 && b.y0 >= a.y0 - .5 && b.x1 <= a.x1 + .5 && b.y1 <= a.y1 + .5; }
  function size(b){ return (b.x1 - b.x0) * (b.y1 - b.y0); }
  function grow(b, d){ return {x0:b.x0 - d, y0:b.y0 - d, x1:b.x1 + d, y1:b.y1 + d}; }
  function union(u, b){ return u ? {x0:Math.min(u.x0, b.x0), y0:Math.min(u.y0, b.y0),
    x1:Math.max(u.x1, b.x1), y1:Math.max(u.y1, b.y1)} : b; }
  var HOME = {}, CARD = {}, ROUTES = all('path.flow[data-edge]', svg), LABELS = {};
  all('.flowlbl[data-edge]', svg).forEach(function(l){ LABELS[l.dataset.edge] = l; });
  all('.node', svg).forEach(function(n){
    var r = n.querySelector('.node__box');
    if(r){ CARD[n.dataset.id] = {node:n, box:rectOf(r)}; }
  });
  META.regions.forEach(function(r, k){
    HOME[r.id] = {id:r.id, rank:k + 1, label:r.label, name:(k + 1) + ' ' + r.label,
      box:rect(r.box[0], r.box[1], r.box[2], r.box[3])};
  });
  var REGION_BOXES = META.regions.map(function(r){ return HOME[r.id].box; });
  function homeOf(id){ var d = A.detail[id]; return (d && d.region) || ''; }
  (function(){
    var frames = all(':scope > rect', view).map(rectOf), cards = {}, order = [];
    Object.keys(CARD).forEach(function(id){
      var h = homeOf(id);
      if(HOME[h]){ return; }
      if(!cards[h]){ order.push(h); }
      cards[h] = union(cards[h], CARD[id].box);
    });
    order.forEach(function(h, k){
      // The frame of the container, when it holds no region; else the cards.
      var u = cards[h], fit = null, label = h ? h.replace(/[-_]+/g, ' ').toUpperCase()
        : 'NO REGION';
      frames.forEach(function(f){
        if(holds(f, u) && !REGION_BOXES.some(function(r){ return holds(f, r); })
          && (!fit || size(f) < size(fit))){ fit = f; }
      });
      HOME[h] = {id:h, rank:100 + k, label:label, name:label, box:fit || grow(u, 14)};
    });
  })();
  function home(h){ return HOME[h] || {id:h, rank:999, label:h, name:h}; }

  // ---- the groups of a layer --------------------------------------------------
  // One group for each pair of places that exchange flows, and one group for
  // the flows inside one region. Each flow is in one group only.
  function edgesIn(L){
    if(L === 'all'){ return A.edges.map(function(_e, i){ return i; }); }
    var r = META.readings && META.readings[L];
    return r && L !== 'structure' ? r.edges.slice() : [];
  }
  function byArtifact(list){
    // The flows of one artifact stay together, in the order of their first flow.
    var b = bucket(list, function(i){ return A.edges[i].art; });
    return flat(b.order.map(function(a){ return b.by[a]; }));
  }
  function between(key, list){
    var ids = key.split('|'), h0 = home(ids[0]), h1 = home(ids[1]);
    var out0 = list.filter(function(i){ return homeOf(A.edges[i].from) === ids[0]; });
    var out1 = list.filter(function(i){ return homeOf(A.edges[i].from) !== ids[0]; });
    // The place that sends more flows comes first.
    var swap = out1.length > out0.length, fwd = swap ? out1 : out0, back = swap ? out0 : out1;
    var a = swap ? h1 : h0, b = swap ? h0 : h1, two = fwd.length > 0 && back.length > 0;
    return {key:key, a:a, b:b, two:two, fwd:fwd, back:back,
      edges:byArtifact(fwd).concat(byArtifact(back)),
      name:a.name + (two ? ' ⇄ ' : ' → ') + b.name,
      say:a.name + (two ? ' to and from ' : ' to ') + b.name};
  }
  function inside(list){
    var b = bucket(list, function(i){ return homeOf(A.edges[i].from); });
    b.order.sort(function(x, y){
      return b.by[y].length - b.by[x].length || home(x).rank - home(y).rank; });
    return {key:'inside', inside:true, two:false, name:'INSIDE ONE REGION',
      edges:flat(b.order.map(function(h){ return byArtifact(b.by[h]); })),
      parts:b.order.map(function(h){ return home(h).label + ' ' + b.by[h].length; })};
  }
  function groupsOf(list){
    var within = list.filter(function(i){
      return homeOf(A.edges[i].from) === homeOf(A.edges[i].to); });
    var b = bucket(list.filter(function(i){ return within.indexOf(i) < 0; }), function(i){
      var x = homeOf(A.edges[i].from), y = homeOf(A.edges[i].to);
      return home(x).rank <= home(y).rank ? x + '|' + y : y + '|' + x;
    });
    var out = b.order.map(function(k){ return between(k, b.by[k]); });
    out.sort(function(x, y){
      return y.edges.length - x.edges.length || (y.two ? 1 : 0) - (x.two ? 1 : 0)
        || x.a.rank - y.a.rank || x.b.rank - y.b.rank;
    });
    return within.length ? out.concat([inside(within)]) : out;
  }
  var CACHE = {};
  function info(L){
    if(!CACHE[L]){
      var list = edgesIn(L), groups = groupsOf(list);
      var lines = groups.filter(function(g){ return !g.inside; });
      CACHE[L] = {list:list, groups:groups, lines:lines, geo:null,
        on:list.length > LIMIT && lines.length >= 2};
    }
    return CACHE[L];
  }

  // ---- the lines: straight, or with one or two bends, from edge to edge ------
  // The line goes through the space between the places, at the largest
  // distance from other places and from the lines of larger groups.
  var VB = svg.viewBox.baseVal, CLEAR = 6, GAP = 12, INSET = 14;
  var BLOCKS = (META.headers || []).filter(function(h){ return h.kind === 'container'; })
    .map(function(h){ return rect(h.box[0], h.box[1], h.box[2], h.box[3]); });
  function len(p, q){ return Math.hypot(q.x - p.x, q.y - p.y); }
  function hits(p, q, b, pad){
    // True when the segment pq goes into the box b, grown by pad.
    var dx = q.x - p.x, dy = q.y - p.y, t0 = 0, t1 = 1;
    var ps = [-dx, dx, -dy, dy];
    var qs = [p.x - b.x0 + pad, b.x1 + pad - p.x, p.y - b.y0 + pad, b.y1 + pad - p.y];
    for(var k = 0; k < 4; k++){
      if(ps[k] === 0){ if(qs[k] <= 0){ return false; } continue; }
      var r = qs[k] / ps[k];
      if(ps[k] < 0){ if(r > t1){ return false; } t0 = Math.max(t0, r); }
      else { if(r < t0){ return false; } t1 = Math.min(t1, r); }
    }
    return t1 - t0 > 1e-6;
  }
  function toSeg(c, a, b){
    var dx = b.x - a.x, dy = b.y - a.y, l = dx * dx + dy * dy;
    var t = l ? Math.max(0, Math.min(1, ((c.x - a.x) * dx + (c.y - a.y) * dy) / l)) : 0;
    return Math.hypot(c.x - a.x - t * dx, c.y - a.y - t * dy);
  }
  function side(a, b, c){ return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x); }
  function crosses(a, b, c, d){
    return side(a, b, c) * side(a, b, d) < 0 && side(c, d, a) * side(c, d, b) < 0; }
  function apart(a, b, c, d){
    if(crosses(a, b, c, d)){ return 0; }
    return Math.min(toSeg(a, c, d), toSeg(b, c, d), toSeg(c, a, b), toSeg(d, a, b));
  }
  function fromBox(a, b, r){
    if(hits(a, b, r, 0)){ return 0; }
    var c = [{x:r.x0, y:r.y0}, {x:r.x1, y:r.y0}, {x:r.x1, y:r.y1}, {x:r.x0, y:r.y1}], m = Infinity;
    for(var k = 0; k < 4; k++){ m = Math.min(m, apart(a, b, c[k], c[(k + 1) % 4])); }
    return m;
  }
  function angle(a, b, c, d){
    var t = Math.abs(Math.atan2(b.y - a.y, b.x - a.x) - Math.atan2(d.y - c.y, d.x - c.x)) % Math.PI;
    return Math.min(t, Math.PI - t);
  }
  function near(a, b, c, d){
    // The gap between the boxes around two segments: a fast lower bound.
    return Math.max(Math.min(c.x, d.x) - Math.max(a.x, b.x),
      Math.min(a.x, b.x) - Math.max(c.x, d.x), Math.min(c.y, d.y) - Math.max(a.y, b.y),
      Math.min(a.y, b.y) - Math.max(c.y, d.y));
  }
  function span(lo, hi, step, most){
    // Points from lo to hi, step apart, and not more than `most` + 1 points.
    if(hi < lo){ return []; }
    var n = Math.max(1, Math.min(most || 24, Math.round((hi - lo) / step))), out = [];
    for(var k = 0; k <= n; k++){ out.push(lo + (hi - lo) * k / n); }
    return out;
  }
  // The middle of each space between two box edges is a good place for a line.
  var MIDS = {x:[], y:[]};
  ['x', 'y'].forEach(function(ax){
    var edges = [VB[ax], VB[ax] + (ax === 'x' ? VB.width : VB.height)];
    Object.keys(HOME).map(function(h){ return HOME[h].box; }).concat(BLOCKS)
      .forEach(function(b){ edges.push(b[ax + '0'], b[ax + '1']); });
    edges.sort(function(p, q){ return p - q; });
    for(var k = 0; k + 1 < edges.length; k++){
      if(edges[k + 1] - edges[k] > 2 * CLEAR){ MIDS[ax].push((edges[k] + edges[k + 1]) / 2); }
    }
  });
  function marks(ax, lo, hi, step, most){
    return span(lo, hi, step, most).concat(MIDS[ax].filter(function(v){
      return v > lo && v < hi; }));
  }
  function along(B, step, most){
    return {x:marks('x', B.x0 + INSET, B.x1 - INSET, step, most),
      y:marks('y', B.y0 + INSET, B.y1 - INSET, step, most)};
  }
  function each2(xs, ys, fn){ xs.forEach(function(x){ ys.forEach(function(y){ fn(x, y); }); }); }
  function shapesFor(P0, P1){
    var out = [], a = along(P0, 8, 20), b = along(P1, 8, 20);
    var a2 = along(P0, 16, 10), b2 = along(P1, 16, 10);
    var above = P0.y1 <= P1.y0, below = P0.y0 >= P1.y1;
    var left = P0.x1 <= P1.x0, right = P0.x0 >= P1.x1;
    var ya = above ? P0.y1 : P0.y0, yb = above ? P1.y0 : P1.y1;
    var xa = left ? P0.x1 : P0.x0, xb = left ? P1.x0 : P1.x1;
    if(above || below){
      // Straight up or down, and with two bends through the space between.
      marks('x', Math.max(P0.x0, P1.x0) + INSET, Math.min(P0.x1, P1.x1) - INSET, 4, 40)
        .forEach(function(x){ out.push([{x:x, y:ya}, {x:x, y:yb}]); });
      marks('y', Math.min(ya, yb) + GAP, Math.max(ya, yb) - GAP, 6, 10).forEach(function(y){
        each2(a2.x, b2.x, function(x0, x1){
          if(Math.abs(x0 - x1) >= 16){
            out.push([{x:x0, y:ya}, {x:x0, y:y}, {x:x1, y:y}, {x:x1, y:yb}]); }
        });
      });
    }
    if(left || right){
      marks('y', Math.max(P0.y0, P1.y0) + INSET, Math.min(P0.y1, P1.y1) - INSET, 4, 40)
        .forEach(function(y){ out.push([{x:xa, y:y}, {x:xb, y:y}]); });
      marks('x', Math.min(xa, xb) + GAP, Math.max(xa, xb) - GAP, 6, 10).forEach(function(x){
        each2(a2.y, b2.y, function(y0, y1){
          if(Math.abs(y0 - y1) >= 16){
            out.push([{x:xa, y:y0}, {x:x, y:y0}, {x:x, y:y1}, {x:xb, y:y1}]); }
        });
      });
    }
    // One bend: out of the top or the bottom, into a side; or the opposite.
    each2(a.x, b.y, function(x, y){
      if((y < P0.y0 || y > P0.y1) && (x < P1.x0 || x > P1.x1)){
        out.push([{x:x, y:y < P0.y0 ? P0.y0 : P0.y1}, {x:x, y:y},
          {x:x < P1.x0 ? P1.x0 : P1.x1, y:y}]); }
    });
    each2(a.y, b.x, function(y, x){
      if((x < P0.x0 || x > P0.x1) && (y < P1.y0 || y > P1.y1)){
        out.push([{x:x < P0.x0 ? P0.x0 : P0.x1, y:y}, {x:x, y:y},
          {x:x, y:y < P1.y0 ? P1.y0 : P1.y1}]); }
    });
    // Every shape is horizontal and vertical lines only, as the flow routes are.
    return out;
  }
  function offCentre(p, B){
    var onSide = Math.abs(p.x - B.x0) < .5 || Math.abs(p.x - B.x1) < .5;
    return onSide ? Math.abs(p.y - (B.y0 + B.y1) / 2) : Math.abs(p.x - (B.x0 + B.x1) / 2);
  }
  function cost(shape, P0, P1, blocks, placed, badges, soft){
    var pts = shape.pts, n = pts.length - 1, in0 = grow(P0, -1), in1 = grow(P1, -1), k, s, a, b;
    var under = 0, clear = 80, cross = 0;
    for(k = 0; k <= n; k++){
      if(pts[k].x < VB.x + 4 || pts[k].x > VB.x + VB.width - 4 || pts[k].y < VB.y + 4
        || pts[k].y > VB.y + VB.height - 4){ return Infinity; }
    }
    for(k = 0; k < n; k++){
      a = pts[k]; b = pts[k + 1];
      if(hits(a, b, in0, 0) || hits(a, b, in1, 0)){ return Infinity; }
      for(s = 0; s < blocks.length; s++){ if(hits(a, b, blocks[s], CLEAR)){ return Infinity; } }
      for(s = 0; s < badges.length; s++){
        if(toSeg(badges[s], a, b) < 18){ if(!soft){ return Infinity; } under++; }
      }
    }
    for(k = 0; k < n; k++){
      a = pts[k]; b = pts[k + 1];
      for(s = 0; s < blocks.length; s++){
        var r = blocks[s];
        if(near(a, b, {x:r.x0, y:r.y0}, {x:r.x1, y:r.y1}) < clear){
          clear = Math.min(clear, fromBox(a, b, r)); }
      }
      for(s = 0; s < placed.length; s++){
        var c = placed[s][0], d = placed[s][1];
        if(near(a, b, c, d) >= clear){ continue; }
        if(crosses(a, b, c, d)){
          if(angle(a, b, c, d) < Math.PI / 6){ return Infinity; }
          cross++;
        } else {
          var gap = apart(a, b, c, d);
          if(gap < GAP){ return Infinity; }
          clear = Math.min(clear, gap);
        }
      }
    }
    return shape.low + 60 + 60 * cross + 200 * under - 2 * Math.min(clear, 20) - .25 * clear;
  }
  function centres(P0, P1){
    // The last choice: from the centre of one box to the centre of the other,
    // with horizontal and vertical lines only. The boxes overlap on one axis:
    // a straight line in the overlap. Otherwise: one bend.
    var c0 = {x:(P0.x0 + P0.x1) / 2, y:(P0.y0 + P0.y1) / 2};
    var c1 = {x:(P1.x0 + P1.x1) / 2, y:(P1.y0 + P1.y1) / 2};
    var lo = Math.max(P0.x0, P1.x0), hi = Math.min(P0.x1, P1.x1);
    if(lo < hi){
      var x = (lo + hi) / 2, down = c0.y < c1.y;
      return [{x:x, y:down ? P0.y1 : P0.y0}, {x:x, y:down ? P1.y0 : P1.y1}];
    }
    lo = Math.max(P0.y0, P1.y0); hi = Math.min(P0.y1, P1.y1);
    if(lo < hi){
      var y = (lo + hi) / 2, right = c0.x < c1.x;
      return [{x:right ? P0.x1 : P0.x0, y:y}, {x:right ? P1.x0 : P1.x1, y:y}];
    }
    return [{x:c0.x, y:c0.y < c1.y ? P0.y1 : P0.y0}, {x:c0.x, y:c1.y},
      {x:c0.x < c1.x ? P1.x0 : P1.x1, y:c1.y}];
  }
  function lineFor(g, placed, badges){
    var P0 = g.a.box, P1 = g.b.box;
    var blocks = BLOCKS.concat(Object.keys(HOME).filter(function(h){
      return HOME[h] !== g.a && HOME[h] !== g.b; }).map(function(h){ return HOME[h].box; }));
    // The cost without the distances is a lower bound: the search stops at
    // the first shape whose bound is higher than the best cost.
    var ranked = shapesFor(P0, P1).map(function(pts){
      var total = 0, n = pts.length - 1;
      for(var k = 0; k < n; k++){ total += len(pts[k], pts[k + 1]); }
      return {pts:pts, low:total + 50 * (n - 1) - 60
        + .06 * (offCentre(pts[0], P0) + offCentre(pts[n], P1))};
    }).sort(function(x, y){ return x.low - y.low; });
    var best = null, bestCost = Infinity;
    function search(others, marks, soft){
      for(var k = 0; k < ranked.length && ranked[k].low < bestCost; k++){
        var c = cost(ranked[k], P0, P1, blocks, others, marks, soft);
        if(c < bestCost){ bestCost = c; best = ranked[k].pts; }
      }
    }
    // When no shape keeps away from the badges, a line can go under a badge.
    search(placed, badges);
    if(!best){ search(placed, badges, true); }
    if(!best){ search([], []); }
    return best || centres(P0, P1);
  }
  function badgeAt(pts, taken, segs, labels){
    // On the longest part of the line, away from other badges, cards and lines,
    // and if possible away from the route labels of the layer.
    var k0 = 0, k, tries = [.5, .4, .6, .3, .7, .2, .8], free = [];
    for(k = 1; k + 1 < pts.length; k++){
      if(len(pts[k], pts[k + 1]) > len(pts[k0], pts[k0 + 1])){ k0 = k; }
    }
    var a = pts[k0], b = pts[k0 + 1];
    for(k = 0; k < tries.length; k++){
      var c = {x:a.x + (b.x - a.x) * tries[k], y:a.y + (b.y - a.y) * tries[k]};
      if(taken.every(function(t){ return len(t, c) >= 30; })
        && Object.keys(CARD).every(function(id){ return !hits(c, c, grow(CARD[id].box, 16), 0); })
        && segs.every(function(s){ return toSeg(c, s[0], s[1]) >= 16; })){ free.push(c); }
    }
    return free.filter(function(c){
      return labels.every(function(r){ return !hits(c, c, grow(r, 13), 0); }); })[0]
      || free[0] || {x:(a.x + b.x) / 2, y:(a.y + b.y) / 2};
  }
  function geometry(I){
    // Larger groups first: they get the best space. A later line keeps away
    // from the lines and the badges that are on the map before it.
    if(I.geo){ return I.geo; }
    var placed = [], geo = {}, taken = [], labels = [];
    I.list.forEach(function(i){
      var hit = LABELS[i] && LABELS[i].querySelector('.flowlbl__hit');
      if(hit){ labels.push(rectOf(hit)); }
    });
    I.lines.forEach(function(g){
      var pts = lineFor(g, placed, taken), badge = badgeAt(pts, taken, placed, labels);
      for(var k = 0; k + 1 < pts.length; k++){ placed.push([pts[k], pts[k + 1]]); }
      taken.push(badge);
      geo[g.key] = {pts:pts, badge:badge};
    });
    I.geo = geo;
    return geo;
  }

  // ---- the drawing ----------------------------------------------------------------
  // The lines go under the routes and the cards. The badges go over the cards
  // and under the route labels, so a label stays readable.
  var LINES = el('g', {'class':'fg-lines'}), BADGES = el('g', {'class':'fg-badges'});
  var flowLayers = all(':scope > g[data-layer="flow"]', view);
  var labelLayer = flowLayers.filter(function(g){ return g.querySelector('.flowlbl'); })[0];
  view.insertBefore(LINES, flowLayers[0] || null);
  view.insertBefore(BADGES, labelLayer || null);
  function f1(v){ return (Math.round(v * 10) / 10).toFixed(1); }
  function unit(a, b){ var l = len(a, b) || 1; return {x:(b.x - a.x) / l, y:(b.y - a.y) / l}; }
  function arrow(tip, from, w){
    // An arrowhead with its point on the edge of the place. It is wider than the line.
    var u = unit(from, tip), h = Math.max(6.2, w / 2 + 2), l = Math.max(12.4, h * 1.9);
    var bx = tip.x - u.x * l, by = tip.y - u.y * l;
    return {d:'M ' + f1(tip.x) + ' ' + f1(tip.y) + ' L ' + f1(bx - u.y * h) + ' '
      + f1(by + u.x * h) + ' L ' + f1(bx + u.y * h) + ' ' + f1(by - u.x * h) + ' Z',
      back:{x:tip.x - u.x * (l - 1.5), y:tip.y - u.y * (l - 1.5)}};
  }
  function pathOf(pts){
    var d = 'M ' + f1(pts[0].x) + ' ' + f1(pts[0].y), last = pts[pts.length - 1];
    for(var k = 1; k + 1 < pts.length; k++){
      var p = pts[k], u = unit(pts[k - 1], p), v = unit(p, pts[k + 1]);
      var r = Math.min(8, len(pts[k - 1], p) / 2, len(p, pts[k + 1]) / 2);
      d += ' L ' + f1(p.x - u.x * r) + ' ' + f1(p.y - u.y * r) + ' Q ' + f1(p.x) + ' ' + f1(p.y)
        + ' ' + f1(p.x + v.x * r) + ' ' + f1(p.y + v.y * r);
    }
    return d + ' L ' + f1(last.x) + ' ' + f1(last.y);
  }
  function draw(L){
    LINES.textContent = ''; BADGES.textContent = '';
    var I = info(L);
    if(!I.on){ return; }
    var geo = geometry(I);
    I.lines.forEach(function(g){
      var pts = geo[g.key].pts.slice(), n = g.edges.length, q = pts.length - 1;
      var w = Math.min(8, 1.1 * (n + 1)), end = arrow(pts[q], pts[q - 1], w), heads = [end.d];
      pts[q] = end.back;
      if(g.two){ var start = arrow(pts[0], pts[1], w); heads.push(start.d); pts[0] = start.back; }
      var group = el('g', {'class':'fg-group', 'data-fg':g.key, style:'--w:' + f1(w)});
      group.appendChild(el('title', {}, g.name + ': ' + plural(n, 'flow')));
      group.appendChild(el('path', {'class':'fg-hit', d:pathOf(geo[g.key].pts)}));
      group.appendChild(el('path', {'class':'fg-line', d:pathOf(pts)}));
      heads.forEach(function(d){ group.appendChild(el('path', {'class':'fg-arrow', d:d})); });
      LINES.appendChild(group);
      var c = geo[g.key].badge, r = n > 99 ? 15 : 12.4, cx = f1(c.x), cy = f1(c.y);
      var badge = el('g', {'class':'fg-badge', 'data-fg':g.key, role:'button', tabindex:'0',
        'aria-label':'Show the routes of the group ' + g.say + '. ' + plural(n, 'flow') + '.'});
      badge.appendChild(el('circle', {'class':'fg-badge__ring', cx:cx, cy:cy, r:r + 4.5}));
      badge.appendChild(el('circle', {'class':'fg-badge__c', cx:cx, cy:cy, r:r}));
      badge.appendChild(el('text', {x:cx, y:cy}, String(n)));
      BADGES.appendChild(badge);
    });
    bindMarks();
  }

  // ---- the state ------------------------------------------------------------------
  var S = {layer:null, open:'', routes:{}, hover:'', focus:null};
  function active(){
    var L = A.state.layer, m = P.mode ? P.mode() : 'understand';
    return info(L).on && !S.routes[L] && (m === 'understand' || m === 'review')
      && !A.state.focus && !A.state.journey && A.state.edge < 0;
  }
  function groupOf(L, key){
    return info(L).groups.filter(function(g){ return g.key === key; })[0] || null; }
  function openGroup(){ return S.layer === A.state.layer ? groupOf(S.layer, S.open) : null; }
  function shownEdges(I, g){
    // The routes that the map draws: the open group, or the flows inside one region.
    return g ? g.edges : flat(I.groups.filter(function(x){ return x.inside; })
      .map(function(x){ return x.edges; }));
  }
  function apply(){
    var L = A.state.layer;
    if(L !== S.layer){ S.layer = L; S.open = ''; S.hover = ''; draw(L); }
    var on = active(), I = info(L), g = on ? openGroup() : null, keep = {}, ends = {}, inL = {};
    I.list.forEach(function(i){ inL[i] = true; });
    shownEdges(I, g).forEach(function(i){ keep[i] = true; });
    (g ? g.edges : []).forEach(function(i){
      ends[A.edges[i].from] = true; ends[A.edges[i].to] = true; });
    ROUTES.forEach(function(p){
      var i = +p.dataset.edge, hide = on && !!inL[i] && !keep[i];
      p.classList.toggle('fg-hide', hide);
      if(LABELS[i]){ LABELS[i].classList.toggle('fg-hide', hide); }
    });
    Object.keys(CARD).forEach(function(id){
      CARD[id].node.classList.toggle('fg-out', !!g && !ends[id]); });
    svg.classList.toggle('fg-on', on);
    svg.classList.toggle('fg-quiet', !!g);
    svg.classList.toggle('fg-peek', on && !!S.hover);
    all('[data-fg]', view).forEach(function(n){
      n.classList.toggle('open', !!g && n.dataset.fg === g.key);
      n.classList.toggle('hover', on && n.dataset.fg === S.hover);
    });
  }
  function refresh(){
    if(P.renderRead){ P.renderRead(); }
    if(P.syncFrame){ P.syncFrame(); }
  }
  function revealLines(){
    // A new layer draws its group lines one after the other, in 600 ms at most.
    if(reduced() || !svg.classList.contains('fg-on')){ return; }
    var groups = all('.fg-group', LINES);
    var stagger = groups.length > 1 ? Math.min(60, 300 / (groups.length - 1)) : 0;
    groups.forEach(function(group, k){
      var badge = BADGES.querySelector('[data-fg="' + group.dataset.fg + '"]');
      [group, badge].forEach(function(n, m){
        if(n && n.animate){ n.animate([{opacity:0}, {opacity:1}], {duration:m ? 160 : 300,
          delay:k * stagger + (m ? 140 : 0), easing:'ease-out', fill:'backwards'}); }
      });
    });
  }
  function open(key, quiet){
    if(A.state.focus || A.state.journey){ A.clear(); }
    S.routes[A.state.layer] = false;
    S.open = S.open === key ? '' : key;
    S.hover = '';
    apply();
    var g = openGroup();
    // The cards fade in 160 ms, then the routes of the group draw in 240 ms.
    if(g && !quiet && A.drawLines && !reduced()){
      A.drawLines(g.edges, {each:240, delay:160, labels:true}); }
    refresh();
  }
  function close(){ if(S.open){ S.open = ''; apply(); refresh(); } }
  function showAll(on){
    S.routes[A.state.layer] = !!on; S.open = '';
    apply(); refresh();
    if(!on){ revealLines(); }
  }
  function hover(key){ if(S.hover !== key){ S.hover = key; apply(); } }

  // ---- the map: a group line or its badge opens the group --------------------------
  function bindMarks(){
    all('[data-fg]', view).forEach(function(n){
      var key = n.dataset.fg;
      n.addEventListener('click', function(e){ e.stopPropagation(); open(key); });
      n.addEventListener('mouseenter', function(){ hover(key); });
      n.addEventListener('mouseleave', function(){ hover(''); });
      if(!n.classList.contains('fg-badge')){ return; }
      n.addEventListener('focus', function(){ hover(key); });
      n.addEventListener('blur', function(){ hover(''); });
      n.addEventListener('keydown', function(e){
        if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); open(key); } });
    });
  }
  // A click on the empty map closes the group. The first click only clears a selection.
  var hadFocus = false;
  svg.addEventListener('click', function(){ hadFocus = !!A.state.focus; }, true);
  svg.addEventListener('click', function(e){
    if(hadFocus || !S.open || e.target.closest('.node, .flow, .flowlbl, [data-fg]')){ return; }
    close();
  });
  function busy(t){
    // Typing in a field, an open menu, or an open sheet keeps its own Escape.
    var more = document.getElementById('theme-menu');
    return /^(INPUT|SELECT|TEXTAREA)$/.test((t && t.tagName) || '') || !!(t && t.isContentEditable)
      || !!(more && more.open) || ['keys', 'present', 'submap'].some(function(id){
        var n = document.getElementById(id); return n && !n.hidden; });
  }
  // Escape closes the open group before it closes the panel.
  document.addEventListener('keydown', function(e){
    if(e.key !== 'Escape' || e.altKey || e.ctrlKey || e.metaKey || !S.open || !active()
      || busy(e.target)){ return; }
    e.preventDefault(); e.stopImmediatePropagation();
    close();
  }, true);
  ['systemap:mode', 'systemap:select', 'systemap:clear', 'systemap:step',
    'systemap:workspace'].forEach(function(name){ svg.addEventListener(name, apply); });
  svg.addEventListener('systemap:layer', function(){ apply(); revealLines(); });

  // ---- the Read panel ---------------------------------------------------------------
  function evidenceText(list){
    var words = {observed:'with a recorded source review'};
    var b = bucket(list, function(i){ return A.edges[i].evidence; });
    if(b.order.length === 1){ return 'all ' + (words[b.order[0]] || b.order[0]); }
    return b.order.map(function(v){ return b.by[v].length + ' ' + (words[v] || v); }).join(' · ');
  }
  function summary(g){
    var parts = g.inside ? g.parts : [g.fwd.length + ' to ' + g.b.label]
      .concat(g.back.length ? [g.back.length + ' to ' + g.a.label] : []);
    return parts.join(' · ') + ' · ' + evidenceText(g.edges);
  }
  function artifacts(g){
    return g.inside ? g.parts.join(' · ')
      : g.edges.map(function(i){ return A.edges[i].art; }).join(' · ');
  }
  function openCard(g){
    return '<section class="fg-open" aria-label="Open group">'
      + '<button type="button" class="fg-open__head" data-fg-close aria-pressed="true" '
      + 'title="Close the group"><b>' + g.edges.length + '</b><span class="fg-open__name">'
      + esc(g.name) + '</span></button>'
      + '<ul class="fg-open__flows">' + g.edges.map(function(i){
        var e = A.edges[i];
        return '<li><button type="button" class="fg-flow" data-fg-edge="' + i + '"><span>'
          + esc(e.art) + '</span><small>' + esc(e.from) + ' → ' + esc(e.to)
          + '</small></button></li>';
      }).join('') + '</ul><p class="fg-open__sum">' + esc(summary(g)) + '</p></section>';
  }
  function rows(list, title){
    if(!list.length){ return ''; }
    return '<section class="lay" aria-label="' + esc(title.toLowerCase())
      + '"><div class="seq-row"><h3 class="seq-kicker">' + esc(title)
      + '</h3><span class="seq-count">' + list.length + '</span></div><ul class="fg-rows">'
      + list.map(function(g){
        return '<li><button type="button" class="fg-row" data-fg-row="' + esc(g.key)
          + '" aria-pressed="false"><b>' + g.edges.length + '</b><span class="fg-row__name">'
          + esc(g.name) + '</span><span class="fg-row__arts">' + esc(artifacts(g))
          + '</span></button></li>';
      }).join('') + '</ul></section>';
  }
  function reader(L){
    var I = info(L);
    if(!I.on || (P.mode && P.mode() !== 'understand')){ return null; }
    var routes = !!S.routes[L], g = !routes && S.layer === L ? groupOf(L, S.open) : null;
    var name = L === 'all' ? 'All layers' : String(LAY[L] ? LAY[L].label : L);
    var kind = L === 'all' ? 'flows' : name.toLowerCase().replace(/( flow)?$/, ' flows');
    var text = routes ? 'The map shows each of the ' + plural(I.list.length, 'flow')
      + ' as a route. Select a group to show only its routes.'
      : 'One grey line shows all ' + kind + ' between two regions. The number '
      + 'is the quantity of flows. Select a group to show its routes.';
    var h = '<section class="read__section lay fg-read" aria-label="' + esc(name.toLowerCase())
      + ' groups"><div class="seq-row"><p class="seq-kicker">LAYER</p><span class="seq-count">'
      + plural(I.list.length, 'flow') + ' · ' + plural(I.groups.length, 'group')
      + '</span></div><div class="seq-head"><h2 class="seq-title">' + esc(name)
      + '</h2></div><p class="lay-text">' + esc(text) + '</p>' + (g ? openCard(g) : '')
      + rows(I.groups.filter(function(x){ return x !== g; }), g ? 'OTHER GROUPS' : 'GROUPS')
      + '<div class="fg-read__foot"><p class="seq-note">Each flow is in one group only.</p>'
      + '<button type="button" class="fg-read__all" data-fg-all aria-pressed="' + routes + '">'
      + (routes ? 'Show groups' : 'Show all routes') + '</button></div></section>';
    return {html:h, bind:bind};
  }
  function bind(root){
    function on(sel, type, fn){ all(sel, root).forEach(function(b){
      b.addEventListener(type, function(){ fn(b); }); }); }
    function unpeek(){ if(A.unpeek){ A.unpeek(); } else { A.peek(-1); } }
    function keep(attr, value){ S.focus = {attr:attr, value:value}; }
    on('[data-fg-row]', 'click', function(b){
      keep('data-fg-row', b.dataset.fgRow); open(b.dataset.fgRow); });
    on('[data-fg-row]', 'mouseenter', function(b){ if(active()){ hover(b.dataset.fgRow); } });
    on('[data-fg-row]', 'mouseleave', function(){ hover(''); });
    on('[data-fg-close]', 'click', function(){ keep('data-fg-row', S.open); close(); });
    on('[data-fg-all]', 'click', function(){
      keep('data-fg-all', ''); showAll(!S.routes[A.state.layer]); });
    on('[data-fg-edge]', 'mouseenter', function(b){ A.peek(+b.dataset.fgEdge); });
    on('[data-fg-edge]', 'focus', function(b){ A.peek(+b.dataset.fgEdge); });
    on('[data-fg-edge]', 'mouseleave', unpeek);
    on('[data-fg-edge]', 'blur', unpeek);
    on('[data-fg-edge]', 'click', function(b){ A.inspectFlow(+b.dataset.fgEdge); });
    var f = S.focus;
    S.focus = null;
    if(!f){ return; }
    var target = all('[' + f.attr + ']', root).filter(function(n){
      return f.attr !== 'data-fg-row' || n.getAttribute(f.attr) === f.value; })[0]
      || root.querySelector('[data-fg-close]');
    if(target){ target.focus({preventScroll:true}); }
  }
  P.readers.push(reader);

  // ---- the legend and the readout --------------------------------------------------
  function swatch(cls, style, label){
    return '<span class="lg"><i class="' + cls + '"' + (style ? ' style="' + style + '"' : '')
      + '></i>' + esc(label) + '</span>';
  }
  P.legendFor.push(function(){
    if(!active()){ return null; }
    var g = openGroup(), kinds = {}, dashed = false;
    shownEdges(info(A.state.layer), g).forEach(function(i){
      var e = A.edges[i];
      kinds[e.layer] = true;
      dashed = dashed || e.evidence === 'structural' || e.evidence === 'declared';
    });
    var h = swatch('lg__line fg-lg__group', '', 'Group of flows, with count');
    A.layers.forEach(function(l){
      if(kinds[l.id]){ h += swatch('lg__line', '--c:' + l.colour, l.label + ' route'); } });
    if(dashed){ h += swatch('lg__line lg__line--dash', '', 'No source review'); }
    return h + (g ? swatch('lg__card fg-lg__out', '', 'Not in the open group') : '');
  });
  P.readoutFor.push(function(){
    if(!active()){ return null; }
    var I = info(A.state.layer), g = openGroup();
    if(g){ return g.name + ' · ' + plural(g.edges.length, 'flow'); }
    var actors = A.layerIds(A.state.layer).filter(function(id){
      return A.detail[id] && A.detail[id].kind === 'actor'; }).length;
    return plural(I.list.length, 'flow') + ' · ' + plural(I.groups.length, 'group')
      + (actors ? ' · ' + plural(actors, 'actor') : '');
  });
  P.groups = {active:active, close:close, showAll:showAll,
    open:function(key){ if(key !== S.open){ open(key, true); } },
    groups:function(L){ return info(L === undefined ? A.state.layer : L).groups; },
    state:function(){ return {layer:S.layer, open:S.open, routes:!!S.routes[A.state.layer]}; }};
  apply();
  refresh();
  // The lines of the other layers are ready before the reader selects them.
  (window.requestIdleCallback || window.setTimeout)(function(){
    A.layers.concat([{id:'all'}]).forEach(function(l){
      if(info(l.id).on){ geometry(info(l.id)); } });
  });
})();
""".replace("__LIMIT__", str(LIMIT))
