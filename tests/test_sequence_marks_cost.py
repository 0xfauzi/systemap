"""The cost of the sequence marks on the map (audit finding g1page-1, scope seqcap).

Acceptance:

- Each step of a sequence has a step number on the map, also when the sequence has more
  than 40 steps. The step view has a number on each step other than the current step.
  The legend has no note about a range of numbered steps.
- The grid of the mark script gives the same count as a scan of all items, also for a box
  with very large or not-a-number coordinates. Thus the marks on a normal map do not change.
  In Chromium on a map with 72 components and 450 flows, one click on a route of 200 steps
  took 27.7 to 35.0 s at d7d7a8b and 0.8 to 1.1 s with the grid and all step numbers
  (bench/jev/README.md, "All step numbers of a long sequence").
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
  const steps = [];
  for(let k = 0; k < 60; k++){
    const i = k % E;
    steps.push({edge:i, acts:[A.edges[i].to], measures:[], say:'Step ' + k});
  }
  A.journeys.push({label:'L60', steps, drafted:false, starts:''});
  function numbers(){
    return svg.querySelector('.seq-marks').querySelectorAll('.seq-pill__n')
      .map((t) => +t.textContent).sort((a, b) => a - b);
  }
  function legend(){ return P.legendFor.map((f) => f()).filter((h) => h).join(''); }
  P.journey.route(A.journeys.length - 1); runFrames(win);
  out.whole = numbers(); out.wholeLegend = legend();
  P.journey.step(30); runFrames(win);
  out.step = numbers(); out.stepLegend = legend();
  return out;
}
"""


def test_each_step_of_a_long_sequence_has_a_number(sample: Sample, tmp_path: Path) -> None:
    html = page.build(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {"has_change": False}
    )
    report = drive(html, tmp_path, "longroute", LONG_ROUTE)
    # 60 steps: a number for each step in the whole route, and no legend note.
    assert report["whole"] == list(range(1, 61))
    assert "Numbers on steps" not in report["wholeLegend"]
    # Step 31: the current step has a note, not a number. All other steps have a number.
    assert report["step"] == [n for n in range(1, 61) if n != 31]
    assert "Numbers on steps" not in report["stepLegend"]


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
