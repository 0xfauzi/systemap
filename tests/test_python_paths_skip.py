"""The Python file list does not enter node_modules (result `followup-python-paths`).

Before this change, `python_repo.python_paths` used `rglob`. Thus it read each folder in
node_modules, .venv, and the other skipped folders, and only then removed their files.

Acceptance, written before the change:

- `python_paths` and `PythonRepository.detect` with folders open no folder below
  node_modules, .git, .venv, __pycache__, build, or dist. An audit hook records each
  folder that `os.scandir` and `os.listdir` open.
- The results do not change: a Python file in a skipped folder is not in the list, and
  a Python file outside the skipped folders is in the list.
- `bench/python_paths.py`: for each measured call, the ratio of the median time with
  40,000 files in node_modules to the median time without them is 1.2 or less.

Acceptance for `python_tests.test_files`, written before its change: the same three
values. The walk of a test folder opens no folder with a `PYTHON_SKIP` name, the list
and its order do not change, and the `test_files` ratio in `bench/python_paths.py` is
1.2 or less.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree

from systemap import python_tests
from systemap.language import NO_SOURCE, SOURCE
from systemap.python_repo import PYTHON_REPOSITORY, PYTHON_SKIP, python_paths

SKIPPED = {f"{name}/pkg/deep/x.py": "X = 1\n" for name in sorted(PYTHON_SKIP)}
_OPENED: list[str] = []
_ACTIVE = [False]


def _hook(event: str, args: tuple[Any, ...]) -> None:
    if _ACTIVE[0] and event in ("os.scandir", "os.listdir") and args:
        _OPENED.append(os.fspath(args[0]) if args[0] is not None else "")


sys.addaudithook(_hook)

Record = Callable[[Callable[[], object]], tuple[object, list[str]]]


@pytest.fixture
def opened() -> Iterator[Record]:
    """Give a function that operates a call and gives its result and the opened folders."""

    def record(call: Callable[[], object]) -> tuple[object, list[str]]:
        _OPENED.clear()
        _ACTIVE[0] = True
        try:
            result = call()
        finally:
            _ACTIVE[0] = False
        return result, list(_OPENED)

    yield record
    _ACTIVE[0] = False


def _skipped_folders(paths: list[str], base: Path) -> list[str]:
    """Give the opened folders that have a skip name below the base folder."""
    return [path for path in paths if PYTHON_SKIP & set(Path(path).relative_to(base).parts)]


def test_the_file_list_does_not_enter_the_skipped_folders(tmp_path: Path, opened: Record) -> None:
    write_tree(
        tmp_path,
        {"__init__.py": "", "a.py": "", "sub/__init__.py": "", "sub/b.py": "", **SKIPPED},
    )
    found, folders = opened(
        lambda: sorted(path.relative_to(tmp_path).as_posix() for path in python_paths(tmp_path))
    )
    assert found == ["__init__.py", "a.py", "sub/__init__.py", "sub/b.py"]
    assert folders and not _skipped_folders(folders, tmp_path)


def test_detection_with_folders_does_not_enter_the_skipped_folders(
    tmp_path: Path, opened: Record
) -> None:
    write_tree(tmp_path, {"empty/README.md": "", "full/lib/c.py": ""})
    write_tree(tmp_path / "empty", SKIPPED)
    write_tree(tmp_path / "full", SKIPPED)
    evidence, folders = opened(lambda: PYTHON_REPOSITORY.detect(tmp_path, [tmp_path / "empty"]))
    assert evidence == NO_SOURCE
    assert folders and not _skipped_folders(folders, tmp_path)
    evidence, folders = opened(lambda: PYTHON_REPOSITORY.detect(tmp_path, [tmp_path / "full"]))
    assert evidence == SOURCE
    assert not _skipped_folders(folders, tmp_path)


def test_a_folder_with_a_python_suffix_is_not_a_file(tmp_path: Path) -> None:
    """A folder named `x.py` is not a Python file. Its Python files are in the list."""
    write_tree(tmp_path, {"x.py/y.py": ""})
    assert [path.relative_to(tmp_path).as_posix() for path in python_paths(tmp_path)] == [
        "x.py/y.py"
    ]


def test_the_test_file_list_does_not_enter_the_skipped_folders(
    tmp_path: Path, opened: Record
) -> None:
    """The order is the sorted order of the paths, as before the change."""
    tests = {"tests/test_b.py": "", "tests/a/test_x.py": "", "tests/a/helper.py": ""}
    write_tree(tmp_path, tests)
    write_tree(tmp_path / "tests", {k.replace("x.py", "test_x.py"): "" for k in SKIPPED})
    found, folders = opened(
        lambda: [
            path.relative_to(tmp_path).as_posix()
            for path in python_tests.test_files(tmp_path, ("tests",), (), [])
        ]
    )
    assert found == ["tests/a/test_x.py", "tests/test_b.py"]
    assert folders and not _skipped_folders(folders, tmp_path)
