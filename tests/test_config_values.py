"""Configuration and model values that the reader refuses with one line and a fix.

A value of the wrong type or form gives exit code 2 and a message with the key name.
No value gives a traceback.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import STARTER_MODULES, init_two_cards, write_tree

from systemap import config
from systemap.cli import main

BOM = b"\xef\xbb\xbf"


def run(*argv: str) -> int:
    return main(list(argv))


@pytest.fixture
def two_cards(tmp_path: Path) -> Path:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    return tmp_path


def add_config(root: Path, text: str) -> None:
    """Put configuration text at the end of the file."""
    path = root / "systemap.toml"
    path.write_text(path.read_text(encoding="utf-8") + "\n" + text, encoding="utf-8")


def test_a_model_file_with_a_byte_order_mark_loads(two_cards: Path) -> None:
    path = two_cards / "map/model.py"
    path.write_bytes(BOM + path.read_bytes())
    model, _meaning = config.load_model(path)
    assert [c.id for c in model.components] == ["Reader", "Writer"]


def test_place_writes_a_model_file_with_a_byte_order_mark(two_cards: Path) -> None:
    path = two_cards / "map/model.py"
    path.write_bytes(BOM + path.read_bytes())
    assert run("--root", str(two_cards), "extract") == 0
    assert run("--root", str(two_cards), "place", "--all") == 0
    model, _meaning = config.load_model(path)
    assert all(c.x is not None and c.y is not None for c in model.components)


def test_a_configuration_with_a_byte_order_mark_loads(two_cards: Path) -> None:
    path = two_cards / "systemap.toml"
    path.write_bytes(BOM + path.read_bytes())
    assert config.load(two_cards).package_roots == (("pkg", "pkg"),)


def test_only_a_systemap_name_gives_the_systemap_import_advice(
    two_cards: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = two_cards / "map/model.py"
    model = path.read_text(encoding="utf-8")
    path.write_text(model + "\nimport my_shared_layout_helpers\n", encoding="utf-8")
    assert run("--root", str(two_cards), "check") == 2
    err = capsys.readouterr().err
    assert "an import of my_shared_layout_helpers, which is not a file in the directory" in err
    assert "import from systemap" not in err
    path.write_text(model + "\nSIZE = CANVAS_SIZE\n", encoding="utf-8")
    assert run("--root", str(two_cards), "check") == 2
    err = capsys.readouterr().err
    assert "the name CANVAS_SIZE, which the file does not define before this line" in err
    assert "import from systemap" not in err
    path.write_text(model + "\nfrom systemap import Layers\n", encoding="utf-8")
    assert run("--root", str(two_cards), "check") == 2
    err = capsys.readouterr().err
    assert "an import of Layers from systemap" in err
    assert "Add Layers" not in err
    assert "Use a name that systemap exports for a model: " in err and "Layer, " in err


def test_the_permitted_model_code_keeps_the_systemap_import_advice(
    two_cards: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """With SYSTEMAP_TRUST_MODEL_CODE=1, the file runs as Python code, with the 2.0 advice."""
    monkeypatch.setenv("SYSTEMAP_TRUST_MODEL_CODE", "1")
    path = two_cards / "map/model.py"
    model = path.read_text(encoding="utf-8")
    path.write_text(model + "\nimport my_shared_layout_helpers\n", encoding="utf-8")
    assert run("--root", str(two_cards), "check") == 2
    err = capsys.readouterr().err
    assert "No module named 'my_shared_layout_helpers'" in err
    assert "import from systemap" not in err
    path.write_text(model + "\nSIZE = CANVAS_SIZE\n", encoding="utf-8")
    assert run("--root", str(two_cards), "check") == 2
    err = capsys.readouterr().err
    assert "name 'CANVAS_SIZE' is not defined" in err
    assert "import from systemap" not in err
    path.write_text(model + "\nfrom systemap import Layers\n", encoding="utf-8")
    assert run("--root", str(two_cards), "check") == 2
    err = capsys.readouterr().err
    assert "cannot import name 'Layers' from 'systemap'" in err
    assert "Add the missing name" not in err
    assert "Use a name that systemap exports: " in err and "Layer, " in err


def test_figures_of_the_wrong_type_are_a_configuration_error(
    two_cards: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (two_cards / "systemap.toml").write_text(
        'figures = 5\n[package_roots]\n"pkg" = "pkg"\n', encoding="utf-8"
    )
    assert run("--root", str(two_cards), "check", "--brief") == 2
    err = capsys.readouterr().err
    assert "systemap.toml: figures must be a list of tables. Use [[figures]]." in err
    assert "Traceback" not in err


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (
            '[judgement]\nanswered = [{ crossing = ["Reader", 1], reason = "r" }]',
            "crossing must contain two or more different component IDs",
        ),
        ('[theme]\nlayers = "x"', "The theme value layers must be a table"),
        ("[theme.layers]\ndata = 5", "The theme value layers.data must be a color"),
        ('[theme]\nbg = "red"', "The theme value bg must be a color"),
        ('[theme]\nchange = "#abc"', "The theme value change must be a color"),
        ("[theme.light]\nraised = 5", "The theme value raised must be a color"),
        ("[theme]\nlayer_palette = []", "The theme value layer_palette must be a list"),
        ('[theme]\nlayer_palette = ["x"]', "The theme value layer_palette must be a"),
        ("[theme]\nmarks = 5", "The theme value marks must be a table"),
    ],
)
def test_a_value_of_the_wrong_form_is_a_configuration_error(
    two_cards: Path, capsys: pytest.CaptureFixture[str], text: str, message: str
) -> None:
    add_config(two_cards, text)
    assert run("--root", str(two_cards), "check", "--brief") == 2
    err = capsys.readouterr().err
    assert message in err
    assert "Traceback" not in err
    assert err.rstrip().endswith(
        "Correct systemap.toml or the model module. Then run the command again."
    )


def test_a_color_in_the_correct_form_is_accepted(two_cards: Path) -> None:
    add_config(two_cards, '[theme]\nbg = "#101010"\n[theme.layers]\ndata = "#AA3355"')
    assert run("--root", str(two_cards), "refresh") == 0
