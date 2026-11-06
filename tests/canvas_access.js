// Drives a canvas page (systemap.canvas_page) in the Chromium of Playwright for the access
// checks, and prints one JSON object. tests/test_canvas_access.py reads it.
//
//     node tests/canvas_access.js --axe PAGE.html NESTED [--small]
//     node tests/canvas_access.js --held PAGE.html CARD
//     node tests/canvas_access.js --probe
//
// --axe puts axe-core into the page with page.evaluate and runs it. The page loads no
// axe-core file, and its CSP does not change. axe-core comes from the node_modules folder
// of the checkout or from NODE_PATH. NESTED is the ID of a nested map. --small runs only
// the screen of 1440 x 900 pixels. --held gives the state after a URL hash that names a
// property of all objects, after a zoom out that closes the map of the focused card, after
// Esc, and after a pinch. CARD is a card of the top map that opens a map. --probe exits 0
// and prints the axe-core version when Playwright can start Chromium and axe-core is there.
'use strict';
const fs = require('fs');
const { chromium } = require('playwright');

const settle = (page, ms) => page.waitForTimeout(ms || 400);
const axeFile = () => require.resolve('axe-core/axe.min.js');
const SCREENS = [
  { tag: '1440x900', viewport: { width: 1440, height: 900 } },
  { tag: '390x844', viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3 },
];

async function audit(page, source) {
  await page.evaluate(source);
  return page.evaluate(async () => {
    const r = await window.axe.run(document, { resultTypes: ['violations'] });
    return { version: window.axe.version, violations: r.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.map((n) => n.target.join(' ')) })) };
  });
}

// axe-core in each screen, scheme and place, with no focus, with the focus on a link of
// the list of the tree, and with the focus on a card after Tab.
async function axe(file, nested, small) {
  const source = fs.readFileSync(axeFile(), 'utf8'), browser = await chromium.launch(), runs = [];
  for (const s of small ? SCREENS.slice(0, 1) : SCREENS) {
    for (const scheme of ['light', 'dark']) {
      const context = await browser.newContext({
        viewport: s.viewport, isMobile: !!s.isMobile, hasTouch: !!s.hasTouch,
        deviceScaleFactor: s.deviceScaleFactor || 1, colorScheme: scheme, reducedMotion: 'reduce',
      });
      const page = await context.newPage(), errors = [];
      page.on('pageerror', (e) => errors.push(String(e)));
      page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
      for (const hash of ['', '#' + nested]) {
        await page.goto('file://' + file + hash);
        await settle(page, 600);
        const at = { screen: s.tag, scheme, hash };
        runs.push({ ...at, state: 'no focus', ...(await audit(page, source)) });
        await page.focus('#canvas-tree a[data-c]');
        runs.push({ ...at, state: 'link', ...(await audit(page, source)) });
        await page.focus('#canvas');
        await page.keyboard.press('Tab');
        await settle(page, 300);
        runs.push({ ...at, state: 'card', focus: await page.evaluate(() => window.systemapCanvas.keys().focus), ...(await audit(page, source)) });
      }
      runs.forEach((r) => { if (r.screen === s.tag && r.scheme === scheme) r.errors = errors; });
      await context.close();
    }
  }
  await browser.close();
  return { runs };
}

const keyed = (page) => page.evaluate(() => ({
  ...window.systemapCanvas.keys(), chain: window.systemapCanvas.chain(), selected: window.systemapCanvas.selected().id,
  active: document.activeElement.id || document.activeElement.tagName,
}));

async function held(file, card) {
  const browser = await chromium.launch(), out = { hashes: {}, errors: [] };
  // A hash that names a property of all objects names no map and no card.
  for (const hash of ['#constructor', '#toString', '#' + card + '/__proto__', '#' + card + '/hasOwnProperty']) {
    const page = await browser.newPage(), errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('file://' + file + hash);
    await settle(page);
    out.hashes[hash] = {
      errors, api: await page.evaluate(() => !!window.systemapCanvas),
      links: await page.evaluate(() => document.querySelectorAll('#canvas-tree a').length),
      chain: await page.evaluate(() => window.systemapCanvas && window.systemapCanvas.chain()),
    };
    if (hash === '#constructor') {
      await page.evaluate(() => { location.hash = 'valueOf'; });
      await settle(page);
      out.hashes['#valueOf after the load'] = { errors };
    }
    await page.close();
  }
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
  const page = await context.newPage();
  page.on('pageerror', (e) => out.errors.push(String(e)));
  await page.goto('file://' + file);
  await settle(page);
  const toCard = async () => {
    await page.focus('#canvas');
    const order = await page.evaluate(() => window.systemapCanvas.order(''));
    for (let i = 0; i <= order.indexOf(card); i++) await page.keyboard.press('Tab');
  };
  // Esc from the map of CARD: the live region gives the map and the focused card.
  await toCard();
  await page.keyboard.press('Enter');
  await settle(page);
  await page.keyboard.press('Escape');
  await settle(page, 1200);
  out.escaped = await keyed(page);
  // A zoom out closes the map of the focused card: the card loses the keyboard focus, and
  // Enter selects nothing.
  await page.keyboard.press('Enter');
  await settle(page);
  await page.keyboard.press('Tab');
  out.inner = await keyed(page);
  for (let i = 0; i < 6; i++) { await page.keyboard.press('-'); await settle(page, 100); }
  await settle(page);
  out.closed = await keyed(page);
  await page.keyboard.press('Enter');
  await settle(page);
  out.closedEnter = await keyed(page);
  // Esc on a link of the list of the tree does not move the keyboard focus to a card.
  await page.goto('file://' + file + '#' + card);
  await settle(page);
  await page.focus('#canvas-tree a[data-c]');
  await page.keyboard.press('Escape');
  await settle(page, 1200);
  out.linkEscaped = await keyed(page);
  await context.close();
  out.pinch = await pinch(browser, file);
  await browser.close();
  return out;
}

// A pinch out and a pinch in with two fingers about the middle of a phone screen. Each
// touch event moves the two fingers. For each pinch: the zoom ratio, and the screen
// distance from the middle of the fingers at the end to the world point that was at the
// middle of the fingers at the start.
async function pinch(browser, file) {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3, reducedMotion: 'reduce' });
  const page = await context.newPage(), cdp = await context.newCDPSession(page), out = [];
  await page.goto('file://' + file);
  await settle(page);
  const touch = (type, pts) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints: pts.map(([x, y, id]) => ({ x, y, id })) });
  const cam = () => page.evaluate(() => window.systemapCanvas.camera());
  for (const [from, to, cx, cy] of [[40, 120, 180, 400], [120, 40, 200, 430]]) {
    const c0 = await cam(), wx = c0.x + cx / c0.k, wy = c0.y + cy / c0.k;
    await touch('touchStart', [[cx - from, cy - from / 2, 0], [cx + from, cy + from / 2, 1]]);
    for (let i = 1; i <= 10; i++) {
      const d = from + (to - from) * i / 10;
      await touch('touchMove', [[cx - d, cy - d / 2, 0], [cx + d, cy + d / 2, 1]]);
      await page.waitForTimeout(16);
    }
    await touch('touchEnd', []);
    await settle(page, 200);
    const c1 = await cam();
    out.push({ ratio: c1.k / c0.k, drift: Math.hypot((wx - c1.x) * c1.k - cx, (wy - c1.y) * c1.k - cy) });
  }
  await context.close();
  return out;
}

(async () => {
  const [mode, file, id, flag] = process.argv.slice(2);
  if (mode === '--probe') {
    const b = await chromium.launch();
    await b.close();
    console.log(JSON.parse(fs.readFileSync(require.resolve('axe-core/package.json'), 'utf8')).version);
    return;
  }
  const out = mode === '--axe' ? await axe(file, id, flag === '--small') : await held(file, id);
  console.log(JSON.stringify(out));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
