// The browser part of tests/test_atlas_parity_browser.py: the parity parts of the atlas page.
//
//     node atlas_parity.js MODE PAGE.html [ARG ...]
//
// MODE is one of:
// - --tools: the theme control, Reduce motion and the keyboard sheet at 1440 x 900, with the
//   light scheme of the device. Then a reload, a change of the scheme of the device, and the
//   Tools menu at 390 x 844 on a touch screen.
// - --find CARD FLOW: Ctrl K, / and the Find button, the rows for the name of CARD, Enter on
//   the first row, the result of the flow with the artifact FLOW, a sequence and a step when
//   the page has one, and Find from the Tools menu of a phone.
// - --hash MAP CARD: loads with #MAP, with #MAP/CARD and with a hash that names nothing.
// - --marks MAP: the marks and their words at the top map and at the fit of MAP, in the light
//   and the dark scheme.
// - --tree: the text list of the map tree, and a click on the link of a card.
// - --axe [MAP]: axe-core (from NODE_PATH; null when it is not there) in the light and the
//   dark scheme, at 1440 x 900 and 390 x 844: at rest, with Find open, with the keyboard sheet
//   open, with the Tools menu open (phone), and at #MAP when MAP is given.
// - --live URL HASH FLAG: the page of `systemap live` at URL with HASH. A new version, then a
//   version that the command cannot render (after the file FLAG is written).
// Each mode prints one JSON object. `errors` has the script errors of the page.
'use strict';
const fs = require('fs');
const { chromium } = require('playwright');

const WIDE = { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, reducedMotion: 'reduce' };
const PHONE = { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, hasTouch: true, isMobile: true, reducedMotion: 'reduce' };

async function open(ctx, file, hash) {
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + file + (hash || ''));
  await ready(page);
  return { page, errors };
}
async function ready(page) {
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await page.waitForTimeout(500);
}
const tools = (page) => page.evaluate(() => window.systemapCanvas.tools());
const active = (page) => page.evaluate(() => { const a = document.activeElement; return a ? a.id || a.getAttribute('data-theme-pick') || a.tagName : null; });
const stored = (page) => page.evaluate(() => ({ theme: localStorage.getItem('systemap-theme'), motion: localStorage.getItem('systemap-reduce-motion') }));
const boxOf = (page, sel) => page.evaluate((s) => Array.from(document.querySelectorAll(s)).filter((e) => e.getClientRects().length).map((e) => { const r = e.getBoundingClientRect(); return [r.width, r.height]; }), sel);

async function toolsMode(browser, file) {
  const out = {};
  const ctx = await browser.newContext({ ...WIDE, colorScheme: 'light' });
  let { page, errors } = await open(ctx, file);
  out.start = { tools: await tools(page), stored: await stored(page), pressed: await page.getAttribute('[data-theme-pick="device"]', 'aria-pressed') };
  await page.click('[data-theme-pick="dark"]');
  await page.waitForTimeout(200);
  out.dark = { tools: await tools(page), stored: await stored(page), say: await page.textContent('#atlas-said'),
    ground: await page.evaluate(() => getComputedStyle(document.body).backgroundColor),
    pressed: await page.evaluate(() => Array.from(document.querySelectorAll('[data-theme-pick]')).map((b) => b.getAttribute('aria-pressed'))) };
  await page.click('#atlas-motion');
  out.motion = { tools: await tools(page), stored: await stored(page), pressed: await page.getAttribute('#atlas-motion', 'aria-pressed') };
  await page.reload(); await ready(page);
  out.reload = { tools: await tools(page), pressed: await page.getAttribute('#atlas-motion', 'aria-pressed'),
    themePressed: await page.getAttribute('[data-theme-pick="dark"]', 'aria-pressed') };
  await page.click('#atlas-motion');
  await page.click('[data-theme-pick="device"]');
  out.device = { tools: await tools(page), stored: await stored(page) };
  await page.emulateMedia({ colorScheme: 'dark' });
  await page.waitForTimeout(200);
  out.deviceDark = { tools: await tools(page) };
  await page.emulateMedia({ colorScheme: 'light' });
  await page.waitForTimeout(200);
  // The keyboard sheet: ? on the canvas, Tab stays in the sheet, Esc closes it.
  await page.focus('#canvas');
  await page.keyboard.press('?');
  out.sheet = { tools: await tools(page), active: await active(page), rows: await page.$$eval('#keys dt', (d) => d.length) };
  await page.keyboard.press('Tab');
  out.sheet.tab = await active(page);
  const cam = await page.evaluate(() => window.systemapCanvas.camera());
  await page.keyboard.press('ArrowLeft');
  out.sheet.moved = JSON.stringify(cam) !== JSON.stringify(await page.evaluate(() => window.systemapCanvas.camera()));
  await page.keyboard.press('Escape');
  out.sheet.closed = await tools(page);
  out.sheet.back = await active(page);
  await page.click('#atlas-keys');
  out.button = { tools: await tools(page) };
  await page.click('[data-keys-close]');
  out.button.back = await active(page);
  out.errors = errors;
  await ctx.close();
  // The Tools menu of a phone.
  const pctx = await browser.newContext({ ...PHONE, colorScheme: 'dark' });
  ({ page, errors } = await open(pctx, file));
  out.phone = { before: await tools(page), wideTools: await boxOf(page, '.tools .tool'), open: await boxOf(page, '#atlas-tools-open') };
  await page.tap('#atlas-tools-open');
  out.phone.menu = await tools(page);
  out.phone.targets = await boxOf(page, '#atlas-tools .tool');
  out.phone.active = await active(page);
  out.phone.scroll = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  await page.tap('[data-theme-pick="light"]');
  out.phone.light = await tools(page);
  await page.keyboard.press('Escape');
  out.phone.closed = await tools(page);
  out.phone.back = await active(page);
  await page.tap('#atlas-tools-open');
  await page.tap('#atlas-keys');
  out.phone.keys = await tools(page);
  out.phone.errors = errors;
  await pctx.close();
  return out;
}

const fstate = () => ({ side: window.systemapCanvas.side(), lit: window.systemapCanvas.lit(), say: document.getElementById('atlas-said').textContent,
  current: window.systemapCanvas.current(), hash: location.hash, mode: window.systemapCanvas.viewState ? document.body.getAttribute('data-mode') : null,
  find: window.systemapCanvas.tools().find, active: document.activeElement && document.activeElement.id, seq: window.systemapCanvas.seq().view });

async function findMode(browser, file, card, flow) {
  const ctx = await browser.newContext({ ...WIDE, colorScheme: 'light' });
  const { page, errors } = await open(ctx, file);
  const out = {};
  await page.focus('#canvas');
  await page.keyboard.press('Control+k');
  out.ctrl = { find: (await tools(page)).find, active: await active(page) };
  await page.keyboard.press('Escape');
  out.ctrl.closed = (await tools(page)).find;
  out.ctrl.back = await active(page);
  await page.keyboard.press('/');
  out.slash = (await tools(page)).find;
  await page.keyboard.press('Escape');
  await page.click('#atlas-find');
  out.button = { find: (await tools(page)).find, expanded: await page.getAttribute('#atlas-find', 'aria-expanded') };
  out.empty = await page.evaluate(() => window.systemapCanvas.find.rank(''));
  out.rows = await page.evaluate((t) => window.systemapCanvas.find.rank(t), card);
  await page.keyboard.type(card);
  await page.waitForTimeout(100);
  out.listed = await page.$$eval('#pal-list [role="option"] .pal__t', (o) => o.map((x) => x.textContent));
  out.status = await page.textContent('#pal-status');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(1200);
  out.card = await page.evaluate(fstate);
  out.flowRows = await page.evaluate((t) => window.systemapCanvas.find.rank(t), flow);
  await page.evaluate((t) => { const g = window.systemapCanvas.find.rank(t).filter((x) => x.g === 'Flows')[0]; if (g) window.systemapCanvas.find.run(t, 'Flows', 0); }, flow);
  await page.waitForTimeout(1200);
  out.flow = await page.evaluate(fstate);
  out.other = await page.evaluate(() => window.systemapCanvas.find.rank('a').filter((g) => g.g === 'Other maps').map((g) => g.rows.length));
  const seqs = await page.evaluate(() => window.systemapCanvas.find.rank('').filter((g) => g.g === 'Sequences').map((g) => g.rows.map((r) => r.t))[0] || []);
  out.sequences = seqs;
  if (seqs.length) {
    await page.evaluate((t) => window.systemapCanvas.find.run(t, 'Sequences', 0), seqs[0]);
    await page.waitForTimeout(600);
    out.sequence = await page.evaluate(fstate);
    const step = await page.evaluate((t) => { const g = window.systemapCanvas.find.rank(t).filter((x) => x.g === 'Steps')[0]; return g ? g.rows.length : 0; }, seqs[0]);
    if (step > 1) {
      await page.evaluate((t) => window.systemapCanvas.find.run(t, 'Steps', 1), seqs[0]);
      await page.waitForTimeout(600);
      out.step = await page.evaluate(fstate);
    }
  }
  await page.evaluate(() => window.systemapCanvas.find.run('top map', 'Actions', 0));
  await page.waitForTimeout(800);
  out.top = await page.evaluate(fstate);
  out.errors = errors;
  await ctx.close();
  const pctx = await browser.newContext({ ...PHONE, colorScheme: 'dark' });
  const ph = await open(pctx, file);
  await ph.page.tap('#atlas-tools-open');
  await ph.page.tap('#atlas-find-menu');
  out.phone = { tools: await tools(ph.page), active: await active(ph.page), errors: ph.errors };
  await ph.page.keyboard.press('Escape');
  out.phone.back = await active(ph.page);
  await pctx.close();
  return out;
}

async function hashMode(browser, file, map, card) {
  const ctx = await browser.newContext({ ...WIDE, colorScheme: 'light' });
  const hs = () => ({ hash: location.hash, current: window.systemapCanvas.current(), chain: window.systemapCanvas.chain(), say: document.getElementById('atlas-said').textContent });
  const out = {};
  let o = await open(ctx, file, '#' + map);
  out.map = await o.page.evaluate(hs);
  out.errors = o.errors;
  o = await open(ctx, file, '#' + map + '/' + card);
  out.card = await o.page.evaluate(hs);
  out.card.box = await o.page.evaluate(([m, c]) => window.systemapCanvas.box(m, c), [map, card]);
  out.errors = out.errors.concat(o.errors);
  o = await open(ctx, file, '#NoSuchMap/Nothing');
  out.none = await o.page.evaluate(hs);
  // A change of the hash in a loaded page moves the camera, and the top map clears the hash.
  await o.page.evaluate((m) => { location.hash = '#' + m; }, map);
  await o.page.waitForTimeout(900);
  out.changed = await o.page.evaluate(hs);
  await o.page.keyboard.press('Escape');
  await o.page.waitForTimeout(900);
  out.out = await o.page.evaluate(hs);
  out.errors = out.errors.concat(o.errors);
  await ctx.close();
  return out;
}

async function marksMode(browser, file, map) {
  const out = { runs: [] };
  for (const scheme of ['light', 'dark']) {
    const ctx = await browser.newContext({ ...WIDE, colorScheme: scheme });
    const { page, errors } = await open(ctx, file);
    const run = { scheme, errors };
    const one = async () => ({ drawn: (await page.evaluate(() => window.systemapCanvas.drawn())).marks.filter((m) => m.t === 'mark' || m.t === 'changed line'),
      head: await page.textContent('#atlas-ask-n'), say: await page.textContent('#atlas-said'), current: await page.evaluate(() => window.systemapCanvas.current()) });
    run.top = await one();
    run.topState = await page.evaluate(() => window.systemapCanvas.marks(''));
    run.tokens = await page.evaluate(() => ({ change: getComputedStyle(document.documentElement).getPropertyValue('--change').trim(), ink2: getComputedStyle(document.documentElement).getPropertyValue('--ink-2').trim() }));
    await page.evaluate((m) => { location.hash = '#' + m; }, map);
    await page.waitForTimeout(1200);
    run.nested = await one();
    // The layer All shows each flow of the map, also the lost flows.
    await page.evaluate(() => window.systemapCanvas.setLayer('all'));
    await page.waitForTimeout(500);
    run.nestedAll = await one();
    run.state = await page.evaluate((m) => window.systemapCanvas.marks(m), map);
    const marked = run.state.cards[0];
    if (marked) {
      await page.evaluate(([m, c]) => window.systemapCanvas.pointAt(m, c), [map, marked.id]);
      await page.waitForTimeout(300);
      run.reading = await page.textContent('#atlas-say');
    }
    await page.waitForTimeout(400);
    run.tree = await page.textContent('#atlas-tree');
    out.runs.push(run);
    await ctx.close();
  }
  return out;
}

async function treeMode(browser, file) {
  const ctx = await browser.newContext({ ...WIDE, colorScheme: 'light' });
  const { page, errors } = await open(ctx, file);
  await page.waitForTimeout(400);
  const out = { errors };
  out.label = await page.getAttribute('#atlas-tree', 'aria-label');
  out.links = await page.$$eval('#atlas-tree a', (a) => a.map((x) => ({ text: x.textContent, href: x.getAttribute('href'), m: x.getAttribute('data-m'), c: x.getAttribute('data-c'), f: x.getAttribute('data-f') })));
  out.lists = await page.$$eval('#atlas-tree ul[aria-label]', (u) => u.map((x) => x.getAttribute('aria-label')));
  out.text = await page.textContent('#atlas-tree');
  const card = out.links.find((l) => l.c !== null && l.m !== '0');
  if (card) {
    await page.focus('#atlas-tree a[data-c="' + card.c + '"][data-m="' + card.m + '"]');
    await page.keyboard.press('Enter');
    await page.waitForTimeout(1200);
    out.went = { card, hash: await page.evaluate(() => location.hash), current: await page.evaluate(() => window.systemapCanvas.current()),
      focus: await page.evaluate(() => document.activeElement && document.activeElement.getAttribute('data-c')) };
  }
  await ctx.close();
  return out;
}

async function axeRun(page) {
  let source;
  try { source = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8'); } catch (e) { return null; }
  await page.addScriptTag({ content: source });
  return page.evaluate(async () => {
    const r = await window.axe.run(document, { resultTypes: ['violations'] });
    return { version: window.axe.version, violations: r.violations.map((v) => v.impact + ' ' + v.id + ': ' + v.nodes.map((n) => n.target.join(' ')).join(', ')) };
  });
}
async function axeMode(browser, file, map) {
  const runs = [];
  for (const scheme of ['light', 'dark']) {
    for (const opts of [WIDE, PHONE]) {
      const phone = opts === PHONE;
      const states = [['rest', null], ['find', async (p) => { await p.keyboard.press('Control+k'); }],
        ['keys', async (p) => { await p.focus('#canvas'); await p.keyboard.press('?'); }]];
      if (phone) states.push(['menu', async (p) => { await p.tap('#atlas-tools-open'); }]);
      if (map) states.push(['nested', null, '#' + map]);
      for (const [state, act, hash] of states) {
        const ctx = await browser.newContext({ ...opts, colorScheme: scheme, bypassCSP: true });
        const { page, errors } = await open(ctx, file, hash);
        if (act) { await act(page); await page.waitForTimeout(300); }
        const axe = await axeRun(page);
        runs.push({ scheme, width: opts.viewport.width, state, errors, axe });
        await ctx.close();
        if (axe === null) return { runs: null };
      }
    }
  }
  return { runs };
}

async function refresh(page, url) {
  const res = await page.request.post(new URL('/refresh', url).href);
  if (res.status() !== 202) throw new Error('refresh gave ' + res.status());
}
async function liveMode(browser, url, hash, flag) {
  const origin = new URL(url).origin;
  const ctx = await browser.newContext({ ...WIDE, colorScheme: 'light' });
  const out = { loads: [], violations: [], errors: [], outside: [], sources: [], notice: null };
  await ctx.exposeBinding('reportViolation', (_s, text) => { out.violations.push(text); });
  await ctx.exposeBinding('reportSource', (_s, at) => { out.sources.push(at); });
  await ctx.addInitScript(() => {
    document.addEventListener('securitypolicyviolation', (e) => { window.reportViolation(e.violatedDirective + ' ' + e.blockedURI); });
    const Real = window.EventSource;
    if (Real) { window.EventSource = function (u, o) { window.reportSource(String(u)); return new Real(u, o); }; window.EventSource.prototype = Real.prototype; }
  });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => out.errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') out.errors.push(m.text()); });
  page.on('request', (r) => { if (!r.url().startsWith(origin + '/')) out.outside.push(r.url()); });
  let navigations = 0;
  page.on('load', () => { navigations++; });
  const loaded = async () => {
    await ready(page);
    out.loads.push(await page.evaluate(() => ({ hash: location.hash, chain: window.systemapCanvas.chain(), current: window.systemapCanvas.current(),
      atlas: !!document.getElementById('atlas-data') })));
  };
  await page.goto(url + hash);
  await loaded();
  const before = navigations;
  await refresh(page, url);
  for (let i = 0; i < 100 && navigations === before; i++) await page.waitForTimeout(100);
  await loaded();
  fs.writeFileSync(flag, 'fail');
  await refresh(page, url);
  await page.waitForSelector('#live-notice', { timeout: 30000 });
  out.notice = await page.textContent('#live-notice');
  await page.waitForTimeout(1000);
  out.navigations = navigations;
  await ctx.close();
  return out;
}

(async () => {
  const [mode, file, ...rest] = process.argv.slice(2);
  const run = { '--tools': toolsMode, '--find': findMode, '--hash': hashMode, '--marks': marksMode, '--tree': treeMode, '--axe': axeMode, '--live': liveMode }[mode];
  if (!run) throw new Error('unknown mode ' + mode);
  const browser = await chromium.launch();
  try { process.stdout.write(JSON.stringify(await run(browser, file, ...rest))); } finally { await browser.close(); }
})().catch((e) => { process.stderr.write(String(e && e.stack || e)); process.exit(1); });
