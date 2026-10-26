"""The live server refuses a POST request from a different site and limits slow clients.

A web page of a different site can send `POST /refresh` with a form, `sendBeacon`, or a
no-cors fetch. Before this check, each such request started a full render. A program
without an Origin header, for example curl or the agent hook, can still send it.
"""

from __future__ import annotations

import errno
import http.client
import socket
import threading
import time
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from systemap import serve, serve_guard


def _running(httpd: ThreadingHTTPServer) -> Iterator[int]:
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield int(httpd.server_address[1])
    finally:
        httpd.shutdown()
        httpd.server_close()


class Live:
    """A live server with a count of the renders."""

    def __init__(self, tmp_path: Path) -> None:
        self.renders = 0
        self.map = serve.LiveMap(tmp_path / "out", self._render, lambda _event: None, base="")

    def _render(self) -> serve.Rendered:
        self.renders += 1
        return serve.Rendered(files={"index.html": "<html>map</html>"})

    def settled(self) -> int:
        """Give the number of renders after the queued versions are complete."""
        self.map.wait(10)
        return self.renders


@pytest.fixture
def live(tmp_path: Path) -> Iterator[tuple[Live, int]]:
    server = Live(tmp_path)
    try:
        for port in _running(serve.make_live_server(server.map, 0)):
            yield server, port
    finally:
        server.map.close()


def _post(port: int, headers: dict[str, str]) -> int:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    connection.request("POST", "/refresh", body=b"x", headers=headers)
    status = connection.getresponse().status
    connection.close()
    return status


@pytest.mark.parametrize(
    "headers",
    [
        {"Sec-Fetch-Site": "cross-site", "Origin": "http://evil.example"},
        {"Sec-Fetch-Site": "same-site"},
        {"Origin": "http://evil.example"},
        {"Origin": "null"},
        {"Sec-Fetch-Site": "cross-site"},
    ],
)
def test_a_post_from_a_different_site_gets_403_and_no_render(
    live: tuple[Live, int], headers: dict[str, str]
) -> None:
    server, port = live
    assert _post(port, {}) == 202
    before = server.settled()
    assert _post(port, headers) == 403
    assert server.settled() == before


@pytest.mark.parametrize(
    "headers",
    [
        {},  # curl and the agent hook send no Origin
        {"Sec-Fetch-Site": "same-origin", "Origin": "http://127.0.0.1:{port}"},
        {"Origin": "http://localhost:{port}"},
        {"Sec-Fetch-Site": "none"},
    ],
)
def test_a_post_from_the_page_or_a_program_causes_a_render(
    live: tuple[Live, int], headers: dict[str, str]
) -> None:
    server, port = live
    before = server.settled()
    sent = {name: value.format(port=port) for name, value in headers.items()}
    assert _post(port, sent) == 202
    assert server.settled() == before + 1


def test_a_get_with_a_foreign_origin_is_not_a_change(live: tuple[Live, int]) -> None:
    _server, port = live
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    connection.request("GET", "/status", headers={"Origin": "http://evil.example"})
    assert connection.getresponse().status == 200
    connection.close()


def test_the_server_closes_a_request_that_does_not_complete(
    live: tuple[Live, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Before the read time limit, this connection stayed open (more than 20 s measured).
    assert serve.PageHandler.timeout == serve_guard.READ_SECONDS
    monkeypatch.setattr(serve.PageHandler, "timeout", 0.3)
    _server, port = live
    with socket.create_connection(("127.0.0.1", port), timeout=5) as client:
        client.sendall(f"GET / HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n".encode())
        assert client.recv(4096) == b""


def _open_events(port: int) -> socket.socket:
    client = socket.create_connection(("127.0.0.1", port), timeout=5)
    client.sendall(f"GET /events HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n\r\n".encode())
    return client


def _read_until(client: socket.socket, end: bytes) -> bytes:
    data = b""
    while end not in data:
        chunk = client.recv(4096)
        if not chunk:
            break
        data += chunk
    return data


def test_an_event_connection_stays_open_after_the_read_time_limit(
    live: tuple[Live, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(serve.PageHandler, "timeout", 0.3)
    monkeypatch.setattr(serve, "KEEP_SECONDS", 0.1)
    _server, port = live
    with _open_events(port) as client:
        head = _read_until(client, b"\r\n\r\n")
        assert head.startswith(b"HTTP/1.0 200")
        time.sleep(1.0)
        # Comment lines continue to come after three times the read time limit.
        assert b": live" in client.recv(4096)


def test_an_event_connection_after_the_limit_gets_503(
    live: tuple[Live, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(serve_guard, "MAX_READERS", 2)
    _server, port = live
    first, second = _open_events(port), _open_events(port)
    try:
        for client in (first, second):
            assert _read_until(client, b"\r\n\r\n").startswith(b"HTTP/1.0 200")
        with _open_events(port) as third:
            answer = _read_until(third, b"Then try again.")
        assert answer.startswith(b"HTTP/1.0 503")
        assert b"maximum number of event connections (2)" in answer
    finally:
        first.close()
        second.close()


@pytest.mark.parametrize(
    "headers",
    [
        {"Sec-Fetch-Site": "cross-site", "Origin": "http://evil.example"},
        {"Sec-Fetch-Site": "same-site"},
        {"Origin": "http://evil.example"},
    ],
)
def test_an_event_connection_from_a_different_site_gets_403_and_no_slot(
    live: tuple[Live, int], monkeypatch: pytest.MonkeyPatch, headers: dict[str, str]
) -> None:
    """Acceptance (post-server-1): before the repair, a page of a different site got an
    event connection. Each such connection held one of the slots until the next write."""
    monkeypatch.setattr(serve_guard, "MAX_READERS", 1)
    _server, port = live
    sent = "".join(f"{name}: {value}\r\n" for name, value in headers.items())
    with socket.create_connection(("127.0.0.1", port), timeout=5) as other:
        other.sendall(f"GET /events HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n{sent}\r\n".encode())
        assert _read_until(other, b"\r\n\r\n").startswith(b"HTTP/1.0 403")
    page = f"Sec-Fetch-Site: same-origin\r\nOrigin: http://127.0.0.1:{port}\r\n"
    with socket.create_connection(("127.0.0.1", port), timeout=5) as own:
        own.sendall(f"GET /events HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n{page}\r\n".encode())
        assert _read_until(own, b"\r\n\r\n").startswith(b"HTTP/1.0 200")


class _NoDescriptors:
    """A listening socket whose accept fails as at the file descriptor limit."""

    def __init__(self, code: int) -> None:
        self.code = code
        self.calls = 0

    def accept(self) -> tuple[socket.socket, object]:
        self.calls += 1
        raise OSError(self.code, "accept failed")


@pytest.mark.parametrize(("code", "pauses"), [(errno.EMFILE, 1), (errno.ECONNABORTED, 0)])
def test_accept_pauses_only_when_the_process_has_no_descriptor(
    monkeypatch: pytest.MonkeyPatch, code: int, pauses: int
) -> None:
    # Before the pause, serve_forever called accept again at once and used 99% of one core
    # (measured with a 256 descriptor limit and 300 held connections).
    slept: list[float] = []
    monkeypatch.setattr(serve_guard.time, "sleep", slept.append)
    httpd = serve_guard.Server(("127.0.0.1", 0), serve.PageHandler, bind_and_activate=False)
    httpd.socket.close()
    httpd.socket = _NoDescriptors(code)  # type: ignore[assignment]
    with pytest.raises(OSError):
        httpd.get_request()
    assert slept == [serve_guard.ACCEPT_PAUSE] * pauses


def test_the_servers_pause_after_a_failed_accept(tmp_path: Path) -> None:
    for httpd in (
        serve.make_server(tmp_path, 0),
        serve.make_live_server(serve.LiveMap(tmp_path / "out", serve.Rendered, print), 0),
    ):
        assert isinstance(httpd, serve_guard.Server)
        httpd.server_close()
