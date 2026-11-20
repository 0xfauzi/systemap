// The browser part of tests/test_atlas_inside_browser.py: the signs of a nested map on the
// atlas page (`atlas_inside`).
//
//     node atlas_inside.js MODE PAGE.html ARG
//
// MODE is one of:
// - --signs PAGE MAPS: MAPS is a list of map IDs with commas. For the top map and each map
//   of the list, in the light and the dark scheme, at 1440 x 900 and at 390 x 844: a load
//   with the hash of the map, and the state of the bar (its box, the size and the contrast
//   of each text), the locator, the screen boxes of the cards and of the labels at rest, the
//   ground color, the mean color of a part of the ground of the canvas, and the texts of the
//   frame titles.
// - --move PAGE PATH: 1440 x 900. PATH is the list of the map IDs from the top map down, with
//   commas. From the top map, a double-click on the card of each map of the path. Then, from
//   the deepest map: Esc, a click on the Back button, and Enter on the Back button, each
//   after a new double-click into the deepest map. The state after each step has the
//   movements of the page (`moves`) and the selected card.
// - --reduced PAGE PATH: the same with reduced motion (`dblInto`).
//   Each step also has the cameras of the frames of the step (`cams`).
// - --axe PAGE MAP: axe-core in the map MAP, in the light and the dark scheme, at 1440 x 900
//   and at 390 x 844 (null when axe-core is not on NODE_PATH).
// - --queue PAGE PATH: 1440 x 900, PATH as for --move. From the deepest map: one Esc in each
//   map of the path (the normal moves out), then two and three presses of Esc, and two and
//   three clicks on the Back button, 80 ms apart. Each run has the cameras of its frames and
//   the state at the end.
// - --path PAGE PATH: 1440 x 900, PATH as for --move. From the deepest map, a click on each
//   name of the path in the bar except the last one. The state after each click.
// - --zooms PAGE MAPS: 1440 x 900 and 390 x 844, light and dark. In each map of MAPS, the
//   camera at the fit times 0.35, 0.5, 0.7, 1, 1.4, 2 and 3: the neighbour marks (`up`) and the
//   screen boxes of the neighbour cards.
// - --views PAGE MAP: 1440 x 900 and 390 x 844. Each view (Map, Sequences on the map and as a
//   diagram, States, Focus and History) on the nested map MAP and on the top map, where the
//   page has it: the map that the view shows, the bar, the ground and the boxes of the parts
//   of the view. Then for the nested map, a click on the Back button and the state after it.
// - --totals PAGE MAP: 1440 x 900. On the top map: the reading line for the card MAP and the
//   text of the button of its details that goes in. Then in the map MAP: the counts of the
//   headline in each layer tab.
// - --hash PAGE MAP: 1440 x 900. Each view (as for --views) on the top map, then a change of
//   location.hash to the nested map MAP. The state after it: the view, the map that the view
//   shows, the current map, and the bar.
// Each mode prints one JSON object. `errors` has the script errors of the page.
'use strict';
const fs = require('fs');
const { chromium } = require('playwright');

const WIDE = { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 };
const PHONE = { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, hasTouch: true, isMobile: true };

async function open(browser, file, hash, opts) {
  const page = await browser.newPage(opts);
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + file + (hash ? '#' + hash : ''));
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await page.waitForTimeout(900);
  return { page, errors };
}

// The bar: each element with its own text, its font size, and the contrast of its color on the
// first ground under it that is not transparent.
function barTexts() {
  function rgb(s) { const m = s.match(/[\d.]+/g).map(Number); return { c: m.slice(0, 3), a: m.length > 3 ? m[3] : 1 }; }
  function lum(c) {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
  }
  function ground(e) {
    for (let x = e; x; x = x.parentElement) { const b = rgb(getComputedStyle(x).backgroundColor); if (b.a > 0.99) return b.c; }
    return [255, 255, 255];
  }
  const bar = document.getElementById('atlas-inside'), out = [];
  if (!bar || bar.hidden) return out;
  bar.querySelectorAll('*').forEach((e) => {
    const own = Array.from(e.childNodes).some((n) => n.nodeType === 3 && n.textContent.trim());
    if (!own) return;
    const cs = getComputedStyle(e), fg = rgb(cs.color).c, bg = ground(e), a = lum(fg), b = lum(bg);
    out.push({ text: e.textContent.trim(), size: parseFloat(cs.fontSize), ratio: (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05) });
  });
  return out;
}
// The mean color of a box of 16 x 16 CSS pixels of the canvas at x, y.
function groundAt([x, y]) {
  const cv = document.getElementById('canvas'), d = cv.width / cv.clientWidth, g = cv.getContext('2d');
  const px = g.getImageData(Math.round(x * d), Math.round(y * d), Math.round(16 * d), Math.round(16 * d)).data, sum = [0, 0, 0];
  for (let i = 0; i < px.length; i += 4) { sum[0] += px[i]; sum[1] += px[i + 1]; sum[2] += px[i + 2]; }
  return sum.map((v) => v / (px.length / 4));
}

async function signs(browser, file, maps) {
  const runs = [], errors = [];
  for (const scheme of ['light', 'dark']) {
    for (const opts of [WIDE, PHONE]) {
      for (const id of [''].concat(maps.split(','))) {
        const o = await open(browser, file, id, { ...opts, colorScheme: scheme });
        const st = await o.page.evaluate((id) => {
          const s = window.systemapCanvas, d = s.drawn();
          return { id, current: s.current(), inside: s.inside(), cards: s.boxes(id), labels: s.lines(id).labels.map((l) => l.box),
            titles: d.marks.filter((m) => m.t === 'title'), titleTexts: d.texts.filter((t) => d.marks.some((m) => m.t === 'title' && m.s === t.s)),
            ups: d.marks.filter((m) => m.t === 'up'), width: innerWidth, height: innerHeight, scroll: document.documentElement.scrollWidth };
        }, id);
        st.bar = await o.page.evaluate(barTexts);
        st.ground = await o.page.evaluate(groundAt, [opts.viewport.width / 2 - 8, opts.viewport.height - 40]);
        runs.push({ scheme, width: opts.viewport.width, ...st });
        errors.push(...o.errors);
        await o.page.close();
      }
    }
  }
  return { runs, errors };
}

// The state after a step of --move: the movements, the selected card and the current map.
async function moveState(page) {
  return page.evaluate(() => {
    const s = window.systemapCanvas;
    return { moves: s.inside().moves, sel: s.side().sel, current: s.current(), bar: !!s.inside().bar, loc: !!s.inside().loc, focus: document.activeElement && document.activeElement.id };
  });
}
// The camera of each frame from now (`systemapCanvas.camera`), until `camsEnd`.
async function camsStart(page) {
  await page.evaluate(() => {
    window.__cams = [];
    const me = {};
    window.__camRun = me;
    (function each() { if (window.__camRun !== me) return; window.__cams.push(window.systemapCanvas.camera()); requestAnimationFrame(each); })();
  });
}
async function camsEnd(page) { return page.evaluate(() => { window.__camRun = null; return window.__cams; }); }
// Go into the map of a card: a double-click on the card, with and without reduced motion. A
// click of a mouse on a card that opens a map opens the details after a wait (`OPEN_MS` in
// atlas_details), also with reduced motion. Thus the camera does not move before the second
// click.
async function dblInto(page, mapId, cardId) {
  const b = await page.evaluate(([m, c]) => window.systemapCanvas.box(m, c), [mapId, cardId]);
  await page.mouse.dblclick(b[0] + b[2] / 2, b[1] + b[3] / 2);
  await page.waitForTimeout(1100);
}
async function move(browser, file, path, reduced) {
  const o = await open(browser, file, '', { ...WIDE, reducedMotion: reduced ? 'reduce' : 'no-preference' });
  const page = o.page, ids = path.split(','), steps = [];
  let from = '';
  for (const id of ids) {
    await camsStart(page);
    await dblInto(page, from, id.split('/').pop());
    steps.push({ step: 'enter ' + id, ...(await moveState(page)), cams: await camsEnd(page) });
    from = id;
  }
  const deep = ids[ids.length - 1], up = ids.length > 1 ? ids[ids.length - 2] : '';
  const leave = {
    esc: async () => { await page.keyboard.press('Escape'); },
    click: async () => { await page.click('#atlas-inside .inside__back'); },
    enter: async () => { await page.focus('#atlas-inside .inside__back'); await page.keyboard.press('Enter'); },
    locator: async () => { await page.click('#atlas-loc'); }
  };
  for (const how of Object.keys(leave)) {
    if (how !== 'esc') {
      await page.keyboard.press('Escape'); await page.waitForTimeout(500);
      await dblInto(page, up, deep.split('/').pop());
    }
    await page.waitForTimeout(300);
    await camsStart(page);
    await leave[how]();
    await page.waitForTimeout(1100);
    steps.push({ step: 'leave ' + how, ...(await moveState(page)), cams: await camsEnd(page) });
  }
  await page.close();
  return { steps, errors: o.errors };
}

async function axeRun(page) {
  let source;
  try { source = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8'); } catch (e) { return null; }
  await page.addScriptTag({ content: source });
  return page.evaluate(async () => {
    const r = await window.axe.run(document, { resultTypes: ['violations'] });
    return r.violations.map((v) => v.impact + ' ' + v.id + ': ' + v.nodes.map((n) => n.target.join(' ')).join(', '));
  });
}
async function axeMode(browser, file, map) {
  const runs = [];
  for (const scheme of ['light', 'dark']) {
    for (const opts of [WIDE, PHONE]) {
      const o = await open(browser, file, map, { ...opts, colorScheme: scheme, bypassCSP: true });
      const violations = await axeRun(o.page);
      if (violations === null) { await o.page.close(); return { runs: null, errors: [] }; }
      runs.push({ scheme, width: opts.viewport.width, current: await o.page.evaluate(() => window.systemapCanvas.current()), violations, errors: o.errors });
      await o.page.close();
    }
  }
  return { runs, errors: [] };
}

async function queue(browser, file, path) {
  const ids = path.split(','), deep = ids[ids.length - 1], runs = [], errors = [];
  const plan = ids.slice().reverse().map((id) => ({ from: id, how: 'esc', n: 1 }));
  for (const how of ['esc', 'click']) for (const n of [2, 3]) plan.push({ from: deep, how, n });
  for (const p of plan) {
    const o = await open(browser, file, p.from, WIDE);
    await o.page.focus('#canvas');
    await camsStart(o.page);
    for (let i = 0; i < p.n; i++) {
      if (p.how === 'esc') await o.page.keyboard.press('Escape');
      else await o.page.click('#atlas-inside .inside__back', { timeout: 2000 });
      await o.page.waitForTimeout(80);
    }
    await o.page.waitForTimeout(2200);
    runs.push({ ...p, ...(await moveState(o.page)), cams: await camsEnd(o.page), size: [1440, 900] });
    errors.push(...o.errors);
    await o.page.close();
  }
  return { runs, errors };
}

async function pathMode(browser, file, path) {
  const ids = path.split(','), deep = ids[ids.length - 1], steps = [], errors = [];
  const names = await (async () => {
    const o = await open(browser, file, deep, WIDE);
    const t = await o.page.$$eval('#atlas-inside .inside__path button', (bs) => bs.map((b) => b.textContent));
    await o.page.close();
    return t;
  })();
  for (let i = 0; i < names.length - 1; i++) {
    const o = await open(browser, file, deep, WIDE);
    await o.page.click(`#atlas-inside .inside__path button >> nth=${i}`);
    await o.page.waitForTimeout(1600);
    steps.push({ name: names[i], ...(await moveState(o.page)) });
    errors.push(...o.errors);
    await o.page.close();
  }
  return { names, steps, errors };
}

async function zooms(browser, file, maps) {
  const runs = [], errors = [];
  for (const scheme of ['light', 'dark']) {
    for (const opts of [WIDE, PHONE]) {
      for (const id of maps.split(',')) {
        const o = await open(browser, file, id, { ...opts, colorScheme: scheme });
        for (const f of [0.35, 0.5, 0.7, 1, 1.4, 2, 3]) {
          const st = await o.page.evaluate(([id, f]) => {
            const s = window.systemapCanvas, c = s.camera(), W = innerWidth, H = innerHeight;
            const mx = c.x + W / 2 / c.k, my = c.y + H / 2 / c.k, k = c.k * f;
            s.view({ x: mx - W / 2 / k, y: my - H / 2 / k, k: k });
            const d = s.drawn();
            return { ups: d.marks.filter((m) => m.t === 'up'), cards: s.boxes(id).filter((b) => b.k === 'actor'), current: s.current() };
          }, [id, f]);
          runs.push({ scheme, width: opts.viewport.width, id, f, ...st });
          await o.page.evaluate(([id]) => { const s = window.systemapCanvas; s.view(s.fit(id)); }, [id]);
        }
        errors.push(...o.errors);
        await o.page.close();
      }
    }
  }
  return { runs, errors };
}

// Put the page in a view on map id. Give false when the page has no such view for the map.
async function toView(page, view, id) {
  return page.evaluate(([view, id]) => {
    const s = window.systemapCanvas;
    if (view === 'map') return s.mode('map') || document.body.getAttribute('data-mode') === 'map';
    if (view === 'history') return s.mode('history');
    if (view === 'seq-map' || view === 'seq-diagram') {
      if (!s.mode('seq') || !s.choose(id, 0)) return false;
      s.form(view === 'seq-map' ? 'map' : 'diagram');
      return true;
    }
    if (view === 'states') return s.mode('states') && s.machine(id, 0);
    if (view === 'focus') {
      if (!s.mode('focus')) return false;
      return s.boxes(id).some((c) => c.k !== 'actor' && s.focusOn(id, c.id));
    }
    return false;
  }, [view, id]);
}
function viewBoxes() {
  const out = {};
  for (const [k, q] of Object.entries({ ask: '#atlas-ask', rail: '.rail:not(.srail):not(.frail)', srail: '.srail', frail: '.frail', board: '.board', sboard: '.sboard', fboard: '.fboard', hboard: '.hboard' })) {
    const e = document.querySelector(q);
    if (!e || e.hidden) continue;
    const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden' || !r.width || !r.height) continue;
    out[k] = [r.left, r.top, r.right, r.bottom];
  }
  return out;
}
async function views(browser, file, map) {
  const runs = [], errors = [];
  for (const opts of [WIDE, PHONE]) {
    for (const view of ['map', 'seq-map', 'seq-diagram', 'states', 'focus', 'history']) {
      for (const id of [map, '']) {
        const o = await open(browser, file, id, { ...opts, colorScheme: 'light' });
        const has = await toView(o.page, view, id);
        await o.page.waitForTimeout(1300);
        const st = await o.page.evaluate(() => {
          const s = window.systemapCanvas, i = s.inside(), bar = document.getElementById('atlas-inside');
          return { mode: document.body.getAttribute('data-mode'), shows: i.view, current: s.current(), bar: i.bar, ground: i.ground, top: i.top, inside: i.inside,
            attr: document.documentElement.hasAttribute('data-inside'), body: getComputedStyle(document.body).backgroundColor,
            barBox: bar && !bar.hidden ? (function (r) { return [r.left, r.top, r.right, r.bottom]; })(bar.getBoundingClientRect()) : null };
        });
        st.boxes = await o.page.evaluate(viewBoxes);
        const run = { view, id, width: opts.viewport.width, has, ...st };
        if (has && st.bar) {
          await o.page.click('#atlas-inside .inside__back');
          await o.page.waitForTimeout(1600);
          run.back = await o.page.evaluate(() => {
            const s = window.systemapCanvas;
            return { mode: document.body.getAttribute('data-mode'), current: s.current(), sel: s.side().sel, bar: !!s.inside().bar };
          });
        }
        runs.push(run);
        errors.push(...o.errors);
        await o.page.close();
      }
    }
  }
  return { runs, errors };
}

async function hashMode(browser, file, map) {
  const runs = [], errors = [];
  for (const view of ['map', 'seq-map', 'seq-diagram', 'states', 'focus', 'history']) {
    const o = await open(browser, file, '', WIDE);
    const has = await toView(o.page, view, '');
    await o.page.waitForTimeout(600);
    await o.page.evaluate((map) => { location.hash = '#' + map; }, map);
    await o.page.waitForTimeout(1300);
    const st = await o.page.evaluate(() => {
      const s = window.systemapCanvas, i = s.inside(), bar = document.getElementById('atlas-inside');
      return { mode: document.body.getAttribute('data-mode'), shows: i.view, current: s.current(), bar: !!i.bar, hidden: !bar || bar.hidden,
        back: bar && !bar.hidden ? bar.textContent : '' };
    });
    runs.push({ view, has, ...st });
    errors.push(...o.errors);
    await o.page.close();
  }
  return { runs, errors };
}

async function totals(browser, file, map) {
  const o = await open(browser, file, '', WIDE);
  await o.page.evaluate((map) => window.systemapCanvas.pointAt('', map), map);
  await o.page.waitForTimeout(400);
  const out = { say: await o.page.evaluate(() => window.systemapCanvas.say().text) };
  await o.page.evaluate((map) => { const s = window.systemapCanvas; s.pointAt('', null); s.select('', map); }, map);
  await o.page.waitForTimeout(900);
  out.button = await o.page.evaluate(() => { const b = document.querySelector('#atlas-side .enter'); return b ? b.textContent : null; });
  await o.page.close();
  const n = await open(browser, file, map, WIDE);
  const tabs = await n.page.$$eval('#atlas-tabs [role="tab"]', (bs) => bs.map((b) => b.getAttribute('data-layer')));
  out.heads = [];
  for (const id of tabs) {
    await n.page.evaluate((id) => window.systemapCanvas.setLayer(id), id);
    await n.page.waitForTimeout(500);
    out.heads.push({ layer: id, counts: await n.page.evaluate(() => window.systemapCanvas.viewState().counts) });
  }
  await n.page.close();
  return { ...out, errors: o.errors.concat(n.errors) };
}

(async () => {
  const [mode, file, arg] = process.argv.slice(2);
  const browser = await chromium.launch();
  try {
    const run = {
      '--signs': () => signs(browser, file, arg),
      '--move': () => move(browser, file, arg, false),
      '--reduced': () => move(browser, file, arg, true),
      '--axe': () => axeMode(browser, file, arg),
      '--queue': () => queue(browser, file, arg),
      '--path': () => pathMode(browser, file, arg),
      '--zooms': () => zooms(browser, file, arg),
      '--views': () => views(browser, file, arg),
      '--totals': () => totals(browser, file, arg),
      '--hash': () => hashMode(browser, file, arg)
    }[mode];
    process.stdout.write(JSON.stringify(await run()));
  } finally {
    await browser.close();
  }
})();
