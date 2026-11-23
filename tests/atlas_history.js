// The browser part of tests/test_atlas_history_browser.py: the History view of the atlas page.
//
//     node atlas_history.js MODE PAGE.html
//
// MODE is one of:
// - --wide: 1440 x 900. The page before and after a click on History. A pointer on the
//   first cell with a change of the row of the test, and off the board. A click on that
//   cell, a second click, a click and a click on the ground. The keys from the stop of
//   Tab of the board: the right arrow key, the down arrow key, End, Home, the up arrow key,
//   the right arrow key and Enter, Esc, and F. Then Home and Enter on the name of the row.
//   Then the screen size 1000 x 800 with the History view. After the click on History, the
//   transition of a cell before, during and after a press of Reduce motion (`motion`).
// - --phone: 390 x 844 with a touch screen, in the light and the dark scheme. The layer tabs
//   and the headline of the Map view, the History view, and a tap on the first cell with a
//   change of the row of the test.
// - --axe: axe-core in the History view with the keyboard focus on a cell, in the light and
//   the dark scheme, at 1440 x 900 and at 390 x 844 (null when axe-core is not on NODE_PATH).
// - --none: 1440 x 900, a page with no history data.
// Each mode prints one JSON object. `errors` has the script errors of the page. The row of
// the test is the second argument after PAGE.html (a card ID).
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
    const box = (sel) => { const e = document.querySelector(sel); return e ? e.getBoundingClientRect().toJSON() : null; };
    return { history: s.history(), view: s.viewState(), say: s.say(), said: document.getElementById('atlas-said').textContent,
      camera: s.camera(), canvas: getComputedStyle(document.getElementById('canvas')).visibility, side: s.side(),
      tabs: shown('#atlas-tabs'), zoom: shown('.zoom'), counts: shown('#atlas-ask-n'), ask: box('#atlas-ask'), sayBox: box('#atlas-say'),
      pressed: Array.from(document.querySelectorAll('#atlas-head [data-mode]')).map((x) => [x.textContent, x.getAttribute('aria-pressed')]),
      scroll: document.documentElement.scrollWidth, width: innerWidth };
  });
}
// The middle of the first cell with a change of row `id`.
async function cellMid(page, id) {
  const st = await page.evaluate(() => window.systemapCanvas.history());
  const it = st.items.find((o) => o.kind === 'c' && o.id === id && !/none/.test(o.cls));
  return { key: it.key, at: [it.rect.x + it.rect.width / 2, it.rect.y + it.rect.height / 2] };
}
async function press(page, key) { await page.keyboard.press(key); await page.waitForTimeout(120); return state(page); }

async function wide(browser, file, id) {
  const { page, errors } = await open(browser, file, { ...WIDE, colorScheme: 'light' });
  const out = { errors };
  out.before = await state(page);
  await page.click('#atlas-head [data-mode="history"]');
  await page.waitForTimeout(600);
  out.shown = await state(page);
  // The transition of a cell, with and without the Reduce motion button.
  const motion = () => page.evaluate(() => getComputedStyle(document.querySelector('#atlas-hworld .hcell:not(.none) rect:last-of-type')).transitionDuration);
  out.motion = { normal: await motion() };
  await page.click('#atlas-motion');
  out.motion.reduced = await motion();
  await page.click('#atlas-motion');
  out.motion.back = await motion();
  const c = await cellMid(page, id);
  out.cell = c.key;
  await page.mouse.move(c.at[0], c.at[1]);
  await page.waitForTimeout(200);
  out.pointed = await state(page);
  await page.mouse.move(5, 880);
  await page.waitForTimeout(200);
  out.off = await state(page);
  await page.mouse.click(c.at[0], c.at[1]);
  await page.mouse.move(5, 880);
  await page.waitForTimeout(200);
  out.pinned = await state(page);
  await page.mouse.click(c.at[0], c.at[1]);
  await page.waitForTimeout(150);
  out.second = await state(page);
  await page.mouse.click(c.at[0], c.at[1]);
  await page.mouse.click(5, 880);
  await page.waitForTimeout(150);
  out.ground = await state(page);
  // The keys. The stop of Tab is the first name.
  await page.evaluate(() => { const e = document.querySelector('#atlas-hworld [tabindex="0"]'); e.focus(); });
  await page.keyboard.press('Tab');
  await page.keyboard.press('Shift+Tab');
  await page.waitForTimeout(100);
  out.keys = { start: await state(page) };
  out.keys.right = await press(page, 'ArrowRight');
  out.keys.down = await press(page, 'ArrowDown');
  out.keys.end = await press(page, 'End');
  out.keys.home = await press(page, 'Home');
  out.keys.up = await press(page, 'ArrowUp');
  out.keys.right2 = await press(page, 'ArrowRight');
  out.keys.enter = await press(page, 'Enter');
  out.keys.esc = await press(page, 'Escape');
  out.keys.f = await press(page, 'f');
  // Enter on the name of the row of the test.
  await page.evaluate((id) => {
    const st = window.systemapCanvas.history(), it = st.items.find((o) => o.kind === 'r' && o.id === id);
    document.querySelector('#atlas-hworld [data-item="' + it.key + '"]').focus();
  }, id);
  out.named = await press(page, 'Enter');
  await page.waitForTimeout(500);
  out.map = await state(page);
  await page.click('#atlas-head [data-mode="history"]');
  await page.waitForTimeout(400);
  await page.setViewportSize({ width: 1000, height: 800 });
  await page.waitForTimeout(500);
  out.narrow = await state(page);
  return out;
}

async function phone(browser, file, id) {
  const out = { errors: [] };
  for (const scheme of ['light', 'dark']) {
    const { page, errors } = await open(browser, file, { ...PHONE, colorScheme: scheme });
    const mapView = await page.evaluate(() => {
      const r = (s) => { const e = document.querySelector(s); return e ? e.getBoundingClientRect().toJSON() : null; };
      const tabs = Array.from(document.querySelectorAll('#atlas-tabs [role="tab"]')).map((t) => t.getBoundingClientRect().toJSON());
      return { tabs, strip: r('#atlas-tabs'), views: r('#atlas-head .views'), ask: r('#atlas-ask'), scroll: document.documentElement.scrollWidth };
    });
    await page.tap('#atlas-head [data-mode="history"]');
    await page.waitForTimeout(700);
    const run = { mapView, shown: await state(page) };
    const c = await cellMid(page, id);
    await page.touchscreen.tap(c.at[0], c.at[1]);
    await page.waitForTimeout(300);
    run.tapped = await state(page);
    run.cell = c.key;
    out[scheme] = run;
    out.errors.push(...errors);
    await page.close();
  }
  return out;
}

async function axe(browser, file) {
  let source;
  try { source = require.resolve('axe-core/axe.min.js'); } catch (e) { return { axe: null, errors: [] }; }
  const out = { axe: [], errors: [] };
  for (const opts of [WIDE, PHONE]) for (const scheme of ['light', 'dark']) {
    const { page, errors } = await open(browser, file, { ...opts, colorScheme: scheme, bypassCSP: true });
    await page.click('#atlas-head [data-mode="history"]');
    await page.waitForTimeout(500);
    await page.focus('#atlas-hworld [tabindex="0"]');
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

async function none(browser, file) {
  const { page, errors } = await open(browser, file, { ...WIDE, colorScheme: 'light' });
  const out = { errors };
  out.shown = await state(page);
  out.mode = await page.evaluate(() => window.systemapCanvas.mode('history'));
  out.after = await state(page);
  return out;
}

(async () => {
  const [mode, file, id] = process.argv.slice(2);
  const browser = await chromium.launch();
  try {
    const run = { '--wide': wide, '--phone': phone, '--axe': axe, '--none': none }[mode];
    if (!run) throw new Error('unknown mode ' + mode);
    process.stdout.write(JSON.stringify(await run(browser, file, id)));
  } finally {
    await browser.close();
  }
})().catch((e) => { process.stderr.write(String(e.stack || e)); process.exit(1); });
