"""The watcher of `systemap live` finds the files that a render reads and scans them.

The files are the configuration files, the model files, and the source and test files
of the configured language. A language also reads its configuration files below the
repository root. Thus the watcher includes the configuration files of the language
adapter below each package root and in the folders between a package root and the
repository root.
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
# The configuration files and the files that extraction records in its provenance.
CONFIG_FILES = (config.CONFIG_FILE, "pyproject.toml", "package.json", "tsconfig.json")


class Requester(Protocol):
    """The live map: it renders a version after a request."""

    def request(self) -> None: ...


class Stopper(Protocol):
    """The stop event of the scan."""

    def wait(self, timeout: float, /) -> bool: ...


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
    for folder in {cfg.model_path.parent, *(path.parent for path in models)}:
        found += sorted(folder.glob(model_load.MODEL_FILES))
    if not cfg.language:
        return found
    adapter = languages.repository(cfg.language)
    tests = [root / rel for rel in cfg.test_dirs if rel]
    folders = [package for package, _name in cfg.roots] + tests
    # Output folders hold no source of the project, for each language.
    skip = adapter.skip_dirs | config.OUTPUT_DIRS
    # A language reads its configuration files below the repository root also, such as
    # the nearest configuration file above a source file.
    configs = tuple(Path(rel).name for rel in adapter.config_files)
    for folder in folders:
        found += _files(folder, adapter.source_suffixes, skip, configs)
        found += _above(root, folder, configs)
    return found


def _files(
    folder: Path, suffixes: tuple[str, ...], skip: frozenset[str], configs: tuple[str, ...]
) -> Iterator[Path]:
    """Give the files with the suffixes or the configuration names below the folder. Skip
    the folders without source."""
    for here, folders, names in os.walk(folder):
        folders[:] = [name for name in folders if name not in skip]
        yield from (
            Path(here) / name for name in names if name.endswith(suffixes) or name in configs
        )


def _above(root: Path, folder: Path, configs: tuple[str, ...]) -> list[Path]:
    """Give the configuration paths in the folders between the folder and the root."""
    between = [p for p in folder.parents if p.is_relative_to(root) and p != root]
    return [parent / name for parent in between for name in configs]


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
