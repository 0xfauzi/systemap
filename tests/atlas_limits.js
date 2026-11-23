// The browser part of tests/test_atlas_limits_browser.py: the disclosure "Not in this
// comparison" of a compared atlas page.
//
//     node atlas_limits.js PAGE.html
//
// At 1440 x 900 and 390 x 844, in the light and the dark scheme: the order of the keyboard
// focus from the start of the page to the summary of the disclosure, Enter on the summary,
// the boxes of the open disclosure, the disclosure in the Focus view and again in the Map
// view, and axe-core (from NODE_PATH; null when it is not there) with the disclosure open.
// It prints one JSON object. `errors` has the script errors of the page.
'use strict';
const fs = require('fs');
const { chromium } = require('playwright');

const WIDE = { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, reducedMotion: 'reduce' };
const PHONE = { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, hasTouch: true, isMobile: true, reducedMotion: 'reduce' };

function axeSource() {
  try { return fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8'); } catch (e) { return null; }
}

const box = (sel) => {
  const e = document.querySelector(sel);
  if (!e || !e.getClientRects().length) return null;
  const r = e.getBoundingClientRect();
  return { left: r.left, top: r.top, right: r.right, bottom: r.bottom };
};

const where = () => {
  const a = document.activeElement;
  if (!a) return null;
  if (a.closest && a.closest('#atlas-limits')) return 'limits';
  return a.id || a.tagName;
};

async function sizeRun(browser, file, opts, scheme, source) {
  const ctx = await browser.newContext({ ...opts, colorScheme: scheme, bypassCSP: true });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + file);
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await page.waitForTimeout(500);
  const run = { scheme, width: opts.viewport.width, errors, order: [] };
  for (let i = 0; i < 60; i += 1) {
    await page.keyboard.press('Tab');
    const at = await page.evaluate(where);
    run.order.push(at);
    if (at === 'limits') break;
  }
  run.summary = await page.evaluate(box, '#atlas-limits summary');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(300);
  run.open = await page.evaluate(() => document.getElementById('atlas-limits').open);
  run.text = await page.evaluate(() => document.querySelector('#atlas-limits > div').innerText);
  run.body = await page.evaluate(box, '#atlas-limits > div');
  run.tabs = await page.evaluate(box, '#atlas-tabs');
  run.question = await page.evaluate(box, '#atlas-ask-q');
  run.scroll = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  if (source) {
    await page.addScriptTag({ content: source });
    run.axe = await page.evaluate(async () => {
      const r = await window.axe.run(document, { resultTypes: ['violations'] });
      return r.violations.map((v) => v.impact + ' ' + v.id + ': ' + v.nodes.map((n) => n.target.join(' ')).join(', '));
    });
  }
  const focus = await page.$('.views button[data-mode="focus"]');
  run.hasFocus = Boolean(focus);
  if (focus) {
    await focus.click();
    await page.waitForTimeout(400);
    run.inFocus = await page.evaluate(box, '#atlas-limits');
    await page.click('.views button[data-mode="map"]');
    await page.waitForTimeout(400);
    run.back = await page.evaluate(box, '#atlas-limits');
  }
  await ctx.close();
  return run;
}

(async () => {
  const [file] = process.argv.slice(2);
  const browser = await chromium.launch();
  const source = axeSource();
  const runs = [];
  try {
    for (const scheme of ['light', 'dark']) {
      for (const opts of [WIDE, PHONE]) runs.push(await sizeRun(browser, file, opts, scheme, source));
    }
  } finally { await browser.close(); }
  process.stdout.write(JSON.stringify({ axe: source !== null, runs }));
})().catch((e) => { process.stderr.write(String(e && e.stack || e)); process.exit(1); });
