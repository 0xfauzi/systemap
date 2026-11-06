"""The image part of the canvas renderer: the images of a large map.

`page_canvas` joins this part after the drawing part (`page_canvas_draw`). The part
follows the rules of the section "Performance" of docs/design/nested-canvas.md:

- When the cards of a large map are marks only, it draws the map into an image one time
  for each zoom step, and it uses that image in each frame (`marksImage`).
- While the camera moves, it draws a large open map from images that it makes in slices,
  in the free time of the frames (`mapImage`, `makeImages`).
- The change between these images and the full drawing fades in time, and so does the
  text that MOVE_TEXT hides while the camera moves (`speedFrame`, `imageLayer`). The rule
  of the maintainer is "Each change follows the zoom continuously. Nothing appears at one
  time."
"""

from __future__ import annotations

IMAGE = r"""
// ---- the image of the marks of a large map -------------------------------------------
// One image for each half step of zoom (a factor of 1.41). A pan uses the same image.
// The key has the device pixel ratio, so a change of the ratio makes the image again. The
// images of the maps that the last frame did not draw are removed first when all the images
// have more than MARKS_PX pixels.
var MARKS_PX = 16e6, MARKS = [];
function marksImage(m, a) {
  var z = Math.round(Math.log2(a) * 2) / 2, s = Math.pow(2, z) * dpr(), key = EPOCH + '|' + z + '|' + dpr();
  if (m.img && m.img.key === key) { m.img.used = drawn; return m.img; }
  var w = Math.ceil(m.size[0] * s), h = Math.ceil(m.size[1] * s);
  if (w < 1 || h < 1 || w > IMG_MAX || h > IMG_MAX) return null;
  marksRoom(m, w * h);
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
  m.img = {canvas: c, key: key, used: drawn, px: w * h};
  if (MARKS.indexOf(m) < 0) MARKS.push(m);
  return m.img;
}
// Remove the marks images of other maps, the oldest first, until `px` more pixels fit in
// MARKS_PX. Keep each image that the frame before or this frame drew.
function marksRoom(m, px) {
  var total = px;
  MARKS.forEach(function (o) { if (o !== m) total += o.img.px; });
  MARKS.sort(function (u, v) { return u.img.used - v.img.used; });
  MARKS = MARKS.filter(function (o) {
    if (o === m || total <= MARKS_PX || o.img.used >= drawn - 1) return true;
    total -= o.img.px; o.img = null;
    return false;
  });
}

// ---- the image of a large map while the camera moves ----------------------------------
// While the camera moves, a large open map with no nested map and no port is drawn from
// images of the full map, at the moving resolution: one image for each step of MAP_STEP in
// log2 of the scale, with at most MAP_PX pixels. Between two steps, the frame draws the
// lower image, and the higher image over it with an opacity from 0 to 1. Thus each fade of
// the level of detail follows the zoom. A frame makes slices of the images until MAP_MS
// after its start. When only one of the two images is complete, the frame uses that image.
// When neither is complete, the frame uses the normal drawing.
// The resolution of an image is 2 to the power MAP_STEP times the moving resolution. Thus
// the frame never shows an image larger than its pixels, and the text stays clear. Only the
// map that asked last keeps its images (`IMG_MAP`), at most MAP_KEEP images.
var MAP_STEP = 0.5, MAP_PX = 2e6, MAP_KEEP = 4, MAP_SLICE = 25, MAP_MS = 8;
var JOB = null, WANT = null, LAST_L = null, ZOOM_DIR = 1, IMG_MAP = null;
function isLeaf(m) {
  return m._leaf !== undefined ? m._leaf : (m._leaf = !(m.ports && m.ports.length) && m.cards.every(function (c) { return !c.child; }));
}
function imageSize(m, z) {
  var d = dpr() * 0.5 * Math.pow(2, MAP_STEP), s = Math.pow(2, z);
  return {w: Math.ceil(m.size[0] * s * d), h: Math.ceil(m.size[1] * s * d), d: d, s: s, key: TEXTS + '|' + z + '|' + d};
}
function readyImage(m, key) {
  var list = m._imgs || [];
  for (var i = 0; i < list.length; i++) if (list[i].key === key) return list[i];
  return null;
}
// The part of each complete image of the two steps around the scale `a`, as a list of
// [image, part], or null. When the two images are complete, the higher image has the
// part t, from 0 to 1 between the two steps. The frame also asks for these images.
// Above the highest step that has an image, the image of that step stays for the part
// MAP_OVER of the next step, and the layer goes to 0 over that part (`v` of the list).
// Thus the change between the images and the normal drawing occurs in that part of the
// zoom, where the frame draws the normal drawing also without images. That image has
// a little less than one pixel for each pixel of the frame (2 to the power -MAP_OVER / 2).
// In that part, a frame draws the normal drawing and the image, which is the most
// expensive frame of a large map. Thus the part is short (an eighth of a step of zoom),
// and the layer fades more quickly than the other fades (IMAGE_MS). While the camera
// zooms, the layer follows the zoom. Thus a slower zoom gives more of these frames.
// MARKS_OVER is the part of a step before the end of the marks, where the images fade
// in over the marks image while the zoom goes in (`drawMap`).
var MAP_OVER = 0.25, MARKS_OVER = 0.5;
function tooLarge(m, z) { var r = imageSize(m, z); return r.w * r.h > MAP_PX || r.w > IMG_MAX || r.h > IMG_MAX; }
function mapImage(m, a) {
  if (!isLeaf(m)) return null;
  var l = Math.log2(a) / MAP_STEP, z = Math.floor(l) * MAP_STEP, t = l - Math.floor(l), out = null;
  WANT = {m: m, l: l, z: z};
  var lo = readyImage(m, imageSize(m, z).key), hi = readyImage(m, imageSize(m, z + MAP_STEP).key);
  var below = !lo && t < MAP_OVER && tooLarge(m, z) ? readyImage(m, imageSize(m, z - MAP_STEP).key) : null;
  if (lo && hi) out = [[lo, 1 - t], [hi, t]];
  else if (lo || hi) out = [[lo || hi, 1]];
  else if (below) { out = [[below, 1]]; out.v = 1 - t / MAP_OVER; }
  return out;
}
// The boxes of the normal drawing that cover a boundary flow: the cards on the screen, the
// plates of the flow labels and the names of the boxes. Give the card count.
function mapObstacles(m, a, ox, oy, box, alpha) {
  var cards = m.cardIndex.query(box[0], box[1], box[2], box[3], []), fs = labelSize(a), la = labelAlpha(a, alpha), na = nameAlpha(a, alpha);
  cards.forEach(function (c) { obstacle(ox + a * c.b[0], oy + a * c.b[1], a * c.b[2], a * c.b[3], 1, alpha); });
  if (hasLabels(fs, la)) plates(m.flowIndex.query(box[0], box[1], box[2], box[3], []), a, ox, oy, fs, function (x, y, w, h) { obstacle(x, y, w, h, 1, la); });
  if (fs < MIN_TEXT || na <= 0.02) return cards.length;
  boxNames(m, a, ox, oy, function (s, x, y) { if (s) textBox(s, x, y, fs, 600, false, '', na); });
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
    flushCards(ctx);
  });
  parts.push(function () { drawLabels(m.flows, s, 0, 0, 1); });
  slices(m.cards, function (part) {
    part.forEach(function (c) { if (hasText(s * c.b[3])) cardText(c, s * c.b[0], s * c.b[1], s * c.b[2], s * c.b[3], 1); });
  });
  return parts;
}
// Draw the next part of the job into its image, in the coordinates of the image. An image
// has the text of a moving frame (HIDE is 1), as the normal drawing of a moving frame.
function drawSlice(job) {
  var m = job.m, keep = [ctx, W, H, STATS.cards, NOBST, HIDE];
  ctx = job.g; W = m.size[0] * job.s; H = m.size[1] * job.s; HIDE = 1;
  ctx.setTransform(job.d, 0, 0, job.d, 0, 0); ctx.globalAlpha = 1;
  try { job.parts[job.i++](); } finally { ctx = keep[0]; W = keep[1]; H = keep[2]; STATS.cards = keep[3]; NOBST = keep[4]; HIDE = keep[5]; }
  job.done = job.i >= job.parts.length;
  // Paint the part in this frame, and not in the first frame that uses the image.
  job.g.getImageData(0, 0, 1, 1);
}
function newJob(m, z) {
  var r = imageSize(m, z), c = document.createElement('canvas');
  c.width = r.w; c.height = r.h;
  return {m: m, z: z, key: r.key, c: c, g: c.getContext('2d', {alpha: false}), i: 0, d: r.d, s: r.s, parts: imageParts(m, r.s), done: false};
}
// Keep the new image. Remove each image whose key is not current (the text or the device
// pixel ratio changed). When the map has too many images, remove the image of the step that
// is farthest from the current step.
function keepImage(job, z) {
  var m = job.m, list = (m._imgs || []).filter(function (im) { return im.key === imageSize(m, im.z).key; });
  list.push({canvas: job.c, key: job.key, z: job.z});
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
    return r.w * r.h <= MAP_PX && r.w <= IMG_MAX && r.h <= IMG_MAX && m.maxH * Math.pow(2, y + MAP_STEP) >= MARK_H - 6 && !readyImage(m, r.key);
  });
}
// Make slices of the wanted images until MAP_MS after `began`, the start of the frame.
function makeImages(began) {
  var want = WANT;
  WANT = null;
  if (!want) return;
  if (IMG_MAP && IMG_MAP !== want.m) IMG_MAP._imgs = null;
  IMG_MAP = want.m;
  var steps = wantedSteps(want), at = JOB ? steps.indexOf(JOB.z) : -1;
  if (JOB && (JOB.m !== want.m || JOB.key !== imageSize(JOB.m, JOB.z).key || at < 0)) JOB = null;
  else if (JOB) steps.splice(at, 1);
  while (performance.now() - began < MAP_MS && (JOB || steps.length)) {
    JOB = JOB || newJob(want.m, steps.shift());
    drawSlice(JOB);
    if (JOB.done) { keepImage(JOB, want.z); JOB = null; }
  }
}

// ---- the fades of the two speed changes ---------------------------------------------
// The images of a large map and the rule MOVE_TEXT make a moving frame faster. Each change
// between them and the full drawing fades in time. It does not appear or go at one time.
// - HIDE goes to 1 while the camera moves and to 0 after it stops. The text that MOVE_TEXT
//   hides has the alpha 1 - HIDE.
// - The image layer of a map has the value `m._ia`. It goes to 1 while the camera moves and
//   an image of the scale is complete (to `v` of `mapImage` above the highest step), and to
//   0 in all other frames. While the value is between 0 and 1, the frame draws the normal
//   drawing and the images over it. Thus the two drawings are in the same frames only
//   during a fade: 5 frames or more at 60 frames each second, and above the highest step
//   for as long as the zoom stays in the part MAP_OVER. A fade out uses the last images. After a stop, the fade of the next
//   part removes the images and HIDE.
// - In the layer, each image has a weight that goes to its part of `mapImage`. Its part of
//   the result is `m._ia` times its weight, divided by the sum of the weights. Thus an image
//   that becomes complete fades in, and the higher image of a step becomes the lower image
//   of the next step with no change.
// - HIDE changes by 1 in SPEED_MS or more. The image layer and the weights change by 1 in
//   IMAGE_MS or more, because a frame of a fade between the images and the normal drawing
//   draws both. Each value changes by SPEED_MAX or less in one frame. With reduced motion,
//   each one goes to its target at once.
// `SPEED_FADING` is true when a value did not get to its target in the frame.
var HIDE = 0, SPEED_MS = 160, IMAGE_MS = 80, SPEED_MAX = 0.2, SPEED_STEP = 1, IMAGE_STEP = 1, SPEED_LAST = 0, SPEED_FADING = false, LAYERS = [];
function speedStep(dt, ms) { return Math.min(SPEED_MAX, dt / ms); }
function speedFrame() {
  var now = performance.now(), dt = SPEED_LAST ? now - SPEED_LAST : Infinity;
  SPEED_LAST = now; SPEED_FADING = false; LAYERS = [];
  SPEED_STEP = reduced() ? 1 : speedStep(dt, SPEED_MS);
  IMAGE_STEP = reduced() ? 1 : speedStep(dt, IMAGE_MS);
  HIDE = toward(HIDE, sharp ? 0 : 1, SPEED_STEP);
  if (cam.k > ZOOM_K && ZOOM_K) ZOOM_UP = now;
  ZOOM_K = cam.k;
}
function toward(v, to, step) {
  var n = approach(v, to, step);
  if (n !== to) SPEED_FADING = true;
  return n;
}
// The image layer of a large map in this frame: a list of [image, part of the result], or
// null. The frame asks for the images when `ask` is true, and it uses them when `use` is
// also true. A map that the frame before did not draw starts again at 0.
function imageLayer(m, a, ask, use) {
  var asked = ask ? mapImage(m, a) : null, parts = use ? asked : null, list = m._iaAt === drawn - 1 && m._iw || [], sum = 0;
  if (m._iaAt !== drawn - 1) m._ia = 0;
  m._iaAt = drawn;
  m._ia = toward(m._ia, parts ? (parts.v === undefined ? 1 : parts.v) : 0, IMAGE_STEP);
  // Without images of the scale, the weights do not change, and only the layer fades out.
  if (parts) {
    parts.forEach(function (p) { if (!list.some(function (e) { return e.img === p[0]; })) list.push({img: p[0], w: 0}); });
    list = list.filter(function (e) {
      var to = 0;
      parts.forEach(function (p) { if (p[0] === e.img) to = p[1]; });
      e.w = toward(e.w, to, IMAGE_STEP);
      return e.w > 0 || to > 0;
    });
  }
  list.forEach(function (e) { sum += e.w; });
  m._iw = m._ia > 0 && sum > 0 ? list : null;
  if (!m._iw) { m._ia = 0; return null; }
  var out = list.filter(function (e) { return e.w > 0; }).map(function (e) { return [e.img, m._ia * e.w / sum]; });
  LAYERS.push({id: m.id, v: m._ia, parts: out.map(function (p) { return [p[0].key, p[1]]; })});
  return out;
}
// ---- the fade after the camera stops ------------------------------------------------
// A moving frame is drawn on a second canvas over the page canvas (`#still`). When the
// camera stops, `stillStart` draws the full drawing (full resolution, all text, no image
// layer) one time on the page canvas, under the last moving frame. Then each frame of
// `stillFrame` only sets the opacity of the second canvas to 1 - `STILL.s`, and the browser
// blends the two canvases. Thus no frame copies or draws the canvas again. The value
// `STILL.s` goes from 0 to 1 at the speed of the other fades. Nothing changes during this
// fade: a boundary flow keeps its value, and it continues to fade after this fade. A camera
// change stops the fade (`stillStop`). Then the text and the image layers continue from the
// values that the screen shows. The second canvas does not get the input events.
var STILL = null, STILL_CV = null, STILL_CTX = null, PAGE_CTX = ctx;
function stillCanvas() {
  if (STILL_CV) return STILL_CV;
  STILL_CV = document.createElement('canvas');
  STILL_CV.id = 'still'; STILL_CV.hidden = true; STILL_CV.setAttribute('aria-hidden', 'true');
  STILL_CTX = STILL_CV.getContext('2d', {alpha: false});
  cv.parentNode.insertBefore(STILL_CV, cv.nextSibling);
  return STILL_CV;
}
// The canvas of a frame: the second canvas while the camera moves, or else the page canvas.
// It also sets `ctx`.
function frameCanvas() {
  if (sharp) { ctx = PAGE_CTX; return cv; }
  var o = stillCanvas();
  ctx = STILL_CTX;
  return o;
}
// After a frame: show the second canvas while the camera moves, and hide it after a frame
// on the page canvas, but not during the fade. While the second canvas covers the page
// canvas, the page canvas has the opacity 0, so that the browser does not paint it. It
// still gets the input events and the focus.
function frameShown() {
  if (!STILL_CV) return;
  if (!sharp) { STILL_CV.hidden = false; STILL_CV.style.opacity = '1'; cv.style.opacity = '0'; return; }
  cv.style.opacity = '';
  if (!STILL) STILL_CV.hidden = true;
}
function stillStart() {
  if (reduced() || !STILL_CV || STILL_CV.hidden) { draw(); return; }
  var was = {hide: HIDE, layers: LAYERS, maps: []}, log = LOG;
  ORDER.forEach(function (m) { if (m._ia) { was.maps.push({m: m, ia: m._ia, iw: m._iw}); m._ia = 0; m._iw = null; } });
  STILL = {s: 0, was: was, want: false, last: 0};
  HIDE = 0; LOG = null;
  draw();
  LOG = log; clearTimeout(fadeTimer);
  STILL.want = FADING;
  stillFrame(STILL);
}
// The layers of the moving frame, with the part `keep` of the result.
function keptLayers(layers, keep) {
  return keep <= 0 ? [] : layers.map(function (l) {
    return {id: l.id, v: l.v * keep, parts: l.parts.map(function (p) { return [p[0], p[1] * keep]; })};
  });
}
function stillFrame(st) {
  if (STILL !== st) return;
  var now = performance.now(), dt = st.last ? now - st.last : Infinity;
  st.last = now;
  st.s = Math.min(1, st.s + speedStep(dt, SPEED_MS));
  STILL_CV.style.opacity = String(1 - st.s);
  if (LOG) LOG.push({at: now, ms: performance.now() - now, sharp: true, fine: st.s >= 1, hide: (1 - st.s) * st.was.hide, images: keptLayers(st.was.layers, 1 - st.s)});
  if (st.s < 1) { requestAnimationFrame(function () { stillFrame(st); }); return; }
  STILL = null; STILL_CV.hidden = true;
  if (st.want) request();
}
function stillStop() {
  var st = STILL, keep = st ? 1 - st.s : 0;
  if (!st) return;
  STILL = null;
  HIDE = keep * st.was.hide;
  st.was.maps.forEach(function (e) { e.m._ia = keep * e.ia; e.m._iw = e.iw; e.m._iaAt = drawn - 1; });
}
// Tell if the scale went up in the last ZOOM_WAIT ms. `speedFrame` records the changes.
var ZOOM_K = 0, ZOOM_UP = 0, ZOOM_WAIT = 300;
function zoomingIn() { return performance.now() - ZOOM_UP < ZOOM_WAIT; }
// Tell if the images of a layer give all of the result, without the normal drawing.
function layerFull(layer) { var r = 1; layer.forEach(function (p) { r -= p[1]; }); return r < 1e-6; }
// Draw the images of a layer over the normal drawing, the first image at the bottom. Each
// image has an opacity that gives it its part of the result: its part divided by 1 less the
// parts of the images over it.
function drawLayer(layer, ox, oy, mw, mh, alpha) {
  var above = 0, ops = [];
  for (var i = layer.length - 1; i >= 0; i--) {
    var c = layer[i][1], room = 1 - above;
    ops[i] = room <= c + 1e-6 ? 1 : c / room;
    above += c;
  }
  layer.forEach(function (p, j) { ctx.globalAlpha = alpha * ops[j]; ctx.drawImage(p[0].canvas, ox, oy, mw, mh); STATS.image++; });
}

"""
