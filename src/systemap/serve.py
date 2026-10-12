"""The page servers supply map pages through HTTP on the loopback address.

`systemap serve` supplies the output directory. The page script must have an HTTP
address. A port that the computer cannot give to the server is an option error, and the
message tells the person how to select a port.

`systemap live` renders the pages of the working tree into a temporary directory and
supplies that directory. It does not write the output directory or a tracked file.
The Changes view compares the working tree with the merge base of a base ref and HEAD.
When a watched file changes, or after `POST /refresh`, the command renders the pages
again. Each time, the pages get a new version number. The command renders one version
at a time. A request while the command renders causes one more version after the
current version. If the command cannot render a version, it keeps the last pages and
gives the error.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import json
import os
import queue
import shutil
import signal
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from functools import partial
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import FrameType
from typing import Any

from systemap import change, config, delta, explain, extract, figure, history, nest, page, page_live
from systemap.config import ArgumentError, Config, ConfigError
from systemap.model import problems as model_problems
from systemap.source_text import PYTHON_SKIP
from systemap.typescript_config import SOURCE_SKIP, SOURCE_SUFFIXES

DEFAULT_PORT = 8765
# Without --base, the first of these refs that has a merge base with HEAD is the
# comparison base.
BASES = ("origin/HEAD", "origin/main", "main", "origin/master", "master")
# The figure beside the page: the change figure, or the system figure without a change.
FIGURE = "change.svg"
# The time between two scans of the watched files.
SCAN_SECONDS = 1.0
# The time between two comment lines on an event connection. A write to a closed
# connection gives an error, so the server finds closed connections.
KEEP_SECONDS = 15.0
# The configuration files and the files that extraction records in its provenance.
CONFIG_FILES = (config.CONFIG_FILE, "pyproject.toml", "package.json", "tsconfig.json")


def _listen(handler: Callable[..., BaseHTTPRequestHandler], port: int) -> ThreadingHTTPServer:
    try:
        return ThreadingHTTPServer(("127.0.0.1", port), handler)
    except (OSError, OverflowError) as exc:
        reason = exc.strerror if isinstance(exc, OSError) and exc.strerror else str(exc)
        raise ArgumentError(
            f"The server cannot use port {port}: {reason}. Use --port 0 to select an "
            f"available port, or give a different port."
        ) from exc


class PageHandler(SimpleHTTPRequestHandler):
    """Supply files only for requests to this loopback server.

    A web page can make its own domain name point at 127.0.0.1 (DNS rebinding). Then the
    browser sends that name in the Host header. The server refuses each request whose Host
    is not 127.0.0.1 or localhost with the server port, so such a page cannot read the map.
    """

    def parse_request(self) -> bool:
        if not super().parse_request():
            return False
        port = self.server.server_address[1]  # type: ignore[index] # a TCP server: (host, port)
        if self.headers.get("Host", "") in {f"127.0.0.1:{port}", f"localhost:{port}"}:
            return True
        self.send_error(403, "The server answers only requests to 127.0.0.1 or localhost.")
        return False


def make_server(directory: Path, port: int) -> ThreadingHTTPServer:
    """Make an HTTP server for `directory` on 127.0.0.1. Port 0 selects an available port."""
    return _listen(partial(PageHandler, directory=str(directory)), port)


# ---- one version of the working tree --------------------------------------------------


@dataclass(frozen=True)
class Rendered:
    """The pages, the figure and the map update lines of one version.

    `files` maps a path in the served directory to its text. `lines` are the map update
    lines, each with its text and its action. `components` are the changed components
    of the top map. `models` are the model files of the map tree.
    """

    files: dict[str, str] = dataclasses.field(default_factory=dict)
    updates: int = 0
    lines: tuple[dict[str, str], ...] = ()
    components: tuple[str, ...] = ()
    comparison_base: str = ""
    models: tuple[Path, ...] = ()
    seconds: float = 0.0
    svg: str = ""
    svg_bytes: int = 0


def render_tree(root: Path, base: str) -> Rendered:
    """Render the pages and the figure of the working tree. Write no file.

    The facts come from the source files and the models from the model files. With a
    base, the Changes view and the map update lines compare the working tree with the
    merge base of the base and HEAD. `systemap delta` uses the same comparison of the
    facts for all maps.
    """
    cfg = config.load(root)
    tree = nest.load(cfg)
    _no_problems(tree)
    facts = extract.build(cfg)
    compared = {m.id: _compare(cfg, m, base, facts) for m in tree.maps}
    files = {
        m.page_path(cfg).relative_to(cfg.out_path).as_posix(): page.build(
            cfg,
            m.model,
            m.meaning,
            m.theme,
            facts,
            compared[m.id],
            nesting=page.nesting_of(cfg, tree, m, facts),
        )
        for m in tree.maps
    }
    top = compared[tree.top.id]
    files[FIGURE] = _figure(cfg, tree, facts, base, top)
    lines = _updates(cfg, tree, facts, base, top.get("comparison_base", ""))
    return Rendered(
        files=files,
        updates=len(lines),
        lines=lines,
        components=tuple(sorted(top.get("direct", ()))),
        comparison_base=top.get("comparison_base", ""),
        models=tuple(m.path for m in tree.maps),
    )


def _no_problems(tree: nest.Tree) -> None:
    """Give the model contradictions as one error, as `systemap render` gives them."""
    found = {m.rel: model_problems(m.model, m.meaning) for m in tree.maps}
    lines = [f"{m.prefix}{line}" for m in tree.maps for line in found[m.rel]]
    if lines:
        files = ", ".join(rel for rel, problems in found.items() if problems)
        raise ConfigError("\n".join([*lines, f"Correct {files}. Then use systemap check."]))


def _compare(cfg: Config, m: nest.Map, base: str, facts: dict[str, Any]) -> dict[str, Any]:
    if not base:
        return {"has_change": False}
    return change.for_page(cfg, m, base, facts, change.WORKING_TREE)


def _figure(
    cfg: Config, tree: nest.Tree, facts: dict[str, Any], base: str, ch: dict[str, Any]
) -> str:
    """Give the change figure as SVG, or the system figure if the comparison has no change."""
    m = tree.top
    svg, _collisions = figure.make(
        cfg,
        m.model,
        m.meaning,
        m.theme,
        facts,
        mode="change" if ch.get("has_change") else "system",
        base=base,
        head=change.WORKING_TREE,
        bare=True,
        opens=nest.opens(tree, m, links=False),
    )
    return svg


def _updates(
    cfg: Config, tree: nest.Tree, facts: dict[str, Any], base: str, merge_base: str
) -> tuple[dict[str, str], ...]:
    """Give the delta lines that need an action, for the working tree and the merge base."""
    if not merge_base:
        return ()
    found = delta.compute_tree(
        cfg,
        tree,
        history.facts_at(cfg, merge_base),
        facts,
        base_ref=base,
        head_ref=change.WORKING_TREE,
    )
    return tuple({"text": line.text, "action": _action(line.kind)} for line in found.open)


def _action(kind: str) -> str:
    lesson = explain.lesson(kind)
    return lesson.do if lesson else ""


def _error_text(exc: Exception) -> str:
    """Give the message of a known error, or the error type and its message."""
    if isinstance(exc, (ConfigError, change.ChangeError, delta.DeltaError, figure.FigureError)):
        return str(exc)
    return f"{type(exc).__name__}: {exc}"


# ---- the live map: versions, state and event readers -----------------------------------


class LiveMap:
    """The state of the live map.

    The command renders one version at a time. A request while the command renders
    causes one more version after the current version. The script of each page has the
    number of its version. If the command cannot render a version, the files of the last
    good version stay.
    """

    def __init__(
        self,
        out: Path,
        render: Callable[[], Rendered],
        emit: Callable[[dict[str, Any]], None],
        base: str = "",
    ) -> None:
        self.out = out
        self.url = ""
        self.base = base
        self.comparison_base = ""
        self._render = render
        self._emit = emit
        self._lock = threading.Lock()
        self._version = 0
        self._good = 0
        self._state = "rendering"
        self._error = ""
        self._last = Rendered()
        self._busy = False
        self._again = False
        self._closed = False
        self._readers: list[queue.Queue[str | None]] = []
        self._thread: threading.Thread | None = None
        self._write({"index.html": page_live.waiting_page()}, 0)

    # -- versions --

    def request(self) -> None:
        """Start a version, or ask for one more version after the current version."""
        with self._lock:
            if self._closed:
                return
            if self._busy:
                self._again = True
                return
            self._busy = True
            self._thread = threading.Thread(target=self._run, name="systemap-live", daemon=True)
        self._thread.start()

    def wait(self, timeout: float | None = None) -> None:
        """Wait until the command has no version to render."""
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def _run(self) -> None:
        again = True
        while again:
            self._once()
            with self._lock:
                again, self._again = self._again and not self._closed, False
                self._busy = again

    def _once(self) -> None:
        with self._lock:
            self._version += 1
            version = self._version
            self._state = "rendering"
        self.say({"event": "rendering", "version": version})
        started = time.perf_counter()
        try:
            result = self._render()
        except Exception as exc:  # noqa: BLE001 - a failed render keeps the last page
            self._failed(version, _error_text(exc))
            return
        self._done(version, dataclasses.replace(result, seconds=time.perf_counter() - started))

    def _failed(self, version: int, text: str) -> None:
        with self._lock:
            self._state, self._error = "error", text
            if not self._good:
                self._write({"index.html": page_live.error_page(text)}, version)
        self.say({"event": "error", "version": version, "text": text})
        self._send("error", {"version": version, "text": text})

    def _done(self, version: int, result: Rendered) -> None:
        with self._lock:
            self._write(result.files, version)
            svg = self.out / FIGURE
            self._last = dataclasses.replace(
                result,
                svg=str(svg) if FIGURE in result.files else "",
                svg_bytes=len(result.files.get(FIGURE, "").encode("utf-8")),
            )
            self._state, self._error, self._good = "ready", "", version
            self.comparison_base = result.comparison_base
            last = self._last
        self.say(
            {
                "event": "rendered",
                "version": version,
                "seconds": round(last.seconds, 2),
                "updates": last.updates,
                "components": list(last.components),
                "svg": last.svg,
                "svg_bytes": last.svg_bytes,
            }
        )
        self._send("rendered", {"version": version})

    def _write(self, files: dict[str, str], version: int) -> None:
        """Write the files. A page gets the script. The caller holds the lock."""
        if self._closed:
            return
        for name, text in files.items():
            path = self.out / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if name.endswith(".html"):
                text = page_live.with_script(text, version)
            part = path.with_name(path.name + ".part")
            part.write_text(text, encoding="utf-8", newline="\n")
            os.replace(part, path)

    # -- state --

    def models(self) -> tuple[Path, ...]:
        with self._lock:
            return self._last.models

    def status(self) -> dict[str, Any]:
        """Give the state for `GET /status`."""
        with self._lock:
            last = self._last
            return {
                "version": self._version,
                "state": self._state,
                "seconds": round(last.seconds, 2),
                "updates": last.updates,
                "lines": [dict(line) for line in last.lines],
                "components": list(last.components),
                "error": self._error,
                "url": self.url,
                "svg": last.svg,
                "svg_bytes": last.svg_bytes,
                "base": self.base,
                "comparison_base": self.comparison_base,
            }

    # -- event readers --

    def listen(self) -> queue.Queue[str | None]:
        """Add an event reader. First, the reader gets the number of the last good version."""
        reader: queue.Queue[str | None] = queue.Queue()
        with self._lock:
            self._readers.append(reader)
            if self._good:
                reader.put(_event("rendered", {"version": self._good}))
        return reader

    def forget(self, reader: queue.Queue[str | None]) -> None:
        with self._lock:
            if reader in self._readers:
                self._readers.remove(reader)

    def say(self, event: dict[str, Any]) -> None:
        """Write one event line. After close, write nothing: the last line is `stopped`."""
        with self._lock:
            if not self._closed:
                self._emit(event)

    def _send(self, name: str, data: dict[str, Any]) -> None:
        message = _event(name, data)
        with self._lock:
            readers = [] if self._closed else list(self._readers)
        for reader in readers:
            reader.put(message)

    def close(self) -> None:
        """Stop the versions and the event readers. After this, the command writes no file."""
        with self._lock:
            self._closed = True
            readers = list(self._readers)
        for reader in readers:
            reader.put(None)


def _event(name: str, data: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"


# ---- the HTTP server -----------------------------------------------------------------


class LiveHandler(PageHandler):
    """Supply the rendered files, the events and the state, and receive the requests."""

    def __init__(self, live: LiveMap, *args: Any, **kwargs: Any) -> None:
        self.live = live
        super().__init__(*args, directory=str(live.out), **kwargs)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/events":
            self._events()
        elif path == "/status":
            self._json(200, self.live.status())
        else:
            super().do_GET()

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != "/refresh":
            self._json(404, {"error": "Use POST /refresh."})
            return
        self.live.request()
        self._json(202, {"queued": True})

    def end_headers(self) -> None:
        # The browser must load each version again, not a stored copy.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - the base name
        """Write no request line. Standard output is for the JSON lines."""

    def _json(self, code: int, body: dict[str, Any]) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _events(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        reader = self.live.listen()
        try:
            for message in _messages(reader):
                self.wfile.write(message.encode("utf-8"))
                self.wfile.flush()
        except OSError:
            return
        finally:
            self.live.forget(reader)


def _messages(reader: queue.Queue[str | None]) -> Iterator[str]:
    """Give the event messages of one reader, with a comment line at regular times."""
    yield ": live\n\n"
    while True:
        try:
            message = reader.get(timeout=KEEP_SECONDS)
        except queue.Empty:
            message = ": live\n\n"
        if message is None:
            return
        yield message


def make_live_server(live: LiveMap, port: int) -> ThreadingHTTPServer:
    """Make the server of the live map on 127.0.0.1. Port 0 selects an available port."""
    httpd = _listen(partial(LiveHandler, live), port)
    live.url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    return httpd


# ---- the watched files -----------------------------------------------------------------


def watched(root: Path, models: Iterable[Path] = ()) -> list[Path]:
    """Give the files that the command reads: the configuration, the model files, and the
    source and test files of the configured language.

    If the configuration does not load, give the configuration files only.
    """
    found = [root / name for name in CONFIG_FILES]
    try:
        cfg = config.load(root)
    except ConfigError:
        return found
    suffixes = (".py",) if cfg.language == extract.PYTHON.name else SOURCE_SUFFIXES
    for folder in {cfg.model_path.parent, *(path.parent for path in models)}:
        found += sorted(folder.glob("*.py"))
    tests = [root / rel for rel in cfg.test_dirs if rel]
    folders = [package for package, _name in cfg.roots] + tests
    for folder in folders:
        found += _files(folder, suffixes)
    return found


def _files(folder: Path, suffixes: tuple[str, ...]) -> Iterator[Path]:
    """Give the files with the suffixes below the folder. Skip the folders without source."""
    skip = PYTHON_SKIP | SOURCE_SKIP
    for here, folders, names in os.walk(folder):
        folders[:] = [name for name in folders if name not in skip]
        yield from (Path(here) / name for name in names if name.endswith(suffixes))


def scan(paths: Iterable[Path]) -> dict[str, tuple[int, int]]:
    """Give the change time and the size of each file that exists."""
    found: dict[str, tuple[int, int]] = {}
    for path in paths:
        try:
            stat = path.stat()
        except OSError:
            continue
        found[str(path)] = (stat.st_mtime_ns, stat.st_size)
    return found


def watch(
    live: LiveMap,
    files: Callable[[], Iterable[Path]],
    stop: threading.Event,
    seconds: float = SCAN_SECONDS,
) -> None:
    """Scan the files at each interval. After a change, request a version when the next
    scan finds no more change."""
    last = scan(files())
    changed = False
    while not stop.wait(seconds):
        now = scan(files())
        if now != last:
            last, changed = now, True
        elif changed:
            changed = False
            live.request()


# ---- the command ---------------------------------------------------------------------


def comparison_ref(root: Path, given: str) -> str:
    """Give the comparison base: the given ref, or the first ref of BASES with a merge
    base with HEAD. Give an empty string if no ref has one.

    A given ref without a merge base with HEAD gives ChangeError.
    """
    if given:
        change.comparison_base(root, given)
        return given
    for ref in BASES:
        try:
            change.comparison_base(root, ref)
        except change.ChangeError:
            continue
        return ref
    return ""


def _short(revision: str) -> str:
    return revision[:7]


HUMAN: dict[str, Callable[[dict[str, Any]], str]] = {
    "serving": lambda e: (
        f"map: The live map is at {e['url']}. Use Ctrl-C to stop the server.\n"
        + (
            f"map: The Changes view compares the working tree with {e['base']} at the "
            f"merge base {_short(e['comparison_base'])}."
            if e["base"]
            else "map: No base ref is available. The page has no revision comparison."
        )
    ),
    "rendering": lambda e: f"map: The command renders version {e['version']}.",
    "rendered": lambda e: (
        f"map: Version {e['version']} is on the page ({e['seconds']:.1f} s). Map updates: "
        f"{e['updates']}. Changed components: {', '.join(e['components']) or 'none'}."
    ),
    "error": lambda e: (
        f"map: The command could not render version {e['version']}. The page does not "
        f"change.\n{e['text']}"
    ),
    "stopped": lambda e: "map: The server stopped.",
}


def printer(as_json: bool) -> Callable[[dict[str, Any]], None]:
    """Give the function that writes one event: a JSON line, or text for a person."""
    lock = threading.Lock()

    def emit(event: dict[str, Any]) -> None:
        text = json.dumps(event) if as_json else HUMAN[event["event"]](event)
        with lock:
            try:
                print(text, flush=True)
            except OSError:
                return

    return emit


def _stop(_signum: int, _frame: FrameType | None) -> None:
    raise KeyboardInterrupt


# Windows cannot send SIGTERM to a different process: it ends the process at once.
# There, Ctrl-Break (SIGBREAK) stops the command.
STOP_SIGNALS = [signal.SIGTERM]
if sys.platform == "win32":
    STOP_SIGNALS.append(signal.SIGBREAK)


@contextlib.contextmanager
def _sigterm_stops() -> Iterator[None]:
    """In the main thread, SIGTERM and SIGBREAK stop the command as Ctrl-C does."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    before = {number: signal.signal(number, _stop) for number in STOP_SIGNALS}
    try:
        yield
    finally:
        for number, handler in before.items():
            signal.signal(number, handler)


def run(root: Path, port: int, base: str, scan_files: bool, emit: Callable[..., None]) -> int:
    """Supply the live map until Ctrl-C, SIGTERM, or SIGBREAK. Then delete the temporary directory.

    A port that the computer cannot give is an option error. Then the command writes no
    event line.
    """
    ref = comparison_ref(root, base)
    out = Path(tempfile.mkdtemp(prefix="systemap-live-"))
    live = LiveMap(out, partial(render_tree, root, ref), emit, base=ref)
    stop = threading.Event()
    with _sigterm_stops():
        try:
            _serve(make_live_server(live, port), live, root, scan_files, stop)
        except KeyboardInterrupt:
            pass
        finally:
            stop.set()
            live.close()
            shutil.rmtree(out, ignore_errors=True)
    emit({"event": "stopped"})
    return 0


def _serve(
    httpd: ThreadingHTTPServer, live: LiveMap, root: Path, scan_files: bool, stop: threading.Event
) -> None:
    """Write the serving line, start the scan and the first version, and supply the pages."""
    try:
        live.comparison_base = change.comparison_base(root, live.base) if live.base else ""
        live.say(
            {
                "event": "serving",
                "url": live.url,
                "base": live.base,
                "comparison_base": live.comparison_base,
            }
        )
        if scan_files:
            files = partial(_inputs, root, live)
            threading.Thread(
                target=watch, args=(live, files, stop), name="systemap-live-watch", daemon=True
            ).start()
        live.request()
        httpd.serve_forever()
    finally:
        httpd.server_close()


def _inputs(root: Path, live: LiveMap) -> list[Path]:
    """Give the watched files with the model files of the last good version."""
    return watched(root, live.models())


def cmd_live(args: argparse.Namespace) -> int:
    from systemap.cli import _root

    return run(_root(args), int(args.port), args.base, not args.no_watch, printer(bool(args.json)))


def add_parsers(sub: Any, add_root: Callable[[argparse.ArgumentParser], None]) -> None:
    s = sub.add_parser(
        "live",
        help="Supply the map of the working tree. Render it again after each change.",
        description=(
            "This command renders the page of the working tree into a temporary directory "
            "and supplies it on 127.0.0.1. It does not write the output directory. The "
            "Changes view compares the working tree with the merge base of the base ref and "
            "HEAD. When a source, model, or configuration file changes, or after POST "
            "/refresh, the command renders the page again. Then the browser loads the page "
            "again and keeps the view. GET /status gives the state as JSON. GET /events "
            "gives the events."
        ),
    )
    add_root(s)
    s.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="Set the server port. The default is 8765. Use 0 to select an available port.",
    )
    s.add_argument(
        "--base",
        default="",
        metavar="REF",
        help=(
            "Set the base ref of the Changes view. The default is the first of "
            + ", ".join(BASES)
            + " that has a merge base with HEAD. Without one, the page has no revision "
            "comparison."
        ),
    )
    s.add_argument(
        "--no-watch",
        dest="no_watch",
        action="store_true",
        help="Do not scan the files. Render the page again only after POST /refresh.",
    )
    s.add_argument(
        "--json",
        action="store_true",
        help="For each event, write one JSON object on a line of standard output.",
    )
    s.set_defaults(func=cmd_live)
