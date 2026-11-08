"""`systemap live` with the canvas page, in a browser (`page_live`, `serve`).

The test renders the fixture of tests/test_nest_join.py with the default setting
(`serve.render_tree`), and supplies it with the server of `systemap live`
(`serve.LiveMap` and `serve.make_live_server`). The driver (tests/canvas_live.js) opens the
canvas page in the Chromium of Playwright with the hash of a card. It asks for a new
version, and then for a version that the command cannot render. The test skips when Node
or Playwright is not there, except when SYSTEMAP_BROWSER_TESTS is "required" (the CI job
canvas-browser).

Acceptance values (acceptance 7 of the default output, docs/design/nested-canvas.md,
step 5, written before the first run):

1. Each load of the page opens 1 event connection, to `/events`.
2. A newer version loads the page 1 time. After the load, the hash is the same
   (`#Gateway/Routes`), and the map Gateway is open.
3. A version that the command cannot render shows the notice "The map is not updated:"
   with the first line of the error, and it does not load the page again.
4. 0 securitypolicyviolation events, 0 script errors, and 0 requests outside the origin
   of the server. The live script runs under the policy of the canvas page
   (`page_csp.with_live_script`), which keeps frame-src 'none'.
5. The pages of a nested map are the small pages, also in the served directory.
"""

from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path

from test_canvas_browser import browser
from test_canvas_page import _made

from systemap import page_csp, serve
from systemap.config import ConfigError

DRIVER = Path(__file__).resolve().parent / "canvas_live.js"
FAILED = "The model cannot load: a test error."


def test_live_reloads_the_canvas_page_and_keeps_the_hash(tmp_path: Path) -> None:
    """Acceptance 1 to 5."""
    root = _made(tmp_path / "repo", "")
    flag = tmp_path / "fail"

    def render() -> serve.Rendered:
        if flag.exists():
            raise ConfigError(FAILED + "\nThe second line.")
        return serve.render_tree(root, "")

    live = serve.LiveMap(tmp_path / "out", render, lambda _event: None)
    httpd = serve.make_live_server(live, 0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        live.request()
        live.wait(120)
        top = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
        nested = (tmp_path / "out" / "Gateway" / "index.html").read_text(encoding="utf-8")
        assert '<canvas id="canvas"' in top and "<canvas" not in nested
        policy = page_csp.of_page(top).split("; ")
        assert "frame-src 'none'" in policy and "connect-src 'self'" in policy
        proc = subprocess.run(
            [browser(), str(DRIVER), live.url + "index.html", "#Gateway/Routes", str(flag)],
            capture_output=True,
            text=True,
            timeout=240,
        )
    finally:
        httpd.shutdown()
        httpd.server_close()
        live.close()
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["violations"] == [] and out["errors"] == [] and out["outside"] == [], out
    assert out["sources"] == ["/events", "/events"], out
    assert out["navigations"] == 2, out
    assert [load["hash"] for load in out["loads"]] == ["#Gateway/Routes", "#Gateway/Routes"]
    assert all(load["chain"] == ["Gateway"] for load in out["loads"]), out
    assert out["notice"] == "The map is not updated: " + FAILED
