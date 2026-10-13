"""Model IDs that are names of JavaScript object properties do not change the map script.

Acceptance (Codex results schematic-10 and schematic-11, and the same pattern):

- schematic-10: with a custom layer named `__proto__`, the detail data in the script has
  an own record for the layer. When the reader selects the layer, its one flow shows,
  and the layer gives the two components at the ends of that flow.
- schematic-11: on a map without such components, a link to `#toString`,
  `#constructor`, `#hasOwnProperty` or `#__proto__` gives no exception and selects no
  component.
- The same pattern: on a map with a component named `constructor` and no flow to it,
  a selection of `Reader` dims the `constructor` card, and a layer without the card
  makes the card quiet.

The tests operate the generated script under Node, with the DOM of tests/page_driver.js.
They do not operate a browser.
"""

from __future__ import annotations

import dataclasses
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from conftest import COL, ROW, Sample
from test_keyboard import needs_node
from test_schematic_names import change_layer_sample

from systemap.model import Component
from systemap.schematic import interactive_script
from systemap.schematic import render as render_schematic

DRIVER = Path(__file__).resolve().parent / "schematic_keys_driver.js"
LINKS = ("toString", "constructor", "hasOwnProperty", "__proto__")
EMPTY = "constructor"


def drive(tmp_path: Path, s: Sample, layer: str, card: str) -> dict[str, Any]:
    """Write a page with the map and its script, and operate the script."""
    svg, detail = render_schematic(s.model, s.meaning, s.theme, s.facts)
    script = interactive_script(s.theme, "schematic", "panel", detail)
    page = tmp_path / "figure.html"
    page.write_text(
        f'<!doctype html><html><head></head><body>{svg}<div id="panel"></div>{script}'
        "</body></html>",
        encoding="utf-8",
    )
    args = [shutil.which("node") or "node", str(DRIVER), str(page), layer, card, *LINKS]
    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert proc.returncode == 0, proc.stderr
    report: dict[str, Any] = json.loads(proc.stdout)
    return report


@needs_node
def test_a_layer_named_proto_shows_its_flow(sample: Sample, tmp_path: Path) -> None:
    s, _t = change_layer_sample(sample, "__proto__")
    record = [
        i for i, f in enumerate(s.model.flows) if s.meaning.layer_for(f, f.kind) == "__proto__"
    ]
    assert record == [3]
    report = drive(tmp_path, s, "__proto__", "Reader")
    assert report["shown"] == record
    assert sorted(report["layerIds"]) == ["Ledger", "Writer"]


@needs_node
def test_a_link_to_an_object_property_selects_nothing(sample: Sample, tmp_path: Path) -> None:
    report = drive(tmp_path, sample, "all", "Reader")
    assert report["links"] == {name: {"value": ""} for name in LINKS}


@needs_node
def test_a_component_named_constructor_dims_and_goes_quiet(sample: Sample, tmp_path: Path) -> None:
    lone = Component(EMPTY, "Has no flow.", region="work", x=COL["c3"], y=ROW["r1"])
    model = dataclasses.replace(sample.model, components=(*sample.model.components, lone))
    meaning = dataclasses.replace(sample.meaning, plain={**sample.meaning.plain, EMPTY: "none"})
    s = dataclasses.replace(sample, model=model, meaning=meaning)
    report = drive(tmp_path, s, "record", "Reader")
    assert report["links"]["constructor"] == {"value": EMPTY}
    assert EMPTY in report["quiet"]
    assert EMPTY in report["dimmed"]["value"]
