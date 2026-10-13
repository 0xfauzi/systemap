"""The watcher of `systemap live` finds the files that a render reads and scans them.

The files are the systemap configuration files, the model files, the source and test
files of the configured language, and the configuration files of the language. The
language adapter gives the configuration files that it reads (`config_paths`). This
module does not know their names.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Protocol

from systemap import config, model_load
from systemap import language as languages
from systemap.config import ConfigError

# The time between two scans of the watched files.
SCAN_SECONDS = 1.0
# The two files that can hold the systemap configuration. `config.load` reads them for
# each language. The language adapter gives its other configuration files.
CONFIG_FILES = (config.CONFIG_FILE, "pyproject.toml")


class Requester(Protocol):
    """The live map: it renders a version after a request."""

    def request(self) -> None: ...


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
    tests = [root / rel for rel in cfg.test_dirs if rel]
    folders = [package for package, _name in cfg.roots] + tests
    found += adapter.config_paths(root, folders)
    # The watcher skips the folders that the source walk of the adapter skips. Then it
    # watches each source file that extraction reads.
    for folder in folders:
        found += _files(folder, adapter.source_suffixes, adapter.skip_dirs)
    return list(dict.fromkeys(found))


def _files(folder: Path, suffixes: tuple[str, ...], skip: frozenset[str]) -> Iterator[Path]:
    """Give the files with the suffixes below the folder. Skip the folders without source."""
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
    live: Requester,
    files: Callable[[], Iterable[Path]],
    stop: Stopper,
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
