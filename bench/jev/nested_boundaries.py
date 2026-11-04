"""M14 and M16 of the nested parts design: the contrast of the new marks, and the same-side rule.

Acceptance (written before the run, from the design of the nested parts, section
"Measurements"):

- M14. Each new text mark of a nested map has a contrast of at least 4.5:1 on its ground,
  and each new line has at least 3:1, in Ink (`dark`) and in Paper (`light`). The marks
  and their grounds are the table `schematic_nested.MARK_COLOURS`. The test
  `tests/test_theme.py::test_the_marks_of_a_nested_map_clear_their_contrast_floor`
  examines the same table.
- M16. After `systemap place` on a new copy of each fixture, 100 percent of the neighbour
  actors of the nested maps are in the band (top, right, bottom, or left of the frame)
  that agrees with the direction from the opening card to that component in the parent
  layout (`place_nested.parent_sides` against `place_nested.band_of`).

The fixtures for M16 are the nested fixture of tests/test_nested.py (3 maps) and the
fixture of tests/three_levels.py with the default sizes (11 maps on 4 levels) and with
3 parts of 3 (22 maps). The script writes each fixture in a new temporary folder and
sends no data out.

Run from the repository root: uv run python bench/jev/nested_boundaries.py
"""

from __future__ import annotations

import sys
import tempfile
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests"))

import test_nested  # noqa: E402
import three_levels  # noqa: E402

from systemap import config, nest, place_nested, schematic_nested  # noqa: E402
from systemap import theme as theme_mod  # noqa: E402
from systemap.cli import main  # noqa: E402


def _luminance(colour: str) -> float:
    out = []
    for i in (1, 3, 5):
        c = int(colour[i : i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = out
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def m14() -> bool:
    passed = True
    print("M14: contrast of the new marks")
    print("| Mark | Token | Ground | Floor | Ink | Paper |")
    print("|---|---|---|---|---|---|")
    for what, token, ground, floor in schematic_nested.MARK_COLOURS:
        cells = []
        for scheme in ("dark", "light"):
            t = theme_mod.SCHEMES[scheme]
            base = theme_mod.Palette(t).actor()[0] if ground == "actor" else str(t[ground])
            ratio = contrast(str(t[token]), base)
            passed = passed and ratio >= floor
            cells.append(f"{ratio:.2f}")
        print(f"| {what} | {token} | {ground} | {floor} | {' | '.join(cells)} |")
    return passed


def _write(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text), encoding="utf-8")


def _same_side(root: Path) -> tuple[int, int, int, list[str]]:
    """Give the agreeing actors, all actors, the maps, and each actor in a different band."""
    assert main(["--root", str(root), "place"]) == 0
    tree = nest.load(config.load(root))
    agree = total = 0
    wrong: list[str] = []
    for m in tree.maps[1:]:
        parent = tree.parent_of(m)
        assert parent is not None
        actors = [c.id for c in m.model.components if c.kind == "actor"]
        sides = place_nested.parent_sides(parent.model, m.card, actors) or {}
        for cid in actors:
            total += 1
            band = place_nested.band_of(m.model, cid)
            if band == sides.get(cid):
                agree += 1
            else:
                wrong.append(f"{m.id}: {cid} is {band}, parent direction {sides.get(cid)}")
    return agree, total, len(tree.maps) - 1, wrong


def m16() -> bool:
    fixtures = {
        "tests/test_nested.py": {
            **test_nested.TREE,
            "systemap.toml": test_nested.CONFIG,
            **test_nested.MODELS,
        },
        "tests/three_levels.py, 2 parts of 2": three_levels.files(2, 2),
        "tests/three_levels.py, 3 parts of 3": three_levels.files(3, 3),
    }
    passed = True
    print("M16: the same-side rule")
    print("| Fixture | Nested maps | Actors | In the agreeing band |")
    print("|---|---|---|---|")
    for name, files in fixtures.items():
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, files)
            agree, total, maps, wrong = _same_side(root)
        passed = passed and agree == total
        print(
            f"| {name} | {maps} | {total} | {agree} ({100 * agree / max(total, 1):.0f} percent) |"
        )
        for line in wrong:
            print(f"  {line}")
    return passed


if __name__ == "__main__":
    first, second = m14(), m16()
    print(f"M14: {'pass' if first else 'fail'}")
    print(f"M16: {'pass' if second else 'fail'}")
