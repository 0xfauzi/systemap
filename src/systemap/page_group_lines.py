"""Flow groups: the route of each group line, and the work in small parts.

The search tries straight lines, and lines with one or two bends, between the
two places of a group. It selects the line with the lowest cost: the line keeps
away from the other places, from the lines of larger groups, and from their
badges. The search keeps the shapes for each pair of places, and uses only the
items near each segment. Thus the search is fast also on a large map. The work
for a layer goes in small parts, thus a part can go in the idle time of the
browser. The script is a part of the page_groups script, and it uses its names.
"""

SCRIPT = r"""
  // ---- the lines: straight, or with one or two bends, from edge to edge ------
  // The line goes through the space between the places, at the largest
  // distance from other places and from the lines of larger groups.
  // The viewBox does not change. A copy of its values is faster to read than the DOM.
  // The cost of a shape uses only the items at a distance of less than FAR.
  var VB = (function(b){ return {x:b.x, y:b.y, width:b.width, height:b.height}; })(
    svg.viewBox.baseVal), CLEAR = 6, GAP = 12, INSET = 14, FAR = 80;
  var BLOCKS = (META.headers || []).filter(function(h){ return h.kind === 'container'; })
    .map(function(h){ return rect(h.box[0], h.box[1], h.box[2], h.box[3]); });
  function len(p, q){ return Math.hypot(q.x - p.x, q.y - p.y); }
  var T0 = 0, T1 = 1;
  function edge(pk, qk){
    // False when the segment is fully outside one edge of the box. Else the
    // part of the segment inside the edges so far is from T0 to T1.
    if(pk === 0){ return !(qk <= 0); }
    var r = qk / pk;
    if(pk < 0){ if(r > T1){ return false; } T0 = Math.max(T0, r); }
    else { if(r < T0){ return false; } T1 = Math.min(T1, r); }
    return true;
  }
  function hits(p, q, b, pad){
    // True when the segment pq goes into the box b, grown by pad.
    var dx = q.x - p.x, dy = q.y - p.y;
    T0 = 0; T1 = 1;
    return edge(-dx, p.x - b.x0 + pad) && edge(dx, b.x1 + pad - p.x)
      && edge(-dy, p.y - b.y0 + pad) && edge(dy, b.y1 + pad - p.y) && T1 - T0 > 1e-6;
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
  function gapTo(a, b, x0, y0, x1, y1){
    // The gap between the box around the segment ab and the box around the
    // segment from (x0, y0) to (x1, y1): a fast lower bound of the distance.
    return Math.max(Math.min(x0, x1) - Math.max(a.x, b.x),
      Math.min(a.x, b.x) - Math.max(x0, x1), Math.min(y0, y1) - Math.max(a.y, b.y),
      Math.min(a.y, b.y) - Math.max(y0, y1));
  }
  function near(a, b, c, d){ return gapTo(a, b, c.x, c.y, d.x, d.y); }
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
  function shapesFor(P0, P1, keep){
    // Each shape goes to keep(pts), in a fixed order. A shape that keep()
    // returns is in the list.
    var out = [], a = along(P0, 8, 20), b = along(P1, 8, 20);
    function add(pts){ var shape = keep(pts); if(shape){ out.push(shape); } }
    var a2 = along(P0, 16, 10), b2 = along(P1, 16, 10);
    var above = P0.y1 <= P1.y0, below = P0.y0 >= P1.y1;
    var left = P0.x1 <= P1.x0, right = P0.x0 >= P1.x1;
    var ya = above ? P0.y1 : P0.y0, yb = above ? P1.y0 : P1.y1;
    var xa = left ? P0.x1 : P0.x0, xb = left ? P1.x0 : P1.x1;
    if(above || below){
      // Straight up or down, and with two bends through the space between.
      marks('x', Math.max(P0.x0, P1.x0) + INSET, Math.min(P0.x1, P1.x1) - INSET, 4, 40)
        .forEach(function(x){ add([{x:x, y:ya}, {x:x, y:yb}]); });
      marks('y', Math.min(ya, yb) + GAP, Math.max(ya, yb) - GAP, 6, 10).forEach(function(y){
        each2(a2.x, b2.x, function(x0, x1){
          if(Math.abs(x0 - x1) >= 16){
            add([{x:x0, y:ya}, {x:x0, y:y}, {x:x1, y:y}, {x:x1, y:yb}]); }
        });
      });
    }
    if(left || right){
      marks('y', Math.max(P0.y0, P1.y0) + INSET, Math.min(P0.y1, P1.y1) - INSET, 4, 40)
        .forEach(function(y){ add([{x:xa, y:y}, {x:xb, y:y}]); });
      marks('x', Math.min(xa, xb) + GAP, Math.max(xa, xb) - GAP, 6, 10).forEach(function(x){
        each2(a2.y, b2.y, function(y0, y1){
          if(Math.abs(y0 - y1) >= 16){
            add([{x:xa, y:y0}, {x:x, y:y0}, {x:x, y:y1}, {x:xb, y:y1}]); }
        });
      });
    }
    // One bend: out of the top or the bottom, into a side; or the opposite.
    each2(a.x, b.y, function(x, y){
      if((y < P0.y0 || y > P0.y1) && (x < P1.x0 || x > P1.x1)){
        add([{x:x, y:y < P0.y0 ? P0.y0 : P0.y1}, {x:x, y:y},
          {x:x < P1.x0 ? P1.x0 : P1.x1, y:y}]); }
    });
    each2(a.y, b.x, function(y, x){
      if((x < P0.x0 || x > P0.x1) && (y < P1.y0 || y > P1.y1)){
        add([{x:x < P0.x0 ? P0.x0 : P0.x1, y:y}, {x:x, y:y},
          {x:x, y:y < P1.y0 ? P1.y0 : P1.y1}]); }
    });
    // Every shape is horizontal and vertical lines only, as the flow routes are.
    return out;
  }
  function offCentre(p, B){
    var onSide = Math.abs(p.x - B.x0) < .5 || Math.abs(p.x - B.x1) < .5;
    return onSide ? Math.abs(p.y - (B.y0 + B.y1) / 2) : Math.abs(p.x - (B.x0 + B.x1) / 2);
  }
  function inView(p){
    return !(p.x < VB.x + 4 || p.x > VB.x + VB.width - 4 || p.y < VB.y + 4
      || p.y > VB.y + VB.height - 4); }
  function strips(items, boxFor, limit){
    // This function makes a filter for segments. The filter gives, in their
    // order, the items that can be at a distance of less than `limit` from a
    // segment. For a vertical segment, it compares only the x values. For a
    // horizontal segment, it compares only the y values. The filter keeps
    // the result for each value.
    var boxes = items.map(boxFor), byX = new Map(), byY = new Map();
    function pick(known, v, lo, hi){
      if(!known.has(v)){
        known.set(v, items.filter(function(_t, k){
          return !(Math.max(boxes[k][lo] - v, v - boxes[k][hi]) >= limit); }));
      }
      return known.get(v);
    }
    return function(a, b){
      if(a.x === b.x){ return pick(byX, a.x, 'x0', 'x1'); }
      return a.y === b.y ? pick(byY, a.y, 'y0', 'y1') : items;
    };
  }
  function boxOfBox(r){
    return {x0:Math.min(r.x0, r.x1), y0:Math.min(r.y0, r.y1), x1:Math.max(r.x0, r.x1),
      y1:Math.max(r.y0, r.y1)}; }
  function boxOfLine(s){
    return boxOfBox({x0:s[0].x, y0:s[0].y, x1:s[1].x, y1:s[1].y}); }
  function boxOfDot(m){ return {x0:m.x, y0:m.y, x1:m.x, y1:m.y}; }
  var NONE = strips([], boxOfDot, 0);
  // One empty list for each segment without a place near it.
  var NEAR_NONE = [];
  function closeTo(a, b, ends, near){
    // The places near the segment ab, or null when it goes into a place.
    if(hits(a, b, ends[0], 0) || hits(a, b, ends[1], 0)){ return null; }
    var close = NEAR_NONE, blocks = near(a, b);
    for(var s = 0; s < blocks.length; s++){
      // A place at FAR or more from the segment cannot touch it.
      var r = blocks[s];
      if(gapTo(a, b, r.x0, r.y0, r.x1, r.y1) >= FAR){ continue; }
      if(hits(a, b, r, CLEAR)){ return null; }
      close = close.concat([r]);
    }
    return close;
  }
  function fits(pts, ends, blocks, last){
    // The checks that do not change with the layer: the view box, the two
    // places and the other places. For each segment, the places near it; or
    // null when the shape goes out of the view box or into a place. Shapes
    // that come one after the other often have the same first segment:
    // `last` keeps the result of the last segment at each position.
    if(!pts.every(inView)){ return null; }
    var out = [];
    for(var k = 0; k + 1 < pts.length; k++){
      var a = pts[k], b = pts[k + 1], m = last[k];
      if(!m || m.a.x !== a.x || m.a.y !== a.y || m.b.x !== b.x || m.b.y !== b.y){
        m = last[k] = {a:a, b:b, close:closeTo(a, b, ends, blocks)};
      }
      if(m.close === null){ return null; }
      out.push(m.close);
    }
    return out;
  }
  var NO = {v:Infinity, under:0};
  function cost(shape, nearLines, nearBadges){
    // The shape fits. An item at FAR or more from a segment does not change the cost.
    // The cost `v` lets the line go under a badge; `under` counts the badges on the line.
    var pts = shape.pts, n = pts.length - 1, k, s, a, b, blocks, badges, placed;
    var under = 0, clear = FAR, cross = 0;
    for(k = 0; k < n; k++){
      a = pts[k]; b = pts[k + 1]; badges = nearBadges(a, b);
      for(s = 0; s < badges.length; s++){
        // A badge at 19 or more from the box around the segment is not near it.
        var m = badges[s];
        if(gapTo(a, b, m.x, m.y, m.x, m.y) >= 19){ continue; }
        if(toSeg(m, a, b) < 18){ under++; }
      }
    }
    for(k = 0; k < n; k++){
      a = pts[k]; b = pts[k + 1]; blocks = shape.close[k]; placed = nearLines(a, b);
      for(s = 0; s < blocks.length; s++){
        var r = blocks[s];
        if(gapTo(a, b, r.x0, r.y0, r.x1, r.y1) < clear){
          clear = Math.min(clear, fromBox(a, b, r)); }
      }
      for(s = 0; s < placed.length; s++){
        var c = placed[s][0], d = placed[s][1];
        if(near(a, b, c, d) >= clear){ continue; }
        if(crosses(a, b, c, d)){
          if(angle(a, b, c, d) < Math.PI / 6){ return NO; }
          cross++;
        } else {
          var gap = apart(a, b, c, d);
          if(gap < GAP){ return NO; }
          clear = Math.min(clear, gap);
        }
      }
    }
    return {v:shape.low + 60 + 60 * cross + 200 * under - 2 * Math.min(clear, 20) - .25 * clear,
      under:under};
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
  var SHAPES = table();
  function pairKey(g){
    // The key is the JSON text of the two IDs, in the order of the line.
    return JSON.stringify([g.a.id, g.b.id]); }
  function rankedFor(g){
    // The shapes that fit between the two places, by their lower bound, and
    // the box around the two places. The layers use the same shapes for the
    // same two places, in the same order.
    var P0 = g.a.box, P1 = g.b.box, key = pairKey(g);
    if(SHAPES[key]){ return SHAPES[key]; }
    // Each point of a shape is on the edge of P0 or P1, or between their
    // edges: in the box around the two places. A place at FAR or more from
    // this box is at FAR or more from each segment.
    var u = union(P0, P1), lo = {x:u.x0, y:u.y0}, hi = {x:u.x1, y:u.y1};
    var ends = [grow(P0, -1), grow(P1, -1)];
    var blocks = BLOCKS.concat(Object.keys(HOME).filter(function(h){
      return HOME[h] !== g.a && HOME[h] !== g.b; }).map(function(h){ return HOME[h].box; }))
      .filter(function(r){ return !(gapTo(lo, hi, r.x0, r.y0, r.x1, r.y1) >= FAR); });
    blocks = strips(blocks, boxOfBox, FAR);
    var last = [];
    // The sort is stable: the shapes with the same bound stay in their order.
    var ranked = shapesFor(P0, P1, function(pts){
      var close = fits(pts, ends, blocks, last), total = 0, n = pts.length - 1;
      if(!close){ return null; }
      for(var k = 0; k < n; k++){ total += len(pts[k], pts[k + 1]); }
      return {pts:pts, close:close, low:total + 50 * (n - 1) - 60
        + .06 * (offCentre(pts[0], P0) + offCentre(pts[n], P1))};
    }).sort(function(x, y){ return x.low - y.low; });
    SHAPES[key] = {ranked:ranked, lo:lo, hi:hi};
    return SHAPES[key];
  }
  function lineFor(g, placed, badges){
    // The cost without the distances is a lower bound: the search stops at
    // the first shape whose bound is higher than the best cost.
    var R = rankedFor(g), ranked = R.ranked, best = null, bestCost = Infinity;
    // The lines and the badges that can be near a segment of a shape.
    var lines = strips(placed.filter(function(s){
      return !(near(R.lo, R.hi, s[0], s[1]) >= FAR); }), boxOfLine, FAR);
    var dots = strips(badges.filter(function(m){
      return !(gapTo(R.lo, R.hi, m.x, m.y, m.x, m.y) >= 19); }), boxOfDot, 19);
    var known = [];
    function full(k){
      // The cost with the lines and the badges. The second search uses it again.
      return known[k] || (known[k] = cost(ranked[k], lines, dots));
    }
    function search(value){
      for(var k = 0; k < ranked.length && ranked[k].low < bestCost; k++){
        var c = value(k);
        if(c < bestCost){ bestCost = c; best = ranked[k].pts; }
      }
    }
    // When no shape keeps away from the badges, a line can go under a badge.
    search(function(k){ return full(k).under ? Infinity : full(k).v; });
    if(!best){ search(function(k){ return full(k).v; }); }
    if(!best){ search(function(k){ return cost(ranked[k], NONE, NONE).v; }); }
    return best || centres(g.a.box, g.b.box);
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
  function step(I){
    // One part of the work for the lines of a layer: the shapes for the
    // places of the next group, or the line of the next group. Larger groups
    // first: they get the best space. A later line keeps away from the lines
    // and the badges that are on the map before it. True when the work is done.
    var J = I.job;
    if(!J){
      J = I.job = {k:0, placed:[], geo:table(), taken:[], labels:[]};
      I.list.forEach(function(i){
        var hit = LABELS[i] && LABELS[i].querySelector('.flowlbl__hit');
        if(hit){ J.labels.push(rectOf(hit)); }
      });
    }
    var g = I.lines[J.k];
    if(g && !SHAPES[pairKey(g)]){ rankedFor(g); return false; }
    if(g){
      var pts = lineFor(g, J.placed, J.taken), badge = badgeAt(pts, J.taken, J.placed, J.labels);
      for(var k = 0; k + 1 < pts.length; k++){ J.placed.push([pts[k], pts[k + 1]]); }
      J.taken.push(badge);
      J.geo[g.key] = {pts:pts, badge:badge};
      J.k++;
    }
    if(J.k < I.lines.length){ return false; }
    I.geo = J.geo;
    return true;
  }
"""
