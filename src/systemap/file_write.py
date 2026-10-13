"""Write a cache file in one operation, and lock a cache file between processes.

`write_atomic` writes the text to a temporary file of this writer in the directory of
the path. Then it replaces the path with that file. A reader gets the full previous
file or the full new file. Two writers do not use the same temporary file.

`locked` holds an exclusive lock on the file `<path>.lock` while its `with` statement
operates. A different process that tries to get the same lock waits. The operating
system releases the lock when the process stops, also after a failure.
"""

from __future__ import annotations

import errno
import os
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def write_atomic(path: Path, text: str) -> None:
    """Write the text to a temporary file of this writer. Then replace the path with it."""
    handle, name = tempfile.mkstemp(dir=path.parent, prefix=f"{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as out:
            out.write(text)
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


@contextmanager
def locked(path: Path) -> Iterator[None]:
    """Hold an exclusive lock on `<path>.lock` while the `with` statement operates."""
    lock = path.with_name(f"{path.name}.lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "a+b") as handle:
        _lock(handle.fileno())
        try:
            yield
        finally:
            _unlock(handle.fileno())


if sys.platform == "win32":
    import msvcrt

    def _lock(fd: int) -> None:
        # LK_LOCK tries again for 10 seconds. Then it raises OSError with EDEADLOCK,
        # and this function starts again. Another error stops the function.
        os.lseek(fd, 0, os.SEEK_SET)
        while True:
            try:
                msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
                return
            except OSError as exc:
                if exc.errno != errno.EDEADLOCK:
                    raise

    def _unlock(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _lock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_EX)

    def _unlock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)
