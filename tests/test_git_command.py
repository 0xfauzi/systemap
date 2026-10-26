"""Git commands of systemap do not run the programs that a repository configuration names.

Acceptance (exec-4): a repository configuration names a marker program for
`core.fsmonitor`, the hooks, `diff.external`, a filter, a `textconv` program, and
`gpg.program` with `log.showSignature`. Plain Git commands run the markers. The Git
commands of `live`, `judgement --order-by-drift`, `history`, `delta`, and `render --base`
write no marker line.

Acceptance (exec-5): a Git command that does not stop gives the error class of the module,
with "did not stop". A Git program that cannot start gives "could not start".

Acceptance (safedir-1): if Git refuses the repository (for example because of dubious
ownership), the error text gives the Git cause, not "unknown revision".
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from systemap import change, delta_git, drift_order, extraction, git_command, history, trend
from systemap.cli import main
from systemap.delta import DeltaError

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the markers are shell scripts")

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
DIGEST = "a" * 64
MARKER = """#!/bin/sh
echo "$(basename "$0")" >> {hits}
case "$(basename "$0")" in
  clean|smudge) cat ;;
  textconv) cat "$1" ;;
esac
exit 0
"""
DUBIOUS = (
    "fatal: detected dubious ownership in repository at '/srv/repo'\n"
    "To add an exception for this directory, call:\n"
    "\n"
    "\tgit config --global --add safe.directory /srv/repo\n"
)


def git(root: Path, *args: str, stdin: bytes | None = None) -> str:
    done = subprocess.run(
        [*GIT, *args], cwd=root, input=stdin, capture_output=True, check=True, timeout=120
    )
    return done.stdout.decode("utf-8").strip()


def _markers(tmp: Path) -> tuple[Path, Path]:
    """Give the folder of the marker programs and the file of their marker lines."""
    hits, folder = tmp / "hits", tmp / "bin"
    folder.mkdir()
    for name in ("fsmonitor", "extdiff", "clean", "smudge", "textconv", "gpg", "hook"):
        path = folder / name
        path.write_text(MARKER.format(hits=hits), encoding="utf-8")
        path.chmod(0o755)
    hooks = tmp / "hooks"
    hooks.mkdir()
    for name in ("post-index-change", "reference-transaction", "post-checkout"):
        (hooks / name).symlink_to(folder / "hook")
    return folder, hits


def _signed(root: Path) -> str:
    """Write a copy of HEAD with a signature header. Git gives it to `gpg.program`."""
    body = git(root, "cat-file", "commit", "HEAD")
    head, _, message = body.partition("\n\n")
    signature = "gpgsig -----BEGIN PGP SIGNATURE-----\n \n AAAA\n -----END PGP SIGNATURE-----"
    raw = f"{head}\n{signature}\n\n{message}\n".encode()
    sha = git(root, "hash-object", "-t", "commit", "-w", "--stdin", stdin=raw)
    git(root, "update-ref", "HEAD", sha)
    return sha


def hostile(tmp: Path) -> tuple[Path, Path, str, str]:
    """A repository with two commits whose configuration names a marker for each program.

    The working tree has a changed file and an untracked file. The result is the root, the
    marker file, the base commit, and the head commit.
    """
    folder, hits = _markers(tmp)
    root = tmp / "repo"
    (root / "map").mkdir(parents=True)
    (root / "pkg").mkdir()
    (root / ".gitattributes").write_text("* filter=evil diff=evil\n", encoding="utf-8")
    (root / "map/model.py").write_text("source_review = 'x'\n", encoding="utf-8")
    (root / "pkg/a.py").write_text("A = 1\n", encoding="utf-8")
    git(root, "init", "-q", "-b", "main")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "base")
    base = git(root, "rev-parse", "HEAD")
    (root / "map/model.py").write_text(f"source_review = {DIGEST!r}\n", encoding="utf-8")
    (root / "pkg/b.py").write_text("B = 1\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "head")
    head = _signed(root)
    for key, value in (
        ("core.fsmonitor", folder / "fsmonitor"),
        ("core.hooksPath", tmp / "hooks"),
        ("diff.external", folder / "extdiff"),
        ("filter.evil.clean", folder / "clean"),
        ("filter.evil.smudge", folder / "smudge"),
        ("filter.evil.required", "true"),
        ("diff.evil.textconv", folder / "textconv"),
        ("gpg.program", folder / "gpg"),
        ("log.showSignature", "true"),
    ):
        git(root, "config", key, str(value))
    (root / "pkg/a.py").write_text("A = 22\n", encoding="utf-8")
    (root / "pkg/new.py").write_text("N = 1\n", encoding="utf-8")
    return root, hits, base, head


def lines(hits: Path) -> list[str]:
    return sorted(set(hits.read_text().split())) if hits.exists() else []


def test_the_fixture_runs_each_marker_with_plain_git(tmp_path: Path) -> None:
    """Plain Git runs the markers. Thus the next test examines a real risk."""
    root, hits, base, _head = hostile(tmp_path)
    for args in (
        ["diff", "--name-only", base],
        ["diff", base, "--", "pkg"],
        ["log", f"-S{DIGEST}", "-1", "--format=%H", "--", "map"],
        ["log", "-1", "--format=%H"],
    ):
        subprocess.run(["git", *args], cwd=root, capture_output=True, check=False, timeout=120)
    assert {"clean", "extdiff", "fsmonitor", "gpg", "textconv"} <= set(lines(hits))


def test_the_git_commands_of_systemap_run_no_repository_program(tmp_path: Path) -> None:
    """Acceptance (exec-4): the Git commands of systemap write no marker line."""
    root, hits, base, head = hostile(tmp_path)
    # live: the working tree comparison and the untracked files.
    assert change._changed_files(root, base) == ["map/model.py", "pkg/a.py", "pkg/b.py"]
    assert change._untracked_files(root) == ["pkg/new.py"]
    assert change.comparison_base(root, base) == base
    # judgement --order-by-drift: the reviewed commit and the diff to the working tree.
    assert drift_order.reviewed_commit(root, "map", DIGEST) == head
    assert "A = 22" in drift_order._diff(root, base, ["pkg/a.py"])
    # history and delta: the samples, the changed files, the diff, and the tree reader.
    assert history.sample(root, "10 years ago", 1) == [base, head]
    assert history.changed_files(root, base, head) == ["map/model.py", "pkg/b.py"]
    assert "+B = 1" in history.diff_of(root, base, head, ["pkg/b.py"])
    assert history.shallow_note(root, [base, head]) == []
    window = trend.Window(base=base, head=head, new_files=("pkg/b.py",))
    assert trend.with_causes(root, window).caused_by == ("head",)
    assert delta_git.merge_base(root, base, head) == base
    assert delta_git.blobs_at(root, head, ["pkg/b.py"]) == {"pkg/b.py": b"B = 1\n"}
    assert lines(hits) == []


def test_a_filter_of_a_submodule_configuration_does_not_run(tmp_path: Path) -> None:
    """Acceptance (exec-4): a submodule has its own configuration in the `.git` folder.

    Before the repair, `git diff` ran the status command of Git in the submodule. Then Git
    started the `clean` program that the configuration of the submodule names.
    """
    folder, hits = _markers(tmp_path)
    inner, root = tmp_path / "inner", tmp_path / "repo"
    inner.mkdir()
    root.mkdir()
    (inner / ".gitattributes").write_text("* filter=evil diff=evil\n", encoding="utf-8")
    (inner / "a.txt").write_text("one\n", encoding="utf-8")
    git(inner, "init", "-q")
    git(inner, "add", "-A")
    git(inner, "commit", "-qm", "inner")
    (root / "top.txt").write_text("top\n", encoding="utf-8")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "top")
    git(root, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(inner), "sub")
    git(root, "commit", "-qm", "sub")
    for key, name in (("filter.evil.clean", "clean"), ("core.fsmonitor", "fsmonitor")):
        git(root / "sub", "config", key, str(folder / name))
    (root / "sub/a.txt").write_text("two\n", encoding="utf-8")
    assert change._changed_files(root, "HEAD") == []
    assert drift_order._diff(root, "HEAD", ["sub"]) == ""
    assert lines(hits) == []


def test_a_filter_of_the_user_configuration_is_not_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only a filter of the repository scopes gets the settings that stop it."""
    user = tmp_path / "user.cfg"
    user.write_text('[filter "lfs"]\n\tclean = git-lfs clean -- %f\n', encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(user))
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "filter.evil.clean", "cat")
    git(root, "config", "filter.e.v il.process", "cat")
    stops = git_command._no_filters(root, git_command.GitError)
    assert "filter.evil.clean=" in stops
    assert "filter.e.v il.process=" in stops
    assert not [arg for arg in stops if "lfs" in arg]


def test_a_filter_name_with_an_equals_sign_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "filter.e=vil.clean", "cat")
    with pytest.raises(change.ChangeError, match="contains '='"):
        change._changed_files(root, "HEAD")


def test_the_hooks_folder_is_the_null_device_of_the_platform() -> None:
    assert f"core.hooksPath={os.devnull}" in git_command.SAFE_CONFIG


def _fake_git(tmp: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> None:
    folder = tmp / "fakebin"
    folder.mkdir()
    program = folder / "git"
    program.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    program.chmod(0o755)
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")


def test_a_git_command_that_does_not_stop_gives_the_module_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance (exec-5): before the repair, `history.git` had no time limit. Thus it
    waited until the fake Git stopped after 60 seconds. Now the time limit of 1 s stops it."""
    _fake_git(tmp_path, monkeypatch, "exec sleep 60")
    monkeypatch.setattr(history, "TIMEOUT", 1.0)
    with pytest.raises(DeltaError, match="did not stop in the time limit of 1 s"):
        history.git(tmp_path, "log", "-1")
    with pytest.raises(change.ChangeError, match="did not stop"):
        git_command.run(tmp_path, "status", timeout=1.0, error=change.ChangeError)


def test_a_cat_file_process_that_does_not_answer_gives_the_time_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Before the repair, the blob reader had no time limit. It waited 60 s until the fake
    process stopped, and then gave "gave no blob". Now the time limit of 0.5 s stops it."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.txt").write_text("a\n", encoding="utf-8")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "c")
    real = git_command.command

    def hang(*args: str) -> list[str]:
        return ["sleep", "60"] if args[:1] == ("cat-file",) else real(*args)

    monkeypatch.setattr(git_command, "command", hang)
    monkeypatch.setattr(delta_git, "BLOB_LIMIT", 0.5, raising=False)
    with pytest.raises(DeltaError, match="did not stop in the time limit of 0.5 s"):
        delta_git.blobs_at(root, "HEAD", ["a.txt"])


def test_a_git_program_that_cannot_start_gives_the_module_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "nothing"))
    with pytest.raises(DeltaError, match="could not start"):
        history.git(tmp_path, "log", "-1")
    with pytest.raises(DeltaError, match="could not start"):
        delta_git.resolve(tmp_path, "HEAD")


def test_a_git_refusal_gives_the_git_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance (safedir-1): before the repair, the text was "unknown revision main"."""
    _fake_git(tmp_path, monkeypatch, f"printf '%s' \"{DUBIOUS}\" >&2\nexit 128")
    with pytest.raises(change.ChangeError, match="dubious ownership") as found:
        change.comparison_base(tmp_path, "main")
    assert "unknown revision" not in str(found.value)
    with pytest.raises(DeltaError, match="dubious ownership"):
        delta_git.resolve(tmp_path, "main")
    commit, cause = extraction.head_commit(tmp_path)
    assert (commit, "dubious ownership" in cause) == ("", True)


def test_extract_gives_a_note_when_git_gives_no_commit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance (safedir-1): before the repair, extract wrote an empty `built_at_commit`
    with no note."""
    from conftest import STARTER_MODULES, init_two_cards, write_tree

    root = tmp_path / "repo"
    write_tree(root, {**STARTER_MODULES, "pkg/__init__.py": ""})
    init_two_cards(root, "--no-ci")
    capsys.readouterr()
    assert main(["--root", str(root), "extract"]) == 0
    out = capsys.readouterr()
    assert "built_at_commit" in out.out + out.err
    assert "not a git repository" in (out.out + out.err).lower()


@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() != 0, reason="needs chown")
def test_a_repository_of_a_different_owner_gives_the_git_cause(tmp_path: Path) -> None:
    """Acceptance (safedir-1): a repository of uid 4242 gives "dubious ownership"."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    (root / "a").write_text("a\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "c")
    for folder, _dirs, files in os.walk(root):
        os.chown(folder, 4242, 4242)
        for name in files:
            os.chown(Path(folder) / name, 4242, 4242)
    with pytest.raises(change.ChangeError, match="dubious ownership"):
        change.comparison_base(root, "HEAD")


def _promisor(tmp: Path) -> tuple[Path, Path, str]:
    """A repository with a missing blob and a promisor remote that names a marker program.

    Git does a lazy fetch for a missing blob. The fetch runs `remote.origin.uploadpack`.
    The result is the root, the marker file, and the commit that refers to the blob.
    """
    root, mark = tmp / "repo", tmp / "MARK"
    root.mkdir()
    (root / "f").write_text("lost\n", encoding="utf-8")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "c")
    blob = git(root, "rev-parse", "HEAD:f")
    (root / ".git/objects" / blob[:2] / blob[2:]).unlink()
    for key, value in (
        ("core.repositoryformatversion", "1"),
        ("extensions.partialClone", "origin"),
        ("remote.origin.promisor", "true"),
        ("remote.origin.url", str(tmp)),
        ("remote.origin.uploadpack", f"touch {mark}; false"),
    ):
        git(root, "config", key, value)
    return root, mark, git(root, "rev-parse", "HEAD")


def test_the_fixture_does_a_lazy_fetch_with_plain_git(tmp_path: Path) -> None:
    root, mark, head = _promisor(tmp_path)
    subprocess.run(["git", "cat-file", "-p", f"{head}:f"], cwd=root, capture_output=True)
    assert mark.exists()


def test_a_missing_blob_does_not_start_a_lazy_fetch(tmp_path: Path) -> None:
    """Acceptance (git-sec-1): a read of a missing blob does not run the upload program.

    Before the repair, `git_command.run` and the `cat-file --batch` process of `delta`
    did a lazy fetch, and the fetch made the marker file.
    """
    root, mark, head = _promisor(tmp_path)
    git_command.run(root, "cat-file", "-p", f"{head}:f")
    with pytest.raises(DeltaError, match="gave no blob"):
        delta_git.blobs_at(root, head, ["f"])
    assert not mark.exists()
