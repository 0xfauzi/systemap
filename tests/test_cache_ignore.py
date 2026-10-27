"""Git does not add the systemap caches in `.systemap/` after `git add -A` (cacheignore).

`systemap init` and a cache save make `.systemap/.gitignore` with the line `*` if the
folder has no such entry. They do not change an existing entry or the `.gitignore` file
of the repository root. The tests use an injected agent.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from conftest import write_tree
from test_cache_trust import answer, git, route_project, run_journeys

from systemap import decisions_store, delta, file_write, history, jev
from systemap.cli import main
from systemap.config import Config

IGNORE = Path(".systemap/.gitignore")


def porcelain(root: Path) -> list[str]:
    return git(root, "status", "--porcelain", "--untracked-files=all").splitlines()


def test_init_and_one_cached_answer_leave_no_cache_entry_in_git_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance: before the change, `git status --porcelain` gave
    `?? .systemap/agent-cache.json` and `?? .systemap/agent-cache.json.lock`."""
    monkeypatch.delenv(jev.TRUST_TRACKED, raising=False)
    git(tmp_path, "init", "-q")
    route_project(tmp_path)
    calls: list[int] = []
    assert run_journeys(tmp_path, answer("first"), calls) == 0
    assert calls == [1]
    assert (tmp_path / ".systemap/agent-cache.json").is_file()
    assert (tmp_path / IGNORE).read_bytes() == b"*\n"
    assert [line for line in porcelain(tmp_path) if ".systemap" in line] == []
    git(tmp_path, "add", "-A")
    assert git(tmp_path, "ls-files", ".systemap") == ""


def test_init_writes_the_file_and_tells_the_reader(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": ""})
    assert main(["--root", str(tmp_path), "init", "--no-ci"]) == 0
    assert "wrote .systemap/.gitignore" in capsys.readouterr().out.splitlines()
    assert (tmp_path / IGNORE).read_bytes() == b"*\n"


def test_an_existing_file_stays_the_same_byte_for_byte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(jev.TRUST_TRACKED, raising=False)
    mine = b"# mine\r\n!agent-cache.json\r\nfacts/"
    (tmp_path / ".systemap").mkdir()
    (tmp_path / IGNORE).write_bytes(mine)
    os.chmod(tmp_path / IGNORE, 0o600)
    mode = (tmp_path / IGNORE).stat().st_mode
    root_ignore = b"/dist\n"
    (tmp_path / ".gitignore").write_bytes(root_ignore)
    git(tmp_path, "init", "-q")
    route_project(tmp_path)
    assert "kept .systemap/.gitignore (file exists)" in capsys.readouterr().out.splitlines()
    assert run_journeys(tmp_path, answer("first"), []) == 0
    cache = jev.Cache(tmp_path / ".systemap/jev-cache.json", root=tmp_path)
    cache.entries["k"] = {"prose": "p"}
    cache.save()
    assert (tmp_path / IGNORE).read_bytes() == mine
    assert (tmp_path / IGNORE).stat().st_mode == mode
    assert (tmp_path / ".gitignore").read_bytes() == root_ignore


def test_a_cache_save_without_init_makes_the_file(tmp_path: Path) -> None:
    """Acceptance: before the change, the save made no `.systemap/.gitignore`."""
    git(tmp_path, "init", "-q")
    cache = jev.Cache(tmp_path / ".systemap/jev-cache.json", root=tmp_path)
    cache.entries["k"] = {"prose": "p"}
    cache.save()
    assert (tmp_path / IGNORE).read_bytes() == b"*\n"
    assert porcelain(tmp_path) == []
    assert not (tmp_path / ".gitignore").exists()


def test_a_facts_cache_write_makes_the_file(tmp_path: Path) -> None:
    """Acceptance: before the change, `.systemap/facts/` showed in `git status`."""
    write_tree(tmp_path, {"pkg/__init__.py": "", "pkg/reader.py": "X = 1\n"})
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "source")
    cfg = Config(tmp_path, "Example", (("pkg", "pkg"),), "python")
    history.facts_at(cfg, delta.resolve(tmp_path, "HEAD"))
    assert list(history.cache_dir(cfg).glob("*.json"))
    assert (tmp_path / IGNORE).read_bytes() == b"*\n"
    assert porcelain(tmp_path) == []


def test_a_decisions_store_save_makes_the_file(tmp_path: Path) -> None:
    """Acceptance: before the change, `.systemap/decisions.json` showed in `git status`."""
    git(tmp_path, "init", "-q")
    decisions_store.save(tmp_path, {"k": {"answer": "a"}})
    assert decisions_store.path(tmp_path).is_file()
    assert (tmp_path / IGNORE).read_bytes() == b"*\n"
    assert porcelain(tmp_path) == []


def test_a_cache_outside_the_cache_folder_makes_no_file(tmp_path: Path) -> None:
    cache = jev.Cache(tmp_path / "answers/jev.json", root=tmp_path)
    cache.entries["k"] = {"prose": "p"}
    cache.save()
    assert json.loads((tmp_path / "answers/jev.json").read_text(encoding="utf-8"))["entries"]
    assert not (tmp_path / ".systemap").exists()
    assert not file_write.ignore_caches(tmp_path, tmp_path / "answers/jev.json")


def test_a_link_or_a_folder_at_the_name_stays_as_it_is(tmp_path: Path) -> None:
    target = tmp_path / "elsewhere.txt"
    target.write_bytes(b"x")
    (tmp_path / ".systemap").mkdir()
    (tmp_path / IGNORE).symlink_to(target)
    assert not file_write.ignore_caches(tmp_path)
    assert (tmp_path / IGNORE).is_symlink()
    assert target.read_bytes() == b"x"
    other = tmp_path / "other"
    (other / IGNORE).mkdir(parents=True)
    assert not file_write.ignore_caches(other)
    assert (other / IGNORE).is_dir()


def test_a_cache_folder_that_is_a_link_out_of_the_root_is_refused(tmp_path: Path) -> None:
    root, outside = tmp_path / "root", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / ".systemap").symlink_to(outside, target_is_directory=True)
    with pytest.raises(file_write.RefusedFile):
        file_write.ignore_caches(root)
    assert list(outside.iterdir()) == []


def test_the_repository_and_its_fixtures_commit_no_cache_folder() -> None:
    top = Path(__file__).resolve().parents[1]
    listed = subprocess.run(
        ["git", "ls-files", "-z"], cwd=top, capture_output=True, text=True, check=True
    ).stdout.split("\0")
    assert [p for p in listed if "/.systemap/" in f"/{p}"] == []
