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
// - --labels W H: W x H with reduced motion. Each sequence of each map, at the whole route
//   and at each step: for each label of a line, the distance of its screen box to its own
//   line and to the nearest other line, and the height of the box. For the line of the
//   current step, its length on the screen and the part of it that no label covers. Also the
//   zoom of the map (`zoom`), the free part of the screen and the screen boxes of the cards
//   of the step: the source and the target of its flow, or its acting and measurement cards.
// - --open W H: W x H. A click on a card at step 2 opens the details: the boxes of the bar,
//   of the button Next, of the details, of the list and of the entry points with no
//   sequence, and the frame of the map at the whole route.
// - --wide also: a pointer on a card of a later step and then on the ground at step 2, and
//   the diagram after a change of the screen size to 1000 x 800.
// - --phone also: the background of the current name, and the diagram at step 5.
// - --motion also: the Reduce motion control of the header.
// - --labels also: the labels that show only at their step (`hide`), the frame of the map
//   and the box of the bar.
// - --open also: the boxes with the details open, at step 3 and at the last step.
// - --fit W H: W x H with reduced motion. Each sequence of each map in the diagram form: the
//   scale, the box, the scroll and the cards of the diagram, and the boxes of the step count,
//   the dots and the step controls of the bar.
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
  out.pointed = await pointAt(page, out.whole.seq.view);
  await page.focus('#atlas-step-next');
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(100);
  out.right = await state(page, false);
  await page.keyboard.press('ArrowLeft');
  await page.waitForTimeout(100);
  out.left = await state(page, false);
  await page.focus('#canvas');
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(100);
  out.canvasRight = await state(page, false);
  await page.focus('#atlas-rail-list button');
  await page.keyboard.press('ArrowLeft');
  await page.waitForTimeout(100);
  out.railLeft = await state(page, false);
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
  await page.setViewportSize({ width: 1000, height: 800 });
  await page.waitForTimeout(500);
  out.resized = await state(page, false);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(500);
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

// A pointer on a card of a later step, and then on the ground: the light of each, from the
// frame of the map at the right of the map.
async function pointAt(page, view) {
  const card = await page.evaluate((v) => {
    const d = JSON.parse(document.getElementById('atlas-data').textContent), m = d.maps.find((x) => x.id === v.map), st = m.sq[v.k].s;
    const later = st.slice(2).find((x) => x.f >= 0);
    return later ? m.flows[later.f].t : null;
  }, view);
  if (!card) return null;
  const b = await page.evaluate((id) => window.systemapCanvas.box('', id), card);
  await page.mouse.move(b[0] + b[2] / 2, b[1] + b[3] / 2);
  await page.waitForTimeout(300);
  const on = await state(page, false);
  await page.mouse.move(1430, 700);
  await page.waitForTimeout(300);
  return { card, on: on.lit, off: (await state(page, false)).lit };
}

async function nested(browser, file) {
  const { page, errors } = await open(browser, file, { ...WIDE, colorScheme: 'light' });
  const out = { errors };
  await page.click('#atlas-head [data-mode="seq"]');
  await page.waitForTimeout(900);
  out.top = await state(page, false);
  out.groups = await page.evaluate(() => Array.from(document.querySelectorAll('#atlas-rail .rail__g')).map((g) => g.textContent));
  out.steps = [];
  for (const n of [0, 1, 2]) {
    await page.evaluate((k) => window.systemapCanvas.step(k), n);
    await page.waitForTimeout(150);
    out.steps.push((await state(page, false)).seq.view);
  }
  await page.evaluate(() => window.systemapCanvas.step(-1));
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
    whole.askN = await page.evaluate(() => { const e = document.getElementById('atlas-ask-n'); return { display: getComputedStyle(e).display, text: e.textContent, box: e.getBoundingClientRect().toJSON() }; });
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
    step.railBg = await page.evaluate(() => getComputedStyle(document.querySelector('#atlas-rail-list button[aria-current="true"]')).backgroundColor);
    await page.tap('[data-form="diagram"]');
    await page.waitForTimeout(400);
    for (let i = 0; i < 3; i++) { await page.tap('#atlas-step-next'); await page.waitForTimeout(250); }
    const diagram = await state(page, false);
    out[scheme] = { errors, whole, step, diagram };
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
  // The Reduce motion control of the header, with no reduced motion of the device.
  const { page, errors } = await open(browser, file, { ...WIDE, reducedMotion: 'no-preference' });
  await page.click('#atlas-head [data-mode="seq"]');
  await page.waitForTimeout(1200);
  await page.click('#atlas-motion');
  await page.waitForTimeout(100);
  await page.click('#atlas-step-next');
  await page.waitForTimeout(50);
  const s = await state(page, true);
  out.button = { errors, pressed: await page.getAttribute('#atlas-motion', 'aria-pressed'), dim: s.lit.dim, parts: s.drawn.marks.filter((m) => m.t === 'lit').map((m) => m.part) };
  await page.close();
  return out;
}

// The distance of box b (x0, y0, x1, y1) to the segment from p to q.
function boxDist(b, p, q) {
  let best = Infinity;
  const n = Math.max(1, Math.ceil(Math.hypot(q[0] - p[0], q[1] - p[1])));
  for (let i = 0; i <= n; i++) {
    const x = p[0] + (q[0] - p[0]) * i / n, y = p[1] + (q[1] - p[1]) * i / n;
    best = Math.min(best, Math.hypot(Math.max(b[0] - x, 0, x - b[2]), Math.max(b[1] - y, 0, y - b[3])));
  }
  return best;
}
function lineDist(b, pts) {
  let best = Infinity;
  for (let i = 0; i + 1 < pts.length; i++) best = Math.min(best, boxDist(b, pts[i], pts[i + 1]));
  return best;
}
// The length of the line pts, and the part of it that is in no box of `boxes`.
function freeLength(pts, boxes) {
  let all = 0, free = 0;
  for (let i = 0; i + 1 < pts.length; i++) {
    const p = pts[i], q = pts[i + 1], l = Math.hypot(q[0] - p[0], q[1] - p[1]), n = Math.max(1, Math.ceil(l));
    for (let k = 0; k < n; k++) {
      const x = p[0] + (q[0] - p[0]) * (k + 0.5) / n, y = p[1] + (q[1] - p[1]) * (k + 0.5) / n;
      all += l / n;
      if (!boxes.some((b) => x >= b[0] && x <= b[2] && y >= b[1] && y <= b[3])) free += l / n;
    }
  }
  return [all, free];
}
// The marks of map `id` in one frame.
async function marksOf(page, id) {
  return page.evaluate((id) => {
    let cur = null;
    return window.systemapCanvas.drawn().marks.filter((m) => { if (m.t === 'map') cur = m.id; return cur === id && ['line', 'label', 'litLabel', 'lit'].includes(m.t); });
  }, id);
}
function measure(marks, W, H) {
  const lines = {}, labels = [], out = {labels: [], lit: []};
  marks.forEach((m) => { if (m.t === 'line') lines[m.f] = m.p; else if (m.t === 'label' || m.t === 'litLabel') labels.push(m); });
  labels.forEach((l) => {
    const b = l.box;
    if (!lines[l.f] || b[2] < 0 || b[0] > W || b[3] < 0 || b[1] > H) return;
    let other = Infinity;
    for (const f in lines) if (+f !== l.f) other = Math.min(other, lineDist(b, lines[f]));
    const cx = (b[0] + b[2]) / 2, cy = (b[1] + b[3]) / 2, p = lines[l.f];
    let flat = false;
    for (let i = 0; i + 1 < p.length; i++) if (Math.abs(p[i][1] - p[i + 1][1]) < 0.5 && Math.abs(cy - p[i][1]) <= 2 && cx >= Math.min(p[i][0], p[i + 1][0]) && cx <= Math.max(p[i][0], p[i + 1][0])) flat = true;
    out.labels.push({f: l.f, s: l.s, t: l.t, own: lineDist(b, lines[l.f]), other: other, h: b[3] - b[1], step: l.step || '', flat: flat});
  });
  marks.filter((m) => m.t === 'lit').forEach((m) => {
    const [all, free] = freeLength(m.p, labels.map((l) => l.box));
    out.lit.push({f: m.f, all: all, free: free});
  });
  return out;
}

async function labels(browser, file, W, H) {
  const { page, errors } = await open(browser, file, { viewport: { width: W, height: H }, deviceScaleFactor: 2, reducedMotion: 'reduce' });
  await page.evaluate(() => window.systemapCanvas.mode('seq'));
  const runs = [];
  const maps = await page.evaluate(() => JSON.parse(document.getElementById('atlas-data').textContent).maps.filter((m) => m.sq && m.sq.length).map((m) => [m.id, m.sq.map((q) => q.s.length)]));
  for (const [id, counts] of maps) {
    for (let k = 0; k < counts.length; k++) {
      await page.evaluate(([id, k]) => window.systemapCanvas.choose(id, k), [id, k]);
      for (let n = -1; n < counts[k]; n++) {
        await page.evaluate((n) => window.systemapCanvas.step(n), n);
        await page.waitForTimeout(n < 0 ? 400 : 260);
        const extra = await page.evaluate((id) => {
          const s = window.systemapCanvas, v = s.seq().view, d = JSON.parse(document.getElementById('atlas-data').textContent);
          const m = d.maps.find((x) => x.id === id), st = v.step >= 0 ? m.sq[v.k].s[v.step] : null, f = st && st.f >= 0 ? m.flows[st.f] : null;
          const cards = st ? (f ? [f.s, f.t] : (st.a || []).concat(st.me || [])).map((c) => s.box(id, c)).filter(Boolean) : [];
          return { hidden: s.lines(id).labels.filter((x) => x.hide).map((x) => x.f), frame: s.frame(id), barTop: v.bar.box.top, bar: v.bar.box, name: v.id,
            zoom: v.zoom, free: v.free, cards };
        }, id);
        runs.push({map: id, k: k, step: n, ...extra, ...measure(await marksOf(page, id), W, H)});
      }
    }
  }
  await page.close();
  return { errors, runs };
}

async function opened(browser, file, W, H) {
  const { page, errors } = await open(browser, file, { viewport: { width: W, height: H }, deviceScaleFactor: 2, colorScheme: 'light' });
  await page.click('#atlas-head [data-mode="seq"]');
  await page.waitForTimeout(1200);
  const whole = await state(page, false);
  const rect = (sel) => page.evaluate((sel) => document.querySelector(sel).getBoundingClientRect().toJSON(), sel);
  const list = await page.evaluate(() => { const l = document.getElementById('atlas-rail-list'), r = l.getBoundingClientRect(); return { box: r.toJSON(), scroll: l.scrollHeight, client: l.clientHeight }; });
  const ne = await rect('#atlas-rail-ne');
  await page.click('#atlas-step-next');
  await page.click('#atlas-step-next');
  await page.waitForTimeout(900);
  const b = await page.evaluate(() => window.systemapCanvas.box('', window.systemapCanvas.lit().cards[0]));
  await page.mouse.click(b[0] + b[2] / 2, b[1] + b[3] / 2);
  await page.waitForTimeout(1200);
  const out = { errors, whole, list, ne, side: await rect('#atlas-side'), bar: await rect('#atlas-step'), next: await rect('#atlas-step-next'),
    nextHit: await page.evaluate(() => { const r = document.getElementById('atlas-step-next').getBoundingClientRect(), e = document.elementFromPoint(r.right - 4, r.top + r.height / 2); return !!e && !!e.closest('#atlas-step-next'); }) };
  out.openNe = ne && await rect('#atlas-rail-ne'); out.openList = await rect('#atlas-rail-list'); out.zoom = await rect('.zoom');
  await page.click('#atlas-step-next');
  await page.waitForTimeout(200);
  out.after = (await state(page, false)).seq.view.step;
  // The last step: the longest sentence of the bar in the sequence of this repository.
  const n = out.whole.seq.view.n;
  for (let i = 3; i < n; i++) { await page.click('#atlas-step-next'); await page.waitForTimeout(150); }
  await page.waitForTimeout(600);
  out.late = { step: (await state(page, false)).seq.view.step, bar: await rect('#atlas-step'), ne: await rect('#atlas-rail-ne'), list: await rect('#atlas-rail-list'), zoom: await rect('.zoom'), side: await rect('#atlas-side') };
  await page.close();
  return out;
}

// Each sequence of each map in the diagram form at the whole route: the scale, the part of
// the screen, the scroll and the card boxes of the diagram, and the boxes of the step count,
// the dots and the step controls of the bar.
async function fitted(browser, file, W, H) {
  const { page, errors } = await open(browser, file, { viewport: { width: W, height: H }, deviceScaleFactor: 2, reducedMotion: 'reduce' });
  await page.evaluate(() => { window.systemapCanvas.mode('seq'); window.systemapCanvas.form('diagram'); });
  const runs = [];
  const maps = await page.evaluate(() => JSON.parse(document.getElementById('atlas-data').textContent).maps.filter((m) => m.sq && m.sq.length).map((m) => [m.id, m.sq.length]));
  for (const [id, count] of maps) {
    for (let k = 0; k < count; k++) {
      await page.evaluate(([id, k]) => window.systemapCanvas.choose(id, k), [id, k]);
      await page.waitForTimeout(150);
      runs.push(await page.evaluate(([id, k]) => {
        const s = window.systemapCanvas, b = s.seq().board, v = s.seq().view;
        const r = (sel) => document.querySelector(sel).getBoundingClientRect().toJSON();
        return { map: id, k, name: v.id, n: v.n, board: { k: b.k, view: b.view, scroll: b.scroll, nodes: b.nodes }, count: r('#atlas-step-n'), dots: r('#atlas-step-dots'), nav: r('#atlas-step .nav') };
      }, [id, k]));
    }
  }
  await page.close();
  return { errors, runs };
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
  const [mode, file, w, h] = process.argv.slice(2);
  const browser = await chromium.launch();
  const run = { '--wide': wide, '--nested': nested, '--phone': phone, '--motion': motion, '--axe': axe, '--labels': labels, '--open': opened, '--fit': fitted }[mode];
  const out = await run(browser, file, +w, +h);
  await browser.close();
  process.stdout.write(JSON.stringify(out) + '\n');
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
