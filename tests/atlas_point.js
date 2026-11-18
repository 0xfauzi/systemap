// The browser part of tests/test_atlas_point_browser.py: pointing and selecting on the atlas page.
//
//     node atlas_point.js MODE PAGE.html CARD [MAP]
//
// MODE is one of:
// - --point: 1440 x 900. A mouse move onto CARD of the top map: the light, the lit lines of
//   each frame for 900 ms (`systemapCanvas.drawn`), the colors of the canvas at the middle of
//   the lit lines, the labels, and the reading line. Then the same for a move onto the line
//   of the first lit flow, and for a card with no flow in the layer.
// - --select: 1440 x 900. A click on CARD: the details, the frame of the map, the selection
//   ring and the rows. Then a pointer on the first row, a click on that row, and Esc.
// - --phone: 390 x 844 with a touch screen. A tap on CARD: the sheet and the card box.
// - --keys: 1440 x 900. Tab, Enter, Esc and F on the canvas.
// - --motion: the light of CARD with the reduced motion of the device, and with the Reduce
//   motion button of the page.
// - --nested: 1440 x 900 on a page with the nested map MAP that CARD opens. The details of
//   CARD, the button that goes into the map, the path of the headline, a click on a
//   neighbour in MAP, and Esc in MAP.
// - --axe: axe-core with the details open, in the light and the dark scheme, at 1440 x 900
//   and at 390 x 844 (null when axe-core is not on NODE_PATH).
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
async function boxOf(page, map, id) { return page.evaluate(([m, c]) => window.systemapCanvas.box(m, c), [map, id]); }
function mid(b) { return [b[0] + b[2] / 2, b[1] + b[3] / 2]; }
const state = () => ({ lit: window.systemapCanvas.lit(), say: window.systemapCanvas.say(), side: window.systemapCanvas.side(),
  keys: window.systemapCanvas.keys(), chain: window.systemapCanvas.chain(), current: window.systemapCanvas.current(),
  camera: window.systemapCanvas.camera(), active: document.activeElement && document.activeElement.id });

// The colors of the canvas at screen points (CSS pixels), as [R, G, B].
function colorsAt(points) {
  const c = document.getElementById('canvas'), g = c.getContext('2d'), d = c.width / innerWidth;
  return points.map((p) => Array.from(g.getImageData(Math.round(p[0] * d), Math.round(p[1] * d), 1, 1).data.slice(0, 3)));
}
// Points along each lit line of a frame: from 10 % to 90 % of each segment of 20 px or more.
function samples(marks) {
  return marks.filter((m) => m.t === 'lit').map((m) => {
    const at = [];
    for (let i = 0; i + 1 < m.p.length; i++) {
      const a = m.p[i], b = m.p[i + 1];
      if (Math.hypot(b[0] - a[0], b[1] - a[1]) < 20) continue;
      for (let t = 0.1; t < 0.95; t += 0.1) at.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]);
    }
    return { f: m.f, k: m.k, at };
  });
}

async function point(browser, file, card) {
  const { page, errors } = await open(browser, file, WIDE);
  const at = mid(await boxOf(page, '', card));
  await page.mouse.move(at[0], at[1]);
  // The frames of the draw, each 30 ms.
  const frames = [];
  for (let t = 0; t < 900; t += 30) {
    frames.push(await page.evaluate(() => window.systemapCanvas.drawn().marks.filter((m) => m.t === 'lit' || m.t === 'line' || m.t === 'litLabel')));
    await page.waitForTimeout(30);
  }
  const out = { errors, frames, state: await page.evaluate(state) };
  const drawn = await page.evaluate(() => window.systemapCanvas.drawn());
  out.drawn = drawn;
  out.colors = [];
  for (const one of samples(drawn.marks)) out.colors.push({ f: one.f, k: one.k, colors: await page.evaluate(`(${colorsAt.toString()})(${JSON.stringify(one.at)})`) });
  out.kinds = await page.evaluate(() => { const cs = getComputedStyle(document.documentElement); return ['--data', '--control', '--judge', '--context', '--tool', '--ink-2', '--map'].reduce((o, k) => { o[k] = cs.getPropertyValue(k).trim(); return o; }, {}); });
  // A move onto the first lit line, at the middle of its longest segment.
  const line = samples(drawn.marks)[0], first = line && line.at.length ? { f: line.f, at: line.at[Math.floor(line.at.length / 2)] } : null;
  await page.mouse.move(5, 300);
  await page.waitForTimeout(400);
  out.away = await page.evaluate(state);
  if (first) {
    await page.mouse.move(first.at[0], first.at[1]);
    await page.waitForTimeout(600);
    out.line = { f: first.f, state: await page.evaluate(state) };
    // A click pins the line: it stays lit after the pointer goes.
    await page.mouse.click(first.at[0], first.at[1]);
    await page.mouse.move(5, 300);
    await page.waitForTimeout(400);
    out.pinned = await page.evaluate(state);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
    out.unpinned = await page.evaluate(state);
  }
  // A card with no flow in the layer.
  const quiet = await page.evaluate(() => { const q = window.systemapCanvas.quiet('').find((x) => x.q); return q ? q.id : null; });
  if (quiet) {
    const qa = mid(await boxOf(page, '', quiet));
    await page.mouse.move(qa[0], qa[1]);
    await page.waitForTimeout(500);
    out.quiet = { id: quiet, state: await page.evaluate(state) };
  }
  await page.close();
  return out;
}

const sideText = () => {
  const s = document.getElementById('atlas-side');
  return { kicker: document.getElementById('atlas-side-k').textContent, title: document.getElementById('atlas-side-h').textContent,
    rows: Array.prototype.map.call(s.querySelectorAll('.row'), (r) => ({ f: +r.getAttribute('data-f'), text: r.textContent })),
    heads: Array.prototype.map.call(s.querySelectorAll('.sec h3'), (h) => h.firstChild.textContent),
    text: s.textContent, enter: (s.querySelector('[data-go]') || { textContent: null }).textContent };
};

async function select(browser, file, card) {
  const { page, errors } = await open(browser, file, WIDE);
  const at = mid(await boxOf(page, '', card));
  await page.mouse.move(at[0], at[1]);
  await page.mouse.click(at[0], at[1]);
  await page.waitForTimeout(1600);
  const out = { errors, state: await page.evaluate(state), frame: await page.evaluate(() => window.systemapCanvas.frame('')),
    size: [1440, 900], details: await page.evaluate(sideText) };
  out.marks = (await page.evaluate(() => window.systemapCanvas.drawn())).marks.filter((m) => m.t === 'selected');
  const row = await page.$('#atlas-side .row');
  if (row) {
    await row.hover();
    await page.waitForTimeout(300);
    out.row = await page.evaluate(state);
    await row.click();
    await page.waitForTimeout(1600);
    out.rowClick = await page.evaluate(state);
  }
  await page.keyboard.press('Escape');
  await page.waitForTimeout(1600);
  out.closed = { state: await page.evaluate(state), frame: await page.evaluate(() => window.systemapCanvas.frame('')) };
  await page.close();
  return out;
}

async function phone(browser, file, card) {
  const { page, errors } = await open(browser, file, PHONE);
  const at = mid(await boxOf(page, '', card));
  await page.touchscreen.tap(at[0], at[1]);
  await page.waitForTimeout(1600);
  const out = { errors, state: await page.evaluate(state), box: await boxOf(page, '', card),
    head: await page.evaluate(() => document.getElementById('atlas-ask').getBoundingClientRect().bottom),
    scroll: await page.evaluate(() => document.documentElement.scrollWidth) };
  await page.close();
  return out;
}

async function keys(browser, file, card) {
  const { page, errors } = await open(browser, file, WIDE);
  const order = await page.evaluate(() => window.systemapCanvas.tabOrder(''));
  await page.focus('#canvas');
  const steps = [];
  for (let i = 0; i < 3; i++) { await page.keyboard.press('Tab'); await page.waitForTimeout(350); steps.push(await page.evaluate(state)); }
  // Tab to the card, then Enter.
  const n = order.findIndex((x) => x.id === card);
  for (let i = 3; i <= n; i++) await page.keyboard.press('Tab');
  await page.waitForTimeout(400);
  const onCard = await page.evaluate(state);
  await page.keyboard.press('Enter');
  await page.waitForTimeout(1200);
  const entered = await page.evaluate(state);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(1200);
  const escaped = await page.evaluate(state);
  await page.evaluate(() => { const a = window.systemapCanvas, c = a.camera(); a.view({ x: c.x + 300, y: c.y, k: c.k * 1.7 }); });
  await page.waitForTimeout(300);
  await page.keyboard.press('f');
  await page.waitForTimeout(1500);
  const fitted = { camera: await page.evaluate(() => window.systemapCanvas.camera()), fit: await page.evaluate(() => window.systemapCanvas.fit('')) };
  await page.close();
  return { errors, order, steps, onCard, entered, escaped, fitted };
}

async function lightOf(page, card) {
  const at = mid(await boxOf(page, '', card));
  await page.mouse.move(at[0], at[1]);
  await page.waitForTimeout(50);
  return page.evaluate(() => ({ lit: window.systemapCanvas.lit(), parts: window.systemapCanvas.drawn().marks.filter((m) => m.t === 'lit').map((m) => m.part) }));
}

async function motion(browser, file, card) {
  const out = {};
  const device = await open(browser, file, { ...WIDE, reducedMotion: 'reduce' });
  out.device = { errors: device.errors, light: await lightOf(device.page, card) };
  await device.page.close();
  const plain = await open(browser, file, WIDE);
  out.plain = { light: await lightOf(plain.page, card) };
  await plain.page.mouse.move(5, 300);
  await plain.page.waitForTimeout(400);
  await plain.page.click('#atlas-motion');
  out.button = { pressed: await plain.page.getAttribute('#atlas-motion', 'aria-pressed'), attr: await plain.page.evaluate(() => document.documentElement.getAttribute('data-reduce-motion')),
    light: await lightOf(plain.page, card), errors: plain.errors };
  await plain.page.close();
  return out;
}

async function nested(browser, file, card, map) {
  const { page, errors } = await open(browser, file, WIDE);
  const marks = (await page.evaluate(() => window.systemapCanvas.drawn())).marks;
  const at = mid(await boxOf(page, '', card));
  await page.mouse.click(at[0], at[1]);
  await page.waitForTimeout(1200);
  const out = { errors, marks: marks.filter((m) => (m.t === 'card' && m.id === card) || (m.t === 'map' && m.id === map)), details: await page.evaluate(sideText) };
  await page.click('#atlas-side [data-go]');
  await page.waitForTimeout(2000);
  out.inside = { state: await page.evaluate(state), path: await page.evaluate(() => Array.prototype.map.call(document.querySelectorAll('#atlas-ask-k button'), (b) => b.textContent)) };
  const nb = await page.evaluate((m) => window.systemapCanvas.boxes(m).filter((c) => c.k === 'actor')[0], map);
  out.neighbour = nb ? nb.id : null;
  if (nb) {
    await page.mouse.move(...mid(nb.b));
    await page.waitForTimeout(300);
    out.neighbourSay = await page.evaluate(() => window.systemapCanvas.say());
    await page.mouse.click(...mid(nb.b));
    await page.waitForTimeout(2500);
    out.out = await page.evaluate(state);
  }
  // Into the map again, then Esc goes out one level.
  await page.keyboard.press('Escape');
  await page.waitForTimeout(1500);
  const g = mid(await boxOf(page, '', card));
  await page.mouse.dblclick(g[0], g[1]);
  await page.waitForTimeout(2000);
  const again = await page.evaluate(state);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(2000);
  out.esc = { before: again, after: await page.evaluate(state) };
  await page.close();
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

async function axe(browser, file, card) {
  const runs = [];
  for (const opts of [WIDE, PHONE]) {
    for (const scheme of ['light', 'dark']) {
      const { page, errors } = await open(browser, file, { ...opts, colorScheme: scheme, reducedMotion: 'reduce', bypassCSP: true });
      await page.evaluate((c) => window.systemapCanvas.select('', c), card);
      await page.waitForTimeout(500);
      runs.push({ scheme, width: opts.viewport.width, errors, axe: await axeRun(page) });
      await page.close();
    }
  }
  return { runs };
}

(async () => {
  const [mode, file, card, map] = process.argv.slice(2);
  const browser = await chromium.launch();
  const run = { '--point': point, '--select': select, '--phone': phone, '--keys': keys, '--motion': motion, '--nested': nested, '--axe': axe }[mode];
  const out = await run(browser, file, card, map);
  await browser.close();
  process.stdout.write(JSON.stringify(out) + '\n');
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
