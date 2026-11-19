// The browser part of tests/test_atlas_browser.py: the Map view of the atlas page at rest.
//
//     node atlas_map.js MODE PAGE.html [MAP]
//
// MODE is one of:
// - --rest: 1440 x 900. The fit of the top map, with its scale beside the headline and
//   below it. For each layer tab: the state of the view, the lines of the top map
//   (`systemapCanvas.lines`), the texts of a frame, the screen boxes of the cards and of the
//   headline, and the grid.
// - --phone: 390 x 844 with a touch screen: the camera at the open, the scale readout, the
//   frame of the top map, the texts and the geometry of a frame, and the same after a click
//   on the Fit control. Also the scroll width of the page.
// - --nested: 1440 x 900 on a page with the nested map MAP: the geometry of the top map at
//   rest, the alpha of the top map and of MAP at eight cameras from the fit of the top map
//   to the fit of MAP, a double-click on the card of MAP, the chain, the headline and the
//   live region after the flight, Esc, and a load with the hash #MAP. The picture after
//   the double-click and the picture after the load with the hash are compared.
// - --marks: 1440 x 900. For each layer tab: the texts and the geometry of one frame
//   (`systemapCanvas.drawn`), the colors of the canvas at the dots and the arrowheads, and
//   the same at two other zooms. Also the dots of the grid as the canvas shows them, far
//   from the map, at four zooms.
// - --input: 1440 x 900 for the wheel and a drag, and 390 x 844 with a touch screen for a
//   pinch: the camera before and after each, and the world point under the pointer.
// - --motion: 1440 x 900 on a page with the nested map MAP, with and without reduced
//   motion: the camera 60 ms after a double-click on the card of MAP and after the flight,
//   and the smallest alpha of the lines after a change of the layer.
// - --inside: the map MAP (the top map when MAP is empty), opened with the hash #MAP. For
//   each layer tab, the frame of the map and the labels at rest with their screen boxes
//   (`systemapCanvas.lines`): at 1440 x 900 at the fit, and at 390 x 844 at the open and
//   after a click on the Fit control.
// - --page: 1440 x 900, the nested map MAP opened with the hash #MAP. The maps of the page,
//   the cards of MAP and of the top map, the texts and the geometry of one frame, and the
//   headline of each layer tab. Then for each neighbour of MAP (an actor card of MAP), in a
//   new load with the hash: a mouse click on the middle of its screen box, and after the
//   flight the chain, the current map and the selected card.
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
  const out = { errors, first, fit: await page.evaluate(() => window.systemapCanvas.fit('')), layers: [] };
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
  const atDrawn = await page.evaluate(() => window.systemapCanvas.drawn());
  await page.click('#atlas-zf');
  await page.waitForTimeout(1500);
  const fitted = await read();
  const fitDrawn = await page.evaluate(() => window.systemapCanvas.drawn());
  await page.close();
  return { errors, at, fitted, atDrawn, fitDrawn };
}

// The pixels of the canvas, as a list of numbers: R, G, B of the mean of each block of
// 4 x 4 device pixels.
function canvasPixels() {
  const c = document.getElementById('canvas'), w = c.width, h = c.height, d = c.getContext('2d').getImageData(0, 0, w, h).data, out = [];
  for (let y = 0; y + 4 <= h; y += 4) {
    for (let x = 0; x + 4 <= w; x += 4) {
      const sum = [0, 0, 0];
      for (let j = 0; j < 4; j++) for (let i = 0; i < 4; i++) { const o = ((y + j) * w + x + i) * 4; sum[0] += d[o]; sum[1] += d[o + 1]; sum[2] += d[o + 2]; }
      out.push(sum[0] / 16, sum[1] / 16, sum[2] / 16);
    }
  }
  return out;
}
// The part of the blocks of a and b that differ by more than 24 in a channel.
function differ(a, b) {
  if (a.length !== b.length) return 1;
  let n = 0;
  for (let i = 0; i < a.length; i += 3) if (Math.abs(a[i] - b[i]) > 24 || Math.abs(a[i + 1] - b[i + 1]) > 24 || Math.abs(a[i + 2] - b[i + 2]) > 24) n++;
  return n / (a.length / 3);
}

async function nested(browser, file, map) {
  const { page, errors } = await open(browser, file, WIDE);
  const top = await page.evaluate(() => window.systemapCanvas.drawn());
  // The camera on the line from the fit of the top map to the fit of the nested map.
  const fade = await page.evaluate(async (id) => {
    const a = window.systemapCanvas, f0 = a.fit(''), f1 = a.fit(id), out = [];
    for (const t of [0, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 1]) {
      const k = f0.k * Math.pow(f1.k / f0.k, t), cx0 = f0.x + innerWidth / 2 / f0.k, cy0 = f0.y + innerHeight / 2 / f0.k;
      const cx1 = f1.x + innerWidth / 2 / f1.k, cy1 = f1.y + innerHeight / 2 / f1.k, cx = cx0 + (cx1 - cx0) * t, cy = cy0 + (cy1 - cy0) * t;
      a.view({ x: cx - innerWidth / 2 / k, y: cy - innerHeight / 2 / k, k });
      await new Promise((r) => setTimeout(r, 450));
      const d = a.drawn(), own = (m) => (d.marks.find((x) => x.t === 'map' && x.id === m) || { own: 0 }).own;
      out.push({ t, top: own(''), inner: own(id), deep: a.deep() });
    }
    const f = a.fit('');
    a.view({ x: f.x, y: f.y, k: f.k });
    return out;
  }, map);
  await page.waitForTimeout(600);
  const box = await page.evaluate((id) => window.systemapCanvas.box('', id), map);
  await page.mouse.dblclick(box[0] + 20, box[1] + box[3] / 2);
  await page.waitForTimeout(2000);
  const inside = await page.evaluate(() => ({ chain: window.systemapCanvas.chain(), deep: window.systemapCanvas.deep(), view: window.systemapCanvas.viewState(),
    path: Array.prototype.map.call(document.querySelectorAll('#atlas-ask-k button'), (b) => b.textContent), hash: location.hash,
    said: document.getElementById('atlas-said').textContent, camera: window.systemapCanvas.camera() }));
  const divePixels = await page.evaluate(canvasPixels);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(2000);
  const out = await page.evaluate(() => ({ chain: window.systemapCanvas.chain(), view: window.systemapCanvas.viewState() }));
  await page.close();
  const second = await open(browser, file, WIDE, '#' + map);
  const hashed = await second.page.evaluate(() => ({ chain: window.systemapCanvas.chain(), view: window.systemapCanvas.viewState(), camera: window.systemapCanvas.camera() }));
  // The picture after the double-click and the picture after a load with the hash.
  hashed.differ = await second.page.evaluate(`(${differ.toString()})(${JSON.stringify(divePixels)}, (${canvasPixels.toString()})())`);
  // A click on the first part of the path goes to the top map.
  await second.page.click('#atlas-ask-k button');
  await second.page.waitForTimeout(2000);
  const back = await second.page.evaluate(() => window.systemapCanvas.chain());
  await second.page.close();
  return { errors: errors.concat(second.errors), top, fade, inside, out, hashed, back };
}

// The colors of the canvas at screen points (CSS pixels), as [R, G, B].
function colorsAt(points) {
  const c = document.getElementById('canvas'), g = c.getContext('2d'), d = c.width / innerWidth;
  return points.map((p) => Array.from(g.getImageData(Math.round(p[0] * d), Math.round(p[1] * d), 1, 1).data.slice(0, 3)));
}
// The dots of the canvas in a box of CSS pixels: each group of pixels that differ from the
// most common color, with its middle and its size in CSS pixels.
function dotsIn(box) {
  const c = document.getElementById('canvas'), d = c.width / innerWidth, x0 = Math.round(box[0] * d), y0 = Math.round(box[1] * d);
  const w = Math.round(box[2] * d), h = Math.round(box[3] * d), px = c.getContext('2d').getImageData(x0, y0, w, h).data, count = new Map();
  for (let i = 0; i < px.length; i += 4) { const k = px[i] + ',' + px[i + 1] + ',' + px[i + 2]; count.set(k, (count.get(k) || 0) + 1); }
  const ground = [...count.entries()].sort((a, b) => b[1] - a[1])[0][0].split(',').map(Number), on = new Uint8Array(w * h);
  for (let i = 0; i < w * h; i++) on[i] = Math.abs(px[4 * i] - ground[0]) + Math.abs(px[4 * i + 1] - ground[1]) + Math.abs(px[4 * i + 2] - ground[2]) > 9 ? 1 : 0;
  const out = [];
  for (let i = 0; i < w * h; i++) {
    if (!on[i]) continue;
    const list = [i]; on[i] = 0; let sx = 0, sy = 0, lx = w, hx = 0, ly = h, hy = 0;
    while (list.length) {
      const j = list.pop(), x = j % w, y = (j - x) / w;
      sx += x; sy += y; lx = Math.min(lx, x); hx = Math.max(hx, x); ly = Math.min(ly, y); hy = Math.max(hy, y);
      [[1, 0], [-1, 0], [0, 1], [0, -1]].forEach(([u, v]) => { const xx = x + u, yy = y + v, n = yy * w + xx; if (xx >= 0 && yy >= 0 && xx < w && yy < h && on[n]) { on[n] = 0; list.push(n); } });
    }
    out.push({ x: box[0] + (lx + hx) / 2 / d, y: box[1] + (ly + hy) / 2 / d, w: (hx - lx + 1) / d, h: (hy - ly + 1) / d, edge: lx === 0 || ly === 0 || hx === w - 1 || hy === h - 1 });
  }
  return out.filter((o) => !o.edge);
}

async function marks(browser, file) {
  const { page, errors } = await open(browser, file, WIDE);
  const first = await page.evaluate(() => window.systemapCanvas.viewState());
  const out = { errors, layers: [], zooms: [], grid: [] };
  for (const tab of first.tabs) {
    await page.evaluate((id) => window.systemapCanvas.setLayer(id), tab.id);
    await page.waitForTimeout(700);
    out.layers.push(await page.evaluate(`(() => {
      const a = window.systemapCanvas, d = a.drawn(), colorsAt = ${colorsAt.toString()};
      const ends = d.marks.filter((m) => m.t === 'ends');
      const heads = ends.map((e) => { const l = Math.hypot(e.tip[0] - e.from[0], e.tip[1] - e.from[1]) || 1; return [e.tip[0] - (e.tip[0] - e.from[0]) / l * e.s * 0.4, e.tip[1] - (e.tip[1] - e.from[1]) / l * e.s * 0.4]; });
      return { view: a.viewState(), lines: a.lines(''), drawn: d, dots: colorsAt(ends.map((e) => e.dot)), heads: colorsAt(heads),
        ground: colorsAt([[innerWidth - 4, innerHeight - 4]])[0] };
    })()`));
  }
  // The labels of the first layer at three zooms.
  await page.evaluate(() => window.systemapCanvas.setLayer(document.querySelector('[role="tab"]').getAttribute('data-layer')));
  await page.waitForTimeout(700);
  for (const f of [1, 1.3, 1.7]) {
    await page.evaluate((f) => { const a = window.systemapCanvas, c = a.fit(''), k = c.k * f, cx = c.x + innerWidth / 2 / c.k, cy = c.y + innerHeight / 2 / c.k; a.view({ x: cx - innerWidth / 2 / k, y: cy - innerHeight / 2 / k, k }); }, f);
    await page.waitForTimeout(600);
    out.zooms.push(await page.evaluate(() => ({ k: window.systemapCanvas.camera().k, labels: window.systemapCanvas.lines('').labels, texts: window.systemapCanvas.texts() })));
  }
  await page.close();
  // The dot grid, far from the map, at a device pixel ratio of 2.
  const second = await open(browser, file, { ...WIDE, deviceScaleFactor: 2 });
  for (const k of [0.45, 1, 1.6, 3.3]) {
    await second.page.evaluate((k) => window.systemapCanvas.view({ x: -1e5 / k, y: -1e5 / k, k }), k);
    await second.page.waitForTimeout(600);
    out.grid.push({ k, dots: await second.page.evaluate(`(${dotsIn.toString()})([400, 300, 300, 200])`) });
  }
  out.errors = out.errors.concat(second.errors);
  await second.page.close();
  return out;
}

function worldAt(p) { const c = window.systemapCanvas.camera(); return [c.x + p[0] / c.k, c.y + p[1] / c.k]; }

async function input(browser, file) {
  const { page, errors } = await open(browser, file, WIDE);
  const at = [700, 500], out = { errors };
  await page.mouse.move(at[0], at[1]);
  const before = await page.evaluate(worldAt, at), k0 = await page.evaluate(() => window.systemapCanvas.camera().k);
  await page.mouse.wheel(0, -240);
  await page.waitForTimeout(400);
  out.wheel = { before, after: await page.evaluate(worldAt, at), k0, k1: await page.evaluate(() => window.systemapCanvas.camera().k) };
  const c0 = await page.evaluate(() => window.systemapCanvas.camera());
  await page.mouse.move(600, 450);
  await page.mouse.down();
  await page.mouse.move(720, 530, { steps: 8 });
  await page.mouse.up();
  await page.waitForTimeout(400);
  out.drag = { from: c0, to: await page.evaluate(() => window.systemapCanvas.camera()), move: [120, 80] };
  await page.close();
  const phonePage = await open(browser, file, PHONE), p = phonePage.page, cdp = await p.context().newCDPSession(p);
  const mid = [195, 500], pinch0 = await p.evaluate(worldAt, mid), pk0 = await p.evaluate(() => window.systemapCanvas.camera().k);
  const touch = (type, d) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints: type === 'touchEnd' ? [] : [{ x: mid[0] - d, y: mid[1], id: 1 }, { x: mid[0] + d, y: mid[1], id: 2 }] });
  await touch('touchStart', 40);
  for (let d = 45; d <= 80; d += 5) { await touch('touchMove', d); await p.waitForTimeout(20); }
  await touch('touchEnd', 80);
  await p.waitForTimeout(400);
  out.pinch = { before: pinch0, after: await p.evaluate(worldAt, mid), k0: pk0, k1: await p.evaluate(() => window.systemapCanvas.camera().k), ratio: 2 };
  out.errors = out.errors.concat(phonePage.errors);
  await p.close();
  return out;
}

async function motion(browser, file, map) {
  const out = {};
  for (const reducedMotion of ['reduce', 'no-preference']) {
    const { page, errors } = await open(browser, file, { ...WIDE, reducedMotion });
    const box = await page.evaluate((id) => window.systemapCanvas.box('', id), map);
    await page.mouse.dblclick(box[0] + 20, box[1] + box[3] / 2);
    await page.waitForTimeout(60);
    const soon = await page.evaluate(() => window.systemapCanvas.camera());
    await page.waitForTimeout(2000);
    const late = await page.evaluate(() => window.systemapCanvas.camera());
    await page.keyboard.press('Escape');
    await page.waitForTimeout(2000);
    const tabs = await page.evaluate(() => window.systemapCanvas.viewState().tabs.filter((t) => !t.on).map((t) => t.id));
    // The smallest alpha of the lines in the frames of 400 ms after a change of the layer.
    const swap = await page.evaluate((id) => new Promise((done) => {
      const a = window.systemapCanvas, t0 = performance.now();
      let low = 1;
      a.setLayer(id);
      (function step() { low = Math.min(low, a.stats().swap); if (performance.now() - t0 < 400) requestAnimationFrame(step); else done(low); })();
    }), tabs[tabs.length - 1]);
    out[reducedMotion] = { errors, soon, late, swap };
    await page.close();
  }
  return out;
}

// The frame and the labels at rest of the map id in each layer tab of the page.
async function eachLayer(page, id, state) {
  const out = [], tabs = (await page.evaluate(() => window.systemapCanvas.viewState())).tabs;
  for (const tab of tabs) {
    await page.evaluate((t) => window.systemapCanvas.setLayer(t), tab.id);
    await page.waitForTimeout(700);
    out.push(await page.evaluate(([i, s]) => ({ state: s, layer: window.systemapCanvas.viewState().layer,
      frame: window.systemapCanvas.frame(i), labels: window.systemapCanvas.lines(i).labels, size: [innerWidth, innerHeight] }), [id, state]));
  }
  return out;
}

async function inside(browser, file, map) {
  const id = map || '', hash = id ? '#' + id : '';
  const wide = await open(browser, file, WIDE, hash);
  const out = { errors: wide.errors, chain: await wide.page.evaluate(() => window.systemapCanvas.chain()), runs: [] };
  out.runs.push(...await eachLayer(wide.page, id, 'fit'));
  await wide.page.close();
  const phone = await open(browser, file, PHONE, hash);
  out.runs.push(...await eachLayer(phone.page, id, 'open'));
  await phone.page.click('#atlas-zf');
  await phone.page.waitForTimeout(1500);
  out.runs.push(...await eachLayer(phone.page, id, 'phoneFit'));
  out.errors = out.errors.concat(phone.errors);
  await phone.page.close();
  return out;
}

async function nestedPage(browser, file, map) {
  const hash = '#' + map, wide = await open(browser, file, WIDE, hash), page = wide.page;
  const out = await page.evaluate((id) => ({ chain: window.systemapCanvas.chain(), maps: window.systemapCanvas.maps(),
    cards: window.systemapCanvas.boxes(id), top: window.systemapCanvas.boxes(''), drawn: window.systemapCanvas.drawn() }), map);
  out.errors = wide.errors;
  out.heads = [];
  for (const tab of (await page.evaluate(() => window.systemapCanvas.viewState())).tabs) {
    await page.evaluate((t) => window.systemapCanvas.setLayer(t), tab.id);
    await page.waitForTimeout(700);
    out.heads.push(await page.evaluate(() => window.systemapCanvas.viewState()));
  }
  await page.close();
  out.goes = [];
  for (const card of out.cards.filter((c) => c.k === 'actor')) {
    const one = await open(browser, file, WIDE, hash), b = card.b;
    await one.page.mouse.click(b[0] + b[2] / 2, b[1] + b[3] / 2);
    await one.page.waitForTimeout(2500);
    out.goes.push(await one.page.evaluate((id) => ({ id, chain: window.systemapCanvas.chain(), current: window.systemapCanvas.current(),
      sel: window.systemapCanvas.side().sel, hash: location.hash }), card.id));
    out.errors = out.errors.concat(one.errors);
    await one.page.close();
  }
  return out;
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
  const run = { '--rest': rest, '--phone': phone, '--nested': nested, '--marks': marks, '--input': input, '--motion': motion, '--axe': axe, '--inside': inside, '--page': nestedPage }[mode];
  const out = await run(browser, file, map);
  await browser.close();
  process.stdout.write(JSON.stringify(out) + '\n');
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
