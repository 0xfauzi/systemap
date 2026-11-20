"""The performance budget of the atlas page on the generated tree, in the suite (stage 8).

docs/design/atlas.md, "The performance budget": stage 8 adds a test in the suite that fails
when a limit of the budget fails. The test uses the measurement code of the budget
(bench/jev/atlas_budget.py) and its limits, with no change. The limits come from the gate G1
(bench/jev/README.md): the zoom into a nested map is the measure that the SVG map failed,
thus the dive has the same limit as the pan.

The input is the generated tree with 50 maps (`m11_tree` of bench/jev/canvas_frames.py), with
the atlas page and the canvas page of the same data, measured in the same run on the same
machine, at 4 times CPU slowdown, 1440 x 900, device pixel ratio 1.

The frame intervals are multiples of 16.7 ms, and one run can fail because of other work on
the host (see tests/test_canvas_frames.py). Acceptance values, written on 2026-11-19 before
the first run of this test:

1. The first complete frame (`first`), the pan (`pan`) and the dive (`dive`): one attempt
   measures the canvas page and then the atlas page, and it passes when the atlas value is
   in the limit of the budget against the canvas value of the same attempt (`verdicts` of
   the budget: 1.5 times or less and 1,500 ms or less for the first frame, 1.25 times or less
   or 35 ms or less for the pan and the dive). The value passes when two attempts of three
   pass. The test stops when two attempts pass or when two attempts fail.
   Changed on 2026-11-20 with value 3 of the budget: the dive value of an attempt is the
   share of the frame intervals over 20 ms (`_over` of the budget), and the limit is 1.25
   times or less, or 0.05 or less.
2. The time from a pointer move onto a card to the lit paths (bench/jev/atlas_point.js, the
   largest time of the 8 moves of one run): 100 ms or less in two runs of three.
3. The size of the atlas page file is 1.5 times the size of the canvas page file or less.

The test skips when Node or the Playwright package is not there, except when
SYSTEMAP_BROWSER_TESTS is "required". Then it fails.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

BENCH = Path(__file__).resolve().parent.parent / "bench" / "jev"


def _budget() -> ModuleType:
    sys.path.insert(0, str(BENCH))
    spec = importlib.util.spec_from_file_location("bench_atlas_budget", BENCH / "atlas_budget.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def budget(tmp_path_factory: pytest.TempPathFactory) -> tuple[ModuleType, ModuleType, Path, Path]:
    module = _budget()
    import canvas_frames  # noqa: PLC0415  (a script in bench/jev)

    if canvas_frames.node() is None:
        if os.environ.get("SYSTEMAP_BROWSER_TESTS") == "required":
            pytest.fail(canvas_frames.missing())
        pytest.skip("the frame test needs Node with the Playwright package and Chromium")
    canvas, atlas = module.write_pages("M11 tree", tmp_path_factory.mktemp("atlas-frames"))
    return module, canvas_frames, canvas, atlas


MEASURES = [("load", "first"), ("pan-fit", "pan"), ("dive", "dive")]


@pytest.mark.parametrize(("mode", "name"), MEASURES, ids=[m[1] for m in MEASURES])
def test_the_atlas_page_is_in_the_budget_against_the_canvas_page(
    budget: tuple[ModuleType, ModuleType, Path, Path], mode: str, name: str
) -> None:
    """Acceptance 1."""
    module, frames, canvas, atlas = budget
    key = "ready" if mode == "load" else "p95"
    passed, runs = 0, []
    while passed < 2 and len(runs) - passed < 2:
        pair = (
            (module._over(canvas), module._over(atlas))
            if mode == "dive"
            else (
                float(frames.run(canvas, mode, module.RATE)[key]),
                float(frames.run(atlas, mode, module.RATE)[key]),
            )
        )
        runs.append(pair)
        found = {m: (1.0, 1.0) for m, _n in MEASURES} | {"size": (1.0, 1.0), "point": (0.0, 0.0)}
        found[mode] = pair
        passed += module.verdicts(found)[name]
    assert passed == 2, (name, runs)


def test_the_pointer_lights_the_paths_in_100_ms(
    budget: tuple[ModuleType, ModuleType, Path, Path],
) -> None:
    """Acceptance 2."""
    module, frames, _canvas, atlas = budget
    passed, runs = 0, []
    while passed < 2 and len(runs) - passed < 2:
        proc = subprocess.run(
            [str(frames.node()), str(BENCH / "atlas_point.js"), str(atlas), str(module.RATE)],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        value = float(json.loads(proc.stdout)["max"])
        runs.append(value)
        passed += value <= module.POINT_LIMIT
    assert passed == 2, runs


def test_the_page_file_is_in_the_size_limit(
    budget: tuple[ModuleType, ModuleType, Path, Path],
) -> None:
    """Acceptance 3."""
    module, _frames, canvas, atlas = budget
    assert atlas.stat().st_size <= module.SIZE_FACTOR * canvas.stat().st_size
