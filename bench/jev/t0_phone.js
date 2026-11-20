// The browser part of t0_phone.py (C3): the opening view of a map on a phone of 390 x 844.
//
//     node t0_phone.js PAGE.html RULE MAPS [CARD]
//
// The page must be a T0 page with the rule edit of t0_phone.py: the phone branch of
// `mapFit` calls window.__T0RULE when it is set. RULE is today, height, name11 or cols2.
// MAPS is a list of map ids with commas ("top" is the top map). For each map, in a new load
// with the hash of the map: the zoom, the sizes of the card names, the empty rows of the map
// area, the left column, and the line of each neighbour (`up` marks, Z1 of
// tests/test_atlas_inside_browser.py). With CARD, the driver also does acceptance 9 of
// tests/test_atlas_point_browser.py on the top map: a tap on CARD, the sheet and the box.
'use strict';
const { chromium } = require('playwright');

const PHONE = { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, hasTouch: true, isMobile: true };

// The opening rules. `avail` is the height of the map area of the fit, in screen px.
function rules(name) {
  const cols = (m) => {
    const xs = m.cards.map((c) => [c.b[0], c.b[0] + c.b[2]]).sort((a, b) => a[0] - b[0]), out = [];
    xs.forEach((x) => { const l = out[out.length - 1]; if (l && x[0] < l[1]) l[1] = Math.max(l[1], x[1]); else out.push([x[0], x[1]]); });
    return out;
  };
  window.__T0COLS = cols;
  if (name === 'height') window.__T0RULE = (m, b, avail) => avail / b[3];
  if (name === 'name11') window.__T0RULE = (m) => 11 / 13.5 / m.T.s;
  if (name === 'cols2') window.__T0RULE = (m, b, avail, W) => { const c = cols(m), r = c[Math.min(1, c.length - 1)][1]; return (W - 28) / (r * m.T.s); };
}

function measure(id) {
  const T = window.__T0, s = window.systemapCanvas, m = T.MAPS[id], v = T.view(m), W = innerWidth, H = innerHeight;
  const ask = document.getElementById('atlas-ask').getBoundingClientRect().bottom;
  const d = s.drawn(), names = [];
  const ids = new Set(m.cards.map((c) => c.id));
  d.texts.forEach((t) => { if (t.weight === 600 && (ids.has(t.s) || [...ids].some((i) => t.s.endsWith('…') && i.startsWith(t.s.slice(0, -1))))) names.push(t.size); });
  const cards = s.boxes(id), L = s.lines(id), rows = new Uint8Array(H);
  const mark = (y0, y1) => { for (let y = Math.max(0, Math.floor(y0)); y < Math.min(H, Math.ceil(y1)); y++) rows[y] = 1; };
  cards.forEach((c) => { if (c.b[0] < W && c.b[0] + c.b[2] > 0) mark(c.b[1], c.b[1] + c.b[3]); });
  L.lanes.forEach((e) => {
    for (let i = 0; i + 1 < e.q.length; i++) {
      const x0 = v.ox + v.a * e.q[i][0], x1 = v.ox + v.a * e.q[i + 1][0], y0 = v.oy + v.a * e.q[i][1], y1 = v.oy + v.a * e.q[i + 1][1];
      if (Math.max(x0, x1) < 0 || Math.min(x0, x1) > W) continue;
      mark(Math.min(y0, y1) - 1, Math.max(y0, y1) + 1);
    }
  });
  const top = Math.ceil(ask);
  let empty = 0, run = 0, best = 0, tail = 0;
  for (let y = top; y < H; y++) { if (!rows[y]) { empty++; run++; best = Math.max(best, run); } else run = 0; }
  tail = run;
  const col = window.__T0COLS(m)[0], left = m.cards.filter((c) => c.b[0] < col[1] && c.b[0] + c.b[2] > col[0]);
  const seen = left.map((c) => { const b = s.box(id, c.id); return b[0] >= 0 && b[0] + b[2] <= W && b[1] >= ask && b[1] + b[3] <= H; });
  const actors = new Set(cards.filter((c) => c.k === 'actor').map((c) => c.id)), byId = Object.fromEntries(cards.map((c) => [c.id, c.b]));
  const ups = d.marks.filter((x) => x.t === 'up');
  const inBox = (u, b) => u[0] >= b[0] && u[1] >= b[1] && u[2] <= b[0] + b[2] && u[3] <= b[1] + b[3];
  const z1 = { actors: actors.size, ups: ups.length, drawn: ups.filter((u) => u.box).length,
    inCard: ups.filter((u) => u.box && inBox(u.box, byId[u.id])).length, alpha1: ups.filter((u) => u.alpha === 1).length,
    sizes: [...new Set(ups.map((u) => u.size))] };
  z1.pass = actors.size > 0 && ups.length === actors.size && new Set(ups.map((u) => u.id)).size === actors.size && z1.drawn === actors.size && z1.inCard === actors.size && z1.alpha1 === actors.size;
  const fr = s.frame(id);
  return { current: s.current(), zoom: v.a, k: s.camera().k, names: names.length ? [Math.min(...names), Math.max(...names)] : null,
    area: H - top, empty, emptyShare: empty / (H - top), longest: best, bottomRun: tail, left: { n: left.length, seen: seen.filter(Boolean).length, ids: left.map((c) => c.id) },
    frame: fr, frameSeen: [Math.max(0, Math.min(W, fr[0] + fr[2]) - Math.max(0, fr[0])) / fr[2], Math.max(0, Math.min(H, fr[1] + fr[3]) - Math.max(ask, fr[1])) / fr[3]], z1, scroll: document.documentElement.scrollWidth };
}

async function open(browser, file, rule, hash) {
  const context = await browser.newContext(PHONE);
  await context.addInitScript(rules, rule);
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + file + hash);
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await page.waitForTimeout(900);
  return { context, page, errors };
}

(async () => {
  const [file, rule, maps, card] = process.argv.slice(2);
  const browser = await chromium.launch();
  const out = { errors: [], maps: [] };
  for (const name of maps.split(',')) {
    const id = name === 'top' ? '' : name;
    const o = await open(browser, file, rule, id ? '#' + id : '');
    const r = await o.page.evaluate(measure, id);
    r.id = name;
    if (card && !id) {
      // Acceptance 9 of tests/test_atlas_point_browser.py.
      const b = await o.page.evaluate((c) => window.systemapCanvas.box('', c), card);
      const ask = await o.page.evaluate(() => document.getElementById('atlas-ask').getBoundingClientRect().bottom);
      const at = [b[0] + b[2] / 2, b[1] + b[3] / 2];
      const tappable = at[0] > 0 && at[0] < 390 && at[1] > ask && at[1] < 844;
      r.a9 = { card, box: b, tappable };
      if (tappable) {
        await o.page.touchscreen.tap(at[0], at[1]);
        await o.page.waitForTimeout(1600);
        const st = await o.page.evaluate((c) => ({ side: window.systemapCanvas.side(), box: window.systemapCanvas.box('', c),
          head: document.getElementById('atlas-ask').getBoundingClientRect().bottom, scroll: document.documentElement.scrollWidth }), card);
        r.a9.pass = !!st.side.sel && st.side.sel.id === card && st.side.box[0] === 0 && st.side.box[2] === 390 && st.side.top > 844 / 3 &&
          st.box[1] >= st.head && st.box[1] + st.box[3] <= st.side.top && st.scroll === 390;
        r.a9.after = st;
      } else r.a9.pass = false;
    }
    out.maps.push(r);
    out.errors.push(...o.errors);
    await o.context.close();
  }
  console.log(JSON.stringify(out));
  await browser.close();
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
