// The browser part of t0_steps.py (C2): the step labels of the Sequences view on the map
// that cross the edge of a region or of a surface, at 1440 x 900.
//
//     node t0_steps.js PAGE.html
//
// The page must be a T0 page (t0_common.py, `window.__T0`). With reduced motion the camera
// goes to each step at once. For each map with sequences, each sequence and each step (-1
// is the whole route), the driver reads the labels that show in that frame. For each label
// that crosses an edge, it searches the full line of the label for a place that is on one
// ground: at each half unit of each part of the line, on the line and beside it (the box
// touches the line, as `near` in `atlas_lines`). A place must be on no box of `walls` (the
// cards, the names, the sides of the map and the edges) and on no other label of the frame
// (`free`). `clean` also has no other line through the box.
'use strict';
const { chromium } = require('playwright');

function frame(args) {
  const [id, k, n] = args;
  const T = window.__T0, m = T.MAPS[id], layer = T.shownLayer(m), v = T.view(m), L = T.linesOf(m, layer);
  const S = T.seatsOf(m, layer, v.a);
  const wall = T.walls(m), edges = m._walls.slice(m._walls0.length);
  const shown = (S ? S.list : []).filter((x) => !x.hide || ['now', 'was'].includes(T.stepState(m, x.e.f.i)));
  const out = { layer, a: v.a, labels: shown.length, hidden: (S ? S.list : []).filter((x) => x.hide).length, cross: [] };
  shown.forEach((x) => {
    if (!edges.some((b) => T.over(x.box, b))) return;
    const w = x.box[2] - x.box[0], hh = x.box[3] - x.box[1], q = x.e.q;
    const taken = shown.filter((o) => o !== x).map((o) => o.box);
    let free = 0, clean = 0, places = 0;
    for (let i = 0; i + 1 < q.length; i++) {
      const a = q[i], b = q[i + 1], len = T.segLen(q, i), flat = Math.abs(a[1] - b[1]) < 0.01;
      for (let t = 0; t <= len; t += 0.5) {
        const u = len ? t / len : 0, cx = a[0] + (b[0] - a[0]) * u, cy = a[1] + (b[1] - a[1]) * u;
        const d = flat ? hh / 2 + 2 : w / 2 + 2;
        const at = [[cx, cy], flat ? [cx, cy - d] : [cx - d, cy], flat ? [cx, cy + d] : [cx + d, cy]];
        at.forEach(([px, py]) => {
          const box = [px - w / 2, py - hh / 2, px + w / 2, py + hh / 2];
          places++;
          if (wall.some((c) => T.over(box, c)) || taken.some((c) => T.over(box, c))) return;
          free++;
          if (!T.crossed(box, L.list, x.e)) clean++;
        });
      }
    }
    out.cross.push({ f: x.e.f.i, s: x.e.s, hide: !!x.hide, places, free, clean });
  });
  return out;
}

(async () => {
  const [file] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1, reducedMotion: 'reduce' });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + file);
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await page.waitForTimeout(600);
  const maps = await page.evaluate(() => window.__T0.ORDER.filter((m) => m.sq && m.sq.length).map((m) => ({ id: m.id, sq: m.sq.map((j) => ({ n: j.n, steps: j.s.length })) })));
  const out = { errors, maps: [] };
  await page.evaluate(() => window.systemapCanvas.mode('seq'));
  for (const m of maps) {
    const one = { id: m.id, seqs: [] };
    for (let k = 0; k < m.sq.length; k++) {
      await page.evaluate(([id, k]) => window.systemapCanvas.choose(id, k), [m.id, k]);
      await page.waitForTimeout(500);
      const steps = [];
      for (let n = -1; n < m.sq[k].steps; n++) {
        await page.evaluate((n) => window.systemapCanvas.step(n), n);
        await page.waitForTimeout(450);
        steps.push({ n, ...(await page.evaluate(frame, [m.id, k, n])) });
      }
      one.seqs.push({ k, n: m.sq[k].n, steps });
    }
    out.maps.push(one);
  }
  out.errors = errors;
  console.log(JSON.stringify(out));
  await browser.close();
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
