// The browser part of tests/test_atlas_select_browser.py: the camera after a selection on
// the atlas page at 1440 x 900.
//
//     node atlas_select.js camera PAGE.html VISIBLE UNDER FAR
//     node atlas_select.js partner PAGE.html CARD PARTNER
//     node atlas_select.js resize PAGE.html CARD
//     node atlas_select.js nested PAGE.html MAP
//
// camera: in the layer All, the script zooms in, puts the card VISIBLE with its right edge
// 10 px at the left of the details and clicks it, then presses Esc. It puts the card UNDER where the details would cover it and
// clicks it. It moves the camera away from the card FAR and selects FAR with Find.
// partner: in the layer All, the script puts PARTNER, a card at the other end of a flow of CARD, with its right
// edge at 1430 px, and clicks CARD.
// resize: at the fit, the script clicks CARD, changes the window to 1000 px wide, and back
// to 1440 px.
// nested: the script loads the page with the hash MAP, clicks the first part, and then
// clicks each other part that is fully on the screen and not under the details. Then it
// moves the camera so that the last part that is not selected is at the top right of the free part of the
// screen, where the locator goes while the details are open, and clicks that part.
// The output is one JSON object with the camera and the screen boxes of the cards.
'use strict';
const { chromium } = require('playwright');

const W = 1440, H = 900;
const cam = (page) => page.evaluate(() => window.systemapCanvas.camera());
const box = (page, id) => page.evaluate((c) => window.systemapCanvas.box('', c), id);
const sel = (page) => page.evaluate(() => window.systemapCanvas.side().sel);
const boxes = (page) => page.evaluate(() => window.systemapCanvas.boxes(''));

// Put the middle of card `id` at the screen point x, y with the scale k.
async function place(page, id, x, y, k) {
  const c = await cam(page), b = await box(page, id);
  const wx = c.x + (b[0] + b[2] / 2) / c.k, wy = c.y + (b[1] + b[3] / 2) / c.k;
  await page.evaluate((v) => window.systemapCanvas.view(v), { x: wx - x / k, y: wy - y / k, k });
  await page.waitForTimeout(300);
}
async function click(page, id) {
  const b = await box(page, id);
  await page.mouse.click(b[0] + b[2] / 2, b[1] + b[3] / 2);
  await page.waitForTimeout(1500);
}

async function camera(page, out, visible, under, far) {
  const k = (await cam(page)).k * 1.5;
  await page.evaluate(() => window.systemapCanvas.setLayer('all'));
  await page.waitForTimeout(400);

  // VISIBLE ends 10 px at the left of the details, thus a card at its right is under them.
  await place(page, visible, 300, 500, k);
  const v = await box(page, visible);
  await place(page, visible, W - 16 - 380 - 10 - v[2] / 2, 500, k);
  out.visible = { before: await cam(page), box: await box(page, visible), boxes: await boxes(page) };
  await click(page, visible);
  out.visible.after = await cam(page);
  out.visible.sel = await sel(page);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(1200);
  out.visible.closed = await cam(page);
  out.visible.closedSel = await sel(page);

  await place(page, under, 0, 500, k);
  const b = await box(page, under);
  await place(page, under, W - 100 - b[2] / 2, 500, k);
  out.under = { before: await cam(page), box: await box(page, under), boxes: await boxes(page) };
  await click(page, under);
  out.under.after = await cam(page);
  out.under.boxAfter = await box(page, under);
  out.under.boxesAfter = await boxes(page);
  out.under.sel = await sel(page);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(800);

  await place(page, far, -2000, -2000, k);
  out.far = { before: await box(page, far) };
  await page.focus('#canvas');
  await page.keyboard.press('Control+k');
  await page.keyboard.type(far);
  await page.waitForTimeout(200);
  await page.keyboard.press('Enter');
  await page.waitForTimeout(2500);
  out.far.after = await box(page, far);
  out.far.sel = await sel(page);
}

async function partner(page, out, card, other) {
  const k = (await cam(page)).k * 1.5;
  await page.evaluate(() => window.systemapCanvas.setLayer('all'));
  await page.waitForTimeout(400);
  await place(page, other, 0, 500, k);
  const b = await box(page, other);
  await place(page, other, 1430 - b[2] / 2, 500, k);
  out.before = { cam: await cam(page), card: await box(page, card), other: await box(page, other) };
  await click(page, card);
  out.after = { cam: await cam(page), card: await box(page, card), other: await box(page, other), sel: await sel(page) };
}

async function resize(page, out, card) {
  out.fit = await page.evaluate(() => window.systemapCanvas.fit(''));
  await click(page, card);
  out.selected = { cam: await cam(page), sel: await sel(page) };
  await page.setViewportSize({ width: 1000, height: H });
  await page.waitForTimeout(1200);
  await page.setViewportSize({ width: W, height: H });
  await page.waitForTimeout(1200);
  out.back = { cam: await cam(page), fit: await page.evaluate(() => window.systemapCanvas.fit('')),
    frame: await page.evaluate(() => window.systemapCanvas.frame('')), sel: await sel(page) };
}

async function nested(page, out, map) {
  const parts = async () => (await page.evaluate((m) => window.systemapCanvas.boxes(m), map)).filter((c) => c.k !== 'actor');
  const first = (await parts())[0];
  await page.mouse.click(first.b[0] + first.b[2] / 2, first.b[1] + first.b[3] / 2);
  await page.waitForTimeout(1500);
  out.clicks = [];
  const seen = (b) => b[0] >= 0 && b[1] >= 48 && b[0] + b[2] <= W - 380 && b[1] + b[3] <= H;
  for (const c of (await parts()).slice(1)) {
    const now = (await parts()).find((x) => x.id === c.id);
    if (!seen(now.b)) continue;
    await page.mouse.click(now.b[0] + now.b[2] / 2, now.b[1] + now.b[3] / 2);
    await page.waitForTimeout(1500);
    out.clicks.push({ id: c.id, current: await page.evaluate(() => window.systemapCanvas.current()), sel: await sel(page),
      loc: await page.evaluate(() => window.systemapCanvas.inside().loc), boxes: (await parts()).map((x) => x.b) });
  }  // A part where the locator goes while the details are open: at the top right of the free
  // part of the screen, under the bar of the nested map.
  const now = await sel(page), last = (await parts()).filter((x) => !now || x.id !== now.id).pop(), k = (await cam(page)).k;
  const c = await cam(page), b = last.b, wx = c.x + (b[0] + b[2] / 2) / c.k, wy = c.y + (b[1] + b[3] / 2) / c.k;
  await page.evaluate((v) => window.systemapCanvas.view(v), { x: wx - (W - 16 - 380 - 70) / k, y: wy - 165 / k, k });
  await page.waitForTimeout(400);
  const at = (await parts()).find((x) => x.id === last.id).b;
  await page.mouse.click(at[0] + at[2] / 2, at[1] + at[3] / 2);
  await page.waitForTimeout(1500);
  out.clicks.push({ id: last.id, current: await page.evaluate(() => window.systemapCanvas.current()), sel: await sel(page),
    loc: await page.evaluate(() => window.systemapCanvas.inside().loc), boxes: (await parts()).map((x) => x.b), box: at });
}

(async () => {
  const [mode, file, ...rest] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  const errors = [], out = { errors };
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + file + (mode === 'nested' ? '#' + rest[0] : ''));
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await page.waitForTimeout(mode === 'nested' ? 2500 : 800);
  await { camera, partner, resize, nested }[mode](page, out, ...rest);
  console.log(JSON.stringify(out));
  await browser.close();
})();
