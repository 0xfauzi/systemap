// The browser part of canvas_details.py: C2 of the canvas page with the Details panel open.
//
//     node canvas_details.js PAGE.html MODE RATE VARIANT [FRAMES]
//
// MODE is pan-fit, all-open or dive, as in canvas_frames.js. VARIANT is `plain` (no
// selection and no panel) or `details`: before the move, Tab moves the keyboard focus to the
// first card of the top map that opens no map, Enter selects it, and the D key opens the
// Details panel. The page of the base commit has no panel: it gets the same keys. The
// script prints {frames, median, p95, max, over, open, writes}: the intervals between
// animation frames in milliseconds, `over` (the largest count of seam calls of a frame less
// the count of the cards and the flows that the frame draws), `open` (the panel shows), and
// `writes` (the DOM changes of the panel during the move).
'use strict';
const { chromium } = require('playwright');

function scenario(args) {
  const [mode, frames] = args;
  const api = window.systemapCanvas, W = innerWidth, H = innerHeight, top = api.fit('');
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
  const panel = document.getElementById('cdetails');
  let writes = 0;
  if (panel) new MutationObserver((l) => { writes += l.length; }).observe(panel, { subtree: true, childList: true, characterData: true });
  return new Promise((done) => {
    const gaps = [];
    let f = 0, last = null, over = api.viewState ? -Infinity : null;
    const step = (now) => {
      if (last !== null) gaps.push(now - last);
      last = now;
      if (over !== null && f) { const s = api.viewState(); over = Math.max(over, s.hooks - s.cards - s.flows); }
      api.view(at(f / frames));
      if (++f <= frames) { requestAnimationFrame(step); return; }
      gaps.sort((a, b) => a - b);
      const pick = (q) => +gaps[Math.min(gaps.length - 1, Math.floor(gaps.length * q))].toFixed(1);
      done({ frames: gaps.length, median: pick(0.5), p95: pick(0.95), max: pick(1), over, open: !!(panel && !panel.hidden), writes });
    };
    requestAnimationFrame(step);
  });
}

(async () => {
  if (process.argv[2] === '--probe') { const b = await chromium.launch(); await b.close(); return; }
  const [file, mode, rate, variant, count] = process.argv.slice(2);
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  await page.goto('file://' + file);
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await page.waitForTimeout(300);
  if (variant === 'details') {
    await page.focus('#canvas');
    const opens = await page.evaluate(() => {
      const d = JSON.parse(document.getElementById('canvas-data').textContent).maps[0];
      return d.cards.filter((c) => c.o !== undefined).map((c) => c.id);
    });
    for (let i = 0; i < 60; i++) {
      await page.keyboard.press('Tab');
      const k = await page.evaluate(() => window.systemapCanvas.keys());
      const id = k.focus && k.focus.id;
      if (id && opens.indexOf(id) < 0) break;
    }
    await page.keyboard.press('Enter');
    await page.keyboard.press('d');
    await page.waitForTimeout(400);
  }
  const cdp = await context.newCDPSession(page);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: +rate });
  const result = await page.evaluate(scenario, [mode, +(count || 180)]);
  result.selected = await page.evaluate(() => window.systemapCanvas.selected().id);
  await browser.close();
  process.stdout.write(JSON.stringify(result) + '\n');
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
