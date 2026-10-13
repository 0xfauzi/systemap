"""The Python repository adapter gives the Python operations that do not extract facts.

It finds Python package roots, the project name, and the Python source files. It also
reads the name of a recorded method.
"""

from __future__ import annotations

import fnmatch
import os
import re
import sys
import tomllib
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Any

from systemap import config, config_walk, identifier
from systemap.language import LOOSE_FILES, NO_SOURCE, SOURCE

# Below a Python package root or test directory, these folders hold no source of the
# project. The folders above the root are not examined.
PYTHON_SKIP = frozenset({".git", ".venv", "node_modules", "__pycache__", "build", "dist"})
PACKAGE_MARKER = "__init__.py"
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


def python_paths(root: Path, pattern: str = "*.py") -> Iterator[Path]:
    """List the Python files below a folder that match the file name pattern, in a stable
    order.

    The walk does not go into a folder whose name is in PYTHON_SKIP (result
    `followup-python-paths`). `fnmatch` gives the same case rule as `rglob`: on Windows,
    the name match ignores case."""
    for current, names, files in os.walk(root):
        names[:] = sorted(name for name in names if name not in PYTHON_SKIP)
        for name in sorted(files):
            if fnmatch.fnmatch(name, pattern):
                yield Path(current, name)


def package_dir(directory: Path) -> bool:
    """Find a directory that is a Python package: it has an `__init__.py` file."""
    return (directory / PACKAGE_MARKER).is_file()


def pyproject(root: Path) -> dict[str, Any]:
    """Read pyproject.toml, or give an empty table if it is missing or not valid."""
    path = root / "pyproject.toml"
    if not path.is_file():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def workspace_members(root: Path) -> list[Path]:
    """Find the directories that `[tool.uv.workspace] members` patterns select."""
    workspace = pyproject(root).get("tool", {}).get("uv", {}).get("workspace", {})
    members = workspace.get("members", []) if isinstance(workspace, dict) else []
    patterns = [pattern for pattern in members if isinstance(pattern, str)]
    out: list[Path] = []
    for path in (path for pattern in patterns for path in sorted(root.glob(pattern))):
        if path.is_dir() and path.resolve() != root.resolve() and path not in out:
            out.append(path)
    return out


def discover_roots(root: Path) -> list[tuple[str, str]]:
    """Find package directories with __init__.py, including src layouts and uv workspace
    members."""
    found: list[tuple[str, str]] = []
    parents = [
        parent
        for base in (root, *workspace_members(root))
        for parent in (base, base / "src")
        if parent.is_dir()
    ]
    for child in (child for parent in parents for child in sorted(parent.iterdir())):
        entry = (child.relative_to(root).as_posix(), child.name)
        if _root_dir(child) and entry not in found:
            found.append(entry)
    return found


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
    config_files: tuple[str, ...] = ("pyproject.toml",)
    install_extra = ""
    roots_note = (
        '# Package roots use "path" = "import name".\n'
        "# Without explicit roots, the extractor finds top-level Python packages\n"
        "# in the repository and its uv workspace members."
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
        project = pyproject(root).get("project", {})
        name = project.get("name") if isinstance(project, dict) else None
        return name.strip() if isinstance(name, str) else ""

    def parser_version(self) -> str:
        # CPython patch releases share a grammar. A minor release can change the AST.
        return f"{sys.version_info.major}.{sys.version_info.minor}"

    def method_name(self, signature: str) -> str:
        found = METHOD.match(signature)
        return found.group(1) if found and identifier.complete(found.group(1)) else ""


PYTHON_REPOSITORY = PythonRepository()
