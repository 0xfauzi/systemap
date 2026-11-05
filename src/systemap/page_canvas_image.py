"""The image part of the canvas renderer: the images of a large map.

`page_canvas` joins this part after the drawing part (`page_canvas_draw`). The part
follows the rules of the section "Performance" of docs/design/nested-canvas.md:

- When the cards of a large map are marks only, it draws the map into an image one time
  for each zoom step, and it uses that image in each frame (`marksImage`).
- While the camera moves, it draws a large open map from images that it makes in slices,
  in the free time of the frames (`mapImage`, `makeImages`).
"""

from __future__ import annotations

IMAGE = r"""
// ---- the image of the marks of a large map -------------------------------------------
// One image for each half step of zoom (a factor of 1.41). A pan uses the same image.
function zoomStep(a) { return Math.round(Math.log2(a) * 2) / 2; }
function marksImage(m, a) {
  var z = zoomStep(a), s = Math.pow(2, z) * (window.devicePixelRatio || 1), key = EPOCH + '|' + z;
  if (m.img && m.img.key === key) return m.img;
  var w = Math.ceil(m.size[0] * s), h = Math.ceil(m.size[1] * s);
  if (w < 1 || h < 1 || w > 4096 || h > 4096) return null;
  var c = m.img ? m.img.canvas : document.createElement('canvas'), g;
  c.width = w; c.height = h; g = c.getContext('2d');
  g.fillStyle = C['--map']; g.fillRect(0, 0, w, h);
  drawBoxes(g, m, s, 0, 0, 1, false);
  drawFlows(g, m.flows, s, 0, 0, 0.7, false);
  var marks = new Batch(true);
  m.cards.forEach(function (card) {
    marks.rect(colors(card).mark, 1, s * card.b[0], s * card.b[1], s * card.b[2], s * card.b[3], 0);
  });
  marks.flush(g);
  m.img = {canvas: c, key: key};
  return m.img;
}

// ---- the image of a large map while the camera moves ----------------------------------
// While the camera moves, a large open map with no nested map and no port is drawn from
// images of the full map, at the moving resolution: one image for each step of MAP_STEP in
// log2 of the scale, with at most MAP_PX pixels. Between two steps, the frame draws the
// lower image, and the higher image over it with an opacity from 0 to 1. Thus each fade of
// the level of detail follows the zoom. A frame makes slices of the images until MAP_MS
// after its start. Until the two images are complete, the frame uses the normal drawing.
var MAP_STEP = 0.5, MAP_PX = 2e6, MAP_KEEP = 4, MAP_SLICE = 25, MAP_MS = 8;
var JOB = null, WANT = null, LAST_L = null, ZOOM_DIR = 1;
function isLeaf(m) {
  return m._leaf !== undefined ? m._leaf : (m._leaf = !(m.ports && m.ports.length) && m.cards.every(function (c) { return !c.child; }));
}
function imageSize(m, z) {
  var d = (window.devicePixelRatio || 1) * 0.5, s = Math.pow(2, z);
  return {w: Math.ceil(m.size[0] * s * d), h: Math.ceil(m.size[1] * s * d), d: d, s: s, key: TEXTS + '|' + z + '|' + d};
}
function readyImage(m, z) {
  var key = imageSize(m, z).key, list = m._imgs || [];
  for (var i = 0; i < list.length; i++) if (list[i].key === key) return list[i];
  return null;
}
// The images of the two steps around the scale `a` and the opacity of the higher image,
// or null. The frame also asks for these images.
function mapImage(m, a) {
  if (!isLeaf(m)) return null;
  var l = Math.log2(a) / MAP_STEP, z = Math.floor(l) * MAP_STEP;
  WANT = {m: m, l: l, z: z};
  var lo = readyImage(m, z), hi = readyImage(m, z + MAP_STEP);
  return lo && hi ? {lo: lo, hi: hi, t: l - Math.floor(l)} : null;
}
// The boxes of the normal drawing that a boundary flow must not cross: the cards on the
// screen, the plates of the flow labels and the names of the boxes. Give the card count.
function mapObstacles(m, a, ox, oy, box, alpha) {
  var cards = m.cardIndex.query(box[0], box[1], box[2], box[3], []), fs = q(clamp(10.5 * a, 0, 13));
  cards.forEach(function (c) { obstacle(ox + a * c.b[0], oy + a * c.b[1], a * c.b[2], a * c.b[3]); });
  if (fs >= 8 && alpha > 0.05) plates(m.flowIndex.query(box[0], box[1], box[2], box[3], []), a, ox, oy, fs, obstacle);
  if (fs < MIN_TEXT || alpha <= 0.02) return cards.length;
  boxNames(m, a, ox, oy, function (s, x, y) { if (s) obstacle(x, y - fs, unitWidth(s, 600) * fs, fs * 1.3); });
  return cards.length;
}
// The parts of an image in the order of the normal drawing: the boxes, the flows in
// slices, the cards in slices, the labels, and the text of the cards in slices.
function imageParts(m, s) {
  var parts = [function () {
    ctx.fillStyle = C['--map']; ctx.fillRect(0, 0, W, H);
    drawBoxes(ctx, m, s, 0, 0, 1, true);
  }];
  function slices(list, each) {
    for (var i = 0; i < list.length; i += MAP_SLICE) parts.push(each.bind(null, list.slice(i, i + MAP_SLICE)));
  }
  slices(m.flows, function (part) { drawFlows(ctx, part, s, 0, 0, 1, m.maxH * s > 14); });
  slices(m.cards, function (part) {
    part.forEach(function (c) { cardBox(c, s * c.b[0], s * c.b[1], s * c.b[2], s * c.b[3], 1); });
    BACK.flush(ctx); FILL.flush(ctx); LINE.flush(ctx);
  });
  parts.push(function () { drawLabels(m.flows, s, 0, 0, 1); });
  slices(m.cards, function (part) {
    part.forEach(function (c) { if (s * c.b[3] >= MARK_H - 4) cardText(c, s * c.b[0], s * c.b[1], s * c.b[2], s * c.b[3], 1); });
  });
  return parts;
}
// Draw the next part of the job into its image, in the coordinates of the image.
function drawSlice(job) {
  var m = job.m, keep = [ctx, W, H, STATS.cards, NOBST];
  ctx = job.g; W = m.size[0] * job.s; H = m.size[1] * job.s;
  ctx.setTransform(job.d, 0, 0, job.d, 0, 0); ctx.globalAlpha = 1;
  try { job.parts[job.i++](); } finally { ctx = keep[0]; W = keep[1]; H = keep[2]; STATS.cards = keep[3]; NOBST = keep[4]; }
  job.done = job.i >= job.parts.length;
  // Paint the part in this frame, and not in the first frame that uses the image.
  job.g.getImageData(0, 0, 1, 1);
}
function newJob(m, z) {
  var r = imageSize(m, z), c = document.createElement('canvas');
  c.width = r.w; c.height = r.h;
  return {m: m, z: z, key: r.key, c: c, g: c.getContext('2d', {alpha: false}), i: 0, d: r.d, s: r.s, parts: imageParts(m, r.s), done: false};
}
// Keep the new image. When the map has too many images, remove the image of the step that
// is farthest from the current step.
function keepImage(job, z) {
  var m = job.m, list = (m._imgs || []).filter(function (im) { return im.texts === TEXTS; });
  list.push({canvas: job.c, key: job.key, texts: TEXTS, z: job.z});
  list.sort(function (u, v) { return Math.abs(u.z - z) - Math.abs(v.z - z); });
  m._imgs = list.slice(0, MAP_KEEP);
}
// The steps of zoom to make for the map that the frame asked for: the two steps around the
// scale, the next step in the direction of the zoom, and the step behind. A step whose
// cards are marks up to the next step is not necessary.
function wantedSteps(want) {
  var m = want.m, z = want.z, ahead;
  if (LAST_L !== null && want.l !== LAST_L) ZOOM_DIR = want.l > LAST_L ? 1 : -1;
  LAST_L = want.l;
  ahead = ZOOM_DIR > 0 ? z + 2 * MAP_STEP : z - MAP_STEP;
  return [z, z + MAP_STEP, ahead, ZOOM_DIR > 0 ? z - MAP_STEP : z + 2 * MAP_STEP].filter(function (y) {
    var r = imageSize(m, y);
    return r.w * r.h <= MAP_PX && r.w <= 4096 && r.h <= 4096 && m.maxH * Math.pow(2, y + MAP_STEP) >= MARK_H - 6 && !readyImage(m, y);
  });
}
// Make slices of the wanted images until MAP_MS after `began`, the start of the frame.
function makeImages(began) {
  var want = WANT;
  WANT = null;
  if (!want) return;
  var steps = wantedSteps(want), at = JOB ? steps.indexOf(JOB.z) : -1;
  if (JOB && (JOB.m !== want.m || JOB.key !== imageSize(JOB.m, JOB.z).key || at < 0)) JOB = null;
  else if (JOB) steps.splice(at, 1);
  while (performance.now() - began < MAP_MS && (JOB || steps.length)) {
    JOB = JOB || newJob(want.m, steps.shift());
    drawSlice(JOB);
    if (JOB.done) { keepImage(JOB, want.z); JOB = null; }
  }
}

"""
