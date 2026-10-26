"""The bytes of the map page, its security policy, and the comment marks in theme values.

- uiperf-6: a page with a change map contained two copies of the map code (about 45 KB
  each) and two full copies of the map detail. The page now contains the code one time.
  The change map gets the detail of the system map with a set of changes.
- perf-8: the source records contained `names` and `public_names` with the same names,
  and the page data had a space after each comma and colon.
- xss-1: the page, the figures and the servers gave no Content-Security-Policy.
- regex-5: a theme value with /*, an unpaired quote or a backslash removed page CSS with
  no error.
"""

from __future__ import annotations

import base64
import copy
import dataclasses
import hashlib
import http.client
import json
import re
import shutil
import subprocess
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import Sample, page_detail

from systemap import nest, page, page_csp, page_live, serve
from systemap import theme as theme_mod
from systemap.config import ConfigError
from systemap.schematic import page_maps_script

COMPARISON: dict[str, Any] = {
    "has_change": True,
    "base": "main",
    "head": "feature",
    "direct": {"Reader"},
    "adjacent": set(),
    "modules": {"pkg.reader"},
    "flow_artifacts": set(),
    "per_component": {"Reader": {"modules": ["pkg.reader"], "gained": {"tests": 1}, "surface": {}}},
    "files": 1,
    "reach_known": True,
    "unparsed": [],
}

# A function of the map code. Each copy of the code contains it one time.
ENGINE_MARK = "function recordOf(id)"


def _build(sample: Sample, ch: dict[str, Any]) -> str:
    return page.build(sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, ch)


def _digest(text: str) -> str:
    value = base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode("ascii")
    return f"'sha256-{value}'"


# ---- uiperf-6: one copy of the map code -------------------------------------------


def test_a_page_with_a_change_map_has_one_copy_of_the_map_code(sample: Sample) -> None:
    """Before the fix, the page with a change map had 2 copies of the map code."""
    html = _build(sample, copy.deepcopy(COMPARISON))
    assert 'id="changemap"' in html
    assert html.count(ENGINE_MARK) == 1
    assert html.count("var FIRST = ") == 1
    # The change map gets changes, not a second full detail.
    assert html.count("show(changed(JSON.parse(") == 1
    assert "var DETAIL = JSON.parse(" not in html
    plain = _build(sample, {"has_change": False})
    assert plain.count(ENGINE_MARK) == 1 and "function changed(" not in plain


def _node_details(script: str) -> list[dict[str, Any]]:
    """Run the map script in Node with no SVG element. Give the detail of each call."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("the map script needs Node")
    body = re.fullmatch(r"<script>(.*)</script>", script, re.S)
    assert body is not None
    marked = body.group(1).replace(
        "function show(DETAIL, svgId, panelId){\n",
        "function show(DETAIL, svgId, panelId){\n"
        "OUT.push({json: JSON.stringify(DETAIL), keys: Object.keys(DETAIL),"
        " proto: Object.getPrototypeOf(DETAIL) === Object.prototype});\n",
        1,
    )
    program = (
        "var OUT = [];\nvar document = {getElementById: function(){ return null; }};\n"
        + marked
        + "\nprocess.stdout.write(JSON.stringify(OUT));\n"
    )
    done = subprocess.run(
        [node, "-e", program], capture_output=True, text=True, encoding="utf-8", timeout=30
    )
    assert done.returncode == 0, done.stderr
    found: list[dict[str, Any]] = json.loads(done.stdout)
    return found


def test_the_changes_give_the_detail_of_the_second_map_in_the_browser(sample: Sample) -> None:
    first = {
        "__proto__": {"id": "__proto__", "does": "a"},
        "Reader": {"id": "Reader", "does": "Reads.", "gained": {}},
        "_meta": {"edges": [1, 2], "layers": ["data"]},
    }
    second = {
        "__proto__": {"id": "__proto__", "does": "b"},
        "Reader": {"id": "Reader", "does": "Reads.", "gained": {"tests": 1}, "moved": True},
        "_meta": {"edges": [1, 2], "change": {"base": "main"}, "layers": ["data"]},
    }
    script = page_maps_script(
        sample.theme,
        [("schematic", "panel", json.dumps(first)), ("changemap", "none", json.dumps(second))],
    )
    assert script.count(ENGINE_MARK) == 1 and "show(changed(" in script
    got = _node_details(script)
    assert [json.loads(call["json"]) for call in got] == [first, second]
    assert [call["keys"] for call in got] == [list(first), list(second)]
    assert all(call["proto"] for call in got), "the key __proto__ did not set the prototype"


def test_a_second_map_with_other_keys_gets_its_full_detail(sample: Sample) -> None:
    first = {"A": {"id": "A"}, "_meta": {}}
    second = {"B": {"id": "B"}, "_meta": {}}
    script = page_maps_script(
        sample.theme, [("s", "p", json.dumps(first)), ("c", "q", json.dumps(second))]
    )
    assert "function changed(" not in script
    assert [json.loads(call["json"]) for call in _node_details(script)] == [first, second]


# ---- perf-8: no duplicate field and compact data ----------------------------------


def test_the_page_data_has_compact_separators(sample: Sample) -> None:
    html = _build(sample, {"has_change": False})
    line = next(s for s in html.split("\n") if s.startswith("<script>window.systemapWorkspace="))
    data = json.loads(line[len("<script>window.systemapWorkspace=") : -len(";</script>")])
    assert line == (
        "<script>window.systemapWorkspace="
        + json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).replace(
            "<", "\\u003c"
        )
        + ";</script>"
    )
    records = [m for source in data["sources"].values() for m in source["modules"]]
    assert records and all("names" not in record for record in records)
    assert any(record["public_names"] for record in records)


# ---- xss-1: the Content-Security-Policy -------------------------------------------


def test_the_policy_has_the_digest_of_each_inline_script_and_style(sample: Sample) -> None:
    html = _build(sample, copy.deepcopy(COMPARISON))
    head = html.split("</head>")[0]
    assert head.count('http-equiv="Content-Security-Policy"') == 1
    assert head.index("Content-Security-Policy") < head.index("<script>")
    policy = page_csp.of_page(html)
    directives = dict(part.split(" ", 1) for part in policy.split("; "))
    for name in ("default-src", "object-src", "base-uri", "form-action"):
        assert directives[name] == "'none'", name
    assert "http" not in policy and "*" not in policy and "connect-src" not in directives
    scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
    styles = re.findall(r"<style>(.*?)</style>", html, re.S)
    assert len(scripts) > 5 and len(styles) > 2
    assert set(directives["script-src"].split(" ")) == {_digest(s) for s in scripts}
    assert set(directives["style-src-elem"].split(" ")) == {_digest(s) for s in styles}
    # A script that an injection adds to the page has no digest in the policy.
    assert _digest("alert(1)") not in policy


def test_the_policy_has_the_style_digests_of_the_inserted_previews() -> None:
    page_text = '<html><head><meta charset="utf-8"><style>p{}</style></head><body></body></html>'
    preview = "<svg><style>#p .a &gt; .b{}</style></svg>"
    policy = page_csp.of_page(page_csp.with_policy(page_text, [preview]))
    assert _digest("p{}") in policy
    # In an SVG element the browser decodes &gt;. The policy has the two digests.
    assert _digest("#p .a &gt; .b{}") in policy and _digest("#p .a > .b{}") in policy


def test_the_live_script_gets_a_digest_and_a_connection(sample: Sample) -> None:
    html = page_live.with_script(_build(sample, {"has_change": False}), 3)
    policy = page_csp.of_page(html)
    live = re.findall(r"<script>(.*?)</script>", html, re.S)[-1]
    assert "new EventSource('/events')" in live
    assert _digest(live) in policy and policy.endswith("; connect-src 'self'")
    assert html.count('http-equiv="Content-Security-Policy"') == 1
    waiting = page_live.with_script(page_live.waiting_page(), 0)
    assert "connect-src 'self'" in page_csp.of_page(waiting)


def _headers(port: int, path: str) -> tuple[int, dict[str, str]]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    connection.request("GET", path)
    response = connection.getresponse()
    response.read()
    connection.close()
    return response.status, dict(response.getheaders())


def _running(httpd: Any) -> Iterator[int]:
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield int(httpd.server_address[1])
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_the_page_server_sends_the_policy_of_the_page(sample: Sample, tmp_path: Path) -> None:
    out = tmp_path / "out"
    (out / "child").mkdir(parents=True)
    html = _build(sample, {"has_change": False})
    (out / "index.html").write_text(html, encoding="utf-8")
    (out / "child" / "index.html").write_text(html, encoding="utf-8")
    (out / "figure.svg").write_text("<svg><style>a{}</style></svg>", encoding="utf-8")
    (out / "notes.txt").write_text("text", encoding="utf-8")
    for port in _running(serve.make_server(out, 0)):
        for path in ("/", "/index.html", "/child/"):
            status, headers = _headers(port, path)
            assert status == 200 and headers["Content-Security-Policy"] == page_csp.of_page(html)
        assert _headers(port, "/figure.svg")[1]["Content-Security-Policy"] == (
            page_csp.FIGURE_POLICY
        )
        assert "Content-Security-Policy" not in _headers(port, "/notes.txt")[1]
        assert _headers(port, "/missing.html")[0] == 404


def test_a_refused_request_gets_no_policy(sample: Sample, tmp_path: Path) -> None:
    """Before the fix, a 403 answer for a wrong Host had the policy of the page file."""
    out = tmp_path / "out"
    out.mkdir()
    (out / "index.html").write_text(_build(sample, {"has_change": False}), encoding="utf-8")
    for port in _running(serve.make_server(out, 0)):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        connection.request("GET", "/index.html", headers={"Host": f"evil.example:{port}"})
        response = connection.getresponse()
        response.read()
        connection.close()
        assert response.status == 403
        assert response.getheader("Content-Security-Policy") is None


def test_the_live_server_sends_the_policy_with_the_live_script(tmp_path: Path) -> None:
    def rendered() -> serve.Rendered:
        return serve.Rendered(files={"index.html": "<html>map</html>"})

    live = serve.LiveMap(tmp_path / "out", rendered, lambda _event: None, base="main")
    try:
        for port in _running(serve.make_live_server(live, 0)):
            status, headers = _headers(port, "/")
            assert status == 200
            policy = headers["Content-Security-Policy"]
            assert policy == page_csp.of_page((tmp_path / "out/index.html").read_text())
            assert "connect-src 'self'" in policy and "script-src 'sha256-" in policy
            assert "Content-Security-Policy" not in _headers(port, "/status")[1]
    finally:
        live.close()


# ---- regex-5: comment marks in theme values ----------------------------------------


@pytest.mark.parametrize("value", ["#888 /*", "#888 */", "/* x */ #888", "#888 '", "#888 \\"])
def test_a_theme_value_with_a_css_comment_mark_is_refused(sample: Sample, value: str) -> None:
    """Before the fix, "#888 /*" in ink_2 removed 5,707 characters of page CSS. The
    value "#888 '" started a CSS string that removed the dark theme rule."""
    with pytest.raises(ValueError, match="theme value ink_2 contains"):
        theme_mod.resolve({"ink_2": value}, [])
    cfg = dataclasses.replace(sample.cfg, theme={"ink_2": value})
    with pytest.raises(ConfigError, match="ink_2"):
        nest._theme(cfg, sample.model, sample.meaning)


def test_page_detail_reads_the_system_map(sample: Sample) -> None:
    detail = page_detail(_build(sample, copy.deepcopy(COMPARISON)))
    assert "change" not in detail["_meta"]


@pytest.mark.parametrize("value", ["Inter',sans-serif", 'Inter",sans-serif', "Inter\\,serif"])
def test_a_font_stack_with_an_unpaired_quote_or_a_backslash_is_refused(value: str) -> None:
    with pytest.raises(ValueError, match="theme value font_ui contains"):
        theme_mod.resolve({"font_ui": value}, [])


@pytest.mark.parametrize("value", ["'Inter',sans-serif", '"Inter",sans-serif'])
def test_a_font_stack_with_quotes_in_pairs_is_accepted(value: str) -> None:
    assert theme_mod.resolve({"font_ui": value}, [])["font_ui"] == value
