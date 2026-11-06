"""The text part of the canvas renderer: the name and the text of a card.

`page_canvas` joins this part after the drawing part (`page_canvas_draw`). The part
follows the rule of the maintainer in docs/design/nested-canvas.md: "Each change follows
the zoom continuously. Nothing appears at one time." Each level of detail of the text of a
card fades in and out with the size of the card:

- A name fades in from the size MIN_TEXT, at which the page starts to draw it.
- A new line of a text, a new row of a list, the fact row and the lists fade in with the
  space that they get. The text under them moves with that space, and does not jump.
- A text has a count of columns that does not change with the zoom while its font size
  follows the zoom. When the font size stays at a limit, the count of columns changes, and
  the lines of the two counts fade into each other in time (`colFade`).
- The lists change from one column to two columns with a fade (`lists`).
"""

from __future__ import annotations

TEXT = r"""
// ---- the name and the text of a card -------------------------------------------------
function title(c, x, y, w, size, alpha, extra) {
  if (size < MIN_TEXT || alpha <= 0.02) return;
  var name = fit(c.id, size, w, 600);
  text(name, x, y + size, size, C['--ink'], alpha, 600);
  if (extra && extra.alpha > 0.02) {
    var at = unitWidth(name, 600) * size + size * 0.6, small = q(size * 0.82);
    text(fit(extra.s, small, w - at, 400), x + at, y + size, small, C['--ink-3'], alpha * extra.alpha);
  }
}
// The name of each card has the same size and place, also on a card that opens a map.
// Thus the name does not move when the preview comes into view. `titleRaw` is the size
// before the rounding to half pixels, for the card height h. It grows continuously:
// - from MIN_TEXT - 0.25 at NAME_H (15 px) to MIN_TEXT + 1.5 (8.5 px) at NAME_H + 4. Over
//   this range the name fades in (`cardShow`).
// - to 9 px at a card height of 24 px. It stays at 9 px to a card height of 75 px.
// - 0.12 times the card height above that, to 26 px or less.
function titleRaw(h) {
  var fade = MIN_TEXT - 0.25 + (h - NAME_H) * 1.75 / 4, small = MIN_TEXT + 1.5 + (h - NAME_H - 4) * 0.1;
  return clamp(Math.max(Math.min(fade, small, 9), h * 0.12), 0, 26);
}
function titleSize(h) { return q(titleRaw(h)); }
function inset(h) { return clamp(h * 0.1, 3, 14); }
// The text of a card fades in from NAME_H to NAME_H + 4 of card height, as the card changes
// from a mark into a card. Thus the names do not appear at one time in a zoom. The name starts near the top of the card, and the
// text under the name starts 1.4 times the name size below that top.
function cardText(c, x, y, w, h, alpha) {
  var ur = titleRaw(h), u = q(ur), pad = inset(h), top = y + Math.max(2, h * 0.06);
  var t = alpha * cardShow(h);
  if (u < MIN_TEXT || t <= 0.02) return;
  title(c, x + pad, top, w - 2 * pad, u, t);
  top += u * 1.4;
  // While the camera moves, a card with a name below MOVE_TEXT shows only its name. While
  // the name grows from MOVE_TEXT to MOVE_TEXT + 2, the text under the name fades in.
  // Text is the largest cost of a moving frame. HIDE fades this rule in and out in time.
  details(c, x + pad, top, w - 2 * pad, y + h - pad * 0.6 - top, t * (1 - HIDE * (1 - smooth(MOVE_TEXT, MOVE_TEXT + 2, ur))), ur);
}
function facts(c) {
  var n = (c.m || []).length, parts = [];
  parts.push(c.k === 'actor' ? 'actor' : n + (n === 1 ? ' module' : ' modules'));
  parts.push(c.ins.length + ' in · ' + c.outs.length + ' out');
  if (c.as) parts.push(c.as[0] + ' · ' + c.as[1]);
  return parts.join('  ·  ');
}
// The text of a card under its name: the card text, the description, the lists and the
// fact row. Each part fades in with the space that it gets. `ur` is the size of the name
// before the rounding. The line height and the count of columns come from it, the count
// with a margin of 4 percent for the rounding of the font size. Thus the space of a part
// changes continuously, and the count does not change while the font size follows the
// zoom. The description has 4 lines or less.
function details(c, x, y, w, h, alpha, ur) {
  var u = q(ur), raw = clamp(ur * 0.78, MIN_TEXT, 19), fs = q(raw), lh = raw * 1.38, small = q(clamp(u * 0.66, MIN_TEXT, 15));
  if (h < lh * 0.9 || w < 30 || alpha <= 0.02) return;
  var fact = smooth(3, 3.5, h / lh) * smooth(90, 110, w), bottom = y + h - small * 1.7 * fact;
  var cols = 2 * w / (raw * 1.04), at = block(c, 'p', c.p, x, y, (bottom - y) / lh, 2, fs, cols, lh, C['--ink-2'], alpha);
  var room = (bottom - at) / lh, shown = alpha * smooth(7, 9, room) * smooth(150, 170, w);
  if (c.d) at = block(c, 'd', c.d, x, at + lh * 0.3, room - 1, 4, fs, cols, lh, C['--ink-3'], alpha);
  if (shown > 0.02) lists(c, x, at + lh * 0.5, w, bottom - at - lh * 0.5, fs, small, lh, shown);
  if (fact > 0) text(fit(facts(c), small, w, 400), x, y + h - small * 0.3, small, C['--ink-3'], alpha * fact);
}
// The weights of the two integer steps around a value v: [[n - 1, 1 - f], [n, f]]. The
// step n starts at the value n with the weight 0, and has the weight 1 from n + 0.5.
function steps(v, most) {
  var n = clamp(Math.floor(v), 0, most), f = n ? smooth(n, n + 0.5, v) : 1;
  return [[n - 1, 1 - f], [n, f]];
}
// Texts from more than one variant of a layout, each variant with a weight. A text that
// two variants put at the same place is drawn one time, with the sum of the weights. Thus
// a change between two variants fades, and a text that does not change keeps its alpha.
function Mix() { this.all = new Map(); }
Mix.prototype.put = function (wgt, s, x, y, size, color, weight, mono) {
  if (wgt <= 0 || !s) return;
  var key = s + '|' + x + '|' + y + '|' + size + '|' + color + '|' + weight + '|' + !!mono, e = this.all.get(key);
  if (e) e.a += wgt; else this.all.set(key, {a: wgt, t: [s, x, y, size, color, weight, mono]});
};
Mix.prototype.draw = function (alpha) {
  this.all.forEach(function (e) { var t = e.t; text(t[0], t[1], t[2], t[3], t[4], alpha * Math.min(1, e.a), t[5], t[6]); });
};
// The lines of a text in `room` lines (a fraction), `most` lines or less, in `cols` columns
// (a fraction). A new line and the change of the last line ('...') fade with the room
// (`steps`). A change of the count of columns fades in time (`colFade`). Give the y under
// the lines. It changes with the weights, thus the text under it does not jump.
function block(c, name, s, x, y, room, most, fs, cols, lh, color, alpha) {
  if (!s || room < 1) return y;
  var k = Math.floor(cols), g = colFade(c, name, k), mix = new Mix(), used = 0;
  steps(room, most).forEach(function (n) {
    [[g.from, 1 - g.f], [k, g.f]].forEach(function (w) {
      var wgt = n[1] * w[1];
      if (wgt <= 0 || n[0] < 1) return;
      var list = wrap(c, name, s, fs, w[0], n[0], 400);
      used += wgt * list.length;
      list.forEach(function (line, i) { mix.put(wgt, line, x, y + fs + i * lh, fs, color, 400); });
    });
  });
  mix.draw(alpha);
  return y + used * lh;
}
// The count of columns of a text of a card goes from `from` to `k`, with the weight `f` of
// `k`. When the count changes, the weight goes from 0 to 1 at the speed of HIDE (`toward`).
// A change of the count occurs when the font size stays at a limit while the card grows or
// becomes smaller. The text of an image of a map (`drawSlice`) has no fade. A card that the
// frame before did not draw starts again with no fade (`at`).
function colFade(c, name, k) {
  if (ctx !== PAGE_CTX && ctx !== STILL_CTX) return {from: k, f: 1};
  var key = '_cols' + name, st = c[key];
  if (!st || st.at < drawn - 1) st = c[key] = {k: k, from: k, f: 1};
  st.at = drawn;
  if (st.k !== k) { st.from = st.f >= 0.5 ? st.k : st.from; st.k = k; st.f = 0; }
  st.f = toward(st.f, 1, SPEED_STEP);
  return st;
}
// The lists of flows and modules, in one column, or in two columns on a wide card. A new
// row fades in with the room (`steps`), and the change from one column to two columns
// fades from a width of 320 px to 360 px.
function lists(c, x, y, w, h, fs, small, lh, alpha) {
  if (alpha <= 0.02) return;
  var flows = c.outs.map(function (f) { return 'to ' + f.t + ' · ' + f.a; })
    .concat(c.ins.map(function (f) { return 'from ' + f.s + ' · ' + f.a; }));
  var mods = (c.m || []).concat(c.u || []), two = smooth(320, 360, w), mix = new Mix();
  steps(h / lh, Infinity).forEach(function (r) {
    if (r[0] >= 2) { layout(r[0], false, r[1] * (1 - two)); layout(r[0], true, r[1] * two); }
  });
  mix.draw(alpha);
  function layout(rows, wide, wgt) {
    if (wgt <= 0) return;
    var cw = wide ? (w - fs) / 2 : w, first = Math.min(rows, Math.max(2, Math.ceil(rows / 2)));
    if (wide) {
      list('FLOWS', flows, x, y, rows, false);
      list('MODULES', mods, x + cw + fs, y, rows, true);
      return;
    }
    list('FLOWS', flows, x, y, first, false);
    list('MODULES', mods, x, y + first * lh, rows - first, true);
    function list(name, items, lx, ly, n, mono) {
      if (n < 2) return;
      mix.put(wgt, name, lx, ly + small, small, C['--ink-3'], 600);
      if (!items.length) { mix.put(wgt, 'none', lx, ly + small + lh, fs, C['--ink-3'], 400); return; }
      var fitN = items.length <= n - 1 ? items.length : n - 2;
      for (var i = 0; i < fitN; i++) mix.put(wgt, fit(items[i], fs, cw, 400, mono), lx, ly + small + (i + 1) * lh, fs, C['--ink-2'], 400, mono);
      if (fitN < items.length) mix.put(wgt, '+ ' + (items.length - fitN) + ' more', lx, ly + small + (fitN + 1) * lh, fs, C['--ink-3'], 400);
    }
  }
}
"""
