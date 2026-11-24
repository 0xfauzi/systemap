// The browser part of tests/test_atlas_calm_browser.py: a pointer that goes across the map,
// and the scrollbars of the boards.
//
//     node atlas_calm.js --sweep PAGE.html
//     node atlas_calm.js --bars PAGE.html WIDTHxHEIGHT...
//
// --sweep: at 1440 x 900, the key of the light (`systemapCanvas.lit().key`) in each
// animation frame while the pointer does four moves. `fast`: from card A, where the pointer
// was at rest, to card B in steps of 16 ms, each step more than 0.3 px for each ms. `stop`: the 150 ms after the last
// step. `rest`: after 400 ms with no move, one move onto card A. `slow`: from the side of a
// card onto the card in steps of 3 px each 16 ms.
// --bars: the browser shows its scrollbars (Playwright hides them by default). For each
// size, each view and each item of the view, the boards whose content is larger than their
// box, with the number of px in each direction, and the smallest content size.
// The output is one JSON object. `errors` has the script errors of the page.
'use strict';
const { chromium } = require('playwright');

const watch = () => {
  window.__keys = [];
  const me = (window.__run = {});
  (function each() {
    if (window.__run !== me) return;
    window.__keys.push([Math.round(performance.now()), window.systemapCanvas.lit().key || '']);
    requestAnimationFrame(each);
  })();
};
const taken = () => { window.__run = null; return window.__keys; };

async function sweep(file) {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto('file://' + file);
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await page.waitForTimeout(800);
  const boxes = await page.evaluate(() => window.systemapCanvas.boxes('').map((c) => ({ id: c.id, b: window.systemapCanvas.box('', c.id) })));
  const mid = (c) => [c.b[0] + c.b[2] / 2, c.b[1] + c.b[3] / 2];
  // The two cards that are farthest from each other.
  let a = boxes[0], b = boxes[1], far = 0;
  for (const p of boxes) for (const q of boxes) { const d = Math.hypot(mid(p)[0] - mid(q)[0], mid(p)[1] - mid(q)[1]); if (d > far) { far = d; a = p; b = q; } }
  const out = { errors, a: a.id, b: b.id, far };
  await page.mouse.move(5, 300);
  await page.waitForTimeout(500);
  const [x0, y0] = mid(a), [x1, y1] = mid(b), n = 30;
  // The pointer rests on card A, so card A is the light before the fast move.
  await page.mouse.move(x0, y0);
  await page.waitForTimeout(500);
  out.before = await page.evaluate(() => window.systemapCanvas.lit().key || '');
  await page.evaluate(watch);
  const t0 = Date.now();
  for (let i = 1; i <= n; i++) {
    await page.mouse.move(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n);
    await page.waitForTimeout(12);
  }
  out.sweepMs = Date.now() - t0;
  out.step = far / n;
  out.fast = await page.evaluate(taken);
  await page.evaluate(watch);
  await page.waitForTimeout(150);
  out.stop = await page.evaluate(taken);
  // A pointer at rest, then one move onto card A.
  await page.mouse.move(5, 300);
  await page.waitForTimeout(500);
  await page.evaluate(watch);
  await page.mouse.move(x0, y0);
  await page.waitForTimeout(120);
  out.rest = await page.evaluate(taken);
  // A slow move onto card A from its left side.
  await page.mouse.move(5, 300);
  await page.waitForTimeout(500);
  await page.mouse.move(a.b[0] - 30, y0);
  await page.waitForTimeout(400);
  await page.evaluate(watch);
  for (let x = a.b[0] - 30; x <= a.b[0] + 12; x += 3) { await page.mouse.move(x, y0); await page.waitForTimeout(14); }
  await page.waitForTimeout(60);
  out.slow = await page.evaluate(taken);
  out.keyA = await page.evaluate(() => window.systemapCanvas.lit().key || '');
  await browser.close();
  return out;
}

const boards = () => ['atlas-board', 'atlas-sboard', 'atlas-fboard', 'atlas-hboard'].map((id) => {
  const x = document.getElementById(id);
  if (!x || getComputedStyle(x).display === 'none') return null;
  const s = x.querySelector('svg'), w = x.querySelector('svg > g');
  const bb = w ? w.getBoundingClientRect() : { width: 0, height: 0 }, r = x.getBoundingClientRect();
  return { id, h: x.scrollWidth - x.clientWidth, v: x.scrollHeight - x.clientHeight, box: [r.width, r.height], content: [bb.width, bb.height], svg: [+s.getAttribute('width'), +s.getAttribute('height')], bar: [x.offsetWidth - x.clientWidth, x.offsetHeight - x.clientHeight] };
}).filter(Boolean);

async function bars(file, sizes) {
  const browser = await chromium.launch({ ignoreDefaultArgs: ['--hide-scrollbars'] });
  const out = { errors: [], runs: [], barWidth: 0 };
  for (const size of sizes) {
    const [w, h] = size.split('x').map(Number);
    const page = await browser.newPage({ viewport: { width: w, height: h } });
    page.on('pageerror', (e) => out.errors.push(String(e)));
    await page.goto('file://' + file);
    await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
    await page.waitForTimeout(600);
    out.barWidth = out.barWidth || await page.evaluate(() => { const d = document.createElement('div'); d.setAttribute('class', 'board'); document.body.appendChild(d); const s = document.createElement('div'); s.textContent = 'x'; d.appendChild(s); const o = d.offsetWidth; d.remove(); const e = document.createElement('textarea'); e.rows = 1; e.value = 'a\nb\nc\nd\ne'; document.body.appendChild(e); const bw = e.offsetWidth - e.clientWidth - 2 * parseFloat(getComputedStyle(e).borderLeftWidth); e.remove(); return bw + o * 0; });
    const note = async (item) => { for (const b of await page.evaluate(boards)) out.runs.push({ size, item, ...b }); };
    const mode = async (m) => { const el = await page.$('#atlas-head [data-mode="' + m + '"]'); if (!el || !(await el.isVisible())) return false; await el.click(); await page.waitForTimeout(450); return true; };
    const each = async (sel, tag, more) => {
      const n = await page.$$eval(sel, (l) => l.length);
      for (let i = 0; i < n; i++) { await (await page.$$(sel))[i].click(); await page.waitForTimeout(300); if (more) await more(i); else await note(tag + ' ' + i); }
    };
    if (await mode('seq')) {
      await each('#atlas-rail-list button', 'seq', async (i) => {
        await page.click('[data-form="diagram"]');
        await page.waitForTimeout(300);
        await note('seq ' + i);
        await page.click('[data-form="map"]');
        await page.waitForTimeout(150);
      });
    }
    if (await mode('states')) await each('#atlas-srail-list button', 'states');
    if (await mode('focus')) await each('#atlas-frail-list button', 'focus');
    if (await mode('history')) await note('history');
    await page.close();
  }
  await browser.close();
  return out;
}

(async () => {
  const [how, file, ...rest] = process.argv.slice(2);
  const out = how === '--sweep' ? await sweep(file) : await bars(file, rest);
  console.log(JSON.stringify(out));
})();
