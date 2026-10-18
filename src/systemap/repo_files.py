"""Read a repository file only if the file is a regular file in the repository.

The facts file, the configuration, the model, and a submitted result give file paths.
A cloned repository can contain an absolute path, a path with a `..` part, or a link
to a file that is not in the repository. Then a command can read a file that is not
part of the repository. Some commands send this text to an external service.

These functions refuse such a path with `RepoPathError`. `RepoPathError` is an `OSError`.
Thus each caller gives its usual result for a file that it cannot read.
A missing file gives `FileNotFoundError`, as before.

A different process can change a folder of the path to a link after the check. Thus the
read does not open the full path. Where the operating system can open a path relative to
an open folder (`WALK`), the read opens the resolved path one part at a time. Each part
opens relative to the folder before it, and a part that is a link gives `RepoPathError`.
Windows cannot do this step. There, the read opens the checked path, and a change of a
folder between the check and the open is not found.
"""

from __future__ import annotations

import errno
import os
import re
import stat
from collections.abc import Sequence
from pathlib import Path, PurePath, PureWindowsPath

_PARTS = re.compile(r"[\\/]")
# True when `os.open` can open a path part relative to an open folder, without a link.
WALK = os.open in os.supports_dir_fd and hasattr(os, "O_DIRECTORY") and hasattr(os, "O_NOFOLLOW")
_FOLDER_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_DIRECTORY", 0)
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_CLOEXEC", 0)
)
_FILE_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_NONBLOCK", 0)
    | getattr(os, "O_CLOEXEC", 0)
    | getattr(os, "O_BINARY", 0)
)
# The errors of an open with O_NOFOLLOW at a link: ELOOP (Linux), ENOTDIR for a folder
# open (macOS), and EMLINK (FreeBSD).
_LINK_ERRORS = frozenset({errno.ELOOP, errno.ENOTDIR, errno.EMLINK})
CHANGED = "a part of the path is a link"


class RepoPathError(OSError):
    """The path is not a regular file in the repository."""


def _lexical(rel: str) -> None:
    """Refuse an empty path, an absolute path, a drive or UNC path, and a `..` part."""
    if not rel:
        raise RepoPathError("the path is empty")
    if "\0" in rel:
        raise RepoPathError("the path contains a NUL character")
    windows = PureWindowsPath(rel)
    if rel.startswith(("/", "\\")) or windows.drive or windows.root:
        raise RepoPathError("the path is not relative to the repository")
    if ".." in _PARTS.split(rel):
        raise RepoPathError("the path contains a .. part")


def plain(rel: object) -> bool:
    """Tell if a value is a relative path below the root. Only the text of the path counts.

    The function does not examine the disk. Thus a link can go to a file that is not in
    the root.
    """
    try:
        _lexical(rel if isinstance(rel, str) else "")
    except RepoPathError:
        return False
    return True


def checked(root: Path, rel: str | PurePath) -> Path:
    """Give the resolved path of a regular file in the root, or give an OSError.

    The function resolves links. A missing file gives `FileNotFoundError`. Each other
    refusal gives `RepoPathError`.
    """
    text = os.fspath(rel)
    _lexical(text)
    base = root.resolve()
    try:
        target = (base / text).resolve(strict=True)
    except RuntimeError as exc:
        # Python 3.11 gives RuntimeError for a link loop.
        raise RepoPathError("the path is a link loop") from exc
    except OSError as exc:
        # Python 3.13 gives OSError with ELOOP for a link loop.
        if exc.errno == errno.ELOOP:
            raise RepoPathError("the path is a link loop") from exc
        raise
    if not target.is_relative_to(base):
        raise RepoPathError("the file is not in the repository")
    if not stat.S_ISREG(target.stat().st_mode):
        raise RepoPathError("the path is not a regular file")
    return target


def relative(root: Path, path: Path) -> str:
    """Give the path of a file below the root, relative to the root.

    The extractors use this function for the files that they find below the root.
    A path that is not below the root gives `RepoPathError`.
    """
    for base in (root, root.resolve()):
        if path.is_relative_to(base):
            return path.relative_to(base).as_posix()
    raise RepoPathError("the file is not in the repository")


def open_folder(base: Path, parts: Sequence[str], make: bool = False) -> int:
    """Open the folder `base/parts` one part at a time, and give its descriptor.

    Each part opens relative to the folder before it. A part that is a link gives
    `RepoPathError`. A part that is a file gives the error of the operating system.
    With `make`, the function makes a missing part. Use this function only if `WALK` is
    true.
    """
    descriptor = os.open(base, _FOLDER_FLAGS)
    try:
        for part in parts:
            child = _child(descriptor, part, make)
            os.close(descriptor)
            descriptor = child
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def _child(folder: int, part: str, make: bool) -> int:
    try:
        return os.open(part, _FOLDER_FLAGS, dir_fd=folder)
    except FileNotFoundError:
        if not make:
            raise
    except OSError as exc:
        if exc.errno in _LINK_ERRORS and _is_link(part, folder):
            raise RepoPathError(CHANGED) from exc
        raise
    try:
        os.mkdir(part, 0o777, dir_fd=folder)
    except FileExistsError:
        pass
    return _child(folder, part, False)


def _is_link(part: str, folder: int) -> bool:
    """Tell if the part in the open folder is a link. A part that is a file is not a link:
    the caller then gives the error of the operating system, as for a usual open."""
    try:
        return stat.S_ISLNK(os.lstat(part, dir_fd=folder).st_mode)
    except OSError:
        return False


def _open(root: Path, rel: str | PurePath) -> int:
    """Open the checked file. No part of the resolved path can be a link at the open.

    The function examines the open file again.
    """
    target = checked(root, rel)
    if WALK:
        descriptor = _open_below(root.resolve(), target)
    else:
        descriptor = os.open(target, _FILE_FLAGS)
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise RepoPathError("the path is not a regular file")
    return descriptor


def _open_below(base: Path, target: Path) -> int:
    """Open the file `target` in `base` through the descriptor of each folder."""
    parts = target.relative_to(base).parts
    folder = open_folder(base, parts[:-1])
    try:
        return os.open(parts[-1], _FILE_FLAGS, dir_fd=folder)
    except OSError as exc:
        if exc.errno in _LINK_ERRORS:
            raise RepoPathError(CHANGED) from exc
        raise
    finally:
        os.close(folder)


def read_bytes(root: Path, rel: str | PurePath, size: int = -1) -> bytes:
    """Give the bytes of a regular file in the root, or give an OSError.

    With a size that is not negative, give at most that number of bytes."""
    with os.fdopen(_open(root, rel), "rb") as handle:
        return handle.read(size)


def read_text(
    root: Path, rel: str | PurePath, encoding: str = "utf-8", errors: str | None = None
) -> str:
    """Give the text of a regular file in the root, or give an OSError.

    The text has universal newlines, as `Path.read_text` gives.
    """
    with os.fdopen(_open(root, rel), "r", encoding=encoding, errors=errors) as handle:
        return handle.read()


def present(path: Path) -> bool:
    """Tell if the path names an entry that is not a folder: a file, a link, or a FIFO.

    A reader then reads the entry with `read_text`, which refuses a link out of the root
    and a file that is not regular, with the cause. Thus such an entry is not silently
    treated as a missing file.
    """
    return os.path.lexists(path) and not path.is_dir()


def inside(root: Path, path: Path) -> bool:
    """Tell if the resolved path is in the resolved root. A link loop is not in the root."""
    try:
        return path.resolve().is_relative_to(root.resolve())
    except RuntimeError:
        # Python 3.11 gives RuntimeError for a link loop.
        return False


LINK_OUT = "link out of the repository"
NOT_REGULAR = "not a regular file in the repository"
_REFUSALS = {
    "the file is not in the repository": LINK_OUT,
    "the path is not a regular file": NOT_REGULAR,
}


def refusal(exc: BaseException) -> str:
    """Give the cause of a refused source file for a record: LINK_OUT, NOT_REGULAR, or the
    text of a different refusal. A missing file gives "missing"."""
    if isinstance(exc, FileNotFoundError):
        return "missing"
    if isinstance(exc, RepoPathError):
        return _REFUSALS.get(str(exc), str(exc))
    return type(exc).__name__


def reason(exc: BaseException) -> str:
    """Give the read problem of an exception: the refusal text, or the exception name."""
    return str(exc) if isinstance(exc, RepoPathError) else type(exc).__name__
