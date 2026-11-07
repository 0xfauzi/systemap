// Drives the Changes view of a canvas page (systemap.page_canvas_changes) in the Chromium of
// Playwright and prints one JSON object. tests/test_canvas_changes_browser.py reads it.
//
//     node tests/canvas_changes.js --marks PAGE.html NESTED [--light]
//     node tests/canvas_changes.js --fade PAGE.html
//     node tests/canvas_changes.js --axe PAGE.html NESTED
//     node tests/canvas_changes.js --probe
//
// --marks: on a screen of 1440 x 900 pixels with reduced motion, at the fit of the top map
// and of the map NESTED, in the Map view and in the Changes view: the change state of the
// cards (`systemapCanvas.changes`), the drawn texts, the pixel at the middle of the left
// side of the ring of each card with a ring, the live region and the text of the list of
// the tree. Then Esc in the Changes view and the live region.
// --fade: without reduced motion, the alpha of the view in each frame after the Changes
// view starts and after it stops, and the alpha of each tag text in a zoom. Then the same
// with reduced motion.
// --axe: axe-core in the Changes view, on screens of 1440 x 900 and 390 x 844 pixels, light
// and dark, at the top map and in NESTED, with the scroll width and the boxes of the
// buttons. axe-core comes from NODE_PATH, as in tests/canvas_access.js.
'use strict';
const fs = require('fs');
const { chromium } = require('playwright');

const settle = (page, ms) => page.waitForTimeout(ms || 400);
const BIG = { width: 1440, height: 900 };
const PHONE = { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3 };

async function opened(browser, options, file, hash) {
  const context = await browser.newContext(options);
  const page = await context.newPage(), errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + file + (hash || ''));
  await settle(page);
  return { context, page, errors };
}

// The state of one place: the cards, the texts of the marks, the ring pixels, the live region
// and the list of the tree.
const place = (page, id) => page.evaluate((id) => {
  const S = window.systemapCanvas, cv = document.getElementById('canvas'), g = cv.getContext('2d');
  const d = cv.width / cv.getBoundingClientRect().width, state = S.changes(id);
  const texts = S.texts().filter((t) => /^(CHANGED|TESTS|IMPORTS|changed inside)$/.test(t.s));
  const rings = {};
  state.cards.forEach((c) => {
    // The pixels of the middle part of the left side of the ring, 3 px outside the card
    // (`viewMarksAt` in page_canvas_view). A dashed ring has gaps. The three columns of
    // pixels around the left side, on the middle fifth of its height.
    const b = S.box(id, c.id), x = Math.floor((b[0] - 3) * d) - 1, y = Math.floor((b[1] + b[3] * 0.4) * d), n = Math.max(1, Math.floor(b[3] * 0.2 * d));
    const px = g.getImageData(x, y, 3, n).data;
    rings[c.id] = [];
    for (let i = 0; i < 3 * n; i++) rings[c.id].push([px[4 * i], px[4 * i + 1], px[4 * i + 2]]);
  });
  // The text after the link of each card of the list, by the hash of the link, and the text
  // after the link of the top map.
  const list = {}, top = document.querySelector('#canvas-tree > ul > li');
  document.querySelectorAll('#canvas-tree li > a[data-c]').forEach((a) => {
    list[a.getAttribute('href')] = a.nextSibling ? a.nextSibling.textContent : '';
  });
  return { state, texts, rings, list, top: top && top.childNodes[1] ? top.childNodes[1].textContent : '', said: document.getElementById('canvas-said').textContent,
    change: getComputedStyle(document.documentElement).getPropertyValue('--change').trim(), view: S.viewState() };
}, id);

async function marks(file, nested, light) {
  const browser = await chromium.launch(), out = { places: {} };
  for (const id of ['', nested]) {
    const { context, page, errors } = await opened(browser, { viewport: BIG, colorScheme: light ? 'light' : 'dark', reducedMotion: 'reduce' }, file, id ? '#' + id : '');
    await page.evaluate(() => new Promise((r) => setTimeout(r, 100)));
    const before = await place(page, id);
    const ok = await page.evaluate(() => window.systemapCanvas.setView('changes'));
    await settle(page);
    const during = await place(page, id);
    await page.evaluate(() => window.systemapCanvas.setView('map'));
    await settle(page);
    const after = await place(page, id);
    out.places[id] = { before, during, after, ok, errors };
    await context.close();
  }
  // Esc in the Changes view: the live region gives the map above and its changes.
  const { context, page, errors } = await opened(browser, { viewport: BIG, reducedMotion: 'reduce' }, file, '#' + nested);
  await page.evaluate(() => window.systemapCanvas.setView('changes'));
  await settle(page);
  await page.locator('#canvas').focus();
  await page.keyboard.press('Escape');
  await settle(page, 600);
  out.escaped = { said: await page.evaluate(() => document.getElementById('canvas-said').textContent), chain: await page.evaluate(() => window.systemapCanvas.chain()), errors };
  out.bad = await page.evaluate(() => window.systemapCanvas.setView('nothing'));
  await context.close();
  await browser.close();
  return out;
}

// The alpha of the view in each frame, from the call of setView. `ms` is the time from the
// call to the first frame with the target alpha.
const fadeTo = (page, view) => page.evaluate((view) => new Promise((done) => {
  const S = window.systemapCanvas;
  S.changeRecord();
  const t0 = performance.now();
  S.setView(view);
  setTimeout(() => {
    const log = S.changeRecorded(), to = view === 'changes' ? 1 : 0, at = log.find((e) => e.t === to);
    done({ t: log.map((e) => e.t), ms: at ? at.at - t0 : null });
  }, 700);
}), view);

// The alpha of each tag text in a zoom of 90 frames from 0.3 to 1.6 times the fit of the
// top map, at the middle of the fit.
const zoom = (page) => page.evaluate(() => new Promise((done) => {
  const S = window.systemapCanvas, fit = S.fit(''), W = innerWidth, H = innerHeight, out = [];
  const cx = fit.x + W / 2 / fit.k, cy = fit.y + H / 2 / fit.k;
  let f = 0;
  const step = () => {
    const k = fit.k * 0.3 * Math.pow(1.6 / 0.3, f / 89);
    S.view({ x: cx - W / 2 / k, y: cy - H / 2 / k, k });
    const shown = {};
    S.texts().forEach((t) => { if (/^(CHANGED|changed inside)$/.test(t.s)) shown[t.s] = { alpha: t.alpha, size: t.size }; });
    out.push(shown);
    if (++f < 90) requestAnimationFrame(step); else done(out);
  };
  requestAnimationFrame(step);
}));

async function fade(file) {
  const browser = await chromium.launch(), out = {};
  for (const motion of ['no-preference', 'reduce']) {
    const { context, page, errors } = await opened(browser, { viewport: BIG, reducedMotion: motion }, file);
    await settle(page, 600);
    const into = await fadeTo(page, 'changes');
    const zoomed = await zoom(page);
    await settle(page, 600);
    const back = await fadeTo(page, 'map');
    out[motion] = { into, back, zoomed, errors };
    await context.close();
  }
  await browser.close();
  return out;
}

async function axe(file, nested) {
  const source = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8'), browser = await chromium.launch(), runs = [];
  for (const [tag, screen] of [['1440x900', { viewport: BIG }], ['390x844', PHONE]]) {
    for (const scheme of ['light', 'dark']) {
      for (const id of ['', nested]) {
        const { context, page, errors } = await opened(browser, { ...screen, colorScheme: scheme, reducedMotion: 'reduce' }, file, id ? '#' + id : '');
        await page.evaluate(() => window.systemapCanvas.setView('changes'));
        await settle(page);
        const panel = await page.evaluate(() => {
          const s = document.getElementById('canvas-changes-empty');
          if (!s || s.hidden) return null;
          const b = s.querySelector('button').getBoundingClientRect(), p = s.getBoundingClientRect();
          return { button: [b.width, b.height], box: [p.left, p.top, p.width, p.height] };
        });
        let focus = null;
        if (panel) {
          await page.locator('#canvas-changes-empty button').focus();
          focus = await page.evaluate(() => {
            const b = document.activeElement, r = b.getBoundingClientRect(), s = getComputedStyle(b);
            return { tag: b.tagName, outline: s.outlineStyle + ' ' + s.outlineWidth, top: document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2) === b };
          });
          await page.keyboard.press('Enter');
          await settle(page);
          focus.said = await page.evaluate(() => document.getElementById('canvas-said').textContent);
        }
        await page.evaluate(source);
        const found = await page.evaluate(async () => {
          const r = await window.axe.run(document, { resultTypes: ['violations'] });
          return { version: window.axe.version, violations: r.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.map((n) => n.target.join(' ')) })) };
        });
        const scroll = await page.evaluate(() => ({ width: document.documentElement.scrollWidth, x: scrollX }));
        runs.push({ screen: tag, scheme, id, panel, focus, scroll, errors, ...found });
        await context.close();
      }
    }
  }
  await browser.close();
  return { runs };
}

(async () => {
  const [mode, file, nested, flag] = process.argv.slice(2);
  if (mode === '--probe') {
    const browser = await chromium.launch();
    await browser.close();
    process.stdout.write(require('axe-core/package.json').version + '\n');
    return;
  }
  const out = mode === '--marks' ? await marks(file, nested, flag === '--light')
    : mode === '--fade' ? await fade(file)
      : await axe(file, nested);
  process.stdout.write(JSON.stringify(out) + '\n');
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
