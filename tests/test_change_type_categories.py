"""The Changes panel gives the source category of each changed type (Codex result page-6).

Before this change, the panel called each name in the `types` bucket a class. The
bucket also holds the TypeScript interfaces, enums, and type aliases from the `types`
fact. Thus the panel said "Added classes" for an added interface.

Acceptance: for a Python fixture and a TypeScript fixture, the panel text of the
component says "Added types" and does not contain "classes". Each added name has the
category that the facts give: `class` from the `classes` fact, and `interface`, `enum`,
or `type alias` from the `types` fact.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from conftest import Sample
from test_changes_view import COMPARISON, drive

from systemap import change, extract, page
from systemap.typescript import TYPESCRIPT

PANEL = r"""
function panel(page) {
  const {doc} = page, A = doc.getElementById('changemap').systemap;
  A.select('Reader');
  return {text: doc.getElementById('change-panel').textContent};
}
"""

PYTHON_HEAD = "class Ledger:\n    def record(self) -> None:\n        pass\n"
TYPESCRIPT_HEAD = (
    "export interface User { name: string }\n"
    "export enum Color { Red }\n"
    "export type Id = string;\n"
    "export class Store { public save(): void {} }\n"
)


def _categories(delta: dict[str, Any] | None) -> dict[str, list[str]]:
    assert delta is not None
    surface, _unknown = change._component_surface(["pkg.reader"], {"pkg.reader": delta})
    assert surface["added"]["types"]
    return dict(surface["categories"])


def _panel(sample: Sample, tmp_path: Path, delta: dict[str, Any] | None) -> str:
    assert delta is not None
    surface, _unknown = change._component_surface(["pkg.reader"], {"pkg.reader": delta})
    record = {"modules": ["pkg.reader"], "gained": {}, "surface": surface}
    ch = {**COMPARISON, "per_component": {"Reader": record}}
    html = page.build(sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, ch)
    return str(drive(html, tmp_path, "#changes", "panel", PANEL)["text"])


def test_the_python_change_gives_the_class_category(sample: Sample, tmp_path: Path) -> None:
    delta = change.surface_delta("", PYTHON_HEAD, extract.PYTHON, "pkg/reader.py")
    assert _categories(delta) == {"Ledger": ["class"]}
    text = _panel(sample, tmp_path, delta)
    assert "Added types: Ledger (class)." in text
    assert "classes" not in text


def test_the_typescript_change_gives_each_type_category(sample: Sample, tmp_path: Path) -> None:
    delta = change.surface_delta("", TYPESCRIPT_HEAD, TYPESCRIPT, "src/reader.ts")
    assert _categories(delta) == {
        "Color": ["enum"],
        "Id": ["type_alias"],
        "Store": ["class"],
        "User": ["interface"],
    }
    text = _panel(sample, tmp_path, delta)
    assert "Added types: Color (enum), Id (type alias), Store (class), User (interface)." in text
    assert "classes" not in text


def test_a_removed_type_gets_its_category_from_the_base(sample: Sample, tmp_path: Path) -> None:
    delta = change.surface_delta(TYPESCRIPT_HEAD, "", TYPESCRIPT, "src/reader.ts")
    assert delta is not None
    assert delta["removed"]["types"] == ["Color", "Id", "Store", "User"]
    assert _removed_categories(delta) == {
        "Color": ["enum"],
        "Id": ["type_alias"],
        "Store": ["class"],
        "User": ["interface"],
    }


def _removed_categories(delta: dict[str, Any]) -> dict[str, list[str]]:
    surface, _unknown = change._component_surface(["pkg.reader"], {"pkg.reader": delta})
    return dict(surface["categories"])
