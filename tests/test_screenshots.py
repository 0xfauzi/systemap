"""The screenshots the README embeds exist, at the size the README states,
and the tour is what the script says it is.

`scripts/screenshots.py` is run by hand (it needs Chrome and ffmpeg); this
test holds what it wrote to its claims: three PNGs of 1600 by 900, one
per scheme; a GIF under four megabytes; a tour whose every state names a
reading or a card the model has, so a renamed card cannot leave the tour
showing nothing.
"""

from __future__ import annotations

import importlib.util
import json
import re
import struct
import sys
from pathlib import Path
from types import ModuleType

from systemap import config, nest
from systemap import theme as theme_mod
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


def test_every_scheme_is_photographed_at_the_stated_size() -> None:
    assert list(theme_mod.SCHEMES) == ["warm", "graphite", "paper"]
    for name in theme_mod.SCHEMES:
        assert png_size(SHOTS / f"{name}.png") == (1600, 900), name
    for old in ("dark", "light"):
        assert not (SHOTS / f"{old}.png").exists(), "the 0.11 names are gone"


def test_the_tour_is_a_gif_under_the_limit() -> None:
    gif = SHOTS / "tour.gif"
    raw = gif.read_bytes()
    assert raw[:6] == b"GIF89a"
    assert len(raw) <= 4 * 1024 * 1024, f"tour.gif is {len(raw) / 1024 / 1024:.2f} MB"
    # Every frame is one state, on screen for the stated seconds: the
    # graphic control extension carries the delay in hundredths.
    delays = [
        d
        for (d,) in struct.iter_unpack("<H", b"".join(re.findall(rb"\x21\xf9\x04.(..)", raw, re.S)))
    ]
    script = load_script()
    assert len(delays) == len(script.TOUR), "one frame per state"
    assert sum(delays) / 100 == len(script.TOUR) * script.SECONDS_PER_STATE
    assert 28 <= sum(delays) / 100 <= 32, "thirty seconds"


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
    for rel in (
        "docs/screenshots/tour.gif",
        "docs/screenshots/warm.png",
        "docs/screenshots/graphite.png",
        "docs/screenshots/paper.png",
    ):
        assert rel in readme, rel
        assert (ROOT / rel).is_file(), rel
    assert "[docs/benchmarks.md](docs/benchmarks.md)" in readme
    # Python, and only Python, is said before a reader has scrolled.
    assert "Python" in readme[:1200] and "only Python" in readme
    # Every cost the README quotes is a cost bench/results.jsonl holds, so the
    # sales line and the measurements cannot drift apart. The maintenance runs
    # are quoted one by one and the first maps as a range.
    rows = [
        json.loads(line)
        for line in (ROOT / "bench" / "results.jsonl").read_text().splitlines()
        if line.strip()
    ]
    quoted = re.search(
        r"that path cost ([\d., and]+) dollars, against\s+between (\d+) and (\d+) dollars",
        readme.replace("\n", " "),
    )
    assert quoted, "the README no longer quotes the measured costs in the form the test reads"
    said = {float(v) for v in re.findall(r"\d+\.\d+", quoted.group(1))}
    measured = {round(r["dollars"], 2) for r in rows if r["mode"].startswith("maintenance")}
    assert said == measured, (said, measured)
    firsts = [r["dollars"] for r in rows if r["mode"] == "first-map"]
    low, high = int(quoted.group(2)), int(quoted.group(3))
    assert low <= min(firsts) and max(firsts) <= high, (low, high, min(firsts), max(firsts))


def test_the_readme_names_every_image_absolutely() -> None:
    """PyPI shows the README with no repository to resolve a path against.

    A relative `src` renders on GitHub and breaks on the project page, which
    is the same file, so every image the README shows is named by its full
    URL.
    """
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    relative = [
        url
        for url in re.findall(r'(?:src|srcset)="([^"]+)"', readme)
        if not url.startswith("http")
    ]
    assert not relative, relative
    raw = "https://raw.githubusercontent.com/0xfauzi/systemap/main/"
    for url in re.findall(rf'(?:src|srcset)="({re.escape(raw)}[^"]+)"', readme):
        assert (ROOT / url[len(raw) :]).is_file(), url
