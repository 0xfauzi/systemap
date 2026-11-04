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
keeps its mode. On Windows, a different program can open the new file for a short
time. Then `os.replace` gives PermissionError, and `write_atomic` waits and tries
`os.replace` again a small number of times.

A different process can change a folder of the path to a link after the check. Where
`repo_files.WALK` is true, `write_atomic` and `locked` open the resolved folder one part
at a time, without a link, and they make, replace, and open the file relative to that
open folder. A part that is a link at that time gives `RefusedFile`. On Windows, the two
functions use the checked path, and a change of a folder after the check is not found.

`locked` holds an exclusive lock on the file `<path>.lock` while its `with` statement
operates. A different process that tries to get the same lock waits. The operating
system releases the lock when the process stops, also after a failure. A lock file that
is a link, a FIFO, or a device gives `RefusedFile`.

`exclusive` permits only one command at a time to write the shared files of the
repository. It makes `.systemap/write.lock` with O_EXCL. The file holds the process ID,
the command, and the time. A different process that tries to get the lock does not wait.
It gets `HeldLock`, with the path and the text of the lock file. In one process, an inner
`exclusive` for the same lock continues and does not stop the command. `exclusive_file`
does the same for the lock `<path>.lock` of one file, for example a model file. The last
`with` statement removes the lock when it stops, also after a failure. A stopped process
cannot remove its lock. Thus a later command gets `HeldLock`, and only a person removes
that lock file.

`ignore_caches` makes the file `.systemap/.gitignore` with the line `*` if the folder has
no entry with that name. Then Git does not add the caches in that folder after
`git add -A`. The function does not change an existing entry.
"""

from __future__ import annotations

import errno
import os
import secrets
import stat
import sys
import threading
import time
from collections.abc import Iterable, Iterator
from contextlib import ExitStack, contextmanager, suppress
from datetime import UTC, datetime
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
CACHE_FOLDER = ".systemap"
GIT_IGNORE = ".gitignore"
# The pattern applies to each file in the folder, also to the .gitignore file.
IGNORE_ALL = "*\n"
# On Windows, a different program, for example an antivirus scan, can open the new
# file for a short time. Then `os.replace` gives PermissionError. If RETRY_REPLACE is
# true, `write_atomic` waits for each time in REPLACE_WAITS and tries `os.replace` again.
# These values are a limit. They are not a measurement. A measurement on Windows CI is
# necessary to know if the limit is sufficient.
RETRY_REPLACE = os.name == "nt"
WRITE_LOCK = f"{CACHE_FOLDER}/write.lock"
# The command that operates in this process. `cli.main` sets it. A lock file records it.
command = "systemap"
REPLACE_WAITS = (0.05, 0.1, 0.2, 0.4)


class RefusedFile(Exception):
    """The command does not read, write, or lock the file, because it is not in its root."""

    def __init__(self, path: Path, cause: str) -> None:
        super().__init__(
            f"{path}: the command does not use this file, because {cause}. "
            "Remove the file or the link. Then run the command again."
        )


class HeldLock(Exception):
    """A different command holds the lock. This command does not wait for it."""

    def __init__(self, lock: Path, holder: str) -> None:
        super().__init__(
            f"{lock}: a different command holds this lock ({holder}). This command stopped "
            "before it changed a file that the lock controls. If no systemap command "
            f"operates now, a stopped command left the lock. Then remove {lock} and run the "
            "command again."
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
            _replace(name, _name(path, parent), parent)
        except BaseException:
            with suppress(FileNotFoundError):
                os.unlink(name, dir_fd=parent)
            raise


def _replace(name: str, target: str, parent: int | None) -> None:
    """Replace the target with the temporary file.

    If RETRY_REPLACE is true, after a PermissionError, wait for the next time in
    REPLACE_WAITS and try again. After the last time in REPLACE_WAITS, the next
    PermissionError goes to the caller. A different OSError goes to the caller at once.
    """
    waits = REPLACE_WAITS if RETRY_REPLACE else ()
    for wait in waits:
        try:
            os.replace(name, target, src_dir_fd=parent, dst_dir_fd=parent)
        except PermissionError:
            time.sleep(wait)
        else:
            return
    os.replace(name, target, src_dir_fd=parent, dst_dir_fd=parent)


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


def ignore_caches(root: Path, path: Path | None = None) -> bool:
    """Make `.systemap/.gitignore` in the root with the line `*`. Give True for a new file.

    If `path` is not in `.systemap/`, the function does nothing. An entry with the name
    `.gitignore`, also a link or a folder, stays as it is. The open with O_EXCL does not
    replace a file that a different process makes at the same time."""
    cache_folder = root / CACHE_FOLDER
    if path is not None and not path.is_relative_to(cache_folder):
        return False
    target = cache_folder / GIT_IGNORE
    folder(root, target)
    with _parent(root, target) as parent:
        name = _name(target, parent)
        try:
            handle = os.open(name, _TEMPORARY_FLAGS, 0o666, dir_fd=parent)
        except FileExistsError:
            return False
        except PermissionError:
            # Windows gives this error, not FileExistsError, for a folder at the name.
            if _exists(name, parent):
                return False
            raise
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as out:
            out.write(IGNORE_ALL)
    return True


def _exists(name: str, parent: int | None) -> bool:
    """Find if an entry, also a link, has the name in the parent folder."""
    try:
        os.lstat(name, dir_fd=parent)
    except FileNotFoundError:
        return False
    return True


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


# Each lock that this process holds, by the absolute path of the lock file: the depth of
# the `with` statements and the text of the lock file.
_HELD: dict[str, tuple[int, str]] = {}
_GUARD = threading.Lock()


@contextmanager
def exclusive(root: Path, holder: str = "") -> Iterator[None]:
    """Hold `.systemap/write.lock` in the root while the `with` statement operates.

    A different process that holds the lock gives HeldLock. In this process, an inner
    `exclusive` continues. The folder of the lock file must be in the root."""
    lock = root / WRITE_LOCK
    folder(root, lock)
    ignore_caches(root, lock)
    with _parent(root, lock) as parent, _held(lock, parent, holder):
        yield


@contextmanager
def exclusive_file(path: Path, holder: str = "") -> Iterator[None]:
    """Hold the lock `<path>.lock` of one file while the `with` statement operates."""
    with _held(path.with_name(f"{path.name}.lock"), None, holder):
        yield


@contextmanager
def exclusive_files(paths: Iterable[Path], holder: str = "") -> Iterator[None]:
    """Hold the lock of each file. The locks are taken in the sequence of the paths."""
    with ExitStack() as stack:
        for path in sorted(set(paths)):
            stack.enter_context(exclusive_file(path, holder))
        yield


@contextmanager
def _held(lock: Path, parent: int | None, holder: str) -> Iterator[None]:
    """Make the lock file, or continue if this process holds it. Remove it at the end.

    The guard covers the make and the removal. Thus a different thread of this process
    continues only after the lock file exists, and the last `with` statement to stop
    removes the file."""
    key = os.path.abspath(lock)
    with _GUARD:
        depth, text = _HELD.get(key) or (0, "")
        if not depth:
            text = _take(lock, parent, holder)
        _HELD[key] = (depth + 1, text)
    try:
        yield
    finally:
        with _GUARD:
            depth, text = _HELD.pop(key)
            if depth > 1:
                _HELD[key] = (depth - 1, text)
            else:
                _give_back(lock, parent, text)


def _take(lock: Path, parent: int | None, holder: str) -> str:
    """Make the lock file with O_EXCL. Give its text. A lock that exists gives HeldLock."""
    name = _name(lock, parent)
    started = datetime.now(UTC).isoformat(timespec="seconds")
    text = f"process {os.getpid()}, command {holder or command}, started {started}"
    try:
        handle = os.open(name, _TEMPORARY_FLAGS, 0o666, dir_fd=parent)
    except FileExistsError:
        raise HeldLock(lock, _holder(name, parent)) from None
    with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as out:
        out.write(text + "\n")
    return text


def _holder(name: str, parent: int | None) -> str:
    """Give the text of a lock file that a different command made, or a short notice."""
    try:
        handle = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent)
        with os.fdopen(handle, encoding="utf-8", errors="replace") as source:
            text = source.read(400).strip()
    except OSError:
        text = ""
    return text or "the holder is not known"


def _give_back(lock: Path, parent: int | None, text: str) -> None:
    """Remove the lock file if it still holds the text of this process."""
    name = _name(lock, parent)
    if _holder(name, parent) == text:
        with suppress(FileNotFoundError):
            os.unlink(name, dir_fd=parent)
