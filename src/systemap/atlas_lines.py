"""The lines part of the atlas renderer: the lanes, the busy layer rule and the labels at rest.

`atlas_script` joins this part after the view part (`atlas_view`). The rules are the
section "Map view: the rules" of docs/design/atlas.md:

- Lanes. The router puts the paths that share a gap on one line. For each layer of a map,
  the script gives each such path its own lane, LANE map units apart, so that N flows show
  as N lines. Two segments share a line when they are on the same axis value (to a half
  unit) and their ranges overlap by more than 2 units. The lanes of a group are in the
  order of the flows, around the line of the router (`lanesOf`).
- The end of a line. The drawn line stops END units before the target, where the
  arrowhead starts (`laned`).
- Busy layers. With many flows, the lines go light: the alpha of a line at rest is
  1.25 - n / 56, from 0.3 to 1, and the alpha of the dot and the arrowhead is
  1.25 - n / 160, from 0.8 to 1. At 0.8 the dot and the arrowhead keep a contrast of 3.0 or
  more on the map (tests/test_atlas_contrast.py). With more than DENSE flows, no label shows
  at rest.
- Labels at rest. A label shows at rest only when it is on its line, on no card, on no name
  of a region or of a container, on no edge of a surface or of a region, on no other label,
  in the box of the map, and no other line of the layer goes through it. The parts of its
  own line before and after its part do not go through it (`ownCrossed`): thus a label is
  not on a corner of its line. The halo of a label has the color of the ground under it,
  the surface of a container or the ground of the map (`groundOf`). An artifact of more than
  LABEL_MAX characters is cut at the end of a word, with "..." after it (`shortText`). A
  label of a sequence that has no place on one ground can cross such an edge, so that it
  still shows (`m._walls0`). A horizontal part of the line comes first, then the longest
  part. The label has a constant size on the screen (`labelPx`). The short lines get their
  places first. A line with no such place has no label at rest (`seatsOf`).
- Sequences. In the layer of a sequence (`atlas_sequences`), the label of each line has the
  numbers of its steps before the artifact, and the busy layer rule does not apply. A label
  with no free place on its line goes beside its own line and touches it, with no other
  line in it or near it (`seqSeat`). Thus a label is not on the line of a different step,
  and it does not cover its own line. A label with no such place does not show at rest, as
  in the design study. It shows only while its step is the current step or an earlier
  step (`hide`), at its line: on it, or beside it and touching it (`stepSeat`).
- The places on a part of a line. The page tries the middle of the part first, then
  places farther from the middle, in steps of a twentieth of the part (`SEAT_T`).

The script calculates the lanes one time for each map and layer, and the places of the
labels one time for each map, layer and quarter step of zoom, in the full drawing at rest.
The place of a quarter step uses the smallest zoom of the step. A label at rest is thus
never larger on the screen than the box that its place keeps free. While the camera
moves, the labels keep the places of the last calculation, as in the design study.
"""

from __future__ import annotations

LINES = r"""
// ---- the lanes, the busy layer rule and the labels at rest ----------------------------
var LANE = 4.5, END = 5, DENSE = 48, LABEL_MAX = 36;
// The lines of map m in layer `id`: for each flow index of the layer, `q` (the laned
// points), `d` (the points to draw, which stop END units before the target) and `len`. Also
// the count `n` of the lines, `dense`, `rest` (the alpha of a line at rest) and `ends` (the
// alpha of the dot and the arrowhead).
function linesOf(m, id) {
  var memo = m._ln || (m._ln = Object.create(null));
  if (memo[id]) return memo[id];
  var fl = layerFlags(m, id).flow, list = [];
  m.flows.forEach(function (f, i) {
    if (fl[i] && f.p.length > 1) list.push({f: f, q: f.p.map(function (p) { return [p[0], p[1]]; })});
  });
  lanesOf(list);
  var seq = isSeqLayer(id), out = {list: list, n: list.length, dense: !seq && list.length > DENSE, seq: seq, seats: null};
  out.rest = clamp(1.25 - list.length / 56, 0.3, 1);
  out.ends = clamp(1.25 - list.length / 160, 0.8, 1);
  list.forEach(function (e) { laned(e); seqLabel(m, id, e); });
  memo[id] = out;
  return out;
}
// Give each path that shares a line with a different path its own lane.
function lanesOf(list) {
  [0, 1].forEach(function (ax) {
    var segs = [];
    list.forEach(function (e, n) {
      for (var i = 0; i + 1 < e.q.length; i++) {
        var a = e.q[i], b = e.q[i + 1];
        if (Math.abs(a[ax] - b[ax]) < 0.01 && Math.abs(a[1 - ax] - b[1 - ax]) > 1) {
          segs.push({e: e, n: n, i: i, c: Math.round(a[ax] * 2) / 2, lo: Math.min(a[1 - ax], b[1 - ax]), hi: Math.max(a[1 - ax], b[1 - ax])});
        }
      }
    });
    segs.sort(function (a, b) { return a.c - b.c || a.lo - b.lo; });
    var k = 0;
    while (k < segs.length) {
      var group = [segs[k]], hi = segs[k].hi, j = k + 1;
      while (j < segs.length && segs[j].c === segs[k].c && segs[j].lo < hi - 2) { group.push(segs[j]); hi = Math.max(hi, segs[j].hi); j++; }
      if (group.length > 1) {
        group.sort(function (a, b) { return a.n - b.n; });
        group.forEach(function (s, n) {
          var d = (n - (group.length - 1) / 2) * LANE;
          s.e.q[s.i][ax] += d; s.e.q[s.i + 1][ax] += d;
        });
      }
      k = j;
    }
  });
}
function segLen(q, i) { return Math.abs(q[i + 1][0] - q[i][0]) + Math.abs(q[i + 1][1] - q[i][1]); }
// The points to draw and the length of a line. The last point moves END units back.
function laned(e) {
  var q = e.q, n = q.length, z = q[n - 1], y = q[n - 2], l = Math.hypot(z[0] - y[0], z[1] - y[1]) || 1, cut = Math.min(END, l / 2);
  e.d = q.slice(0, n - 1).concat([[z[0] - (z[0] - y[0]) / l * cut, z[1] - (z[1] - y[1]) / l * cut]]);
  e.len = 0;
  for (var i = 0; i + 1 < n; i++) e.len += segLen(q, i);
  e.s = shortText(e.f.a);
}
// A long artifact is cut at the end of a word, with "..." after it.
function shortText(a) {
  if (a.length <= LABEL_MAX) return a;
  var cut = a.slice(0, LABEL_MAX - 2), end = cut.lastIndexOf(' ');
  return (end > LABEL_MAX / 2 ? cut.slice(0, end) : cut).replace(/[ ,;]+$/, '') + '...';
}
// The size of a label on the screen for the map scale a: 11 px, smaller when the map is
// small (15 units of the map).
function labelPx(a) { return Math.min(11, 15 * a); }
// The box b of the map in the coordinates of the screen, for the tests.
function labelBox(b, a, ox, oy) { return [ox + a * b[0], oy + a * b[1], ox + a * b[2], oy + a * b[3]]; }
function over(a, b) { return a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1]; }
// The boxes that a label must not cover: the cards, the names of the regions and the names
// of the containers, in the coordinates of the map.
function walls(m) {
  if (m._walls) return m._walls;
  var out = m.cards.map(function (c) { return [c.b[0] - 3, c.b[1] - 3, c.b[0] + c.b[2] + 3, c.b[1] + c.b[3] + 3]; });
  m.regions.forEach(function (r) { out.push([r.b[0], r.b[1] + 6, r.b[0] + 40 + r.n.length * 6.6, r.b[1] + 28]); });
  m.boxes.forEach(function (b) { out.push([b.b[0] + 12, b.b[1] + 16, b.b[0] + 230, b.b[1] + 38]); });
  // The four sides of the map: a label at rest stays in the map, so that the fit and the
  // phone view, which use the frame of the map, show the full label.
  var w = m.size[0], h = m.size[1], far = 1e6;
  out.push([-far, -far, 0, far], [-far, -far, far, 0], [w, -far, far, far], [-far, h, far, far]);
  m._walls0 = out.slice();
  // The edges of each surface and of each region tint: a label at rest is fully on one
  // ground, so that its halo has the color of the ground under it (`groundOf`).
  m.boxes.forEach(function (b) { if (boxKind(m, b) === 'box') edges(out, b.b, 0); });
  m.regions.forEach(function (r) { edges(out, r.b, 3); });
  m._walls = out;
  return out;
}
// Four thin boxes on the edges of the box b, `inset` units inside it.
function edges(out, b, inset) {
  var x0 = b[0] + inset, y0 = b[1] + inset, x1 = b[0] + b[2] - inset, y1 = b[1] + b[3] - inset, e = 0.5;
  out.push([x0 - e, y0, x0 + e, y1], [x1 - e, y0, x1 + e, y1], [x0, y0 - e, x1, y0 + e], [x0, y1 - e, x1, y1 + e]);
}
// The color of the ground under the label box b of map m: the surface of a container, or
// the ground of the map.
function groundOf(m, b) {
  var x = (b[0] + b[2]) / 2, y = (b[1] + b[3]) / 2;
  return m.boxes.some(function (o) { return boxKind(m, o) === 'box' && x > o.b[0] && x < o.b[0] + o.b[2] && y > o.b[1] && y < o.b[1] + o.b[3]; }) ? C['--surface'] : C['--map'];
}
// Tell if a part of the line q, other than part i, goes through the box b. A label on part
// i must not have the next part or the part before it in its box (a corner).
function ownCrossed(b, q, i) {
  for (var j = 0; j + 1 < q.length; j++) {
    if (j === i) continue;
    if (Math.min(q[j][0], q[j + 1][0]) < b[2] && Math.max(q[j][0], q[j + 1][0]) > b[0] &&
      Math.min(q[j][1], q[j + 1][1]) < b[3] && Math.max(q[j][1], q[j + 1][1]) > b[1]) return true;
  }
  return false;
}
// Tell if a line of `list`, except `skip`, goes through the box b.
function crossed(b, list, skip) {
  for (var n = 0; n < list.length; n++) {
    if (list[n] === skip) continue;
    var q = list[n].q;
    for (var i = 0; i + 1 < q.length; i++) {
      if (Math.min(q[i][0], q[i + 1][0]) <= b[2] && Math.max(q[i][0], q[i + 1][0]) >= b[0] &&
        Math.min(q[i][1], q[i + 1][1]) <= b[3] && Math.max(q[i][1], q[i + 1][1]) >= b[1]) return true;
    }
  }
  return false;
}
// The places on a part of a line, as fractions of the part: the places of the study first,
// then each twentieth of the part, the nearest to the middle first.
var SEAT_T = (function () {
  var out = [0.5, 0.35, 0.65, 0.22, 0.78, 0.12, 0.88], more = [];
  for (var n = 1; n < 20; n++) if (out.indexOf(n / 20) < 0) more.push(n / 20);
  more.sort(function (u, v) { return Math.abs(u - 0.5) - Math.abs(v - 0.5); });
  return out.concat(more);
})();
// A place for the label of line e at the font size fs (in units of the map), or null.
function seat(e, fs, wall, taken, list) {
  var w = unitWidth(e.s, 500) * fs + 8, hh = fs * 1.35, q = e.q, best = null;
  function flat(i) { return Math.abs(q[i][1] - q[i + 1][1]) < 0.01; }
  var order = q.slice(0, -1).map(function (p, i) { return i; }).sort(function (a, b) { return (flat(b) - flat(a)) || segLen(q, b) - segLen(q, a); });
  for (var o = 0; o < order.length && !best; o++) {
    var i = order[o], a = q[i], b = q[i + 1];
    if (segLen(q, i) < (flat(i) ? w : hh) + 18) continue;
    SEAT_T.forEach(function (t) {
      if (best) return;
      var cx = a[0] + (b[0] - a[0]) * t, cy = a[1] + (b[1] - a[1]) * t, box = [cx - w / 2, cy - hh / 2, cx + w / 2, cy + hh / 2];
      if (wall.some(function (c) { return over(box, c); }) || taken.some(function (c) { return over(box, c); })) return;
      if (!crossed(box, list, e) && !ownCrossed(box, q, i)) best = {x: cx, y: cy, box: box};
    });
  }
  return best;
}
// A place beside line e for its label: the box touches the line, at a right angle to a part
// of the line. Thus the label never covers its line, and the reader sees which line it
// names. A horizontal part comes first, then the longest part. The box is on no box of
// `wall` and of `taken`. With `strict`, no other line of `list` is nearer to the box than
// its own line and NEAR_GAP units. Else no other line is within half a label height and
// NEAR_GAP units of the box. Null when no such place is free.
var NEAR_GAP = 3, NEAR_STEPS = 0;
function near(e, fs, wall, taken, list, strict) {
  var w = unitWidth(e.s, 500) * fs + 8, hh = fs * 1.35, q = e.q, parts = [];
  for (var i = 0; i + 1 < q.length; i++) {
    var flat = Math.abs(q[i][1] - q[i + 1][1]) < 0.01, l = segLen(q, i);
    if (l >= (flat ? w / 2 : hh)) parts.push({i: i, flat: flat, l: l});
  }
  parts.sort(function (u, v) { return (v.flat - u.flat) || v.l - u.l; });
  for (var k = 0; k <= NEAR_STEPS; k++) {
    for (var p = 0; p < parts.length; p++) {
      var at = nearPart(q, parts[p], k, w, hh, wall, taken, list, e, strict);
      if (at) return at;
    }
  }
  return null;
}
function nearPart(q, part, k, w, hh, wall, taken, list, e, strict) {
  var a = q[part.i], b = q[part.i + 1], d = (part.flat ? hh / 2 : w / 2) + 2 + k * hh, ts = [0.5, 0.35, 0.65, 0.22, 0.78];
  for (var n = 0; n < ts.length; n++) {
    var cx = a[0] + (b[0] - a[0]) * ts[n], cy = a[1] + (b[1] - a[1]) * ts[n];
    for (var side = -1; side <= 1; side += 2) {
      var x = part.flat ? cx : cx + side * d, y = part.flat ? cy + side * d : cy, box = [x - w / 2, y - hh / 2, x + w / 2, y + hh / 2];
      var g = (strict ? 2 + k * hh : hh / 2) + NEAR_GAP, wide = [box[0] - g, box[1] - g, box[2] + g, box[3] + g];
      if (wall.some(function (c) { return over(box, c); }) || taken.some(function (c) { return over(box, c); })) continue;
      if (!crossed(wide, list, e)) return {x: x, y: y, box: box};
    }
  }
  return null;
}
// The place of the label of a line of a sequence that has no free place on its line:
// beside its line with its own line the nearest (`near`, strict), then on its line with
// other lines through the label but with a free part of the line at each side (`seat`),
// then beside its line with no other line in or near the label. Null when no such place is
// free: then the label does not show at rest (`stepSeat`).
function seqSeat(e, fs, wall, taken, list) {
  return near(e, fs, wall, taken, list, true) || seat(e, fs, wall, taken, []) || near(e, fs, wall, taken, list, false);
}
// The place of a label of a sequence that shows only at its step and after it (`hide`): on
// its line or beside it and touching it, on no other label. A place on no card comes first.
// The last choice is the middle of the longest part of the line.
function stepSeat(e, fs, wall, taken, base) {
  var at = seat(e, fs, wall, taken, []) || near(e, fs, wall, taken, [], false) || seat(e, fs, base, taken, []) || near(e, fs, base, taken, [], false) || near(e, fs, [], taken, [], false);
  if (at) return at;
  var q = e.q, w = unitWidth(e.s, 500) * fs + 8, hh = fs * 1.35, best = 0;
  for (var i = 1; i + 1 < q.length; i++) if (segLen(q, i) > segLen(q, best)) best = i;
  var x = (q[best][0] + q[best + 1][0]) / 2, y = (q[best][1] + q[best + 1][1]) / 2;
  return {x: x, y: y, box: [x - w / 2, y - hh / 2, x + w / 2, y + hh / 2]};
}
// The places of the labels at rest of map m in layer `id` at the map scale a: a list of
// {e, x, y} in the coordinates of the map, and `fs`, the font size in units of the map.
// A busy layer has no labels at rest.
function seatsOf(m, id, a) {
  var L = linesOf(m, id);
  if (L.dense || !L.n) return null;
  var step = Math.floor(Math.log2(a) * 4), key = step + '|' + TEXTS;
  // While the camera moves, the labels keep their places: a new calculation costs more than
  // a frame. The full drawing at rest calculates the places of the new zoom.
  if (L.seats && (L.seats.key === key || !sharp)) return L.seats;
  // The tags of the marks come first: a label does not cover a tag (`tagsOf` in `atlas_marks`).
  var low = Math.pow(2, step / 4), fs = labelPx(low) / low, taken = tagsOf(m, id, a).boxes.slice(), wall = walls(m), out = [], later = [];
  L.list.slice().sort(function (u, v) { return u.len - v.len; }).forEach(function (e) {
    // A line of a sequence with no free place on the line: the label goes beside its own
    // line (`seqSeat`), or it shows only at its step (`stepSeat`).
    // A label of a sequence with no place on one ground can cross an edge of a surface or
    // of a region (`m._walls0`), so that it still shows at rest.
    var at = seat(e, fs, wall, taken, L.list) || (L.seq ? seqSeat(e, fs, wall, taken, L.list) || seqSeat(e, fs, m._walls0, taken, L.list) : null);
    if (!at) { if (L.seq) later.push(e); return; }
    taken.push(at.box); out.push({e: e, x: at.x, y: at.y, box: at.box});
  });
  later.forEach(function (e) {
    var at = stepSeat(e, fs, wall, taken, m._walls0);
    taken.push(at.box); out.push({e: e, x: at.x, y: at.y, box: at.box, hide: true});
  });
  L.seats = {key: key, list: out, fs: fs};
  return L.seats;
}
"""
