// The browser part of t0_context.py (C1): the lines of the System context layer of the top
// map between the actor column and the system frame, at the fit of 1440 x 900.
//
//     node t0_context.js PAGE.html
//
// The page must be a T0 page (t0_common.py, `window.__T0`). The output is one JSON object:
// the fit, the size of the map, the count of the labels at rest in each layer tab, and for
// the layer "system": the band, the parallel pairs, the crossings and the labels in the band
// (`system`: the actors at the left of the frame, `below`: the actors below the frame).
'use strict';
const { chromium } = require('playwright');

function measure(side) {
  const T = window.__T0, s = window.systemapCanvas, m = T.MAPS[''], L = T.linesOf(m, 'system'), v = T.view(m), a = v.a;
  const out = { side, a, n: L.n, dense: L.dense, actorsAll: m.cards.filter((c) => c.k === 'actor').length };
  const inBox = (c, b) => c.b[0] >= b[0] - 0.5 && c.b[1] >= b[1] - 0.5 && c.b[0] + c.b[2] <= b[0] + b[2] + 0.5 && c.b[1] + c.b[3] <= b[1] + b[3] + 0.5;
  let frame = null, most = 0;
  m.boxes.forEach((b) => { const k = m.cards.filter((c) => c.k !== 'actor' && inBox(c, b.b)).length; if (k > most) { most = k; frame = b; } });
  out.frame = frame ? { id: frame.id, b: frame.b } : null;
  if (!frame) return out;
  // The band: between the actors at the left of the frame and its left edge (axis x), or
  // between its bottom edge and the actors below it (axis y).
  const f = frame.b, ax = side === 'left' ? 0 : 1;
  const actors = m.cards.filter((c) => c.k === 'actor' && (side === 'left' ? c.b[0] + c.b[2] <= f[0] : c.b[1] >= f[1] + f[3]));
  out.actors = actors.length;
  out.axis = actors.length ? ax : -1;
  if (!actors.length) return out;
  const lo = side === 'left' ? Math.max(...actors.map((c) => c.b[0] + c.b[2])) : f[1] + f[3];
  const hi = side === 'left' ? f[0] : Math.min(...actors.map((c) => c.b[1]));
  out.band = [lo, hi];
  const P = (p) => (ax === 0 ? p : [p[1], p[0]]);
  const V = [], H = [];
  L.list.forEach((e, n) => {
    for (let i = 0; i + 1 < e.q.length; i++) {
      const p = P(e.q[i]), r = P(e.q[i + 1]);
      if (Math.abs(p[0] - r[0]) < 0.01) {
        if (p[0] > lo + 0.01 && p[0] < hi - 0.01 && Math.abs(p[1] - r[1]) > 0.01) V.push({ n, x: p[0], y0: Math.min(p[1], r[1]), y1: Math.max(p[1], r[1]) });
      } else if (Math.abs(p[1] - r[1]) < 0.01) {
        const x0 = Math.max(lo, Math.min(p[0], r[0])), x1 = Math.min(hi, Math.max(p[0], r[0]));
        if (x1 - x0 > 0.5) H.push({ n, y: p[1], x0, x1 });
      }
    }
  });
  const pairs = [];
  for (let i = 0; i < V.length; i++) for (let j = i + 1; j < V.length; j++) {
    const u = V[i], w = V[j];
    if (u.n !== w.n && Math.min(u.y1, w.y1) - Math.max(u.y0, w.y0) > 0.5) pairs.push({ kind: 'across', d: Math.abs(u.x - w.x) * a, f: [L.list[u.n].f.i, L.list[w.n].f.i] });
  }
  for (let i = 0; i < H.length; i++) for (let j = i + 1; j < H.length; j++) {
    const u = H[i], w = H[j];
    if (u.n !== w.n && Math.min(u.x1, w.x1) - Math.max(u.x0, w.x0) > 0.5) pairs.push({ kind: 'along', d: Math.abs(u.y - w.y) * a, f: [L.list[u.n].f.i, L.list[w.n].f.i] });
  }
  let cross = 0;
  V.forEach((u) => H.forEach((w) => { if (u.n !== w.n && w.y > u.y0 + 0.01 && w.y < u.y1 - 0.01 && u.x > w.x0 + 0.01 && u.x < w.x1 - 0.01) cross++; }));
  const lines = new Set([...V, ...H].map((x) => x.n));
  out.lines = lines.size;
  out.tracks = new Set(V.map((u) => Math.round(u.x * 10) / 10)).size;
  out.vertical = V.length; out.horizontal = H.length;
  out.pairs = pairs.map((p) => p.d).sort((x, y) => x - y);
  out.near = pairs.filter((p) => p.d < 10).sort((x, y) => x.d - y.d);
  out.pairKinds = { across: pairs.filter((p) => p.kind === 'across').length, along: pairs.filter((p) => p.kind === 'along').length };
  out.crossings = cross;
  // The labels at rest with a box in the band.
  const seats = T.seatsOf(m, 'system', a);
  const segD = (x, y, q) => {
    let best = Infinity;
    for (let i = 0; i + 1 < q.length; i++) {
      const [x0, y0] = q[i], [x1, y1] = q[i + 1], dx = x1 - x0, dy = y1 - y0, l = dx * dx + dy * dy;
      const t = l ? Math.max(0, Math.min(1, ((x - x0) * dx + (y - y0) * dy) / l)) : 0;
      best = Math.min(best, Math.hypot(x - x0 - t * dx, y - y0 - t * dy));
    }
    return best;
  };
  // The distance of a box to a line: 0 when the line goes through the box.
  const boxD = (b, q) => {
    let best = Infinity;
    for (let i = 0; i + 1 < q.length; i++) {
      const xa = Math.min(q[i][0], q[i + 1][0]), xb = Math.max(q[i][0], q[i + 1][0]), ya = Math.min(q[i][1], q[i + 1][1]), yb = Math.max(q[i][1], q[i + 1][1]);
      const dx = Math.max(0, xa - b[2], b[0] - xb), dy = Math.max(0, ya - b[3], b[1] - yb);
      best = Math.min(best, Math.hypot(dx, dy));
    }
    return best;
  };
  out.labels = [];
  (seats ? seats.list : []).forEach((x) => {
    const b = P([x.box[0], x.box[1]]), c = P([x.box[2], x.box[3]]);
    if (Math.max(b[0], c[0]) <= lo || Math.min(b[0], c[0]) >= hi) return;
    let other = Infinity, otherBox = Infinity, who = null;
    L.list.forEach((e) => {
      if (e === x.e) return;
      const d = segD(x.x, x.y, e.q);
      if (d < other) { other = d; who = e.f.i; }
      otherBox = Math.min(otherBox, boxD(x.box, e.q));
    });
    out.labels.push({ f: x.e.f.i, s: x.e.s, own: segD(x.x, x.y, x.e.q) * a, other: other * a, otherBox: otherBox * a, near: who, h: (x.box[3] - x.box[1]) * a });
  });
  out.labelsAll = seats ? seats.list.length : 0;
  return out;
}

(async () => {
  const [file] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + file);
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await page.waitForTimeout(800);
  const head = await page.evaluate(() => {
    const s = window.systemapCanvas, m = window.__T0.MAPS[''];
    const zoom = document.getElementById('atlas-zoom-v') ? document.getElementById('atlas-zoom-v').textContent : null;
    return { fit: s.fit(''), frame: s.frame(''), size: m.size, width: innerWidth, zoom, tabs: s.viewState().tabs.map((t) => t.id) };
  });
  const out = { errors, ...head, perTab: {} };
  for (const tab of head.tabs) {
    await page.evaluate((id) => window.systemapCanvas.setLayer(id), tab);
    await page.waitForTimeout(500);
    out.perTab[tab] = await page.evaluate(() => window.systemapCanvas.lines('').labels.length);
  }
  if (head.tabs.includes('system')) {
    await page.evaluate(() => window.systemapCanvas.setLayer('system'));
    await page.waitForTimeout(600);
    out.system = await page.evaluate(measure, 'left');
    out.below = await page.evaluate(measure, 'below');
  } else out.system = null;
  out.errors = errors;
  console.log(JSON.stringify(out));
  await browser.close();
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
