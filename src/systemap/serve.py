"""The page server supplies the output directory over HTTP on the loopback address.

The page script must have an HTTP address. A port that the computer cannot give to the
server is an option error, and the message tells the person how to select a port.
"""

from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from systemap.config import ArgumentError


def make_server(directory: Path, port: int) -> ThreadingHTTPServer:
    """Make an HTTP server for `directory` on 127.0.0.1. Port 0 selects an available port."""
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    try:
        return ThreadingHTTPServer(("127.0.0.1", port), handler)
    except (OSError, OverflowError) as exc:
        reason = exc.strerror if isinstance(exc, OSError) and exc.strerror else str(exc)
        raise ArgumentError(
            f"The server cannot use port {port}: {reason}. Use --port 0 to select an "
            f"available port, or give a different port."
        ) from exc
