"""TypeScript language detection does not enter node_modules (result `followup-detect`).

Before this change, `TypeScriptRepository.detect` and `discover_typescript_roots` used
`rglob`. Thus they read each folder in node_modules and only then removed its files.

Acceptance, written before the change:

- `detect` without folders, `detect` with folders, and `discover_typescript_roots` open
  no folder below node_modules, .git, or .venv. An audit hook records each folder that
  `os.scandir` and `os.listdir` open.
- The results do not change: a source file in node_modules is not source, and a source
  file outside the skipped folders is source.
- `bench/typescript_detect.py`: for each measured call, the median time with 40,000
  files in node_modules is at most 1.2 times the median time without them.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree

from systemap.language import CONFIG_ONLY, NO_SOURCE, SOURCE
from systemap.typescript_config import discover_typescript_roots
from systemap.typescript_repo import TYPESCRIPT_REPOSITORY

SKIPPED = {
    "node_modules/pkg/lib/index.ts": "export const x = 1;\n",
    "node_modules/pkg/deep/more/index.ts": "export const x = 1;\n",
    ".venv/lib/x.ts": "export const x = 1;\n",
    ".git/hooks/x.ts": "export const x = 1;\n",
}
_OPENED: list[str] = []
_ACTIVE = [False]


def _hook(event: str, args: tuple[Any, ...]) -> None:
    if _ACTIVE[0] and event in ("os.scandir", "os.listdir") and args:
        _OPENED.append(os.fspath(args[0]) if args[0] is not None else "")


sys.addaudithook(_hook)


@pytest.fixture
def opened() -> Iterator[Callable[[Callable[[], object]], tuple[object, list[str]]]]:
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


def _skipped_folders(paths: list[str]) -> list[str]:
    names = {"node_modules", ".venv", ".git"}
    return [path for path in paths if names & set(Path(path).parts)]


def test_detection_without_source_does_not_enter_node_modules(
    tmp_path: Path, opened: Callable[[Callable[[], object]], tuple[object, list[str]]]
) -> None:
    write_tree(tmp_path, {"tsconfig.json": "{}", "lib/index.js": "", **SKIPPED})
    roots, folders = opened(lambda: discover_typescript_roots(tmp_path))
    assert roots == []
    assert folders and not _skipped_folders(folders)
    evidence, folders = opened(lambda: TYPESCRIPT_REPOSITORY.detect(tmp_path))
    assert evidence == CONFIG_ONLY
    assert folders and not _skipped_folders(folders)
    evidence, folders = opened(lambda: TYPESCRIPT_REPOSITORY.detect(tmp_path, [tmp_path]))
    assert evidence == NO_SOURCE
    assert folders and not _skipped_folders(folders)


def test_detection_finds_source_outside_the_skipped_folders(
    tmp_path: Path, opened: Callable[[Callable[[], object]], tuple[object, list[str]]]
) -> None:
    write_tree(
        tmp_path,
        {
            "tsconfig.json": "{}",
            "lib/types.d.ts": "export type T = 1;\n",
            "lib/deep/main.ts": "export const m = 1;\n",
            **SKIPPED,
        },
    )
    roots, folders = opened(lambda: discover_typescript_roots(tmp_path))
    assert roots == [(".", tmp_path.name)]
    assert not _skipped_folders(folders)
    evidence, folders = opened(lambda: TYPESCRIPT_REPOSITORY.detect(tmp_path, [tmp_path]))
    assert evidence == SOURCE
    assert not _skipped_folders(folders)
