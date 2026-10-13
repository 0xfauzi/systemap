"""The page and its scripts: the repairs for the Codex results page-1 to page-10.

Acceptance:

- page-1: a child map preview of a card with the ID `A" onload="alert(1)`, and with a
  component of that ID, has no `onload` attribute.
- page-2: a page with a flow artifact `constructor` operates its scripts without an
  error, and the flow is in a flow group.
- page-3: after a live load, a saved sequence or flow that the new page does not have
  gives no selection. A saved flow that the new page has stays selected.
- page-4: at a width of 600 pixels, the W key in the step overlay shows the whole route.
- page-5: while the step overlay is open, the ? key and the Keyboard keys button do not
  open the keyboard sheet, and the right arrow key goes from the whole route to step 1.
  After the overlay closes, the ? key opens the sheet.
- page-7: an entry point that is the same console script under another name is not in
  the coverage total. The covered count is the number of counted entry points with a
  sequence. The count is correct for Python and TypeScript entry points.
- page-8: a component with the symbol claim `pkg.cli:main` lists the entry points with
  the module `pkg.cli` and the target `main`, and no other entry point of that module.
- page-9: a changed flow with source references and no review digest does not get the
  text about a recorded source review. Its text gives the missing review digest.
- page-10: `page_phone` has no unused `_esc` function.

The Node harness in tests/page_driver.js operates the page scripts.
"""

from __future__ import annotations

import dataclasses
import json
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest
from conftest import Sample
from test_changes_view import COMPARISON
from test_changes_view import drive as drive_changes

from systemap import nest, page, page_data, page_live, page_phone, page_sequences
from systemap import theme as theme_mod
from systemap.model import Component, Flow, Model, all_layers
from systemap.source_facts import entry_identity

DRIVER = Path(__file__).with_name("page_driver.js")
SCENARIOS = "const scenarios = {keyboard, framing, submap, theme, workspace};"
UNSAFE = 'A" onload="alert(1)'


def drive(html: str, tmp_path: Path, name: str, scenario: str, *flags: str) -> dict[str, Any]:
    """Operate the page scripts under the Node harness with one added scenario."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("the page scripts need Node")
    out = tmp_path / "index.html"
    out.write_text(html, encoding="utf-8")
    driver = DRIVER.read_text(encoding="utf-8")
    assert driver.count(SCENARIOS) == 1
    driver = driver.replace(SCENARIOS, SCENARIOS[:-2] + f", {name}}};")
    harness = tmp_path / f"{name}.js"
    harness.write_text(driver + scenario, encoding="utf-8")
    proc = subprocess.run(
        [node, str(harness), str(out), "--scenario", name, *flags],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return dict(json.loads(proc.stdout))


def built(sample: Sample, ch: dict[str, Any] | None = None, **model: Any) -> str:
    m = dataclasses.replace(sample.model, **model)
    t = theme_mod.resolve({}, all_layers(m, sample.meaning))
    return page.build(sample.cfg, m, sample.meaning, t, sample.facts, ch or {"has_change": False})


# ---- page-1: the preview of a child map ---------------------------------------------


class _Attributes(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.names: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.names.update(name for name, _value in attrs)


def _renamed(sample: Sample, old: str, new: str) -> tuple[Component, ...]:
    return tuple(
        dataclasses.replace(c, id=new) if c.id == old else c for c in sample.model.components
    )


def test_a_preview_has_no_attribute_from_a_card_or_component_id(sample: Sample) -> None:
    flows = tuple(
        dataclasses.replace(
            f,
            src=UNSAFE if f.src == "Reader" else f.src,
            dst=UNSAFE if f.dst == "Reader" else f.dst,
        )
        for f in sample.model.flows
    )
    model = dataclasses.replace(
        sample.model, components=_renamed(sample, "Reader", UNSAFE), flows=flows
    )
    t = theme_mod.resolve({}, all_layers(model, sample.meaning))
    child = nest.Map(
        UNSAFE, Path("map/c.py"), "map/c.py", model, sample.meaning, t, parent="", card=UNSAFE
    )
    svg = page.preview(sample.cfg, child, sample.facts)
    parser = _Attributes()
    parser.feed(svg)
    assert "onload" not in parser.names
    assert svg.startswith('<svg id="preview-') and 'id="preview-A"' not in svg


# ---- page-2: model names that are also object property names -----------------------

GROUPS = r"""
function groups(page) {
  const {A, svg} = page;
  return {groups: svg.page.groups.groups('all').map((g) => g.edges.map((i) => A.edges[i].art))};
}
"""


def test_a_flow_artifact_named_constructor_is_in_a_group(sample: Sample, tmp_path: Path) -> None:
    flows = tuple(
        dataclasses.replace(f, artifact="constructor") if f.artifact == "parts" else f
        for f in sample.model.flows
    )
    report = drive(built(sample, flows=flows), tmp_path, "groups", GROUPS)
    assert any("constructor" in g for g in report["groups"])


# ---- page-3: the live load and a removed sequence or flow ---------------------------

LIVE_GONE = r"""
function livegone(page) {
  const report = {};
  const saved = (extra) => SESSION.set('systemap-live-view', JSON.stringify(Object.assign({
    path: '/index.html', mode: 'understand', layer: 'all', focus: '', edge: null, camera: null,
    journey: null, change: null}, extra)));
  const state = (p) => {
    const e = p.A.edges[p.A.state.edge];
    return {mode: p.svg.page.mode(), j: p.svg.page.journey.state().j, focus: p.A.state.focus,
      edge: e ? e.art : null};
  };
  saved({mode: 'trace', journey: {id: 'no-such-sequence', s: 1, view: 'steps'}});
  report.sequence = state(page.reload(''));
  saved({focus: 'Reader', edge: {from: 'Reader', to: 'Parser', art: 'no-such-artifact'}});
  report.flow = state(page.reload(''));
  saved({focus: 'Reader', edge: {from: 'Reader', to: 'Parser', art: 'parse'}});
  report.kept = state(page.reload(''));
  return report;
}
"""


def test_a_live_load_selects_nothing_for_a_removed_sequence_or_flow(
    sample: Sample, tmp_path: Path
) -> None:
    html = page_live.with_script(built(sample), 3)
    report = drive(html, tmp_path, "livegone", LIVE_GONE)
    assert report["sequence"]["j"] == -1
    assert report["sequence"]["focus"] == ""
    assert report["flow"] == {"mode": "understand", "j": -1, "focus": "", "edge": None}
    assert report["kept"] == {"mode": "understand", "j": -1, "focus": "Reader", "edge": "parse"}


# ---- page-4 and page-5: the step overlay --------------------------------------------

OVERLAY = r"""
function overlay(page) {
  const {doc, svg, key} = page, P = svg.page, S = P.sequence;
  const sheet = () => !doc.getElementById('keys').hidden;
  P.journey.start(0);
  P.present();
  const report = {open: !doc.getElementById('present').hidden};
  key('ArrowRight');
  report.afterRight = S.state();
  key('w');
  report.afterWhole = S.state();
  key('?');
  report.sheetAfterKey = sheet();
  key('ArrowRight');
  report.afterArrow = S.state();
  doc.getElementById('keys-open').click();
  report.sheetAfterButton = sheet();
  key('Escape');
  report.closed = doc.getElementById('present').hidden;
  key('?');
  report.sheetAfterClose = sheet();
  return report;
}
"""


@pytest.mark.parametrize("flags", [(), ("--phone", "--viewport", "600x900")])
def test_the_step_overlay_keeps_the_whole_route_and_its_keys(
    sample: Sample, tmp_path: Path, flags: tuple[str, ...]
) -> None:
    report = drive(built(sample), tmp_path, "overlay", OVERLAY, *flags)
    assert report["open"] is True
    assert report["afterRight"]["view"] == "steps" and report["afterRight"]["s"] == 1
    assert report["afterWhole"]["view"] == "whole"
    assert report["sheetAfterKey"] is False
    assert report["afterArrow"]["view"] == "steps" and report["afterArrow"]["s"] == 0
    assert report["sheetAfterButton"] is False
    assert report["closed"] is True
    assert report["sheetAfterClose"] is True


# ---- page-7: the entry point coverage of the Sequences view -------------------------

# The Python adapter writes `same_as` on the `main` function that a console script starts.
PY_SCRIPT = {
    "kind": "console_script",
    "name": "cli",
    "module": "pkg.cli",
    "target": "main",
    "symbol": "main",
}
PY_POINTS = [
    PY_SCRIPT,
    {
        "kind": "main_function",
        "name": "main",
        "module": "pkg.cli",
        "target": "main",
        "symbol": "main",
        "same_as": entry_identity(PY_SCRIPT),
    },
]
TS_POINTS = [
    {"kind": "console_script", "name": "tool", "module": "src/bin", "target": ""},
    {"kind": "public_function", "name": "run", "module": "src/index", "target": ""},
]


@pytest.mark.parametrize(
    ("points", "covered", "expected"),
    [
        (PY_POINTS, (), {"total": 1, "covered": 0, "missing": ["cli"]}),
        (PY_POINTS, (entry_identity(PY_POINTS[0]),), {"total": 1, "covered": 1, "missing": []}),
        (TS_POINTS, (), {"total": 2, "covered": 0, "missing": ["tool", "run"]}),
        (
            TS_POINTS,
            (entry_identity(TS_POINTS[1]),),
            {"total": 2, "covered": 1, "missing": ["tool"]},
        ),
    ],
)
def test_the_coverage_counts_each_entry_point_one_time(
    sample: Sample, points: list[dict[str, str]], covered: tuple[str, ...], expected: dict[str, Any]
) -> None:
    journey = dataclasses.replace(sample.meaning.journeys[0], covers=covered)
    meaning = dataclasses.replace(sample.meaning, journeys=(journey,))
    facts = {"entry_points": points, "components": {p["module"]: {} for p in points}}
    coverage = page_sequences.data(sample.model, meaning, facts)["coverage"]
    assert {k: coverage[k] for k in expected} == expected


# ---- page-8: the entry points of a component with a symbol claim --------------------


def test_a_symbol_claim_lists_the_entry_points_of_its_target() -> None:
    facts = {
        "components": {"pkg.cli": {"names": [{"name": "main", "kind": "function"}]}},
        "entry_points": [
            *PY_POINTS,
            {"kind": "route", "name": "GET /x", "module": "pkg.cli", "target": "other"},
        ],
    }
    card = Component("Cli", "Reads the command line.", implemented_by=("pkg.cli:main",))
    whole = Component("Whole", "Holds the module.", implemented_by=("pkg.cli",))
    model = Model((100, 100), (), (), (card, whole), (), ())
    out = page_data.sources(model, facts)
    assert out["Cli"]["points"] == ["cli (console script)", "main() in pkg.cli"]
    assert len(out["Whole"]["points"]) == 3


# ---- page-9: the Changes text for a flow without a review digest --------------------

CHANGE_TEXT = r"""
function changetext(page) {
  const {doc} = page, panel = doc.getElementById('change-panel');
  const card = panel.querySelector('[data-change-card="Reader"] .chg-card__note');
  const flows = doc.getElementById('chg-flows');
  return {card: card ? card.textContent : '', flows: flows ? flows.textContent : ''};
}
"""


@pytest.mark.parametrize("digest", ["", "b" * 64])
def test_a_flow_without_a_review_digest_has_no_recorded_review(
    sample: Sample, tmp_path: Path, digest: str
) -> None:
    ref = f"pkg.reader:read@{'a' * 64}"
    flows = tuple(
        Flow(f.src, f.dst, f.artifact, f.kind, source_refs=(ref,), review_digest=digest)
        if (f.src, f.dst) == ("Reader", "Parser")
        else f
        for f in sample.model.flows
    )
    html = built(sample, COMPARISON, flows=flows)
    report = drive_changes(html, tmp_path, "#changes", "changetext", CHANGE_TEXT)
    text = report["card"] + report["flows"]
    if digest:
        assert "recorded source review that does not agree" in report["card"]
        return
    assert "recorded source review" not in text
    assert "1 flow has source references but no review digest." in report["card"]


# ---- page-10: no unused HTML conversion in the phone module -------------------------


def test_the_phone_module_has_no_unused_conversion() -> None:
    assert not hasattr(page_phone, "_esc")
    assert not hasattr(page_phone, "html_mod")
