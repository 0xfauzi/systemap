"""The pages of a map tree: a link goes to the page of a nested map.

The Node driver runs the page scripts of the `nested` fixture. Each map has its own
page, and the page has no frame. The U key goes to the parent map, and the T key opens
the Map tree panel."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from test_keyboard import DRIVER, needs_node
from test_nested import nested  # noqa: F401 - a fixture

from systemap.cli import main


def run(*argv: str) -> int:
    return main(list(argv))


def _drive(page: Path, scenario: str) -> dict[str, Any]:
    args = [shutil.which("node") or "node", str(DRIVER), str(page), "--scenario", scenario]
    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert proc.returncode == 0, proc.stderr
    report: dict[str, Any] = json.loads(proc.stdout)
    return report


@needs_node
def test_the_map_inside_a_card_is_a_linked_page(nested: Path) -> None:  # noqa: F811
    """The Node driver: the panel's preview and Open map link; the link, a
    double-click and a second Enter go to the page of the map inside, and the
    page has no frame; in the Changes view the links add #changes; T opens the
    Map tree panel; a card without a map is left alone by the same keys."""
    assert run("--root", str(nested), "refresh") == 0
    report = _drive(nested / "docs/map/index.html", "submap")
    # The first opening card in reading order, whichever place put on top.
    card = report["id"]
    # The cards of its own, and the rectangles of the compact preview: one for each own card.
    inside = {"Gateway": (3, 3), "Style": (2, 2)}[card]
    href = f"{card}/index.html"
    assert report["href"] == href
    assert report["frames"] == 0 and report["overlays"] == 0
    has = report["panelHas"]
    assert has["opens"] == f"Map inside: {card} ({inside[0]} cards)"
    assert has["preview"] is True and has["previewId"] == f"preview-{card}"
    assert has["previewCards"] == inside[1] and has["previewInert"] is True
    assert (has["links"], has["buttons"], has["linkText"]) == (1, 0, "Open map")
    assert has["linkHref"] == href
    assert report["linkPrevented"] is False, "the browser follows the Open map link"
    assert report["enterPrevented"] is False, "Enter on the link is the link's own action"
    steps = {s["label"]: s for s in report["steps"]}
    for label in ("start", "selected", "link", "enter-once", "plain-enter-twice"):
        assert steps[label]["went"] == "", label
    for label in ("dblclick", "enter-twice"):
        assert steps[label]["went"] == href, label
    assert steps["enter-once"]["focus"] == card
    assert steps["plain-enter-twice"]["focus"] == report["plainId"]
    assert steps["change-open"]["went"] == f"{href}#changes"
    assert report["changeHrefs"] == ["Gateway/index.html#changes", "Style/index.html#changes"]
    assert report["mapHrefs"] == ["Gateway/index.html", "Style/index.html"]
    keys = report["keys"]
    assert keys["path"] == "" and keys["hasList"] is True
    assert keys["typing"] == {"went": "", "open": False}, "a text field stops the keys"
    assert keys["ctrl"] == ""
    assert keys["tPrevented"] is True and keys["listOpen"] is True
    assert keys["active"] == "summary"
    assert keys["uPrevented"] is False and keys["up"] == "", "the top map has no parent"


@needs_node
def test_the_u_key_goes_to_the_parent_map(nested: Path) -> None:  # noqa: F811
    """On a nested page, U goes to the parent page and selects the opening card.
    A page without child maps also has the Map tree panel, so T opens it."""
    assert run("--root", str(nested), "refresh") == 0
    keys = _drive(nested / "docs/map/Gateway/index.html", "pathkeys")
    assert keys["path"] == "../index.html#Gateway" and keys["hasList"] is True
    assert keys["typing"] == {"went": "", "open": False}
    assert keys["ctrl"] == "", "a modifier key stops the keys"
    assert keys["tPrevented"] is True and keys["listOpen"] is True
    assert keys["uPrevented"] is True and keys["up"] == "../index.html#Gateway"
    assert keys["capital"] == "../index.html#Gateway"
