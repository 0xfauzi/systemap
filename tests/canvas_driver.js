// Drives a canvas page (systemap.canvas_page) in the Chromium of Playwright and prints
// one JSON object of what the page did. tests/test_canvas_browser.py reads it.
//
//     node tests/canvas_driver.js PAGE.html CARD NEIGHBOUR [--light]
//     node tests/canvas_driver.js --probe
//
// CARD is a card of the top map that opens a map, and NEIGHBOUR is a card of the top
// map that is a neighbour of that map. The page runs with prefers-reduced-motion, so
// each camera move occurs at one time. --probe exits 0 if Playwright can start Chromium.
'use strict';
const { chromium } = require('playwright');

const settle = (page) => page.waitForTimeout(400);
const state = (page) => page.evaluate(() => ({
  chain: window.systemapCanvas.chain(), hash: location.hash, camera: window.systemapCanvas.camera(),
  hits: window.systemapCanvas.hits(), label: document.getElementById('canvas').getAttribute('aria-label'),
}));
const centre = (b) => [b[0] + b[2] / 2, b[1] + b[3] / 2];

async function run(file, card, neighbour, light) {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 }, reducedMotion: 'reduce', colorScheme: light ? 'light' : 'dark',
  });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  const out = {};
  await page.goto('file://' + file);
  await settle(page);
  out.start = await state(page);
  out.theme = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  // Double-click the card that opens a map: the camera goes into its map.
  const box = await page.evaluate((id) => window.systemapCanvas.box('', id), card);
  await page.mouse.dblclick(...centre(box));
  await settle(page);
  out.inside = await state(page);
  // A portal: a neighbour of the open map at the edge of the screen. A click moves the camera to it.
  const portal = out.inside.hits.find((h) => h.kind === 'portal' && h.id === neighbour);
  if (portal) {
    await page.mouse.click(portal.x + portal.w / 2, portal.y + portal.h / 2);
    await settle(page);
    out.portal = await state(page);
    out.portalCard = await page.evaluate((id) => window.systemapCanvas.box('', id), neighbour);
    await page.mouse.dblclick(...centre(await page.evaluate((id) => window.systemapCanvas.box('', id), card)));
    await settle(page);
  }
  // Escape goes out one level.
  await page.keyboard.press('Escape');
  await settle(page);
  out.escaped = await state(page);
  // + zooms in, - zooms out, and F fits the current map.
  const before = (await state(page)).camera.k;
  await page.keyboard.press('+');
  await settle(page);
  out.zoomIn = (await state(page)).camera.k / before;
  await page.keyboard.press('-');
  await page.keyboard.press('-');
  await settle(page);
  out.zoomOut = (await state(page)).camera.k / before;
  await page.keyboard.press('f');
  await settle(page);
  out.fitted = (await state(page)).camera.k / before;
  // The hash: a link with the map ID opens the canvas at that map.
  await page.goto('file://' + file + '#' + encodeURIComponent(card));
  await settle(page);
  out.linked = await state(page);
  // A drag moves the camera.
  const k0 = (await state(page)).camera;
  await page.mouse.move(600, 400);
  await page.mouse.down();
  await page.mouse.move(500, 380, { steps: 5 });
  await page.mouse.up();
  await settle(page);
  const k1 = (await state(page)).camera;
  out.dragged = [(k1.x - k0.x) * k0.k, (k1.y - k0.y) * k0.k];
  // The wheel zooms at the pointer: the world point under the pointer stays.
  const under = (c) => [c.x + 300 / c.k, c.y + 200 / c.k];
  const w0 = under((await state(page)).camera);
  await page.mouse.move(300, 200);
  await page.mouse.wheel(0, -200);
  await settle(page);
  const c2 = (await state(page)).camera, w1 = under(c2);
  out.wheel = { zoom: c2.k / k1.k, moved: Math.hypot(w1[0] - w0[0], w1[1] - w0[1]) * c2.k };
  out.errors = errors;
  await browser.close();
  return out;
}

// --phone: a link with the hash of CARD on a screen of 390 x 844 pixels.
async function phone(file, card) {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce', hasTouch: true });
  const page = await context.newPage();
  await page.goto('file://' + file + '#' + encodeURIComponent(card));
  await settle(page);
  const out = { linked: await state(page) };
  await browser.close();
  return out;
}

(async () => {
  if (process.argv[2] === '--probe') { const b = await chromium.launch(); await b.close(); return; }
  const [file, card, neighbour] = process.argv.slice(2);
  const out = process.argv.includes('--phone') ? await phone(file, card) : await run(file, card, neighbour, process.argv.includes('--light'));
  process.stdout.write(JSON.stringify(out) + '\n');
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
