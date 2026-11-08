"""The small page of a nested map in a browser (`canvas_redirect`).

The test writes the pages of the fixture of tests/test_nest_join.py with the default
setting, and serves them with the server of `systemap serve` (`serve.make_server`). The
server sends the policy of each page in the Content-Security-Policy header. The driver
(tests/canvas_redirect.js) opens the pages in the Chromium of Playwright. The test skips
when Node or Playwright is not there, except when SYSTEMAP_BROWSER_TESTS is "required"
(the CI job canvas-browser).

Acceptance values (acceptance 5 of the default output, docs/design/nested-canvas.md,
step 5):

1. `Gateway/index.html` goes to `index.html#Gateway`. The canvas is at the fit of the map
   Gateway, in the Map view.
2. `Gateway/index.html#Routes` goes to `index.html#Gateway/Routes`. The camera is at the
   card Routes of the map Gateway.
3. Without a script, the refresh meta element goes to `index.html#Gateway`. The small page
   and the canvas page have a link to the map or the canvas.
4. `Gateway/index.html#changes` goes to `index.html#Gateway/changes`, and the canvas opens
   the Changes view at the map Gateway. `index.html#changes` opens the Changes view at the
   top map (the link of `delta_link.CHANGES`).
5. On a page whose top map has a card with the ID `changes`, `#changes` names that card:
   the view stays the Map view, and the hash stays.
6. Each run has 0 securitypolicyviolation events, 0 script errors and 0 requests outside
   the origin of the server.
7. On a phone screen (390 x 844, touch), the move is the same, and the page has no
   horizontal scroll.
8. Added after the verification of step 5, before the run: `Gateway/index.html#Nothing`
   (a card that the map Gateway does not have) goes to `index.html#Gateway/Nothing`. The
   canvas stays in the map Gateway, and the live region tells that no map and no card has
   the link.
9. Added after the second verification of step 5, before the run: at the card Routes of
   item 2, the large card shows its lists: the canvas draws the names FLOWS and MODULES
   in the box of the card at rest, with an alpha of 0.98 or more.
10. Added after the second verification of step 5, before the run: when the map Gateway
    is open and the hash changes to `#Nothing`, the live region keeps the words "No map
    and no card has the link #Nothing" after the camera stops.
"""

from __future__ import annotations

import json
import subprocess
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from test_canvas_browser import browser
from test_canvas_page import _made

from systemap import canvas_data, canvas_page, config, facts_file, nest, serve

DRIVER = Path(__file__).resolve().parent / "canvas_redirect.js"


@pytest.fixture(scope="module")
def origin(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    root = _made(tmp_path_factory.mktemp("redirect"), "")
    cfg = config.load(root)
    tree = nest.load(cfg)
    data = canvas_data.build(cfg, tree, facts_file.read_facts(cfg.facts_path, cfg.root))
    named = json.loads(json.dumps(data).replace('"Log"', '"changes"'))
    page = canvas_page.build(canvas_page.tree_theme(cfg, tree), named)
    (root / "docs" / "map" / "named.html").write_text(page, encoding="utf-8")
    httpd = serve.make_server(root / "docs" / "map", 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def _go(url: str, *flags: str) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), "--go", url, *flags], capture_output=True, text=True, timeout=180
    )
    assert proc.returncode == 0, proc.stderr
    out = dict(json.loads(proc.stdout))
    assert out["violations"] == [], out
    assert out["outside"] == [], out
    assert out["errors"] == [], out
    return out


def test_the_small_page_goes_to_the_map(origin: str) -> None:
    """Acceptance 1 and 6."""
    out = _go(origin + "/Gateway/index.html")
    assert out["url"] == origin + "/index.html#Gateway"
    assert out["chain"] == ["Gateway"] and out["atFit"] and out["view"] == "map"
    assert any(url.endswith("/Gateway/index.html") for url in out["requests"])


def test_the_small_page_keeps_the_hash_of_the_link(origin: str) -> None:
    """Acceptance 2 and 6."""
    out = _go(origin + "/Gateway/index.html#Routes")
    assert out["url"] == origin + "/index.html#Gateway/Routes"
    assert out["hash"] == "#Gateway/Routes"
    assert out["chain"] == ["Gateway"]
    # Acceptance 9.
    assert sorted(out["lists"]) == ["FLOWS", "MODULES"], out["card"]


def test_without_a_script_the_refresh_goes_to_the_map(origin: str) -> None:
    """Acceptance 3 and 6."""
    out = _go(origin + "/Gateway/index.html#Routes", "--no-script")
    assert out["url"] == origin + "/index.html#Gateway"
    assert out["canvas"]


def test_the_changes_link_opens_the_changes_view(origin: str) -> None:
    """Acceptance 4 and 6."""
    nested = _go(origin + "/Gateway/index.html#changes")
    assert nested["url"] == origin + "/index.html#Gateway/changes"
    assert nested["view"] == "changes" and nested["chain"] == ["Gateway"]
    top = _go(origin + "/index.html#changes")
    assert top["view"] == "changes" and top["chain"] == []
    assert top["hash"] == "#changes"


@pytest.mark.parametrize("scheme", ["--light", ""])
def test_the_small_page_on_a_phone(origin: str, scheme: str) -> None:
    """Acceptance 7 and 6."""
    out = _go(origin + "/Gateway/index.html", "--phone", *([scheme] if scheme else []))
    assert out["url"] == origin + "/index.html#Gateway"
    assert out["chain"] == ["Gateway"] and out["atFit"]
    assert out["scroll"] == out["width"] == 390 and out["scrollX"] == 0


def test_a_card_with_the_id_changes_keeps_its_link(origin: str) -> None:
    """Acceptance 5 and 6."""
    out = _go(origin + "/named.html#changes")
    assert out["view"] == "map" and out["chain"] == []
    assert out["hash"] == "#changes"


def test_a_link_to_a_lost_card_stays_in_its_map(origin: str) -> None:
    """Acceptance 8 and 6."""
    out = _go(origin + "/Gateway/index.html#Nothing")
    assert out["chain"] == ["Gateway"] and out["atFit"], out
    said = out["said"]
    assert said.startswith("No map and no card has the link #Gateway/Nothing. Open map: "), said
    assert said.endswith(" / Gateway."), said


def test_a_hash_change_to_a_lost_card_keeps_its_words(origin: str) -> None:
    """Acceptance 10 and 6."""
    out = _go(origin + "/index.html#Gateway", "--then=Nothing")
    said = out["said"]
    assert said.startswith("No map and no card has the link #Nothing. Open map: "), said
