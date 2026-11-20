// The browser part of tests/test_atlas_names_browser.py: the card names of the atlas page at
// the fit and at each zoom ZOOM.
//
//     node atlas_names.js PAGE.html ZOOM...
//
// At 1440 x 900, the names that the page draws for the cards of the top map: at the fit, and
// then for each zoom, with each card in the middle of the screen. Also the width of each
// character from 32 to 126 in the page font at weight 600 and 100 px, with no kerning.
// The output is one JSON object. `errors` has the script errors of the page.
'use strict';
const { chromium } = require('playwright');

(async () => {
  const [file, ...zooms] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + file);
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await page.waitForTimeout(600);
  const out = await page.evaluate((ks) => {
    const s = window.systemapCanvas, id = s.current(), names = (l) => l.map((t) => t.s);
    const g = document.createElement('canvas').getContext('2d');
    g.font = '600 100px "systemap Inter"'; g.fontKerning = 'none';
    const widths = [];
    for (let c = 32; c < 127; c++) widths.push(g.measureText(String.fromCharCode(c)).width);
    const fit = s.fit(), res = { cards: s.boxes(id).map((c) => c.id), fit: names(s.texts()), widths, zooms: [] };
    for (const k of ks.map(Number)) {
      for (const c of s.boxes(id)) {
        s.view(fit);
        const b = s.box(id, c.id), cx = fit.x + (b[0] + b[2] / 2) / fit.k, cy = fit.y + (b[1] + b[3] / 2) / fit.k;
        s.view({ x: cx - innerWidth / 2 / k, y: cy - innerHeight / 2 / k, k });
        res.zooms.push({ k, card: c.id, texts: names(s.texts()) });
      }
    }
    return res;
  }, zooms);
  out.errors = errors;
  console.log(JSON.stringify(out));
  await browser.close();
})();
