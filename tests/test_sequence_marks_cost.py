"""The cost of the sequence marks on the map (audit finding g1page-1).

Acceptance:

- A sequence with 40 steps or fewer has a step number for each step, as before.
- A sequence with more than 40 steps has numbers on 40 steps only: the first 40 steps of
  the whole route, or the 40 steps near the current step. The legend gives these steps.
  The test counts the numbers, not the time. Before the change, the whole route of 3000
  steps on one flow drew 3000 numbers. Each number examined each number that was already
  on the map. In Chromium on a map with 72 components and 450 flows, one click on a
  route of 200 steps took 26 to 28 s before the change and 87 to 187 ms after it.
- The grid of the mark script gives the same count as a scan of all items, also for a box
  with very large or not-a-number coordinates. Thus the marks on a normal map do not change.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import Sample
from test_page_results import drive

from systemap import page
from systemap.page_sequence_script import GRID_JS

LONG_ROUTE = r"""
function longroute(page){
  const {doc, win, svg, A} = page, P = svg.page, E = A.edges.length, out = {};
  doc.querySelector('[data-mode="trace"]').click(); runFrames(win);
  function add(n, same){
    const steps = [];
    for(let k = 0; k < n; k++){
      const i = same ? 0 : k % E;
      steps.push({edge:i, acts:[A.edges[i].to], measures:[], say:'Step ' + k});
    }
    A.journeys.push({label:'L' + n, steps, drafted:false, starts:''});
    return A.journeys.length - 1;
  }
  function pills(){ return svg.querySelector('.seq-marks').querySelectorAll('.seq-pill').length; }
  function legend(){ return P.legendFor.map((f) => f()).filter((h) => h).join(''); }
  P.journey.route(add(40, false)); runFrames(win);
  out.short = pills(); out.shortLegend = legend();
  P.journey.route(add(3000, true)); runFrames(win);
  out.whole = pills(); out.wholeLegend = legend();
  P.journey.step(1500); runFrames(win);
  out.step = pills(); out.stepLegend = legend();
  out.numbers = svg.querySelector('.seq-marks').querySelectorAll('.seq-pill__n')
    .map((t) => +t.textContent).sort((a, b) => a - b);
  return out;
}
"""


def test_a_long_sequence_has_numbers_on_forty_steps_only(sample: Sample, tmp_path: Path) -> None:
    html = page.build(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {"has_change": False}
    )
    report = drive(html, tmp_path, "longroute", LONG_ROUTE)
    # 40 steps: a number for each step, and no legend note.
    assert report["short"] == 40
    assert "Numbers on steps" not in report["shortLegend"]
    # 3000 steps: 40 numbers in the whole route, and the legend gives them.
    assert report["whole"] == 40
    assert "Numbers on steps 1 to 40 only" in report["wholeLegend"]
    # Step 1501: the 40 steps near it. The current step has a note, not a number.
    assert report["step"] == 39
    assert "Numbers on steps 1481 to 1520 only" in report["stepLegend"]
    assert report["numbers"] == [n for n in range(1481, 1521) if n != 1501]


GRID_CHECK = r"""
const rand = (() => { let s = 7; return () => (s = (s * 16807) % 2147483647) / 2147483647; })();
function hit(a, b, m){
  return a.x < b.x + b.w + m && b.x < a.x + a.w + m && a.y < b.y + b.h + m && b.y < a.y + a.h + m;
}
function inside(p, r){ return p.x >= r.x && p.x <= r.x + r.w && p.y >= r.y && p.y <= r.y + r.h; }
const g = grid(), b = grid(), dots = [], boxes = [];
for(let k = 0; k < 3000; k++){
  const p = {x:rand() * 2000 - 500, y:rand() * 1500 - 300}; dots.push(p); g.add(p);
}
for(let k = 0; k < 400; k++){
  const r = {x:rand() * 2000 - 500, y:rand() * 1500 - 300, w:rand() * 300, h:rand() * 40};
  if(k === 0){ r.w = 1e12; } if(k === 1){ r.x = NaN; } if(k === 2){ r.w = 5000; }
  boxes.push(r); b.add(r);
}
let wrong = 0, queries = 0;
for(let k = 0; k < 2000; k++){
  const r = {x:rand() * 2200 - 600, y:rand() * 1600 - 350, w:rand() * 260, h:rand() * 120};
  if(k === 0){ r.w = 1e9; } if(k === 1){ r.y = NaN; } if(k === 2){ r.x = -Infinity; }
  const m = k % 5;
  if(g.count(r, 0, (p) => inside(p, r)) !== dots.filter((p) => inside(p, r)).length){ wrong++; }
  if(b.count(r, m, (q) => hit(r, q, m)) !== boxes.filter((q) => hit(r, q, m)).length){ wrong++; }
  queries += 2;
}
console.log(JSON.stringify({wrong, queries}));
"""


def test_the_grid_count_is_the_count_of_a_full_scan(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("the page scripts need Node")
    script = tmp_path / "grid.js"
    script.write_text(GRID_JS + GRID_CHECK, encoding="utf-8")
    proc = subprocess.run(
        [node, str(script)], capture_output=True, text=True, encoding="utf-8", timeout=60
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == {"wrong": 0, "queries": 4000}
