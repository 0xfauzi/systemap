// The browser part of bench/jev/atlas_page_phone.py: the fit of a nested map on the atlas
// page at one screen size.
//
//     node atlas_page_phone.js PAGE.html MAP WIDTH HEIGHT [SCREENSHOT.png]
//
// After a load with the hash of the map MAP: the text of the zoom control, the screen box
// of the frame of the map, the size of the screen and the screen box of each card of the
// map. The output is one JSON object. `errors` has the script errors of the page.
'use strict';
const { chromium } = require('playwright');

(async () => {
  const [file, map, w, h, shot] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: +w, height: +h }, deviceScaleFactor: 2 });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + file + '#' + map);
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await page.waitForTimeout(1200);
  const out = await page.evaluate((id) => {
    const s = window.systemapCanvas;
    const zoom = [...document.querySelectorAll('button, span, output, div')]
      .map((e) => e.childElementCount ? '' : e.textContent.trim()).find((t) => /^\d+%$/.test(t)) || null;
    return { zoom, frame: s.frame(id), width: innerWidth, height: innerHeight, cards: s.boxes(id) };
  }, map);
  if (shot) await page.screenshot({ path: shot });
  out.errors = errors;
  console.log(JSON.stringify(out));
  await browser.close();
})();
