// Drives a canvas page (systemap.canvas_page) in the Chromium of Playwright and prints
// one JSON object of what the page did. tests/test_canvas_browser.py reads it.
//
//     node tests/canvas_driver.js PAGE.html CARD NEIGHBOUR [--light | --phone | --fits]
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
// The cards of the open map that a portal covers, or can cover when it moves along its
// screen edge, as "portal over card". A portal in the left or the right 15 % of the screen
// moves up and down. Another portal moves to the left and to the right.
const covered = (page) => page.evaluate(() => {
  const S = window.systemapCanvas, chain = S.chain(), id = chain.length ? chain[chain.length - 1] : '', out = [];
  const map = JSON.parse(document.getElementById('canvas-data').textContent).maps.find((m) => m.id === id);
  const W = innerWidth, H = innerHeight;
  const bands = S.hits().filter((h) => h.kind === 'portal').map((p) => (p.x + p.w < 0.15 * W || p.x > 0.85 * W
    ? { id: p.id, x: p.x, y: 0, w: p.w, h: H } : { id: p.id, x: 0, y: p.y, w: W, h: p.h }));
  map.cards.forEach((c) => {
    const b = S.box(id, c.id);
    bands.forEach((p) => {
      if (p.x < b[0] + b[2] && p.x + p.w > b[0] && p.y < b[1] + b[3] && p.y + p.h > b[1]) out.push(p.id + ' over ' + c.id);
    });
  });
  return out;
});

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
  // The boundary flows from the portals, and the screen boxes of the cards around them.
  out.inside.links = await page.evaluate(() => window.systemapCanvas.links ? window.systemapCanvas.links() : null);
  out.inside.boxes = await page.evaluate((id) => window.systemapCanvas.boxes
    ? window.systemapCanvas.boxes(id).concat(window.systemapCanvas.boxes('').filter((c) => c.id !== id)) : null, card);
  out.inside.covered = await covered(page);
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

// --fits: on a screen of 1440 x 900 pixels, the camera fit of each map, and the portals
// that cover a card of that map. CARD is the ID of the first map and NEIGHBOUR of the second.
async function fits(file, ids) {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
  const page = await context.newPage();
  await page.goto('file://' + file);
  await settle(page);
  const out = {};
  for (const id of ids) {
    await page.evaluate((m) => window.systemapCanvas.view(window.systemapCanvas.fit(m)), id);
    out[id] = { chain: (await state(page)).chain, portals: (await state(page)).hits.filter((h) => h.kind === 'portal').length, covered: await covered(page) };
  }
  await browser.close();
  return out;
}

(async () => {
  if (process.argv[2] === '--probe') { const b = await chromium.launch(); await b.close(); return; }
  const [file, card, neighbour] = process.argv.slice(2);
  const out = process.argv.includes('--fits') ? await fits(file, [card, neighbour])
    : process.argv.includes('--phone') ? await phone(file, card) : await run(file, card, neighbour, process.argv.includes('--light'));
  process.stdout.write(JSON.stringify(out) + '\n');
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
