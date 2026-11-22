"""The card names of the atlas page and of the check, in a browser.

A Django map had the card ManagementCommands, with no nested map. `systemap check` reported no
error, because the name has 18 characters and the check permitted 20 mono characters at
11.5 px in 140 units. But the atlas page draws a name in Inter at weight 600 and 13.5 units in
129 units, and it showed "ManagementCo...". Now the check and the page use one measure of a
name (`card_names`). The test drives the atlas page of a two-card map at 1440 x 900 in the
Chromium of Playwright (tests/atlas_names.js). The test skips when Node or the Playwright
package is not there, except when SYSTEMAP_BROWSER_TESTS is "required". Then it fails.

Acceptance values, written on 2026-11-20 before the first run of this test:

N1. The check accepts the card name ManageCommands (127 units), and the atlas page shows it in
    full at the fit and at each zoom in ZOOMS, with each card in the middle of the screen: no
    drawn text is the name cut with three dots.
N2. The check gives a warning for the card name ManagementCommands (160 units, 18
    characters), and the atlas page cuts it at a zoom of 1 or less: the same measure gives
    the same result. In this release, the warning does not change the exit code (0). The
    maintainer changed N2 on 2026-11-21: before, the check refused the name with exit code 1.
N3. The page width of each character from 32 to 126 at weight 600 and 100 px with no
    kerning is the width that `NAME_ADVANCES` gives, with a difference of 0.001 px or less.
    Changed on 2026-11-22 after CI: in the Chrome Headless Shell of the CI runner, the
    browser gave each character a width in whole pixels (the space 25 px, not 25.146 px),
    so N3 failed there and passed in the Chromium of the development machine. A browser can
    round the font widths, so the page now measures a card name with `NAME_ADVANCES` itself,
    not with the browser. N3 is now: when each width that the browser measures is 1.3 times
    its value, the page still shows the name of N1 in full at the fit and at each zoom.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import init_two_cards, write_tree
from test_canvas_browser import browser

from systemap.card_names import name_room, name_width
from systemap.cli import main

ROOT = Path(__file__).resolve().parent
DRIVER = ROOT / "atlas_names.js"
ZOOMS = ("0.3", "0.45", "0.6", "0.75", "1", "1.25", "1.6", "2", "3")
FITS = "ManageCommands"
CUT = "ManagementCommands"
MODULES = {
    "pkg/__init__.py": "",
    "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
    "pkg/writer.py": "def write(request: str) -> str:\n    return request\n",
}


def named(root: Path, name: str) -> None:
    """Give the card Reader of the two-card map the name `name`."""
    for rel in ("map/model.py", "map/contract.py"):
        path = root / rel
        path.write_text(
            path.read_text(encoding="utf-8").replace('"Reader"', f'"{name}"'), encoding="utf-8"
        )


def two_cards(root: Path, name: str) -> Path:
    write_tree(root, MODULES)
    init_two_cards(root, "--no-ci")
    named(root, name)
    assert main(["--root", str(root), "extract"]) == 0
    assert main(["--root", str(root), "render"]) == 0
    return root / "docs/map/index.html"


def drive(page: Path, skew: float = 1.0) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), str(page), *ZOOMS],
        capture_output=True,
        text=True,
        timeout=300,
        env={**os.environ, "SKEW": str(skew)},
    )
    assert proc.returncode == 0, proc.stderr
    got = dict(json.loads(proc.stdout))
    assert got["errors"] == [], got["errors"]
    return got


def cut(texts: list[str], name: str) -> bool:
    return any(t.endswith("...") and name.startswith(t[:-3]) and t != name for t in texts)


def test_check_and_page_agree_on_a_name_that_fits(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """N1 and N3."""
    page = two_cards(tmp_path, FITS)
    width = name_width(FITS)
    assert width is not None and 125 < width <= name_room("component")
    assert main(["--root", str(tmp_path), "refresh"]) == 0, capsys.readouterr().out
    assert main(["--root", str(tmp_path), "check"]) == 0, capsys.readouterr().out
    got = drive(page)
    assert FITS in got["cards"]
    assert FITS in got["fit"] and not cut(got["fit"], FITS)
    shown = 0
    for zoom in got["zooms"]:
        assert not cut(zoom["texts"], FITS), (zoom["k"], zoom["card"], zoom["texts"])
        shown += FITS in zoom["texts"]
    assert shown >= len(ZOOMS)
    skewed = drive(page, 1.3)
    assert FITS in skewed["fit"]
    for zoom in skewed["zooms"]:
        assert not cut(zoom["texts"], FITS), (zoom["k"], zoom["card"], zoom["texts"])


def test_check_reports_the_name_that_the_page_cuts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """N2."""
    page = two_cards(tmp_path, CUT)
    assert len(CUT) <= 20
    capsys.readouterr()
    assert main(["--root", str(tmp_path), "refresh"]) == 0, capsys.readouterr().out
    assert main(["--root", str(tmp_path), "check"]) == 0
    out = capsys.readouterr().out
    assert (
        f"warning: card {CUT}: name does not fit on the atlas page (component cards on that page show a "
        "name of 129 units or less on one line, and this one is 160 units)"
    ) in out
    got = drive(page)
    small = [z for z in got["zooms"] if float(z["k"]) <= 1 and z["card"] == CUT]
    assert small and all(cut(z["texts"], CUT) for z in small if CUT[:4] in "".join(z["texts"]))
    assert any(cut(z["texts"], CUT) for z in small)
