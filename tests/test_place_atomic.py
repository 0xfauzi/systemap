"""`systemap place` replaces the model file. It does not write into the open file.

Finding rest-7: `place_source.write` wrote the model file in place with write_text, and
it restored the previous bytes with write_bytes. A reader of the file at the same time,
or a stop of the process during the write, could get a part of a file. The writer now
writes a temporary file and replaces the model file with os.replace
(`model_write.write_models` and `model_write.replace_bytes`).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from test_place_route_repairs import _unplaced

from systemap import model_load, model_write, place_source
from systemap.cli import main

# On Windows, os.replace cannot replace a file that is open.
POSIX = pytest.mark.skipif(sys.platform == "win32", reason="an open file blocks os.replace")


def count_replaces(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    replaced: list[str] = []
    real = os.replace

    def counted(source: str | Path, target: str | Path) -> None:
        replaced.append(Path(target).name)
        real(source, target)

    monkeypatch.setattr(model_write.os, "replace", counted)
    return replaced


@POSIX
def test_place_replaces_the_model_file_and_a_reader_keeps_the_previous_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _unplaced(tmp_path)
    before = path.read_bytes()
    replaced = count_replaces(monkeypatch)
    with path.open("rb") as reader:
        assert main(["--root", str(tmp_path), "place"]) == 0, capsys.readouterr()
        # A write into the open file changes the bytes that the reader gets. A replacement
        # does not change them.
        assert reader.read() == before
    assert path.read_bytes() != before
    assert replaced == ["model.py"]
    assert [p.name for p in path.parent.iterdir() if p.name.startswith(".model.py-")] == []


@POSIX
def test_place_restores_the_previous_bytes_with_a_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _unplaced(tmp_path)
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    # The file is a few bytes below the limit of the model reader. Thus the reader refuses
    # the file after the command adds the x and y values, and the command restores it.
    pad = model_load.MAX_BYTES - len(path.read_bytes()) - 4
    path.write_bytes(path.read_bytes() + b"#" * (pad - 1) + b"\n")
    before = path.read_bytes()
    replaced = count_replaces(monkeypatch)
    assert main(["--root", str(tmp_path), "place"]) == 1
    assert "restored" in capsys.readouterr().err
    assert path.read_bytes() == before
    # One replacement writes the positions. One replacement restores the previous bytes.
    assert replaced == ["model.py", "model.py"]
    assert [p.name for p in path.parent.iterdir() if p.name.startswith(".model.py-")] == []


def test_place_does_not_change_the_file_if_the_new_text_does_not_compile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _unplaced(tmp_path)
    before = path.read_bytes()
    monkeypatch.setattr(place_source, "written", lambda source, placement: "MODEL = (\n")
    assert main(["--root", str(tmp_path), "place"]) == 1
    err = capsys.readouterr().err
    assert "The command could not compile the new text of map/model.py: " in err
    assert "The command did not change the file." in err
    assert "after the change" not in err
    assert path.read_bytes() == before
    assert [p.name for p in path.parent.iterdir() if p.name.startswith(".model.py-")] == []
