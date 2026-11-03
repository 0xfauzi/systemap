"""Tests for the two ratchet hooks in scripts/precommit (issue #94)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path, PureWindowsPath
from types import ModuleType

import pytest

HOOKS = Path(__file__).resolve().parents[1] / "scripts" / "precommit"
# The ruff in the project environment has the same version as the hook pin.
# Thus the tests do not download a tool.
LOCAL_RUFF = [sys.executable, "-m", "ruff"]


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, HOOKS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def git(repo: Path, *args: str) -> None:
    subprocess.run([*GIT, "-C", str(repo), *args], check=True, capture_output=True)


def make_repo(root: Path, rel: str, text: str) -> Path:
    git(root, "init", "-q")
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    git(root, "add", rel)
    git(root, "commit", "-q", "--no-verify", "-m", "start")
    return path


def branchy(name: str, count: int, indent: str = "    ") -> str:
    """A function with `count` decision points: cyclomatic `count + 1`."""
    body = "".join(f"{indent}    if x == {i}:\n{indent}        return {i}\n" for i in range(count))
    return f"{indent}def {name}(self, x):\n{body}{indent}    return -1\n"


def two_parsers(first: int, second: int) -> str:
    return "class A:\n" + branchy("parse", first) + "\n\nclass B:\n" + branchy("parse", second)


def test_ruff_failure_stops_the_cyclomatic_hook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = load("cyclomatic_ratchet")
    make_repo(tmp_path, "mod.py", two_parsers(2, 2))
    failing = "import sys; sys.stderr.write('error: no ruff'); sys.exit(2)"
    monkeypatch.setattr(hook, "RUFF", [sys.executable, "-c", failing])
    monkeypatch.chdir(tmp_path)
    assert hook.main(["mod.py"]) == 2


def test_missing_ruff_stops_the_cyclomatic_hook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = load("cyclomatic_ratchet")
    make_repo(tmp_path, "mod.py", two_parsers(2, 2))
    monkeypatch.setattr(hook, "RUFF", [str(tmp_path / "no-such-tool")])
    monkeypatch.chdir(tmp_path)
    assert hook.main(["mod.py"]) == 2


def test_unreadable_ruff_output_stops_the_cyclomatic_hook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = load("cyclomatic_ratchet")
    make_repo(tmp_path, "mod.py", two_parsers(2, 2))
    changed = "import sys; print('mod.py:1:1 something else'); sys.exit(1)"
    monkeypatch.setattr(hook, "RUFF", [sys.executable, "-c", changed])
    monkeypatch.chdir(tmp_path)
    assert hook.main(["mod.py"]) == 2


def test_a_file_without_rows_stops_the_cyclomatic_hook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = load("cyclomatic_ratchet")
    make_repo(tmp_path, "a.py", two_parsers(2, 2))
    (tmp_path / "b.py").write_text(two_parsers(2, 2))
    git(tmp_path, "add", "b.py")
    git(tmp_path, "commit", "-q", "--no-verify", "-m", "b")
    rows = "a.py:2:9: C901 `parse` is too complex (3 > 0)"
    only_a = f"import sys; print({rows!r}); sys.exit(1)"
    monkeypatch.setattr(hook, "RUFF", [sys.executable, "-c", only_a])
    monkeypatch.chdir(tmp_path)
    assert hook.main(["a.py", "b.py"]) == 2


def test_syntax_error_in_the_index_stops_the_cyclomatic_hook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = load("cyclomatic_ratchet")
    monkeypatch.setattr(hook, "RUFF", LOCAL_RUFF)
    make_repo(tmp_path, "good.py", two_parsers(2, 2))
    (tmp_path / "bad.py").write_text(branchy("run", 30, indent="") + "def broken(:\n")
    git(tmp_path, "add", "bad.py")
    monkeypatch.chdir(tmp_path)
    assert hook.main(["good.py", "bad.py"]) == 2


def test_syntax_error_at_head_does_not_stop_its_fix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = load("cyclomatic_ratchet")
    monkeypatch.setattr(hook, "RUFF", LOCAL_RUFF)
    path = make_repo(tmp_path, "mod.py", two_parsers(2, 2) + "def broken(:\n")
    path.write_text(two_parsers(2, 2))
    git(tmp_path, "add", "mod.py")
    monkeypatch.chdir(tmp_path)
    assert hook.main(["mod.py"]) == 0


def test_a_file_that_git_cannot_show_stops_the_cyclomatic_hook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = load("cyclomatic_ratchet")
    monkeypatch.setattr(hook, "RUFF", LOCAL_RUFF)
    make_repo(tmp_path, "mod.py", two_parsers(2, 2))
    (tmp_path / "untracked.py").write_text(two_parsers(2, 2))
    monkeypatch.chdir(tmp_path)
    assert hook.main(["untracked.py"]) == 2


def test_a_file_that_git_cannot_show_stops_the_length_hook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = load("file_length_ratchet")
    make_repo(tmp_path, "mod.py", "X = 1\n")
    (tmp_path / "untracked.py").write_text("X = 1\n")
    monkeypatch.chdir(tmp_path)
    assert hook.main(["untracked.py"]) == 2


def test_same_name_methods_are_measured_apart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = load("cyclomatic_ratchet")
    monkeypatch.setattr(hook, "RUFF", LOCAL_RUFF)
    path = make_repo(tmp_path, "mod.py", two_parsers(19, 1))
    path.write_text(two_parsers(19, 14))
    git(tmp_path, "add", "mod.py")
    monkeypatch.chdir(tmp_path)
    assert hook.main(["mod.py"]) == 1


def test_same_name_methods_in_a_dot_directory_are_measured_apart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = load("cyclomatic_ratchet")
    monkeypatch.setattr(hook, "RUFF", LOCAL_RUFF)
    path = make_repo(tmp_path, ".hooks/s/mod.py", two_parsers(19, 1))
    path.write_text(two_parsers(19, 14))
    git(tmp_path, "add", ".hooks/s/mod.py")
    monkeypatch.chdir(tmp_path)
    assert hook.main([".hooks/s/mod.py"]) == 1


def test_bare_names_on_both_sides_when_python_cannot_parse_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = load("cyclomatic_ratchet")
    monkeypatch.setattr(hook, "RUFF", LOCAL_RUFF)
    path = make_repo(tmp_path, "mod.py", "class A:\n" + branchy("run", 14))
    path.write_text("class A:\n" + branchy("run", 14))
    git(tmp_path, "add", "mod.py")
    real = hook.qualified_names

    def old_python(source: Path) -> dict[int, str] | None:
        # The index side stands for new syntax that this Python cannot parse.
        return None if source.parent.name == "index" else real(source)

    monkeypatch.setattr(hook, "qualified_names", old_python)
    monkeypatch.chdir(tmp_path)
    assert hook.main(["mod.py"]) == 0


def test_unchanged_same_name_methods_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hook = load("cyclomatic_ratchet")
    monkeypatch.setattr(hook, "RUFF", LOCAL_RUFF)
    path = make_repo(tmp_path, "mod.py", two_parsers(19, 1))
    path.write_text("# A new comment moves each line.\n" + two_parsers(19, 1))
    git(tmp_path, "add", "mod.py")
    monkeypatch.chdir(tmp_path)
    assert hook.main(["mod.py"]) == 0


@pytest.mark.parametrize("name", ["cyclomatic_ratchet", "file_length_ratchet"])
def test_git_paths_use_forward_slashes(name: str) -> None:
    hook = load(name)
    repo = PureWindowsPath("C:/work/repo")
    path = PureWindowsPath("C:/work/repo/src/pkg/mod.py")
    assert hook.git_path(path, repo) == "src/pkg/mod.py"
    assert hook.git_path(PureWindowsPath("D:/other/mod.py"), repo) is None
