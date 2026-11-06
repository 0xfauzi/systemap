// Drives a canvas page (systemap.canvas_page) in the Chromium of Playwright and prints
// one JSON object of what the page did. tests/test_canvas_browser.py reads it.
//
//     node tests/canvas_driver.js PAGE.html CARD NEIGHBOUR [--light | --phone | --fits [--phone] | --links | --fade [--phone] | --layers | --portals [--phone] | --layout]
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
    // The same test as `into` in page_canvas_draw.py, with a box x, y, w, h. The driver
    // cannot get the functions of the page.
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


// --fade: without reduced motion, slow camera moves of 200 frames each, with one animation
// frame for each camera step. CARD is a map on level 2 and NEIGHBOUR is its parent map. On a
// screen of 1440 x 900 pixels, the moves are the four moves of F1: from the top fit into the
// map CARD, from the map CARD out to the top fit, from the map NEIGHBOUR into the map CARD,
// and a zoom from 0.5 to 3 times the fit of the map CARD. With --phone, the screen is 390 x
// 844 pixels and these moves are not done. On the two screens, five moves zoom out: from the
// fit of NEIGHBOUR, of CARD and of the first map in CARD out to the fit of the map above,
// and a zoom from 3 to 0.5 times the fit of NEIGHBOUR and of CARD.
// The scale moves in log space, and the move is slow at its two ends (smoothstep). Each
// frame records the alpha of each drawn boundary flow path. `worst` is the largest change of
// an alpha between two frames, where a path that is not drawn has the alpha 0. A problem is
// a pixel of the layer of the lines (`systemapCanvas.layer`) with an alpha more than 0 in a
// card that is not open, 2 pixels or more in from the edge of its box. The page puts that
// layer on the screen with no other change, thus such a pixel is a line pixel over a card.
// `under` counts the drawn paths that go into a card that is not open. The card covers them.
async function fade(file, ids, small) {
  const browser = await chromium.launch();
  const viewport = small ? { width: 390, height: 844 } : { width: 1440, height: 900 };
  const context = await browser.newContext({ viewport, reducedMotion: 'no-preference' });
  const page = await context.newPage();
  await page.goto('file://' + file);
  await settle(page);
  const [card, up] = ids;
  const deep = await page.evaluate((id) => window.systemapCanvas.maps().find((m) => m.id === id).opens[0], card);
  const moves = small ? [] : [['', card, 1, 1], [card, '', 1, 1], [up, card, 1, 1], [card, card, 0.5, 3]];
  moves.push([up, '', 1, 1], [card, up, 1, 1], [deep, card, 1, 1], [up, up, 3, 0.5], [card, card, 3, 0.5]);
  const out = { dives: [] };
  for (const move of moves) {
    out.dives.push(await page.evaluate(([from, to, za, zb]) => new Promise((done) => {
      const S = window.systemapCanvas, W = innerWidth, H = innerHeight, fa = S.fit(from), fb = S.fit(to);
      const mid = (c) => [c.x + W / 2 / c.k, c.y + H / 2 / c.k], [ax, ay] = mid(fa), [bx, by] = mid(fb);
      const a = { k: fa.k * za }, b = { k: fb.k * zb };
      // The same test as `into` in page_canvas_draw.py, with a box x, y, w, h. The driver
      // cannot get the functions of the page.
      const into = (p, q, r) => Math.min(p[0], q[0]) < r[0] + r[2] - 1 && Math.max(p[0], q[0]) > r[0] + 1 &&
        Math.min(p[1], q[1]) < r[1] + r[3] - 1 && Math.max(p[1], q[1]) > r[1] + 1;
      const r = { from, to, zoom: [za, zb], frames: 0, drawn: 0, under: 0, worst: 0, where: '', checked: 0, problems: [] };
      // The pixels of the layer with an alpha more than 0 in the inside of a card box.
      const pixels = (cards) => {
        const L = S.layer();
        if (!L) return;
        const sx = L.canvas.width / W, sy = L.canvas.height / H, g = L.canvas.getContext('2d');
        const x0 = Math.floor(L.box[0] * sx), y0 = Math.floor(L.box[1] * sy);
        const w = Math.ceil(L.box[2] * sx) - x0, h = Math.ceil(L.box[3] * sy) - y0;
        if (w <= 0 || h <= 0) return;
        const data = g.getImageData(x0, y0, w, h).data;
        cards.forEach(([name, c]) => {
          const i0 = Math.max(Math.ceil((c[0] + 2) * sx), x0), i1 = Math.min(Math.floor((c[0] + c[2] - 2) * sx), x0 + w);
          const j0 = Math.max(Math.ceil((c[1] + 2) * sy), y0), j1 = Math.min(Math.floor((c[1] + c[3] - 2) * sy), y0 + h);
          let most = 0;
          for (let j = j0; j < j1; j++) for (let i = i0; i < i1; i++) { most = Math.max(most, data[((j - y0) * w + i - x0) * 4 + 3]); r.checked++; }
          if (most > 0) r.problems.push(r.frames + ' alpha ' + most + ' over ' + name);
        });
      };
      let f = 0, before = {};
      const step = () => {
        const u = f / 199, t = u * u * (3 - 2 * u), k = a.k * Math.pow(b.k / a.k, t), cx = ax + (bx - ax) * t, cy = ay + (by - ay) * t;
        S.view({ x: cx - W / 2 / k, y: cy - H / 2 / k, k });
        const now = {}, open = new Set(S.chain()), cards = [];
        S.maps().forEach((m) => S.boxes(m.id).forEach((c) => {
          const b = c.b;
          if (!open.has((m.id ? m.id + '/' : '') + c.id) && b[0] < W && b[1] < H && b[0] + b[2] > 0 && b[1] + b[3] > 0) cards.push([m.id + ':' + c.id, b]);
        }));
        S.links().forEach((l) => {
          now[l.key] = Math.max(now[l.key] || 0, l.alpha);
          r.drawn++;
          let hidden = false;
          for (let i = 1; i < l.points.length; i++) cards.forEach(([, box]) => { hidden = hidden || into(l.points[i - 1], l.points[i], box); });
          if (hidden) r.under++;
        });
        pixels(cards);
        if (f) new Set(Object.keys(now).concat(Object.keys(before))).forEach((key) => {
          const d = Math.abs((now[key] || 0) - (before[key] || 0));
          if (d > r.worst) { r.worst = d; r.where = f + ' ' + key; }
        });
        before = now; r.frames = ++f;
        if (f < 200) requestAnimationFrame(step); else done(r);
      };
      requestAnimationFrame(step);
    }), move));
  }
  await browser.close();
  return out;
}

// --layers: the page FILE of a large map (CARD and NEIGHBOUR are not used), on a screen of
// 1440 x 900 pixels without reduced motion. Three camera moves, each with one animation
// frame for each camera step and then a stop of STOP_MS: a dive of 180 frames from the fit
// of the map into its middle card, a pan of 120 frames, and the dive back out. The page
// records each frame (`record`). The layers of a frame are HIDE (the text that MOVE_TEXT
// hides has the alpha 1 - HIDE), the image layer `v` of each map, and the part of the result
// that each image gives. A layer that a frame does not have has the alpha 0. `worst` is the
// largest change of an alpha between two frames. `full` counts the frames with an image
// layer of 1, and `fading` the frames with an image layer between 0 and 1.
const STOP_MS = 700;
async function layers(file) {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'no-preference' });
  const page = await context.newPage();
  await page.goto('file://' + file);
  await settle(page);
  const out = { moves: [] };
  for (const kind of ['dive in', 'pan', 'dive out']) {
    out.moves.push(await page.evaluate(([kind, stop]) => new Promise((done) => {
      const S = window.systemapCanvas, W = innerWidth, H = innerHeight, top = S.fit(''), deep = S.deepFit();
      const mid = (c) => [c.x + W / 2 / c.k, c.y + H / 2 / c.k], [tx, ty] = mid(top), [dx, dy] = mid(deep);
      const camAt = (e) => {
        const k = top.k * Math.pow(deep.k / top.k, e);
        return { x: tx + (dx - tx) * e - W / 2 / k, y: ty + (dy - ty) * e - H / 2 / k, k };
      };
      const smooth = (u) => u * u * (3 - 2 * u), n = kind === 'pan' ? 120 : 180;
      const at = kind === 'dive in' ? (u) => camAt(smooth(u)) : kind === 'dive out' ? (u) => camAt(1 - smooth(u))
        : (u) => { const c = camAt(0.22); return { x: c.x + Math.sin(u * Math.PI * 2) * 200 / c.k, y: c.y, k: c.k }; };
      const alphas = (r) => {
        const a = { hide: r.hide };
        r.images.forEach((l) => {
          a['layer ' + l.id] = l.v;
          l.parts.forEach(([key, part]) => { a['image ' + l.id + ' ' + key] = part; });
        });
        return a;
      };
      let f = 0;
      S.record();
      const step = () => {
        S.view(at(f / (n - 1)));
        if (++f < n) { requestAnimationFrame(step); return; }
        setTimeout(() => {
          const log = S.recorded(), r = { kind, frames: log.length, worst: 0, where: '', full: 0, fading: 0, hideMax: 0, still: 0, stillFading: 0 };
          let before = null;
          log.forEach((rec, i) => {
            const now = alphas(rec), v = rec.images.map((l) => l.v);
            if (v.some((x) => x >= 1)) r.full++;
            if (v.some((x) => x > 0 && x < 1)) r.fading++;
            r.hideMax = Math.max(r.hideMax, rec.hide);
            if (rec.sharp) { r.still++; if (rec.hide > 0 || rec.images.length) r.stillFading++; }
            if (before) new Set(Object.keys(now).concat(Object.keys(before))).forEach((key) => {
              const d = Math.abs((now[key] || 0) - (before[key] || 0));
              if (d > r.worst) { r.worst = d; r.where = i + ' ' + key; }
            });
            before = now;
          });
          const last = log[log.length - 1];
          r.end = { sharp: last.sharp, fine: last.fine, hide: last.hide, images: last.images.length };
          done(r);
        }, stop);
      };
      requestAnimationFrame(step);
    }), [kind, STOP_MS]));
  }
  await browser.close();
  return out;
}

// --portals: on a screen of 1440 x 900 pixels (390 x 844 with --phone), without reduced
// motion, two slow camera moves of 300 frames each, with one animation frame for each
// camera step: a dive into the map CARD and a zoom out from it. The middle of the screen
// stays on the middle of the fit of CARD, and the scale goes from the scale of the top fit
// to the scale of the fit of CARD (the dive), or back (the zoom out), in log space and
// slowly at the two ends (smoothstep). Each frame records the alpha and the middle of each
// portal. `worst` is the largest change of a portal alpha between two frames, where a
// portal that is not drawn has the alpha 0. `jump` is the largest move of the middle of a
// portal between two frames in which it is drawn. `changes` is the count of frames in
// which the chain changed, and `most` is the largest count of portals in one frame.
async function portals(file, card, small) {
  const browser = await chromium.launch();
  const viewport = small ? { width: 390, height: 844 } : { width: 1440, height: 900 };
  const context = await browser.newContext({ viewport, reducedMotion: 'no-preference' });
  const page = await context.newPage();
  await page.goto('file://' + file);
  await settle(page);
  const out = { moves: [] };
  for (const dive of [true, false]) {
    out.moves.push(await page.evaluate(([card, dive]) => new Promise((done) => {
      const S = window.systemapCanvas, W = innerWidth, H = innerHeight, top = S.fit('').k, fit = S.fit(card), n = 300;
      const cx = fit.x + W / 2 / fit.k, cy = fit.y + H / 2 / fit.k, ka = dive ? top : fit.k, kb = dive ? fit.k : top;
      const r = { move: dive ? 'dive' : 'zoom out', frames: 0, worst: 0, jump: 0, where: '', at: '', changes: 0, most: 0 };
      let f = 0, before = {}, chain = '';
      const step = () => {
        const u = f / (n - 1), t = u * u * (3 - 2 * u), k = ka * Math.pow(kb / ka, t);
        S.view({ x: cx - W / 2 / k, y: cy - H / 2 / k, k });
        const now = {}, c = S.chain().join(' ');
        if (f && c !== chain) r.changes++;
        chain = c;
        S.hits().filter((h) => h.kind === 'portal').forEach((h) => {
          const key = h.map + '/' + h.id, a = h.show === undefined ? 1 : h.show;
          now[key] = { a: Math.max(a, now[key] ? now[key].a : 0), x: h.x + h.w / 2, y: h.y + h.h / 2 };
        });
        r.most = Math.max(r.most, Object.keys(now).length);
        if (f) new Set(Object.keys(now).concat(Object.keys(before))).forEach((key) => {
          const a = now[key], b = before[key], d = Math.abs((a ? a.a : 0) - (b ? b.a : 0));
          if (d > r.worst) { r.worst = d; r.where = f + ' ' + key; }
          const m = a && b ? Math.hypot(a.x - b.x, a.y - b.y) : 0;
          if (m > r.jump) { r.jump = m; r.at = f + ' ' + key; }
        });
        before = now; r.frames = ++f;
        if (f < n) requestAnimationFrame(step); else done(r);
      };
      requestAnimationFrame(step);
    }), [card, dive]));
  }
  await browser.close();
  return out;
}

// --layout: the camera fit of the top map and of the first map on each level below it, to
// level 3, on screens of 390 x 844, 844 x 390 and 1440 x 900 pixels, and after the screen
// of 390 x 844 pixels turns to 844 x 390 pixels. For each fit: the screen size, the frame
// of the open map, the free bands (`gutters`), the cards of the open map that the screen edge
// cuts, and the boxes of the path, the help line and the portals that cover each other.
const fitState = (page, id) => page.evaluate((id) => {
  const S = window.systemapCanvas, W = innerWidth, H = innerHeight, L = S.layout(), out = [];
  const boxes = [['path', L.path], ['help', L.help]].concat(S.hits().filter((h) => h.kind === 'portal').map((h) => ['portal ' + h.id, [h.x, h.y, h.w, h.h]]));
  boxes.forEach(([a, p], i) => boxes.slice(i + 1).forEach(([b, q]) => {
    if (p[0] < q[0] + q[2] && q[0] < p[0] + p[2] && p[1] < q[1] + q[3] && q[1] < p[1] + p[3]) out.push(a + ' over ' + b);
  }));
  const cut = S.boxes(id).filter((c) => c.b[0] < -0.5 || c.b[1] < -0.5 || c.b[0] + c.b[2] > W + 0.5 || c.b[1] + c.b[3] > H + 0.5).map((c) => c.id);
  return { id, W, H, chain: S.chain(), frame: S.frame(id), gutters: L.gutters, cut, covers: out, help: L.help, line: L.line };
}, id);
async function layout(file) {
  const browser = await chromium.launch(), out = [];
  for (const [width, height] of [[390, 844], [844, 390], [1440, 900]]) {
    const context = await browser.newContext({ viewport: { width, height }, reducedMotion: 'reduce' });
    const page = await context.newPage();
    await page.goto('file://' + file);
    await settle(page);
    const ids = await page.evaluate(() => {
      const S = window.systemapCanvas, maps = S.maps(), list = [''];
      for (let m = maps.find((x) => x.id === ''); m.opens.length && list.length < 4; m = maps.find((x) => x.id === m.opens[0])) list.push(m.opens[0]);
      return list;
    });
    for (const id of ids) {
      await page.evaluate((m) => window.systemapCanvas.view(window.systemapCanvas.fit(m)), id);
      out.push(await fitState(page, id));
    }
    if (width === 390) {
      await page.setViewportSize({ width: height, height: width });
      await settle(page);
      out.push({ turned: true, ...await fitState(page, ids[ids.length - 1]) });
    }
    await context.close();
  }
  await browser.close();
  return { fits: out };
}

(async () => {
  if (process.argv[2] === '--probe') { const b = await chromium.launch(); await b.close(); return; }
  const [file, card, neighbour] = process.argv.slice(2);
  const small = process.argv.includes('--phone');
  const out = process.argv.includes('--layout') ? await layout(file)
    : process.argv.includes('--fits') ? await fits(file, [card, neighbour], small)
    : process.argv.includes('--links') ? await links(file, [card, neighbour])
    : process.argv.includes('--fade') ? await fade(file, [card, neighbour], small)
    : process.argv.includes('--layers') ? await layers(file)
    : process.argv.includes('--portals') ? await portals(file, card, small)
    : small ? await phone(file, card) : await run(file, card, neighbour, process.argv.includes('--light'));
  process.stdout.write(JSON.stringify(out) + '\n');
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
