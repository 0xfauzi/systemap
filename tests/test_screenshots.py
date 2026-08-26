"""The screenshots the README embeds exist, at the size the README states,
and the tour is what the script says it is.

`scripts/screenshots.py` is run by hand (it needs Chrome and ffmpeg); this
test holds what it wrote to its claims: two PNGs of 1600 by 900, one per
scheme; a tour whose every state names a reading or a card the model has,
so a renamed card cannot leave the tour showing nothing.
"""

from __future__ import annotations

import importlib.util
import re
import struct
import sys
from pathlib import Path
from types import ModuleType

from systemap import config, nest
from systemap.model import all_layers

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "docs" / "screenshots"
SCRIPT = ROOT / "scripts" / "screenshots.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("screenshots", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["screenshots"] = module
    spec.loader.exec_module(module)
    return module


def png_size(path: Path) -> tuple[int, int]:
    raw = path.read_bytes()
    assert raw[:8] == b"\x89PNG\r\n\x1a\n", path
    assert raw[12:16] == b"IHDR"
    width, height = struct.unpack(">II", raw[16:24])
    return width, height


def test_both_schemes_are_photographed_at_the_stated_size() -> None:
    for name in ("dark", "light"):
        assert png_size(SHOTS / f"{name}.png") == (1600, 900), name


def test_every_tour_state_names_a_reading_or_a_card_the_model_has() -> None:
    script = load_script()
    cfg = config.load(ROOT)
    m = nest.load(cfg).top
    layers = {layer.id for layer in all_layers(m.model, m.meaning)} | {"all"}
    cards = {c.id for c in m.model.components}
    names = [name for name, _ in script.TOUR]
    assert len(names) == len(set(names))
    for name, actions in script.TOUR:
        for layer in re.findall(r"layer\('([^']+)'\)", actions):
            assert layer in layers, (name, layer)
        for card in re.findall(r"A\.select\('([^']+)'\)", actions):
            assert card in cards, (name, card)
        for k in re.findall(r"journey\((\d+)\)", actions):
            assert int(k) < len(m.meaning.journeys), (name, k)
    assert any("journey(" in a for _, a in script.TOUR)
    assert any("A.select(" in a for _, a in script.TOUR)
    assert sum(1 for _, a in script.TOUR if "layer(" in a) >= len(layers) - 1


def test_the_readme_embeds_what_the_script_writes() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for rel in ("docs/screenshots/dark.png", "docs/screenshots/light.png"):
        assert rel in readme, rel
        assert (ROOT / rel).is_file(), rel
