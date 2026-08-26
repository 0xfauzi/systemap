"""What the package promises on every operating system it claims.

Every file systemap writes ends its lines with LF, whatever the platform's
own convention, so a page rendered on one machine is byte for byte what
another renders and the committed map compares as written. Every path it
prints or records uses forward slashes, so a message, a facts file and a
test that reads them are the same on Windows as on Linux. The workflow
runs the suite and the wheel on all three.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import TINY_PACKAGE, init_two_cards, write_tree

from systemap.cli import main
from systemap.config import Config

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "systemap.yml"


def run(*argv: str) -> int:
    return main(list(argv))


def test_every_written_file_ends_its_lines_with_lf(tmp_path: Path) -> None:
    write_tree(tmp_path, TINY_PACKAGE)
    init_two_cards(tmp_path)
    assert run("--root", str(tmp_path), "refresh") == 0
    assert run("--root", str(tmp_path), "place", "--all") == 0
    written = [
        "systemap.toml",
        "map/model.py",
        ".github/workflows/systemap.yml",
        ".claude/skills/systemap/SKILL.md",
        ".claude/skills/systemap/references/schema.md",
        "docs/map/map.json",
        "docs/map/index.html",
        "docs/map/figures/structure.svg",
        "docs/map/figures/system.svg",
    ]
    for rel in written:
        raw = (tmp_path / rel).read_bytes()
        assert b"\r" not in raw, f"{rel} carries a carriage return"
        assert raw.endswith(b"\n"), rel


def test_paths_are_printed_and_recorded_with_forward_slashes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = Config(root=tmp_path, name="demo", package_roots=(("pkg", "pkg"),))
    assert cfg.rel(tmp_path / "docs" / "map" / "index.html") == "docs/map/index.html"
    assert cfg.rel(tmp_path.parent / "elsewhere") == str(tmp_path.parent / "elsewhere")
    write_tree(tmp_path, TINY_PACKAGE)
    init_two_cards(tmp_path)
    out = capsys.readouterr().out
    assert "wrote .claude/skills/systemap/ (SKILL.md and 8 references)" in out
    assert run("--root", str(tmp_path), "extract") == 0
    facts = (tmp_path / "docs/map/map.json").read_text(encoding="utf-8")
    assert '"file":"pkg/reader.py"' in facts.replace(" ", "")
    assert "\\\\" not in facts, "a module's file is recorded with forward slashes"


def test_the_workflow_runs_the_suite_and_the_wheel_on_three_operating_systems() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    for job in ("\n  test:\n", "\n  install:\n", "\n  plugin:\n", "\n  systemap:\n"):
        assert job in text, job
    assert text.count("os: [ubuntu-latest, macos-latest, windows-latest]") == 2
    assert text.count('python: ["3.11", "3.13"]') == 2
    assert "UV_PYTHON: ${{ matrix.python }}" in text
    install = text.split("\n  install:\n", 1)[1].split("\n  plugin:\n", 1)[0]
    assert "uv build --wheel" in install
    assert "uv venv --seed venv" in install
    assert "pip install --no-deps dist/systemap-*.whl" in install
    for command in (
        "systemap init",
        "systemap extract",
        "systemap refresh",
        "systemap check",
        "systemap judgement --strict",
        "systemap render --check",
    ):
        assert f"\n          {command}\n" in install, command
    assert "cd ../selfmap" in install, "the copy is beside the checkout, not in it"
    # Every action is pinned to a commit and no job keeps the token.
    for line in text.splitlines():
        if "uses:" in line:
            assert "@" in line and "#" in line, line
            sha = line.split("@", 1)[1].split()[0]
            assert len(sha) == 40, line
    assert "persist-credentials: false" in text
