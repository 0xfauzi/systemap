// Drives a canvas page (systemap.canvas_page) in the Chromium of Playwright for the access
// checks, and prints one JSON object. tests/test_canvas_access.py reads it.
//
//     node tests/canvas_access.js --axe PAGE.html NESTED [--small]
//     node tests/canvas_access.js --held PAGE.html CARD
//     node tests/canvas_access.js --dive PAGE.html CARD
//     node tests/canvas_access.js --probe
//
// --axe puts axe-core into the page with page.evaluate and runs it. The page loads no
// axe-core file, and its CSP does not change. axe-core comes from the node_modules folder
// of the checkout or from NODE_PATH. NESTED is the ID of a nested map. --small runs only
// the screen of 1440 x 900 pixels. --held gives the state after a URL hash that names a
// property of all objects, after a zoom out that closes the map of the focused card, after
// Esc, after a zoom into the map of a card that is not the focused card, and after a pinch.
// CARD is a card of the top map that opens a map. --dive gives the state after Enter on
// CARD and Tab during the flight, without reduced motion. --probe exits 0 and prints the
// axe-core version when Playwright can start Chromium and axe-core is there. Each place
// has a new load of the page: a change of only the hash keeps the document.
'use strict';
const fs = require('fs');
const { chromium } = require('playwright');

const settle = (page, ms) => page.waitForTimeout(ms || 400);
const axeFile = () => require.resolve('axe-core/axe.min.js');
const PHONE = { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3 };
const SCREENS = [{ tag: '1440x900', viewport: { width: 1440, height: 900 } }, { tag: '390x844', ...PHONE }];
// A new load of the page at `hash`.
const load = async (page, file, hash) => { await page.goto('about:blank'); await page.goto('file://' + file + (hash || '')); };
// Record each text of the live region from now, in window.__said.
const hear = (page) => page.evaluate(() => {
  const said = document.getElementById('canvas-said'), out = [];
  window.__said = out;
  new MutationObserver((records) => records.forEach((r) => {
    if (r.type === 'childList') r.addedNodes.forEach((n) => out.push(n.textContent));
    else out.push(r.target.data);
  })).observe(said, { childList: true, characterData: true, subtree: true });
});
const heard = (page) => page.evaluate(() => window.__said);

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
        await load(page, file, hash);
        await settle(page, 600);
        const at = { screen: s.tag, scheme, hash };
        const before = await page.evaluate(() => ({ focus: window.systemapCanvas.keys().focus, active: document.activeElement.id || document.activeElement.tagName }));
        runs.push({ ...at, state: 'no focus', before, ...(await audit(page, source)) });
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
  live: document.getElementById('canvas-said').textContent, active: document.activeElement.id || document.activeElement.tagName,
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
  await hear(page);
  await page.keyboard.press('Escape');
  await settle(page, 1200);
  out.escaped = await keyed(page);
  out.escapedSaid = await heard(page);
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
  // A zoom into the map of CARD, with the keyboard focus on a different card of the top
  // map: that card loses the keyboard focus, and the next Tab goes to the first card of the
  // map of CARD.
  await load(page, file);
  await settle(page);
  await page.focus('#canvas');
  await page.keyboard.press('Tab');
  if ((await keyed(page)).focus.id === card) await page.keyboard.press('Tab');
  out.other = (await keyed(page)).focus;
  const b = await page.evaluate((id) => window.systemapCanvas.box('', id), card);
  await page.mouse.move(b[0] + b[2] / 2, b[1] + b[3] / 2);
  for (let i = 0; i < 60 && (await keyed(page)).chain.length === 0; i++) { await page.mouse.wheel(0, -120); await settle(page, 50); }
  await settle(page);
  out.zoomedIn = await keyed(page);
  out.innerOrder = await page.evaluate((id) => window.systemapCanvas.order(id), card);
  await page.keyboard.press('Tab');
  out.zoomedTab = await keyed(page);
  // Esc on a link of the list of the tree does not move the keyboard focus to a card.
  await load(page, file, '#' + card);
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
  const context = await browser.newContext({ ...PHONE, reducedMotion: 'reduce' });
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

// Enter on CARD of the top map, and Tab 400 ms later, during the flight into the map of
// CARD. The screen is 1280 x 800 pixels, without reduced motion. `said` gives each text of
// the live region after Enter.
async function dive(file, card) {
  const browser = await chromium.launch(), out = { errors: [] };
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: 'no-preference' })).newPage();
  page.on('pageerror', (e) => out.errors.push(String(e)));
  await load(page, file);
  await settle(page, 1500);
  await page.focus('#canvas');
  for (let i = 0; i < 100 && ((await keyed(page)).focus || {}).id !== card; i++) await page.keyboard.press('Tab');
  await settle(page, 1500);
  await hear(page);
  await page.keyboard.press('Enter');
  await page.waitForTimeout(400);
  await page.keyboard.press('Tab');
  await settle(page, 3000);
  out.state = await keyed(page);
  out.said = await heard(page);
  out.order = await page.evaluate((id) => window.systemapCanvas.order(id), card);
  await browser.close();
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
  const out = mode === '--axe' ? await axe(file, id, flag === '--small') : mode === '--dive' ? await dive(file, id) : await held(file, id);
  console.log(JSON.stringify(out));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
