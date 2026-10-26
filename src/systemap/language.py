"""The language adapter gives the language-specific operations to the shared modules.

Each adapter reads the syntax of one source language. It writes facts with the same
meaning for each language. The shared modules read these facts, and they call this
protocol for each other language-specific operation. A shared module does not examine
a language name or a file suffix.

The repository part of the protocol does not read syntax. Configuration and setup use
it, so they do not load a parser.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

# The adapter for each value of the `language` key, as "module:object". The modules
# load only when a command asks for the adapter.
REPOSITORIES = {
    "python": "systemap.python_repo:PYTHON_REPOSITORY",
    "typescript": "systemap.typescript_repo:TYPESCRIPT_REPOSITORY",
}
ADAPTERS = {
    "python": "systemap.extract:PYTHON",
    "typescript": "systemap.typescript:TYPESCRIPT",
}
# The packages that an adapter needs and that an optional install supplies.
OPTIONAL = {"tree_sitter", "tree_sitter_typescript"}
# The evidence that an adapter finds for its language in a repository.
NO_SOURCE = 0
LOOSE_FILES = 1  # source files of the language, but no package root
CONFIG_ONLY = 2  # a configuration file of the language, without a source root
SOURCE = 3  # source files below a package root or a configured folder


class RepositoryAdapter(Protocol):
    """This protocol specifies the language operations that do not read syntax."""

    name: str
    # The suffixes of the source files that the adapter reads.
    source_suffixes: tuple[str, ...]
    # The folder names below a package root that hold no project source.
    skip_dirs: frozenset[str]
    # The import names that identify a model SDK or an agent framework.
    model_sdks: tuple[str, ...]
    # The character after which an import name continues inside the same package.
    import_separator: str
    # The root-relative configuration files. A change to the text of one of these files
    # can change the facts. The facts record a digest of each file that is present.
    config_files: tuple[str, ...]
    # The package extra that installs the adapter, or an empty string.
    install_extra: str
    # The comment above the package roots in a new systemap.toml.
    roots_note: str
    # The commented example for a repository without discovered package roots.
    roots_example: str

    def discover_roots(self, root: Path) -> list[tuple[str, str]]: ...

    def discover_test_patterns(self, root: Path) -> list[str]:
        """Give the `test_patterns` entries that init writes for test files that the
        default test rule does not find."""
        ...

    def detect(self, root: Path, folders: Iterable[Path] = ()) -> int:
        """Give the evidence for this language: NO_SOURCE, CONFIG_ONLY, or SOURCE."""
        ...

    def package_dir(self, directory: Path) -> bool: ...

    def config_paths(self, root: Path, folders: Sequence[Path]) -> list[Path]:
        """Give the configuration files that the adapter reads for the root and the source
        folders. A path can name a file that does not exist yet. The live watcher watches
        these files."""
        ...

    def extraction_inputs(self, root: Path, folders: Sequence[Path]) -> dict[Path, bytes]:
        """Give each configuration file that extraction reads and that is present, with a
        stable text of the values that extraction reads from it. A comment or a value that
        extraction does not read does not change the text. A file that cannot be read gives
        a ConfigError. The facts provenance has a digest of each text."""
        ...

    def root_name_problem(self, rel: str, name: str) -> str: ...

    def missing_roots_message(self, root: Path) -> str: ...

    def project_name(self, root: Path) -> str: ...

    def parser_version(self) -> str: ...

    def method_name(self, signature: str) -> str: ...


class LanguageAdapter(RepositoryAdapter, Protocol):
    """This protocol specifies the source operations for extraction and change analysis."""

    def source_paths(
        self,
        root: Path,
        repo: Path,
        tests_dirs: tuple[str, ...],
        test_patterns: tuple[str, ...],
    ) -> Iterable[Path]: ...

    def context(
        self,
        repo: Path,
        paths: dict[str, Path],
        tests_dirs: tuple[str, ...],
        test_patterns: tuple[str, ...],
    ) -> Any: ...

    def module_of(self, path: Path, root: Path, name: str) -> str: ...

    def package_of(self, path: Path, root: Path, name: str) -> str: ...

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
        context: Any,
    ) -> dict[str, Any] | None: ...

    def is_package_module(self, path: Path) -> bool: ...

    def empty_marker(self, record: Mapping[str, Any], raw: str) -> bool: ...

    def internal_uses(
        self,
        raw: str,
        prefixes: set[str],
        known: set[str],
        module: str = "",
        is_package: bool = False,
        repo: Path | None = None,
        paths: dict[str, Path] | None = None,
        context: Any = None,
    ) -> dict[str, set[str]]: ...

    def call_sites(
        self,
        raw: str,
        module: str,
        prefixes: set[str],
        known: set[str],
        components: Mapping[str, Mapping[str, Any]],
        is_package: bool = False,
        paths: dict[str, Path] | None = None,
        context: Any = None,
    ) -> list[dict[str, Any]] | None:
        """Give the `call_sites` records of one module, or None if they are not known."""
        ...

    def external_imports(
        self,
        raw: str,
        prefixes: set[str],
        module: str = "",
        repo: Path | None = None,
        paths: dict[str, Path] | None = None,
        context: Any = None,
    ) -> list[str]: ...

    def unresolved_imports(
        self,
        raw: str,
        prefixes: set[str],
        known: set[str],
        module: str,
        repo: Path,
        paths: dict[str, Path],
        context: Any,
    ) -> list[str]: ...

    def collect_tests(
        self,
        repo: Path,
        tests_dirs: tuple[str, ...],
        prefixes: set[str],
        paths: dict[str, Path],
        context: Any,
    ) -> dict[str, list[dict[str, Any]]]: ...

    def entry_points(
        self,
        repo: Path,
        prefixes: set[str],
        components: dict[str, Any],
        sources: dict[str, str],
        context: Any,
    ) -> tuple[list[dict[str, str]], list[dict[str, Any]]]: ...

    def entry_label(self, point: Mapping[str, str]) -> str: ...

    def compiler_record(self, context: Any, repo: Path) -> dict[str, str]: ...

    def extra_facts(self, context: Any, entry_issues: list[dict[str, Any]]) -> dict[str, Any]: ...

    def release(self, context: Any) -> None:
        """Remove the data that the adapter keeps during one extraction."""
        ...

    def parse_surface(self, raw: str, path: str = "") -> dict[str, Any] | None: ...

    def test_names(self, raw: str, path: str = "") -> list[str]: ...

    def is_test_file(
        self, path: str, tests_dirs: tuple[str, ...], test_patterns: tuple[str, ...] = ()
    ) -> bool: ...


class LanguageError(ValueError):
    """The configuration names a language without an adapter, or the adapter is not
    installed."""


# The language value when the configuration has no language key and the repository
# has no source of a known language. A command that needs the adapter then stops.
UNKNOWN = ""


def _choices() -> str:
    return " or ".join(f'"{name}"' for name in names())


def _set_the_key(problem: str) -> LanguageError:
    return LanguageError(f"{problem}. Set the language key to {_choices()} in systemap.toml.")


def names() -> tuple[str, ...]:
    """Give the values of the `language` key that have an adapter."""
    return tuple(REPOSITORIES)


def _load(table: dict[str, str], name: str) -> Any:
    if name == UNKNOWN:
        raise _set_the_key("No source of a known language is available")
    try:
        module, _, attribute = table[name].partition(":")
    except KeyError:
        raise LanguageError(f"unsupported language: {name}") from None
    return getattr(importlib.import_module(module), attribute)


def repository(name: str) -> RepositoryAdapter:
    """Give the repository operations of the language. They do not load a parser."""
    adapter: RepositoryAdapter = _load(REPOSITORIES, name)
    return adapter


def adapter(name: str) -> LanguageAdapter:
    """Give the full adapter of the language, with the parser."""
    try:
        found: LanguageAdapter = _load(ADAPTERS, name)
    except ModuleNotFoundError as exc:
        if exc.name not in OPTIONAL:
            raise
        extra = repository(name).install_extra
        raise LanguageError(
            f"The {name} adapter is not installed. Install systemap[{extra}]"
        ) from exc
    return found


def detect(root: Path, folders: Iterable[Path] = ()) -> str:
    """Give the language of the source in the repository.

    With folders, the adapter examines the source files in these folders. Without folders,
    the adapter finds its package roots. The language with the strongest evidence is the
    result. If two adapters find evidence of the same strength, LanguageError tells the
    maintainer to set the `language` key. If no adapter finds evidence, the result is
    UNKNOWN, and each command that needs the adapter stops with the same instruction.
    """
    folders = tuple(folders)
    evidence = {name: repository(name).detect(root, folders) for name in names()}
    strongest = max(evidence.values())
    found = [name for name, value in evidence.items() if value == strongest > NO_SOURCE]
    if len(found) > 1:
        raise _set_the_key(f"The source contains {' and '.join(found)} files")
    return found[0] if found else UNKNOWN
