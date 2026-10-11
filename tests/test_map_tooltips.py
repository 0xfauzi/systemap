"""The map shows no browser tooltips; the legend explains its marks.

A <title> in the page's inline SVG is a tooltip on every shape under it, and the
map's titles only repeated its name. The page removes them and keeps the SVG
aria-label. The legend names the note dot and the mark of a card that opens a
map, only when the view shows such a card. A figure file keeps its titles.
"""

from __future__ import annotations

import dataclasses
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import Sample

from systemap import page
from systemap.schematic import render as render_schematic


def _map_svgs(html: str) -> list[str]:
    return re.findall(r'<svg id="(?:schematic|changemap|preview-[^"]*)".*?</svg>', html, re.S)


def test_the_page_maps_have_no_tooltips_and_keep_their_names(sample: Sample) -> None:
    html = page.build(sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {})
    svgs = _map_svgs(html)
    assert svgs, "the page has a map"
    for svg in svgs:
        assert "<title>" not in svg
        assert 'aria-label="System map.' in svg


def test_a_figure_file_keeps_its_title(sample: Sample) -> None:
    svg, _detail = render_schematic(sample.model, sample.meaning, sample.theme, sample.facts)
    assert "<title>System map</title>" in svg


LEGEND = r"""
function legendmarks(page){
  const {doc,win,svg}=page;
  doc.querySelector('[data-layer-btn="all"]').click();runFrames(win);
  return {legend:doc.getElementById('map-legend').innerHTML,
    quiet:svg.querySelectorAll('.node.quiet, .node.dim').map(n=>n.getAttribute('data-id'))};
}
"""


def _legend(sample: Sample, tmp_path: Path, note: str) -> str:
    node = shutil.which("node")
    if node is None:
        pytest.skip("The JavaScript test requires Node.")
    model = dataclasses.replace(
        sample.model,
        components=tuple(
            dataclasses.replace(c, note=note) if c.id == "Writer" else c
            for c in sample.model.components
        ),
    )
    html = tmp_path / "map.html"
    html.write_text(
        page.build(sample.cfg, model, sample.meaning, sample.theme, sample.facts, {}),
        encoding="utf-8",
    )
    driver = Path(__file__).with_name("page_driver.js").read_text(encoding="utf-8")
    driver = driver.replace(
        "const scenarios = {keyboard, framing, submap, theme, workspace};",
        "const scenarios = {keyboard, framing, submap, theme, workspace, legendmarks};",
    )
    harness = tmp_path / "legendmarks.js"
    harness.write_text(driver + LEGEND, encoding="utf-8")
    result = subprocess.run(
        [node, str(harness), str(html), "--scenario", "legendmarks"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    legend: str = json.loads(result.stdout)["legend"]
    return legend


def test_the_legend_names_the_note_dot_only_when_a_card_has_a_note(
    sample: Sample, tmp_path: Path
) -> None:
    assert "Has a note in Details" in _legend(sample, tmp_path, "the writer keeps no state")
    assert "Has a note in Details" not in _legend(sample, tmp_path, "")
