// The browser part of canvas_frames.py (C2 and C3 of the nested canvas design).
//
//     node canvas_frames.js PAGE.html MODE RATE [FRAMES] [VIEW]
//     node canvas_frames.js --probe
//
// MODE is load, pan-fit, all-open, dive, dive-stop or pan-stop. RATE is the CPU throttling rate of
// Emulation.setCPUThrottlingRate. The script prints one JSON object:
// - load: {ready, treeMs}: the milliseconds from the start of the navigation to
//   systemapCanvas.ready (the first frame is drawn and the input handlers are attached),
//   and the milliseconds to write the list of the tree (null for a page without the list);
// - a scenario: {frames, median, p95, max} of the intervals between animation frames, in
//   milliseconds. Each frame sets the camera with systemapCanvas.view, as a move does.
// - dive-stop and pan-stop: the same object for a move, and `stop`: {frames, max, over} of
//   the intervals between animation frames in the STOP_MS after the move, with no camera
//   change. `over` is the count of intervals of more than 35 ms (two ticks plus 5 percent).
//   dive-stop goes from the top fit to the part DEPTH of the dive (the scale moves in log
//   space). pan-stop moves the camera of that point 200 screen pixels to the left and right.
// VIEW is the name of a view of the page (`systemapCanvas.setView`, for example changes). The
// scenario starts 400 ms after the page shows that view. A page without views ignores it.
// --probe exits 0 if Playwright can start Chromium.
'use strict';
const { chromium } = require('playwright');

const VIEWPORT = { width: 1440, height: 900 };
const STOP_MS = 700, DEPTH = 0.2;

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
  const found = await page.evaluate(() => ({ ready: window.systemapCanvas.ready, treeMs: window.systemapCanvas.treeMs ?? null }));
  await browser.close();
  return found;
}

// The scenario runs in the page. `at(t)` gives the camera for t from 0 to 1.
function scenario(args) {
  const [mode, frames, stopMs, depth] = args;
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
    const dive = (e) => camAt(tx + (cx - tx) * e, ty + (cy - ty) * e, top.k * Math.pow(deep.k / top.k, e));
    const near = dive(depth);
    if (mode === 'dive-stop') at = (t) => dive(depth * t * t * (3 - 2 * t));
    else if (mode === 'pan-stop') at = (t) => ({ x: near.x + Math.sin(t * Math.PI * 2) * 200 / near.k, y: near.y, k: near.k });
    else at = (t) => { const u = t < 0.5 ? 2 * t : 2 - 2 * t; return dive(u * u * (3 - 2 * u)); };
  }
  const stats = (gaps) => {
    gaps.sort((a, b) => a - b);
    const pick = (q) => +gaps[Math.min(gaps.length - 1, Math.floor(gaps.length * q))].toFixed(1);
    return { frames: gaps.length, median: pick(0.5), p95: pick(0.95), max: pick(1) };
  };
  // The intervals between animation frames for `ms` after the move.
  const still = (ms, done) => {
    const gaps = [], t0 = performance.now();
    let last = t0;
    const tick = (now) => {
      gaps.push(now - last); last = now;
      if (now - t0 < ms) requestAnimationFrame(tick);
      else done({ frames: gaps.length, max: +Math.max(...gaps).toFixed(1), over: gaps.filter((g) => g > 35).length });
    };
    requestAnimationFrame(tick);
  };
  return new Promise((done) => {
    const gaps = [];
    let f = 0, last = null;
    const step = (now) => {
      if (last !== null) gaps.push(now - last);
      last = now;
      api.view(at(f / frames));
      if (++f <= frames) { requestAnimationFrame(step); return; }
      const result = stats(gaps);
      if (!mode.endsWith('-stop')) { done(result); return; }
      still(stopMs, (stop) => done({ ...result, stop }));
    };
    requestAnimationFrame(step);
  });
}

async function frames(file, mode, rate, count, view) {
  const { browser, page } = await open(rate);
  await page.goto('file://' + file);
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await page.waitForTimeout(300);
  if (view && await page.evaluate((v) => !!window.systemapCanvas.setView && window.systemapCanvas.setView(v), view)) await page.waitForTimeout(400);
  const result = await page.evaluate(scenario, [mode, count, STOP_MS, DEPTH]);
  if (view) result.view = await page.evaluate(() => (window.systemapCanvas.viewState ? window.systemapCanvas.viewState().mode : 'map'));
  await browser.close();
  return result;
}

(async () => {
  if (process.argv[2] === '--probe') {
    const browser = await chromium.launch();
    await browser.close();
    return;
  }
  const [file, mode, rate, count, view] = process.argv.slice(2);
  const result = mode === 'load' ? await load(file, +rate) : await frames(file, mode, +rate, +(count || 180), view);
  process.stdout.write(JSON.stringify(result) + '\n');
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
