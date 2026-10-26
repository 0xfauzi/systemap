"""The live map extracts only the changed files, and a blocked output stops no request.

Before the fact cache, each live render extracted all files again and compared the
sources two times. On this repository, one render after one edit took 3.9 s, and 6.4 s
with a base (measured). The kept facts must be the same as the facts of a full
extraction after each edit, addition, removal and rename.

Before the change of `LiveMap.say`, the server held the state lock while it wrote an
event line. A standard output that nobody read then stopped `GET /status`.
"""

from __future__ import annotations

import json
import os
import socket
import threading
import time
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree
from test_live_change import commit, make_repo

from systemap import change, config, extraction, fact_cache, serve

CONFIG = """
tests_dir = "tests"

[package_roots]
"pkg" = "pkg"
"""

TREE = {
    "systemap.toml": CONFIG,
    "pkg/__init__.py": '"""The package."""\n',
    "pkg/base.py": "def helper() -> int:\n    return 1\n\n\ndef other() -> int:\n    return 2\n",
    "pkg/star.py": "from pkg.base import *\n\n\ndef use() -> int:\n    return helper()\n",
    "pkg/reader.py": "from pkg import base\n\n\ndef read() -> int:\n    return base.other()\n",
    "tests/test_reader.py": "from pkg.reader import read\n\n\ndef test_read():\n    assert read()\n",
}


def facts(root: Path, cache: fact_cache.FactCache | None = None) -> dict[str, Any]:
    return extraction.build(config.load(root), cache)


def same_as_full(root: Path, cache: fact_cache.FactCache) -> dict[str, Any]:
    """Extract with the cache and without it. The two results must be equal."""
    kept = facts(root, cache)
    assert json.dumps(kept, sort_keys=True) == json.dumps(facts(root), sort_keys=True)
    return kept


def made(cache: fact_cache.FactCache, step: Callable[[], None], root: Path) -> dict[str, int]:
    """Do the step, extract with the cache, and give the values that the cache made."""
    step()
    before = dict(cache.made)
    same_as_full(root, cache)
    return {kind: count - before.get(kind, 0) for kind, count in cache.made.items()}


def edit(path: Path, text: str) -> Callable[[], None]:
    return lambda: path.write_text(text, encoding="utf-8")


def test_the_kept_facts_are_the_facts_of_a_full_extraction_after_each_change(
    tmp_path: Path,
) -> None:
    write_tree(tmp_path, TREE)
    cache = fact_cache.FactCache()
    same_as_full(tmp_path, cache)
    pkg, tests = tmp_path / "pkg", tmp_path / "tests"
    steps = [
        edit(pkg / "reader.py", "from pkg import base\n\n\ndef read() -> int:\n    return 3\n"),
        # The star import gets a different name set. The call sites of pkg.star change.
        edit(pkg / "base.py", "def other() -> int:\n    return 2\n"),
        edit(pkg / "base.py", "def helper() -> int:\n    return 1\n"),
        edit(
            pkg / "added.py",
            "from pkg.reader import read\n\n\ndef add() -> int:\n    return read()\n",
        ),
        lambda: (pkg / "star.py").unlink(),
        lambda: (pkg / "added.py").rename(pkg / "renamed.py"),
        edit(
            tests / "test_renamed.py",
            "from pkg.renamed import add\n\n\ndef test_add():\n    assert add()\n",
        ),
        edit(tests / "test_reader.py", "def test_nothing():\n    assert True\n"),
        edit(pkg / "reader.py", "def read(:\n"),
        edit(pkg / "reader.py", "def read() -> int:\n    return 4\n"),
        edit(tmp_path / "systemap.toml", CONFIG.replace('tests_dir = "tests"', "")),
    ]
    for step in steps:
        made(cache, step, tmp_path)


def test_one_edit_extracts_only_the_changed_file(tmp_path: Path) -> None:
    write_tree(tmp_path, TREE)
    cache = fact_cache.FactCache()
    first = made(cache, lambda: None, tmp_path)
    assert first["module"] == 4 and first["tests"] == 1
    again = made(cache, lambda: None, tmp_path)
    assert again.get("module", 0) == 0 and again.get("sites", 0) == 0
    after = made(
        cache, edit(tmp_path / "pkg/reader.py", "def read() -> int:\n    return 5\n"), tmp_path
    )
    # One module record and the call sites of that module. The test file is the same.
    assert after["module"] == 1 and after["sites"] == 1 and after.get("tests", 0) == 0


def test_a_changed_file_with_the_same_size_and_time_is_extracted_again(tmp_path: Path) -> None:
    write_tree(tmp_path, TREE)
    cache = fact_cache.FactCache()
    path = tmp_path / "pkg/reader.py"
    # A file older than the racy time: the cache can use the status without a read.
    old = time.time_ns() - 10 * fact_cache.RACY_NS
    os.utime(path, ns=(old, old))
    first = same_as_full(tmp_path, cache)["components"]["pkg.reader"]
    # Bytes keep the size the same on Windows, where write_text writes "\r\n".
    data = path.read_bytes()
    path.write_bytes(data.replace(b"return", b"assert"))
    os.utime(path, ns=(old, old))
    assert path.stat().st_size == len(data)
    now = same_as_full(tmp_path, cache)["components"]["pkg.reader"]
    assert now["sha"] != first["sha"]


def test_where_the_status_does_not_show_writes_a_changed_file_is_read_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # On Windows, st_ctime is the creation time. A write that keeps the size and the
    # modification time keeps the full status. This test gives the same status each time.
    monkeypatch.setattr(fact_cache, "STATUS_SHOWS_WRITES", False)
    monkeypatch.setattr(fact_cache, "_status", lambda path: (1, 2, 3, 0, 0))
    write_tree(tmp_path, TREE)
    cache = fact_cache.FactCache()
    path = tmp_path / "pkg/reader.py"
    first = same_as_full(tmp_path, cache)["components"]["pkg.reader"]
    path.write_bytes(path.read_bytes().replace(b"return", b"assert"))
    now = same_as_full(tmp_path, cache)["components"]["pkg.reader"]
    assert now["sha"] != first["sha"]


def test_the_live_renderer_gives_the_pages_of_a_render_without_cache(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    renderer = serve.LiveRenderer(root, "main")
    renderer()
    write_tree(root, {"pkg/writer.py": "def write() -> str:\n    return 'new'\n"})
    commit(root, {"pkg/store.py": "def keep(text: str) -> int:\n    return 0\n"}, "store")
    write_tree(
        root,
        {
            "pkg/audit.py": "from pkg.reader import read\n\n\ndef check() -> str:\n"
            "    return read()\n"
        },
    )
    kept, full = renderer(), serve.render_tree(root, "main")
    assert kept.files == full.files and kept.lines == full.lines
    assert kept.components == full.components and kept.components


def test_a_live_render_compares_the_sources_one_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Before, the change figure made a second source comparison of the same base.
    root = make_repo(tmp_path)
    write_tree(root, {"pkg/writer.py": "def write() -> str:\n    return 'new'\n"})
    calls: list[str] = []
    compare = change.source_change

    def counted(*args: Any, **kwargs: Any) -> change.SourceChange:
        calls.append(args[1])
        return compare(*args, **kwargs)

    monkeypatch.setattr(change, "source_change", counted)
    assert serve.render_tree(root, "main").components == ("Writer",)
    assert calls == ["main"]


# ---- a standard output that nobody reads ------------------------------------------------


class Blocked:
    """An event output that writes to a pipe that nobody reads. The pipe becomes full."""

    def __init__(self) -> None:
        self.read_end, self.write_end = os.pipe()
        self.writing = threading.Event()

    def __call__(self, event: dict[str, Any]) -> None:
        self.writing.set()
        try:
            os.write(self.write_end, json.dumps(event).encode() * 100_000)
        except OSError:
            return

    def close(self) -> None:
        os.close(self.read_end)


@pytest.fixture
def blocked(tmp_path: Path) -> Iterator[tuple[serve.LiveMap, Blocked, str]]:
    output = Blocked()
    live = serve.LiveMap(tmp_path / "out", serve.Rendered, output, base="")
    httpd = serve.make_live_server(live, 0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield live, output, live.url
    finally:
        output.close()
        live.close()
        httpd.shutdown()
        httpd.server_close()
        os.close(output.write_end)


def test_status_answers_while_the_event_output_is_blocked(
    blocked: tuple[serve.LiveMap, Blocked, str],
) -> None:
    live, output, url = blocked
    writer = threading.Thread(target=live.say, args=({"event": "stopped"},), daemon=True)
    writer.start()
    assert output.writing.wait(10)
    with urllib.request.urlopen(url + "status", timeout=10) as answer:
        assert answer.status == 200
        assert json.loads(answer.read())["state"] == "rendering"
    assert live.models() == ()
    assert writer.is_alive()


def test_a_client_that_sends_one_byte_at_a_time_loses_the_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Before the time limit for the full request head, each byte started the read time
    # limit again, and the connection stayed open (more than 30 s measured).
    monkeypatch.setattr(serve.PageHandler, "timeout", 0.3)
    (tmp_path / "index.html").write_text("map", encoding="utf-8")
    httpd = serve.make_server(tmp_path, 0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = int(httpd.server_address[1])
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=5) as client:
            client.sendall(f"GET / HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nX-Slow: ".encode())
            assert _closed_within(client, 5.0)
    finally:
        httpd.shutdown()
        httpd.server_close()


def _closed_within(client: socket.socket, seconds: float) -> bool:
    """Send one byte each 0.1 s. Give True if the server closes the connection in time."""
    end = time.monotonic() + seconds
    client.settimeout(0.1)
    while time.monotonic() < end:
        try:
            client.sendall(b"a")
            if client.recv(1) == b"":
                return True
        except TimeoutError:
            continue
        except OSError:
            return True
    return False
