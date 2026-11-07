// Drives a canvas page (systemap.canvas_page) in the Chromium of Playwright for the Sequences
// view, and prints one JSON object. tests/test_canvas_sequences_browser.py reads it.
//
//     node tests/canvas_sequences.js --choose PAGE.html MAP SEQUENCE [--phone]
//     node tests/canvas_sequences.js --fade PAGE.html MAP SEQUENCE
//     node tests/canvas_sequences.js --keys PAGE.html MAP
//     node tests/canvas_sequences.js --access PAGE.html MAP SEQUENCE
//     node tests/canvas_sequences.js --shots PAGE.html MAP SEQUENCE FOLDER
//     node tests/canvas_sequences.js --routes PAGE.html MAP
//
// --routes gives, for each sequence of MAP, the values of the flows of MAP at its fit in the
// Whole route and at each step.
// MAP is the ID of the map of the sequence SEQUENCE. --choose starts at the top map with
// reduced motion, goes into the Sequences view, selects the sequence with the keyboard in
// the listbox, and gives the camera, the fit of MAP, the bands of the fit, the values of the
// flows of MAP in the last frame, and the marks of the route. Then it goes through the steps
// with Start at step 1, Next and Previous, and gives the screen boxes of the cards of each
// step. --fade does the same changes without reduced motion and gives the values of each
// frame; then it does them with the reduced motion of the system and of the page. --keys
// gives the order of Tab, the names and the focus outline of the toolbar controls, and the
// camera after the keys of the listbox and of the toolbar. --access runs axe-core (from
// NODE_PATH; null when it is not there) with the toolbar shown and with the list open, and
// gives the target boxes and the scroll on a phone. --shots writes screenshots.
'use strict';
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const DESK = { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 };
const PHONE = { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3 };
const settle = (page, ms) => page.waitForTimeout(ms || 400);

async function open(file, options) {
  const browser = await chromium.launch();
  const context = await browser.newContext({ colorScheme: 'dark', reducedMotion: 'reduce', ...DESK, ...options });
  const page = await context.newPage(), errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + file + (options && options.hash || ''));
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await settle(page, 300);
  return { browser, page, errors };
}

const tap = (page, sel, touch) => (touch ? page.tap(sel) : page.click(sel));

// Go into the Sequences view, and select the sequence `seq` of map `mapId` in the listbox with
// the arrow keys and Enter. Give the cameras while the keys go.
async function choose(page, mapId, seq, touch) {
  await tap(page, '[data-view="sequences"]', touch);
  await settle(page, 250);
  await tap(page, '#cseq-pick', touch);
  await settle(page, 100);
  const cams = [await page.evaluate(() => window.systemapCanvas.camera())];
  for (let i = 0; i < 40; i++) {
    const at = await page.evaluate(() => {
      const e = document.activeElement;
      return e && e.getAttribute('role') === 'option' ? window.systemapCanvas.maps()[+e.dataset.m].id + '|' + e.dataset.k : null;
    });
    const want = await page.evaluate(([m, s]) => {
      const data = JSON.parse(document.getElementById('canvas-data').textContent), map = data.maps.find((x) => x.id === m);
      return m + '|' + map.sq.findIndex((j) => j.id === s);
    }, [mapId, seq]);
    if (at === want) break;
    await page.keyboard.press('ArrowDown');
    cams.push(await page.evaluate(() => window.systemapCanvas.camera()));
  }
  await page.keyboard.press('Enter');
  return cams;
}

// The values of the flows of map `mapId` and the marks of the route in a new frame.
async function frame(page, mapId) {
  return page.evaluate(async (mapId) => {
    const S = window.systemapCanvas, wait = (ms) => new Promise((r) => setTimeout(r, ms));
    const oi = S.maps().findIndex((m) => m.id === mapId);
    S.viewLog(); S.seqLog(); S.view(S.camera()); await wait(250);
    const frames = S.viewLogged(), marks = S.seqLogged(), last = frames[frames.length - 1];
    const flows = {};
    last.flows.forEach((f) => { if (f[0] === oi) flows[f[1]] = f[2]; });
    const route = marks.filter((x) => x.map === mapId).pop();
    return { flows, marks: route ? route.marks : [] };
  }, mapId);
}

function inBox(r, g, w, h) {
  return r && r[0] >= g.x - 1 && r[1] >= g.top - 1 && r[0] + r[2] <= w - g.x + 1 && r[1] + r[3] <= h - g.bottom + 1;
}

async function state(page, mapId) {
  return page.evaluate((mapId) => {
    const S = window.systemapCanvas, seq = S.seqState(), data = JSON.parse(document.getElementById('canvas-data').textContent);
    const map = data.maps.find((m) => m.id === seq.map), j = map ? map.sq.find((x) => x.id === seq.id) : null;
    const st = j && seq.steps ? j.s[seq.s] : null, f = st && st.f >= 0 ? map.flows[st.f] : null;
    const ids = f ? [f.s, f.t] : st ? (st.a || []) : [];
    return {
      seq, camera: S.camera(), fit: S.fit(mapId), frame: S.frame(mapId), layout: S.layout(), chain: S.chain(),
      view: S.viewState(), said: document.getElementById('canvas-said').textContent, width: innerWidth, height: innerHeight,
      cards: ids.map((id) => ({ id, box: S.box(seq.map, id) })),
      count: document.getElementById('cseq-count').textContent
    };
  }, mapId);
}

async function chooseRun(file, mapId, seq, phone) {
  const { browser, page, errors } = await open(file, phone ? PHONE : {});
  const cams = await choose(page, mapId, seq, phone);
  await settle(page, 500);
  const chosen = await state(page, mapId);
  chosen.drawn = await frame(page, mapId);
  const steps = [];
  await tap(page, '#cseq-start', phone);
  await settle(page, 500);
  steps.push(await state(page, mapId));
  for (let i = 0; i < 6; i++) {
    const off = await page.evaluate(() => document.getElementById('cseq-next').disabled);
    if (off) break;
    await tap(page, '#cseq-next', phone);
    await settle(page, 500);
    const s = await state(page, mapId);
    s.drawn = await frame(page, mapId);
    steps.push(s);
  }
  await tap(page, '#cseq-prev', phone);
  await settle(page, 500);
  steps.push(await state(page, mapId));
  inBoxes(steps);
  await browser.close();
  return { errors, cams, chosen, steps };
}

function inBoxes(steps) {
  steps.forEach((s) => { s.inside = s.cards.map((c) => inBox(c.box, s.layout.gutters, s.width, s.height)); });
}

// The value changes of all frames: the cards and the flows of the view, and the marks of
// the route. For each key: the largest change in one frame, and each run of changes with
// its time and its total. `values` gives each value that a frame shows, to 3 decimals.
function changes(frames, marks) {
  const series = new Map();
  function put(key, at, v) { if (!series.has(key)) series.set(key, []); series.get(key).push([at, v]); }
  frames.forEach((fr) => {
    fr.cards.forEach((c) => { put('c' + c[0] + ':' + c[1], fr.at, c[2]); put('d' + c[0] + ':' + c[1], fr.at, c[3]); });
    fr.flows.forEach((f) => put('f' + f[0] + ':' + f[1], fr.at, f[2]));
  });
  marks.forEach((fr) => fr.marks.forEach((m) => put('m' + fr.map + ':' + m.kind + ':' + m.f + ':' + (m.n || 0), fr.at, m.a)));
  let most = 0, fastest = Infinity, runs = 0, keys = 0;
  const values = new Set();
  series.forEach((list) => {
    keys++;
    let start = null, total = 0;
    list.forEach((x) => values.add(Math.round(x[1] * 1000) / 1000));
    const end = (at) => {
      if (start !== null && total >= 0.5) { runs++; fastest = Math.min(fastest, (at - start) / total); }

      start = null;
    };
    for (let i = 1; i < list.length; i++) {
      const d = Math.abs(list[i][1] - list[i - 1][1]);
      if (d > 1e-9) {
        most = Math.max(most, d);
        if (start === null) { start = list[i - 1][0]; total = 0; }
        total += d;
      } else end(list[i - 1][0]);
    }
    end(list[list.length - 1][0]);
  });
  return { most, msPerUnit: fastest === Infinity ? null : fastest, runs, keys, values: [...values].sort() };
}

async function fadeRun(file, mapId, seq) {
  const out = {};
  for (const motion of ['none', 'system', 'page']) {
    const { browser, page, errors } = await open(file, { reducedMotion: motion === 'system' ? 'reduce' : 'no-preference' });
    if (motion === 'page') await page.evaluate(() => document.documentElement.setAttribute('data-reduce-motion', 'true'));
    await page.evaluate(() => { window.systemapCanvas.viewLog(); window.systemapCanvas.seqLog(); });
    const moves = [];
    // The camera one frame after a change, and after the move. With reduced motion, the two
    // are the same.
    async function act(sel, ms) {
      await page.click(sel);
      const one = await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => r(window.systemapCanvas.camera())))));
      await settle(page, ms);
      const two = await page.evaluate(() => window.systemapCanvas.camera());
      moves.push({ sel, one, two });
    }
    await act('[data-view="sequences"]', 600);
    await choose(page, mapId, seq, false);
    const one = await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => r(window.systemapCanvas.camera())))));
    await settle(page, 1800);
    moves.push({ sel: 'choose', one, two: await page.evaluate(() => window.systemapCanvas.camera()) });
    await act('#cseq-start', 1500);
    await act('#cseq-next', 1500);
    await act('#cseq-prev', 1500);
    await act('#cseq-whole', 1500);
    await act('[data-view="map"]', 700);
    const logs = await page.evaluate(() => ({ frames: window.systemapCanvas.viewLogged(), marks: window.systemapCanvas.seqLogged() }));
    out[motion] = { errors, moves, ...changes(logs.frames, logs.marks), frames: logs.frames.length };
    await browser.close();
  }
  return out;
}

// The accessible name of an element, for the controls of the toolbar.
function nameOf(e) {
  const by = e.getAttribute('aria-labelledby');
  if (by) return by.split(/\s+/).map((id) => (document.getElementById(id) || {}).textContent || '').join(' ').trim();
  return (e.getAttribute('aria-label') || e.textContent || '').trim();
}

async function keysRun(file, mapId) {
  const { browser, page, errors } = await open(file, { hash: '#' + mapId });
  await page.evaluate('window.nameOf = ' + nameOf.toString());
  await page.click('[data-view="sequences"]');
  await settle(page, 300);
  const S = () => page.evaluate(() => ({ cam: window.systemapCanvas.camera(), chain: window.systemapCanvas.chain(), list: !document.getElementById('cseq-list').hidden, at: document.activeElement && (document.activeElement.id || document.activeElement.getAttribute('role')) }));
  // Tab from the view button through the toolbar.
  async function tabs() {
    await page.focus('[data-view="sequences"]');
    const order = [];
    for (let i = 0; i < 30; i++) {
      await page.keyboard.press('Tab');
      const at = await page.evaluate(() => {
        const e = document.activeElement, s = getComputedStyle(e);
        if (!e.closest('#cseq')) return { out: e.id || e.tagName };
        return { id: e.id, name: window.nameOf(e), visible: e.matches(':focus-visible'), style: s.outlineStyle, width: parseFloat(s.outlineWidth) };
      });
      order.push(at);
      if (at.out === 'find-open' || at.out === 'canvas') break;
    }
    return order;
  }
  const whole = await tabs();
  await page.click('#cseq-start');
  await settle(page, 400);
  const steps = await tabs();
  const out = { errors, whole, steps, list: {} };
  // The listbox: the arrow keys move the focus between the options and not the camera.
  await page.focus('#cseq-pick');
  const before = await S();
  await page.keyboard.press('ArrowDown');
  out.list.opened = await S();
  const seen = [];
  for (const key of ['ArrowDown', 'ArrowDown', 'ArrowUp', 'End', 'Home', 'ArrowLeft', 'ArrowRight', '+', '-', 'f']) {
    await page.keyboard.press(key);
    await settle(page, 60);
    seen.push({ key, ...(await S()), focus: await page.evaluate(() => document.activeElement.textContent) });
  }
  out.list.keys = seen;
  await page.keyboard.press('Escape');
  await settle(page, 300);
  out.list.escaped = await S();
  // Escape on the chooser with the list closed, and the arrow keys on a toolbar button.
  await page.keyboard.press('Escape');
  await settle(page, 300);
  out.list.escapedAgain = await S();
  await page.keyboard.press('ArrowRight');
  await settle(page, 200);
  out.list.right = await S();
  out.list.before = before;
  // The keyboard focus after Enter on a button that goes or becomes disabled: Start at step
  // 1, Next to the last step, and End sequence.
  const at = () => page.evaluate(() => document.activeElement.id || document.activeElement.tagName);
  const enter = async (sel) => { await page.focus(sel); await page.keyboard.press('Enter'); await settle(page, 400); };
  out.focus = {};
  await enter('#cseq-end');
  await enter('#cseq-start');
  out.focus.start = await at();
  for (let i = 0; i < 10 && !(await page.evaluate(() => document.getElementById('cseq-next').disabled)); i++) await enter('#cseq-next');
  out.focus.last = await at();
  await enter('#cseq-end');
  out.focus.end = await at();
  // On the canvas, an arrow key still moves the camera.
  await page.focus('#canvas');
  await page.keyboard.press('ArrowRight');
  await settle(page, 200);
  out.canvas = await S();
  await browser.close();
  return out;
}

async function axeRun(page, source) {
  if (!source) return null;
  await page.evaluate(source);
  return page.evaluate(async () => {
    const r = await window.axe.run(document, { resultTypes: ['violations'] });
    return { version: window.axe.version, violations: r.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.map((n) => n.target.join(' ')) })) };
  });
}

async function accessRun(file, mapId, seq) {
  let source = null;
  try { source = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8'); } catch (e) { source = null; }
  const runs = [];
  for (const screen of [{ tag: '1440x900', ...DESK }, { tag: '390x844', ...PHONE }]) {
    for (const scheme of ['light', 'dark']) {
      const touch = screen.tag !== '1440x900';
      const { browser, page, errors } = await open(file, { ...screen, colorScheme: scheme });
      await choose(page, mapId, seq, touch);
      await settle(page, 500);
      const shown = await axeRun(page, source);
      await tap(page, '#cseq-start', touch);
      await settle(page, 400);
      const steps = await axeRun(page, source);
      await tap(page, '#cseq-pick', touch);
      await settle(page, 200);
      const listed = await axeRun(page, source);
      const boxes = await page.evaluate(() => Array.from(document.querySelectorAll('#cseq button, #cseq [role="option"]'))
        .filter((e) => e.getClientRects().length && getComputedStyle(e).visibility === 'visible')
        .map((e) => { const r = e.getBoundingClientRect(); return { id: e.id || e.textContent.trim(), w: r.width, h: r.height, x: r.x, right: r.right }; }));
      const scroll = await page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, scrollX: window.scrollX, width: innerWidth,
        bar: document.getElementById('cseq').scrollWidth - document.getElementById('cseq').clientWidth,
        list: document.getElementById('cseq-list').getBoundingClientRect().right }));
      runs.push({ screen: screen.tag, scheme, errors, axe: { shown, steps, listed }, boxes, scroll });
      await browser.close();
    }
  }
  return { runs };
}

async function shotsRun(file, mapId, seq, folder) {
  const out = [];
  for (const screen of [{ tag: 'desk', ...DESK }, { tag: 'phone', ...PHONE }]) {
    for (const scheme of ['light', 'dark']) {
      const touch = screen.tag === 'phone';
      const { browser, page, errors } = await open(file, { ...screen, colorScheme: scheme });
      const shot = async (name) => { const p = path.join(folder, `${screen.tag}-${scheme}-${name}.png`); await page.screenshot({ path: p }); out.push(p); };
      await tap(page, '[data-view="sequences"]', touch);
      await settle(page, 400);
      await shot('1-top-route');
      await tap(page, '#cseq-pick', touch);
      await settle(page, 200);
      await shot('2-list');
      await page.keyboard.press('Escape');
      await choose(page, mapId, seq, touch);
      await settle(page, 600);
      await shot('3-nested-route');
      await tap(page, '#cseq-start', touch);
      await settle(page, 600);
      await shot('4-step-1');
      await tap(page, '#cseq-next', touch);
      await settle(page, 600);
      await shot('5-step-2');
      if (errors.length) out.push({ errors });
      await browser.close();
    }
  }
  return { shots: out };
}

// For each sequence of map `mapId` (the current map at the start): the values of the flows
// of the map in the Whole route and at each step, at the fit of the map.
async function routesRun(file, mapId) {
  const { browser, page, errors } = await open(file, { hash: mapId ? '#' + mapId : '' });
  await page.click('[data-view="sequences"]');
  await settle(page, 300);
  const count = await page.evaluate((m) => JSON.parse(document.getElementById('canvas-data').textContent).maps.find((x) => x.id === m).sq.length, mapId);
  const out = [];
  for (let k = 0; k < count; k++) {
    await page.click('#cseq-pick');
    await page.keyboard.press('Home');
    for (let i = 0; i < k; i++) await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Enter');
    await settle(page, 150);
    if (!(await page.evaluate(() => document.getElementById('cseq-whole').getAttribute('aria-pressed') === 'true'))) {
      await page.click('#cseq-whole');
    }
    await page.evaluate((m) => window.systemapCanvas.view(window.systemapCanvas.fit(m)), mapId);
    const whole = { seq: await page.evaluate(() => window.systemapCanvas.seqState()), drawn: await frame(page, mapId) };
    const steps = [];
    if (whole.seq.n) {
      await page.click('#cseq-start');
      for (let s = 0; s < whole.seq.n; s++) {
        if (s) await page.click('#cseq-next');
        await page.evaluate((m) => window.systemapCanvas.view(window.systemapCanvas.fit(m)), mapId);
        steps.push({ seq: await page.evaluate(() => window.systemapCanvas.seqState()), drawn: await frame(page, mapId) });
      }
    }
    out.push({ whole, steps });
  }
  await browser.close();
  return { errors, routes: out };
}

(async () => {
  const [mode, file, mapId, seq, extra] = process.argv.slice(2);
  let out;
  if (mode === '--routes') out = await routesRun(file, mapId);
  else if (mode === '--choose') out = await chooseRun(file, mapId, seq, extra === '--phone');
  else if (mode === '--fade') out = await fadeRun(file, mapId, seq);
  else if (mode === '--keys') out = await keysRun(file, mapId);
  else if (mode === '--access') out = await accessRun(file, mapId, seq);
  else if (mode === '--shots') out = await shotsRun(file, mapId, seq, extra);
  else throw new Error('unknown mode ' + mode);
  process.stdout.write(JSON.stringify(out) + '\n');
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
