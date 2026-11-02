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


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def make_repo(root: Path, rel: str, text: str) -> Path:
    git(root, "init", "-q")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "test")
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    git(root, "add", rel)
    git(root, "commit", "-q", "-m", "start")
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
    path = make_repo(tmp_path, "mod.py", two_parsers(2, 2))
    path.write_text(two_parsers(30, 2))
    git(tmp_path, "add", "mod.py")
    failing = "import sys; sys.stderr.write('error: no ruff'); sys.exit(2)"
    monkeypatch.setattr(hook, "RUFF", [sys.executable, "-c", failing])
    monkeypatch.chdir(tmp_path)
    assert hook.main(["mod.py"]) != 0


def test_unreadable_ruff_output_stops_the_cyclomatic_hook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = load("cyclomatic_ratchet")
    make_repo(tmp_path, "mod.py", two_parsers(2, 2))
    changed = "import sys; print('mod.py:1:1 something else'); sys.exit(1)"
    monkeypatch.setattr(hook, "RUFF", [sys.executable, "-c", changed])
    monkeypatch.chdir(tmp_path)
    assert hook.main(["mod.py"]) != 0


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
