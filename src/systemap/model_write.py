"""Stage model replacements and restore completed writes after an I/O failure."""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path


def _stage(path: Path, data: bytes) -> Path:
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
        temporary.chmod(stat.S_IMODE(path.stat().st_mode))
    except OSError:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def _restore(completed: list[Path], backups: dict[Path, Path]) -> list[str]:
    failures = []
    for path in reversed(completed):
        try:
            os.replace(backups[path], path)
            backups.pop(path)
        except OSError as exc:
            failures.append(f"{path}: {exc}; original retained at {backups[path]}")
    return failures


def _replace(staged: dict[Path, Path], backups: dict[Path, Path]) -> None:
    completed: list[Path] = []
    try:
        for path, temporary in staged.items():
            os.replace(temporary, path)
            completed.append(path)
    except OSError as exc:
        failures = _restore(completed, backups)
        for path in set(backups) - set(completed):
            backups.pop(path).unlink(missing_ok=True)
        if failures:
            raise OSError(f"{exc}; rollback incomplete: {'; '.join(failures)}") from exc
        raise OSError(f"{exc}; original models restored") from exc


def write_models(sources: dict[Path, str]) -> None:
    """Prepare every replacement and backup before changing any model.

    A replace failure restores prior files. If restoration also fails, the
    error names each affected model and the retained original backup. This
    handles reported I/O errors, not process termination or concurrent edits.
    """
    for path, source in sources.items():
        compile(source, str(path), "exec")
    staged: dict[Path, Path] = {}
    backups: dict[Path, Path] = {}
    try:
        for path, source in sources.items():
            backups[path] = _stage(path, path.read_bytes())
            staged[path] = _stage(path, source.encode("utf-8"))
    except OSError:
        for temporary in (*staged.values(), *backups.values()):
            temporary.unlink(missing_ok=True)
        raise
    try:
        _replace(staged, backups)
    except OSError:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
        # Backups left by an incomplete rollback are recovery files.
        raise
    for temporary in backups.values():
        temporary.unlink(missing_ok=True)
