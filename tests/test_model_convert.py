"""systemap convert writes a model that needs code again with literal values only.

It runs the old model file only with SYSTEMAP_TRUST_MODEL_CODE=1, and it writes the file
only if the reader that runs no code gives the same model from the new text.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import TWO_CARD_MODEL, init_two_cards, write_tree

from systemap import config, model_load
from systemap.cli import main

CODE_TAIL = """
from dataclasses import replace

MEANING = replace(MEANING, plain={c.id: c.id.lower() + " part" for c in COMPONENTS})
"""


def _project(tmp_path: Path, model: str) -> Path:
    write_tree(tmp_path, {"pkg/__init__.py": ""})
    init_two_cards(tmp_path, "--no-ci")
    (tmp_path / "map/model.py").write_text(model, encoding="utf-8")
    return tmp_path / "map/model.py"


def test_without_permission_the_command_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(model_load.TRUST, raising=False)
    path = _project(tmp_path, TWO_CARD_MODEL + CODE_TAIL)
    before = path.read_text(encoding="utf-8")
    assert main(["--root", str(tmp_path), "convert"]) == 2
    assert path.read_text(encoding="utf-8") == before
    captured = capsys.readouterr()
    out = " ".join((captured.out + captured.err).split())  # the CLI wraps long lines
    assert f"set {model_load.TRUST}=1. Then run systemap convert again." in out


def test_with_permission_the_new_file_gives_the_same_model_without_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _project(tmp_path, TWO_CARD_MODEL + CODE_TAIL)
    monkeypatch.setenv(model_load.TRUST, "1")
    old = config.load_model(path, "map/model.py")
    assert old[1].plain["Reader"] == "reader part"
    assert main(["--root", str(tmp_path), "convert"]) == 0
    monkeypatch.delenv(model_load.TRUST)
    new = config.load_model(path, "map/model.py")  # the reader that runs no code
    assert repr(new) == repr(old)
    text = path.read_text(encoding="utf-8")
    assert "replace(" not in text and " for " not in text
    assert text.startswith('"""The system map of pkg.\n\nsystemap convert wrote this file')
    assert main(["--root", str(tmp_path), "check"]) in (0, 1)  # the page may be stale


def test_a_literal_model_is_not_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(model_load.TRUST, raising=False)
    path = _project(tmp_path, TWO_CARD_MODEL)
    assert main(["--root", str(tmp_path), "convert"]) == 0
    assert path.read_text(encoding="utf-8") == TWO_CARD_MODEL
    assert "There is nothing to write." in " ".join(capsys.readouterr().out.split())


def test_the_command_names_a_file_beside_the_model_that_it_no_longer_imports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    model = TWO_CARD_MODEL.replace(
        "from __future__ import annotations\n",
        "from __future__ import annotations\n\nimport words\n",
    ) + CODE_TAIL.replace('" part"', "words.TAIL")
    path = _project(tmp_path, model)
    (path.parent / "words.py").write_text('TAIL = " part"\n', encoding="utf-8")
    monkeypatch.setenv(model_load.TRUST, "1")
    assert main(["--root", str(tmp_path), "convert"]) == 0
    out = " ".join(capsys.readouterr().out.split())
    assert "map/model.py does not import words.py now." in out
    assert "import words" not in path.read_text(encoding="utf-8")
