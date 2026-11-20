// The browser part of tests/test_atlas_faults_browser.py.
//
//     node atlas_faults.js MODE PAGE.html
//
// PAGE is the atlas page of the fixture of the test. MODE selects the measurement:
// - sheet: on a phone of 390 x 844 px, in the All layer, for each card of the top map that
//   is not an actor: select it, and give the box of the visible headline (null when it does
//   not show), the boxes of the cards, the box of the selected card, the bottom of the bars
//   at the top and the top of the sheet.
// The driver gives one JSON object. `errors` has the script errors of the page.
'use strict';
const { chromium } = require('playwright');

const PHONE = { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, hasTouch: true, isMobile: true };

async function open(browser, file, opts) {
  const page = await browser.newPage(opts);
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + file);
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await page.waitForTimeout(500);
  return { page, errors };
}

async function sheet(browser, file) {
  const { page, errors } = await open(browser, file, PHONE);
  await page.evaluate(() => window.systemapCanvas.setLayer('all'));
  const ids = await page.evaluate(() => window.systemapCanvas.boxes('').filter((c) => c.k !== 'actor').map((c) => c.id));
  const runs = [];
  for (const id of ids) {
    await page.evaluate((x) => window.systemapCanvas.select('', x), id);
    await page.waitForTimeout(1300);
    runs.push(await page.evaluate((x) => {
      const S = window.systemapCanvas, ask = document.getElementById('atlas-ask');
      const r = ask.getBoundingClientRect(), shown = getComputedStyle(ask).visibility === 'visible' && r.height > 0;
      const bars = ['atlas-head', 'atlas-tabs', 'atlas-inside'].map((n) => document.getElementById(n))
        .filter((e) => e && !e.hidden && getComputedStyle(e).display !== 'none')
        .reduce((b, e) => Math.max(b, e.getBoundingClientRect().bottom), 0);
      return {
        id: x, selected: S.side().sel && S.side().sel.id, ask: shown ? [r.left, r.top, r.right, r.bottom] : null,
        cards: S.boxes(''), box: S.box('', x), bars, sheet: S.side().top,
      };
    }, id));
  }
  await page.close();
  return { runs, errors };
}

(async () => {
  const [mode, file] = process.argv.slice(2);
  const browser = await chromium.launch();
  const modes = { sheet };
  const out = await modes[mode](browser, file);
  await browser.close();
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { process.stderr.write(String(e && e.stack || e)); process.exit(1); });
