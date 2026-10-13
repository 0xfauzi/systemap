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
full new file. Two writers do not use the same temporary file. A new file gets the mode
of a usual write: 0666 without the bits of the umask. A regular file that is at the path
keeps its mode.

A different process can change a folder of the path to a link after the check. Where
`repo_files.WALK` is true, `write_atomic` and `locked` open the resolved folder one part
at a time, without a link, and they make, replace, and open the file relative to that
open folder. A part that is a link at that time gives `RefusedFile`. On Windows, the two
functions use the checked path, and a change of a folder after the check is not found.

`locked` holds an exclusive lock on the file `<path>.lock` while its `with` statement
operates. A different process that tries to get the same lock waits. The operating
system releases the lock when the process stops, also after a failure. A lock file that
is a link, a FIFO, or a device gives `RefusedFile`.
"""

from __future__ import annotations

import errno
import os
import secrets
import stat
import sys
from collections.abc import Iterator
from contextlib import contextmanager, suppress
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
# O_EXCL refuses a path that is present, also a link.
_TEMPORARY_FLAGS = (
    os.O_WRONLY
    | os.O_CREAT
    | os.O_EXCL
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_NOINHERIT", 0)
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
    if repo_files.WALK:
        os.close(_open_parent(root, path))
        return
    confined(root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not repo_files.inside(root, path.parent):
        raise RefusedFile(path, _outside(root))


def _open_parent(root: Path, path: Path) -> int:
    """Make and open the folder of the path in the root, and give its descriptor.

    The nearest folder that exists is resolved, and it must be in the resolved root.
    Then each part of the folder opens relative to the part before it. A part that is a
    link at that time gives RefusedFile."""
    confined(root, path)
    # The root is not a path from the repository: a missing root is made, as before.
    root.mkdir(parents=True, exist_ok=True)
    base = root.resolve()
    existing = path.parent
    while not os.path.lexists(existing) and existing != root:
        existing = existing.parent
    resolved = existing.resolve()
    if not resolved.is_relative_to(base):
        raise RefusedFile(path, _outside(root))
    parts = resolved.relative_to(base).parts + path.parent.relative_to(existing).parts
    try:
        return repo_files.open_folder(base, parts, make=True)
    except repo_files.RepoPathError as exc:
        raise RefusedFile(path, str(exc)) from exc


@contextmanager
def _parent(root: Path, path: Path) -> Iterator[int | None]:
    """Hold the open folder of the path, or None where `repo_files.WALK` is false."""
    if not repo_files.WALK:
        yield None
        return
    descriptor = _open_parent(root, path)
    try:
        yield descriptor
    finally:
        os.close(descriptor)


def _name(path: Path, parent: int | None) -> str:
    """Give the name of the path relative to its open folder, or the full path."""
    return path.name if parent is not None else str(path)


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
    with _parent(root, path) as parent:
        handle, name = _temporary(path, parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as out:
                out.write(text)
            _keep_mode(_name(path, parent), name, parent)
            os.replace(name, _name(path, parent), src_dir_fd=parent, dst_dir_fd=parent)
        except BaseException:
            with suppress(FileNotFoundError):
                os.unlink(name, dir_fd=parent)
            raise


def _temporary(path: Path, parent: int | None) -> tuple[int, str]:
    """Make a new temporary file of this writer next to the path. Give its descriptor and
    its name, relative to the open folder `parent` if there is one.

    The operating system applies the umask to the mode 0666, as for a usual write. The
    file must not be present before. Thus a link or a file of a different writer is not used.
    """
    while True:
        name = _name(path.with_name(f"{path.name}.{secrets.token_hex(8)}.tmp"), parent)
        try:
            return os.open(name, _TEMPORARY_FLAGS, 0o666, dir_fd=parent), name
        except FileExistsError:
            continue


def _keep_mode(path: str, name: str, parent: int | None) -> None:
    """Give the temporary file the mode of the regular file at the path, if there is one."""
    try:
        existing = os.lstat(path, dir_fd=parent)
    except FileNotFoundError:
        return
    if stat.S_ISREG(existing.st_mode):
        os.chmod(name, stat.S_IMODE(existing.st_mode), dir_fd=parent)


@contextmanager
def locked(root: Path, path: Path) -> Iterator[None]:
    """Hold an exclusive lock on `<path>.lock` while the `with` statement operates.

    The folder of the lock file must be in the root.
    """
    lock = path.with_name(f"{path.name}.lock")
    folder(root, lock)
    with _parent(root, lock) as parent:
        descriptor = _open_lock(lock, parent)
    try:
        _lock(descriptor)
        try:
            yield
        finally:
            _unlock(descriptor)
    finally:
        os.close(descriptor)


def _open_lock(lock: Path, parent: int | None) -> int:
    """Open or make the lock file. Refuse a link, a FIFO, and a device with RefusedFile.

    The open does not wait on a FIFO. A platform without O_NOFOLLOW gets the link test
    before the open only.
    """
    name = _name(lock, parent)
    with suppress(FileNotFoundError):
        if stat.S_ISLNK(os.lstat(name, dir_fd=parent).st_mode):
            raise RefusedFile(lock, LINK)
    try:
        descriptor = _create(name, parent)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise RefusedFile(lock, LINK) from exc
        raise
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise RefusedFile(lock, "the path is not a regular file")
    return descriptor


def _create(name: str, parent: int | None) -> int:
    """Open or make the lock file. Try the same open again after FileNotFoundError.

    On macOS, an open with O_CREAT relative to a folder descriptor can give ENOENT when
    other processes make the same new name at the same time. In a probe of 1200 opens by
    8 processes at the same time, 260 opens gave ENOENT, and each second try opened the
    file. A folder that was removed gives FileNotFoundError at each try.
    """
    for _attempt in range(4):
        with suppress(FileNotFoundError):
            return os.open(name, _LOCK_FLAGS, 0o666, dir_fd=parent)
    return os.open(name, _LOCK_FLAGS, 0o666, dir_fd=parent)


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
