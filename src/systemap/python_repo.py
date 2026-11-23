"""The Python repository adapter gives the Python operations that do not extract facts.

It finds Python package roots, the project name, and the Python source files. It also
reads the name of a recorded method.
"""

from __future__ import annotations

import configparser
import fnmatch
import os
import re
import sys
import tomllib
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path, PurePath, PurePosixPath
from typing import Any

from systemap import config, config_walk, file_names, identifier, repo_files, tree_walk
from systemap.language import LOOSE_FILES, NO_SOURCE, SOURCE

# Below a Python package root or test directory, these folders hold no source of the
# project. The folders above the root are not examined.
PYTHON_SKIP = frozenset({".git", ".venv", "node_modules", "__pycache__", "build", "dist"})
PACKAGE_MARKER = "__init__.py"
PYPROJECT = "pyproject.toml"
SETUP_CFG = "setup.cfg"
# The method name in a recorded method header, such as `async def save(self)`. The
# name can contain Unicode letters and marks (`identifier.complete`).
METHOD = re.compile(r"(?:async )?def ([^\s(]+)\(")

# Import names that mark a module as calling a model or running an agent framework.
# Dotted where the namespace is shared. A cloud SDK that also reaches a model (boto3)
# is too coarse to list. Each name matches as a prefix of the import name.
MODEL_SDKS: tuple[str, ...] = (
    "anthropic",
    "openai",
    "google.generativeai",
    "google.adk",
    "litellm",
    "langchain",
    "langgraph",
    "llama_index",
    "mistralai",
    "cohere",
    "typesafe_sdk",
    "vertexai",
)


def skipped(path: Path, base: Path, names: frozenset[str]) -> bool:
    """Find a skip name in the path parts below the base folder."""
    return any(part in names for part in path.relative_to(base).parts)


def python_paths(
    root: Path, pattern: str = "*.py", refused: list[Path] | None = None
) -> Iterator[Path]:
    """List the Python files below a folder that match the file name pattern, in a stable
    order.

    The walk does not go into a folder whose name is in PYTHON_SKIP (result
    `followup-python-paths`). `fnmatch` gives the same case rule as `rglob`: on Windows,
    the name match ignores case. If a path below the root is not valid UTF-8, the walk
    does not give the file. If `refused` is a list, the walk adds the file to it."""
    for current, names, files in tree_walk.walk(root):
        names[:] = sorted(name for name in names if name not in PYTHON_SKIP)
        matched = (name for name in sorted(files) if fnmatch.fnmatch(name, pattern))
        for name in file_names.files(root, current, matched, refused):
            yield Path(current, name)


def package_dir(directory: Path) -> bool:
    """Find a directory that is a Python package: it has an `__init__.py` file."""
    return (directory / PACKAGE_MARKER).is_file()


def pyproject(root: Path) -> dict[str, Any]:
    """Read pyproject.toml, or give an empty table if it is missing.

    The function reads only a regular file in the root, with `repo_files`. A link out of
    the root, a FIFO, and a file that the function cannot read give a ConfigError with
    the path and the cause. They are not a missing file. Text that is not valid TOML
    gives a ConfigError with the parse error: an empty table would give a project without
    scripts, workspace members, or name, and that result is not known.
    """
    path = root / PYPROJECT
    if not repo_files.present(path):
        return {}
    try:
        text = repo_files.read_text(root, PYPROJECT, encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise config.ConfigError(f"The parser could not read {path}: {exc}") from exc
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise config.ConfigError(f"The parser could not read {path}: {exc}") from exc


def table(data: dict[str, Any], *keys: str) -> dict[str, Any]:
    """Give the table at the keys in the pyproject.toml data. A missing key gives an empty
    table.

    A value that is not a table gives a ConfigError with the key, such as `project` in
    `project = "name"`. An empty table would hide the incorrect setting."""
    out = data
    for index, key in enumerate(keys):
        found = out.get(key, {})
        if not isinstance(found, dict):
            dotted = ".".join(keys[: index + 1])
            raise config.ConfigError(f"{PYPROJECT}: the value of {dotted} must be a table.")
        out = found
    return out


def workspace_members(root: Path) -> list[Path]:
    """Find the directories that `[tool.uv.workspace] members` patterns select.

    The function gives only the directories in the resolved root. A pattern that is an
    absolute path or that contains `..` gives a ConfigError. A link to a folder out of the
    root gives no member. Thus no name of a folder out of the root goes into the facts."""
    members = table(pyproject(root), "tool", "uv", "workspace").get("members", [])
    if not isinstance(members, list):
        raise config.ConfigError(
            f"{PYPROJECT}: the value of tool.uv.workspace.members must be an array."
        )
    out: list[Path] = []
    for pattern in (pattern for pattern in members if isinstance(pattern, str)):
        for path in _member_paths(root, pattern):
            if path.is_dir() and path.resolve() != root.resolve() and path not in out:
                out.append(path)
    return out


def _member_paths(root: Path, pattern: str) -> list[Path]:
    """Give the paths in the root that one workspace member pattern selects.

    In Python 3.11, a `**` part in the pattern makes `Path.glob` call itself for each
    folder level. Thus a folder tree deeper than the recursion limit gives a
    RecursionError. This function changes that error into a ConfigError."""
    posix = PurePosixPath(pattern.replace("\\", "/"))
    if PurePath(pattern).is_absolute() or posix.is_absolute() or ".." in posix.parts:
        raise config.ConfigError(
            f"{PYPROJECT}: the workspace member pattern {pattern!r} must be a relative path "
            "in the repository. Remove an absolute path or a '..' part."
        )
    try:
        found = _valid_paths(root, root.glob(pattern))
    except (OSError, ValueError, NotImplementedError, RecursionError) as exc:
        raise config.ConfigError(
            f"{PYPROJECT}: the workspace member pattern {pattern!r} is not correct: {exc}"
        ) from exc
    return [path for path in found if repo_files.inside(root, path)]


def discover_roots(root: Path) -> list[tuple[str, str]]:
    """Find package directories with __init__.py, including src layouts and uv workspace
    members.

    When the packaging configuration names the directories of the packages (`declared_dirs`,
    for example `where = ["lib"]`), the packages of the repository root are those
    directories. Without them, the root and `src` hold the packages. A test directory
    (`config.TEST_DIR_NAMES`) is not a package root: the tests have their own setting."""
    found: list[tuple[str, str]] = []
    declared = declared_dirs(root)
    tops = declared or [root, root / "src"]
    members = [p for base in workspace_members(root) for p in (base, base / "src")]
    parents = [parent for parent in (*tops, *members) if parent.is_dir()]
    for child in (child for parent in parents for child in _valid_paths(root, parent.iterdir())):
        entry = (child.relative_to(root).as_posix(), child.name)
        if child.name in config.TEST_DIR_NAMES:
            continue
        # A link to a folder out of the root is not a package root of the repository.
        if _root_dir(child) and repo_files.inside(root, child) and entry not in found:
            found.append(entry)
    return found


def declared_dirs(root: Path) -> list[Path]:
    """Give the directories in the root that the packaging configuration names as the place
    of the packages: `where` of `[tool.setuptools.packages.find]`, the "" key of
    `[tool.setuptools] package-dir`, and the same keys in setup.cfg (`[options]` and
    `[options.packages.find]`). A value that names no directory in the root is not used.

    Without this, a library under `lib/` was not found, and the test and example packages
    of the root became the package roots."""
    data = pyproject(root)
    tools = table(data, "tool", "setuptools")
    names: list[object] = [
        *_listed(table(data, "tool", "setuptools", "packages", "find").get("where"))
    ]
    names.append(_mapping(tools.get("package-dir")).get(""))
    names.extend(_setup_cfg(root))
    out: list[Path] = []
    for name in (n.strip() for n in names if isinstance(n, str) and n.strip() not in ("", ".")):
        path = root / name
        if (
            ".." not in PurePosixPath(name).parts
            and path.is_dir()
            and repo_files.inside(root, path)
        ):
            if path not in out:
                out.append(path)
    return out


def _listed(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else [value] if isinstance(value, str) else []


def _mapping(value: object) -> dict[str, object]:
    return {str(k): v for k, v in value.items()} if isinstance(value, dict) else {}


def _setup_cfg(root: Path) -> list[str]:
    """Give the package directories of setup.cfg: `[options] package_dir` with the "" key
    (`= lib`), and `[options.packages.find] where`. A file that cannot be read gives none."""
    parser = configparser.ConfigParser(interpolation=None)
    if not repo_files.present(root / SETUP_CFG):
        return []
    try:
        parser.read_string(repo_files.read_text(root, SETUP_CFG, encoding="utf-8-sig"))
    except (OSError, UnicodeError, configparser.Error):
        return []
    out = [parser.get("options.packages.find", "where", fallback="")]
    for line in parser.get("options", "package_dir", fallback="").splitlines():
        key, eq, value = line.partition("=")
        if eq and not key.strip():
            out.append(value)
    return out


def _valid_paths(root: Path, paths: Iterable[Path]) -> list[Path]:
    """Sort the paths. Do not give a path whose part below the root is not valid UTF-8."""
    return sorted(path for path in paths if file_names.valid(os.path.relpath(path, root)))


def _root_dir(child: Path) -> bool:
    if not child.is_dir() or config.skipped(child, config.SKIP_DIRS, package_dir):
        return False
    return package_dir(child)


def candidate_packages(root: Path, depth: int = config.CANDIDATE_DEPTH) -> list[str]:
    """List the relative package-directory paths within the depth, for a missing-root
    diagnostic."""
    return [
        d.relative_to(root).as_posix()
        for d in config.walk(root, package_dir, depth)
        if package_dir(d)
    ]


def _loose_files(root: Path) -> bool:
    """Find a .py file within the candidate depth, outside the skipped directories."""
    folders = [root, *config.walk(root, package_dir, config.CANDIDATE_DEPTH)]
    return any(next(folder.glob("*.py"), None) for folder in folders)


class PythonRepository:
    """Give the Python operations that do not extract facts."""

    name = "python"
    source_suffixes: tuple[str, ...] = (".py",)
    skip_dirs = PYTHON_SKIP
    model_sdks = MODEL_SDKS
    # A Python import name continues after a dot: `google.adk.tools` is in `google.adk`.
    import_separator = "."
    config_files: tuple[str, ...] = (PYPROJECT,)
    install_extra = ""
    roots_note = (
        '# Package roots use "path" = "import name".\n'
        "# Without explicit roots, the extractor finds top-level Python packages\n"
        "# in the directories that the packaging configuration names (for example\n"
        '# where = ["lib"]), else in the repository and src, and in its uv workspace\n'
        "# members. A test directory is not a package root."
    )
    roots_example = '# [package_roots]\n# "src/mypackage" = "mypackage"'

    def discover_roots(self, root: Path) -> list[tuple[str, str]]:
        return discover_roots(root)

    def discover_test_patterns(self, root: Path) -> list[str]:
        """The Python test rule finds each test file without a pattern."""
        del root
        return []

    def detect(self, root: Path, folders: Iterable[Path] = ()) -> int:
        """Find Python source: a package root, or a .py file in a configured folder.

        Python files without a package root are the weakest evidence."""
        folders = tuple(folders)
        if folders:
            found = any(
                next(iter(python_paths(folder)), None) for folder in folders if folder.is_dir()
            )
            return SOURCE if found else NO_SOURCE
        if discover_roots(root):
            return SOURCE
        return LOOSE_FILES if _loose_files(root) else NO_SOURCE

    def package_dir(self, directory: Path) -> bool:
        return package_dir(directory)

    def config_paths(self, root: Path, folders: Sequence[Path]) -> list[Path]:
        """Give pyproject.toml at the root, below each folder, and between each folder and
        the root."""
        return config_walk.nearby(
            root, folders, self.config_files, PYTHON_SKIP | config.OUTPUT_DIRS
        )

    def extraction_inputs(self, root: Path, folders: Sequence[Path]) -> dict[Path, bytes]:
        """Give the full text of the root pyproject.toml. Extraction does not read a
        different pyproject.toml file, also not the file of a uv workspace member."""
        del folders
        path = root / PYPROJECT
        if not repo_files.present(path):
            return {}
        try:
            return {path: repo_files.read_bytes(root, PYPROJECT)}
        except OSError as exc:
            raise config.ConfigError(f"The parser could not read {path}: {exc}") from exc

    def root_name_problem(self, rel: str, name: str) -> str:
        if "/" not in name:
            return ""
        return (
            f"The package root {rel} has the import name {name}. A Python import name cannot "
            f"contain a slash."
        )

    def missing_roots_message(self, root: Path) -> str:
        found = candidate_packages(root)
        where = (
            "Directories with an __init__.py: " + ", ".join(found)
            if found
            else f"No directory has an __init__.py within {config.CANDIDATE_DEPTH} levels of "
            "the root."
        )
        return (
            f'No package roots are available. Set [package_roots] in systemap.toml ("path" '
            f'= "import name"). {where}'
        )

    def project_name(self, root: Path) -> str:
        name = table(pyproject(root), "project").get("name")
        return name.strip() if isinstance(name, str) else ""

    def parser_version(self) -> str:
        # CPython patch releases share a grammar. A minor release can change the AST.
        return f"{sys.version_info.major}.{sys.version_info.minor}"

    def method_name(self, signature: str) -> str:
        found = METHOD.match(signature)
        return found.group(1) if found and identifier.complete(found.group(1)) else ""


PYTHON_REPOSITORY = PythonRepository()
