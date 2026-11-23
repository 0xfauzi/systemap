// Drives a canvas page (systemap.canvas_page) in the Chromium of Playwright for the boards
// (page_canvas_board): the States view and the sequence as a diagram. Prints one JSON
// object. tests/test_canvas_board_browser.py reads it.
//
//     node tests/canvas_board.js --states PAGE.html
//     node tests/canvas_board.js --diagram PAGE.html
//     node tests/canvas_board.js --none PAGE.html
'use strict';
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const DESK = { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1, reducedMotion: 'reduce' };

async function open(browser, file) {
  const context = await browser.newContext(DESK);
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + path.resolve(file));
  await page.waitForFunction(() => window.systemapCanvas && document.fonts.status === 'loaded');
  await page.waitForTimeout(400);
  return { page, errors };
}
const top = (page) => page.evaluate(() => JSON.parse(document.getElementById('canvas-data').textContent).maps[0]);
const read = (page) => page.evaluate(() => {
  const S = window.systemapCanvas, v = S.viewState(), body = document.getElementById('cdet-body');
  return { mode: v.mode, layer: v.layer, board: S.board(), caption: S.caption(), camera: S.camera(), seq: S.seqState(),
    texts: S.texts().filter((t) => t.alpha > 0.5).map((t) => t.s),
    hits: S.hits().filter((h) => h.kind === 'board-item').length,
    panel: body ? { title: (body.querySelector('h3') || {}).textContent || '', buttons: Array.from(body.querySelectorAll('button')).map((b) => b.textContent) } : null,
    said: document.getElementById('canvas-said').textContent };
});
async function axeRun(page) {
  let source;
  try { source = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8'); } catch (e) { return null; }
  await page.evaluate(source);
  return page.evaluate(async () => {
    const r = await window.axe.run(document, { resultTypes: ['violations'] });
    return { version: window.axe.version, violations: r.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical').map((v) => v.id) };
  });
}

async function runStates(browser, file) {
  const { page, errors } = await open(browser, file);
  const map = await top(page), out = { machines: map.sm, flows: map.flows.map((f) => [f.s, f.t, f.a]), sq: (map.sq || []).map((q) => q.id), errors };
  out.button = await page.evaluate(() => !document.querySelector('[data-view="states"]').hidden);
  await page.getByRole('button', { name: 'States', exact: true }).click();
  await page.waitForTimeout(300);
  out.open = await read(page);
  // The wheel does not move the map under a board.
  await page.mouse.move(600, 500); await page.mouse.wheel(0, -400); await page.waitForTimeout(200);
  out.wheel = (await read(page)).camera;
  await page.locator('#canvas').focus(); await page.keyboard.press('d'); await page.waitForTimeout(300);
  out.list = await read(page);
  await page.locator('#cdet-body [data-sm="tr"][data-i="0"]').click(); await page.waitForTimeout(300);
  out.transition = await read(page);
  out.axe = await axeRun(page);
  await page.locator('#cdet-body [data-sm="flow"]').click(); await page.waitForTimeout(300);
  out.flow = await read(page);
  await page.getByRole('button', { name: 'States', exact: true }).click(); await page.waitForTimeout(300);
  await page.locator('#cdet-body [data-sm="seq"]').click(); await page.waitForTimeout(300);
  out.sequence = await read(page);
  // The second machine, with the select of the bar.
  await page.getByRole('button', { name: 'States', exact: true }).click(); await page.waitForTimeout(200);
  await page.locator('#cst-pick').selectOption({ index: 1 }); await page.waitForTimeout(300);
  out.second = await read(page);
  return out;
}

async function runDiagram(browser, file) {
  const { page, errors } = await open(browser, file);
  const map = await top(page), out = { sq: map.sq, flows: map.flows.map((f) => [f.s, f.t, f.a]), errors };
  await page.getByRole('button', { name: 'Sequences', exact: true }).click(); await page.waitForTimeout(300);
  out.map = await read(page);
  await page.getByRole('button', { name: 'As a diagram', exact: true }).click(); await page.waitForTimeout(300);
  out.diagram = await read(page);
  out.pressed = await page.evaluate(() => ['cseq-onmap', 'cseq-diagram'].map((id) => document.getElementById(id).getAttribute('aria-pressed')));
  await page.getByRole('button', { name: 'Start at step 1', exact: true }).click(); await page.waitForTimeout(300);
  await page.getByRole('button', { name: 'Next', exact: true }).click(); await page.waitForTimeout(300);
  out.step = await read(page);
  out.axe = await axeRun(page);
  await page.getByRole('button', { name: 'On the map', exact: true }).click(); await page.waitForTimeout(300);
  out.back = await read(page);
  return out;
}

async function runNone(browser, file) {
  const { page, errors } = await open(browser, file);
  return { errors, hidden: await page.evaluate(() => document.querySelector('[data-view="states"]').hidden), state: await read(page) };
}

(async () => {
  const [mode, file] = process.argv.slice(2);
  const runs = { '--states': runStates, '--diagram': runDiagram, '--none': runNone };
  if (!runs[mode] || !file) { console.error('usage: canvas_board.js --states|--diagram|--none PAGE.html'); process.exit(2); }
  const browser = await chromium.launch();
  try { console.log(JSON.stringify(await runs[mode](browser, file))); } finally { await browser.close(); }
})().catch((e) => { console.error(e); process.exit(1); });
