// The browser part of tests/test_atlas_uses_browser.py: the Uses and Used by lists of the
// details of the atlas page.
//
//     node atlas_uses.js PAGE.html CARD [CLICK]
//
// The script selects CARD of the top map and gives the sections of the details. CLICK is
// "row:ID" (a click on the row of the card ID) or "all" (a click on the button "Show all").
// Then the script gives the sections again, with the selected card. The output is one JSON
// object. `errors` has the script errors of the page.
'use strict';
const { chromium } = require('playwright');

const sections = () => {
  const out = {};
  document.querySelectorAll('#atlas-side-b section.sec').forEach((s) => {
    const name = s.querySelector('h3').firstChild.textContent;
    out[name] = {
      rows: [...s.querySelectorAll('.row[data-c]')].map((r) => ({
        id: r.getAttribute('data-c'),
        head: r.querySelector('b').textContent,
        text: r.querySelector('small').textContent,
        shown: r.getBoundingClientRect().height > 0,
      })),
      notes: [...s.querySelectorAll('p.side__d')].map((p) => p.textContent),
      more: (s.querySelector('[data-uses]') || {}).textContent || null,
    };
  });
  return { sel: window.systemapCanvas.side().sel, sections: out };
};

(async () => {
  const [file, card, click] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('file://' + file);
  await page.waitForFunction(() => window.systemapCanvas && window.systemapCanvas.ready);
  await page.evaluate((id) => window.systemapCanvas.select('', id), card);
  await page.waitForTimeout(500);
  const out = { before: await page.evaluate(sections) };
  if (click) {
    const target = click === 'all' ? '[data-uses]' : `.row[data-c="${click.slice(4)}"]`;
    await page.click(`#atlas-side-b section.sec ${target}`);
    await page.waitForTimeout(500);
    out.after = await page.evaluate(sections);
  }
  out.errors = errors;
  console.log(JSON.stringify(out));
  await browser.close();
})();
