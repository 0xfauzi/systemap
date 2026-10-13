"""Read, write, and lock a cache file or an output file.

`read_text` reads only a regular file in the folder of the path. A link to a file in a
different folder, a FIFO, and a device give `RefusedFile` with the path and the cause.
Thus a read does not wait on a FIFO, and it does not read a file outside the folder.

`write_atomic` writes the text to a temporary file of this writer in the directory of
the path. Then it replaces the path with that file. A reader gets the full previous
file or the full new file. Two writers do not use the same temporary file.

`locked` holds an exclusive lock on the file `<path>.lock` while its `with` statement
operates. A different process that tries to get the same lock waits. The operating
system releases the lock when the process stops, also after a failure. A lock file that
is a link, a FIFO, or a device gives `RefusedFile`.
"""

from __future__ import annotations

import errno
import os
import stat
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from systemap import repo_files

_LOCK_FLAGS = (
    os.O_RDWR
    | os.O_CREAT
    | os.O_APPEND
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_NONBLOCK", 0)
    | getattr(os, "O_BINARY", 0)
)
LINK = "it is a link"
OUTSIDE = "it is a link to a file in a different folder"


class RefusedFile(Exception):
    """The command does not read or lock the file, because it is not a regular file."""

    def __init__(self, path: Path, cause: str) -> None:
        super().__init__(
            f"{path}: the command does not use this file, because {cause}. "
            "Remove the file or the link. Then run the command again."
        )


def read_text(path: Path) -> str | None:
    """Give the text of a regular file in the folder of the path, or None if it is missing.

    A folder at the path is also missing. A link to a file in a different folder, a FIFO,
    and a device give RefusedFile. A different read problem gives OSError.
    """
    if not repo_files.present(path):
        return None
    try:
        return repo_files.read_text(path.parent, path.name)
    except FileNotFoundError:
        return None
    except repo_files.RepoPathError as exc:
        outside = path.is_symlink() and not repo_files.inside(path.parent, path)
        raise RefusedFile(path, OUTSIDE if outside else str(exc)) from exc


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
    descriptor = _open_lock(lock)
    try:
        _lock(descriptor)
        try:
            yield
        finally:
            _unlock(descriptor)
    finally:
        os.close(descriptor)


def _open_lock(lock: Path) -> int:
    """Open or make the lock file. Refuse a link, a FIFO, and a device with RefusedFile.

    The open does not wait on a FIFO. A platform without O_NOFOLLOW gets the link test
    before the open only.
    """
    if lock.is_symlink():
        raise RefusedFile(lock, LINK)
    try:
        descriptor = os.open(lock, _LOCK_FLAGS, 0o666)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise RefusedFile(lock, LINK) from exc
        raise
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise RefusedFile(lock, "the path is not a regular file")
    return descriptor


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
