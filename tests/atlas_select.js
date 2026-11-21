// The browser part of tests/test_atlas_select_browser.py: the camera after a selection on
// the atlas page at 1440 x 900.
//
//     node atlas_select.js PAGE.html VISIBLE UNDER FAR
//
// The script zooms in, puts the card VISIBLE in the left part of the screen and clicks it,
// then presses Esc. It puts the card UNDER where the details would cover it and clicks it.
// It moves the camera away from the card FAR and selects FAR with Find. The output is one
// JSON object with the camera before and after each step, and the screen boxes of the cards.
'use strict';
const { chromium } = require('playwright');

const W = 1440, H = 900;
const cam = (page) => page.evaluate(() => window.systemapCanvas.camera());
const box = (page, id) => page.evaluate((c) => window.systemapCanvas.box('', c), id);
const sel = (page) => page.evaluate(() => window.systemapCanvas.side().sel);
const boxes = (page) => page.evaluate(() => window.systemapCanvas.boxes(''));

// Put the middle of card `id` at the screen point x, y with the zoom k.
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

(async () => {
  const [file, visible, under, far] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + file);
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await page.waitForTimeout(800);
  const k = (await cam(page)).k * 1.5, out = { errors };

  await place(page, visible, 300, 500, k);
  out.visible = { before: await cam(page), box: await box(page, visible) };
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
  console.log(JSON.stringify(out));
  await browser.close();
})();
