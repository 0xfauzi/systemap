"""Measure the time of one relabel call on the self-map page while a sequence is active.

Acceptance (written before the run): with a sequence on the map, the median time of one relabel
call with the current label script is at most 1.2 times the median time of the script before
the change that reads the mark boxes on each call (57f8180^). The pan case is the acceptance
case. The static case is also given.

The script builds the self-map page one time for each label script:

- `before`: the relabel function of 57f8180^. The key has the count of the marks. The script
  reads the mark boxes only when the key changes.
- `read`: the relabel function of 57f8180. The script reads the mark boxes on each call, and
  the key has the boxes.
- `current`: the relabel function in `src/systemap/schematic_labels.py` now.

Headless Chrome opens each page at 1600 by 900 pixels and shows the whole route of the first
sequence, and then step 1. In the pan case, each call follows a change to the transform of the
map view, as a pan frame does. The time of a loop with the transform changes only is subtracted.
In the static case, the calls follow each other with no change. Each case has 2000 calls after
200 calls that are not counted. The pages operate in turn, for 11 samples. The script gives the
median of the samples in microseconds.

Run from the repository root: uv run python bench/jev/relabel_time.py
"""

from __future__ import annotations

import json
import shutil
import statistics
import subprocess
import tempfile
from pathlib import Path

from systemap import config, facts_file, nest, page, schematic_script
from systemap import schematic_labels as labels_mod

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SAMPLES = 11
LIMIT = 1.2

BEFORE = r"""function relabel(){
  growSoon = 0;
  var L = state.layer, s = growth(), j = state.journey, g = svg.querySelector('.seq-marks');
  var key = L + s + svg.classList.contains('fg-on')
    + (j ? (j.whole ? 'w' : j.edge) + (g ? g.childNodes.length : 0) : '');
  if(key === growKey){ return; }
  growKey = key;
  function on(i){ return edgeIn(i, L) && !flowOf[i].classList.contains('fg-hide'); }
  var ctx = {taken:[], cards:nodes.map(boxOf), segs:SEGS.filter(function(q){ return on(q.e); })};
  var crowd = BESIDE.slice(), m = view.getScreenCTM(), k = m ? Math.hypot(m.a, m.b) : 0;
  [].forEach.call(j && g ? g.childNodes : [], function(c){
    var r = c.getBoundingClientRect();
    if(k && r.width){ ctx.taken.push({x:(r.left - m.e) / k, y:(r.top - m.f) / k,
      w:r.width / k, h:r.height / k}); }
  });
"""

READ = r"""function relabel(){
  growSoon = 0;
  var L = state.layer, s = growth(), j = state.journey, g = svg.querySelector('.seq-marks');
  var m = view.getScreenCTM(), k = m ? Math.hypot(m.a, m.b) : 0, marks = [];
  [].forEach.call(j && g ? g.childNodes : [], function(c){
    var r = c.getBoundingClientRect();
    if(k && r.width){ marks.push({x:(r.left - m.e) / k, y:(r.top - m.f) / k,
      w:r.width / k, h:r.height / k}); }
  });
  var key = L + s + svg.classList.contains('fg-on') + (j ? (j.whole ? 'w' : j.edge) : '')
    + marks.map(function(r){ return [r.x, r.y, r.w, r.h].map(function(v){
      return v.toFixed(1); }).join(','); }).join(';');
  if(key === growKey){ return; }
  growKey = key;
  function on(i){ return edgeIn(i, L) && !flowOf[i].classList.contains('fg-hide'); }
  var ctx = {taken:marks, cards:nodes.map(boxOf),
    segs:SEGS.filter(function(q){ return on(q.e); })};
  var crowd = BESIDE.slice();
"""

# The common end of the three relabel functions.
TAIL = "  HEADS.forEach(function(h){ placeHead(h, s, ctx); });"
# The page script gives the relabel function to the harness.
EXPOSE = "\nsvg.benchRelabel = function(){ relabel(); };\n"

BENCH = r"""
(async () => {
  const svg = document.getElementById('schematic');
  const frames = (n) => new Promise((done) => {
    const step = () => (n-- > 0 ? requestAnimationFrame(step) : done());
    step();
  });
  const view = svg.querySelector('g.view');
  const relabel = svg.benchRelabel;
  const WARM = 200, CALLS = 2000;
  function loop(n, call, pan) {
    const base = view.getAttribute('transform') || '';
    const t0 = performance.now();
    for (let i = 0; i < n; i++) {
      if (pan) { view.setAttribute('transform', base + ' translate(' + (i % 2) + ' 0)'); }
      if (call) { relabel(); }
    }
    const t = performance.now() - t0;
    view.setAttribute('transform', base);
    return t * 1000 / n;
  }
  function measure() {
    loop(WARM, true, true);
    const pan = loop(CALLS, true, true) - loop(CALLS, false, true);
    loop(WARM, true, false);
    const fixed = loop(CALLS, true, false);
    return {pan, static: fixed, marks: svg.querySelector('.seq-marks').childNodes.length};
  }
  svg.page.journey.route(0);
  await frames(30);
  const whole = measure();
  document.getElementById('jstart').click();
  await frames(30);
  const step = measure();
  return JSON.stringify({whole, step});
})()
"""

CDP = r"""
// Open each page in headless Chrome through the debugging pipe, evaluate one expression,
// and print the results.
const {spawn} = require('child_process');
const [chrome, profile, expression, ...urls] = process.argv.slice(2);
const proc = spawn(chrome, ['--headless=new', '--disable-gpu', '--no-first-run',
  '--force-prefers-reduced-motion', '--remote-debugging-pipe', '--window-size=1600,900',
  '--user-data-dir=' + profile, 'about:blank'], {stdio: ['ignore', 'ignore', 'ignore', 'pipe', 'pipe']});
const input = proc.stdio[3], output = proc.stdio[4];
let id = 0, buffer = '', session = '';
const wait = new Map(), events = [];
output.on('data', (chunk) => {
  buffer += chunk.toString('utf8');
  let end;
  while ((end = buffer.indexOf('\0')) >= 0) {
    const d = JSON.parse(buffer.slice(0, end)); buffer = buffer.slice(end + 1);
    if (d.id && wait.has(d.id)) { wait.get(d.id)(d); wait.delete(d.id); } else { events.push(d); }
  }
});
function send(method, params, sessionId) {
  return new Promise((r) => { id += 1; wait.set(id, r);
    input.write(JSON.stringify({id, method, params, sessionId}) + '\0'); });
}
async function main() {
  const targets = await send('Target.getTargets', {});
  const target = targets.result.targetInfos.find((t) => t.type === 'page');
  const attached = await send('Target.attachToTarget', {targetId: target.targetId, flatten: true});
  session = attached.result.sessionId;
  await send('Page.enable', {}, session);
  const out = [];
  for (const url of urls) {
    events.length = 0;
    await send('Page.navigate', {url}, session);
    for (let k = 0; k < 400 && !events.some((e) => e.method === 'Page.loadEventFired'); k++) {
      await new Promise((r) => setTimeout(r, 25)); }
    const r = await send('Runtime.evaluate',
      {expression, awaitPromise: true, returnByValue: true}, session);
    if (r.error || r.result.exceptionDetails) { throw new Error(JSON.stringify(r)); }
    out.push({url, value: JSON.parse(r.result.result.value)});
  }
  console.log(JSON.stringify(out));
  proc.kill();
}
main().catch((e) => { console.error(e); proc.kill(); process.exit(1); });
"""


def variant(head: str) -> str:
    """Give the label script with a different start of the relabel function."""
    text = labels_mod.LABEL_JS
    start = text.index("function relabel(){")
    end = text.index(TAIL)
    return text[:start] + head + text[end:] + EXPOSE


def current_head() -> str:
    text = labels_mod.LABEL_JS
    return text[text.index("function relabel(){") : text.index(TAIL)]


def render(root: Path, label_js: str) -> str:
    """Build the self-map page with one label script."""
    saved = schematic_script._INTERACTIVE_JS
    schematic_script._INTERACTIVE_JS = saved.replace(labels_mod.LABEL_JS, label_js)
    try:
        cfg = config.load(root)
        tree = nest.load(cfg)
        m = tree.top
        facts = facts_file.read_facts(cfg.facts_path)
        nesting = page.nesting_of(cfg, tree, m, facts)
        return page.build(cfg, m.model, m.meaning, m.theme, facts, {"has_change": False}, nesting)
    finally:
        schematic_script._INTERACTIVE_JS = saved


def main() -> None:
    root = Path.cwd()
    node = shutil.which("node")
    if node is None:
        raise SystemExit("The measurement needs Node.")
    heads = {"before": BEFORE, "read": READ, "current": current_head()}
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        urls = {}
        for name, head in heads.items():
            out = work / f"{name}.html"
            out.write_text(render(root, variant(head)), encoding="utf-8")
            urls[out.as_uri()] = name
        (work / "cdp.js").write_text(CDP, encoding="utf-8")
        found: dict[str, list[dict[str, dict[str, float]]]] = {n: [] for n in heads}
        for index in range(SAMPLES):
            proc = subprocess.run(
                [node, str(work / "cdp.js"), CHROME, str(work / f"profile-{index}"), BENCH, *urls],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=300,
                check=False,
            )
            if proc.returncode != 0:
                raise SystemExit(f"The measurement failed:\n{proc.stderr}")
            for record in json.loads(proc.stdout):
                found[urls[record["url"]]].append(record["value"])
    report(found)


def report(found: dict[str, list[dict[str, dict[str, float]]]]) -> None:
    def median(name: str, state: str, case: str) -> float:
        return statistics.median(r[state][case] for r in found[name])

    print("| State | Case | Marks | before (us) | read (us) | current (us) | current / before |")
    print("|---|---|---|---|---|---|---|")
    verdicts = []
    for state in ("whole", "step"):
        marks = int(found["current"][0][state]["marks"])
        for case in ("pan", "static"):
            before, read, now = (median(n, state, case) for n in ("before", "read", "current"))
            ratio = now / before if before > 0 else float("inf")
            if case == "pan":
                verdicts.append(ratio <= LIMIT)
            print(
                f"| {state} | {case} | {marks} | {before:.2f} | {read:.2f} | {now:.2f} "
                f"| {ratio:.2f} |"
            )
    print(f"Acceptance at {LIMIT}: {'passes' if all(verdicts) else 'fails'} (pan case)")


if __name__ == "__main__":
    main()
