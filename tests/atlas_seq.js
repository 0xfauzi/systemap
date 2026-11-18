// The browser part of tests/test_atlas_sequences_browser.py: the Sequences view of the atlas page.
//
//     node atlas_seq.js MODE PAGE.html
//
// MODE is one of:
// - --wide: 1440 x 900. A click on Sequences: the view, the headline, the list, the bar and
//   one frame (`systemapCanvas.drawn`). Then Start, Next, the arrow keys (also with the
//   keyboard focus on Next), the last step and Done. Then the diagram form: its rows, a
//   click on a row, and Enter on a focused row. Then the map form and the Map view.
// - --nested: 1440 x 900 on a page with the sequences of the top map and of the nested map
//   Gateway. A click on the second item of the list, and the steps of that sequence on the
//   map and in the diagram.
// - --phone: 390 x 844 with a touch screen. The list, the headline, the bar and the frame of
//   the map in the Sequences view. Then two taps on Next.
// - --motion: the light of the first step 50 ms after Start, with the reduced motion of the
//   device and with no reduced motion.
// - --axe: axe-core in the Sequences view at step 2 on the map and in the diagram, in the
//   light and the dark scheme, at 1440 x 900 and at 390 x 844 (null when axe-core is not on
//   NODE_PATH).
// Each mode prints one JSON object. `errors` has the script errors of the page.
'use strict';
const fs = require('fs');
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
// The state of the page: the view, the light, the headline, the camera, the boxes and one frame.
async function state(page, frame) {
  return page.evaluate(([frame]) => {
    const s = window.systemapCanvas;
    const b = (sel) => { const e = document.querySelector(sel); return e ? e.getBoundingClientRect().toJSON() : null; };
    const tokens = {};
    ['--ink-2', '--ink-3', '--wire', '--data', '--control', '--judge', '--context', '--tool'].forEach((n) => { tokens[n] = getComputedStyle(document.documentElement).getPropertyValue(n).trim(); });
    return { seq: s.seq(), view: s.viewState(), lit: s.lit(), current: s.current(), camera: s.camera(), frame: s.frame(s.current()),
      say: s.say(), said: document.getElementById('atlas-said').textContent, ask: b('#atlas-ask'), canvas: getComputedStyle(document.getElementById('canvas')).visibility,
      tabs: getComputedStyle(document.getElementById('atlas-tabs')).display, key: getComputedStyle(document.getElementById('atlas-key')).display,
      note: getComputedStyle(document.getElementById('atlas-note')).display, quiet: s.quiet(s.current()), active: document.activeElement && (document.activeElement.id || document.activeElement.getAttribute('data-step')),
      pressed: Array.from(document.querySelectorAll('#atlas-head [data-mode]')).map((x) => [x.textContent, x.getAttribute('aria-pressed')]),
      tokens, scroll: document.documentElement.scrollWidth, drawn: frame ? s.drawn() : null };
  }, [!!frame]);
}

async function wide(browser, file) {
  const { page, errors } = await open(browser, file, { ...WIDE, colorScheme: 'light' });
  const out = { errors };
  out.before = await state(page, true);
  await page.click('#atlas-head [data-mode="seq"]');
  await page.waitForTimeout(1200);
  out.whole = await state(page, true);
  await page.click('#atlas-step-next');
  await page.waitForTimeout(300);
  out.first = await state(page, false);
  await page.click('#atlas-step-next');
  await page.waitForTimeout(1200);
  out.second = await state(page, true);
  await page.focus('#atlas-step-next');
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(100);
  out.right = await state(page, false);
  await page.keyboard.press('ArrowLeft');
  await page.waitForTimeout(100);
  out.left = await state(page, false);
  const n = out.whole.seq.view.n;
  for (let i = 0; i < n + 2; i++) await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(100);
  out.last = await state(page, false);
  await page.click('#atlas-step-next');
  await page.waitForTimeout(100);
  out.done = await state(page, false);
  await page.click('#atlas-step-next');
  await page.click('#atlas-step-next');
  await page.click('[data-form="diagram"]');
  await page.waitForTimeout(500);
  out.diagram = await state(page, false);
  const rows = out.diagram.seq.board.rows;
  if (rows.length > 2) {
    const r = rows[2].box;
    await page.mouse.click(r.x + r.width / 2, r.y + r.height / 2);
    await page.waitForTimeout(300);
    out.rowClick = await state(page, false);
  }
  await page.focus('#atlas-bworld [data-step="0"]');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(300);
  out.rowKey = await state(page, false);
  await page.click('[data-form="map"]');
  await page.waitForTimeout(900);
  out.onMap = await state(page, false);
  await page.click('#atlas-head [data-mode="map"]');
  await page.waitForTimeout(1200);
  out.map = await state(page, true);
  await page.close();
  return out;
}

async function nested(browser, file) {
  const { page, errors } = await open(browser, file, { ...WIDE, colorScheme: 'light' });
  const out = { errors };
  await page.click('#atlas-head [data-mode="seq"]');
  await page.waitForTimeout(900);
  out.top = await state(page, false);
  out.groups = await page.evaluate(() => Array.from(document.querySelectorAll('#atlas-rail .rail__g')).map((g) => g.textContent));
  await page.click('#atlas-rail-list button:nth-of-type(2)');
  await page.waitForTimeout(1800);
  out.chosen = await state(page, true);
  await page.click('#atlas-step-next');
  await page.click('#atlas-step-next');
  await page.waitForTimeout(900);
  out.noflow = await state(page, true);
  await page.click('[data-form="diagram"]');
  await page.waitForTimeout(400);
  out.diagram = await state(page, false);
  await page.close();
  return out;
}

async function phone(browser, file) {
  const out = {};
  for (const scheme of ['light', 'dark']) {
    const { page, errors } = await open(browser, file, { ...PHONE, colorScheme: scheme });
    await page.tap('#atlas-head [data-mode="seq"]');
    await page.waitForTimeout(1200);
    const whole = await state(page, false);
    await page.tap('#atlas-step-next');
    await page.waitForTimeout(300);
    await page.tap('#atlas-step-next');
    await page.waitForTimeout(1400);
    const step = await state(page, false);
    step.cards = await page.evaluate(() => {
      const s = window.systemapCanvas, v = s.seq().view, d = JSON.parse(document.getElementById('atlas-data').textContent);
      const m = d.maps.find((x) => x.id === v.map), st = m.sq[v.k].s[v.step], f = st.f >= 0 ? m.flows[st.f] : null;
      return (f ? [f.s, f.t] : (st.a || [])).map((id) => s.box(v.map, id));
    });
    out[scheme] = { errors, whole, step };
    await page.close();
  }
  return out;
}

async function motion(browser, file) {
  const out = {};
  for (const reduce of ['reduce', 'no-preference']) {
    const { page, errors } = await open(browser, file, { ...WIDE, reducedMotion: reduce });
    await page.click('#atlas-head [data-mode="seq"]');
    await page.waitForTimeout(1200);
    await page.click('#atlas-step-next');
    await page.waitForTimeout(50);
    const s = await state(page, true);
    out[reduce] = { errors, dim: s.lit.dim, parts: s.drawn.marks.filter((m) => m.t === 'lit').map((m) => m.part) };
    await page.close();
  }
  return out;
}

async function axeRun(page) {
  let source;
  try { source = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8'); } catch (e) { return null; }
  await page.addScriptTag({ content: source });
  return page.evaluate(async () => {
    const r = await window.axe.run(document, { resultTypes: ['violations'] });
    return { violations: r.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical').map((v) => v.id + ': ' + v.nodes.map((n) => n.target.join(' ')).join(', ')) };
  });
}

async function axe(browser, file) {
  const runs = [];
  for (const opts of [WIDE, PHONE]) {
    for (const scheme of ['light', 'dark']) {
      const { page, errors } = await open(browser, file, { ...opts, colorScheme: scheme, reducedMotion: 'reduce', bypassCSP: true });
      await page.evaluate(() => { window.systemapCanvas.mode('seq'); window.systemapCanvas.step(1); });
      await page.waitForTimeout(400);
      runs.push({ scheme, width: opts.viewport.width, form: 'map', errors, axe: await axeRun(page) });
      await page.evaluate(() => window.systemapCanvas.form('diagram'));
      await page.waitForTimeout(300);
      runs.push({ scheme, width: opts.viewport.width, form: 'diagram', errors, axe: await axeRun(page) });
      await page.close();
    }
  }
  return { runs };
}

(async () => {
  const [mode, file] = process.argv.slice(2);
  const browser = await chromium.launch();
  const run = { '--wide': wide, '--nested': nested, '--phone': phone, '--motion': motion, '--axe': axe }[mode];
  const out = await run(browser, file);
  await browser.close();
  process.stdout.write(JSON.stringify(out) + '\n');
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
