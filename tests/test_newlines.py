"""Each file that systemap writes has LF line ends, also on Windows.

On Windows, a write in text mode without `newline="\\n"` changes each LF to CRLF. Also,
a model file can have CRLF line ends before a command edits it: a Git checkout on
Windows can make them. An edit command writes the edited model with LF line ends.
"""

from __future__ import annotations

import ast
from pathlib import Path

from conftest import TINY_PACKAGE, TWO_CARD_MODEL, init_two_cards, write_tree

from systemap.cli import main

SOURCE = Path(__file__).resolve().parent.parent / "src" / "systemap"
TEXT_WRITES = {"write_text", "open", "fdopen"}


def _crlf_project(root: Path) -> Path:
    write_tree(root, TINY_PACKAGE)
    init_two_cards(root, "--no-ci")
    model = root / "map" / "model.py"
    model.write_bytes(TWO_CARD_MODEL.replace("\n", "\r\n").encode("utf-8"))
    assert main(["--root", str(root), "refresh"]) == 0
    return model


def test_place_writes_a_crlf_model_with_lf(tmp_path: Path) -> None:
    """win-3: the acceptance value is 0 carriage returns in the model after place --all.

    Before the repair, place kept each CRLF of the model file."""
    model = _crlf_project(tmp_path)
    assert main(["--root", str(tmp_path), "place", "--all"]) == 0
    assert model.read_bytes().count(b"\r") == 0


def test_review_writes_a_crlf_model_with_lf(tmp_path: Path) -> None:
    """win-3: the acceptance value is 0 carriage returns in the model after review.

    Before the repair, review kept each CRLF of the model file."""
    model = _crlf_project(tmp_path)
    assert main(["--root", str(tmp_path), "review", "Reader"]) == 0
    assert b"source_review=" in model.read_bytes()
    assert model.read_bytes().count(b"\r") == 0


def _mode(call: ast.Call) -> str:
    """Give the mode argument of an open call, or "r" if the call has no literal mode."""
    for keyword in call.keywords:
        if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
            return str(keyword.value.value)
    function = call.func
    at = 0 if isinstance(function, ast.Attribute) and function.attr == "open" else 1
    if len(call.args) > at and isinstance(call.args[at], ast.Constant):
        return str(call.args[at].value)
    return "r"


def _text_writes_without_newline(path: Path) -> list[str]:
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        name = function.attr if isinstance(function, ast.Attribute) else ""
        name = function.id if isinstance(function, ast.Name) else name
        if name not in TEXT_WRITES or any(k.arg == "newline" for k in node.keywords):
            continue
        mode = "w" if name == "write_text" else _mode(node)
        if "b" not in mode and any(flag in mode for flag in "wax+"):
            out.append(f"{path.relative_to(SOURCE).as_posix()}:{node.lineno}")
    return out


def test_each_text_write_in_the_source_sets_the_newline() -> None:
    """win-3: the acceptance value is 0 text writes without a `newline` argument.

    Before the repair, 3 writes had no `newline` argument: decisions_store.py,
    file_write.py, and plan.py."""
    found = [
        line for path in sorted(SOURCE.rglob("*.py")) for line in _text_writes_without_newline(path)
    ]
    assert found == []
