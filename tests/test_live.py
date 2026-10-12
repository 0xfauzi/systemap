"""`systemap live`: the render of the working tree, the server and the JSON lines.

Acceptance: a render writes the pages and change.svg into the served directory and no
tracked file. A failed render keeps the last page and gives `state: error`. One render
runs at a time, and requests during a render cause one more render. `GET /` has the live
script, `POST /refresh` causes a render, `GET /status` gives the state, and `/events`
sends `rendered`. The command writes one JSON object for each event and exits 0 on
SIGTERM.
"""

from __future__ import annotations

import http.client
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree
from test_live_change import git, make_repo
from test_nested import nested  # noqa: F401 - a fixture

from systemap import change, config, explain, extract, figure, nest, page_live, serve
from systemap.cli import main
from systemap.config import ConfigError

UNCLAIMED = {"pkg/extra.py": "def extra() -> int:\n    return 0\n"}


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "repo").mkdir()
    return make_repo(tmp_path / "repo")


class Events:
    """The events that a LiveMap gives, kept in order."""

    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []
        self.lock = threading.Lock()

    def __call__(self, event: dict[str, Any]) -> None:
        with self.lock:
            self.items.append(event)

    def names(self) -> list[str]:
        return [e["event"] for e in self.items]


def live_map(repo: Path, out: Path) -> tuple[serve.LiveMap, Events]:
    events = Events()
    ref = serve.comparison_ref(repo, "")
    return serve.LiveMap(out, lambda: serve.render_tree(repo, ref), events, base=ref), events


def render(live: serve.LiveMap) -> dict[str, Any]:
    live.request()
    live.wait(60)
    return live.status()


# ---- the render of the working tree ------------------------------------------------------


def test_the_default_base_is_the_first_ref_that_git_resolves(repo: Path) -> None:
    assert serve.comparison_ref(repo, "") == "main"
    assert serve.comparison_ref(repo, "work") == "work"
    with pytest.raises(change.ChangeError):
        serve.comparison_ref(repo, "no-such-ref")
    git(repo, "branch", "-q", "-m", "main", "trunk")
    assert serve.comparison_ref(repo, "") == ""


def test_a_render_gives_the_pages_the_figure_and_the_map_updates(
    repo: Path, tmp_path: Path
) -> None:
    write_tree(repo, {"pkg/audit.py": "def check(text: str) -> bool:\n    return True\n"})
    write_tree(repo, UNCLAIMED)
    live, events = live_map(repo, tmp_path / "out")
    state = render(live)
    assert state["state"] == "ready" and state["error"] == ""
    assert state["components"] == ["Audit"]
    assert state["base"] == "main"
    assert state["comparison_base"] == git(repo, "rev-parse", "main")
    # The module that no component claims and the new source of Audit need an action.
    assert state["updates"] == 2
    added, review = state["lines"]
    assert added["text"].startswith("added: pkg.extra, No component has a claim for it.")
    assert added["action"] == explain.LESSONS["added"].do
    assert review["text"].startswith("source review: Audit has changed code in pkg.audit.")
    assert review["action"] == explain.LESSONS["source review"].do
    html = (tmp_path / "out/index.html").read_text(encoding="utf-8")
    assert 'id="changemap"' in html, "the page has the Changes view of the working tree"
    assert page_live.VIEW_KEY in html
    svg = Path(state["svg"])
    assert svg == tmp_path / "out" / serve.FIGURE
    assert svg.read_text(encoding="utf-8").startswith("<svg")
    assert state["svg_bytes"] == len(svg.read_bytes())
    assert events.names() == ["rendering", "rendered"]
    assert events.items[1]["components"] == ["Audit"]


def test_nested_maps_get_the_pages_that_systemap_render_writes(nested: Path) -> None:  # noqa: F811
    rendered = serve.render_tree(nested, "")
    assert sorted(rendered.files) == [
        "Gateway/index.html",
        "Style/index.html",
        serve.FIGURE,
        "index.html",
    ]
    assert main(["--root", str(nested), "render"]) == 0
    for name in ("index.html", "Gateway/index.html", "Style/index.html"):
        written = (nested / "docs/map" / name).read_text(encoding="utf-8")
        assert rendered.files[name] == written, name
    assert [path.name for path in rendered.models] == ["model.py", "gateway.py", "style.py"]


def test_without_a_change_the_figure_is_the_system_figure(repo: Path, tmp_path: Path) -> None:
    live, _events = live_map(repo, tmp_path / "out")
    state = render(live)
    assert state["state"] == "ready"
    assert state["components"] == [] and state["updates"] == 0
    cfg = config.load(repo)
    top = nest.load(cfg).top
    system, _collisions = figure.make(
        cfg, top.model, top.meaning, top.theme, extract.build(cfg), mode="system", bare=True
    )
    assert Path(state["svg"]).read_text(encoding="utf-8") == system
    write_tree(repo, UNCLAIMED)
    assert render(live)["svg_bytes"] != len(system.encode("utf-8"))


def test_renders_change_no_tracked_file(repo: Path, tmp_path: Path) -> None:
    write_tree(repo, {"pkg/reader.py": "def read() -> bytes:\n    return b''\n"})
    before = git(repo, "status", "--porcelain", "--untracked-files=all")
    live, _events = live_map(repo, tmp_path / "out")
    assert render(live)["state"] == "ready"
    assert render(live)["state"] == "ready"
    after = git(repo, "status", "--porcelain", "--untracked-files=all").splitlines()
    # The only new file is the facts cache of the merge base, as `render --base` writes it.
    assert [line for line in after if not line.startswith("?? .systemap/facts/")] == [before]
    assert not (repo / "docs").exists()


def test_a_broken_model_keeps_the_last_page_and_gives_the_error(repo: Path, tmp_path: Path) -> None:
    live, events = live_map(repo, tmp_path / "out")
    assert render(live)["state"] == "ready"
    page = (tmp_path / "out/index.html").read_text(encoding="utf-8")
    model = repo / "map/model.py"
    good = model.read_text(encoding="utf-8")
    model.write_text(good + "\nMODEL = (\n", encoding="utf-8")
    state = render(live)
    assert state["state"] == "error"
    assert "map/model.py" in state["error"]
    assert state["version"] == 2
    assert (tmp_path / "out/index.html").read_text(encoding="utf-8") == page
    assert events.items[-1] == {"event": "error", "version": 2, "text": state["error"]}
    model.write_text(good, encoding="utf-8")
    state = render(live)
    assert state["state"] == "ready" and state["error"] == "" and state["version"] == 3


def test_a_failed_first_render_gives_a_page_with_the_error(tmp_path: Path) -> None:
    def broken() -> serve.Rendered:
        raise ConfigError("map/model.py could not import: SyntaxError")

    live = serve.LiveMap(tmp_path / "out", broken, Events())
    waiting = (tmp_path / "out/index.html").read_text(encoding="utf-8")
    assert "systemap renders the map" in waiting
    assert waiting.count("new EventSource") == 1 and "var VERSION = 0," in waiting
    state = render(live)
    assert state["state"] == "error"
    assert state["error"] == "map/model.py could not import: SyntaxError"
    html = (tmp_path / "out/index.html").read_text(encoding="utf-8")
    assert "map/model.py could not import: SyntaxError" in html
    assert "var VERSION = 1," in html, "the next good version loads the page again"
    assert html.count("new EventSource") == 1


def test_requests_during_a_render_cause_one_more_render(tmp_path: Path) -> None:
    started, release = threading.Event(), threading.Event()
    calls: list[int] = []

    def slow() -> serve.Rendered:
        calls.append(1)
        started.set()
        release.wait(10)
        return serve.Rendered(files={"index.html": "<html><body></body></html>"})

    events = Events()
    live = serve.LiveMap(tmp_path / "out", slow, events)
    live.request()
    assert started.wait(10)
    for _ in range(3):
        live.request()
    assert live.status()["state"] == "rendering"
    release.set()
    deadline = time.monotonic() + 10
    while events.names().count("rendered") < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    live.wait(10)
    assert len(calls) == 2
    assert events.names() == ["rendering", "rendered", "rendering", "rendered"]
    assert live.status()["version"] == 2


# ---- the server ------------------------------------------------------------------------


@pytest.fixture
def served(tmp_path: Path) -> Iterator[tuple[serve.LiveMap, list[int]]]:
    calls: list[int] = []

    def counted() -> serve.Rendered:
        calls.append(1)
        return serve.Rendered(
            files={"index.html": f"<html><body>render {len(calls)}</body></html>"},
            updates=1,
            lines=({"text": "added: pkg.extra", "action": "Add it."},),
            components=("Reader",),
        )

    live = serve.LiveMap(tmp_path / "out", counted, Events(), base="main")
    httpd = serve.make_live_server(live, 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield live, calls
    finally:
        live.close()
        httpd.shutdown()
        httpd.server_close()


def fetch(url: str, method: str = "GET") -> tuple[int, str]:
    request = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(request, timeout=10) as answer:
        return answer.status, answer.read().decode("utf-8")


def test_the_server_gives_the_page_with_the_live_script(
    served: tuple[serve.LiveMap, list[int]],
) -> None:
    live, _calls = served
    assert live.url.startswith("http://127.0.0.1:") and live.url.endswith("/")
    code, html = fetch(live.url)
    assert code == 200
    assert page_live.VIEW_KEY in html and "new EventSource('/events')" in html
    assert "var VERSION = 0," in html


def test_refresh_causes_a_render_and_status_gives_the_result(
    served: tuple[serve.LiveMap, list[int]],
) -> None:
    live, calls = served
    code, body = fetch(live.url + "refresh", "POST")
    assert (code, json.loads(body)) == (202, {"queued": True})
    live.wait(10)
    assert calls == [1]
    code, body = fetch(live.url + "status")
    state = json.loads(body)
    assert code == 200
    assert set(state) == {
        "version",
        "state",
        "seconds",
        "updates",
        "lines",
        "components",
        "error",
        "url",
        "svg",
        "svg_bytes",
        "base",
        "comparison_base",
    }
    assert state["version"] == 1 and state["state"] == "ready"
    assert state["lines"] == [{"text": "added: pkg.extra", "action": "Add it."}]
    assert state["components"] == ["Reader"] and state["url"] == live.url
    assert state["base"] == "main"
    _code, html = fetch(live.url)
    assert "render 1" in html and "var VERSION = 1," in html


def test_events_send_rendered_after_each_render(served: tuple[serve.LiveMap, list[int]]) -> None:
    live, _calls = served
    port = int(live.url.rsplit(":", 1)[1].strip("/"))
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    connection.request("GET", "/events")
    answer = connection.getresponse()
    assert answer.status == 200
    assert answer.getheader("Content-Type") == "text/event-stream"
    assert answer.fp.readline() == b": live\n"
    fetch(live.url + "refresh", "POST")
    received = [answer.fp.readline() for _ in range(3)]
    assert received == [b"\n", b"event: rendered\n", b'data: {"version": 1}\n']
    connection.close()
    # A new reader gets the version of the page on disk first.
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    connection.request("GET", "/events")
    answer = connection.getresponse()
    lines = [answer.fp.readline() for _ in range(4)]
    assert lines == [b": live\n", b"\n", b"event: rendered\n", b'data: {"version": 1}\n']
    connection.close()


def test_a_port_that_is_in_use_gives_exit_code_2(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with socket.socket() as held:
        held.bind(("127.0.0.1", 0))
        held.listen()
        port = held.getsockname()[1]
        assert main(["--root", str(repo), "live", "--port", str(port), "--no-watch"]) == 2
    err = capsys.readouterr().err
    assert f"The server cannot use port {port}" in err
    assert "Use --port 0 to select an available port" in err


def test_an_unknown_base_gives_exit_code_2(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--root", str(repo), "live", "--base", "no-such-ref", "--port", "0"]) == 2
    assert "unknown revision no-such-ref" in capsys.readouterr().err


# ---- the watched files -----------------------------------------------------------------


def test_the_watched_files_are_the_inputs_of_a_render(repo: Path) -> None:
    write_tree(repo, {"tests/test_reader.py": "def test_read() -> None:\n    pass\n"})
    names = {p.relative_to(repo).as_posix() for p in serve.watched(repo) if p.exists()}
    assert names == {
        "systemap.toml",
        "map/model.py",
        "pkg/__init__.py",
        "pkg/reader.py",
        "pkg/writer.py",
        "pkg/store.py",
        "tests/test_reader.py",
    }


def test_the_scan_requests_one_render_after_the_changes_stop(repo: Path) -> None:
    class Requests:
        count = 0

        def request(self) -> None:
            self.count += 1

    class Ticks:
        """The stop event of the scan, without a clock. Each wait() is one scan interval:
        it does the next action, and then the scan runs. A test with real time failed on
        a slow runner: a long gap between two writes let one scan see no change."""

        def __init__(self, *actions: Callable[[], None]) -> None:
            self.actions = list(actions)

        def wait(self, _seconds: float) -> bool:
            if not self.actions:
                return True
            self.actions.pop(0)()
            return False

    requests, seen = Requests(), []
    source = repo / "pkg/reader.py"

    def write(n: int) -> Callable[[], None]:
        def act() -> None:
            source.write_text(f"def read() -> str:\n    return '{n}'\n", encoding="utf-8")
            os.utime(source, ns=(n * 10**9, n * 10**9))

        return act

    def quiet() -> None:
        seen.append(requests.count)

    ticks = Ticks(quiet, quiet, write(0), write(1), write(2), quiet, quiet, quiet)
    serve.watch(requests, lambda: serve.watched(repo), ticks, 0)
    # No request before a change, one request after the changes stop, and no more.
    assert seen == [0, 0, 0, 1, 1]
    assert requests.count == 1


# ---- the command ----------------------------------------------------------------------


def test_the_command_writes_json_lines_and_stops_on_sigterm(repo: Path) -> None:
    write_tree(repo, {"pkg/audit.py": "def check(text: str) -> bool:\n    return True\n"})
    before = git(repo, "status", "--porcelain", "--untracked-files=no")
    command = [sys.executable, "-m", "systemap", "live", "--port", "0", "--json", "--no-watch"]
    # Windows ends a process at once on SIGTERM from a different process. There the test
    # sends Ctrl-Break to a new process group, and the command stops on SIGBREAK.
    if sys.platform == "win32":
        flags, stop = subprocess.CREATE_NEW_PROCESS_GROUP, signal.CTRL_BREAK_EVENT
    else:
        flags, stop = 0, signal.SIGTERM
    proc = subprocess.Popen(
        command,
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=flags,
    )
    assert proc.stdout is not None
    try:
        lines = [json.loads(proc.stdout.readline()) for _ in range(3)]
        proc.send_signal(stop)
        out, err = proc.communicate(timeout=30)
    finally:
        proc.kill()
    lines += [json.loads(line) for line in out.splitlines()]
    assert proc.returncode == 0, err
    serving, rendering, rendered, stopped = lines
    assert serving == {
        "event": "serving",
        "url": serving["url"],
        "base": "main",
        "comparison_base": git(repo, "rev-parse", "main"),
    }
    assert serving["url"].startswith("http://127.0.0.1:")
    assert rendering == {"event": "rendering", "version": 1}
    assert set(rendered) == {
        "event",
        "version",
        "seconds",
        "updates",
        "components",
        "svg",
        "svg_bytes",
    }
    assert rendered["event"] == "rendered" and rendered["version"] == 1
    assert rendered["components"] == ["Audit"] and rendered["updates"] == 1
    assert rendered["svg_bytes"] > 0
    assert stopped == {"event": "stopped"}
    assert not Path(rendered["svg"]).parent.exists(), "the temporary directory is removed"
    assert git(repo, "status", "--porcelain", "--untracked-files=no") == before


def test_the_text_lines_name_the_events() -> None:
    lines = {
        name: serve.HUMAN[name](event)
        for name, event in {
            "serving": {"url": "http://127.0.0.1:1/", "base": "main", "comparison_base": "a" * 40},
            "rendering": {"version": 2},
            "rendered": {"version": 2, "seconds": 5.71, "updates": 3, "components": ["Page"]},
            "error": {"version": 3, "text": "map/model.py could not import"},
            "stopped": {},
        }.items()
    }
    assert lines["serving"] == (
        "map: The live map is at http://127.0.0.1:1/. Use Ctrl-C to stop the server.\n"
        "map: The Changes view compares the working tree with main at the merge base aaaaaaa."
    )
    assert lines["rendered"] == (
        "map: Version 2 is on the page (5.7 s). Map updates: 3. Changed components: Page."
    )
    assert lines["error"].endswith("\nmap/model.py could not import")
    assert lines["stopped"] == "map: The server stopped."
