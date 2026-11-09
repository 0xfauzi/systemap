// Drives the marks of the open ports of a canvas page (systemap.page_canvas_ports) in the
// Chromium of Playwright and prints one JSON object. tests/test_canvas_ports_browser.py
// reads it.
//
//     node tests/canvas_ports.js --marks PAGE.html NESTED [--light] [--shots DIR]
//     node tests/canvas_ports.js --fade PAGE.html NESTED CARD
//     node tests/canvas_ports.js --axe PAGE.html NESTED [--shots DIR]
//
// --marks: on a screen of 1440 x 900 pixels with reduced motion: the state of the open
// ports of NESTED (`systemapCanvas.ports`) and the texts of the tags in the Map view and in
// the Changes view, the live region after the camera goes from the top map to NESTED, and
// the text after each link of the list of the tree.
// --fade: without reduced motion and then with it, at the fit of NESTED: the alpha of the
// mark of CARD in each frame after the Changes view starts and after the Map view starts
// again, and the alpha and the size of the tag text in a zoom of 90 frames from the fit of
// the top map to the fit of NESTED.
// --axe: axe-core at the fit of NESTED and of the top map, on screens of 1440 x 900 and
// 390 x 844 pixels, light and dark, with the scroll width and the targets of the canvas.
// With --shots, a screenshot of each place goes into DIR. axe-core comes from NODE_PATH.
'use strict';
const fs = require('fs');
const path = require('path');
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

// The state of the open ports of a map, the tag texts, and the text after each link of the
// list of the tree, by the hash of the link.
const place = (page, id) => page.evaluate((id) => {
  const S = window.systemapCanvas, list = {};
  document.querySelectorAll('#canvas-tree li > a[data-c]').forEach((a) => {
    list[a.getAttribute('href')] = a.nextSibling ? a.nextSibling.textContent : '';
  });
  const top = document.querySelector('#canvas-tree > ul > li');
  const judged = JSON.parse(document.getElementById('canvas-data').textContent).judged;
  return { state: { judged, cards: S.ports(id) }, texts: S.texts().filter((t) => /^(No flow inside|Import with no flow|No flow in the parent map|\d+ open lines)$/.test(t.s)),
    list, top: top && top.childNodes[1] ? top.childNodes[1].textContent : '', view: S.viewState().mode };
}, id);

async function marks(file, nested, light, shots) {
  const browser = await chromium.launch(), scheme = light ? 'light' : 'dark';
  const { context, page, errors } = await opened(browser, { viewport: BIG, colorScheme: scheme, reducedMotion: 'reduce' }, file, '');
  await settle(page);
  // The camera goes from the top map to the map NESTED: the live region tells the new map.
  await page.evaluate((id) => { const S = window.systemapCanvas; S.view(S.fit(id)); }, nested);
  await settle(page, 600);
  const said = await page.evaluate(() => document.getElementById('canvas-said').textContent);
  const map = await place(page, nested);
  if (shots) await page.screenshot({ path: path.join(shots, 'ports-1440x900-' + scheme + '.png') });
  await page.evaluate(() => window.systemapCanvas.setView('changes'));
  await settle(page);
  const changes = await place(page, nested);
  await page.evaluate(() => window.systemapCanvas.setView('map'));
  await settle(page);
  const back = await place(page, nested);
  await context.close();
  await browser.close();
  return { said, map, changes, back, errors };
}

// The alpha `d` of the mark of card `ci` of map `oi` in each frame of the view record, from
// the call of setView. `ms` is the time to the first frame with the target alpha.
const fadeTo = (page, view, oi, ci) => page.evaluate(([view, oi, ci]) => new Promise((done) => {
  const S = window.systemapCanvas;
  S.viewLog();
  const t0 = performance.now();
  S.setView(view);
  setTimeout(() => {
    const log = S.viewLogged(), to = view === 'map' ? 1 : 0, d = [];
    let ms = null;
    log.forEach((e) => {
      const row = e.cards.find((c) => c[0] === oi && c[1] === ci);
      if (!row) return;
      d.push(row[3]);
      if (ms === null && row[3] === to) ms = e.at - t0;
    });
    done({ d, ms });
  }, 700);
}), [view, oi, ci]);

// The alpha and the size of the tag texts in a zoom of 90 frames, in log space, from the fit
// of the top map to the fit of the map `id`.
const zoom = (page, id) => page.evaluate((id) => new Promise((done) => {
  const S = window.systemapCanvas, a = S.fit(''), b = S.fit(id), out = [];
  let f = 0;
  const step = () => {
    const t = f / 89, k = Math.exp(Math.log(a.k) + (Math.log(b.k) - Math.log(a.k)) * t);
    const cx = (a.x + innerWidth / 2 / a.k) * (1 - t) + (b.x + innerWidth / 2 / b.k) * t;
    const cy = (a.y + innerHeight / 2 / a.k) * (1 - t) + (b.y + innerHeight / 2 / b.k) * t;
    S.view({ x: cx - innerWidth / 2 / k, y: cy - innerHeight / 2 / k, k });
    let shown = null;
    S.texts().forEach((x) => { if (/^(No flow inside|Import with no flow|No flow in the parent map|\d+ open lines)$/.test(x.s)) shown = { s: x.s, alpha: x.alpha, size: x.size }; });
    out.push(shown);
    if (++f < 90) requestAnimationFrame(step); else done(out);
  };
  requestAnimationFrame(step);
}), id);

async function fade(file, nested, card) {
  const browser = await chromium.launch(), out = {};
  for (const motion of ['no-preference', 'reduce']) {
    const { context, page, errors } = await opened(browser, { viewport: BIG, reducedMotion: motion }, file, '#' + nested);
    await settle(page, 600);
    const at = await page.evaluate(([id, card]) => {
      const S = window.systemapCanvas, oi = S.maps().findIndex((m) => m.id === id);
      return { oi, ci: S.boxes(id).findIndex((c) => c.id === card) };
    }, [nested, card]);
    const away = await fadeTo(page, 'changes', at.oi, at.ci);
    await settle(page, 300);
    const into = await fadeTo(page, 'map', at.oi, at.ci);
    await page.evaluate(() => { const S = window.systemapCanvas; S.view(S.fit('')); });
    await settle(page, 600);
    const zoomed = await zoom(page, nested);
    out[motion] = { away, into, zoomed, errors };
    await context.close();
  }
  await browser.close();
  return out;
}

async function axe(file, nested, shots) {
  const source = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8'), browser = await chromium.launch(), runs = [];
  for (const [tag, screen] of [['1440x900', { viewport: BIG }], ['390x844', PHONE]]) {
    for (const scheme of ['light', 'dark']) {
      for (const id of ['', nested]) {
        const { context, page, errors } = await opened(browser, { ...screen, colorScheme: scheme, reducedMotion: 'reduce' }, file, id ? '#' + id : '');
        await settle(page, 600);
        if (shots) await page.screenshot({ path: path.join(shots, (id ? 'ports-' : 'top-') + tag + '-' + scheme + '.png') });
        const state = { cards: await page.evaluate((id) => window.systemapCanvas.ports(id), id) };
        const hits = await page.evaluate(() => window.systemapCanvas.hits().filter((h) => h.show === undefined || h.show > 0.5).map((h) => [h.kind, h.w, h.h]));
        await page.evaluate(source);
        const found = await page.evaluate(async () => {
          const r = await window.axe.run(document, { resultTypes: ['violations'] });
          return { version: window.axe.version, violations: r.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.map((n) => n.target.join(' ')) })) };
        });
        const scroll = await page.evaluate(() => ({ width: document.documentElement.scrollWidth, x: scrollX }));
        runs.push({ screen: tag, scheme, id, state, hits, scroll, errors, ...found });
        await context.close();
      }
    }
  }
  await browser.close();
  return { runs };
}

(async () => {
  const args = process.argv.slice(2), at = args.indexOf('--shots'), shots = at >= 0 ? args[at + 1] : null;
  const [mode, file, nested, third] = args;
  const out = mode === '--marks' ? await marks(file, nested, args.includes('--light'), shots)
    : mode === '--fade' ? await fade(file, nested, third)
      : await axe(file, nested, shots);
  process.stdout.write(JSON.stringify(out) + '\n');
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
