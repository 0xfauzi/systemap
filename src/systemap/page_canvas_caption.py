"""The caption of the canvas page: the question of the layer, or the words of a view.

The caption is one line on a plate at the right of the path, in the row of the path. It
gives the reader the question that the screen answers:

- In the Map view, the name and the question of the layer, for example "System context"
  and "Which actors connect to the system?". The question comes from the current map when
  that map has the layer. Else it comes from the first map that has the layer
  (`LAYER_OF` in `page_canvas_view`). With All, the name is "All layers".
- In a different view, the words that the view part gives (`caption` of the seam in
  `page_canvas_view`). The Sequences view gives the name of the sequence and its question
  for the whole route, and "Step k of n" and the sentence of the step in the Steps mode.
  A view part without `caption` has no caption.

The caption has two texts: a short name (`k`) and the sentence (`s`). When the two do not
fit in the row, the name goes. When the sentence does not fit, it becomes shorter with
"..." (`fit`). When the row has less than CAP_ROOM px after the path, the caption does not
show. The words are also in the live region after each change (`viewWords`), so a screen
reader gets them without the canvas.

The caption fades as the marks of a view do: the old words fade out, and then the new
words fade in, with the step of the view (VIEW_STEP). With reduced motion, the words
change in one frame. The plate is a box that a boundary flow does not cross (`obstacle`),
as the plate of the path is. The top row of the portals is below the row of the path, so
a portal does not cover the caption.
"""

from __future__ import annotations

CAPTION = r"""
// ---- the caption: the question of the layer, or the words of a view ------------------
var CAP = {key: '', k: '', s: '', a: 0, at: -1, box: null, parts: null}, CAP_ROOM = 120, CAP_FS = 15, CAP_KS = 10.5;
// The words that the current view wants: `{k, s}`, or null.
function captionWant() {
  if (VIEW.mode !== 'map') { var v = VIEWS[VIEW.mode]; return v && v.caption ? v.caption() : null; }
  var id = VIEW.layer, own = null;
  if (id === 'all') return {k: 'All layers', s: layerQuestion(id)};
  (currentMap().layers || []).forEach(function (l) { if (l.id === id) own = l; });
  var s = own ? own.q : layerQuestion(id);
  return s ? {k: layerName(id), s: s} : null;
}
// The fade of the caption, one time in each frame: the old words go out, then the new
// words come in.
function captionFrame() {
  if (CAP.at === drawn) return;
  CAP.at = drawn;
  var want = captionWant(), key = want ? want.k + '\n' + want.s : '';
  if (key !== CAP.key && (CAP.a <= 0 || reduced())) { CAP.key = key; CAP.k = want ? want.k : ''; CAP.s = want ? want.s : ''; }
  var to = key && key === CAP.key ? 1 : 0;
  CAP.a = approach(CAP.a, to, VIEW_STEP);
  if (CAP.a !== to || key !== CAP.key) VIEW_FADING = true;
}
// The screen box x, y, w, h of the plate, the name and the sentence that fit, or null when
// the row has no room. The name shows only when the full sentence also fits.
function captionParts(path) {
  var p = pathPlate(path), x = p[0] + p[2] + 8, room = W - x - 12 - 24;
  if (!CAP.key || room + 24 < CAP_ROOM) return null;
  var kw = unitWidth(CAP.k.toUpperCase(), 600, true) * CAP_KS + 14, sw = unitWidth(CAP.s, 600) * CAP_FS, k = kw + sw <= room ? CAP.k : '';
  var s = fit(CAP.s, CAP_FS, k ? room - kw : room, 600), w = (k ? kw : 0) + Math.min(sw, unitWidth(s, 600) * CAP_FS) + 24;
  return {box: [x, p[1], w, p[3]], k: k, kw: kw, s: s};
}
// The caption of this frame, before the portals: its plate is a box that a boundary flow
// does not cross.
function captionLay(path) {
  captionFrame();
  var c = CAP.parts = CAP.a > 0.02 ? captionParts(path) : null;
  CAP.box = c ? c.box : null;
  if (c) obstacle(c.box[0], c.box[1], c.box[2], c.box[3], 1, CAP.a);
}
function drawCaption() {
  var c = CAP.parts;
  if (!c) return;
  var b = c.box, base = b[1] + b[3] / 2 + 4.5, x = b[0] + 12;
  plate(b, 0.96 * CAP.a);
  if (c.k) { text(c.k.toUpperCase(), x, base, CAP_KS, C['--ink-3'], CAP.a, 600, true); x += c.kw; }
  text(c.s, x, base + 1, CAP_FS, C['--ink'], CAP.a, 600);
}
// The caption for the tests: the words, the alpha and the screen box of the last frame.
function captionState() { return {k: CAP.k, s: CAP.s, a: CAP.a, box: CAP.box}; }
"""
