"""The watcher of `systemap live` finds the files that a render reads and scans them.

The files are the systemap configuration files, the model files, the source and test
files of the configured language, and the configuration files of the language. The test
rule of the language adapter selects the test files, as for extraction. The
language adapter gives the configuration files that it reads (`config_paths`). This
module does not know their names.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Protocol

from systemap import config, model_load, tree_walk
from systemap import language as languages
from systemap.config import ConfigError

# The minimum time between two scans of the watched files. After a slow scan, the
# watcher waits two times the processor time of that scan. Thus the scans use not more
# than one third of one processor. This limit does not apply to the time that a scan
# waits for files. If a scan waits for files on a slow disk, it uses little processor
# time, and the next scan can start after `SCAN_SECONDS`.
SCAN_SECONDS = 1.0
# The clock of the scan time: the processor time of the watcher thread. During a render,
# the scan thread waits for the Python lock. That wait is not a cost of the scan, and
# the wall time of the scan increases by a large quantity. If the watcher waits two times
# that wall time, it finds a change some seconds late.
SCAN_CLOCK = time.thread_time
# The two files that can hold the systemap configuration. `config.load` reads them for
# each language. The language adapter gives its other configuration files.
CONFIG_FILES = (config.CONFIG_FILE, "pyproject.toml")


class Requester(Protocol):
    """The live map: it renders a version after a request. It also shows a scan error.

    `scan_failed` gets the error text of a failed scan. It gets an empty text when a scan
    gives a result again.
    """

    def request(self) -> None: ...

    def scan_failed(self, text: str) -> None: ...


class Stopper(Protocol):
    """The stop event of the scan."""

    def wait(self, timeout: float, /) -> bool: ...


def watched(root: Path, models: Iterable[Path] = ()) -> list[Path]:
    """Give the files that the command reads: the configuration, the model files, and the
    source and test files of the configured language.

    If the configuration does not load, give the configuration files of each adapter only.
    """
    found = [root / name for name in CONFIG_FILES]
    try:
        cfg = config.load(root)
    except ConfigError:
        cfg = None
    if cfg is None or not cfg.language:
        for name in languages.names():
            found += languages.repository(name).config_paths(root, ())
    if cfg is None:
        return list(dict.fromkeys(found))
    for folder in {cfg.model_path.parent, *(path.parent for path in models)}:
        found += sorted(folder.glob(model_load.MODEL_FILES))
    if not cfg.language:
        return list(dict.fromkeys(found))
    adapter = languages.repository(cfg.language)
    # Read the test directories one time: if they are not configured, each read walks
    # the repository.
    test_dirs = cfg.test_dirs
    tests = [root / rel for rel in test_dirs if rel]
    folders = [package for package, _name in cfg.roots] + tests
    found += adapter.config_paths(root, folders)
    # The watcher skips the folders that the source walk of the adapter skips. Then it
    # watches each source file that extraction reads.
    for folder in folders:
        found += _files(folder, adapter.source_suffixes, adapter.skip_dirs)
    found += _tests(root, cfg, test_dirs)
    return list(dict.fromkeys(found))


def _tests(root: Path, cfg: config.Config, test_dirs: tuple[str, ...]) -> list[Path]:
    """Give the test files that extraction reads: the files that the test rule of the
    adapter selects, below the repository root.

    A test pattern can select a file out of the package roots and the test directories.
    If the adapter is not installed, give no file. Then the render gives the error.
    """
    try:
        adapter = languages.adapter(cfg.language)
    except languages.LanguageError:
        return []
    return [
        path
        for path in _files(root, adapter.source_suffixes, adapter.skip_dirs)
        if adapter.is_test_file(path.relative_to(root).as_posix(), test_dirs, cfg.test_patterns)
    ]


def _files(folder: Path, suffixes: tuple[str, ...], skip: frozenset[str]) -> Iterator[Path]:
    """Give the files with the suffixes below the folder. Skip the folders without source."""
    for here, folders, names in tree_walk.walk(folder):
        folders[:] = [name for name in folders if name not in skip]
        yield from (Path(here) / name for name in names if name.endswith(suffixes))


def scan(paths: Iterable[Path]) -> dict[str, tuple[int, int]]:
    """Give the change time and the size of each file that exists.

    A path with a NUL character names no file. Thus it gives no entry.
    """
    found: dict[str, tuple[int, int]] = {}
    for path in paths:
        try:
            stat = path.stat()
        except (OSError, ValueError):
            continue
        found[str(path)] = (stat.st_mtime_ns, stat.st_size)
    return found


def watch(
    live: Requester,
    files: Callable[[], Iterable[Path]],
    stop: Stopper,
    seconds: float = SCAN_SECONDS,
    clock: Callable[[], float] = SCAN_CLOCK,
) -> None:
    """Scan the files at each interval. After a change, request a version when the next
    scan finds no more change.

    If a scan fails, the live map shows the error, and the watcher continues. The interval
    is `seconds`, or two times the time of the last scan if that time is longer. The
    `clock` gives the time of a scan. The default is the processor time of the thread.
    """
    scanner = _Scanner(live, files, clock)
    last = scanner.scan({})
    changed = False
    while not stop.wait(scanner.interval(seconds)):
        now = scanner.scan(last)
        if now != last:
            last, changed = now, True
        elif changed:
            changed = False
            live.request()


class _Scanner:
    """One scan of the watched files, with the time of the scan and its last error."""

    def __init__(
        self, live: Requester, files: Callable[[], Iterable[Path]], clock: Callable[[], float]
    ) -> None:
        self.live = live
        self.files = files
        self.clock = clock
        self.seconds = 0.0
        self.error = ""

    def scan(self, last: dict[str, tuple[int, int]]) -> dict[str, tuple[int, int]]:
        """Give the result of a new scan. If the scan fails, give `last`.

        The live map gets each different error text one time. When a scan gives a result
        again, the live map gets an empty text.
        """
        started = self.clock()
        try:
            found = scan(self.files())
        except Exception as exc:  # noqa: BLE001 - one failed scan does not stop the watcher
            found = last
            self._failed(f"The watcher could not scan the files. {type(exc).__name__}: {exc}")
        else:
            self._failed("")
        self.seconds = self.clock() - started
        return found

    def interval(self, seconds: float) -> float:
        """Give the time until the next scan."""
        return max(seconds, 2 * self.seconds)

    def _failed(self, text: str) -> None:
        if text != self.error:
            self.error = text
            self.live.scan_failed(text)
