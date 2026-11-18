// The browser part of the point measure of atlas_budget.py: the time from a pointer move
// onto a card to the lit paths on the screen.
//
//     node atlas_point.js PAGE.html RATE [CARDS] [DPR]
//
// The page opens at 1440 x 900, device pixel ratio DPR (default 1), with the CPU throttling
// rate RATE. The budget (atlas_budget.py) uses device pixel ratio 1. The
// cards are the first CARDS cards (default 8) of the order of Tab of the top map that have a
// flow that starts at them in the first layer. For each card: the pointer goes to an empty
// point at the top left of the map, and 400 ms later onto the middle of the card. The time
// starts at the time stamp of the pointermove event on the card. It stops at the first
// animation frame after the frame that drew the lit paths of the card (`systemapCanvas.lit`:
// `shown`). The script prints {times: [ms, ...], max, median}.
//
// Device pixel ratio 2 (written on 2026-11-18 before the first run with DPR): the
// specification gives no pixel ratio, so this is information and not a limit of the
// budget. The record gives, for 3 runs on the self-map at the rate 4, the largest time, the
// time of the first move after the load, and the largest time of the other moves, and it
// says for each of these values if it is 100 ms or less.
'use strict';
const { chromium } = require('playwright');

(async () => {
  const [file, rate, count, dpr] = process.argv.slice(2);
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: +(dpr || 1) });
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: +rate });
  await page.goto('file://' + file);
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await page.waitForTimeout(1500);
  const cards = await page.evaluate((n) => {
    const a = window.systemapCanvas, order = a.tabOrder(''), out = [];
    order.forEach((x, i) => { if (x.id && order[i + 1] && order[i + 1].f !== undefined && out.length < n) out.push(x.id); });
    return out.map((id) => ({ id, b: a.box('', id) }));
  }, +(count || 8));
  const times = [];
  for (const c of cards) {
    await page.mouse.move(2, 60);
    await page.waitForTimeout(400);
    await page.evaluate(() => {
      const cv = document.getElementById('canvas');
      window.__point = new Promise((done) => {
        cv.addEventListener('pointermove', function on(e) {
          cv.removeEventListener('pointermove', on);
          const t0 = e.timeStamp;
          (function step() {
            requestAnimationFrame(() => {
              const lit = window.systemapCanvas.lit();
              if (lit.shown > t0 && lit.key.charAt(0) === 'c') requestAnimationFrame(() => done(performance.now() - t0)); else step();
            });
          })();
        });
      });
    });
    await page.mouse.move(c.b[0] + c.b[2] / 2, c.b[1] + c.b[3] / 2);
    times.push(await page.evaluate(() => window.__point));
  }
  await browser.close();
  const sorted = times.slice().sort((a, b) => a - b);
  process.stdout.write(JSON.stringify({ times, max: sorted[sorted.length - 1], median: sorted[sorted.length >> 1] }) + '\n');
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
