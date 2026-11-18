// The browser part of tests/test_atlas_states_browser.py: the States view of the atlas page.
//
//     node atlas_states.js MODE PAGE.html
//
// MODE is one of:
// - --wide: 1440 x 900. The header before a click on States. Then the view: the headline, the
//   list, the board and the reading line. A pointer on the transition 1 (the middle of its
//   line) and on the state 0, and off the board. A click on the transition 1 keeps its light,
//   and a click on the ground removes it. The keys: the right arrow key with the keyboard
//   focus on the first button of the list, more right arrow keys, End, Home, Enter, Esc and
//   Tab. The camera before and after the keys. A click on the second button of the list. A
//   click on Map. Then a change of the screen size to 1000 x 800 in the States view.
// - --nested: 1440 x 900 on a page with a machine in the top map and in the nested map
//   Gateway. The list, and a click on the machine of Gateway, with the board.
// - --phone: 390 x 844 with a touch screen. The view, the list and the board. A tap on the
//   transition 1. Then the second machine.
// - --axe: axe-core in the States view with a lit transition, in the light and the dark
//   scheme, at 1440 x 900 and at 390 x 844 (null when axe-core is not on NODE_PATH).
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
    const b = (sel) => { const e = document.querySelector(sel); return e ? e.getBoundingClientRect().toJSON() : null; };
    const shown = (sel) => { const e = document.querySelector(sel); return e ? getComputedStyle(e).display : null; };
    return { states: s.states(), view: s.viewState(), say: s.say(), said: document.getElementById('atlas-said').textContent,
      camera: s.camera(), ask: b('#atlas-ask'), canvas: getComputedStyle(document.getElementById('canvas')).visibility,
      tabs: shown('#atlas-tabs'), key: shown('#atlas-key'), zoom: shown('.zoom'), seqRail: shown('#atlas-rail'), sayBox: b('#atlas-say'),
      pressed: Array.from(document.querySelectorAll('#atlas-head [data-mode]')).map((x) => [x.textContent, x.getAttribute('aria-pressed')]),
      scroll: document.documentElement.scrollWidth, width: innerWidth };
  });
}
// The middle of the line of transition i on the screen.
async function edgeMid(page, i) {
  const st = await page.evaluate(() => window.systemapCanvas.states());
  const t = st.items.find((o) => o.kind === 't' && o.i === i);
  return t.points[8];
}
async function stateMid(page, i) {
  const st = await page.evaluate(() => window.systemapCanvas.states());
  const r = st.items.find((o) => o.kind === 's' && o.i === i).rect;
  return [r.x + r.width / 2, r.y + r.height / 2];
}
async function press(page, key) { await page.keyboard.press(key); await page.waitForTimeout(80); return state(page); }

async function wide(browser, file) {
  const { page, errors } = await open(browser, file, { ...WIDE, colorScheme: 'light' });
  const out = { errors };
  out.before = await state(page);
  await page.click('#atlas-head [data-mode="states"]');
  await page.waitForTimeout(600);
  out.shown = await state(page);
  let p = await edgeMid(page, 1);
  await page.mouse.move(p[0], p[1]);
  await page.waitForTimeout(300);
  out.edge = await state(page);
  p = await stateMid(page, 0);
  await page.mouse.move(p[0], p[1]);
  await page.waitForTimeout(300);
  out.node = await state(page);
  await page.mouse.move(1400, 860);
  await page.waitForTimeout(300);
  out.off = await state(page);
  p = await edgeMid(page, 1);
  await page.mouse.click(p[0], p[1]);
  await page.mouse.move(1400, 860);
  await page.waitForTimeout(300);
  out.pinned = await state(page);
  await page.mouse.click(1400, 860);
  await page.waitForTimeout(300);
  out.unpinned = await state(page);
  await page.focus('#atlas-srail-list button');
  out.keys = { start: await state(page) };
  out.keys.right = await press(page, 'ArrowRight');
  out.keys.right2 = await press(page, 'ArrowRight');
  out.keys.down = await press(page, 'ArrowDown');
  out.keys.left = await press(page, 'ArrowLeft');
  out.keys.end = await press(page, 'End');
  out.keys.endRight = await press(page, 'ArrowRight');
  out.keys.home = await press(page, 'Home');
  out.keys.tab = await press(page, 'Tab');
  out.keys.enter = await press(page, 'Enter');
  out.keys.esc = await press(page, 'Escape');
  out.keys.f = await press(page, 'f');
  await page.click('#atlas-srail-list button:nth-of-type(2)');
  await page.waitForTimeout(400);
  out.second = await state(page);
  await page.setViewportSize({ width: 1000, height: 800 });
  await page.waitForTimeout(400);
  out.resized = await state(page);
  await page.click('#atlas-head [data-mode="map"]');
  await page.waitForTimeout(600);
  out.map = await state(page);
  out.mapLines = await page.evaluate(() => window.systemapCanvas.stats());
  return out;
}

async function nested(browser, file) {
  const { page, errors } = await open(browser, file, { ...WIDE, colorScheme: 'light' });
  const out = { errors };
  await page.click('#atlas-head [data-mode="states"]');
  await page.waitForTimeout(600);
  out.shown = await state(page);
  out.groups = await page.evaluate(() => Array.from(document.querySelectorAll('#atlas-srail-list .rail__g')).map((x) => x.textContent));
  await page.click('#atlas-srail-list button[data-m="1"]');
  await page.waitForTimeout(400);
  out.inner = await state(page);
  const p = await stateMid(page, 2);
  await page.mouse.move(p[0], p[1]);
  await page.waitForTimeout(300);
  out.done = await state(page);
  return out;
}

async function phone(browser, file) {
  const out = {};
  for (const scheme of ['light', 'dark']) {
    const { page, errors } = await open(browser, file, { ...PHONE, colorScheme: scheme });
    const o = { errors };
    await page.tap('#atlas-head [data-mode="states"]');
    await page.waitForTimeout(600);
    o.shown = await state(page);
    const p = await edgeMid(page, 1);
    await page.touchscreen.tap(p[0], p[1]);
    await page.waitForTimeout(300);
    o.tapped = await state(page);
    await page.tap('#atlas-srail-list button:nth-of-type(2)');
    await page.waitForTimeout(400);
    o.second = await state(page);
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
    await page.click('#atlas-head [data-mode="states"]');
    await page.waitForTimeout(500);
    await page.focus('#atlas-sboard [data-item="t1"]');
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
    const run = { '--wide': wide, '--nested': nested, '--phone': phone, '--axe': axe }[mode];
    if (!run) throw new Error('unknown mode ' + mode);
    process.stdout.write(JSON.stringify(await run(browser, file)));
  } finally {
    await browser.close();
  }
})().catch((e) => { process.stderr.write(String(e.stack || e)); process.exit(1); });
