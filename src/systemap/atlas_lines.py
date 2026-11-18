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
  1.25 - n / 160, from 0.75 to 1. With more than DENSE flows, no label shows at rest.
- Labels at rest. A label shows at rest only when it is on its line, on no card, on no name
  of a region or of a container, on no other label, and no other line of the layer goes
  through it. A horizontal part of the line comes first, then the longest part. The label
  has a constant size on the screen (`labelPx`). The short lines get their places first.
  A line with no such place has no label at rest (`seatsOf`).
- Sequences. In the layer of a sequence (`atlas_sequences`), the label of each line has the
  numbers of its steps before the artifact, each line has a label, and the busy layer rule
  does not apply.

The script calculates the lanes one time for each map and layer, and the places of the
labels one time for each map, layer and quarter step of zoom, in the full drawing at rest.
The place of a quarter step uses the smallest zoom of the step. A label at rest is thus
never larger on the screen than the box that its place keeps free. While the camera
moves, the labels keep the places of the last calculation, as in the design study.
"""

from __future__ import annotations

LINES = r"""
// ---- the lanes, the busy layer rule and the labels at rest ----------------------------
var LANE = 4.5, END = 5, DENSE = 48, LABEL_MAX = 30;
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
  out.ends = clamp(1.25 - list.length / 160, 0.75, 1);
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
function shortText(a) { return a.length > LABEL_MAX ? a.slice(0, LABEL_MAX - 2).replace(/[ ,]+$/, '') + '...' : a; }
// The size of a label on the screen for the map scale a: 11 px, smaller when the map is
// small (15 units of the map).
function labelPx(a) { return Math.min(11, 15 * a); }
function over(a, b) { return a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1]; }
// The boxes that a label must not cover: the cards, the names of the regions and the names
// of the containers, in the coordinates of the map.
function walls(m) {
  if (m._walls) return m._walls;
  var out = m.cards.map(function (c) { return [c.b[0] - 3, c.b[1] - 3, c.b[0] + c.b[2] + 3, c.b[1] + c.b[3] + 3]; });
  m.regions.forEach(function (r) { out.push([r.b[0], r.b[1] + 6, r.b[0] + 40 + r.n.length * 6.6, r.b[1] + 28]); });
  m.boxes.forEach(function (b) { out.push([b.b[0] + 12, b.b[1] + 16, b.b[0] + 230, b.b[1] + 38]); });
  m._walls = out;
  return out;
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
// A place for the label of line e at the font size fs (in units of the map), or null.
function seat(e, fs, wall, taken, list) {
  var w = unitWidth(e.s, 500) * fs + 8, hh = fs * 1.35, q = e.q, best = null;
  function flat(i) { return Math.abs(q[i][1] - q[i + 1][1]) < 0.01; }
  var order = q.slice(0, -1).map(function (p, i) { return i; }).sort(function (a, b) { return (flat(b) - flat(a)) || segLen(q, b) - segLen(q, a); });
  for (var o = 0; o < order.length && !best; o++) {
    var i = order[o], a = q[i], b = q[i + 1];
    if (segLen(q, i) < (flat(i) ? w : hh) + 18) continue;
    [0.5, 0.35, 0.65, 0.22, 0.78, 0.12, 0.88].forEach(function (t) {
      if (best) return;
      var cx = a[0] + (b[0] - a[0]) * t, cy = a[1] + (b[1] - a[1]) * t, box = [cx - w / 2, cy - hh / 2, cx + w / 2, cy + hh / 2];
      if (wall.some(function (c) { return over(box, c); }) || taken.some(function (c) { return over(box, c); })) return;
      if (!crossed(box, list, e)) best = {x: cx, y: cy, box: box};
    });
  }
  return best;
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
  var low = Math.pow(2, step / 4), fs = labelPx(low) / low, taken = [], wall = walls(m), out = [];
  L.list.slice().sort(function (u, v) { return u.len - v.len; }).forEach(function (e) {
    // Each line of a sequence has a label with its step numbers: with no free place, the
    // label goes near its line, as a lit label does (`stacked` in `atlas_lit`).
    var at = seat(e, fs, wall, taken, L.list) || (L.seq ? seat(e, fs, wall, taken, []) || stacked(e, fs, taken, wall) : null);
    if (!at) return;
    taken.push(at.box); out.push({e: e, x: at.x, y: at.y, box: at.box});
  });
  L.seats = {key: key, list: out, fs: fs};
  return L.seats;
}
"""
