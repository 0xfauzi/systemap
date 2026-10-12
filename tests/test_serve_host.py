"""The page server and the live server answer only requests to their loopback address.

A web page can make its own domain name point at 127.0.0.1 (DNS rebinding). The browser
then sends that name in the Host header, and without a check the page could read the map
of a private repository. Each server refuses a request whose Host is not 127.0.0.1 or
localhost with the server port.
"""

from __future__ import annotations

import http.client
import threading
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from systemap import serve


def _get(port: int, path: str, host: str | None) -> int:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {} if host is None else {"Host": host}
    connection.request("GET", path, headers=headers)
    status = connection.getresponse().status
    connection.close()
    return status


def _post(port: int, path: str, host: str) -> int:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    connection.request("POST", path, headers={"Host": host})
    status = connection.getresponse().status
    connection.close()
    return status


def _running(httpd: ThreadingHTTPServer) -> Iterator[int]:
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield int(httpd.server_address[1])
    finally:
        httpd.shutdown()
        httpd.server_close()


@pytest.fixture
def page_port(tmp_path: Path) -> Iterator[int]:
    (tmp_path / "index.html").write_text("<html>map</html>", encoding="utf-8")
    yield from _running(serve.make_server(tmp_path, 0))


@pytest.fixture
def live_port(tmp_path: Path) -> Iterator[int]:
    def rendered() -> serve.Rendered:
        return serve.Rendered(files={"index.html": "<html>map</html>"})

    live = serve.LiveMap(tmp_path / "out", rendered, lambda _event: None, base="main")
    try:
        yield from _running(serve.make_live_server(live, 0))
    finally:
        live.close()


def test_the_page_server_answers_its_loopback_names(page_port: int) -> None:
    assert _get(page_port, "/", None) == 200  # http.client sends 127.0.0.1:<port>
    assert _get(page_port, "/", f"localhost:{page_port}") == 200


def test_the_page_server_refuses_another_host(page_port: int) -> None:
    assert _get(page_port, "/", f"attacker.example:{page_port}") == 403
    assert _get(page_port, "/", "127.0.0.1:1") == 403


def test_the_live_server_refuses_another_host(live_port: int) -> None:
    assert _get(live_port, "/status", None) == 200
    assert _get(live_port, "/status", f"attacker.example:{live_port}") == 403
    assert _post(live_port, "/refresh", f"attacker.example:{live_port}") == 403
    assert _post(live_port, "/refresh", f"127.0.0.1:{live_port}") == 202
