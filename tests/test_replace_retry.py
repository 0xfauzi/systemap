"""On Windows, `write_atomic` tries `os.replace` again after a PermissionError.

On Windows CI, `os.replace` in `write_atomic` gave "PermissionError: [WinError 5]" two
times in PR #135. No systemap process had the file open. A different program, for
example an antivirus scan of the new file, can cause this error for a short time.

Acceptance, written before the change:

1. If RETRY_REPLACE is true, one PermissionError and then a success writes the file.
2. If RETRY_REPLACE is true, more PermissionErrors than the limit give PermissionError.
   No temporary file stays.
3. If RETRY_REPLACE is false, the first PermissionError goes to the caller at once.
4. An OSError that is not PermissionError goes to the caller at once.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from systemap import file_write

REAL_REPLACE = os.replace


def fail_replace(
    monkeypatch: pytest.MonkeyPatch,
    failures: int,
    error: OSError | None = None,
) -> list[float]:
    """Make `os.replace` give the error `failures` times. Give the list of waits.

    The default error is PermissionError.
    """
    calls = {"count": 0}
    waits: list[float] = []

    def replace(*args: Any, **kwargs: Any) -> None:
        calls["count"] += 1
        if calls["count"] <= failures:
            raise error or PermissionError(13, "Access is denied")
        REAL_REPLACE(*args, **kwargs)

    monkeypatch.setattr(file_write.os, "replace", replace)
    monkeypatch.setattr(file_write.time, "sleep", waits.append)
    return waits


def leftovers(folder: Path) -> list[str]:
    """Give the names of the temporary files in the folder."""
    return sorted(entry.name for entry in folder.iterdir() if entry.name.endswith(".tmp"))


def test_one_failure_then_success_writes_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(file_write, "RETRY_REPLACE", True)
    waits = fail_replace(monkeypatch, 1)
    target = tmp_path / "cache.json"
    file_write.write_atomic(tmp_path, target, "new")
    assert target.read_text(encoding="utf-8") == "new"
    assert waits == [file_write.REPLACE_WAITS[0]]
    assert leftovers(tmp_path) == []


def test_failures_past_the_limit_raise_and_remove_the_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(file_write, "RETRY_REPLACE", True)
    waits = fail_replace(monkeypatch, len(file_write.REPLACE_WAITS) + 1)
    target = tmp_path / "cache.json"
    target.write_text("old", encoding="utf-8")
    with pytest.raises(PermissionError):
        file_write.write_atomic(tmp_path, target, "new")
    assert waits == list(file_write.REPLACE_WAITS)
    assert target.read_text(encoding="utf-8") == "old"
    assert leftovers(tmp_path) == []


def test_without_retry_the_first_failure_raises_at_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(file_write, "RETRY_REPLACE", False)
    waits = fail_replace(monkeypatch, 1)
    target = tmp_path / "cache.json"
    with pytest.raises(PermissionError):
        file_write.write_atomic(tmp_path, target, "new")
    assert waits == []
    assert not target.exists()
    assert leftovers(tmp_path) == []


def test_a_different_error_raises_at_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(file_write, "RETRY_REPLACE", True)
    waits = fail_replace(monkeypatch, 1, IsADirectoryError(21, "Is a directory"))
    with pytest.raises(IsADirectoryError):
        file_write.write_atomic(tmp_path, tmp_path / "cache.json", "new")
    assert waits == []
    assert leftovers(tmp_path) == []
