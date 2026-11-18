// The browser part of tests/test_atlas_browser.py: the Map view of the atlas page at rest.
//
//     node atlas_map.js MODE PAGE.html [MAP]
//
// MODE is one of:
// - --rest: 1440 x 900. For each layer tab: the state of the view, the lines of the top map
//   (`systemapCanvas.lines`), the texts of a frame, the screen boxes of the cards and of the
//   headline, and the grid.
// - --phone: 390 x 844 with a touch screen: the camera at the open, the scale readout, the
//   frame of the top map, and the same after a click on the Fit control. Also the scroll
//   width of the page.
// - --nested: 1440 x 900 on a page with the nested map MAP: a double-click on the card of
//   MAP, the chain and the headline after the flight, Esc, and a load with the hash #MAP.
// - --axe: axe-core (from NODE_PATH; null when it is not there) in the light and the dark
//   scheme, at 1440 x 900 and at 390 x 844.
// Each mode prints one JSON object. `errors` has the script errors of the page.
'use strict';
const fs = require('fs');
const { chromium } = require('playwright');

async function open(browser, file, opts, hash) {
  const page = await browser.newPage(opts);
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + file + (hash || ''));
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await page.waitForTimeout(500);
  return { page, errors };
}

const WIDE = { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 };
const PHONE = { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, hasTouch: true, isMobile: true };

function headBox() {
  const r = document.getElementById('atlas-ask').getBoundingClientRect();
  const q = document.getElementById('atlas-ask-q').getBoundingClientRect();
  return { left: r.left, top: r.top, right: r.right, bottom: r.bottom, qRight: q.right, qBottom: q.bottom };
}

async function rest(browser, file) {
  const { page, errors } = await open(browser, file, WIDE);
  const first = await page.evaluate(() => window.systemapCanvas.viewState());
  const out = { errors, first, layers: [] };
  for (const tab of first.tabs) {
    await page.evaluate((id) => window.systemapCanvas.setLayer(id), tab.id);
    await page.waitForTimeout(700);
    out.layers.push(await page.evaluate(`(() => {
      const a = window.systemapCanvas, headBox = ${headBox.toString()};
      return { view: a.viewState(), lines: a.lines(''), texts: a.texts(), cards: a.boxes(''), quiet: a.quiet(''),
        frame: a.frame(''), head: headBox(), grid: a.grid(), stats: a.stats() };
    })()`));
  }
  // The keyboard on the tabs: the arrow key moves the focus, Enter selects the layer.
  await page.evaluate(() => window.systemapCanvas.setLayer(document.querySelector('[role="tab"]').getAttribute('data-layer')));
  await page.waitForTimeout(400);
  await page.focus('[role="tab"][aria-selected="true"]');
  await page.keyboard.press('ArrowRight');
  const moved = await page.evaluate(() => ({ focus: document.activeElement.getAttribute('data-layer'), layer: window.systemapCanvas.viewState().layer }));
  await page.keyboard.press('Enter');
  await page.waitForTimeout(500);
  out.keys = { moved, after: await page.evaluate(() => window.systemapCanvas.viewState()) };
  out.size = await page.evaluate(() => [innerWidth, innerHeight]);
  // At a scale of 1.2 the short names show, and the zoom readout gives 120%.
  await page.evaluate(() => { const a = window.systemapCanvas, c = a.camera(), k = 1.2, cx = c.x + innerWidth / 2 / c.k, cy = c.y + innerHeight / 2 / c.k; a.view({ x: cx - innerWidth / 2 / k, y: cy - innerHeight / 2 / k, k }); });
  await page.waitForTimeout(500);
  out.near = await page.evaluate(() => ({ texts: window.systemapCanvas.texts(), view: window.systemapCanvas.viewState() }));
  await page.close();
  return out;
}

async function phone(browser, file) {
  const { page, errors } = await open(browser, file, PHONE);
  const read = () => page.evaluate(() => {
    const a = window.systemapCanvas;
    return { camera: a.camera(), frame: a.frame(''), view: a.viewState(), fit: a.fit(''), whole: a.fit('', true), scroll: document.documentElement.scrollWidth };
  });
  const at = await read();
  await page.click('#atlas-zf');
  await page.waitForTimeout(1500);
  const fitted = await read();
  await page.close();
  return { errors, at, fitted };
}

async function nested(browser, file, map) {
  const { page, errors } = await open(browser, file, WIDE);
  const box = await page.evaluate((id) => window.systemapCanvas.box('', id), map);
  await page.mouse.dblclick(box[0] + 20, box[1] + box[3] / 2);
  await page.waitForTimeout(2000);
  const inside = await page.evaluate(() => ({ chain: window.systemapCanvas.chain(), deep: window.systemapCanvas.deep(), view: window.systemapCanvas.viewState(),
    path: Array.prototype.map.call(document.querySelectorAll('#atlas-ask-k button'), (b) => b.textContent), hash: location.hash }));
  await page.keyboard.press('Escape');
  await page.waitForTimeout(2000);
  const out = await page.evaluate(() => ({ chain: window.systemapCanvas.chain(), view: window.systemapCanvas.viewState() }));
  await page.close();
  const second = await open(browser, file, WIDE, '#' + map);
  const hashed = await second.page.evaluate(() => ({ chain: window.systemapCanvas.chain(), view: window.systemapCanvas.viewState() }));
  // A click on the first part of the path goes to the top map.
  await second.page.click('#atlas-ask-k button');
  await second.page.waitForTimeout(2000);
  const back = await second.page.evaluate(() => window.systemapCanvas.chain());
  await second.page.close();
  return { errors: errors.concat(second.errors), inside, out, hashed, back };
}

async function axeRun(page) {
  let source;
  try { source = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8'); } catch (e) { return null; }
  await page.addScriptTag({ content: source });
  return page.evaluate(async () => {
    const r = await window.axe.run(document, { resultTypes: ['violations'] });
    return { version: window.axe.version, violations: r.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical').map((v) => v.id + ': ' + v.nodes.map((n) => n.target.join(' ')).join(', ')) };
  });
}

async function axe(browser, file) {
  const runs = [];
  for (const opts of [WIDE, PHONE]) {
    for (const scheme of ['light', 'dark']) {
      const { page, errors } = await open(browser, file, { ...opts, colorScheme: scheme, reducedMotion: 'reduce', bypassCSP: true });
      runs.push({ scheme, width: opts.viewport.width, errors, axe: await axeRun(page) });
      await page.close();
    }
  }
  return { runs };
}

(async () => {
  const [mode, file, map] = process.argv.slice(2);
  const browser = await chromium.launch();
  const run = { '--rest': rest, '--phone': phone, '--nested': nested, '--axe': axe }[mode];
  const out = await run(browser, file, map);
  await browser.close();
  process.stdout.write(JSON.stringify(out) + '\n');
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
