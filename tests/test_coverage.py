"""The coverage rule of `systemap check`, driven through the CLI.

Every case starts from what `systemap init` writes: a package `pkg` with a
reader and a writer, a starter model claiming `pkg.reader` and `pkg.writer`,
and one ignore, with a reason, for the package root `pkg`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import write_tree

from systemap.cli import main

STARTER_MODULES = {
    "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
    "pkg/writer.py": "def write(request: str) -> str:\n    return request\n",
}


def run(*argv: str) -> int:
    return main(list(argv))


def scaffold(root: Path) -> None:
    """init and one refresh, so the map is current before a case breaks it."""
    write_tree(root, {"pkg/__init__.py": "", **STARTER_MODULES})
    assert run("--root", str(root), "init") == 0
    assert run("--root", str(root), "refresh") == 0


def test_all_mapped(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    scaffold(tmp_path)
    assert run("--root", str(tmp_path), "check") == 0
    out = capsys.readouterr().out
    assert "coverage: 2/2 modules mapped, 1 ignored" in out
    assert "unmapped" not in out


def test_one_unmapped_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    scaffold(tmp_path)
    write_tree(tmp_path, {"pkg/extra.py": "def extra() -> None:\n    pass\n"})
    assert run("--root", str(tmp_path), "extract") == 0
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "coverage: 2/3 modules mapped, 1 ignored" in out
    assert "unmapped: pkg.extra (no component claims it)" in out
    assert "map layout: clean" in out, "the layout is fine; only coverage failed"
    assert "map every module in map/model.py, or ignore it with a reason" in out
    # refresh runs the same check and refuses too.
    assert run("--root", str(tmp_path), "refresh") == 1
    assert "map: check failed" in capsys.readouterr().out


def test_ignore_with_reason_passes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    scaffold(tmp_path)
    write_tree(tmp_path, {"pkg/extra.py": "def extra() -> None:\n    pass\n"})
    assert run("--root", str(tmp_path), "extract") == 0
    toml = tmp_path / "systemap.toml"
    toml.write_text(
        toml.read_text().replace(
            "ignore = [\n",
            'ignore = [\n    { module = "pkg.extra", reason = "a scratch file with no place on the map" },\n',
        )
    )
    assert run("--root", str(tmp_path), "refresh") == 0
    assert run("--root", str(tmp_path), "check") == 0
    assert "coverage: 2/2 modules mapped, 2 ignored" in capsys.readouterr().out


def test_ignore_without_reason_is_a_config_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    scaffold(tmp_path)
    toml = tmp_path / "systemap.toml"
    toml.write_text(
        toml.read_text().replace("ignore = [\n", 'ignore = [\n    { module = "pkg.extra" },\n')
    )
    assert run("--root", str(tmp_path), "check") == 2
    err = capsys.readouterr().err
    assert "coverage.ignore[1] (pkg.extra) needs a reason" in err

    toml.write_text(
        toml.read_text().replace(
            '{ module = "pkg.extra" }', '{ module = "pkg.extra", reason = "  " }'
        )
    )
    assert run("--root", str(tmp_path), "check") == 2
    assert "needs a reason" in capsys.readouterr().err

    toml.write_text(
        toml.read_text().replace(
            '{ module = "pkg.extra", reason = "  " }',
            '{ module = "pkg.extra", reason = "x", why = "y" }',
        )
    )
    assert run("--root", str(tmp_path), "check") == 2
    assert "coverage.ignore[1] has unknown key: why" in capsys.readouterr().err


def test_double_claim_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    scaffold(tmp_path)
    model = tmp_path / "map/model.py"
    model.write_text(
        model.read_text().replace(
            'implemented_by=("pkg.writer",)', 'implemented_by=("pkg.writer", "pkg.reader")'
        )
    )
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "coverage: 1/2 modules mapped, 1 ignored" in out
    assert "claimed twice: pkg.reader (Reader, Writer)" in out


def test_subtree_claim_covers_the_package(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    scaffold(tmp_path)
    # A subpackage appears; the reader claims it whole with one `.*` entry.
    write_tree(
        tmp_path,
        {"pkg/sub/__init__.py": "", "pkg/sub/deep.py": "def deep() -> None:\n    pass\n"},
    )
    model = tmp_path / "map/model.py"
    text = model.read_text()
    text = text.replace(
        'implemented_by=("pkg.reader",)', 'implemented_by=("pkg.reader", "pkg.sub.*")'
    )
    model.write_text(text)
    assert run("--root", str(tmp_path), "refresh") == 0
    assert run("--root", str(tmp_path), "check") == 0
    assert "coverage: 4/4 modules mapped, 1 ignored" in capsys.readouterr().out


def test_stale_ignore_is_reported(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    scaffold(tmp_path)
    toml = tmp_path / "systemap.toml"
    toml.write_text(
        toml.read_text().replace(
            "ignore = [\n", 'ignore = [\n    { module = "pkg.gone", reason = "it left" },\n'
        )
    )
    assert run("--root", str(tmp_path), "check") == 1
    assert "ignore names a module the facts do not have: pkg.gone" in capsys.readouterr().out


def test_no_facts_fails_closed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    assert run("--root", str(tmp_path), "init") == 0
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "coverage: not checked, there are no facts; run: systemap extract" in out
    assert out.rstrip().endswith("run: systemap extract")
