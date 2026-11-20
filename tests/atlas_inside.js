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
// - --axe PAGE MAP: axe-core in the map MAP, in the light and the dark scheme, at 1440 x 900
//   and at 390 x 844 (null when axe-core is not on NODE_PATH).
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
    return { moves: s.inside().moves, sel: s.side().sel, current: s.current(), bar: !!s.inside().bar, focus: document.activeElement && document.activeElement.id };
  });
}
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
    await dblInto(page, from, id.split('/').pop());
    steps.push({ step: 'enter ' + id, ...(await moveState(page)) });
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
    await leave[how]();
    await page.waitForTimeout(1100);
    steps.push({ step: 'leave ' + how, ...(await moveState(page)) });
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

(async () => {
  const [mode, file, arg] = process.argv.slice(2);
  const browser = await chromium.launch();
  try {
    const run = {
      '--signs': () => signs(browser, file, arg),
      '--move': () => move(browser, file, arg, false),
      '--reduced': () => move(browser, file, arg, true),
      '--axe': () => axeMode(browser, file, arg)
    }[mode];
    process.stdout.write(JSON.stringify(await run()));
  } finally {
    await browser.close();
  }
})();
