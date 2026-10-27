"""The working-tree comparisons and the Git filters of the repository configuration.

Acceptance (gitfilters O1): if the repository configuration and the user configuration
define the same filter name, the working-tree comparison uses the programs of the user
configuration. A file that a touch or a new checkout makes stat-dirty is not a change. The
program of the repository configuration does not run (no marker line).

Acceptance (gitfilters O3): if only the repository configuration defines the filter of a
changed path, the live comparison does not give the path as a changed file. It gives the
path in `filtered_paths`, and the page gives a note for it. The drift question uses the
text form. A path that a commit after the merge base changed stays a changed file.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from systemap import change, drift_order, git_command, page_changes

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the filters are shell commands")

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
# A keyword filter. The index has `$Id$`. The working tree has the expanded form.
KEYWORD = """[filter "kw"]
\tclean = sed -e 's/[$]Id:[^$]*[$]/$Id$/'
\tsmudge = sed -e 's/[$]Id[$]/$Id: expanded $/'
"""
SOURCE = "# $Id$\ndef run():\n    return 1\n"


def git(root: Path, *args: str) -> str:
    done = subprocess.run([*GIT, *args], cwd=root, capture_output=True, check=True, timeout=120)
    return done.stdout.decode("utf-8").strip()


def _marker(tmp: Path) -> tuple[Path, Path]:
    """Give a program that writes a marker line and copies its input, and the marker file."""
    hits, program = tmp / "hits", tmp / "marker.sh"
    program.write_text(f'#!/bin/sh\necho run >> "{hits}"\ncat\n', encoding="utf-8")
    program.chmod(0o755)
    return program, hits


def _keyword_repo(tmp: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repository with one source file under the keyword filter of the user scope.

    The working tree has the expanded keyword. The file is stat-dirty: its content is the
    same as after the checkout, but its time is new.
    """
    user = tmp / "user.cfg"
    user.write_text(KEYWORD, encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(user))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    root = tmp / "repo"
    root.mkdir()
    (root / ".gitattributes").write_text("*.py filter=kw\n", encoding="utf-8")
    (root / "a.py").write_text(SOURCE, encoding="utf-8")
    git(root, "init", "-q", "-b", "main")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "one")
    (root / "a.py").unlink()
    git(root, "checkout", "--", "a.py")
    assert "$Id: expanded $" in (root / "a.py").read_text(encoding="utf-8")
    assert git(root, "status", "--porcelain") == ""
    return root


def _touch(path: Path) -> None:
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 5_000_000_000))


def _local_only(tmp: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """The keyword repository after the filter moves from the user scope to the local scope.

    The local `clean` program writes a marker line. The result is the root and the marker.
    """
    root = _keyword_repo(tmp, monkeypatch)
    program, hits = _marker(tmp)
    (tmp / "user.cfg").write_text("", encoding="utf-8")
    git(root, "config", "filter.kw.clean", str(program))
    _touch(root / "a.py")
    return root, hits


def test_the_trusted_definition_of_the_same_filter_name_is_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance (gitfilters O1): no false change, and the repository program does not run."""
    root = _keyword_repo(tmp_path, monkeypatch)
    program, hits = _marker(tmp_path)
    git(root, "config", "filter.kw.clean", str(program))
    git(root, "config", "filter.kw.required", "true")
    _touch(root / "a.py")
    assert change._changed_files(root, "HEAD") == []
    settings = git_command._no_filters(root, git_command.GitError)
    assert "filter.kw.clean=sed -e 's/[$]Id:[^$]*[$]/$Id$/'" in settings
    assert "filter.kw.required=false" in settings
    assert not [arg for arg in settings if "process" in arg or "smudge" in arg]
    assert git_command.stopped_filters(root, ["a.py"], git_command.GitError) == {}
    assert drift_order._source_diff(root, "HEAD", ["a.py"]) == ""
    # A `process` program of the repository has priority over each `clean` program. Git
    # then gets an empty `process` program, and the filter is stopped.
    git(root, "config", "filter.kw.process", str(program))
    assert "filter.kw.process=" in git_command._no_filters(root, git_command.GitError)
    assert git_command.stopped_filters(root, ["a.py"], git_command.GitError) == {"a.py": "kw"}
    assert not hits.exists()


def test_a_path_with_a_stopped_filter_is_not_a_changed_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance (gitfilters O3): the path is in `filtered_paths`, not in the files."""
    root, hits = _local_only(tmp_path, monkeypatch)
    # Git compares the raw file, so the plain list has a change that does not exist.
    assert change._changed_files(root, "HEAD") == ["a.py"]
    assert git_command.stopped_filters(root, ["a.py", "b.txt"], change.ChangeError) == {
        "a.py": "kw"
    }
    side = change._WorkingTree(SimpleNamespace(root=root), {})  # type: ignore[arg-type]
    assert side.files("HEAD") == []
    assert side.filtered_paths == ("a.py (filter kw)",)
    assert not hits.exists()


def test_a_committed_change_of_a_filtered_path_stays_a_changed_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, hits = _local_only(tmp_path, monkeypatch)
    base = git(root, "rev-parse", "HEAD")
    (root / "b.py").write_text("B = 1\n", encoding="utf-8")
    git(root, "-c", "filter.kw.clean=cat", "add", "b.py")
    git(root, "commit", "-qm", "two")
    # Plain Git ran the program of the repository for the commit. systemap must not.
    hits.unlink(missing_ok=True)
    _touch(root / "b.py")
    side = change._WorkingTree(SimpleNamespace(root=root), {})  # type: ignore[arg-type]
    assert side.files(base) == ["b.py"]
    assert side.filtered_paths == ("a.py (filter kw)",)
    assert not hits.exists()


def test_the_drift_question_uses_the_text_form_for_a_stopped_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance (gitfilters O3): the false diff of the `$Id$` line does not go to Jev."""
    root, hits = _local_only(tmp_path, monkeypatch)
    assert "$Id: expanded $" in drift_order._diff(root, "HEAD", ["a.py"])
    assert drift_order._source_diff(root, "HEAD", ["a.py"]) == ""
    assert not hits.exists()


def test_the_page_gives_a_note_for_the_paths_with_a_stopped_filter() -> None:
    ch: dict[str, Any] = {"filtered_paths": ["a.py (filter kw)"]}
    assert page_changes._not_known_paths(ch) == [
        "<p>systemap does not run the Git filters of the repository configuration for these "
        "paths. Their changes are not known: <code>a.py (filter kw)</code>.</p>"
    ]
    assert page_changes._not_known_paths({"filtered_paths": []}) == []


def test_the_trusted_settings_come_from_the_scopes_that_a_repository_cannot_supply() -> None:
    listing = "\0".join(
        [
            "system",
            "filter.a.clean\nsystem-clean",
            "global",
            "filter.a.clean\nuser-clean",
            "local",
            "filter.a.process\nrepository-program",
            "global",
            "filter.a.required",
            "global",
            "filter.a.smudge",
            "worktree",
            "filter.b.clean\nrepository-program",
            "",
        ]
    ).encode()
    assert git_command._trusted(listing) == {
        "filter.a.clean": "user-clean",
        "filter.a.required": "true",
    }
