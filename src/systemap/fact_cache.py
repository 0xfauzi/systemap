"""The fact cache keeps the source facts of each file for the next extraction.

`systemap live` extracts the facts again after each change. Usually, most files do not
change between two extractions. With this cache, the extraction uses the kept facts of
an unchanged file, and it does not parse the file again. The result is the same as the
result of a full extraction.

A kept value of a file stays valid while the file has the same text. The cache compares
the file status first: the device, the inode, the size, the modification time and the
change time. If the status is the same and the file was not changed in the RACY_NS before
the status read, the text is the same. The cache uses the later of the modification time
and the change time, because a program can set an earlier modification time after a
write. Else the cache reads the text again and compares
its SHA-256 digest. The cache reads the status before the text. Thus a change during an
extraction gives a different status at the next extraction.

The value of a file comes from a different read of the file than the digest. If the
file changes between the two reads, the value is for a different text. Thus
`remember_file` reads the digest again after it makes the value. It keeps the value only
if the digest did not change.

On Windows, `st_ctime` is the creation time of the file, and a write does not change it.
Thus a write that keeps the size and the modification time also keeps the status. On
Windows, the cache always reads the text and compares its digest. It does not parse a
file with the same digest again.

The facts of a file can also change with values that are not in the file: the set of
modules, the configuration and the parser version. The caller gives these values as the
generation of the cache. A different generation removes all kept values.

The cache gives a copy of each kept value, because the extraction changes the records
after it makes them. One extraction at a time can use a cache.
"""

from __future__ import annotations

import copy
import hashlib
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

from systemap import source_text

# A file system can keep the modification time with a resolution of 2 s (FAT). A file
# that changed in this time before the status read can change again with the same
# status. The cache then reads the text.
RACY_NS = 2_000_000_000

# The status shows each write only where the change time changes on each write.
STATUS_SHOWS_WRITES = os.name != "nt"

T = TypeVar("T")
Status = tuple[int, int, int, int, int]


@dataclass(frozen=True)
class _Seen:
    status: Status
    at: int
    digest: str


def _status(path: Path) -> Status | None:
    try:
        found = os.stat(path)
    except OSError:
        return None
    return (found.st_dev, found.st_ino, found.st_size, found.st_mtime_ns, found.st_ctime_ns)


def text_digest(text: str) -> str:
    """Give the SHA-256 digest of a source text."""
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


class FactCache:
    """The kept facts of the files of the last extraction, with the digest of each text."""

    def __init__(self) -> None:
        self.generation = ""
        self._seen: dict[Path, _Seen] = {}
        self._kept: dict[tuple[str, str], tuple[str, Any]] = {}
        # The number of values that the cache made, for each kind. The tests read it.
        self.made: dict[str, int] = {}

    def renew(self, generation: str) -> None:
        """Remove all kept values if the generation is different."""
        if generation != self.generation:
            self._kept.clear()
            self.generation = generation

    def digest(self, repo: Path, path: Path) -> str | None:
        """Give the digest of the text of a source file, or None if the file has no text.

        The text is the text that `source_text.read` gives."""
        at = time.time_ns()
        status = _status(path)
        seen = self._seen.get(path)
        if (
            STATUS_SHOWS_WRITES
            and status is not None
            and seen is not None
            and seen.status == status
        ):
            if seen.at - max(status[3], status[4]) > RACY_NS:
                return seen.digest
        try:
            text = source_text.read(repo, path)
        except (OSError, UnicodeError):
            self._seen.pop(path, None)
            return None
        digest = text_digest(text)
        if status is not None:
            self._seen[path] = _Seen(status, at, digest)
        return digest

    def remember(self, kind: str, name: str, key: str | None, make: Callable[[], T]) -> T:
        """Give the kept value of the name for the key. Else make the value and keep it.

        A key of None keeps no value. A cache without a generation keeps no value."""
        found = self._found(kind, name, key)
        if found:
            value: T = found[0]
            return value
        value = self._make(kind, make)
        self._keep(kind, name, key, value)
        return value

    def remember_file(
        self, kind: str, name: str, repo: Path, path: Path, make: Callable[[], T]
    ) -> T:
        """Give the kept value of a file with the same text. Else make the value.

        `make` reads the file. The key is the digest of the text before `make`. The cache
        keeps the value only if the digest after `make` is the same as the key."""
        key = self.digest(repo, path)
        found = self._found(kind, name, key)
        if found:
            value: T = found[0]
            return value
        value = self._make(kind, make)
        if key is not None and self.digest(repo, path) == key:
            self._keep(kind, name, key, value)
        return value

    def _found(self, kind: str, name: str, key: str | None) -> tuple[Any, ...]:
        """Give a copy of the kept value for the key in a tuple, or an empty tuple."""
        found = self._kept.get((kind, name))
        if key is None or found is None or found[0] != key:
            return ()
        return (copy.deepcopy(found[1]),)

    def _make(self, kind: str, make: Callable[[], T]) -> T:
        self.made[kind] = self.made.get(kind, 0) + 1
        return make()

    def _keep(self, kind: str, name: str, key: str | None, value: object) -> None:
        if key is not None and self.generation:
            self._kept[(kind, name)] = (key, copy.deepcopy(value))


def kept(cache: FactCache | None, kind: str, name: str, key: str, make: Callable[[], T]) -> T:
    """Give the kept value of the cache for the key, or make the value without a cache."""
    return make() if cache is None else cache.remember(kind, name, key, make)
