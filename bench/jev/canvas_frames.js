// The browser part of canvas_frames.py (C2 and C3 of the nested canvas design).
//
//     node canvas_frames.js PAGE.html MODE RATE [FRAMES]
//     node canvas_frames.js --probe
//
// MODE is load, pan-fit, all-open or dive. RATE is the CPU throttling rate of
// Emulation.setCPUThrottlingRate. The script prints one JSON object:
// - load: {ready}: the milliseconds from the start of the navigation to
//   systemapCanvas.ready (the first frame is drawn and the input handlers are attached);
// - a scenario: {frames, median, p95, max} of the intervals between animation frames, in
//   milliseconds. Each frame sets the camera with systemapCanvas.view, as a move does.
// --probe exits 0 if Playwright can start Chromium.
'use strict';
const { chromium } = require('playwright');

const VIEWPORT = { width: 1440, height: 900 };

async function open(rate) {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: 1 });
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate });
  return { browser, page };
}

async function load(file, rate) {
  const { browser, page } = await open(rate);
  await page.goto('file://' + file);
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  const ready = await page.evaluate(() => window.systemapCanvas.ready);
  await browser.close();
  return { ready };
}

// The scenario runs in the page. `at(t)` gives the camera for t from 0 to 1.
function scenario(args) {
  const [mode, frames] = args;
  const api = window.systemapCanvas, W = innerWidth, H = innerHeight;
  const top = api.fit('');
  const centre = (c) => [c.x + W / 2 / c.k, c.y + H / 2 / c.k];
  const camAt = (cx, cy, k) => ({ x: cx - W / 2 / k, y: cy - H / 2 / k, k });
  let at;
  if (mode === 'pan-fit') {
    at = (t) => ({ x: top.x + Math.sin(t * Math.PI * 2) * 200 / top.k, y: top.y, k: top.k });
  } else if (mode === 'all-open') {
    const box = api.openBox();
    const [cx, cy] = centre(box);
    at = (t) => camAt(cx, cy, box.k * (1 + 0.4 * Math.sin(t * Math.PI * 2)));
  } else {
    const deep = api.deepFit();
    const [cx, cy] = centre(deep);
    const [tx, ty] = centre(top);
    at = (t) => {
      const u = t < 0.5 ? 2 * t : 2 - 2 * t, e = u * u * (3 - 2 * u);
      return camAt(tx + (cx - tx) * e, ty + (cy - ty) * e, top.k * Math.pow(deep.k / top.k, e));
    };
  }
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

async function frames(file, mode, rate, count) {
  const { browser, page } = await open(rate);
  await page.goto('file://' + file);
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await page.waitForTimeout(300);
  const result = await page.evaluate(scenario, [mode, count]);
  await browser.close();
  return result;
}

(async () => {
  if (process.argv[2] === '--probe') {
    const browser = await chromium.launch();
    await browser.close();
    return;
  }
  const [file, mode, rate, count] = process.argv.slice(2);
  const result = mode === 'load' ? await load(file, +rate) : await frames(file, mode, +rate, +(count || 180));
  process.stdout.write(JSON.stringify(result) + '\n');
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
