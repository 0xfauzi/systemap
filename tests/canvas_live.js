// Opens the canvas page of `systemap live` (systemap.serve) in the Chromium of Playwright
// and prints one JSON object. tests/test_canvas_live.py reads it.
//
//     node tests/canvas_live.js URL HASH FLAG
//
// The driver opens URL with HASH. Then it asks the server for a new version
// (POST /refresh) and waits for the load of the new version. Then it writes the file FLAG,
// which makes the next render fail, asks for one more version, and waits for the notice of
// the failed render. It gives the loads of the page with the hash and the map chain after
// each load, the event connections of each load, the policy violations, the script errors,
// the requests outside the origin of URL, and the text of the notice.
'use strict';
const fs = require('fs');
const { chromium } = require('playwright');

async function refresh(page, url) {
  const res = await page.request.post(new URL('/refresh', url).href);
  if (res.status() !== 202) throw new Error('refresh gave ' + res.status());
}

(async () => {
  const [url, hash, flag] = process.argv.slice(2);
  const origin = new URL(url).origin;
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
  const out = { loads: [], violations: [], errors: [], outside: [], sources: [], notice: null };
  await ctx.exposeBinding('reportViolation', (_s, text) => { out.violations.push(text); });
  await ctx.exposeBinding('reportSource', (_s, at) => { out.sources.push(at); });
  await ctx.addInitScript(() => {
    document.addEventListener('securitypolicyviolation', (e) => {
      window.reportViolation(e.violatedDirective + ' ' + e.blockedURI);
    });
    const Real = window.EventSource;
    if (Real) {
      window.EventSource = function (u, o) { window.reportSource(String(u)); return new Real(u, o); };
      window.EventSource.prototype = Real.prototype;
    }
  });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => out.errors.push(String(e)));
  page.on('console', (m) => {
    if (m.type() === 'error') out.errors.push(m.text());
    if (/Content Security Policy/.test(m.text())) out.violations.push(m.text());
  });
  page.on('request', (r) => {
    if (!r.url().startsWith(origin + '/')) out.outside.push(r.url());
  });
  const loaded = async () => {
    await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready, null, { timeout: 30000 });
    await page.waitForTimeout(500);
    out.loads.push(await page.evaluate(() => ({ hash: location.hash, chain: window.systemapCanvas.chain(),
      selected: window.systemapCanvas.selected().id })));
  };
  let navigations = 0;
  page.on('load', () => { navigations++; });
  await page.goto(url + hash);
  await loaded();
  const before = navigations;
  await refresh(page, url);
  for (let i = 0; i < 100 && navigations === before; i++) await page.waitForTimeout(100);
  await loaded();
  fs.writeFileSync(flag, 'fail');
  await refresh(page, url);
  await page.waitForSelector('#live-notice', { timeout: 30000 });
  out.notice = await page.textContent('#live-notice');
  // The box of the notice and the plate of the help line, in the coordinates of the page.
  out.noticeBox = await page.evaluate(() => { const r = document.getElementById('live-notice').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; });
  out.helpBox = await page.evaluate(() => window.systemapCanvas.layout().help);
  await page.waitForTimeout(1000);
  out.navigations = navigations;
  await browser.close();
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { process.stderr.write(String(e && e.stack || e)); process.exit(1); });
