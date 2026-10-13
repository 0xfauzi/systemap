"""The source text rules read source files, select source paths, and compare extraction inputs.

The same committed source must give the same facts on each computer. The extractor reads
text as Python and TypeScript read it. A digest of text does not change with the newline
form of a checkout. A path rule examines only the folders below a package root, never the
folders above the repository.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from systemap import repo_files
from systemap.typescript_config import SOURCE_SKIP, compiler_settings, load_typescript_config

# Below a Python package root or test directory, these folders hold no source of the
# project. The folders above the root are not examined.
PYTHON_SKIP = frozenset({".git", ".venv", "node_modules", "__pycache__", "build", "dist"})

# These provenance values can be different on two computers for the same commit: the
# interpreter version, the parser packages, and the compiler settings that installed npm
# packages supply. A difference in these values is a change only if the facts change.
# The other drift comparisons find a change of the facts.
LOCAL_INPUTS = ("parser", "compiler")


def read_problems(path: Path, repo: Path) -> tuple[str, list[str]]:
    """This function gives the source text and its read problems.

    The text is UTF-8, with or without a byte order mark, as Python and TypeScript read
    it. Universal newlines make CRLF text equal to LF text. Text that is not UTF-8 gives
    empty text and one problem. A file that `repo_files` refuses also gives empty text and
    one problem. A different OSError goes to the caller.
    """
    try:
        return repo_files.read_text(repo, repo_files.relative(repo, path), "utf-8-sig"), []
    except (UnicodeError, repo_files.RepoPathError) as exc:
        return "", [f"source could not be read: {repo_files.reason(exc)}"]


def text_digest(data: bytes) -> str:
    """This function hashes text bytes with CRLF and CR newlines changed to LF.

    LF text keeps the digest of its bytes, so the digests that LF checkouts recorded do
    not change.
    """
    return hashlib.sha256(data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()


def skipped(path: Path, base: Path, names: frozenset[str]) -> bool:
    """This function finds a skip name in the path parts below the base folder."""
    return any(part in names for part in path.relative_to(base).parts)


def python_paths(root: Path) -> Iterator[Path]:
    """This function lists the Python files below a package root, except skipped folders."""
    return (path for path in root.rglob("*.py") if not skipped(path, root, PYTHON_SKIP))


def ts_skipped(path: Path, base: Path, out_dir: Path | None) -> bool:
    """This function finds a file that tsc does not read: a file in node_modules, outDir,
    or a similar folder below the base folder. The folders above the base do not count.
    """
    if out_dir is not None and path.resolve().is_relative_to(out_dir):
        return True
    return skipped(path, base, SOURCE_SKIP)


def out_dir_below(base: Path, out_dir: Path | None) -> Path | None:
    """This function gives outDir if it is a folder below the base folder. An outDir that
    contains the base folder does not remove its source.
    """
    folder = base.resolve()
    if out_dir is None or out_dir == folder or not out_dir.is_relative_to(folder):
        return None
    return out_dir


def configured_out_dir(repo: Path, base: Path) -> Path | None:
    """This function gives the configured outDir below the base folder. The TypeScript
    context reports a configuration error.
    """
    try:
        out_dir = load_typescript_config(repo).out_dir
    except ValueError:
        return None
    return out_dir_below(base, out_dir)


def compiler_record(compiler: Any, repo: Path) -> dict[str, str]:
    """This function gives the digest of the TypeScript compiler settings.

    The compiler settings have a record that is separate from the configuration settings,
    because installed npm packages can change them.
    """
    if compiler is None:
        return {}
    settings = json.dumps(compiler_settings(compiler, repo), sort_keys=True)
    return {"compiler": hashlib.sha256(settings.encode()).hexdigest()}


def inputs_changed(stored: object, fresh: object) -> bool:
    """This function compares two provenance records without the values of one computer."""
    return _shared(stored) != _shared(fresh)


def _shared(provenance: object) -> object:
    if not isinstance(provenance, dict):
        return provenance
    return {key: value for key, value in provenance.items() if key not in LOCAL_INPUTS}
