// The browser part of t0_dive.py: one run of the scenario `dive` of canvas_frames.js, with
// the same camera path, the same 180 frames, 1440 x 900 and the same CPU slowdown. It gives
// all the intervals between animation frames, not only the statistics.
//
//     node t0_dive.js PAGE.html RATE
//
// The output is one JSON object: {gaps: [ms, ...]}.
'use strict';
const { chromium } = require('playwright');

function scenario(frames) {
  const api = window.systemapCanvas, W = innerWidth, H = innerHeight;
  const top = api.fit('');
  const centre = (c) => [c.x + W / 2 / c.k, c.y + H / 2 / c.k];
  const camAt = (cx, cy, k) => ({ x: cx - W / 2 / k, y: cy - H / 2 / k, k });
  const deep = api.deepFit();
  const [cx, cy] = centre(deep);
  const [tx, ty] = centre(top);
  const dive = (e) => camAt(tx + (cx - tx) * e, ty + (cy - ty) * e, top.k * Math.pow(deep.k / top.k, e));
  const at = (t) => { const u = t < 0.5 ? 2 * t : 2 - 2 * t; return dive(u * u * (3 - 2 * u)); };
  return new Promise((done) => {
    const gaps = [];
    let f = 0, last = null;
    const step = (now) => {
      if (last !== null) gaps.push(now - last);
      last = now;
      api.view(at(f / frames));
      if (++f <= frames) { requestAnimationFrame(step); return; }
      done(gaps);
    };
    requestAnimationFrame(step);
  });
}

(async () => {
  const [file, rate] = process.argv.slice(2);
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: +rate });
  await page.goto('file://' + file);
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await page.waitForTimeout(300);
  const gaps = await page.evaluate(scenario, 180);
  await browser.close();
  process.stdout.write(JSON.stringify({ gaps }) + '\n');
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
