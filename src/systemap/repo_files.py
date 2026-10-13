"""Read a repository file only if the file is a regular file in the repository.

The facts file, the configuration, the model, and a submitted result give file paths.
A cloned repository can contain an absolute path, a path with a `..` part, or a link
to a file that is not in the repository. Then a command can read a file that is not
part of the repository. Some commands send this text to an external service.

These functions refuse such a path with `RepoPathError`. `RepoPathError` is an `OSError`.
Thus each caller gives its usual result for a file that it cannot read.
A missing file gives `FileNotFoundError`, as before.
"""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path, PurePath, PureWindowsPath

_PARTS = re.compile(r"[\\/]")


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
    target = (base / text).resolve(strict=True)
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


def _open(root: Path, rel: str | PurePath) -> int:
    """Open the checked file. The last part of the path must not be a link.

    The function examines the open file again.
    """
    target = checked(root, rel)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(target, flags | getattr(os, "O_BINARY", 0))
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise RepoPathError("the path is not a regular file")
    return descriptor


def read_bytes(root: Path, rel: str | PurePath) -> bytes:
    """Give the bytes of a regular file in the root, or give an OSError."""
    with os.fdopen(_open(root, rel), "rb") as handle:
        return handle.read()


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
    """Tell if the resolved path is in the resolved root."""
    return path.resolve().is_relative_to(root.resolve())


def reason(exc: BaseException) -> str:
    """Give the read problem of an exception: the refusal text, or the exception name."""
    return str(exc) if isinstance(exc, RepoPathError) else type(exc).__name__
