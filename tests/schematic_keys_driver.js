// Operates the map script of a figure page under the DOM of page_driver.js, with
// model IDs that are also names of JavaScript object properties, such as
// `__proto__`, `constructor` and `toString`.
//
//     node tests/schematic_keys_driver.js PAGE.html LAYER CARD LINK...
//
// It prints one JSON object. `links` gives, for each LINK, the selected component
// after the page opens at #LINK, or the exception. `shown` gives the flows that show
// when LAYER is selected, and `layerIds` the components of LAYER. `quiet` gives the
// quiet cards for LAYER. `dimmed` gives the dim cards after a selection of CARD.
// tests/test_schematic_prototype.py reads the object.
'use strict';
const fs = require('fs');
const {boot, runFrames} = require('./page_driver.js');

const [file, layer, card, ...links] = process.argv.slice(2);
const html = fs.readFileSync(file, 'utf8');
const VIEWPORT = [1600, 900];

function attempt(fn) {
  try { return {value: fn()}; } catch (e) { return {error: String((e && e.message) || e)}; }
}
function ids(svg, cls) {
  return svg.querySelectorAll('.node').filter((n) => n.classList.contains(cls)).map((n) => n.dataset.id);
}

const report = {links: Object.create(null)};
links.forEach((id) => {
  report.links[id] = attempt(() => boot(html, true, VIEWPORT, {hash: '#' + id}).A.state.focus);
});
const {A, svg, win} = boot(html, true, VIEWPORT, {});
A.setLayer(layer);
runFrames(win);
report.shown = svg.querySelectorAll('.flow').filter((p) => !p.classList.contains('off')).map((p) => +p.dataset.edge);
report.layerIds = A.layerIds(layer);
report.quiet = ids(svg, 'quiet');
A.setLayer('all');
report.dimmed = attempt(() => { A.select(card); runFrames(win); return ids(svg, 'dim'); });
process.stdout.write(JSON.stringify(report) + '\n');
