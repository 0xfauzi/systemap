"""Values from the repository never reach Git as options.

Acceptance: a `source_review` value that is an option (for example
`--open-files-in-pager=<command>`) gives no reviewed commit, and the command does not run.
A ref that starts with a dash is refused as an unknown ref, not read as an option.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from systemap import delta_git, drift_order
from systemap.delta import DeltaError


def _repo(root: Path, value: str = "x") -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "map").mkdir()
    (root / "map" / "model.py").write_text(f"source_review = {value!r}\n", encoding="utf-8")
    for args in (
        ["add", "-A"],
        ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "c"],
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True)


def test_a_review_value_that_is_an_option_gives_no_commit_and_runs_nothing(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    marker = tmp_path / "ran"
    value = f"--open-files-in-pager=touch {marker}"
    # The hostile value is in a commit, so `git log -S` finds it and the grep step runs.
    _repo(root, value)
    assert drift_order.reviewed_commit(root, "map", value) is None
    assert not marker.exists()


def test_a_review_value_must_be_a_digest(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _repo(root)
    assert drift_order.reviewed_commit(root, "map", "x") is None
    assert drift_order.reviewed_commit(root, "map", "0" * 64) is None


def test_a_ref_that_starts_with_a_dash_is_an_unknown_ref(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _repo(root)
    with pytest.raises(DeltaError, match="unknown ref"):
        delta_git.resolve(root, "--output=/tmp/x")
