"""The frame time and the load time of the canvas page (C2 and C3 of the nested canvas design).

The test uses the scenarios and the limits of bench/jev/canvas_frames.py. Its docstring
has the acceptance values. The data is generated: a tree with the form of the M11 tree
(50 maps, 40 cards in each map), a map with 400 cards, and a map with 1,500 cards. The
page is the real canvas page. The browser is the Chromium of Playwright with 4 times CPU
throttling. The test fails when a p95 frame interval is more than its limit, or when the
load of the tree takes more than its limit.

The test skips when Node or the Playwright package is not there, except when
SYSTEMAP_BROWSER_TESTS is "required" (the CI job canvas-browser).
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

BENCH = Path(__file__).resolve().parent.parent / "bench" / "jev" / "canvas_frames.py"
RATE = 4


def _bench() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bench_canvas_frames", BENCH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def bench(tmp_path_factory: pytest.TempPathFactory) -> tuple[ModuleType, dict[str, Path]]:
    module = _bench()
    if module.node() is None:
        if os.environ.get("SYSTEMAP_BROWSER_TESTS") == "required":
            pytest.fail("Node with the Playwright package and Chromium is necessary.")
        pytest.skip("the frame test needs Node with the Playwright package and Chromium")
    out = tmp_path_factory.mktemp("frames")
    pages = {
        "M11 shape": module.write_page(module.nested_tree(), out / "tree.html"),
        "400 cards": module.write_page(module.grid_map(400), out / "g400.html"),
        "1,500 cards": module.write_page(module.grid_map(1500), out / "g1500.html"),
    }
    return module, pages


def test_the_generated_tree_has_the_form_of_the_m11_tree() -> None:
    data = _bench().nested_tree()
    assert len(data["maps"]) == 50
    assert {len(m["cards"]) for m in data["maps"]} == {40}
    depth = {m["id"]: m["id"].count("/") + 1 if m["id"] else 0 for m in data["maps"]}
    assert sorted(depth.values()).count(3) == 21


SCENARIOS = [("M11 shape", s) for s in ("pan-fit", "all-open", "dive")] + [
    ("400 cards", "pan-fit"),
    ("400 cards", "dive"),
    ("1,500 cards", "pan-fit"),
]


@pytest.mark.parametrize(("data", "mode"), SCENARIOS)
def test_the_p95_frame_interval_is_in_its_limit(
    bench: tuple[ModuleType, dict[str, Path]], data: str, mode: str
) -> None:
    """C2: p95 at most 33 ms with 4 times CPU throttling (the limit is in the bench script)."""
    module, pages = bench
    found: dict[str, Any] = module.run(pages[data], mode, RATE)
    assert found["frames"] == module.FRAMES
    assert found["p95"] <= module.LIMITS[RATE], found


def test_the_tree_is_interactive_in_its_limit(bench: tuple[ModuleType, dict[str, Path]]) -> None:
    """C3: from the navigation to an interactive map of 50 maps, at most 1.5 s."""
    module, pages = bench
    found: dict[str, Any] = module.run(pages["M11 shape"], "load", 1)
    assert found["ready"] <= module.LOAD_LIMIT, found
