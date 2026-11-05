// Drives a canvas page (systemap.canvas_page) in the Chromium of Playwright and prints
// one JSON object of what the page did. tests/test_canvas_browser.py reads it.
//
//     node tests/canvas_driver.js PAGE.html CARD NEIGHBOUR [--light | --phone | --fits [--phone] | --links | --fade]
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

// The screen box of the frame of the map `id`, and the free width: the screen width less a
// band at each side as wide as the widest portal in the left or the right 15 % of the screen.
const free = (page, id) => page.evaluate((id) => {
  const W = innerWidth, sides = window.systemapCanvas.hits().filter((h) => h.kind === 'portal' && (h.x + h.w < 0.15 * W || h.x > 0.85 * W));
  const band = Math.max(0, ...sides.map((p) => (p.x < W / 2 ? p.x + p.w : W - p.x)));
  return { frame: window.systemapCanvas.frame(id), band, free: W - 2 * band };
}, id);

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
  out.inside.links = await page.evaluate(() => window.systemapCanvas.links());
  out.inside.boxes = await page.evaluate((id) => window.systemapCanvas.boxes(id).concat(window.systemapCanvas.boxes('').filter((c) => c.id !== id)), card);
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

// --fits: on a screen of 1440 x 900 pixels (390 x 844 with --phone), the camera fit of
// each map, the portals that cover a card of that map, and the frame and the free width.
// CARD is the ID of the first map and NEIGHBOUR of the second.
async function fits(file, ids, small) {
  const browser = await chromium.launch();
  const viewport = small ? { width: 390, height: 844 } : { width: 1440, height: 900 };
  const context = await browser.newContext({ viewport, reducedMotion: 'reduce' });
  const page = await context.newPage();
  await page.goto('file://' + file);
  await settle(page);
  const out = {};
  for (const id of ids) {
    await page.evaluate((m) => window.systemapCanvas.view(window.systemapCanvas.fit(m)), id);
    const s = await state(page);
    out[id] = { chain: s.chain, portals: s.hits.filter((h) => h.kind === 'portal').length, covered: await covered(page), ...await free(page, id) };
  }
  await browser.close();
  return out;
}

// --links: on a screen of 1440 x 900 pixels, the boundary flows at the fit of each map,
// zoomed out and in, and moved. A problem is a segment that is not horizontal or vertical,
// that goes into a card that is not open, or that has a point off the screen, or a flow
// that does not end at the edge of its portal. `atFit` is the count of flows at each fit.
async function links(file, ids) {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
  const page = await context.newPage();
  await page.goto('file://' + file);
  await settle(page);
  const out = await page.evaluate((ids) => {
    const S = window.systemapCanvas, W = innerWidth, H = innerHeight, r = { frames: 0, links: 0, atFit: {}, problems: [] };
    const into = (p, q, b) => Math.min(p[0], q[0]) < b[0] + b[2] - 1 && Math.max(p[0], q[0]) > b[0] + 1 &&
      Math.min(p[1], q[1]) < b[1] + b[3] - 1 && Math.max(p[1], q[1]) > b[1] + 1;
    const edge = (p, h) => (Math.abs(p[0] - h.x) < 0.5 || Math.abs(p[0] - h.x - h.w) < 0.5) && p[1] >= h.y - 0.5 && p[1] <= h.y + h.h + 0.5 ||
      (Math.abs(p[1] - h.y) < 0.5 || Math.abs(p[1] - h.y - h.h) < 0.5) && p[0] >= h.x - 0.5 && p[0] <= h.x + h.w + 0.5;
    ids.forEach((id) => {
      const f = S.fit(id);
      [0.6, 0.8, 1, 1.25, 1.6, 2.5].forEach((z) => [-0.2, 0, 0.2].forEach((d) => {
        const k = f.k * z, cx = f.x + W / 2 / f.k + d * W / k, cy = f.y + H / 2 / f.k + d * H / k;
        S.view({ x: cx - W / 2 / k, y: cy - H / 2 / k, k });
        r.frames++;
        if (z === 1 && d === 0) r.atFit[id] = S.links().length;
        const chain = S.chain(), open = new Set(chain), portals = S.hits().filter((h) => h.kind === 'portal');
        const cards = [];
        S.maps().forEach((m) => S.boxes(m.id).forEach((c) => {
          const child = (m.id ? m.id + '/' : '') + c.id;
          if (!open.has(child) && c.b[0] < W && c.b[1] < H && c.b[0] + c.b[2] > 0 && c.b[1] + c.b[3] > 0) cards.push([m.id + ':' + c.id, c.b]);
        }));
        S.links().forEach((l) => {
          r.links++;
          const p = l.points, tag = id + ' x' + z + ' ' + d + ' ' + l.id + ' ';
          p.forEach((q) => { if (q[0] < 0 || q[0] > W || q[1] < 0 || q[1] > H) r.problems.push(tag + 'off the screen'); });
          for (let i = 1; i < p.length; i++) {
            if (Math.abs(p[i][0] - p[i - 1][0]) > 0.5 && Math.abs(p[i][1] - p[i - 1][1]) > 0.5) r.problems.push(tag + 'not a right angle');
            cards.forEach(([name, b]) => { if (into(p[i - 1], p[i], b)) r.problems.push(tag + 'into ' + name); });
          }
          const end = l.d === 'in' ? p[0] : p[p.length - 1];
          if (!portals.some((h) => h.id === l.id && edge(end, h))) r.problems.push(tag + 'not at its portal');
        });
      }));
    });
    return r;
  }, ids);
  await browser.close();
  return out;
}

// --fade: on a screen of 1440 x 900 pixels, without reduced motion, four slow camera moves of
// 200 frames each, with one animation frame for each camera step: from the top fit into the
// map CARD, from the map CARD out to the top fit, from the map NEIGHBOUR into the map CARD,
// and a zoom from 0.5 to 3 times the fit of the map CARD. The scale moves in log space, and
// the move is slow at its two ends (smoothstep). Each frame records the alpha of each drawn
// boundary flow path. `worst` is the largest change of an alpha between two frames, where a
// path that is not drawn has the alpha 0. A problem is a drawn path that goes into a card
// that is not open.
async function fade(file, ids) {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'no-preference' });
  const page = await context.newPage();
  await page.goto('file://' + file);
  await settle(page);
  const out = { dives: [] };
  for (const [from, to, za, zb] of [['', ids[0], 1, 1], [ids[0], '', 1, 1], [ids[1], ids[0], 1, 1], [ids[0], ids[0], 0.5, 3]]) {
    out.dives.push(await page.evaluate(([from, to, za, zb]) => new Promise((done) => {
      const S = window.systemapCanvas, W = innerWidth, H = innerHeight, fa = S.fit(from), fb = S.fit(to);
      const mid = (c) => [c.x + W / 2 / c.k, c.y + H / 2 / c.k], [ax, ay] = mid(fa), [bx, by] = mid(fb);
      const a = { k: fa.k * za }, b = { k: fb.k * zb };
      const into = (p, q, r) => Math.min(p[0], q[0]) < r[0] + r[2] - 1 && Math.max(p[0], q[0]) > r[0] + 1 &&
        Math.min(p[1], q[1]) < r[1] + r[3] - 1 && Math.max(p[1], q[1]) > r[1] + 1;
      const r = { from, to, zoom: [za, zb], frames: 0, drawn: 0, worst: 0, where: '', problems: [] };
      let f = 0, before = {};
      const step = () => {
        const u = f / 199, t = u * u * (3 - 2 * u), k = a.k * Math.pow(b.k / a.k, t), cx = ax + (bx - ax) * t, cy = ay + (by - ay) * t;
        S.view({ x: cx - W / 2 / k, y: cy - H / 2 / k, k });
        const now = {}, open = new Set(S.chain()), cards = [];
        S.maps().forEach((m) => S.boxes(m.id).forEach((c) => {
          if (!open.has((m.id ? m.id + '/' : '') + c.id)) cards.push([m.id + ':' + c.id, c.b]);
        }));
        S.links().forEach((l) => {
          const key = l.key || l.id + '|' + l.d;
          now[key] = Math.max(now[key] || 0, l.alpha === undefined ? 1 : l.alpha);
          r.drawn++;
          for (let i = 1; i < l.points.length; i++) {
            cards.forEach(([name, box]) => { if (into(l.points[i - 1], l.points[i], box)) r.problems.push(f + ' ' + key + ' into ' + name); });
          }
        });
        if (f) new Set(Object.keys(now).concat(Object.keys(before))).forEach((key) => {
          const d = Math.abs((now[key] || 0) - (before[key] || 0));
          if (d > r.worst) { r.worst = d; r.where = f + ' ' + key; }
        });
        before = now; r.frames = ++f;
        if (f < 200) requestAnimationFrame(step); else done(r);
      };
      requestAnimationFrame(step);
    }), [from, to, za, zb]));
  }
  await browser.close();
  return out;
}

(async () => {
  if (process.argv[2] === '--probe') { const b = await chromium.launch(); await b.close(); return; }
  const [file, card, neighbour] = process.argv.slice(2);
  const small = process.argv.includes('--phone');
  const out = process.argv.includes('--fits') ? await fits(file, [card, neighbour], small)
    : process.argv.includes('--links') ? await links(file, [card, neighbour])
    : process.argv.includes('--fade') ? await fade(file, [card, neighbour])
    : small ? await phone(file, card) : await run(file, card, neighbour, process.argv.includes('--light'));
  process.stdout.write(JSON.stringify(out) + '\n');
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
