// The browser part of tests/test_atlas_final_browser.py: the faults of the final review of
// the atlas page.
//
//     node atlas_final.js PAGE.html
//
// PAGE is the atlas page of the map of this repository, with the nested map Page. The
// driver gives one JSON object:
// - dbl: for reduced motion and for no reduced motion, at 1440 x 900, the current map and
//   the hash after a mouse double-click on the middle of the card Page.
// - note: the class of the help note after a selection with Find and Enter, and after a
//   mouse click on a card.
// - say: with the details of Page open, and the pointer on its first flow row: the box of
//   the reading line, the box of the details, the box of the zoom control, the visibility
//   of the key, and the line height of the reading line.
// - board: for each sequence of the top map, at its first step in the diagram form: the
//   box of each label of a row, and the boxes of the plates and the lifelines.
// - page: the nested map Page at 1440 x 900 at the fit: the frames of the containers with a
//   surface, the region tints, the labels at rest, and the region numbers with their boxes.
// - phone: the top map at 390 x 844: the display and the text of the counts of the headline.
// - key: the text of the key at the top map.
// - head: the words under the name in the details of Placer, the description and its line
//   clamp.
// `errors` has the script errors of each page.
'use strict';
const { chromium } = require('playwright');

const WIDE = { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 };
const PHONE = { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, hasTouch: true, isMobile: true };

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

async function dbl(browser, file, reduced) {
  const { page, errors } = await open(browser, file, { ...WIDE, reducedMotion: reduced ? 'reduce' : 'no-preference' });
  const b = await page.evaluate(() => window.systemapCanvas.box('', 'Page'));
  await page.mouse.dblclick(b[0] + b[2] / 2, b[1] + b[3] / 2);
  await page.waitForTimeout(1200);
  const out = await page.evaluate(() => ({ current: window.systemapCanvas.current(), hash: location.hash, selected: String(window.getSelection()) }));
  await page.close();
  return { ...out, errors };
}

const noteClass = (page) => page.evaluate(() => document.getElementById('atlas-note').className);

async function note(browser, file) {
  const out = {};
  {
    const { page, errors } = await open(browser, file, WIDE);
    await page.focus('#canvas');
    await page.keyboard.press('Control+k');
    await page.keyboard.type('Placer');
    await page.waitForTimeout(150);
    await page.keyboard.press('Enter');
    await page.waitForTimeout(900);
    out.find = { cls: await noteClass(page), sel: await page.evaluate(() => window.systemapCanvas.side().sel), errors };
    await page.close();
  }
  {
    const { page, errors } = await open(browser, file, WIDE);
    const b = await page.evaluate(() => window.systemapCanvas.box('', 'Check'));
    await page.mouse.click(b[0] + b[2] / 2, b[1] + b[3] / 2);
    await page.waitForTimeout(900);
    out.click = { cls: await noteClass(page), sel: await page.evaluate(() => window.systemapCanvas.side().sel), errors };
    await page.close();
  }
  return out;
}

async function say(browser, file) {
  const { page, errors } = await open(browser, file, WIDE);
  await page.evaluate(() => window.systemapCanvas.select('', 'Page'));
  await page.waitForTimeout(900);
  await page.hover('#atlas-side-b .row');
  await page.waitForTimeout(400);
  const out = await page.evaluate(() => {
    const box = (e) => e.getBoundingClientRect().toJSON(), s = document.getElementById('atlas-say');
    return { say: box(s), on: s.classList.contains('on'), text: s.textContent, line: parseFloat(getComputedStyle(s.querySelector('b')).lineHeight),
      side: box(document.getElementById('atlas-side')), zoom: box(document.querySelector('.zoom')),
      key: getComputedStyle(document.getElementById('atlas-key')).visibility };
  });
  await page.close();
  return { ...out, errors };
}

async function board(browser, file) {
  const { page, errors } = await open(browser, file, WIDE);
  const n = await page.evaluate(() => { window.systemapCanvas.mode('seq'); return window.systemapCanvas.seq().view.rail.length; });
  const out = [];
  for (let k = 0; k < n; k++) {
    const ok = await page.evaluate((k) => window.systemapCanvas.choose('', k), k);
    if (!ok) continue;
    await page.evaluate(() => { window.systemapCanvas.form('diagram'); window.systemapCanvas.step(0); });
    await page.waitForTimeout(120);
    out.push(await page.evaluate(() => {
      const box = (e) => e.getBoundingClientRect().toJSON(), w = document.getElementById('atlas-bworld');
      return { labels: Array.from(w.querySelectorAll('.sedge > text')).map((t) => ({ text: t.textContent, box: box(t), later: !t.parentNode.classList.contains('lit') && !t.parentNode.classList.contains('done') })),
        plates: Array.from(w.querySelectorAll('.qplate')).map((r) => ({ box: box(r), opacity: getComputedStyle(r).opacity, fill: getComputedStyle(r).fill })),
        lives: Array.from(w.querySelectorAll('.qlife')).map(box), ground: getComputedStyle(document.documentElement).getPropertyValue('--map').trim() };
    }));
  }
  await page.close();
  return { runs: out, errors };
}

async function nested(browser, file) {
  const { page, errors } = await open(browser, file, WIDE, '#Page');
  await page.waitForTimeout(600);
  const out = await page.evaluate(() => {
    const d = window.systemapCanvas.drawn();
    return { current: window.systemapCanvas.current(),
      boxes: d.marks.filter((m) => m.t === 'box').map((m) => m.b), regions: d.marks.filter((m) => m.t === 'region' && m.map === 'Page').map((m) => m.b),
      labels: d.marks.filter((m) => m.t === 'label').map((m) => ({ s: m.s, box: m.box })),
      digits: d.texts.filter((t) => /^[0-9]$/.test(t.s)).map((t) => ({ s: t.s, box: t.box })) };
  });
  await page.close();
  return { ...out, errors };
}

async function phone(browser, file) {
  const { page, errors } = await open(browser, file, PHONE);
  const out = await page.evaluate(() => {
    const e = document.getElementById('atlas-ask-n'), c = e.querySelector('.ask__c');
    return { display: getComputedStyle(e).display, shown: !!c && getComputedStyle(c).display !== 'none' && c.getBoundingClientRect().height >= 1, text: e.textContent,
      k: window.systemapCanvas.camera().k, scroll: document.documentElement.scrollWidth };
  });
  await page.close();
  return { ...out, errors };
}

async function head(browser, file) {
  const { page, errors } = await open(browser, file, WIDE);
  const key = await page.evaluate(() => document.getElementById('atlas-key').textContent);
  await page.evaluate(() => window.systemapCanvas.select('', 'Placer'));
  await page.waitForTimeout(700);
  const out = await page.evaluate(() => {
    const d = document.querySelector('#atlas-side-b .side__d');
    return { state: document.getElementById('atlas-side-s').textContent, about: d ? d.textContent : '', clip: d ? d.classList.contains('clip') : false,
      clamp: d ? getComputedStyle(d).webkitLineClamp : '' };
  });
  await page.close();
  return { key, ...out, errors };
}

(async () => {
  const file = process.argv[2];
  const browser = await chromium.launch();
  const out = {
    dbl: { reduced: await dbl(browser, file, true), normal: await dbl(browser, file, false) },
    note: await note(browser, file), say: await say(browser, file), board: await board(browser, file),
    page: await nested(browser, file), phone: await phone(browser, file), head: await head(browser, file)
  };
  await browser.close();
  process.stdout.write(JSON.stringify(out) + '\n');
})().catch((err) => { process.stderr.write(String(err && err.stack || err) + '\n'); process.exit(1); });
