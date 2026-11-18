// The browser part of tests/test_atlas_point_browser.py: pointing and selecting on the atlas page.
//
//     node atlas_point.js MODE PAGE.html CARD [MAP]
//
// MODE is one of:
// - --point: 1440 x 900. A mouse move onto CARD of the top map: the light, the lit lines of
//   each frame for 900 ms (`systemapCanvas.drawn`), the colors of the canvas at the middle of
//   the lit lines, the labels, and the reading line. Then the same for a move onto the line
//   of the first lit flow, and for a card with no flow in the layer.
//   Also the rest marks before the move, and one frame in the middle of the draw.
// - --labels: 1440 x 900, layer All. The lit labels of each card that is not an actor.
// - --select: 1440 x 900. A click on CARD: the details, the frame of the map, the selection
//   ring and the rows. Then a pointer on the first row, a click on that row, and Esc.
// - --phone: 390 x 844 with a touch screen. A tap on CARD: the sheet and the card box. Then
//   a tap on a line.
// - --resize: a click on CARD at 1440 x 900, then a change of the window to 390 x 844: the
//   sheet and the card box.
// - --keys: 1440 x 900. Tab through the full order, Enter on a line and on CARD, Tab to a
//   row of the details, Esc in the details, F, and Esc and F on a button of the page.
// - --motion: the light of CARD and a click on CARD with the reduced motion of the device,
//   with the Reduce motion button of the page, and with no reduced motion.
// - --nested: 1440 x 900 on a page with the nested map MAP that CARD opens. The details of
//   CARD, the button that goes into the map, the path of the headline, a click on a
//   neighbour in MAP, and Esc in MAP. The reading line after a double-click, after a zoom
//   and after Shift+Enter on the card, and a click on the path of the headline.
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

// In the page: wait for a frame in which a lit line is drawn from 30 % to 65 % of its
// length. In that same frame, give the colors of the canvas near the start and near the end
// of each such line, and the dash of the line.
function midDraw() {
  return new Promise((done) => {
    const t0 = performance.now();
    function along(p, t) {
      const seg = [];
      let total = 0;
      for (let i = 0; i + 1 < p.length; i++) { const l = Math.hypot(p[i + 1][0] - p[i][0], p[i + 1][1] - p[i][1]); seg.push(l); total += l; }
      let want = total * t;
      for (let i = 0; i < seg.length; i++) {
        if (want <= seg[i] || i === seg.length - 1) { const u = seg[i] ? Math.min(1, want / seg[i]) : 0; return [p[i][0] + (p[i + 1][0] - p[i][0]) * u, p[i][1] + (p[i + 1][1] - p[i][1]) * u]; }
        want -= seg[i];
      }
      return p[0];
    }
    (function step() {
      const marks = window.systemapCanvas.drawn().marks.filter((m) => m.t === 'lit' && m.part >= 0.3 && m.part <= 0.65);
      if (marks.length || performance.now() - t0 > 2000) {
        const c = document.getElementById('canvas'), g = c.getContext('2d'), d = c.width / innerWidth;
        const at = (q) => Array.from(g.getImageData(Math.round(q[0] * d), Math.round(q[1] * d), 1, 1).data.slice(0, 3));
        done(marks.map((m) => ({ f: m.f, k: m.k, part: m.part, dash: m.dash,
          start: [0.06, 0.12, 0.18].map((t) => at(along(m.p, t))), end: [0.82, 0.88, 0.94].map((t) => at(along(m.p, t))) })));
        return;
      }
      requestAnimationFrame(step);
    })();
  });
}

async function point(browser, file, card) {
  const { page, errors } = await open(browser, file, WIDE);
  const at = mid(await boxOf(page, '', card));
  const restMarks = (await page.evaluate(() => window.systemapCanvas.drawn())).marks.filter((m) => m.t === 'line' || m.t === 'card');
  await page.mouse.move(at[0], at[1]);
  // The frames of the draw, each 30 ms.
  const frames = [];
  for (let t = 0; t < 900; t += 30) {
    frames.push(await page.evaluate(() => window.systemapCanvas.drawn().marks.filter((m) => m.t === 'lit' || m.t === 'line' || m.t === 'litLabel')));
    await page.waitForTimeout(30);
  }
  const out = { errors, frames, restMarks, state: await page.evaluate(state) };
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
  // The direction of the draw: a new move onto the card, and one frame in the middle of the
  // draw of its lines.
  await page.mouse.move(5, 300);
  await page.waitForTimeout(600);
  await page.mouse.move(at[0], at[1]);
  out.middle = await page.evaluate(`(${midDraw.toString()})()`);
  await page.mouse.move(5, 300);
  await page.waitForTimeout(400);
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

// Layer All: for each card that is not an actor, the lit labels, the card boxes and the
// texts of one frame with the full light.
async function labels(browser, file) {
  const { page, errors } = await open(browser, file, WIDE);
  await page.evaluate(() => window.systemapCanvas.setLayer('all'));
  await page.waitForTimeout(800);
  const ids = await page.evaluate(() => window.systemapCanvas.boxes('').filter((c) => c.k !== 'actor').map((c) => c.id));
  const runs = [];
  for (const id of ids) {
    await page.evaluate((c) => window.systemapCanvas.pointAt('', c), id);
    await page.waitForTimeout(700);
    const d = await page.evaluate(() => window.systemapCanvas.drawn());
    runs.push({ id, labels: d.marks.filter((m) => m.t === 'litLabel'), cards: d.marks.filter((m) => m.t === 'card' && m.map === '').map((m) => ({ id: m.id, b: m.b })),
      texts: d.texts.filter((t) => t.weight === 500) });
  }
  await page.close();
  return { errors, runs };
}

const sideText = () => {
  const s = document.getElementById('atlas-side');
  return { kicker: document.getElementById('atlas-side-k').textContent, title: document.getElementById('atlas-side-h').textContent,
    rows: Array.prototype.map.call(s.querySelectorAll('.row'), (r) => ({ f: +r.getAttribute('data-f'), text: r.textContent })),
    heads: Array.prototype.map.call(s.querySelectorAll('.sec h3'), (h) => h.firstChild.textContent),
    text: s.textContent, enter: (s.querySelector('[data-go]') || { textContent: null }).textContent,
    state: document.getElementById('atlas-side-s').textContent, short: document.getElementById('atlas-side-p').textContent,
    about: (s.querySelector('.side__body > .side__d') || { textContent: null }).textContent,
    summaries: Array.prototype.map.call(s.querySelectorAll('summary'), (x) => x.textContent),
    records: (s.querySelector('.rec') || { textContent: '' }).textContent,
    sequences: Array.prototype.map.call(s.querySelectorAll('.sec'), (x) => x).filter((x) => x.querySelector('h3').firstChild.textContent === 'Sequences').map((x) => Array.prototype.map.call(x.querySelectorAll('li'), (li) => li.textContent))[0] || [],
    rules: Array.prototype.map.call(s.querySelectorAll('.sec'), (x) => x).filter((x) => x.querySelector('h3').firstChild.textContent === 'Rules').map((x) => x.textContent)[0] || '' };
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
  // A tap on empty space closes the details. Then a tap on a line pins it.
  await page.keyboard.press('Escape');
  await page.waitForTimeout(800);
  const target = await page.evaluate(() => {
    const a = window.systemapCanvas, cards = a.boxes(''), H = innerHeight, side = a.side();
    const free = (q) => q[0] > 10 && q[0] < innerWidth - 10 && q[1] > document.getElementById('atlas-ask').getBoundingClientRect().bottom + 10 && q[1] < (side.on ? side.top : H) - 70 &&
      !cards.some((c) => q[0] > c.b[0] - 8 && q[0] < c.b[0] + c.b[2] + 8 && q[1] > c.b[1] - 8 && q[1] < c.b[1] + c.b[3] + 8);
    for (const x of a.tabOrder('')) {
      if (x.f === undefined) continue;
      const p = a.line('', x.f);
      for (let i = 0; p && i + 1 < p.length; i++) {
        const q = [(p[i][0] + p[i + 1][0]) / 2, (p[i][1] + p[i + 1][1]) / 2];
        if (Math.hypot(p[i + 1][0] - p[i][0], p[i + 1][1] - p[i][1]) > 30 && free(q)) return { f: x.f, at: q };
      }
    }
    return null;
  });
  if (target) {
    await page.touchscreen.tap(target.at[0], target.at[1]);
    await page.waitForTimeout(500);
    out.tapLine = { f: target.f, state: await page.evaluate(state) };
  }
  await page.close();
  return out;
}

// The details open at 1440 x 900, then the window changes to 390 x 844.
async function resize(browser, file, card) {
  const { page, errors } = await open(browser, file, WIDE);
  const at = mid(await boxOf(page, '', card));
  await page.mouse.move(at[0], at[1]);
  await page.mouse.click(at[0], at[1]);
  await page.waitForTimeout(1600);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(1600);
  const out = { errors, state: await page.evaluate(state), box: await boxOf(page, '', card),
    head: await page.evaluate(() => document.getElementById('atlas-ask').getBoundingClientRect().bottom) };
  await page.close();
  return out;
}

async function keys(browser, file, card) {
  const { page, errors } = await open(browser, file, WIDE);
  const order = await page.evaluate(() => window.systemapCanvas.tabOrder(''));
  await page.focus('#canvas');
  // Each Tab step through the full order. The camera can move (`showFocus`), so each step
  // waits for the reading line.
  const steps = [];
  for (let i = 0; i < order.length; i++) {
    await page.keyboard.press('Tab');
    await page.waitForTimeout(i < 3 ? 350 : 60);
    steps.push(await page.evaluate(state));
  }
  await page.keyboard.press('Tab');
  await page.waitForTimeout(100);
  const after = await page.evaluate(state);
  // Enter on a focused line pins it. A click on empty space removes the keyboard focus of
  // the item and gives the focus to the canvas.
  await page.mouse.click(5, 300);
  const li = order.findIndex((x) => x.f !== undefined);
  for (let i = 0; i <= li; i++) await page.keyboard.press('Tab');
  await page.waitForTimeout(1200);
  await page.keyboard.press('Enter');
  await page.waitForTimeout(300);
  const pinned = await page.evaluate(state);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);
  // Tab to the card, then Enter.
  await page.mouse.click(5, 300);
  await page.waitForTimeout(1200);
  const n = order.findIndex((x) => x.id === card);
  for (let i = 0; i <= n; i++) await page.keyboard.press('Tab');
  await page.waitForTimeout(400);
  const onCard = await page.evaluate(state);
  await page.keyboard.press('Enter');
  await page.waitForTimeout(1200);
  const entered = await page.evaluate(state);
  // Tab from the heading of the details to the first flow row.
  let tabs = 0;
  while (tabs < 40 && !(await page.evaluate(() => !!(document.activeElement && document.activeElement.classList.contains('row'))))) { await page.keyboard.press('Tab'); tabs++; }
  await page.waitForTimeout(300);
  const onRow = { tabs, f: await page.evaluate(() => +document.activeElement.getAttribute('data-f')), state: await page.evaluate(state) };
  // Esc with the keyboard focus in the details.
  await page.keyboard.press('Escape');
  await page.waitForTimeout(1200);
  const escaped = await page.evaluate(state);
  await page.evaluate(() => { const a = window.systemapCanvas, c = a.camera(); a.view({ x: c.x + 300, y: c.y, k: c.k * 1.7 }); });
  await page.waitForTimeout(300);
  await page.keyboard.press('f');
  await page.waitForTimeout(1500);
  const fitted = { camera: await page.evaluate(() => window.systemapCanvas.camera()), fit: await page.evaluate(() => window.systemapCanvas.fit('')) };
  // Esc and F with the keyboard focus on a button of the page: the details open with a
  // click, then a click on the Reduce motion button (two times), then Esc.
  const at = mid(await boxOf(page, '', card));
  await page.mouse.click(at[0], at[1]);
  await page.waitForTimeout(1200);
  await page.click('#atlas-motion'); await page.click('#atlas-motion');
  const before = await page.evaluate(state);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(1200);
  const button = { before, after: await page.evaluate(state) };
  await page.evaluate(() => { const a = window.systemapCanvas, c = a.camera(); a.view({ x: c.x + 300, y: c.y, k: c.k * 1.7 }); });
  await page.waitForTimeout(300);
  await page.focus('#atlas-zf');
  await page.keyboard.press('F');
  await page.waitForTimeout(1500);
  button.fitted = { active: await page.evaluate(() => document.activeElement.id), camera: await page.evaluate(() => window.systemapCanvas.camera()), fit: await page.evaluate(() => window.systemapCanvas.fit('')) };
  await page.close();
  return { errors, order, steps, after, pinned, onCard, entered, onRow, escaped, fitted, button };
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
  out.button.select = await selectNow(plain.page, card);
  await plain.page.close();
  const dev = await open(browser, file, { ...WIDE, reducedMotion: 'reduce' });
  out.device.select = await selectNow(dev.page, card);
  await dev.page.close();
  const slow = await open(browser, file, WIDE);
  out.plain.select = await selectNow(slow.page, card);
  await slow.page.close();
  return out;
}
// A click on the card: the details and the camera 50 ms later and 1.5 s later, and the
// transition of the details.
async function selectNow(page, card) {
  const at = mid(await boxOf(page, '', card));
  await page.mouse.click(at[0], at[1]);
  await page.waitForTimeout(50);
  const soon = await page.evaluate(() => ({ side: window.systemapCanvas.side(), camera: window.systemapCanvas.camera(),
    shown: document.getElementById('atlas-side').classList.contains('on'), transform: getComputedStyle(document.getElementById('atlas-side')).transform }));
  await page.waitForTimeout(1500);
  return { soon, late: await page.evaluate(() => ({ side: window.systemapCanvas.side(), camera: window.systemapCanvas.camera(),
    transform: getComputedStyle(document.getElementById('atlas-side')).transform })) };
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
  // The reading line after a double-click on the pointed card.
  await page.keyboard.press('Escape');
  await page.waitForTimeout(2000);
  const g2 = mid(await boxOf(page, '', card));
  await page.mouse.move(g2[0], g2[1]);
  await page.waitForTimeout(300);
  out.pointed = await page.evaluate(state);
  await page.mouse.dblclick(g2[0], g2[1]);
  await page.waitForTimeout(2000);
  out.dblSay = await page.evaluate(state);
  // The path of the headline goes to the top map.
  await page.click('#atlas-ask-k button');
  await page.waitForTimeout(2000);
  out.pathOut = await page.evaluate(state);
  // A zoom with the camera into the map, while the pointer stays on the card.
  const g3 = mid(await boxOf(page, '', card));
  await page.mouse.move(g3[0], g3[1]);
  await page.waitForTimeout(300);
  await page.evaluate((m) => { const a = window.systemapCanvas, f = a.fit(m, true); a.view({ x: f.x, y: f.y, k: f.k }); }, map);
  await page.waitForTimeout(1200);
  out.zoomSay = await page.evaluate(state);
  await page.evaluate(() => { const a = window.systemapCanvas, f = a.fit(''); a.view({ x: f.x, y: f.y, k: f.k }); });
  await page.waitForTimeout(1200);
  // Tab to the card and Shift+Enter.
  await page.focus('#canvas');
  const order = await page.evaluate(() => window.systemapCanvas.tabOrder(''));
  const n = order.findIndex((x) => x.id === card);
  for (let i = 0; i <= n; i++) await page.keyboard.press('Tab');
  await page.waitForTimeout(400);
  out.keyed = await page.evaluate(state);
  await page.keyboard.press('Shift+Enter');
  await page.waitForTimeout(2000);
  out.shiftEnter = await page.evaluate(state);
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
  const run = { '--point': point, '--labels': labels, '--select': select, '--phone': phone, '--resize': resize, '--keys': keys, '--motion': motion, '--nested': nested, '--axe': axe }[mode];
  const out = await run(browser, file, card, map);
  await browser.close();
  process.stdout.write(JSON.stringify(out) + '\n');
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
