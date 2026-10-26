"""A movement of the map writes the drawing transform one time.

Acceptance: during 20 wheel events, a drag and a camera tween, the page writes the
transform of the drawing zero times. At the end of each movement, the page writes it
one time. The final transform and the label transforms are equal to the values of a
page that writes the transform for each step. A line reveal reads all lengths and
boxes before its first write. Before the change, the tween wrote the transform at
each frame, and the reveal read a length after each write.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from conftest import Sample
from test_keyboard import DRIVER, needs_node, sample_page

MOVEMENT = r"""
function movement(page) {
  const {svg, A, win} = page;
  const view = () => svg.querySelector('.view');
  const labels = (s) => s.querySelectorAll('[transform]').filter((e) => !e.classList.contains('view'))
    .map((e) => e.getAttribute('transform'));
  function count(s) {
    const v = s.querySelector('.view'), set = v.setAttribute.bind(v), c = {n: 0};
    v.setAttribute = (n, x) => { if (n === 'transform') c.n++; set(n, x); };
    return c;
  }
  function wheel(s, w, d = -10) {
    for (let i = 0; i < 20; i++) {
      const ev = new EventImpl('wheel', {bubbles: true});
      ev.deltaY = d; ev.deltaMode = 0; ev.clientX = 300 + i; ev.clientY = 200;
      s.dispatchEvent(ev); runFrames(w);
    }
  }
  function pointer(s, type, x, y) {
    const ev = new EventImpl(type, {bubbles: true});
    ev.pointerId = 1; ev.pointerType = 'mouse'; ev.button = 0; ev.clientX = x; ev.clientY = y;
    s.dispatchEvent(ev);
  }
  function drag(s, w) {
    pointer(s, 'pointerdown', 400, 300);
    for (let i = 1; i <= 10; i++) { pointer(s, 'pointermove', 400 + i * 7, 300 + i * 3); runFrames(w); }
  }
  // The page: the map frame clips the wrapper, and timers wait until the scenario runs them.
  const timers = new Map();
  let next = 0;
  win.getComputedStyle = (el) => ({overflow: el && el.id === 'mapwrap' ? 'hidden' : ''});
  win.setTimeout = (cb) => { timers.set(++next, cb); return next; };
  win.clearTimeout = (id) => { timers.delete(id); };
  const flush = () => { const all = [...timers.values()]; timers.clear(); all.forEach((cb) => cb()); runFrames(win); };
  // The reference: a new page that writes the transform for each step.
  const ref = page.reload('');
  const out = {};
  const c = count(svg), r = count(ref.svg);
  wheel(svg, win);
  out.wheel = {during: c.n, wrapper: svg.parentNode.style.transform || ''};
  flush();
  wheel(ref.svg, ref.win);
  out.wheel.after = c.n; out.wheel.refWrites = r.n;
  out.wheel.equal = view().getAttribute('transform') === ref.svg.querySelector('.view').getAttribute('transform');
  out.wheel.labelsEqual = JSON.stringify(labels(svg)) === JSON.stringify(labels(ref.svg));
  out.wheel.wrapperAfter = svg.parentNode.getAttribute('style') || '';
  c.n = 0; r.n = 0;
  drag(svg, win);
  out.drag = {during: c.n};
  pointer(svg, 'pointerup', 470, 330); runFrames(win);
  drag(ref.svg, ref.win); pointer(ref.svg, 'pointerup', 470, 330); runFrames(ref.win);
  out.drag.after = c.n; out.drag.refWrites = r.n;
  out.drag.equal = view().getAttribute('transform') === ref.svg.querySelector('.view').getAttribute('transform');
  c.n = 0; r.n = 0;
  A.view.zoomBy(1.5); runFrames(win);
  ref.A.view.zoomBy(1.5); runFrames(ref.win);
  out.tween = {writes: c.n, refWrites: r.n,
    equal: view().getAttribute('transform') === ref.svg.querySelector('.view').getAttribute('transform'),
    labelsEqual: JSON.stringify(labels(svg)) === JSON.stringify(labels(ref.svg)),
    wrapperAfter: svg.parentNode.getAttribute('style') || ''};
  // The present mode moves the wrapper to a parent that does not clip it, and then back.
  const frame = svg.parentNode.parentNode, other = win.document.createElement('div');
  frame.appendChild(other); other.appendChild(svg.parentNode);
  c.n = 0; wheel(svg, win, 10);
  out.moved = {during: c.n, wrapper: svg.parentNode.style.transform || ''};
  flush();
  frame.appendChild(svg.parentNode);
  c.n = 0; wheel(svg, win, 10);
  out.moved.backDuring = c.n; out.moved.backWrapper = svg.parentNode.style.transform || '';
  flush();
  // A line reveal: the order of the layout reads and the writes.
  const log = [];
  const proto = Object.getPrototypeOf(svg);
  const bbox = proto.getBBox, setAttr = proto.setAttribute;
  proto.getTotalLength = function () { log.push('read'); return 100; };
  proto.getBBox = function () { log.push('read'); return bbox.call(this); };
  proto.animate = function () { return {cancel() {}, onfinish: null}; };
  proto.setAttribute = function (n, x) { if (n === 'mask') log.push('write'); return setAttr.call(this, n, x); };
  A.setLayer('all');
  const shown = svg.querySelectorAll('.flow').filter((p) => !p.classList.contains('off')).map((p) => +p.dataset.edge);
  out.reveal = {drawn: A.drawLines(shown), lines: shown.length,
    readsAfterWrite: log.slice(log.indexOf('write')).filter((x) => x === 'read').length,
    writes: log.filter((x) => x === 'write').length};
  return out;
}
"""


def drive(html: Path, tmp_path: Path) -> dict[str, Any]:
    driver = DRIVER.read_text(encoding="utf-8").replace(
        "const scenarios = {keyboard, framing, submap, theme, workspace};",
        "const scenarios = {keyboard, framing, submap, theme, workspace, movement};",
    )
    harness = tmp_path / "movement.js"
    harness.write_text(driver + MOVEMENT, encoding="utf-8")
    proc = subprocess.run(
        [shutil.which("node") or "node", str(harness), str(html), "--scenario", "movement"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    report: dict[str, Any] = json.loads(proc.stdout)
    return report


@needs_node
def test_a_movement_writes_the_drawing_transform_one_time(sample: Sample, tmp_path: Path) -> None:
    report = drive(sample_page(sample, tmp_path), tmp_path)
    wheel, drag, tween = report["wheel"], report["drag"], report["tween"]
    # The wrapper shows the wheel zoom. The drawing transform does not change.
    assert wheel["during"] == 0 and "scale(" in wheel["wrapper"]
    assert wheel["after"] == 1 and wheel["refWrites"] == 20
    assert wheel["equal"] and wheel["labelsEqual"] and wheel["wrapperAfter"] == ""
    assert drag["during"] == 0 and drag["after"] == 1 and drag["refWrites"] == 10
    assert drag["equal"]
    # Before the change, the tween wrote the transform at each frame of 20 ms.
    assert tween["writes"] == 1 and tween["refWrites"] > 10
    assert tween["equal"] and tween["labelsEqual"] and tween["wrapperAfter"] == ""


@needs_node
def test_the_wrapper_moves_only_in_a_parent_that_clips_it(sample: Sample, tmp_path: Path) -> None:
    moved = drive(sample_page(sample, tmp_path), tmp_path)["moved"]
    # Before the change, the page kept the result of the first check. Thus the
    # wrapper moved also in a parent that does not clip it.
    assert moved["during"] == 20 and moved["wrapper"] == ""
    assert moved["backDuring"] == 0 and "scale(" in moved["backWrapper"]


@needs_node
def test_a_line_reveal_reads_all_lengths_before_it_writes(sample: Sample, tmp_path: Path) -> None:
    reveal = drive(sample_page(sample, tmp_path), tmp_path)["reveal"]
    assert reveal["lines"] > 1 and reveal["drawn"] == reveal["lines"]
    assert reveal["writes"] == reveal["lines"]
    # Before the change, the reveal read a length and a box after each write.
    assert reveal["readsAfterWrite"] == 0
