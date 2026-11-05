"""The fade part of the canvas renderer: the value of each boundary flow from frame to frame.

`page_canvas` joins this part after the drawing part (`page_canvas_draw`). A boundary flow
fades in and out with the camera, as the maintainer rule of docs/design/nested-canvas.md
says: "Each change follows the zoom continuously. Nothing appears at one time."

- A line never goes into a card or a text, or into a portal with a `show` of 0.5 or more:
  `boundaryPath` gives only the paths that are possible. Thus the value of a path must go
  to 0 before a box gets to the path. The speed of each box relative to each segment gives
  the frames until they touch (`boxCap`). At a constant speed, the fade out takes 10 frames.
- A line that changes to a different path fades out on the earlier path and fades in on
  the new path. A line of a map above that a deeper map replaces fades out (`spare`).
- A value goes up by 1 in FADE_MS or more. A line with the value 0 costs nothing: the
  script draws only the paths with a value, and it keeps values only for the lines of the
  portals of the frame.
- With reduced motion, a line shows or goes at one time, as each camera move does.
"""

from __future__ import annotations

FADE = r"""
// ---- the fade of the boundary flows -------------------------------------------
// A boundary flow fades in and out with the camera. It does not appear or go at one time.
// FADE keeps a value from 0 to 1 for each of the 16 paths of each line, from frame to frame.
// - A path that goes into a box of OBST is not drawn (`boundaryPath`). Thus the value of a
//   path must be near 0 before a box gets to it. For each box and for each other limit of
//   the path, the distance now and in the frame before give the frames until the path
//   touches it. The value is never more than FADE_NEAR times the smallest count of frames.
//   Thus a path that a box comes near at a constant speed fades out by FADE_NEAR or less
//   in each frame. A box that does not move relative to the path does not change the value.
// - The line uses one path (`c`). It changes to the shortest path only when its path is
//   not possible, or when its path is much longer. Then the earlier path fades out and the
//   new path fades in.
// - A value goes up by 1 in FADE_MS or more, and down at the same rate or faster (the
//   limit above). The time between two frames counts as FADE_DT or less, thus one frame
//   makes a value larger by 0.2 or less.
// - With reduced motion, each value is 1 or 0 at once.
// A line that is not in a portal of the frame has no value, and the script makes no path
// for it. `FADING` is true when a value did not get to its target in the frame.
var FADE = new Map(), FADE_MS = 200, FADE_DT = 40, FADE_NEAR = 0.1, WEIGHT_PX = 40;
var FADE_LAST = 0, FADE_STEP = 1, FADE_FRAME = 0, FADING = false, FADE_CAM = null, CAM_BEFORE = null;
function lineKey(nb, p, m) { return (m.id || '') + '>' + (nb.map.id || '') + '/' + nb.id + '|' + p.d; }
function fadeFrame() {
  var now = performance.now(), dt = FADE_LAST ? Math.min(now - FADE_LAST, FADE_DT) : FADE_DT;
  FADE_LAST = now; FADE_FRAME++; FADING = false;
  FADE_STEP = reduced() ? 1 : dt / FADE_MS;
  CAM_BEFORE = FADE_CAM; FADE_CAM = camCopy();
}
function portalKey(t) { return t.nb.map.id + '/' + t.nb.id; }
// The screen point in the frame before of a screen point of a box that moves with the camera.
function before(x, y) {
  var c = CAM_BEFORE;
  return c ? [(x / cam.k + cam.x - c.x) * c.k, (y / cam.k + cam.y - c.y) * c.k] : [x, y];
}
// The other limits of a path, in pixels, as a list: the distance from its first point to the
// screen edge, the length of its one last segment (`legs`), the part of the portal box that
// is out of the frame `b.f` of the open card (a portal that the frame grows into stops all
// paths soon), and the distance to the frame. A segment on the gutter `b.e` is always out
// of the frame, thus it does not count for the frame. The first segment does not count.
function limitsOf(pts, b) {
  var a = pts[0], pr = b.pr, f = b.f, g = Infinity;
  for (var j = 2; j < pts.length; j++) if (!alongBox(pts[j - 1], pts[j], b.e)) g = Math.min(g, gap(pts[j - 1], pts[j], f[0], f[1], f[2], f[3]));
  return [Math.min(a[0], W - a[0], a[1], H - a[1]) - 1, pts.leg, Math.max(pr[2] - f[2], f[0] - pr[0], pr[3] - f[3], f[1] - pr[1]) - 1, g];
}
function inBox(p, x0, y0, x1, y1) { return p[0] >= x0 && p[0] <= x1 && p[1] >= y0 && p[1] <= y1; }
// The distance from a segment to a box, plus 1: 0 or less when the segment goes into the box.
function gap(p, q, x0, y0, x1, y1) {
  var gx = Math.max(x0 - Math.max(p[0], q[0]), Math.min(p[0], q[0]) - x1);
  var gy = Math.max(y0 - Math.max(p[1], q[1]), Math.min(p[1], q[1]) - y1);
  return Math.max(gx, gy) + 1;
}
// The distance from each segment of a path to a box, as a list. For the first segment, a
// box that holds the first point (the actor card of the flow) does not count.
function pathGaps(pts, x0, y0, x1, y1) {
  var out = [], skip = inBox(pts[0], x0 - 1, y0 - 1, x1 + 1, y1 + 1);
  for (var j = 1; j < pts.length; j++) out.push(skip && j === 1 ? Infinity : gap(pts[j - 1], pts[j], x0, y0, x1, y1));
  return out;
}
// Tell if a segment is on a side of the box e.
function alongBox(p, q, e) {
  return (near(p[0], q[0]) && (near(p[0], e[0]) || near(p[0], e[2]))) || (near(p[1], q[1]) && (near(p[1], e[1]) || near(p[1], e[3])));
}
// FADE_NEAR times the frames until a distance gets to 0, or 1. A change of less than 0.25
// pixels is no move, and a distance that was not known is no move.
function nearCap(now, was) {
  if (!isFinite(was) || !isFinite(now)) return 1;
  var speed = was - Math.max(now, 0);
  return speed > 0.25 ? clamp(FADE_NEAR * Math.max(now, 0) / speed, 0, 1) : 1;
}
// The highest value of a path from its boxes: the path now `pts` and in the frame before
// `old`. A box that moves with the camera was at its place for the camera of the frame
// before. A box with a weight of less than HARD seems up to WEIGHT_PX farther away. The
// box of the portal of the path does not count. When the two paths have the same count of
// points, each segment has its own speed. Thus a near segment that does not move does not
// hide a far segment that moves quickly.
function boxCap(pts, old, pr) {
  var top = 1, same = pts.length === old.length;
  for (var i = 0; i < NOBST && top > 0; i += OB) {
    var x0 = OBST[i], y0 = OBST[i + 1], x1 = OBST[i + 2], y1 = OBST[i + 3], far = (1 - Math.min(1, OBST[i + 4] / HARD)) * WEIGHT_PX;
    if (near(x0, pr[0]) && near(y0, pr[1]) && near(x1, pr[2]) && near(y1, pr[3])) continue;
    var p0 = OBST[i + 5] ? before(x0, y0) : [OBST[i + 6], OBST[i + 7]], p1 = OBST[i + 5] ? before(x1, y1) : [OBST[i + 8], OBST[i + 9]];
    var now = pathGaps(pts, x0, y0, x1, y1), was = pathGaps(old, p0[0], p0[1], p1[0], p1[1]);
    if (!same) { now = [Math.min.apply(null, now)]; was = [Math.min.apply(null, was)]; }
    for (var j = 0; j < now.length; j++) top = Math.min(top, nearCap(now[j] + far, was[j] + far));
  }
  return top;
}
// The highest value of a path: the smallest cap of its boxes and of its other limits. A path
// that was not drawn in the frame before has no cap.
function pathCap(pts, b, s, id) {
  var lim = limitsOf(pts, b), was = s.lim[id], old = s.pts[id], top = 1;
  s.lim[id] = lim; s.pts[id] = pts;
  if (!old) return 1;
  for (var k = 0; k < lim.length; k++) top = Math.min(top, nearCap(lim[k], was[k]));
  return Math.min(top, boxCap(pts, old, b.pr));
}
// The paths of a line to draw in this frame, each with its value.
function fadeOf(key, b, spare) {
  var s = FADE.get(key);
  if (!s) { s = {c: -1, v: {}, lim: {}, pts: {}}; FADE.set(key, s); }
  s.frame = FADE_FRAME;
  var c = s.c;
  if (spare || !b) c = -1;
  else if (c < 0 || !b.all[c] || b.costs[c] > 1.25 * b.costs[b.best] + 40) c = b.best;
  s.c = c;
  var out = [], ids = Object.keys(s.v), step = FADE_STEP;
  if (c >= 0 && !(c in s.v)) ids.push(String(c));
  ids.forEach(function (id) {
    var i = +id, pts = b && b.all[i], top = !pts ? 0 : step < 1 ? pathCap(pts, b, s, id) : 1, was = s.v[id] || 0;
    var target = i === c ? top : 0, v = Math.min(was < target ? was + step : Math.max(was - step, target), top);
    if (v !== target) FADING = true;
    if (v <= 0.004) { delete s.v[id]; delete s.lim[id]; delete s.pts[id]; return; }
    s.v[id] = v;
    out.push({i: i, pts: pts, v: v});
  });
  if (!out.length && c < 0) FADE.delete(key);
  return out;
}
// Remove the values of the lines that the frame did not draw.
function fadeEnd() {
  FADE.forEach(function (s, key) { if (s.frame !== FADE_FRAME) FADE.delete(key); });
}
"""
