"""Acceptance: failed multi-map writes preserve every original or name its backup."""

from pathlib import Path

import pytest

from systemap import model_write


def models(root: Path) -> dict[Path, str]:
    sources = {root / "first.py": "FIRST = 1\n", root / "second.py": "SECOND = 1\n"}
    for path in sources:
        path.write_text("ORIGINAL = 0\r\n", newline="")
        path.chmod(0o640)
    return sources


def test_replace_failure_restores_all_original_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sources = models(tmp_path)
    original_replace = model_write.os.replace
    calls = 0

    def fail_second(source: Path, target: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("second replace failed")
        original_replace(source, target)

    monkeypatch.setattr(model_write.os, "replace", fail_second)
    with pytest.raises(OSError, match="original models restored"):
        model_write.write_models(sources)
    assert all(path.read_bytes() == b"ORIGINAL = 0\r\n" for path in sources)
    assert sorted(tmp_path.iterdir()) == sorted(sources)


def test_rollback_failure_retains_original_and_reports_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sources = models(tmp_path)
    original_replace = model_write.os.replace
    calls = 0

    def fail_after_first(source: Path, target: Path) -> None:
        nonlocal calls
        calls += 1
        if calls > 1:
            raise OSError("replace unavailable")
        original_replace(source, target)

    monkeypatch.setattr(model_write.os, "replace", fail_after_first)
    with pytest.raises(OSError, match="rollback incomplete") as error:
        model_write.write_models(sources)
    backups = list(tmp_path.glob(".first.py-*"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == b"ORIGINAL = 0\r\n"
    assert str(backups[0]) in str(error.value)
    assert (tmp_path / "second.py").read_bytes() == b"ORIGINAL = 0\r\n"


def test_stage_failure_and_syntax_failure_write_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sources = models(tmp_path)
    with pytest.raises(SyntaxError):
        model_write.write_models({**sources, tmp_path / "second.py": "INVALID = ("})
    original_stage = model_write._stage
    calls = 0

    def fail_late(path: Path, data: bytes) -> Path:
        nonlocal calls
        calls += 1
        if calls == 4:
            raise OSError("no space")
        return original_stage(path, data)

    monkeypatch.setattr(model_write, "_stage", fail_late)
    with pytest.raises(OSError, match="no space"):
        model_write.write_models(sources)
    assert all(path.read_bytes() == b"ORIGINAL = 0\r\n" for path in sources)
    assert sorted(tmp_path.iterdir()) == sorted(sources)


def test_success_replaces_all_models_and_preserves_modes(tmp_path: Path) -> None:
    sources = models(tmp_path)
    model_write.write_models(sources)
    assert all(path.read_text() == source for path, source in sources.items())
    assert all(path.stat().st_mode & 0o777 == 0o640 for path in sources)
    assert sorted(tmp_path.iterdir()) == sorted(sources)
