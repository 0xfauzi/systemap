from __future__ import annotations

from pathlib import Path

import pytest
from conftest import TINY_PACKAGE, write_tree

from systemap.cli import main

STARTER_MODULES = {
    "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
    "pkg/writer.py": "def write(request: str) -> str:\n    return request\n",
}


def run(*argv: str) -> int:
    return main(list(argv))


def test_init_then_refresh_round_trip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    assert run("--root", str(tmp_path), "init", "--name", "demo") == 0
    for rel in (
        "systemap.toml",
        "map/model.py",
        "docs/map/.gitkeep",
        ".github/workflows/systemap.yml",
        ".claude/skills/systemap/SKILL.md",
    ):
        assert (tmp_path / rel).is_file(), rel
    assert 'name = "demo"' in (tmp_path / "systemap.toml").read_text()
    out = capsys.readouterr().out
    assert "wrote .claude/skills/systemap/SKILL.md" in out
    assert out.rstrip().endswith("Map this repository with systemap. Follow the systemap skill.")

    # Nothing built yet: extract --check and render are stale, with the fix named.
    assert run("--root", str(tmp_path), "extract", "--check") == 1
    assert "run: systemap extract" in capsys.readouterr().out
    assert run("--root", str(tmp_path), "render") == 1
    assert "run: systemap extract" in capsys.readouterr().out

    assert run("--root", str(tmp_path), "extract") == 0
    assert (tmp_path / "docs/map/map.json").is_file()
    assert run("--root", str(tmp_path), "extract", "--check") == 0
    # Facts but no page yet: every rule is clean except stale, and the fix is refresh.
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "map layout: clean" in out
    assert "docs/map/index.html has not been rendered" in out
    assert "docs/map/system.html has not been rendered" in out
    assert out.rstrip().endswith("run: systemap refresh")
    assert run("--root", str(tmp_path), "render") == 0
    page = (tmp_path / "docs/map/index.html").read_text()
    assert "<title>demo system map</title>" in page
    assert run("--root", str(tmp_path), "render", "--check") == 0

    # The first refresh draws the configured figure; the second has nothing to do.
    assert run("--root", str(tmp_path), "refresh") == 0
    assert (tmp_path / "docs/map/system.html").is_file()
    assert "map: updated" in capsys.readouterr().out
    assert run("--root", str(tmp_path), "check") == 0
    assert run("--root", str(tmp_path), "refresh") == 0
    assert "already current" in capsys.readouterr().out
    # Init never overwrites what exists.
    assert run("--root", str(tmp_path), "init") == 0
    assert "kept systemap.toml" in capsys.readouterr().out


def test_init_no_ci_skips_the_workflow(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    assert run("--root", str(tmp_path), "init", "--no-ci") == 0
    assert not (tmp_path / ".github").exists()
    assert (tmp_path / "map/model.py").is_file()
    assert (tmp_path / ".claude/skills/systemap/SKILL.md").is_file()
    assert "systemap.yml" not in capsys.readouterr().out


def test_stale_after_code_change(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    assert run("--root", str(tmp_path), "init") == 0
    assert run("--root", str(tmp_path), "refresh") == 0
    (tmp_path / "pkg/reader.py").write_text("def read(source):\n    return 1\n")
    assert run("--root", str(tmp_path), "extract", "--check") == 1
    out = capsys.readouterr().out
    assert "code changed since the map was built: pkg.reader" in out
    assert run("--root", str(tmp_path), "refresh") == 0
    assert run("--root", str(tmp_path), "extract", "--check") == 0


def test_configuration_errors_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", "systemap.toml": 'nam = "typo"\n'})
    assert run("--root", str(tmp_path), "extract") == 2
    err = capsys.readouterr().err
    assert "unknown key: nam" in err
    assert "fix systemap.toml" in err

    write_tree(tmp_path, {"systemap.toml": 'name = "ok"\n'})
    assert run("--root", str(tmp_path), "extract") == 2
    assert "model module not found" in capsys.readouterr().err

    write_tree(tmp_path, {"map/model.py": "MODEL = 1\n"})
    assert run("--root", str(tmp_path), "check") == 2
    assert "MODEL must be a systemap.Model" in capsys.readouterr().err

    write_tree(tmp_path, {"pyproject.toml": '[tool.systemap]\ntheme = "dark"\n'})
    (tmp_path / "systemap.toml").unlink()
    assert run("--root", str(tmp_path), "check") == 2
    assert "theme must be a table" in capsys.readouterr().err

    # The tracker's link template left with the tracker; an old key is refused.
    write_tree(tmp_path, {"pyproject.toml": '[tool.systemap]\nissue_url = "https://x/{n}"\n'})
    assert run("--root", str(tmp_path), "check") == 2
    assert "unknown key: issue_url" in capsys.readouterr().err


def test_check_fails_on_overlapping_fixture(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    assert run("--root", str(tmp_path), "init") == 0
    model = tmp_path / "map/model.py"
    model.write_text(model.read_text().replace('x=COL["c2"]', 'x=COL["c1"]'))
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "placement: Reader overlaps Writer" in out
    assert "fix map/model.py" in out
    assert run("--root", str(tmp_path), "refresh") == 1


def test_figure_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    assert run("--root", str(tmp_path), "init") == 0
    assert run("--root", str(tmp_path), "extract") == 0
    out = tmp_path / "fig.html"
    assert run("--root", str(tmp_path), "figure", "--static", "--out", str(out)) == 0
    text = out.read_text()
    assert text.startswith('<figure data-generated="systemap"')
    assert "<script>" not in text
    assert (
        run(
            "--root",
            str(tmp_path),
            "figure",
            "--interactive",
            "--components",
            "Reader,Writer",
            "--out",
            str(out),
        )
        == 0
    )
    assert "<script>" in out.read_text()
    assert run("--root", str(tmp_path), "figure", "--components", "Nope", "--out", str(out)) == 2
    assert "unknown component ids: Nope" in capsys.readouterr().err
    assert run("--root", str(tmp_path), "figure", "--mode", "change", "--out", str(out)) == 1


def test_skill_command_writes_the_skill(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "tmp"
    assert run("--root", str(tmp_path), "skill", "--dir", str(target)) == 0
    written = target / "SKILL.md"
    assert written.is_file()
    assert f"wrote {written}" in capsys.readouterr().out
    text = written.read_text()
    assert text.startswith("---\nname: systemap\n")
    assert "systemap check" in text
    assert "systemap extract" in text
    # The default location is under the root, and rerunning refreshes the text.
    assert run("--root", str(tmp_path), "skill") == 0
    default = tmp_path / ".claude/skills/systemap/SKILL.md"
    assert default.read_text() == text
    default.write_text("edited")
    assert run("--root", str(tmp_path), "skill") == 0
    assert default.read_text() == text
    # --print writes the same text to stdout and touches nothing.
    default.write_text("edited")
    capsys.readouterr()
    assert run("--root", str(tmp_path), "skill", "--print") == 0
    assert capsys.readouterr().out == text
    assert default.read_text() == "edited"


def test_extract_on_tiny_package_via_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(tmp_path, TINY_PACKAGE)
    assert run("--root", str(tmp_path), "init") == 0
    assert run("--root", str(tmp_path), "extract") == 0
    out = capsys.readouterr().out
    assert "modules: 3" in out
    assert "written to docs/map/map.json" in out
