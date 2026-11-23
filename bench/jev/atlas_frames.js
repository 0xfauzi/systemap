// The browser part of atlas_frames.py (the gate of the atlas page).
//
//     node atlas_frames.js PAGE.html MODE RATE
//
// MODE is load, pan, dive or count. RATE is the CPU throttling rate of
// Emulation.setCPUThrottlingRate. The script prints one JSON object:
// - load: {built, painted}: the milliseconds from the start of the navigation to the end of the
//   build of the top map, and to the first task after the first animation frame after the build;
// - pan: {frames, median, p95, max} of the intervals between animation frames, in milliseconds,
//   for a pan of 200 screen pixels to the left and right of the top fit for PAN_MS;
// - dive: the same object for DIVE_FRAMES frames from the top fit into the deepest map below the
//   first card that opens a map, and back out. Each frame sets the camera, as a move does;
// - count: the same dive, with the count of SVG elements after the camera change of each frame:
//   {top, max, built, deepest}: the count at the top fit, the largest count, the largest count
//   of built maps, and the map that the camera was in at the middle of the dive.
// A script error in the page makes the script exit 1.
'use strict';
const { chromium } = require('playwright');

const VIEWPORT = { width: 1440, height: 900 };
const PAN_MS = 2000, DIVE_FRAMES = 180;

async function open(file, rate) {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: 1 });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (err) => errors.push(String(err && err.stack || err)));
  const cdp = await context.newCDPSession(page);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate });
  await page.goto('file://' + file);
  await page.waitForFunction(() => window.atlas && window.atlas.ready.painted > 0);
  return { browser, page, errors };
}

// The scenario runs in the page.
function scenario(args) {
  const [mode, panMs, frames] = args;
  const api = window.atlas;
  const top = api.fit('');
  const stats = (gaps) => {
    gaps.sort((a, b) => a - b);
    const pick = (q) => +gaps[Math.min(gaps.length - 1, Math.floor(gaps.length * q))].toFixed(1);
    return { frames: gaps.length, median: pick(0.5), p95: pick(0.95), max: pick(1) };
  };
  if (mode === 'pan') {
    return new Promise((done) => {
      const gaps = [];
      let t0 = null, last = null;
      const step = (now) => {
        if (last !== null) gaps.push(now - last);
        last = now;
        if (t0 === null) t0 = now;
        const t = (now - t0) / panMs;
        api.view({ x: top.x + Math.sin(Math.min(1, t) * Math.PI * 2) * 200 / top.k, y: top.y, k: top.k });
        if (t < 1) requestAnimationFrame(step); else done(stats(gaps));
      };
      requestAnimationFrame(step);
    });
  }
  const deep = api.fit(api.deep());
  const at = (f) => { const t = f / frames, u = t < 0.5 ? 2 * t : 2 - 2 * t; return api.between(top, deep, u * u * (3 - 2 * u)); };
  return new Promise((done) => {
    const gaps = [], counts = [];
    let f = 0, last = null, built = 0, middle = '';
    const step = (now) => {
      if (last !== null) gaps.push(now - last);
      last = now;
      api.view(at(f));
      if (mode === 'count') { counts.push(api.count()); built = Math.max(built, api.built().length); if (f === frames / 2) middle = api.current(); }
      if (++f <= frames) { requestAnimationFrame(step); return; }
      if (mode === 'count') done({ top: counts[0], max: Math.max(...counts), built, deepest: middle });
      else done(stats(gaps));
    };
    requestAnimationFrame(step);
  });
}

async function measure(file, mode, rate) {
  const { browser, page, errors } = await open(file, rate);
  let result;
  if (mode === 'load') result = await page.evaluate(() => ({ built: window.atlas.ready.built, painted: window.atlas.ready.painted }));
  else {
    await page.waitForTimeout(300);
    result = await page.evaluate(scenario, [mode, PAN_MS, DIVE_FRAMES]);
  }
  await browser.close();
  if (errors.length) throw new Error('script error in the page: ' + errors.join('\n'));
  return result;
}

(async () => {
  const [file, mode, rate] = process.argv.slice(2);
  const result = await measure(file, mode, +rate);
  process.stdout.write(JSON.stringify(result) + '\n');
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
