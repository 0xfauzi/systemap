// The browser part of tests/test_atlas_page_layout_browser.py: the layout of a nested map on
// the atlas page at the fit.
//
//     node atlas_layout.js PAGE.html MAP
//
// At 1440 x 900, a load with the hash of the map MAP. For each layer tab: the labels at
// rest (flow index and text), the laned points of each line (map units), and the screen
// boxes of the cards with their kinds. Also the screen box of the frame of the map at the
// fit, the box of the headline, the width of the screen and the text of the zoom control.
// The output is one JSON object. `errors` has the script errors of the page.
'use strict';
const { chromium } = require('playwright');

(async () => {
  const [file, map] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + file + '#' + map);
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await page.waitForTimeout(900);
  const out = await page.evaluate(async (id) => {
    const s = window.systemapCanvas;
    const ask = document.getElementById('atlas-ask').getBoundingClientRect();
    const zoom = [...document.querySelectorAll('button, span, output, div')]
      .map((e) => e.childElementCount ? '' : e.textContent.trim()).find((t) => /^\d+%$/.test(t)) || null;
    const res = { current: s.current(), frame: s.frame(id), ask: [ask.left, ask.top, ask.width, ask.height],
      width: window.innerWidth, zoom, cards: s.boxes(id), layers: [] };
    const tabs = [...document.querySelectorAll('#atlas-tabs [data-layer]')].map((b) => b.dataset.layer);
    for (const layer of tabs) {
      s.setLayer(layer);
      await new Promise((r) => setTimeout(r, 400));
      const L = s.lines(id);
      res.layers.push({ id: layer, n: L.n, dense: L.dense, labels: L.labels.map((l) => ({ f: l.f, s: l.s })),
        lanes: L.lanes });
    }
    return res;
  }, map);
  out.errors = errors;
  console.log(JSON.stringify(out));
  await browser.close();
})();
