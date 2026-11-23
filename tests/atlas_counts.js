// The browser part of tests/test_atlas_counts_browser.py: the counts of the headline of each
// layer and of the Focus view of the atlas page.
//
//     node atlas_counts.js PAGE.html CARD
//
// The script gives the counts of the headline for each tab of the top map, then opens the
// Focus view on CARD and gives the counts of its headline and the words of the live region.
// The output is one JSON object. `errors` has the script errors of the page.
'use strict';
const { chromium } = require('playwright');

(async () => {
  const [file, card] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + file);
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await page.waitForTimeout(500);
  const out = { errors, layers: {} };
  const tabs = (await page.evaluate(() => window.systemapCanvas.viewState())).tabs;
  for (const tab of tabs) {
    await page.evaluate((t) => window.systemapCanvas.setLayer(t), tab.id);
    await page.waitForTimeout(400);
    out.layers[tab.id] = await page.evaluate(() => window.systemapCanvas.viewState().counts);
  }
  await page.evaluate(() => window.systemapCanvas.mode('focus'));
  out.chosen = await page.evaluate((id) => window.systemapCanvas.focusOn('', id), card);
  await page.waitForTimeout(600);
  out.focus = await page.evaluate(() => ({ counts: window.systemapCanvas.viewState().counts, said: document.getElementById('atlas-said').textContent }));
  console.log(JSON.stringify(out));
  await browser.close();
})();
