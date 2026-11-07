// The browser part of canvas_views.py: C2 of the canvas page with a layer of the Map view.
//
//     node canvas_views.js PAGE.html MODE RATE VARIANT [FRAMES]
//     node canvas_views.js PAGE.html load RATE
//
// MODE is pan-fit, all-open or dive, as in canvas_frames.js. VARIANT is `data` (the layer
// data is set before the move) or `switch` (the layer data is set before the move, All at
// the frame FRAMES / 3, and data again at 2 FRAMES / 3). A page without
// `systemapCanvas.setView` (the page of the base commit) does the same moves with no
// layer. The script prints {frames, median, p95, max, over}: the intervals between
// animation frames in milliseconds, and `over`, the largest count of seam calls of a frame
// less the count of the cards and the flows that the frame draws (null without the view
// part). `load` prints {ready} as canvas_frames.js does.
'use strict';
const { chromium } = require('playwright');

async function open(rate) {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate });
  return { browser, page };
}

function scenario(args) {
  const [mode, frames, variant] = args;
  const api = window.systemapCanvas, W = innerWidth, H = innerHeight, top = api.fit('');
  const set = (layer) => { if (api.setView) api.setView('map', layer); };
  const centre = (c) => [c.x + W / 2 / c.k, c.y + H / 2 / c.k];
  const camAt = (cx, cy, k) => ({ x: cx - W / 2 / k, y: cy - H / 2 / k, k });
  let at;
  if (mode === 'pan-fit') {
    at = (t) => ({ x: top.x + Math.sin(t * Math.PI * 2) * 200 / top.k, y: top.y, k: top.k });
  } else if (mode === 'all-open') {
    const box = api.openBox(), [cx, cy] = centre(box);
    at = (t) => camAt(cx, cy, box.k * (1 + 0.4 * Math.sin(t * Math.PI * 2)));
  } else {
    const deep = api.deepFit(), [cx, cy] = centre(deep), [tx, ty] = centre(top);
    const dive = (e) => camAt(tx + (cx - tx) * e, ty + (cy - ty) * e, top.k * Math.pow(deep.k / top.k, e));
    at = (t) => { const u = t < 0.5 ? 2 * t : 2 - 2 * t; return dive(u * u * (3 - 2 * u)); };
  }
  set('data');
  return new Promise((done) => {
    const gaps = [];
    let f = 0, last = null, over = api.viewState ? -Infinity : null;
    const step = (now) => {
      if (last !== null) gaps.push(now - last);
      last = now;
      if (over !== null && f) { const s = api.viewState(); over = Math.max(over, s.hooks - s.cards - s.flows); }
      if (variant === 'switch' && f === Math.round(frames / 3)) set('all');
      if (variant === 'switch' && f === Math.round(2 * frames / 3)) set('data');
      api.view(at(f / frames));
      if (++f <= frames) { requestAnimationFrame(step); return; }
      gaps.sort((a, b) => a - b);
      const pick = (q) => +gaps[Math.min(gaps.length - 1, Math.floor(gaps.length * q))].toFixed(1);
      done({ frames: gaps.length, median: pick(0.5), p95: pick(0.95), max: pick(1), over });
    };
    requestAnimationFrame(step);
  });
}

(async () => {
  if (process.argv[2] === '--probe') { const b = await chromium.launch(); await b.close(); return; }
  const [file, mode, rate, variant, count] = process.argv.slice(2);
  const { browser, page } = await open(+rate);
  await page.goto('file://' + file);
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  let result;
  if (mode === 'load') result = await page.evaluate(() => ({ ready: window.systemapCanvas.ready }));
  else {
    await page.waitForTimeout(300);
    result = await page.evaluate(scenario, [mode, +(count || 180), variant]);
  }
  await browser.close();
  process.stdout.write(JSON.stringify(result) + '\n');
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
