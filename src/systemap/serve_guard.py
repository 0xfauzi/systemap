"""The page servers refuse requests from other web sites and limit slow clients.

A web page from a different site can send a POST request to 127.0.0.1 without CORS
permission, for example with a form or with `navigator.sendBeacon`. The browser then
sends `Sec-Fetch-Site: cross-site` or an `Origin` header of that site. The servers refuse
such a request that changes the state. A program that sends no such header, for example
curl or the coding agent hook, can still send `POST /refresh`.

Each connection has a read time limit, so a client that does not complete its request
cannot keep a thread. The full request line and headers must arrive in that time. Thus a
client that sends one byte in each read time limit also loses its connection. The
number of event connections has a limit. If the process has no
more file descriptors, the server stops for a short time before the next accept.
"""

from __future__ import annotations

import errno
import io
import socket
import time
from email.message import Message
from http.server import ThreadingHTTPServer
from typing import Any

# The maximum time in seconds of one read or write on a connection.
READ_SECONDS = 10.0
# The maximum number of open event connections of a live server.
MAX_READERS = 32
# The time in seconds between two accept attempts when the process has no free descriptor.
ACCEPT_PAUSE = 0.1
# Errors of accept that do not go away at once.
PAUSE_ERRORS = frozenset({errno.EMFILE, errno.ENFILE, errno.ENOBUFS, errno.ENOMEM})
# Methods that do not change the state of the server.
SAFE_METHODS = frozenset({"GET", "HEAD"})
# The Sec-Fetch-Site values of a request from the page itself or from the person.
OWN_SITE = frozenset({"same-origin", "none"})


class ReadersFull(Exception):
    """The live server has the maximum number of event connections."""


def readers_full() -> ReadersFull:
    return ReadersFull(
        f"The server has the maximum number of event connections ({MAX_READERS}). "
        "Close a page of the live map. Then try again."
    )


def other_site(method: str, headers: Message, port: int) -> bool:
    """Tell if a request that changes the state comes from a page of a different site."""
    if method in SAFE_METHODS:
        return False
    fetch_site = headers.get("Sec-Fetch-Site")
    if fetch_site is not None and fetch_site not in OWN_SITE:
        return True
    origin = headers.get("Origin")
    return origin is not None and origin not in {
        f"http://127.0.0.1:{port}",
        f"http://localhost:{port}",
    }


class Server(ThreadingHTTPServer):
    """A threading HTTP server that does not use all the processor time when accept fails."""

    def get_request(self) -> tuple[socket.socket, Any]:
        try:
            return super().get_request()
        except OSError as exc:
            if exc.errno in PAUSE_ERRORS:
                time.sleep(ACCEPT_PAUSE)
            raise


class HeadReader(io.RawIOBase):
    """Read a connection with one time limit for the full head of each request.

    `start` sets the limit before the request line. `stop` removes it after the headers.
    Then each read and write has the time limit of the socket again."""

    def __init__(self, connection: socket.socket, seconds: float | None) -> None:
        super().__init__()
        self._connection = connection
        self._seconds = seconds
        self._end: float | None = None

    def readable(self) -> bool:
        return True

    def start(self) -> None:
        if self._seconds is not None:
            self._end = time.monotonic() + self._seconds

    def stop(self) -> None:
        self._end = None
        self._connection.settimeout(self._seconds)

    def readinto(self, buffer: Any) -> int:
        if self._end is not None:
            left = self._end - time.monotonic()
            if left <= 0:
                raise TimeoutError("The request head did not arrive in the time limit.")
            self._connection.settimeout(left)
        return self._connection.recv_into(buffer)
