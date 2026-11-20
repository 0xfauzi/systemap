"""The shared parts of the T0 scripts: the pages and the test hook of the measurements.

The T0 scripts (bench/jev/t0_*.py) measure the atlas page of the self map, of the
workspace fixture (tests/fixture_workspace.py, as tests/test_atlas_browser.py builds it)
and of the generated M11 tree. To read the values of the page script that the page API
(`window.systemapCanvas`) does not give, a T0 page has one more line at the end of its
script: `window.__T0` gives some functions and values of the script to the measurement.
The line changes nothing on the page. A T0 page can also have changes of the script text
(`edits`, for the scratch changes of a measurement) and of the page data (`shape`). The
product code does not change: the scripts change only the text and the data of the page
that they write in a temporary directory.

This module has no acceptance value. It is a part of a baseline measurement for target
setting.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(HERE))

from systemap import (  # noqa: E402
    atlas_data,
    atlas_page,
    canvas_page,
    config,
    facts_file,
    nest,
    place,
)

HOOK = (
    "window.__T0 = {MAPS: MAPS, TOP: TOP, ORDER: ORDER, linesOf: linesOf, seatsOf: seatsOf,"
    " walls: walls, shownLayer: shownLayer, view: view, unitWidth: unitWidth, crossed: crossed,"
    " over: over, segLen: segLen, frameOf: frameOf, labelPx: labelPx,"
    " get cam() { return cam; }, get HEAD_H() { return HEAD_H; }, get SEQ() { return SEQ; },"
    " stepState: stepState, smDraw: smDraw, get SM() { return SM; },"
    " setSmMax: function (v) { SM_MAX = v; }};\n"
)
END = "})();"

Data = dict[str, Any]
Theme = dict[str, Any]


def node() -> str:
    """Give the node command. Stop with the failure when it is not there."""
    found = shutil.which("node")
    if found is None:
        raise SystemExit("failure: the node command is not on the PATH")
    return found


def self_data() -> tuple[Theme, Data]:
    """The theme and the atlas data of the map of this repository."""
    cfg = config.load(ROOT)
    tree = nest.load(cfg)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    return canvas_page.tree_theme(cfg, tree), atlas_data.build(cfg, tree, facts)


def workspace_data() -> tuple[Theme, Data]:
    """The theme and the atlas data of tests/fixture_workspace.py with the positions of the
    placer, as the fixture `workspace_page` of tests/test_atlas_browser.py makes them."""
    import fixture_workspace as fw  # noqa: PLC0415

    laid = place.apply(fw.MODEL, place.compute(fw.MODEL, all_cards=True))
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "systemap.toml").write_text('name = "workspace"\n', encoding="utf-8")
        cfg = config.load(Path(tmp))
    theme = nest.load(config.load(ROOT)).top.theme
    one = nest.Map(
        id="", path=Path("m.py"), rel="m.py", model=laid, meaning=fw.MEANING, theme=theme
    )
    tree = nest.Tree(maps=(one,))
    return canvas_page.tree_theme(cfg, tree), atlas_data.build(cfg, tree, fw.facts())


def m11_data() -> tuple[Theme, Data]:
    """The theme and the data of the generated M11 tree (bench/jev/canvas_frames.py)."""
    import canvas_frames  # noqa: PLC0415

    return nest.load(config.load(ROOT)).top.theme, canvas_frames.m11_tree()


def write(
    out: Path,
    theme: Theme,
    data: Data,
    edits: tuple[tuple[str, str], ...] = (),
    shape: Callable[[Data], None] | None = None,
) -> Path:
    """Write a T0 page: the atlas page with the hook, the script edits and the data change."""
    kept = atlas_page._SCRIPT
    text = kept
    for old, new in edits:
        if text.count(old) != 1:
            raise SystemExit(f"failure: the script has the text {old!r} {text.count(old)} times")
        text = text.replace(old, new)
    if not text.endswith(END):
        raise SystemExit("failure: the script does not end with the expected text")
    atlas_page._SCRIPT = text[: -len(END)] + HOOK + END
    try:
        page_data = json.loads(json.dumps(data))
        if shape is not None:
            shape(page_data)
        out.write_text(atlas_page.build(theme, page_data), encoding="utf-8")
    finally:
        atlas_page._SCRIPT = kept
    return out


def drive(driver: Path, *args: str) -> Any:
    """Run a node driver and give its JSON output. Stop with the failure of the driver."""
    env = dict(os.environ)
    proc = subprocess.run(
        [node(), str(driver), *args], capture_output=True, text=True, timeout=1200, env=env
    )
    if proc.returncode != 0:
        raise SystemExit("failure of " + driver.name + ":\n" + (proc.stderr or proc.stdout))
    out = json.loads(proc.stdout)
    if isinstance(out, dict) and out.get("errors"):
        raise SystemExit(f"failure: script errors on the page: {out['errors']}")
    return out
