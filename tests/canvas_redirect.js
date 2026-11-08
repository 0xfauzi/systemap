// Opens the small page of a nested map (systemap.canvas_redirect) in the Chromium of
// Playwright, and prints one JSON object. tests/test_canvas_redirect_browser.py reads it.
//
//     node tests/canvas_redirect.js --go URL [--no-script] [--phone] [--light]
//     node tests/canvas_redirect.js --shots URL FOLDER NAME
//     node tests/canvas_redirect.js --probe
//
// --go opens URL and waits until the page is at its last address. It gives that address,
// the open chain of maps of the canvas, the view, each policy violation (the event
// securitypolicyviolation of each page on the way), each request outside the origin of
// URL, and the script errors. With --no-script, the browser runs no script. Then the page
// at the last address is the small page or the canvas page without its renderer.
// --shots writes screenshots of the small page without a script (the move to the top page
// stops) and of the canvas page at the end of the move, at 1440 x 900 and 390 x 844
// pixels, light and dark.
'use strict';
const path = require('path');
const { chromium } = require('playwright');

const DESK = { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 };
const PHONE = { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3 };

async function context(browser, options) {
  const ctx = await browser.newContext({ colorScheme: 'dark', reducedMotion: 'reduce', ...DESK, ...options });
  const found = { violations: [], outside: [], requests: [], errors: [] };
  await ctx.exposeBinding('reportViolation', (_source, text) => { found.violations.push(text); });
  await ctx.addInitScript(() => {
    document.addEventListener('securitypolicyviolation', (e) => {
      window.reportViolation(e.violatedDirective + ' ' + e.blockedURI + ' ' + location.pathname);
    });
  });
  return { ctx, found };
}

function watch(page, found, origin) {
  page.on('pageerror', (e) => found.errors.push(String(e)));
  page.on('console', (m) => {
    const text = m.text();
    if (m.type() === 'error') found.errors.push(text);
    if (/Content Security Policy/.test(text)) found.violations.push(text);
  });
  page.on('request', (r) => {
    const url = r.url();
    found.requests.push(url);
    if (!url.startsWith(origin + '/') && !url.startsWith('data:')) found.outside.push(url);
  });
}

async function go(url, flags) {
  const browser = await chromium.launch();
  const options = { javaScriptEnabled: !flags.includes('--no-script') };
  if (flags.includes('--phone')) Object.assign(options, PHONE);
  if (flags.includes('--light')) options.colorScheme = 'light';
  const { ctx, found } = await context(browser, options);
  const page = await ctx.newPage(), origin = new URL(url).origin;
  watch(page, found, origin);
  await page.goto(url);
  // The small page goes on at once. Wait until the address stays the same for 600 ms.
  let last = '', same = 0;
  for (let i = 0; i < 60 && same < 3; i++) {
    await page.waitForTimeout(200);
    const now = page.url();
    same = now === last ? same + 1 : 0;
    last = now;
  }
  const out = { url: page.url(), ...found };
  if (options.javaScriptEnabled) {
    await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready, null, { timeout: 15000 });
    await page.waitForTimeout(400);
    Object.assign(out, await page.evaluate(() => {
      const S = window.systemapCanvas, c = S.camera(), m = S.chain();
      const fit = S.fit(m.length ? m[m.length - 1] : '');
      return { chain: m, view: S.viewState().mode, atFit: Math.abs(c.k - fit.k) < 1e-6 * fit.k,
        hash: location.hash, selected: S.selected().id,
        scroll: document.documentElement.scrollWidth, width: window.innerWidth, scrollX: window.scrollX };
    }));
  } else {
    Object.assign(out, await page.evaluate(() => {
      const a = document.querySelector('a[href]');
      return { title: document.title, link: a ? a.getAttribute('href') : null, text: document.body.innerText,
        canvas: !!document.getElementById('canvas') };
    }));
  }
  await browser.close();
  return out;
}

async function shots(url, folder, name) {
  const browser = await chromium.launch();
  const written = [];
  for (const [size, options] of [['1440x900', DESK], ['390x844', PHONE]]) {
    for (const scheme of ['light', 'dark']) {
      for (const script of [false, true]) {
        const { ctx } = await context(browser, { ...options, colorScheme: scheme, javaScriptEnabled: script });
        const page = await ctx.newPage();
        // Without a script, the small page stays: the screenshot copy has no refresh element.
        if (!script) {
          await page.route((u) => u.pathname !== '/index.html', async (r) => {
            const res = await r.fetch(), body = (await res.text()).replace(/<meta http-equiv="refresh"[^>]*>/, '');
            await r.fulfill({ response: res, body });
          });
        }
        await page.goto(url);
        await page.waitForTimeout(script ? 1500 : 300);
        const file = path.join(folder, `${name}-${script ? 'canvas' : 'no-script'}-${size}-${scheme}.png`);
        await page.screenshot({ path: file });
        written.push(file);
        await ctx.close();
      }
    }
  }
  await browser.close();
  return { written };
}

(async () => {
  const args = process.argv.slice(2);
  let out;
  if (args[0] === '--probe') {
    const browser = await chromium.launch();
    await browser.close();
    out = { ok: true };
  } else if (args[0] === '--go') out = await go(args[1], args.slice(2));
  else if (args[0] === '--shots') out = await shots(args[1], args[2], args[3]);
  else throw new Error('unknown arguments: ' + args.join(' '));
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { process.stderr.write(String(e && e.stack || e)); process.exit(1); });
