"""The manual publish script must release only the commit that has the version tag (issue 93)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "publish.sh"

# A replacement for uv: `uv run` gives the package version, and `uv build` makes one file.
FAKE_UV = """#!/usr/bin/env bash
case "$1" in
  run) echo 1.0.0 ;;
  build) mkdir -p dist && touch dist/systemap-1.0.0.tar.gz ;;
  *) exit 2 ;;
esac
"""


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    if shutil.which("bash") is None or shutil.which("git") is None:
        pytest.skip("bash and git are necessary")
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, root / "scripts" / "publish.sh")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "test")
    _git(root, "config", "commit.gpgsign", "false")
    _git(root, "config", "tag.gpgsign", "false")
    (root / ".gitignore").write_text("dist/\n")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "release")
    _git(root, "tag", "v1.0.0")
    return root


def _publish(repo: Path) -> subprocess.CompletedProcess[str]:
    tools = repo.parent / "bin"
    tools.mkdir(exist_ok=True)
    uv = tools / "uv"
    uv.write_text(FAKE_UV)
    uv.chmod(0o755)
    env = {**os.environ, "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}"}
    return subprocess.run(
        ["bash", "scripts/publish.sh", "--dry-run"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )


def test_publish_accepts_the_tagged_commit(repo: Path) -> None:
    result = _publish(repo)
    assert result.returncode == 0, result.stderr
    assert "Dry run" in result.stdout


def test_publish_refuses_a_commit_after_the_tag(repo: Path) -> None:
    (repo / "later.txt").write_text("a change after the release tag\n")
    _git(repo, "add", "later.txt")
    _git(repo, "commit", "-q", "-m", "later")
    result = _publish(repo)
    assert result.returncode == 1
    assert "v1.0.0" in result.stderr
    assert "HEAD" in result.stderr
    assert not (repo / "dist").exists()
