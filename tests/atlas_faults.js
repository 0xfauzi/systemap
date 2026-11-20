// The browser part of tests/test_atlas_faults_browser.py.
//
//     node atlas_faults.js MODE PAGE.html
//
// PAGE is the atlas page of the fixture of the test. MODE selects the measurement:
// - sheet: on a phone of 390 x 844 px, in the All layer, for each card of the top map that
//   is not an actor: select it, and give the box of the visible headline (null when it does
//   not show), the boxes of the cards, the box of the selected card, the bottom of the bars
//   at the top and the top of the sheet.
// - keys: at 1440 x 900, the elements that get the keyboard focus with Tab from the canvas
//   until the focus comes back to the first element of the page, and the current map and
//   the selected card after a click on the link of the list of the neighbour Auth of the
//   nested map Orchestration.
// The driver gives one JSON object. `errors` has the script errors of the page.
'use strict';
const { chromium } = require('playwright');

const WIDE = { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 };
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

async function keys(browser, file) {
  const { page, errors } = await open(browser, file, WIDE);
  await page.focus('#canvas');
  const seen = [];
  for (let i = 0; i < 200; i++) {
    await page.keyboard.press('Tab');
    const at = await page.evaluate(() => {
      const e = document.activeElement, tree = document.getElementById('atlas-tree');
      return { tag: e.tagName, id: e.id, text: (e.getAttribute('aria-label') || e.textContent || '').trim().slice(0, 40), tree: tree.contains(e) };
    });
    // The focus comes back to an element that it had before: the order starts again.
    const again = seen.some((x) => x.tag === at.tag && x.id === at.id && x.text === at.text && x.tag !== 'CANVAS');
    seen.push(at);
    if (again) break;
  }
  const link = await page.evaluate(() => {
    const S = window.systemapCanvas, oi = S.maps().findIndex((m) => m.id === 'Orchestration');
    const a = [...document.querySelectorAll('#atlas-tree a[data-m="' + oi + '"][data-c]')].find((x) => x.textContent === 'Auth');
    if (!a) return null;
    const href = a.getAttribute('href');
    a.click();
    return { href, tabindex: a.getAttribute('tabindex') };
  });
  await page.waitForTimeout(1500);
  const after = await page.evaluate(() => ({ current: window.systemapCanvas.current(), sel: window.systemapCanvas.side().sel, hash: location.hash }));
  await page.close();
  return { seen, link, after, errors };
}

(async () => {
  const [mode, file] = process.argv.slice(2);
  const browser = await chromium.launch();
  const modes = { sheet, keys };
  const out = await modes[mode](browser, file);
  await browser.close();
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { process.stderr.write(String(e && e.stack || e)); process.exit(1); });
