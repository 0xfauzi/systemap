// The browser part of t0_states.py (C4): the board of the States view at 1440 x 900, at
// each largest scale of a list.
//
//     node t0_states.js PAGE.html CAPS
//
// The page must be a T0 page (t0_common.py). CAPS is a list of numbers with commas; "inf" is
// no cap. For each machine of the top map and each cap, the driver sets SM_MAX to the cap,
// draws the board again (`smDraw`) and reads: the scale, the free part of the screen, the
// two fits (width and height) of `smDraw`, the screen box of the board, and for each
// transition the distance of its label box to its line and of the label centre to its line.
'use strict';
const { chromium } = require('playwright');

function board(cap) {
  const T = window.__T0, SM = T.SM;
  T.setSmMax(cap);
  T.smDraw();
  const css = (n) => parseFloat(document.body.style.getPropertyValue(n));
  const aw = css('--sb-w'), ah = css('--sb-h');
  const world = document.getElementById('atlas-sworld') || document.querySelector('#atlas-sboard svg g');
  const bb = world.getBBox(), r = world.getBoundingClientRect();
  const kW = (aw - 1) / (bb.width + 80), kH = (ah - 1) / (bb.height + 60);
  const st = window.systemapCanvas.states();
  const segD = (x, y, q) => {
    let best = Infinity;
    for (let i = 0; i + 1 < q.length; i++) {
      const [x0, y0] = q[i], [x1, y1] = q[i + 1], dx = x1 - x0, dy = y1 - y0, l = dx * dx + dy * dy;
      const t = l ? Math.max(0, Math.min(1, ((x - x0) * dx + (y - y0) * dy) / l)) : 0;
      best = Math.min(best, Math.hypot(x - x0 - t * dx, y - y0 - t * dy));
    }
    return best;
  };
  const labels = st.items.filter((o) => o.kind === 't').map((o) => {
    const b = o.text.box, cx = (b.left + b.right) / 2, cy = (b.top + b.bottom) / 2;
    // The distance of the box to the line: the smallest distance of a point of the line to
    // the box (0 when a point of the line is in the box).
    let box = Infinity;
    for (let i = 0; i + 1 < o.points.length; i++) {
      for (let n = 0; n <= 10; n++) {
        const x = o.points[i][0] + (o.points[i + 1][0] - o.points[i][0]) * n / 10, y = o.points[i][1] + (o.points[i + 1][1] - o.points[i][1]) * n / 10;
        box = Math.min(box, Math.hypot(Math.max(0, b.left - x, x - b.right), Math.max(0, b.top - y, y - b.bottom)));
      }
    }
    return { l: o.l, bend: o.bend, box, centre: segD(cx, cy, o.points), px: o.text.px };
  });
  return { cap, scale: SM.scale, turn: !!SM.turn, aw, ah, kW, kH, w: r.width, h: r.height, labels };
}

(async () => {
  const [file, caps] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + file);
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await page.waitForTimeout(500);
  await page.click('#atlas-head [data-mode="states"]');
  await page.waitForTimeout(600);
  const n = await page.evaluate(() => window.__T0.MAPS[''].sm.length);
  const out = { errors, machines: [] };
  for (let k = 0; k < n; k++) {
    await page.evaluate((k) => window.systemapCanvas.machine('', k), k);
    await page.waitForTimeout(400);
    const one = { k, n: await page.evaluate((k) => window.__T0.MAPS[''].sm[k].n, k), runs: [] };
    for (const c of caps.split(',')) one.runs.push(await page.evaluate(board, c === 'inf' ? Infinity : +c));
    await page.evaluate(() => window.__T0.setSmMax(1.25));
    out.machines.push(one);
  }
  out.errors = errors;
  console.log(JSON.stringify(out));
  await browser.close();
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
