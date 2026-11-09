// The browser part of canvas_find.py (the Find dialog of the canvas page).
//
//     node canvas_find.js PAGE.html MODE RATE
//
// MODE is `build`, `pan` or `pan-after`. RATE is the CPU throttling rate of
// Emulation.setCPUThrottlingRate. The viewport is 1440 x 900 with 1 device pixel for each
// pixel. The script prints one JSON object:
// - build: {build: [ms of each of BUILDS calls of systemapCanvas.find.build()], n (results),
//   rank: {text: ms}}: the time to make the results, and the time to rank them for a text.
// - pan: {frames, median, p95, max} of the intervals between 180 animation frames, with the
//   camera of the pan-fit scenario of canvas_frames.js at each frame.
// - pan-after: the same, after Ctrl+K, the text "c5" and Escape.
'use strict';
const { chromium } = require('playwright');

const BUILDS = 20, FRAMES = 180;

function pan(frames) {
  const api = window.systemapCanvas, top = api.fit('');
  const at = (t) => ({ x: top.x + Math.sin(t * Math.PI * 2) * 200 / top.k, y: top.y, k: top.k });
  return new Promise((done) => {
    const gaps = [];
    let f = 0, last = null;
    const step = (now) => {
      if (last !== null) gaps.push(now - last);
      last = now;
      api.view(at(f / frames));
      if (++f <= frames) { requestAnimationFrame(step); return; }
      gaps.sort((a, b) => a - b);
      const pick = (q) => +gaps[Math.min(gaps.length - 1, Math.floor(gaps.length * q))].toFixed(1);
      done({ frames: gaps.length, median: pick(0.5), p95: pick(0.95), max: pick(1) });
    };
    requestAnimationFrame(step);
  });
}

(async () => {
  const [file, mode, rate] = process.argv.slice(2);
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: +rate });
  await page.goto('file://' + file);
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await page.waitForTimeout(300);
  let out;
  if (mode === 'build') {
    out = await page.evaluate((n) => {
      const f = window.systemapCanvas.find, build = [];
      let count = 0;
      for (let i = 0; i < n; i++) { const r = f.build(); build.push(+r.ms.toFixed(2)); count = r.n; }
      const rank = {};
      for (const t of ['c5', 'record', 'p1 a0']) { const t0 = performance.now(); f.rank(t); rank[t] = +(performance.now() - t0).toFixed(2); }
      return { build, n: count, rank };
    }, BUILDS);
  } else {
    if (mode === 'pan-after') {
      await page.focus('#canvas');
      await page.keyboard.press('Control+k');
      await page.keyboard.type('c5');
      await page.waitForTimeout(200);
      await page.keyboard.press('Escape');
      await page.waitForTimeout(300);
    }
    out = await page.evaluate(pan, FRAMES);
  }
  await browser.close();
  process.stdout.write(JSON.stringify(out) + '\n');
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
