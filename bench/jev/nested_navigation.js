// The browser part of nested_navigation.py: M12, M13 (axe-core part) and M15.
//
//     node bench/jev/nested_navigation.js PAGE.html [AXE_PATH]
//
// prints one JSON object. A browser that Playwright cannot start gives
// {"run": false, "reason": ...} for that browser. No value is put in place
// of a measurement that did not run.
'use strict';
const fs = require('fs');
const path = require('path');
const {pathToFileURL} = require('url');
const playwright = require('playwright');

const RUNS = 5;
const page = path.resolve(process.argv[2]);
const axePath = process.argv[3] || '';
const url = pathToFileURL(page).href;

async function start(kind) {
  try {
    return {browser: await playwright[kind].launch()};
  } catch (e) {
    return {reason: String(e.message || e).split('\n')[0]};
  }
}

// The first animation frame in which the map script and the page script are ready.
const READY = () => {
  const s = document.getElementById('schematic');
  return s && s.systemap && s.page ? performance.now() : false;
};

async function load(browser) {
  const times = [];
  for (let k = 0; k < RUNS; k++) {
    const context = await browser.newContext({viewport: {width: 1440, height: 900}});
    const tab = await context.newPage();
    await tab.goto(url, {waitUntil: 'commit'});
    const handle = await tab.waitForFunction(READY, null, {polling: 'raf', timeout: 30000});
    times.push(await handle.jsonValue());
    await context.close();
  }
  const sorted = times.slice().sort((a, b) => a - b);
  return {run: true, ms: times.map((t) => Math.round(t)), median: Math.round(sorted[(RUNS - 1) / 2]),
    max: Math.round(sorted[RUNS - 1]), cards: CARDS};
}
let CARDS = 0;

async function axe(browser, scheme) {
  if (!axePath || !fs.existsSync(axePath)) { return {run: false, reason: 'no axe-core file (AXE_PATH)'}; }
  // The page policy permits only the scripts of the page. The test adds axe-core.
  const context = await browser.newContext({viewport: {width: 1440, height: 900}, bypassCSP: true,
    colorScheme: scheme === 'light' ? 'light' : 'dark'});
  const tab = await context.newPage();
  await tab.goto(url);
  await tab.waitForFunction(READY, null, {polling: 'raf'});
  const theme = await tab.evaluate(() => document.documentElement.getAttribute('data-theme'));
  await tab.addScriptTag({path: axePath});
  const result = await tab.evaluate(async () => {
    const r = await window.axe.run(document, {resultTypes: ['violations']});
    return {version: window.axe.version, violations: r.violations.map((v) => ({id: v.id, impact: v.impact,
      nodes: v.nodes.length, targets: v.nodes.slice(0, 4).map((n) => n.target.join(' '))}))};
  });
  await context.close();
  const bad = result.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
  return {run: true, theme, version: result.version, seriousOrCritical: bad.length, violations: result.violations};
}

async function phone(browser) {
  const context = await browser.newContext({viewport: {width: 360, height: 740}, isMobile: true,
    hasTouch: true, deviceScaleFactor: 2});
  const tab = await context.newPage();
  await tab.goto(url);
  await tab.waitForFunction(READY, null, {polling: 'raf'});
  await tab.waitForTimeout(300);
  const out = await tab.evaluate(() => {
    const root = document.documentElement;
    const shown = (n) => {
      const r = n.getBoundingClientRect(), cs = getComputedStyle(n);
      return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'
        && !n.closest('[hidden], [inert], .sr-only');
    };
    const name = (n) => (n.tagName.toLowerCase() + (n.id ? '#' + n.id : '')
      + (n.getAttribute('class') ? '.' + String(n.getAttribute('class')).trim().split(/\s+/)[0] : '')
      + (n.dataset && n.dataset.id ? '[' + n.dataset.id + ']' : '')
      + ' "' + (n.getAttribute('aria-label') || n.textContent || '').trim().slice(0, 24) + '"');
    const sel = 'a[href], button, summary, input, select, textarea, [role="button"], [tabindex]:not([tabindex="-1"])';
    const targets = Array.from(document.querySelectorAll(sel)).filter(shown);
    const small = targets.map((n) => ({n, r: n.getBoundingClientRect()}))
      .filter((x) => x.r.width < 44 || x.r.height < 44)
      .map((x) => ({target: name(x.n), w: Math.round(x.r.width), h: Math.round(x.r.height),
        header: !!x.n.closest('.bar'), map: !!x.n.closest('svg')}));
    const h1 = document.querySelector('.project-name');
    const back = Array.from(document.querySelectorAll('#mappath .crumb')).filter(shown);
    return {
      phoneState: document.body.dataset.phone || '',
      scrollWidth: root.scrollWidth, clientWidth: root.clientWidth,
      horizontalScroll: root.scrollWidth > root.clientWidth,
      targets: targets.length, small: small.length,
      smallInHeader: small.filter((x) => x.header).length,
      smallInMap: small.filter((x) => x.map).length,
      smallList: small,
      heading: h1 ? h1.textContent : '', headingCut: h1 ? h1.scrollWidth > h1.clientWidth : true,
      headingShown: !!(h1 && shown(h1)),
      parentLinks: back.map((a) => ({text: a.textContent, w: Math.round(a.getBoundingClientRect().width),
        h: Math.round(a.getBoundingClientRect().height)})),
    };
  });
  await context.close();
  return Object.assign({run: true}, out);
}

async function main() {
  const html = fs.readFileSync(page, 'utf8');
  CARDS = (html.match(/<g class="node /g) || []).length;
  const report = {page: path.relative(process.cwd(), page), playwright: require('playwright/package.json').version};
  for (const kind of ['chromium', 'firefox']) {
    const {browser, reason} = await start(kind);
    if (!browser) {
      report[kind] = {run: false, reason};
      continue;
    }
    report[kind] = {version: browser.version(), m12: await load(browser),
      m13: {ink: await axe(browser, 'dark'), paper: await axe(browser, 'light')},
      m15: await phone(browser)};
    await browser.close();
  }
  process.stdout.write(JSON.stringify(report) + '\n');
}

main().catch((e) => { process.stderr.write(String(e && e.stack || e) + '\n'); process.exit(1); });
