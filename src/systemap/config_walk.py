"""The configuration walk finds the configuration files near the source folders.

A language can read a configuration file at the repository root, below a source folder,
or in a folder between a source folder and the repository root. The language adapter
gives the file names and the skipped folders. This module does not know a language.
"""

from __future__ import annotations

import os
from collections.abc import Collection, Iterable, Iterator
from pathlib import Path

from systemap import file_names


def nearby(
    root: Path, folders: Iterable[Path], names: Collection[str], skip: Collection[str]
) -> list[Path]:
    """Give the paths with the names at the root, below each folder, and in the folders
    between each folder and the root.

    A path at the root or between a folder and the root can name a file that does not
    exist. The walk below a folder does not enter a folder with a name in `skip`, or a
    folder with a name that is not valid UTF-8 (`file_names`).
    """
    found = [root / name for name in names]
    for folder in folders:
        found += _below(folder, names, skip)
        found += _above(root, folder, names)
    return list(dict.fromkeys(found))


def _below(folder: Path, names: Collection[str], skip: Collection[str]) -> Iterator[Path]:
    for here, folders, files in os.walk(folder):
        folders[:] = [name for name in file_names.folders(folders) if name not in skip]
        yield from (Path(here) / name for name in files if name in names)


def _above(root: Path, folder: Path, names: Collection[str]) -> list[Path]:
    between = [p for p in folder.parents if p.is_relative_to(root) and p != root]
    return [parent / name for parent in between for name in names]
