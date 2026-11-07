// Drives the Find dialog of a canvas page (systemap.page_canvas_find) in the Chromium of
// Playwright, and prints one JSON object. tests/test_canvas_find_browser.py reads it.
//
//     node tests/canvas_find.js --go PAGE.html TEXT GROUP MAP CARD [CARD2] [--reduce]
//     node tests/canvas_find.js --keys PAGE.html
//     node tests/canvas_find.js --axe PAGE.html TEXT
//     node tests/canvas_find.js --shots PAGE.html TEXT FOLDER
//     node tests/canvas_find.js --rank < INPUT.json
//
// --go opens the dialog with Ctrl+K at the top map, types TEXT, moves the selection to the
// first row of the group GROUP, and presses Enter. It waits until the camera stops. It gives
// the rows, the camera directly after Enter and when it stops, the screen boxes of the cards
// CARD and CARD2 of the map MAP, the bands of the fit, the hash, the selected card, the chain,
// the label of the canvas and each text of the live region after Enter. --reduce uses
// reduced motion.
// --keys gives the camera before and after the keys of the camera in the field, and the
// state after Escape, /, Ctrl+K and Meta+K.
// --axe puts axe-core into the page (as tests/canvas_access.js does) and runs it with the
// dialog open, with a result selected, and after Enter, on screens of 1440 x 900 and
// 390 x 844 pixels, in the light and the dark scheme. It also gives the height of each row
// and the scroll width of the page.
// --shots writes screenshots of the dialog with no text, with the rows of TEXT, and after
// Enter, for each screen and scheme, into FOLDER.
// --rank runs the match code and the ranking functions of INPUT in Node, with no browser:
// INPUT is {match, ranks: {name: code}, cases: [{order, limit, items, texts}]}. It gives the
// result of each ranking for each text.
'use strict';
const fs = require('fs');
const vm = require('vm');

const PHONE = { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3 };
const SCREENS = [{ tag: '1440x900', viewport: { width: 1440, height: 900 } }, { tag: '390x844', ...PHONE }];
const settle = (page, ms) => page.waitForTimeout(ms || 400);
const api = (page, f, arg) => page.evaluate(f, arg);

function rankMode() {
  const input = JSON.parse(fs.readFileSync(0, 'utf8')), out = {};
  for (const [name, code] of Object.entries(input.ranks)) {
    out[name] = input.cases.map((c) => {
      const ctx = { items: c.items.map((it, k) => ({ s: '', keys: [], words: '', more: [], quiet: false, late: false, ...it, k })), ORDER: c.order, LIMIT: c.limit };
      vm.runInNewContext(input.match + code + '\nthis.rank = rank;', ctx);
      return c.texts.map((t) => ctx.rank(t).map((g) => ({ g: g.g, rows: g.rows.map((r) => r.it.t + (r.it.hint ? ' ' + r.it.hint : '')) })));
    });
  }
  return out;
}

// The Find part with stubs of the other parts of the renderer, in Node with no browser.
// INPUT is {script, data, current, view}: `view` false leaves out the view part and the
// Sequences view. It gives the groups and the rows for each text, and the calls of the
// result actions.
function stubMode() {
  const input = JSON.parse(fs.readFileSync(0, 'utf8')), calls = [];
  const element = () => ({ hidden: true, value: '', dataset: {}, addEventListener() {}, setAttribute() {}, removeAttribute() {}, querySelectorAll: () => [], focus() {}, blur() {} });
  const els = { palette: element(), 'pal-input': element(), 'pal-list': element(), 'pal-status': element(), 'find-open': element() };
  const maps = input.data.maps;
  maps.forEach((m) => { m.T = { x: 0, y: 0, s: 1 }; m.flows.forEach((f, i) => { f.i = i; }); m.cards.forEach((c, i) => { c.i = i; c.map = m; }); });
  const ctx = {
    document: { getElementById: (id) => els[id] || null, querySelectorAll: () => [] },
    window: { addEventListener() {}, systemapCanvas: {} }, navigator: { platform: 'Linux' }, performance: { now: () => 0 },
    requestAnimationFrame: () => 0, DATA: input.data, drawn: 0, flight: null, SAID_MAP: null, SEL_C: null,
    currentMap: () => maps[input.current || 0], esc: (s) => String(s), counted: (n, w) => n + ' ' + w + (n === 1 ? '' : 's'),
    say: (s) => calls.push(['say', s]), setHash: (h) => calls.push(['hash', h]), hashOf: (id) => '#' + id, cardId: (c) => (c.map.id ? c.map.id + '/' + c.id : c.id),
    mapName: (m) => m.id || input.data.name, goalOf: () => ({}), flyGoal: () => calls.push(['fly']), flyTo: () => calls.push(['fly']),
    topFrame: () => [], FIT: 0.04, fitCurrent: () => calls.push(['fit']), select: () => {}, mapOpen: () => true,
  };
  if (input.view) {
    Object.assign(ctx, {
      VIEW: { mode: 'map', layer: 'all' }, VIEWS: { map: {}, sequences: {} },
      LAYER_OF: { data: { n: 'Data', q: 'Which data moves?' }, control: { n: 'Control', q: 'Which calls control?' } },
      setView: (mode, layer) => calls.push(['view', mode, layer === undefined ? null : layer]),
      seqChoose: (m, k, camera) => calls.push(['seq', m.id, k, camera]),
      seqMode: (steps, s, camera) => calls.push(['step', steps, s, camera]),
    });
  }
  vm.runInNewContext(input.script + '\nthis.FIND = FIND;', ctx);
  const out = { texts: {}, runs: {} };
  for (const t of input.texts) out.texts[t] = ctx.FIND.rank(t);
  (input.runs || []).forEach(([text, group, n], k) => {
    calls.length = 0;
    out.runs[k] = { done: ctx.FIND.run(text, group, n), calls: calls.slice() };
  });
  return out;
}

async function start(browser, file, opts) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'no-preference', ...opts });
  const page = await context.newPage(), errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + file);
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await settle(page, 600);
  return { context, page, errors };
}

// Record each text of the live region from now, in window.__said.
const hear = (page) => api(page, () => {
  const said = document.getElementById('canvas-said'), out = [];
  window.__said = out;
  new MutationObserver(() => out.push(said.textContent)).observe(said, { childList: true, characterData: true, subtree: true });
});
const rows = (page) => api(page, () => Array.from(document.querySelectorAll('#pal-list [role="group"]')).map((g) => ({
  g: g.querySelector('.pal__g').textContent,
  rows: Array.from(g.querySelectorAll('.pal__o')).map((o) => ({ k: +o.dataset.k, t: o.querySelector('.pal__t').textContent, s: o.querySelector('.pal__s').textContent, hint: (o.querySelector('.pal__k span') || {}).textContent || '' })),
})));
const state = (page) => api(page, () => {
  const c = window.systemapCanvas, a = document.activeElement;
  return {
    camera: c.camera(), chain: c.chain(), selected: c.selected(), hash: location.hash, label: document.getElementById('canvas').getAttribute('aria-label'),
    live: document.getElementById('canvas-said').textContent, open: c.find.open(), shown: getComputedStyle(document.getElementById('palette')).display !== 'none', active: a.id || a.tagName, layout: c.layout(), W: innerWidth, H: innerHeight,
    expanded: (document.getElementById('find-open') || { getAttribute: () => null }).getAttribute('aria-expanded'),
  };
});
// Wait until the camera does not change for 5 samples of 100 ms, 8 s or less.
async function still(page) {
  let last = null, same = 0;
  for (let i = 0; i < 80 && same < 5; i++) {
    const cam = JSON.stringify(await api(page, () => window.systemapCanvas.camera()));
    same = cam === last ? same + 1 : 0; last = cam;
    await settle(page, 100);
  }
  await settle(page, 300);
}
async function search(page, text) {
  await page.focus('#canvas');
  await page.keyboard.press('Control+k');
  await page.keyboard.type(text);
  await settle(page, 300);
}
// Move the selection to row k of the list.
async function choose(page, k) {
  for (let i = 0; i < k; i++) await page.keyboard.press('ArrowDown');
}

async function go(file, text, group, map, cards, reduce) {
  const { chromium } = require('playwright');
  const browser = await chromium.launch();
  const { page, errors } = await start(browser, file, reduce ? { reducedMotion: 'reduce' } : {});
  const before = await state(page);
  await search(page, text);
  const found = await rows(page), target = (found.find((g) => g.g === group) || { rows: [] }).rows[0];
  await choose(page, target ? target.k : 0);
  await hear(page);
  await page.keyboard.press('Enter');
  const now = await api(page, () => window.systemapCanvas.camera());
  await still(page);
  const out = { errors, before, rows: found, target, now, after: await state(page), said: await api(page, () => window.__said) };
  // A card of a map that has no place on the canvas has no box.
  out.boxes = await api(page, (a) => a.cards.map((id) => { try { return window.systemapCanvas.box(a.map, id); } catch (e) { return null; } }), { map, cards });
  await browser.close();
  return out;
}

async function keys(file) {
  const { chromium } = require('playwright');
  const browser = await chromium.launch();
  const { page, errors } = await start(browser, file, { reducedMotion: 'reduce' });
  const out = { errors };
  await page.focus('#canvas');
  out.before = await state(page);
  await page.keyboard.press('Control+k');
  out.opened = await state(page);
  for (const key of ['f', 'F', '+', '-', '=', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Tab', 'Enter']) {
    if (key === 'Enter') await page.keyboard.type('zzzzqqq');
    await page.keyboard.press(key);
  }
  await settle(page, 400);
  out.typed = await state(page);
  await page.keyboard.press('Escape');
  await settle(page, 400);
  out.escaped = await state(page);
  await page.keyboard.press('/');
  out.slash = await state(page);
  await page.keyboard.press('Control+k');
  out.toggled = await state(page);
  await page.keyboard.press('Meta+k');
  out.meta = await state(page);
  await page.keyboard.press('Escape');
  await settle(page, 400);
  out.closed = await state(page);
  await browser.close();
  return out;
}

async function axe(file, text) {
  const { chromium } = require('playwright');
  const source = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8'), browser = await chromium.launch(), runs = [];
  const audit = async (page) => {
    await page.evaluate(source);
    return page.evaluate(async () => {
      const r = await window.axe.run(document, { resultTypes: ['violations'] });
      return { version: window.axe.version, violations: r.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.map((n) => n.target.join(' ')) })) };
    });
  };
  const sizes = (page) => api(page, () => ({
    rows: Array.from(document.querySelectorAll('.pal__o')).map((o) => o.getBoundingClientRect().height),
    close: document.getElementById('pal-close').getBoundingClientRect().height,
    scroll: document.documentElement.scrollWidth, x: scrollX, width: innerWidth,
  }));
  for (const s of SCREENS) {
    for (const scheme of ['light', 'dark']) {
      const { context, page, errors } = await start(browser, file, {
        viewport: s.viewport, isMobile: !!s.isMobile, hasTouch: !!s.hasTouch,
        deviceScaleFactor: s.deviceScaleFactor || 1, colorScheme: scheme, reducedMotion: 'reduce',
      });
      const at = { screen: s.tag, scheme };
      await search(page, text);
      runs.push({ ...at, state: 'results', size: await sizes(page), ...(await audit(page)) });
      await page.keyboard.press('ArrowDown');
      runs.push({ ...at, state: 'selected', active: await api(page, () => document.getElementById('pal-input').getAttribute('aria-activedescendant')), ...(await audit(page)) });
      await page.keyboard.press('Enter');
      await still(page);
      runs.push({ ...at, state: 'entered', ...(await audit(page)) });
      runs.forEach((r) => { if (r.screen === s.tag && r.scheme === scheme) r.errors = errors; });
      await context.close();
    }
  }
  await browser.close();
  return { runs };
}

async function shots(file, text, folder) {
  const { chromium } = require('playwright');
  const browser = await chromium.launch(), out = [];
  for (const s of SCREENS) {
    for (const scheme of ['light', 'dark']) {
      const { context, page } = await start(browser, file, {
        viewport: s.viewport, isMobile: !!s.isMobile, hasTouch: !!s.hasTouch,
        deviceScaleFactor: s.deviceScaleFactor || 1, colorScheme: scheme,
      });
      const shot = async (name) => {
        const path = folder + '/find-' + name + '-' + s.tag + '-' + scheme + '.png';
        await page.screenshot({ path });
        out.push(path);
      };
      await page.focus('#canvas');
      await page.keyboard.press('Control+k');
      await settle(page, 400);
      await shot('open');
      await page.keyboard.type(text);
      await page.keyboard.press('ArrowDown');
      await settle(page, 400);
      await shot('results');
      await page.keyboard.press('Enter');
      await still(page);
      await shot('entered');
      await context.close();
    }
  }
  await browser.close();
  return { shots: out };
}

(async () => {
  const [mode, file, ...rest] = process.argv.slice(2);
  let out;
  if (mode === '--rank') out = rankMode();
  else if (mode === '--stub') out = stubMode();
  else if (mode === '--go') {
    const reduce = rest.includes('--reduce'), args = rest.filter((a) => a !== '--reduce');
    out = await go(file, args[0], args[1], args[2], args.slice(3), reduce);
  } else if (mode === '--keys') out = await keys(file);
  else if (mode === '--axe') out = await axe(file, rest[0]);
  else if (mode === '--shots') out = await shots(file, rest[0], rest[1]);
  else throw new Error('unknown mode ' + mode);
  console.log(JSON.stringify(out));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
