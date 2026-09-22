"""The source-language boundary shared by extraction and change analysis.

A language adapter reads syntax. The rest of systemap reads the facts the
adapter produces, so a checker and a change view cannot disagree about what a
module exports, imports or tests.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol


class LanguageAdapter(Protocol):
    """Everything extraction and change analysis ask of source syntax."""

    name: str

    def source_paths(self, root: Path) -> Iterable[Path]: ...

    def module_of(self, path: Path, root: Path, name: str) -> str: ...

    def module_for_path(
        self, repo: Path, path: str, roots: list[tuple[Path, str]]
    ) -> str | None: ...

    def collect_module(
        self,
        path: Path,
        repo: Path,
        module: str,
        prefixes: frozenset[str],
        known: set[str],
        paths: dict[str, Path],
    ) -> dict[str, Any] | None: ...

    def internal_uses(
        self,
        raw: str,
        prefixes: set[str],
        known: set[str],
        module: str = "",
        is_package: bool = False,
        repo: Path | None = None,
        paths: dict[str, Path] | None = None,
    ) -> dict[str, set[str]]: ...

    def external_imports(
        self,
        raw: str,
        prefixes: set[str],
        module: str = "",
        repo: Path | None = None,
        paths: dict[str, Path] | None = None,
    ) -> list[str]: ...

    def collect_tests(
        self,
        repo: Path,
        tests_dirs: tuple[str, ...],
        prefixes: set[str],
        paths: dict[str, Path],
    ) -> dict[str, list[dict[str, Any]]]: ...

    def entry_points(
        self,
        repo: Path,
        prefixes: set[str],
        components: dict[str, Any],
        sources: dict[str, str],
    ) -> list[dict[str, str]]: ...

    def parse_surface(self, raw: str, path: str = "") -> dict[str, Any] | None: ...

    def test_names(self, raw: str, path: str = "") -> list[str]: ...

    def is_test_file(self, path: str, tests_dirs: tuple[str, ...]) -> bool: ...
