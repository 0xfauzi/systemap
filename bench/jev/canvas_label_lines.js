// L2 (bench/jev/canvas_label_lines.py): the flow labels and the lines of other flows at
// the fit, for each layer and screen size. Prints one JSON list of rows.
//
//     node bench/jev/canvas_label_lines.js PAGE.html
'use strict';
const { chromium } = require('playwright');

const SCREENS = [[1440, 900], [1600, 900], [1366, 768]];

const read = (page) => page.evaluate(() => {
  const S = window.systemapCanvas, view = S.viewState(), cam = S.camera();
  const data = JSON.parse(document.getElementById('canvas-data').textContent).maps[0];
  const layer = data.layers.find((l) => l.id === view.layer);
  const flows = (layer ? layer.e : data.flows.map((f, i) => i)).map((i) => data.flows[i]);
  const X = (x) => (x - cam.x) * cam.k, Y = (y) => (y - cam.y) * cam.k;
  const segs = (f) => f.p.slice(1).map((p, i) => [X(f.p[i][0]), Y(f.p[i][1]), X(p[0]), Y(p[1])]);
  // The distance between a box x0, y0, x1, y1 and a segment with no slope or no run.
  const gap = (b, s) => {
    const sx0 = Math.min(s[0], s[2]), sx1 = Math.max(s[0], s[2]), sy0 = Math.min(s[1], s[3]), sy1 = Math.max(s[1], s[3]);
    const dx = Math.max(0, b[0] - sx1, sx0 - b[2]), dy = Math.max(0, b[1] - sy1, sy0 - b[3]);
    return Math.hypot(dx, dy);
  };
  const labels = S.texts().filter((t) => t.weight === 500 && t.alpha > 0.5);
  let shift = 0, crossed = 0, lines = 0, far = 0, near = 0;
  const which = [];
  const own = labels.map((t) => {
    const cx = (t.box[0] + t.box[2]) / 2, cy = (t.box[1] + t.box[3]) / 2;
    let best = null, d = Infinity;
    flows.forEach((f) => {
      if (!f.lb || f.a !== t.s) return;
      const e = Math.hypot(X(f.lb[0] + f.lb[2] / 2) - cx, Y(f.lb[1] + f.lb[3] / 2) - cy);
      if (e < d) { d = e; best = f; }
    });
    shift = Math.max(shift, best ? d : 999);
    return best;
  });
  labels.forEach((t, i) => {
    const b = t.box, small = [b[0] + 1, b[1] + 1, b[2] - 1, b[3] - 1];
    const through = flows.filter((f) => f !== own[i] && segs(f).some((s) => gap(small, s) === 0));
    if (through.length) { crossed++; lines += through.length; which.push('crossed: ' + t.s + ' <- ' + through.map((f) => f.s + '->' + f.t).join(', ')); }
    if (own[i] && Math.min(...segs(own[i]).map((s) => gap(b, s))) > 4) { far++; which.push('far: ' + t.s); }
    for (let j = i + 1; j < labels.length; j++) {
      const c = labels[j].box;
      if (Math.max(b[0], c[0]) - Math.min(b[2], c[2]) < 4 && Math.max(b[1], c[1]) - Math.min(b[3], c[3]) < 4) { near++; which.push('near: ' + t.s + ' | ' + labels[j].s); }
    }
  });
  return { zoom: cam.k, labels: labels.length, crossed, lines, far, near, shift, which };
});

(async () => {
  const browser = await chromium.launch();
  const rows = [];
  for (const [width, height] of SCREENS) {
    const context = await browser.newContext({ viewport: { width, height }, reducedMotion: 'reduce' });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('file://' + require('path').resolve(process.argv[2]));
    await page.waitForFunction(() => window.systemapCanvas && document.fonts.status === 'loaded');
    await page.waitForTimeout(400);
    const layers = await page.evaluate(() => JSON.parse(document.getElementById('canvas-data').textContent).maps[0].layers.filter((l) => l.e.length).map((l) => l.id));
    for (const layer of layers.concat(['all'])) {
      await page.evaluate((layer) => { const S = window.systemapCanvas; S.setView('map', layer); S.view(S.fit('')); }, layer);
      await page.waitForTimeout(350);
      rows.push(Object.assign({ screen: width + 'x' + height, layer }, await read(page)));
    }
    if (errors.length) { console.error(errors.join('\n')); process.exit(1); }
    await context.close();
  }
  await browser.close();
  console.log(JSON.stringify(rows));
})().catch((e) => { console.error(e); process.exit(1); });
