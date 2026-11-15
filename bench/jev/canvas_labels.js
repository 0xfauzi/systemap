// L1 (bench/jev/canvas_labels.py): the flow labels of a canvas page at the fit and at the
// zoom 1, for each layer and screen size. Prints one JSON list of rows.
//
//     node bench/jev/canvas_labels.js PAGE.html
'use strict';
const { chromium } = require('playwright');

const SCREENS = [[1440, 900], [1366, 768], [1280, 720]];
const TOL = 2;

// The values of the current frame: the labels (texts with the weight 500), their plates,
// and the counts of plates that go into a card or into a different plate.
const read = (page, tol) => page.evaluate((tol) => {
  const S = window.systemapCanvas, view = S.viewState();
  const data = JSON.parse(document.getElementById('canvas-data').textContent).maps[0];
  const layer = data.layers.find((l) => l.id === view.layer);
  const flows = (layer ? layer.e : data.flows.map((f, i) => i)).map((i) => data.flows[i]);
  const labels = S.texts().filter((t) => t.weight === 500);
  const plates = labels.map((t) => {
    const cx = (t.box[0] + t.box[2]) / 2, cy = (t.box[1] + t.box[3]) / 2, w = t.box[2] - t.box[0] + 6, h = t.size * 1.5;
    return [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2];
  });
  const into = (a, b) => Math.min(a[2], b[2]) - Math.max(a[0], b[0]) > tol && Math.min(a[3], b[3]) - Math.max(a[1], b[1]) > tol;
  const cards = S.boxes('').map((c) => [c.b[0], c.b[1], c.b[0] + c.b[2], c.b[1] + c.b[3]]);
  let inCard = 0, inPlate = 0;
  plates.forEach((p, i) => {
    if (cards.some((c) => into(p, c))) inCard++;
    for (let j = i + 1; j < plates.length; j++) if (into(p, plates[j])) inPlate++;
  });
  const full = labels.filter((t) => t.alpha >= 0.99);
  return {
    zoom: S.camera().k, boxed: flows.filter((f) => f.lb).length, drawn: labels.length, full: full.length,
    min_size: full.length ? Math.min(...full.map((t) => t.size)) : null, in_card: inCard, in_plate: inPlate,
    alpha: labels.length ? Math.min(...labels.map((t) => t.alpha)) : 0, size: labels.length ? Math.min(...labels.map((t) => t.size)) : 0,
  };
}, tol);

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
      for (const at of ['fit', 'zoom 1']) {
        await page.evaluate(([layer, at]) => {
          const S = window.systemapCanvas, f = S.fit('');
          S.setView('map', layer);
          if (at === 'fit') S.view(f);
          else S.view({ x: f.x + innerWidth / 2 / f.k - innerWidth / 2, y: f.y + innerHeight / 2 / f.k - innerHeight / 2, k: 1 });
        }, [layer, at]);
        await page.waitForTimeout(350);
        rows.push(Object.assign({ screen: width + 'x' + height, layer, at }, await read(page, TOL)));
      }
    }
    if (errors.length) { console.error(errors.join('\n')); process.exit(1); }
    await context.close();
  }
  await browser.close();
  console.log(JSON.stringify(rows));
})().catch((e) => { console.error(e); process.exit(1); });
