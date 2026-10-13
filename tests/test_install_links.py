"""`init` and `skill` write only in the selected directory, and keep an existing configuration.

Acceptance (Codex results cli-2 and cli-14):
- cli-2: a symbolic link that puts SKILL.md, the references directory, or a scaffold file
  outside the selected directory gives exit code 2. The file outside the directory does
  not change, and `init` writes no file. A symbolic link to a directory in the selected
  directory is permitted.
- cli-14: with a `[tool.systemap]` table in pyproject.toml and no systemap.toml, `init`
  writes no systemap.toml. The configuration that the commands read stays the table,
  with its model path and recorded answers. `init` writes the model at the model path of
  the table.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import write_tree

from systemap import config, skill
from systemap.cli import main
from systemap.config import ConfigError

STARTER = {
    "pkg/__init__.py": "",
    "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
}
OUTSIDE = "do not change\n"


def _repo(tmp_path: Path) -> tuple[Path, Path]:
    repo, outside = tmp_path / "repo", tmp_path / "outside"
    write_tree(repo, STARTER)
    write_tree(outside, {"SKILL.md": OUTSIDE, "references/language.md": OUTSIDE})
    return repo, outside


def _written(repo: Path) -> set[str]:
    found = {p for p in repo.rglob("*") if p.is_file() and not p.is_symlink()}
    return {p.relative_to(repo).as_posix() for p in found} - set(STARTER)


# ---- cli-2 --------------------------------------------------------------------------------


def test_init_refuses_a_skill_file_link_outside_the_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, outside = _repo(tmp_path)
    folder = repo / skill.DEFAULT_DIR
    folder.mkdir(parents=True)
    (folder / "SKILL.md").symlink_to(outside / "SKILL.md")
    assert main(["--root", str(repo), "init", "--no-ci"]) == 2
    assert "symbolic link" in capsys.readouterr().err
    assert (outside / "SKILL.md").read_text(encoding="utf-8") == OUTSIDE
    assert _written(repo) == set(), "init writes no file before the refusal"


def test_init_refuses_a_references_link_outside_the_repository(tmp_path: Path) -> None:
    repo, outside = _repo(tmp_path)
    folder = repo / skill.DEFAULT_DIR
    folder.mkdir(parents=True)
    (folder / skill.REFERENCES).symlink_to(outside / "references", target_is_directory=True)
    assert main(["--root", str(repo), "init", "--no-ci"]) == 2
    assert (outside / "references/language.md").read_text(encoding="utf-8") == OUTSIDE
    assert sorted(p.name for p in (outside / "references").iterdir()) == ["language.md"]


def test_init_refuses_a_scaffold_link_outside_the_repository(tmp_path: Path) -> None:
    repo, outside = _repo(tmp_path)
    (repo / "systemap.toml").symlink_to(outside / "new.toml")
    assert main(["--root", str(repo), "init", "--no-ci"]) == 2
    assert not (outside / "new.toml").exists()


def test_the_skill_command_refuses_a_link_outside_the_repository(tmp_path: Path) -> None:
    repo, outside = _repo(tmp_path)
    (repo / ".claude").symlink_to(outside, target_is_directory=True)
    assert main(["--root", str(repo), "skill"]) == 2
    with pytest.raises(ConfigError, match="symbolic link"):
        skill.write(repo / skill.DEFAULT_DIR, repo)
    assert (outside / "SKILL.md").read_text(encoding="utf-8") == OUTSIDE


def test_a_link_to_a_directory_in_the_repository_is_permitted(tmp_path: Path) -> None:
    repo, _outside = _repo(tmp_path)
    (repo / "skills/systemap").mkdir(parents=True)
    (repo / ".claude/skills").mkdir(parents=True)
    (repo / skill.DEFAULT_DIR).symlink_to(repo / "skills/systemap", target_is_directory=True)
    assert main(["--root", str(repo), "init", "--no-ci"]) == 0
    assert (repo / "skills/systemap/SKILL.md").read_text(encoding="utf-8") == skill.text()


# ---- cli-14 -------------------------------------------------------------------------------

PYPROJECT = """[project]
name = "demo"

[tool.systemap]
model = "design/model.py"
out_dir = "site/map"

[tool.systemap.package_roots]
"pkg" = "pkg"

[tool.systemap.judgement]
answered = [{ item = "single module: Reader", reason = "The reader is one part." }]
"""


def test_init_keeps_an_existing_pyproject_configuration(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, _outside = _repo(tmp_path)
    write_tree(repo, {"pyproject.toml": PYPROJECT})
    assert main(["--root", str(repo), "init", "--no-ci"]) == 0
    out = capsys.readouterr().out
    assert not (repo / "systemap.toml").exists()
    assert "kept pyproject.toml [tool.systemap] (configuration exists)" in out
    assert (repo / "design/model.py").is_file()
    assert not (repo / "map/model.py").exists()
    assert (repo / "site/map/.gitkeep").is_file()
    cfg = config.load(repo)
    assert cfg.source == "pyproject.toml [tool.systemap]"
    assert (cfg.model, cfg.out_dir) == ("design/model.py", "site/map")
