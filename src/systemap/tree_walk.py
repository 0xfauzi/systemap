"""The folder walk gives the folders and files below a folder without recursion.

In Python 3.11, `os.walk` calls itself for each folder level. Thus a folder tree that is
deeper than the recursion limit (about 1000 levels) stops the walk with a RecursionError.
This walk uses a stack. It gives the same sequence as `os.walk(top)`: the walk goes from
the top down, the caller can change the folder list, and the walk does not follow a link.

A folder tree that is deeper than MAX_DEPTH levels below the top gives a ConfigError that
names the folder. Such a tree is not a source tree of a real project.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import NoReturn

# A walk of a deeper tree gives a ConfigError. The recursive walk stopped at about 985
# levels. At depth 960, an extraction did not complete in 12 minutes (audit item rest-3).
MAX_DEPTH = 500

Step = tuple[str, list[str], list[str]]


def walk(top: str | os.PathLike[str]) -> Iterator[Step]:
    """Give (folder, folder names, file names) for each folder below `top`, as `os.walk`.

    A folder that the walk cannot read gives no step, as in `os.walk`. If the caller
    removes a name from the folder names, the walk does not go into that folder.
    """
    start = os.fspath(top)
    stack: list[tuple[str, int]] = [(start, 0)]
    while stack:
        here, level = stack.pop()
        found = _entries(here)
        if found is None:
            continue
        folders, files = found
        yield here, folders, files
        if folders and level >= MAX_DEPTH:
            _too_deep(start, here)
        below = (os.path.join(here, name) for name in reversed(folders))
        stack.extend((path, level + 1) for path in below if not os.path.islink(path))


def _entries(here: str) -> tuple[list[str], list[str]] | None:
    """Give the folder names and the file names in a folder, or None if a read fails."""
    folders: list[str] = []
    files: list[str] = []
    try:
        with os.scandir(here) as entries:
            for entry in entries:
                (folders if _is_folder(entry) else files).append(entry.name)
    except OSError:
        return None
    return folders, files


def _is_folder(entry: os.DirEntry[str]) -> bool:
    try:
        return entry.is_dir()
    except OSError:
        return False


def _too_deep(start: str, here: str) -> NoReturn:
    # The configuration module imports this module. Thus the import occurs here.
    from systemap.config import ConfigError

    raise ConfigError(
        f"The folder {Path(here)} is {MAX_DEPTH} levels below {Path(start)}, and it has more "
        "folders. The walk does not examine a deeper folder tree. Remove the deep folders."
    )
