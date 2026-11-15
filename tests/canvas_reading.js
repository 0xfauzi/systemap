// Drives a canvas page (systemap.canvas_page) in the Chromium of Playwright for the parts
// that help a person read the map: the flow labels at the fit, the caption
// (page_canvas_caption) and the route in the Details panel (page_canvas_sequences). Prints
// one JSON object. tests/test_canvas_reading_browser.py reads it.
//
//     node tests/canvas_reading.js --labels PAGE.html
//     node tests/canvas_reading.js --caption PAGE.html
//     node tests/canvas_reading.js --route PAGE.html
//     node tests/canvas_reading.js --bands PAGE.html
//
// --labels: the labels at the fit of the top map, for each layer with flows, at 1440 x 900.
// --caption: the words and the box of the caption after each layer, the fade of a change
// with and without reduced motion, and the box on a phone. --route: the caption, the labels
// and the Details panel in the Sequences view, and axe-core (from NODE_PATH; null when it
// is not there). --bands: the bands of the fit and the frame of the top map.
'use strict';
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const DESK = { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 };
const PHONE = { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3 };

async function open(browser, file, options) {
  const context = await browser.newContext(options);
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + path.resolve(file));
  await page.waitForFunction(() => window.systemapCanvas && document.fonts.status === 'loaded');
  await page.waitForTimeout(400);
  return { page, errors };
}
const top = (page) => page.evaluate(() => JSON.parse(document.getElementById('canvas-data').textContent).maps[0]);
// The flow labels of a new frame: each text with the font weight 500.
const labels = (page) => page.evaluate(() => window.systemapCanvas.texts().filter((t) => t.weight === 500 && t.alpha > 0.02)
  .map((t) => ({ s: t.s, size: t.size, alpha: t.alpha })));
const layout = (page) => page.evaluate(() => {
  const S = window.systemapCanvas, l = S.layout();
  return { caption: S.caption(), path: l.path, help: l.help, gutters: l.gutters, frame: S.frame(''), head: S.viewState().head,
    scroll: document.documentElement.scrollWidth, width: innerWidth, height: innerHeight };
});
// The alpha and the sentence of the caption in each frame after `act`, for `ms` ms.
const fade = (page, act, ms) => page.evaluate(([act, ms]) => new Promise((done) => {
  const S = window.systemapCanvas, out = [], t0 = performance.now();
  S.setView('map', act);
  (function tick() {
    const c = S.caption();
    out.push([performance.now() - t0, c.a, c.s]);
    if (performance.now() - t0 < ms) requestAnimationFrame(tick); else done(out);
  })();
}), [act, ms]);

async function runLabels(browser, file) {
  const { page, errors } = await open(browser, file, Object.assign({ reducedMotion: 'reduce' }, DESK));
  const map = await top(page), out = { layers: [], errors };
  for (const lay of map.layers.filter((l) => l.e.length)) {
    await page.evaluate((id) => { const S = window.systemapCanvas; S.setView('map', id); S.view(S.fit('')); }, lay.id);
    await page.waitForTimeout(300);
    out.layers.push({ id: lay.id, want: lay.e.filter((i) => map.flows[i].lb).map((i) => map.flows[i].a).sort(), got: await labels(page) });
  }
  return out;
}

async function runCaption(browser, file) {
  const { page, errors } = await open(browser, file, Object.assign({ reducedMotion: 'reduce' }, DESK));
  const map = await top(page), out = { start: await layout(page), layers: [], errors };
  for (const lay of map.layers) {
    await page.getByRole('button', { name: lay.n, exact: true }).click();
    await page.waitForTimeout(250);
    out.layers.push({ id: lay.id, n: lay.n, q: lay.q, at: await layout(page), said: await page.evaluate(() => document.getElementById('canvas-said').textContent) });
  }
  await page.context().close();
  // The fade, without reduced motion: to a layer, and back to All.
  const moving = await open(browser, file, DESK);
  await moving.page.waitForTimeout(500);
  out.fade = await fade(moving.page, map.layers[0].id, 900);
  out.reduced = await page.context().browser().newContext(Object.assign({ reducedMotion: 'reduce' }, DESK)).then(async (context) => {
    const p = await context.newPage();
    await p.goto('file://' + path.resolve(file));
    await p.waitForFunction(() => window.systemapCanvas);
    await p.waitForTimeout(400);
    return fade(p, map.layers[0].id, 300);
  });
  const phone = await open(browser, file, Object.assign({ reducedMotion: 'reduce' }, PHONE));
  out.phone = await layout(phone.page);
  out.errors = errors.concat(moving.errors, phone.errors);
  return out;
}

async function axeRun(page) {
  let source;
  try { source = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8'); } catch (e) { return null; }
  await page.evaluate(source);
  return page.evaluate(async () => {
    const r = await window.axe.run(document, { resultTypes: ['violations'] });
    return { version: window.axe.version, violations: r.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical').map((v) => v.id) };
  });
}

async function runRoute(browser, file) {
  const out = { axe: [] };
  for (const colorScheme of ['light', 'dark']) {
    const { page, errors } = await open(browser, file, Object.assign({ reducedMotion: 'reduce', colorScheme }, DESK));
    const map = await top(page), seq = map.sq[0];
    const panel = () => page.evaluate(() => {
      const body = document.getElementById('cdet-body'), on = document.activeElement;
      return { title: (body.querySelector('h3') || {}).textContent || '', steps: Array.from(body.querySelectorAll('ol [data-step]')).map((b) => b.textContent),
        current: Array.from(body.querySelectorAll('[aria-current="step"]')).map((b) => b.getAttribute('data-step')),
        sentences: Array.from(body.querySelectorAll('ol li p')).map((p) => p.textContent), focus: on && on.getAttribute ? on.getAttribute('data-step') : null };
    });
    const state = () => page.evaluate(() => ({ seq: window.systemapCanvas.seqState(), caption: window.systemapCanvas.caption(),
      count: document.getElementById('cseq-count').textContent, said: document.getElementById('canvas-said').textContent }));
    await page.getByRole('button', { name: 'Sequences', exact: true }).click();
    await page.waitForTimeout(300);
    await page.evaluate(() => window.systemapCanvas.view(window.systemapCanvas.fit('')));
    await page.waitForTimeout(300);
    const one = { seq, flows: map.flows.map((f) => f.a), whole: await state(), wholeLabels: await labels(page) };
    await page.locator('#canvas').focus();
    await page.keyboard.press('d');
    await page.waitForTimeout(300);
    one.panel = await panel();
    one.axeWhole = await axeRun(page);
    await page.locator('#cdet-body [data-step="2"]').click();
    await page.waitForTimeout(300);
    one.third = { state: await state(), panel: await panel() };
    await page.locator('#cseq-next').click();
    await page.waitForTimeout(300);
    one.fourth = { state: await state(), panel: await panel() };
    one.axeStep = await axeRun(page);
    // A selected card takes the panel, and the route comes back without a selection.
    const card = await page.evaluate(() => { const S = window.systemapCanvas; S.view(S.fit('')); return S.boxes('')[0]; });
    await page.waitForTimeout(200);
    await page.mouse.click(card.b[0] + card.b[2] / 2, card.b[1] + card.b[3] / 2);
    await page.waitForTimeout(300);
    one.card = { id: card.id, panel: await panel() };
    await page.mouse.click(6, 300);
    await page.waitForTimeout(300);
    one.back = await panel();
    one.errors = errors;
    out[colorScheme] = one;
    await page.context().close();
  }
  return out;
}

async function runBands(browser, file) {
  const { page, errors } = await open(browser, file, Object.assign({ reducedMotion: 'reduce' }, DESK));
  const ports = (await page.evaluate(() => JSON.parse(document.getElementById('canvas-data').textContent).maps.some((m) => (m.ports || []).length)));
  return Object.assign({ ports, errors }, await layout(page));
}

(async () => {
  const [mode, file] = process.argv.slice(2);
  const runs = { '--labels': runLabels, '--caption': runCaption, '--route': runRoute, '--bands': runBands };
  if (!runs[mode] || !file) { console.error('usage: canvas_reading.js --labels|--caption|--route|--bands PAGE.html'); process.exit(2); }
  const browser = await chromium.launch();
  try { console.log(JSON.stringify(await runs[mode](browser, file))); } finally { await browser.close(); }
})().catch((e) => { console.error(e); process.exit(1); });
