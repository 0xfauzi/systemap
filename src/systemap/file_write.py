"""Read, write, and lock a cache file or an output file in a stated root folder.

The root is the repository root, or the folder that `systemap live` serves. Each
function examines the path before it reads, makes a folder, writes, or locks:

- The path must be below the root, without a `..` part.
- The nearest folder of the path that exists, after the resolution of links, must be in
  the resolved root. Thus a cache folder or a parent folder that is a link out of the
  root gives `RefusedFile`, and the function makes no folder outside the root.

`read_text` reads only a regular file in the root. A link out of the root, a FIFO, and a
device give `RefusedFile` with the path and the cause. Thus a read does not wait on a
FIFO, and it does not read a file outside the root.

`write_atomic` writes the text to a temporary file of this writer in the directory of
the path. Then it replaces the path with that file. A link at the path is replaced. The
write does not go to the target of the link. A reader gets the full previous file or the
full new file. Two writers do not use the same temporary file.

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


class RefusedFile(Exception):
    """The command does not read, write, or lock the file, because it is not in its root."""

    def __init__(self, path: Path, cause: str) -> None:
        super().__init__(
            f"{path}: the command does not use this file, because {cause}. "
            "Remove the file or the link. Then run the command again."
        )


def _outside(root: Path) -> str:
    return f"its resolved path is not in {root}"


def confined(root: Path, path: Path) -> None:
    """Refuse a path that is not below the root, or whose nearest folder is not in it.

    The function gives RefusedFile. It does not make a folder.
    """
    if not path.is_relative_to(root) or not repo_files.plain(path.relative_to(root).as_posix()):
        raise RefusedFile(path, f"it is not below {root}, without a .. part")
    folder = path.parent
    while not os.path.lexists(folder) and folder != root:
        folder = folder.parent
    if not repo_files.inside(root, folder):
        raise RefusedFile(path, _outside(root))


def folder(root: Path, path: Path) -> None:
    """Make the folder of the path in the root. Refuse a folder that is not in the root."""
    confined(root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not repo_files.inside(root, path.parent):
        raise RefusedFile(path, _outside(root))


def read_text(root: Path, path: Path) -> str | None:
    """Give the text of a regular file in the root, or None if it is missing.

    A folder at the path is also missing. A link out of the root, a FIFO, and a device
    give RefusedFile. A different read problem gives OSError.
    """
    confined(root, path)
    if not repo_files.present(path):
        return None
    try:
        return repo_files.read_text(root, path.relative_to(root))
    except FileNotFoundError:
        return None
    except repo_files.RepoPathError as exc:
        cause = str(exc) if repo_files.inside(root, path) else _outside(root)
        raise RefusedFile(path, cause) from exc


def write_atomic(root: Path, path: Path, text: str) -> None:
    """Write the text to a temporary file of this writer. Then replace the path with it.

    The folder of the path must be in the root. A link at the path is replaced.
    """
    folder(root, path)
    handle, name = tempfile.mkstemp(dir=path.parent, prefix=f"{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as out:
            out.write(text)
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


@contextmanager
def locked(root: Path, path: Path) -> Iterator[None]:
    """Hold an exclusive lock on `<path>.lock` while the `with` statement operates.

    The folder of the lock file must be in the root.
    """
    lock = path.with_name(f"{path.name}.lock")
    folder(root, lock)
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
