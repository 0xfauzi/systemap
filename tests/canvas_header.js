// Drives a canvas page (systemap.canvas_page) in the Chromium of Playwright for the header,
// the views and the layers, and prints one JSON object. tests/test_canvas_header_browser.py
// reads it.
//
//     node tests/canvas_header.js --sets PAGE.html
//     node tests/canvas_header.js --fade PAGE.html MAP
//     node tests/canvas_header.js --hooks PAGE.html
//     node tests/canvas_header.js --keys PAGE.html
//     node tests/canvas_header.js --access PAGE.html
//     node tests/canvas_header.js --phone PAGE.html
//     node tests/canvas_header.js --shots PAGE.html FOLDER NAME
//     node tests/canvas_header.js --probe
//
// --sets gives, for each map and each layer, the flows that the last frame draws with an
// alpha above 0 and the cards that it draws with an alpha below 1, at the fit of the map,
// with reduced motion. --fade records the values of each frame in a layer change and a view
// change at rest and during a pan, without reduced motion, and with the reduced motion of
// the system and of the page. MAP is the map of the pan. --hooks gives the seam calls and
// the drawn cards and flows of each frame of a pan with a layer change. --keys presses the
// camera keys in each control of the header, in a select and in a text field, and gives
// the camera after each key. --access gives the names of the header controls, the order of
// Tab, the focus outline, and axe-core with the focus on each header control (axe-core
// from NODE_PATH; null when it is not there). --phone gives the scroll and the target boxes
// of the header on a phone. --shots writes screenshots.
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

// The flows with an alpha above 0 and the cards with an alpha below 1 of each map in the
// last frame of a record.
async function sets(file) {
  const { browser, page, errors } = await open(file);
  const out = await page.evaluate(async () => {
    const S = window.systemapCanvas, data = JSON.parse(document.getElementById('canvas-data').textContent);
    const ids = S.maps().map((m) => m.id), found = {};
    const layers = ['all'];
    data.maps.forEach((m) => (m.layers || []).forEach((l) => { if (layers.indexOf(l.id) < 0) layers.push(l.id); }));
    const wait = (ms) => new Promise((r) => setTimeout(r, ms));
    for (const id of ids) {
      found[id] = {};
      const oi = ids.indexOf(id), m = data.maps.find((x) => x.id === id);
      for (const layer of layers) {
        S.setView('map', layer);
        S.view(S.fit(id));
        await wait(250);
        S.viewLog(); S.view(S.camera()); await wait(250);
        const frames = S.viewLogged(), last = frames[frames.length - 1];
        const flows = [], quiet = [], drawnFlows = new Set(), drawnCards = new Set(), alphas = new Set();
        last.flows.forEach((f) => { if (f[0] === oi) { drawnFlows.add(f[1]); if (f[2] > 0) flows.push(f[1]); } });
        last.cards.forEach((c) => { if (c[0] === oi) { drawnCards.add(c[1]); if (c[2] < 1) { quiet.push(m.cards[c[1]].id); alphas.add(c[2]); } } });
        found[id][layer] = { flows: flows.sort((a, b) => a - b), quiet: quiet.sort(), drawnFlows: drawnFlows.size, drawnCards: drawnCards.size, alphas: [...alphas], state: S.viewState(),
          links: S.links().map((l) => [l.id, l.d]), chain: S.chain() };
      }
    }
    return found;
  });
  await browser.close();
  return { errors, maps: out };
}

// The largest change of a value between two frames, and the frames of each change.
function steps(frames) {
  let most = 0, frames01 = 0, last = null;
  const seen = new Map();
  frames.forEach((fr, i) => {
    let moved = false;
    const now = new Map();
    fr.cards.forEach((c) => now.set('c' + c[0] + ':' + c[1], [c[2], c[3]]));
    fr.flows.forEach((f) => now.set('f' + f[0] + ':' + f[1], [f[2], 0]));
    // A blend of the marks images is one value for each view change (its epoch).
    (fr.marks || []).forEach((m) => now.set('m' + m[0] + ':' + m[2], [m[1], 0]));
    now.forEach((v, k) => {
      const was = seen.get(k);
      if (!was) return;
      const d = Math.max(Math.abs(v[0] - was[0]), Math.abs(v[1] - was[1]));
      if (d > 1e-9) { moved = true; most = Math.max(most, d); }
    });
    if (moved) { frames01++; last = i; }
    seen.clear(); now.forEach((v, k) => seen.set(k, v));
  });
  return { most, frames: frames01, lastAt: last === null ? null : frames[last].at, count: frames.length };
}

// A layer change and a view change at rest and during a pan, and the values of each frame.
async function fade(file, mapId) {
  const out = {};
  for (const motion of ['none', 'system', 'page']) {
    const { browser, page, errors } = await open(file, { reducedMotion: motion === 'system' ? 'reduce' : 'no-preference' });
    if (motion === 'page') await page.evaluate(() => document.documentElement.setAttribute('data-reduce-motion', 'true'));
    out[motion] = await page.evaluate(async (mapId) => {
      const S = window.systemapCanvas, wait = (ms) => new Promise((r) => setTimeout(r, ms)), at = {};
      const fit = S.fit(mapId);
      S.view(fit); await wait(900);
      // One record for all changes. The frame before a change has the values before it.
      S.viewLog(); S.view(S.camera()); await wait(500);
      const change = async (name, f) => { at[name] = performance.now(); f(); await wait(700); };
      await change('layer', () => S.setView('map', 'data'));
      await change('view', () => S.setView('changes'));
      await change('viewBack', () => S.setView('map', 'data'));
      await change('back', () => S.setView('map', 'all'));
      // A layer change during a pan: the camera moves in each frame.
      at.pan = performance.now();
      await new Promise((done) => {
        let f = 0;
        const step = () => {
          S.view({ x: fit.x + Math.sin(f / 60 * Math.PI * 2) * 200 / fit.k, y: fit.y, k: fit.k });
          if (f === 20) S.setView('map', 'all');
          if (f === 40) S.setView('map', 'data');
          if (++f < 90) requestAnimationFrame(step); else done();
        };
        requestAnimationFrame(step);
      });
      await wait(600);
      return { at, frames: S.viewLogged(), state: S.viewState() };
    }, mapId);
    const { at, frames } = out[motion], names = ['layer', 'view', 'viewBack', 'back', 'pan'];
    names.forEach((k, i) => {
      const t0 = at[k], t1 = i + 1 < names.length ? at[names[i + 1]] : Infinity;
      let from = frames.findIndex((f) => f.at >= t0);
      if (from < 0) from = frames.length;
      const part = frames.slice(Math.max(0, from - 1)).filter((f, j) => j === 0 || f.at < t1);
      const s = steps(part);
      // The time from the change to the last frame that changes a value.
      s.ms = s.frames ? s.lastAt - t0 : 0;
      out[motion][k] = { ...s, marks: part.slice(1).filter((f) => (f.marks || []).length).length };
    });
    delete out[motion].frames;
    delete out[motion].at;
    out[motion].errors = errors;
    await browser.close();
  }
  return out;
}

// The seam calls of each frame of a pan with layer changes, and the drawn cards and flows.
async function hooks(file) {
  const { browser, page, errors } = await open(file, { reducedMotion: 'no-preference' });
  const frames = await page.evaluate(async () => {
    const S = window.systemapCanvas, fit = S.fit(''), out = [];
    S.setView('map', 'data');
    await new Promise((done) => {
      let f = 0;
      const step = () => {
        if (f) { const s = S.viewState(); out.push({ hooks: s.hooks, cards: s.cards, flows: s.flows }); }
        S.view({ x: fit.x + Math.sin(f / 60 * Math.PI * 2) * 200 / fit.k, y: fit.y, k: fit.k * (1 + f / 120) });
        if (f === 30) S.setView('map', 'all');
        if (f === 60) S.setView('map', 'data');
        if (++f < 120) requestAnimationFrame(step); else done();
      };
      requestAnimationFrame(step);
    });
    return out;
  });
  await browser.close();
  return { errors, frames };
}

// The camera after each key in each header control, in a select and in a text field.
async function keys(file) {
  const { browser, page, errors } = await open(file);
  await page.evaluate(() => {
    const input = document.createElement('input');
    input.id = 'probe-input'; input.setAttribute('aria-label', 'Probe');
    input.style.cssText = 'position:fixed;left:8px;bottom:60px;z-index:9';
    document.body.appendChild(input);
  });
  const targets = await page.evaluate(() => Array.from(document.querySelectorAll('#canvas-head button, #canvas-head select'))
    .filter((e) => e.getClientRects().length).map((e, i) => { e.dataset.probe = String(i); return '[data-probe="' + i + '"]'; }));
  targets.push('#canvas-layer', '#probe-input');
  const out = [];
  for (const sel of targets) {
    await page.evaluate((sel) => {
      const el = document.querySelector(sel);
      if (sel === '#canvas-layer') { const head = document.getElementById('canvas-head'); head.setAttribute('data-fit', '1'); }
      el.focus();
    }, sel);
    const before = await page.evaluate(() => ({ camera: window.systemapCanvas.camera(), view: window.systemapCanvas.viewState() }));
    for (const key of ['f', 'F', '+', '-', '=', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Escape']) {
      await page.evaluate((sel) => document.querySelector(sel).focus(), sel);
      await page.keyboard.press(key);
      await settle(page, 120);
    }
    const after = await page.evaluate(() => ({ camera: window.systemapCanvas.camera(), active: document.activeElement.id || document.activeElement.tagName }));
    out.push({ sel, before: before.camera, after: after.camera, active: after.active });
  }
  await page.evaluate(() => document.getElementById('canvas-head').removeAttribute('data-fit'));
  // The arrow keys in the layer toolbar move the pressed layer, and Home and End go to the ends.
  await page.evaluate(() => window.systemapCanvas.setView('map', 'all'));
  await page.focus('#canvas-head [data-layer][aria-pressed="true"]');
  const moves = [];
  for (const key of ['ArrowRight', 'ArrowRight', 'ArrowLeft', 'Home', 'End']) {
    await page.keyboard.press(key);
    moves.push(await page.evaluate(() => ({ layer: window.systemapCanvas.viewState().layer, focus: document.activeElement.getAttribute('data-layer') })));
  }
  // The canvas still gets the camera keys.
  await page.focus('#canvas');
  const c0 = await page.evaluate(() => window.systemapCanvas.camera());
  await page.keyboard.press('ArrowLeft');
  await settle(page, 200);
  const c1 = await page.evaluate(() => window.systemapCanvas.camera());
  await browser.close();
  return { errors, controls: out, moves, canvas: { before: c0, after: c1 } };
}

// The names of the header controls, the order of Tab, the focus outline and axe-core.
async function access(file) {
  let source = null;
  try { source = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8'); } catch (e) { source = null; }
  const out = { runs: [] };
  for (const screen of [{ tag: '1440x900', ...DESK }, { tag: '390x844', ...PHONE }]) {
    for (const scheme of ['light', 'dark']) {
      const { browser, page, errors } = await open(file, { ...screen, colorScheme: scheme });
      const controls = await page.evaluate(() => Array.from(document.querySelectorAll('#canvas-head button, #canvas-head select'))
        .filter((e) => e.getClientRects().length).map((e, i) => {
          e.dataset.probe = String(i);
          const label = e.id ? document.querySelector('label[for="' + e.id + '"]') : null;
          return { sel: '[data-probe="' + i + '"]', tag: e.tagName, name: (e.getAttribute('aria-label') || (label && label.textContent) || e.textContent || '').trim() };
        }));
      for (const c of controls) {
        await page.focus(c.sel);
        await page.keyboard.press('Shift');
        c.focus = await page.evaluate((sel) => {
          const el = document.querySelector(sel), s = getComputedStyle(el), head = getComputedStyle(document.getElementById('canvas-head'));
          return { visible: el.matches(':focus-visible'), style: s.outlineStyle, width: parseFloat(s.outlineWidth), color: s.outlineColor, back: head.backgroundColor };
        }, c.sel);
        if (source) {
          await page.evaluate(source);
          c.axe = await page.evaluate(async () => {
            const r = await window.axe.run(document, { resultTypes: ['violations'] });
            return { version: window.axe.version, violations: r.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.map((n) => n.target.join(' ')) })) };
          });
        }
      }
      // Tab from the start of a new load of the page: the order of the focused elements.
      await page.reload();
      await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
      await settle(page, 300);
      await page.keyboard.press('Tab');
      const order = [];
      for (let i = 0; i < 400; i++) {
        const at = await page.evaluate(() => {
          const e = document.activeElement;
          if (!e || e === document.body) return 'out';
          if (e.closest('#canvas-head')) return 'head:' + (e.getAttribute('data-view') || e.getAttribute('data-layer') || e.id);
          if (e.id === 'canvas') return 'canvas';
          if (e.closest('#canvas-tree')) return 'tree';
          return 'other:' + e.tagName;
        });
        if (at === 'out') { order.push(at); break; }
        if (order[order.length - 1] !== at || !at.startsWith('tree') && at !== 'canvas') order.push(at);
        await page.keyboard.press('Tab');
      }
      out.runs.push({ screen: screen.tag, scheme, errors, controls, order });
      await browser.close();
    }
  }
  return out;
}

// The scroll and the target boxes of the header on a phone.
async function phone(file) {
  const { browser, page, errors } = await open(file, PHONE);
  const found = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth, scrollX: window.scrollX, width: innerWidth,
    head: document.getElementById('canvas-head').getBoundingClientRect().height,
    fit: document.getElementById('canvas-head').getAttribute('data-fit'),
    state: window.systemapCanvas.viewState(),
    targets: Array.from(document.querySelectorAll('#canvas-head button, #canvas-head select')).filter((e) => e.getClientRects().length)
      .map((e) => { const r = e.getBoundingClientRect(); return { name: e.getAttribute('data-view') || e.getAttribute('data-layer') || e.id, x: r.x, y: r.y, w: r.width, h: r.height }; }),
    layout: window.systemapCanvas.layout(),
  }));
  await browser.close();
  return { errors, ...found };
}

// Screenshots of each state at 1440 x 900 and 390 x 844, light and dark.
async function shots(file, folder, name) {
  fs.mkdirSync(folder, { recursive: true });
  const written = [];
  for (const screen of [{ tag: '1440x900', ...DESK }, { tag: '390x844', ...PHONE }]) {
    for (const scheme of ['light', 'dark']) {
      const { browser, page, errors } = await open(file, { ...screen, colorScheme: scheme });
      const shot = async (state) => {
        await settle(page, 500);
        const out = path.join(folder, `${name}-${screen.tag}-${scheme}-${state}.png`);
        await page.screenshot({ path: out });
        written.push(out);
      };
      await shot('all');
      await page.evaluate(() => window.systemapCanvas.setView('map', 'data'));
      await shot('data');
      await page.evaluate(() => window.systemapCanvas.setView('map', 'control'));
      await shot('control');
      await page.focus('#canvas-head [data-layer][aria-pressed="true"]');
      await page.keyboard.press('Shift');
      await shot('focus');
      if (errors.length) written.push('errors: ' + errors.join('; '));
      await browser.close();
    }
  }
  return { written };
}

(async () => {
  const [mode, file, a, b] = process.argv.slice(2);
  if (mode === '--probe') { const br = await chromium.launch(); await br.close(); return; }
  const out = mode === '--sets' ? await sets(file)
    : mode === '--fade' ? await fade(file, a || '')
    : mode === '--hooks' ? await hooks(file)
    : mode === '--keys' ? await keys(file)
    : mode === '--access' ? await access(file)
    : mode === '--phone' ? await phone(file)
    : mode === '--shots' ? await shots(file, a, b)
    : null;
  if (!out) throw new Error('unknown mode ' + mode);
  process.stdout.write(JSON.stringify(out) + '\n');
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
