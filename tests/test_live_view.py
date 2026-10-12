"""The script of `systemap live` loads the page again and keeps the view of the reader.

Acceptance: after a `rendered` event with a newer version, the new page has the same
view, layer, selected component and flow, sequence and step, Changes selection, and
camera. An event with the version of the page does not load it again. A failed render
shows a notice. After a broken connection, the script closes the connection and does
not load the page again. A saved component that the new page does not have stays clear.
The Node harness in tests/page_driver.js runs the page scripts.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import Sample
from test_changes_view import COMPARISON
from test_keyboard import DRIVER

from systemap import page, page_live


def drive(html: str, tmp_path: Path) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("the page script needs Node")
    out = tmp_path / "index.html"
    out.write_text(html, encoding="utf-8")
    proc = subprocess.run(
        [node, str(DRIVER), str(out), "--scenario", "live"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return dict(json.loads(proc.stdout))


@pytest.fixture
def report(sample: Sample, tmp_path: Path) -> dict[str, Any]:
    html = page.build(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, COMPARISON
    )
    return drive(page_live.with_script(html, 3), tmp_path)


def test_the_page_opens_one_event_connection(report: dict[str, Any]) -> None:
    assert report["sources"] == 1
    assert report["url"] == "/events"


@pytest.mark.parametrize("view", ["map", "trace", "change"])
def test_a_newer_render_loads_the_page_again_with_the_same_view(
    report: dict[str, Any], view: str
) -> None:
    cycle = report[view]
    assert cycle["sameVersionReloads"] == 0, "the version of the page does not load it again"
    assert cycle["reloads"] == 1
    assert cycle["stored"] == 1, "the view is in the session storage before the load"
    assert cycle["storedAfter"] == 0, "the new page removes the saved view"
    assert cycle["after"] == cycle["before"]


def test_the_views_are_different_from_the_first_view(report: dict[str, Any]) -> None:
    """The three cases do not compare the default view with itself."""
    first = report["map"]["before"]
    assert first["mode"] == "understand" and first["focus"] and first["edge"]
    assert first["layer"] != "all" and first["fit"] is False
    trace = report["trace"]["before"]
    assert trace["mode"] == "trace"
    assert trace["journey"] == {"j": 0, "s": 1, "view": "steps"}
    change = report["change"]["before"]
    assert change["mode"] == "change"
    assert change["change"]["focus"] and change["change"]["fit"] is False


def test_a_failed_render_shows_a_notice_and_a_broken_connection_stops(
    report: dict[str, Any],
) -> None:
    assert report["notice"] == "The map is not updated: map/model.py could not import"
    assert report["noticeRole"] == "status"
    assert report["closed"] is True
    assert report["reloadsAfterClose"] == 0


def test_a_saved_component_that_the_page_does_not_have_stays_clear(
    report: dict[str, Any],
) -> None:
    unknown = report["unknown"]
    assert unknown["focus"] == ""
    assert unknown["layer"] == unknown["firstLayer"]
    assert unknown["stored"] == 0


def test_the_page_of_systemap_render_has_no_live_script(sample: Sample) -> None:
    html = page.build(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, COMPARISON
    )
    assert page_live.VIEW_KEY not in html and "EventSource" not in html
    live = page_live.with_script(html, 7)
    assert live.endswith("</script></body></html>\n")
    assert "var VERSION = 7," in live
