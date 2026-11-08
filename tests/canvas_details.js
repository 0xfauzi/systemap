// Drives a canvas page (systemap.canvas_page) in the Chromium of Playwright for the reader
// tools and the Details panel (page_canvas_details), and prints one JSON object.
// tests/test_canvas_details_browser.py reads it.
//
//     node tests/canvas_details.js --tools PAGE.html
//     node tests/canvas_details.js --panel PAGE.html MOTION
//     node tests/canvas_details.js --access PAGE.html
//     node tests/canvas_details.js --phone PAGE.html
//     node tests/canvas_details.js --shots PAGE.html FOLDER
//
// --tools: the theme button, the reads of the theme colors, the Reduce motion button with
// the alpha of the selection in each frame, the keys sheet, the F key and the source
// button. --panel: the opacity of the Details panel in each frame, the DOM changes of the
// panel in a pan, and its text. MOTION is "none", "system" or "page". --access: axe-core
// (from NODE_PATH; null when it is not there) with the panel, the keys sheet, the source
// records and the Tools menu open. --phone: the scroll and the target boxes on a phone.
'use strict';
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const DESK = { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 };
const PHONE = { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3 };

// Count each read of the computed style of the root element: the theme colors of the canvas
// (`readColors`).
function countReads() {
  const real = window.getComputedStyle;
  window.__reads = 0;
  window.getComputedStyle = function (el) {
    if (el === document.documentElement) window.__reads++;
    return real.apply(window, arguments);
  };
}

async function open(file, options) {
  const browser = await chromium.launch();
  const context = await browser.newContext({ colorScheme: 'dark', reducedMotion: 'no-preference', ...DESK, ...options });
  await context.addInitScript(countReads);
  const page = await context.newPage(), errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + file);
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await page.waitForTimeout(400);
  return { browser, page, errors };
}

// The middle of the screen box of a card of the top map that is left of the panel.
async function cardPoint(page, skip) {
  return page.evaluate((skip) => {
    const S = window.systemapCanvas;
    const right = Math.min(900, innerWidth - 10), low = innerHeight * 0.45;
    const boxes = S.boxes('').filter((x) => x.b[0] > 10 && x.b[0] + x.b[2] < right && x.b[1] > 120 && x.b[1] + x.b[3] < low + 400 && x.b[3] > 8);
    const data = JSON.parse(document.getElementById('canvas-data').textContent);
    const cards = data.maps[0].cards;
    const pick = boxes.filter((x) => { const c = cards.find((y) => y.id === x.id); return c && c.k !== 'actor' && !c.o; })[skip || 0];
    return { id: pick.id, x: pick.b[0] + pick.b[2] / 2, y: pick.b[1] + pick.b[3] / 2 };
  }, skip);
}

// A pan of `frames` frames, one camera change in each frame.
async function pan(page, frames) {
  await page.evaluate((frames) => new Promise((done) => {
    const S = window.systemapCanvas, c = S.camera();
    let f = 0;
    const step = () => {
      S.view({ x: c.x + Math.sin(f / 30 * Math.PI) * 120 / c.k, y: c.y, k: c.k });
      if (++f < frames) requestAnimationFrame(step); else done();
    };
    requestAnimationFrame(step);
  }), frames);
}

// The value of `f` in each frame for `ms` after the start, as [time, value].
function framesOf(page, f, ms) {
  return page.evaluate(({ f, ms }) => new Promise((done) => {
    const get = new Function('return (' + f + ')();'), out = [], t0 = performance.now();
    // The value is read after the callbacks of the frame, so after the draw of the canvas.
    const step = () => setTimeout(() => {
      out.push([performance.now() - t0, get()]);
      if (performance.now() - t0 < ms) requestAnimationFrame(step); else done(out);
    }, 0);
    requestAnimationFrame(step);
  }), { f: f.toString(), ms });
}

// The alpha of the card `window.__want` in the selection of the frame.
const selAlpha = () => { const e = window.systemapCanvas.selected().shown.find((x) => x.id === window.__want); return e ? e.alpha : 0; };

async function tools(file) {
  const { browser, page, errors } = await open(file);
  const out = {};
  const reads0 = await page.evaluate(() => window.__reads);
  await pan(page, 60);
  await page.waitForTimeout(300);
  out.panReads = (await page.evaluate(() => window.__reads)) - reads0;
  const before = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
  const reads1 = await page.evaluate(() => window.__reads);
  await page.click('#canvas-tools [data-scheme][aria-pressed="false"]');
  await page.waitForTimeout(300);
  out.theme = await page.evaluate((before) => ({
    before, after: document.documentElement.getAttribute('data-theme'),
    stored: localStorage.getItem('systemap-theme'), reads: window.__reads,
    shown: [...document.querySelectorAll('#canvas-tools [data-scheme]')].filter((b) => b.offsetParent).map((b) => b.dataset.scheme),
    focus: document.activeElement && document.activeElement.dataset.scheme,
  }), before);
  out.theme.reads -= reads1;
  // The selection without Reduce motion and with it.
  const a = await cardPoint(page, 0), b = await cardPoint(page, 1);
  // Each record starts before the input, so its first frames have the value before it.
  await page.evaluate((id) => { window.__want = id; }, a.id);
  let rec = framesOf(page, selAlpha, 600);
  await page.waitForTimeout(80);
  await page.mouse.click(a.x, a.y);
  out.fadeOff = await rec;
  out.selected = a.id;
  await page.click('#reduce-motion');
  out.motion = await page.evaluate(() => ({ attr: document.documentElement.getAttribute('data-reduce-motion'),
    stored: localStorage.getItem('systemap-reduce-motion'), pressed: document.getElementById('reduce-motion').getAttribute('aria-pressed') }));
  await page.evaluate((id) => { window.__want = id; }, b.id);
  rec = framesOf(page, selAlpha, 400);
  await page.waitForTimeout(80);
  await page.mouse.click(b.x, b.y);
  out.fadeOn = await rec;
  // The keys sheet and the F key.
  await page.focus('#canvas');
  await page.keyboard.press('?');
  out.keys = await page.evaluate(() => ({ open: !document.getElementById('keys').hidden,
    rows: [...document.querySelectorAll('#keys dd')].map((d) => d.textContent), focus: document.activeElement.textContent }));
  await page.keyboard.press('ArrowLeft');
  await page.keyboard.press('Escape');
  out.keysClosed = await page.evaluate(() => ({ open: !document.getElementById('keys').hidden, focus: document.activeElement.id }));
  await page.evaluate(() => { const S = window.systemapCanvas, c = S.camera(); S.view({ x: c.x + 300 / c.k, y: c.y, k: c.k * 1.5 }); });
  await page.keyboard.press('f');
  await page.waitForTimeout(300);
  out.fit = await page.evaluate(() => ({ camera: window.systemapCanvas.camera(), fit: window.systemapCanvas.fit('') }));
  // The source button.
  await page.click('#snap');
  out.snap = await page.evaluate(() => ({ text: document.getElementById('snap').textContent, open: !document.getElementById('snap-pop').hidden,
    pop: document.getElementById('snap-pop').textContent, expanded: document.getElementById('snap').getAttribute('aria-expanded') }));
  await page.keyboard.press('Escape');
  out.snapClosed = await page.evaluate(() => ({ open: !document.getElementById('snap-pop').hidden, focus: document.activeElement.id }));
  out.errors = errors;
  await browser.close();
  return out;
}

const panelOpacity = () => { const p = document.getElementById('cdetails'); return p.hidden ? -1 : +getComputedStyle(p).opacity; };

async function panel(file, motion) {
  const { browser, page, errors } = await open(file, { reducedMotion: motion === 'system' ? 'reduce' : 'no-preference' });
  if (motion === 'page') await page.click('#reduce-motion');
  const out = {};
  await page.focus('#canvas');
  let rec = framesOf(page, panelOpacity, 500);
  await page.waitForTimeout(80);
  await page.keyboard.press('d');
  out.opening = await rec;
  out.openState = await page.evaluate(() => ({ pressed: document.getElementById('details-toggle').getAttribute('aria-pressed'),
    focus: document.activeElement.id, text: document.getElementById('cdet-body').textContent }));
  const a = await cardPoint(page, 0), b = await cardPoint(page, 1);
  await page.mouse.click(a.x, a.y);
  await page.waitForTimeout(300);
  out.card = await page.evaluate(() => ({ heading: document.querySelector('#cdet-body h3').textContent,
    h4: [...document.querySelectorAll('#cdet-body h4')].map((h) => h.textContent),
    flows: document.querySelectorAll('#cdet-body button[data-f]').length,
    modules: [...document.querySelectorAll('#cdet-body details details summary')].map((s) => s.textContent) }));
  out.cardId = a.id;
  // A pan with the panel open and a card selected: no DOM change in the panel.
  await page.evaluate(() => {
    window.__muts = 0;
    new MutationObserver((l) => { window.__muts += l.length; })
      .observe(document.getElementById('cdetails'), { subtree: true, childList: true, attributes: true, characterData: true });
  });
  await pan(page, 90);
  await page.waitForTimeout(400);
  out.panMutations = await page.evaluate(() => window.__muts);
  await page.mouse.click(b.x, b.y);
  await page.waitForTimeout(300);
  out.newMutations = await page.evaluate(() => window.__muts);
  out.second = await page.evaluate(() => document.querySelector('#cdet-body h3').textContent);
  out.secondId = b.id;
  // A flow of the lists, and back.
  if (await page.$('#cdet-body button[data-f]')) {
    await page.click('#cdet-body button[data-f]');
    out.flow = await page.evaluate(() => ({ heading: document.querySelector('#cdet-body h3').textContent, focus: document.activeElement.textContent }));
    await page.click('#cdet-body button[data-back]');
    out.back = await page.evaluate(() => document.querySelector('#cdet-body h3').textContent);
  }
  // Escape in the panel closes it.
  await page.focus('#cdet-close');
  rec = framesOf(page, panelOpacity, 500);
  await page.waitForTimeout(80);
  await page.keyboard.press('Escape');
  out.closing = await rec;
  out.closed = await page.evaluate(() => ({ hidden: document.getElementById('cdetails').hidden, focus: document.activeElement.id,
    pressed: document.getElementById('details-toggle').getAttribute('aria-pressed'), chain: window.systemapCanvas.chain() }));
  out.errors = errors;
  await browser.close();
  return out;
}

async function axeRun(page, source) {
  if (!source) return null;
  if (!(await page.evaluate(() => !!window.axe))) await page.evaluate(source);
  return page.evaluate(async () => {
    const r = await window.axe.run(document, { resultTypes: ['violations'] });
    return { version: window.axe.version, violations: r.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.map((n) => n.target.join(' ')) })) };
  });
}

async function access(file) {
  let source;
  try { source = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8'); } catch (e) { source = null; }
  const runs = [];
  for (const [screen, options] of [['desk', DESK], ['phone', PHONE]]) {
    for (const scheme of ['dark', 'light']) {
      const { browser, page, errors } = await open(file, { ...options, colorScheme: scheme, reducedMotion: 'reduce' });
      const tap = async (x, y) => (screen === 'phone' ? page.touchscreen.tap(x, y) : page.mouse.click(x, y));
      const menu = async () => { if (await page.isVisible('#tools-open')) await page.click('#tools-open'); };
      const states = {
        details: async () => { const a = await cardPoint(page, 0); await tap(a.x, a.y); await menu(); await page.click('#details-toggle'); },
        flow: async () => { await page.click('#cdet-body button[data-f]'); },
        keys: async () => { await page.keyboard.press('Escape'); await page.focus('#canvas'); await page.keyboard.press('?'); },
        source: async () => { await page.keyboard.press('Escape'); await menu(); await page.click('#snap'); }
      };
      for (const [name, go] of Object.entries(states)) {
        await go();
        await page.waitForTimeout(250);
        runs.push({ screen, scheme, state: name, focus: await page.evaluate(() => document.activeElement && document.activeElement.id),
          axe: await axeRun(page, source), errors: errors.slice() });
      }
      await browser.close();
    }
  }
  return { runs };
}

// The boxes of the targets that show, as x, y, w, h and a name.
const targets = (sel) => [...document.querySelectorAll(sel)].filter((e) => e.offsetParent && getComputedStyle(e).visibility !== 'hidden')
  .map((e) => { const r = e.getBoundingClientRect(); return { name: e.id || e.getAttribute('aria-label') || e.textContent.trim().slice(0, 40), x: r.x, y: r.y, w: r.width, h: r.height }; });

async function phone(file) {
  const { browser, page, errors } = await open(file, { ...PHONE, reducedMotion: 'reduce' });
  const out = {};
  out.menuFlag = await page.evaluate(() => document.getElementById('canvas-head').hasAttribute('data-menu'));
  out.head = await page.evaluate(targets, '#canvas-head button, #canvas-head select');
  const a = await cardPoint(page, 0);
  await page.touchscreen.tap(a.x, a.y);
  await page.click('#tools-open');
  out.menu = await page.evaluate(targets, '#canvas-tools button');
  await page.click('#details-toggle');
  await page.waitForTimeout(200);
  out.panel = await page.evaluate(targets, '#cdetails button, #cdetails summary');
  await page.evaluate(() => { const s = document.querySelector('#cdetails details'); if (s) s.open = true; document.querySelectorAll('#cdetails details details').forEach((d) => { d.open = true; }); });
  out.panelOpen = await page.evaluate(targets, '#cdetails button, #cdetails summary');
  await page.keyboard.press('Escape');
  await page.click('#tools-open');
  await page.click('#keys-open');
  out.keys = await page.evaluate(targets, '#keys button');
  await page.keyboard.press('Escape');
  out.scroll = await page.evaluate(() => ({ width: document.documentElement.scrollWidth, x: window.scrollX, inner: window.innerWidth }));
  out.errors = errors;
  await browser.close();
  return out;
}

async function shots(file, dir) {
  for (const [screen, options] of [['desk', DESK], ['phone', PHONE]]) {
    for (const scheme of ['dark', 'light']) {
      const { browser, page } = await open(file, { ...options, colorScheme: scheme, reducedMotion: 'reduce' });
      const shot = (name) => page.screenshot({ path: path.join(dir, `${screen}-${scheme}-${name}.png`) });
      const menu = async () => { if (await page.isVisible('#tools-open')) await page.click('#tools-open'); };
      await shot('page');
      const a = await cardPoint(page, 0);
      if (screen === 'phone') await page.touchscreen.tap(a.x, a.y); else await page.mouse.click(a.x, a.y);
      await menu();
      await shot('menu');
      await page.click('#details-toggle');
      await page.evaluate(() => document.querySelectorAll('#cdetails details').forEach((d) => { d.open = true; }));
      await page.waitForTimeout(200);
      await shot('details-card');
      await page.click('#cdet-body button[data-f]');
      await page.waitForTimeout(100);
      await shot('details-flow');
      await page.keyboard.press('Escape');
      await menu();
      await page.click('#snap');
      await shot('source');
      await page.keyboard.press('Escape');
      await page.keyboard.press('Escape');
      await page.focus('#canvas');
      await page.keyboard.press('?');
      await shot('keys');
      await browser.close();
    }
  }
  return { done: true };
}

(async () => {
  const [mode, file, arg] = process.argv.slice(2);
  const run = { '--tools': () => tools(file), '--panel': () => panel(file, arg), '--access': () => access(file),
    '--phone': () => phone(file), '--shots': () => shots(file, arg) }[mode];
  process.stdout.write(JSON.stringify(await run()));
})().catch((e) => { console.error(e); process.exit(1); });
