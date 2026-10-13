"""Change detection, the Git tree reader, and the history report (Codex results).

Each test gives its acceptance value in its docstring. The values were written before
the repairs.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tracemalloc
from pathlib import Path
from typing import Any

import pytest
from conftest import STARTER_MODULES, init_two_cards, write_tree
from test_drift_order import TS_MODEL
from test_nested import CONFIG as NESTED_CONFIG
from test_nested import MODELS as NESTED_MODELS
from test_nested import TREE as NESTED_TREE

from systemap import change, config, delta, delta_git, extract, extraction, nest, source_text, trend
from systemap.cli import main

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
TS_APP = Path(__file__).parent / "fixtures/typescript-app"
SOURCE = {"python": "pkg/reader.py", "typescript": "src/service.ts"}
MODULE = {"python": "pkg.reader", "typescript": "acme.web.service"}
OWNER = {"python": "Reader", "typescript": "Service"}
ADDED = {
    "python": "\n\ndef count(source: str) -> int:\n    return len(source)\n",
    "typescript": "\nexport function count(text: string): number {\n  return text.length;\n}\n",
}
OUTSIDE = {
    "python": "def other() -> None:\n    return None\n",
    "typescript": "export function other(): void {\n  return;\n}\n",
}


def git(root: Path, *args: str, stdin: bytes | None = None) -> str:
    done = subprocess.run(
        [*GIT, *args], cwd=root, input=stdin, capture_output=True, check=True, timeout=120
    )
    return done.stdout.decode("utf-8").strip()


def commit(root: Path, message: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-qm", message)
    return git(root, "rev-parse", "HEAD")


def make(root: Path, language: str) -> Path:
    """A project with a model in one Git commit."""
    if language == "python":
        write_tree(root, {**STARTER_MODULES, "pkg/__init__.py": ""})
        init_two_cards(root, "--no-ci")
    else:
        shutil.copytree(TS_APP, root)
        (root / "map/model.py").write_text(TS_MODEL, encoding="utf-8")
    git(root, "init", "-q", "-b", "main")
    commit(root, "base")
    return root


@pytest.fixture(params=["python", "typescript"])
def project(request: pytest.FixtureRequest, tmp_path: Path) -> tuple[Path, str]:
    return make(tmp_path / "repo", request.param), request.param


def compare(root: Path, base: str, head: str) -> dict[str, Any]:
    cfg = config.load(root)
    facts = extraction.build(cfg)
    return change.compute(cfg, nest.load(cfg).top.model, base, facts, head=head)


# ---- change-1: the tree reader and Windows paths ----------------------------------


BAD_NAMES = (
    "..\\outside.py",
    "C:\\outside.py",
    "C:outside.py",
    "\\\\server\\share\\outside.py",
    "pkg\\..\\..\\outside.py",
)


def test_the_tree_reader_refuses_windows_paths_on_each_platform(tmp_path: Path) -> None:
    """Acceptance (change-1): for a commit with a backslash path, a drive path, and a UNC
    path, `write_tree` writes only the safe file `pkg/good.py`. The test makes the tree with
    `git mktree`, so the paths are the same on each platform.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    blob = git(repo, "hash-object", "-w", "--stdin", stdin=b"X = 1\n")
    inner = git(repo, "mktree", stdin=f"100644 blob {blob}\tgood.py\n".encode())
    rows = [f"040000 tree {inner}\tpkg"] + [f"100644 blob {blob}\t{name}" for name in BAD_NAMES]
    tree = git(
        repo,
        "mktree",
        stdin=("\n".join(sorted(rows, key=lambda r: r.split("\t")[1])) + "\n").encode(),
    )
    sha = git(repo, "commit-tree", tree, "-m", "paths", stdin=b"")
    into = tmp_path / "into"
    into.mkdir()
    delta_git.write_tree(repo, sha, into.resolve())
    written = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*.py"))
    assert written == ["into/pkg/good.py"]


# ---- change-5 and change-25: source text in the change detection ------------------


@pytest.mark.parametrize("form", ["link", "mode"])
def test_an_unreadable_source_file_is_not_known_and_not_empty(
    project: tuple[Path, str], form: str, tmp_path: Path
) -> None:
    """Acceptance (change-5): if the working tree cannot read a changed source file, the
    change data gives the module as not known, with the read problem. It gives no removed
    public names for the module.
    """
    root, language = project
    if form == "mode" and (sys.platform == "win32" or os.geteuid() == 0):
        pytest.skip("The file mode does not refuse a read for this user.")
    source = root / SOURCE[language]
    source.write_text(source.read_text(encoding="utf-8") + ADDED[language], encoding="utf-8")
    cfg = config.load(root)
    facts = extraction.build(cfg)
    if form == "link":
        outside = tmp_path / "outside" / source.name
        outside.parent.mkdir()
        outside.write_text(OUTSIDE[language], encoding="utf-8")
        source.unlink()
        source.symlink_to(outside)
    else:
        source.chmod(0)
    try:
        found = change.compute(
            cfg, nest.load(cfg).top.model, "HEAD", facts, head=change.WORKING_TREE
        )
    finally:
        source.chmod(0o644)
    module, owner = MODULE[language], OWNER[language]
    assert module in found["unparsed"]
    part = found["per_component"][owner]
    assert not any(part["surface"]["removed"].values())
    reasons = [issue["reason"] for issue in part["unknown"][module]["head"]]
    assert reasons and all(r.startswith("source could not be read") for r in reasons)


TEST_FILE = {
    "python": (
        "tests/test_reader.py",
        "from pkg.reader import read\n\n\ndef test_read() -> None:\n    assert read('x') == 'x'\n",
    ),
    "typescript": ("tests/service.spec.ts", None),
}


def test_an_unreadable_test_file_gives_its_problem_and_no_removed_tests(
    project: tuple[Path, str], tmp_path: Path
) -> None:
    """Acceptance (change-5): if the working tree cannot read a changed test file, the
    change data gives the file and its read problem in `unread_tests`. It gives no removed
    tests for the file.
    """
    root, language = project
    rel, text = TEST_FILE[language]
    test = root / rel
    if text is not None:
        test.parent.mkdir(exist_ok=True)
        test.write_text(text, encoding="utf-8")
        commit(root, "a test")
    outside = tmp_path / "outside" / test.name
    outside.parent.mkdir()
    outside.write_text(test.read_text(encoding="utf-8"), encoding="utf-8")
    test.unlink()
    test.symlink_to(outside)
    cfg = config.load(root)
    found = change.compute(
        cfg, nest.load(cfg).top.model, "HEAD", extraction.build(cfg), head=change.WORKING_TREE
    )
    assert [line.split(": ")[0] for line in found["unread_tests"]] == [rel]
    assert "source could not be read" in found["unread_tests"][0]
    assert not any(part["surface"]["tests_removed"] for part in found["per_component"].values())


def test_a_missing_working_tree_file_is_a_removal(project: tuple[Path, str]) -> None:
    """Acceptance (change-5): a source file that the working tree does not have is a
    removal. The change data gives its public names as removed, not as not known.
    """
    root, language = project
    (root / SOURCE[language]).unlink()
    cfg = config.load(root)
    found = change.compute(
        cfg, nest.load(cfg).top.model, "HEAD", extraction.build(cfg), head=change.WORKING_TREE
    )
    assert MODULE[language] not in found["unparsed"]
    removed = found["per_component"][OWNER[language]]["surface"]["removed"]
    assert any(removed.values())


def test_a_byte_order_mark_gives_the_same_names_as_without_it(project: tuple[Path, str]) -> None:
    """Acceptance (change-25): a changed source file with a UTF-8 byte order mark gives the
    added name `count` and no unknown surface, as the same file without the mark gives.
    """
    root, language = project
    base = git(root, "rev-parse", "HEAD")
    source = root / SOURCE[language]
    text = source.read_text(encoding="utf-8") + ADDED[language]
    source.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    commit(root, "a mark and a name")
    for head in ("HEAD", change.WORKING_TREE):
        found = compare(root, base, head)
        assert MODULE[language] not in found["unparsed"], head
        part = found["per_component"][OWNER[language]]
        assert part["surface"]["added"]["operations"] == ["count"], head
        assert not part["unknown"], head


def test_source_that_is_not_utf8_is_not_known_as_in_extraction(
    project: tuple[Path, str],
) -> None:
    """Acceptance (change-25): extraction gives a read problem for source that is not
    UTF-8. The change detection gives the module as not known for the same file.
    """
    root, language = project
    base = git(root, "rev-parse", "HEAD")
    source = root / SOURCE[language]
    source.write_bytes(
        source.read_bytes() + b"\n// \xff\n"
        if language != "python"
        else source.read_bytes() + b"\n# \xff\n"
    )
    commit(root, "not UTF-8")
    for head in ("HEAD", change.WORKING_TREE):
        found = compare(root, base, head)
        assert MODULE[language] in found["unparsed"], head


def test_the_source_text_rule_removes_the_mark_and_changes_newlines() -> None:
    """Acceptance (change-25): one function gives the text for extraction and for the
    change detection. It removes a leading mark and gives LF newlines.
    """
    assert source_text.decode(b"\xef\xbb\xbfa\r\nb\rc\n") == "a\nb\nc\n"
    with pytest.raises(UnicodeError):
        source_text.decode(b"\xff")


# ---- change-6: no common ancestor -------------------------------------------------


def test_a_merge_base_that_git_cannot_find_is_an_error(tmp_path: Path) -> None:
    """Acceptance (change-6): for two commits with no common ancestor, `merge_base` raises
    DeltaError. It does not give the base commit. `systemap delta` exits 2.
    """
    root = make(tmp_path / "repo", "python")
    git(root, "checkout", "-q", "--orphan", "other")
    commit(root, "other root")
    with pytest.raises(delta.DeltaError, match="common ancestor"):
        delta.merge_base(root, "main", "other")
    assert main(["--root", str(root), "delta", "--base", "main", "--head", "other"]) == 2


# ---- change-14: the memory of the tree reader --------------------------------------


def test_the_tree_reader_does_not_hold_a_large_blob_in_memory(tmp_path: Path) -> None:
    """Acceptance (change-14): `write_tree` writes a commit with a 32 MiB blob, and the
    peak memory that Python allocates during the call is less than 8 MiB.
    `bench/jev/tree_reader_memory.py` gives the time and the resident memory.
    """
    repo = tmp_path / "repo"
    (repo / "assets").mkdir(parents=True)
    (repo / "assets/data.bin").write_bytes(bytes(range(256)) * (1 << 17))
    git(repo, "init", "-q")
    sha = commit(repo, "blob")
    into = tmp_path / "into"
    into.mkdir()
    tracemalloc.start()
    try:
        delta_git.write_tree(repo, sha, into.resolve())
        _now, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert (into / "assets/data.bin").stat().st_size == 32 << 20
    assert peak < 8 << 20


# ---- change-20: one source comparison for each render -------------------------------


def test_a_render_with_nested_maps_parses_each_changed_file_once_for_each_side(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance (change-20): `systemap render --base HEAD~1` with three maps parses the
    public surface of each changed source file at most two times: one time for the base
    and one time for the head. `bench/jev/change_reuse.py` gives the time and the memory.
    """
    root = tmp_path
    write_tree(root, {**NESTED_TREE, "systemap.toml": NESTED_CONFIG, **NESTED_MODELS})
    assert main(["--root", str(root), "place"]) == 0
    assert main(["--root", str(root), "extract"]) == 0
    git(root, "init", "-q")
    commit(root, "base")
    changed = ("pkg/gateway/store.py", "pkg/style/cache.py", "pkg/reader.py")
    for rel in changed:
        path = root / rel
        path.write_text(path.read_text(encoding="utf-8") + "\n\ndef more() -> None:\n    pass\n")
    assert main(["--root", str(root), "extract"]) == 0
    commit(root, "head")
    assert len(nest.load(config.load(root)).maps) == 3
    calls: list[str] = []
    parse = extract.PythonLanguage.parse_surface

    def counted(self: extract.PythonLanguage, raw: str, path: str = "") -> dict[str, Any] | None:
        calls.append(path)
        return parse(self, raw, path)

    monkeypatch.setattr(extract.PythonLanguage, "parse_surface", counted)
    assert main(["--root", str(root), "render", "--base", "HEAD~1"]) == 0
    assert sorted(set(calls)) == sorted(changed)
    assert all(calls.count(rel) <= 2 for rel in changed), calls


# ---- change-19 and change-22: the history report -----------------------------------


def test_a_window_that_removes_a_crossing_import_is_a_change() -> None:
    """Acceptance (change-19): a window that only removes the crossing import A -> B has a
    size above 0. The report prints the removed crossing import.
    """
    before = trend.Sample(sha="a" * 40, crossings={("A", "B")})
    now = trend.Sample(sha="b" * 40)
    window = trend.between(before, now)
    assert window.size > 0
    lines = trend.report([window], Path("."), "1 year ago", 14, 5)
    assert "      removed crossing imports: A -> B" in lines


def test_the_report_names_only_the_commits_that_added_a_module(tmp_path: Path) -> None:
    """Acceptance (change-22): a window adds `pkg/new.py` in one commit and edits it in a
    later commit. The window gives only the commit that added the file.
    """
    root = make(tmp_path / "repo", "python")
    base = git(root, "rev-parse", "HEAD")
    (root / "pkg/new.py").write_text("X = 1\n", encoding="utf-8")
    commit(root, "add the new module")
    (root / "pkg/new.py").write_text("X = 2\n", encoding="utf-8")
    head = commit(root, "edit the new module")
    window = trend.Window(base=base, head=head, new_files=("pkg/new.py",))
    assert trend.with_causes(root, window).caused_by == ("add the new module",)


# ---- cli-15: the exit code of history for an unknown ref ---------------------------


def test_history_with_an_unknown_ref_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance (cli-15): `systemap history --ref does-not-exist` exits 2, as other
    revision errors do, and gives the correction on stderr.
    """
    root = make(tmp_path / "repo", "python")
    capsys.readouterr()
    assert main(["--root", str(root), "history", "--ref", "does-not-exist"]) == 2
    err = capsys.readouterr().err
    assert "does-not-exist" in err
    assert "Git can resolve" in err
