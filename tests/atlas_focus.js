// The browser part of tests/test_atlas_focus_browser.py: the Focus view of the atlas page.
//
//     node atlas_focus.js MODE PAGE.html
//
// MODE is one of:
// - --wide: 1440 x 900. The view after a click on Focus. A pointer on a card of the column
//   at the right, on a line and off the board. A click on a line keeps its light, and a
//   click on the ground removes it. A click on the button CLI of the list, and a click on a
//   card of the board. The keys from the first button of the list: the right arrow key, the
//   right, down, left and left arrow keys, Home, the right arrow key and Enter, and Esc. Then
//   a change of the screen size to 1000 x 800, and a click on Map.
// - --details: 1440 x 900. The details of the card Check, and a click on the button "Focus
//   on this card".
// - --phone: 390 x 844 with a touch screen, in the light and the dark scheme. The view, and a
//   tap on the first card of the column at the right.
// - --axe: axe-core in the Focus view with a focused card, in the light and the dark scheme,
//   at 1440 x 900 and at 390 x 844 (null when axe-core is not on NODE_PATH).
// Each mode prints one JSON object. `errors` has the script errors of the page.
'use strict';
const { chromium } = require('playwright');

const WIDE = { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 };
const PHONE = { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, hasTouch: true, isMobile: true };

async function open(browser, file, opts) {
  const page = await browser.newPage(opts);
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + file);
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await page.waitForTimeout(600);
  return { page, errors };
}
async function state(page) {
  return page.evaluate(() => {
    const s = window.systemapCanvas;
    const shown = (sel) => { const e = document.querySelector(sel); return e ? getComputedStyle(e).display : null; };
    return { focus: s.focus(), view: s.viewState(), say: s.say(), said: document.getElementById('atlas-said').textContent,
      camera: s.camera(), canvas: getComputedStyle(document.getElementById('canvas')).visibility,
      tabs: shown('#atlas-tabs'), zoom: shown('.zoom'), counts: shown('#atlas-ask-n'),
      pressed: Array.from(document.querySelectorAll('#atlas-head [data-mode]')).map((x) => [x.textContent, x.getAttribute('aria-pressed')]),
      scroll: document.documentElement.scrollWidth, width: innerWidth };
  });
}
// The middle of a card or of a line of the board on the screen.
async function cardMid(page, pick) {
  const st = await page.evaluate(() => window.systemapCanvas.focus());
  const r = st.items.find(pick).rect;
  return [r.x + r.width / 2, r.y + r.height / 2];
}
async function lineMid(page, i) {
  return page.evaluate((i) => {
    const w = document.querySelector('#atlas-fworld [data-item="e' + i + '"] path.hit'), q = w.getPointAtLength(w.getTotalLength() / 2);
    const p = new DOMPoint(q.x, q.y).matrixTransform(w.getScreenCTM());
    return [p.x, p.y];
  }, i);
}
async function press(page, key) { await page.keyboard.press(key); await page.waitForTimeout(120); return state(page); }

async function wide(browser, file) {
  const { page, errors } = await open(browser, file, { ...WIDE, colorScheme: 'light' });
  const out = { errors };
  out.before = await state(page);
  await page.click('#atlas-head [data-mode="focus"]');
  await page.waitForTimeout(600);
  out.shown = await state(page);
  let p = await cardMid(page, (o) => o.kind === 'n' && o.j === 1 && o.i === 0);
  await page.mouse.move(p[0], p[1]);
  await page.waitForTimeout(300);
  out.card = await state(page);
  // The last line of the middle card is above the other lines.
  const edge = out.shown.focus.items.filter((o) => o.kind === 'e' && o.a === '0').pop();
  p = await lineMid(page, edge.i);
  await page.mouse.move(p[0], p[1]);
  await page.waitForTimeout(300);
  out.line = await state(page);
  out.lineIndex = edge.i;
  await page.mouse.move(1400, 880);
  await page.waitForTimeout(300);
  out.off = await state(page);
  p = await lineMid(page, edge.i);
  await page.mouse.click(p[0], p[1]);
  await page.mouse.move(1400, 880);
  await page.waitForTimeout(300);
  out.pinned = await state(page);
  await page.mouse.click(1400, 880);
  await page.waitForTimeout(300);
  out.unpinned = await state(page);
  await page.click('#atlas-frail-list button[data-card="CLI"]');
  await page.waitForTimeout(400);
  out.rail = await state(page);
  p = await cardMid(page, (o) => o.kind === 'n' && o.j === 1 && o.i === 0);
  await page.mouse.click(p[0], p[1]);
  await page.waitForTimeout(400);
  out.board = await state(page);
  await page.click('#atlas-frail-list button[data-card="Model"]');
  await page.waitForTimeout(400);
  await page.focus('#atlas-frail-list button');
  out.keys = { start: await state(page) };
  out.keys.right = await press(page, 'ArrowRight');
  out.keys.right2 = await press(page, 'ArrowRight');
  out.keys.down = await press(page, 'ArrowDown');
  out.keys.left = await press(page, 'ArrowLeft');
  out.keys.left2 = await press(page, 'ArrowLeft');
  out.keys.home = await press(page, 'Home');
  out.keys.right3 = await press(page, 'ArrowRight');
  out.keys.enter = await press(page, 'Enter');
  await page.waitForTimeout(300);
  out.keys.entered = await state(page);
  out.keys.esc = await press(page, 'Escape');
  out.keys.f = await press(page, 'f');
  await page.setViewportSize({ width: 1000, height: 800 });
  await page.waitForTimeout(500);
  out.resized = await state(page);
  await page.click('#atlas-head [data-mode="map"]');
  await page.waitForTimeout(600);
  out.map = await state(page);
  out.mapStats = await page.evaluate(() => window.systemapCanvas.stats());
  return out;
}

async function details(browser, file) {
  const { page, errors } = await open(browser, file, { ...WIDE, colorScheme: 'light' });
  const out = { errors };
  await page.evaluate(() => window.systemapCanvas.select('', 'Check'));
  await page.waitForTimeout(500);
  out.button = await page.evaluate(() => { const b = document.querySelector('#atlas-side-b [data-focus]'); return b ? b.textContent : null; });
  await page.click('#atlas-side-b [data-focus]');
  await page.waitForTimeout(600);
  out.shown = await state(page);
  out.side = await page.evaluate(() => window.systemapCanvas.side());
  return out;
}

async function phone(browser, file) {
  const out = {};
  for (const scheme of ['light', 'dark']) {
    const { page, errors } = await open(browser, file, { ...PHONE, colorScheme: scheme });
    const o = { errors };
    await page.tap('#atlas-head [data-mode="focus"]');
    await page.waitForTimeout(600);
    o.shown = await state(page);
    const p = await cardMid(page, (x) => x.kind === 'n' && x.j === 1 && x.i === 0);
    await page.touchscreen.tap(p[0], p[1]);
    await page.waitForTimeout(400);
    o.tapped = await state(page);
    out[scheme] = o;
    await page.close();
  }
  out.errors = [].concat(out.light.errors, out.dark.errors);
  return out;
}

async function axe(browser, file) {
  let source;
  try { source = require.resolve('axe-core/axe.min.js'); } catch (e) { return { axe: null, errors: [] }; }
  const out = { axe: [], errors: [] };
  for (const opts of [WIDE, PHONE]) for (const scheme of ['light', 'dark']) {
    const { page, errors } = await open(browser, file, { ...opts, colorScheme: scheme, bypassCSP: true });
    await page.click('#atlas-head [data-mode="focus"]');
    await page.waitForTimeout(500);
    await page.focus('#atlas-frail-list button');
    await page.keyboard.press('ArrowRight');
    await page.waitForTimeout(300);
    await page.addScriptTag({ content: require('fs').readFileSync(source, 'utf8') });
    const r = await page.evaluate(async () => (await window.axe.run(document)).violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length })));
    out.axe.push({ width: opts.viewport.width, scheme, violations: r });
    out.errors.push(...errors);
    await page.close();
  }
  return out;
}

(async () => {
  const [mode, file] = process.argv.slice(2);
  const browser = await chromium.launch();
  try {
    const run = { '--wide': wide, '--details': details, '--phone': phone, '--axe': axe }[mode];
    if (!run) throw new Error('unknown mode ' + mode);
    process.stdout.write(JSON.stringify(await run(browser, file)));
  } finally {
    await browser.close();
  }
})().catch((e) => { process.stderr.write(String(e.stack || e)); process.exit(1); });
