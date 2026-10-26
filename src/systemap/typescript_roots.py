"""The TypeScript root reader selects the package roots and the type-test patterns of a
repository. `init` writes them in systemap.toml, and a configuration without
`[package_roots]` uses the same roots.

The root rule, in this order:

1. The repository root must have a tsconfig.json file.
2. If each `include` entry of tsconfig.json names a folder, and one of these folders
   has TypeScript source, that folder is the root. The rule ignores test folders and
   type-test folders. An entry such as `src/**/*` names the folder `src`. An entry that
   names a file, such as `vite.config.ts`, or the tsconfig folder itself stops this step.
3. Otherwise, the root is `src` if it has TypeScript source, then the repository root.

A type-test folder has the name `test-d` (the default folder of tsd), or a name such as
`__tests_dts__` (`__test` or `__tests`, more text, and `__`). A type-test file has a
name that ends in `.test-d.ts` or `.spec-d.ts`, as tsd and Vitest typecheck use. The
folder that package.json names in `tsd.directory` is also a type-test folder.
"""

from __future__ import annotations

import itertools
import os
import re
from collections.abc import Iterator
from pathlib import Path, PurePosixPath

from systemap import config, file_names
from systemap.config import ConfigError
from systemap.typescript_config import (
    SOURCE_SKIP,
    SOURCE_SUFFIXES,
    load_typescript_config,
    package_json,
    source_files,
    typescript_name,
)

TSCONFIG = "tsconfig.json"
# The folder names of tests that a test runner finds without a setting: the configured
# defaults `tests` and `test`, and `__tests__` of Jest and Vitest.
TEST_FOLDERS = frozenset({*config.TEST_DIR_NAMES, "__tests__"})
TYPE_TEST_FOLDER = re.compile(r"test-d|__tests?_\w+__")
TYPE_TEST_FILES = ("test-d", "spec-d")
_GLOB = re.compile(r"[*?]")
EXAMPLE = '[package_roots]\n"packages/web/src" = "web"'


def discover_typescript_roots(root: Path) -> list[tuple[str, str]]:
    """This function selects the package root of the repository with the root rule."""
    if not (root / TSCONFIG).is_file():
        return []
    folder = _include_folder(root) or next(
        (candidate for candidate in (root / "src", root) if _has_source(candidate)), None
    )
    if folder is None:
        return []
    return [(folder.relative_to(root).as_posix() or ".", typescript_name(root))]


def _include_folder(root: Path) -> Path | None:
    """This function gives the one source folder that the `include` entries name, or None.

    A tsconfig.json file that the reader cannot read gives None. The extraction reports
    its problem later.
    """
    try:
        settings = load_typescript_config(root)
    except (ValueError, ConfigError):
        return None
    if settings.inputs is None or not settings.inputs.include or settings.config_dir is None:
        return None
    folders: set[Path] = set()
    for pattern in settings.inputs.include:
        folder = _fixed_folder(settings.config_dir, pattern)
        if folder is None:
            return None
        if not _test_folder(folder.name) and _has_source(folder):
            folders.add(folder)
    return next(iter(folders)) if len(folders) == 1 else None


def _fixed_folder(config_dir: Path, pattern: str) -> Path | None:
    """This function gives the folder before the first wildcard of an `include` entry.

    The result is None if the entry names a file, a missing folder, or the tsconfig
    folder, or a folder outside it.
    """
    parts = itertools.takewhile(lambda part: not _GLOB.search(part), PurePosixPath(pattern).parts)
    folder = Path(os.path.normpath(config_dir.joinpath(*parts)))
    inside = folder != config_dir and folder.is_relative_to(config_dir)
    return folder if inside and folder.is_dir() else None


def _has_source(folder: Path) -> bool:
    # The walk does not enter node_modules and the other SOURCE_SKIP folders.
    return (
        next((path for path in source_files(folder, SOURCE_SKIP) if path.is_file()), None)
        is not None
    )


def _test_folder(name: str) -> bool:
    return name in TEST_FOLDERS or bool(TYPE_TEST_FOLDER.fullmatch(name))


def type_test_patterns(root: Path) -> list[str]:
    """This function gives the `test_patterns` entries for the type tests in the
    repository: one entry for each type-test folder name and each type-test file kind.
    """
    out: dict[str, None] = {}
    configured = _tsd_directory(root)
    if configured:
        out[f"{configured}/**"] = None
    for names, files in _walk(root):
        folders = (name for name in names if TYPE_TEST_FOLDER.fullmatch(name))
        out.update(dict.fromkeys(f"**/{name}/**" for name in folders))
        kinds = (kind for kind in TYPE_TEST_FILES if _has_kind(files, kind))
        out.update(dict.fromkeys(f"**/*.{kind}.*" for kind in kinds))
    return sorted(out)


def _has_kind(files: list[str], kind: str) -> bool:
    suffixes = tuple(f".{kind}{suffix}" for suffix in SOURCE_SUFFIXES)
    return any(name.endswith(suffixes) for name in files)


def _walk(root: Path) -> Iterator[tuple[list[str], list[str]]]:
    """This function walks the repository. It does not enter skipped folders, folders
    with a name that starts with a period, or folders with a name that is not valid UTF-8.
    It does not give a file name that is not valid UTF-8."""
    skip = SOURCE_SKIP | config.SKIP_WALK
    for here, names, files in os.walk(root):
        found = file_names.folders(names)
        names[:] = sorted(name for name in found if name not in skip and name[0] != ".")
        yield names, file_names.files(root, here, files, None)


def _tsd_directory(root: Path) -> str:
    try:
        settings = package_json(root).get("tsd")
    except ConfigError:
        return ""
    folder = settings.get("directory") if isinstance(settings, dict) else None
    return folder.strip("/").removeprefix("./") if isinstance(folder, str) else ""


def missing_roots_message(root: Path) -> str:
    """This function gives the cause when the root rule selects no root, and the exact
    table to write in systemap.toml."""
    if not (root / TSCONFIG).is_file():
        cause = "The repository root has no tsconfig.json file."
    else:
        cause = "The repository has no .ts or .tsx source file outside node_modules."
    found = package_candidates(root)
    if found:
        table = "\n".join(["[package_roots]", *(f'"{path}" = "{name}"' for path, name in found)])
        where = (
            "These package folders have a tsconfig.json file. Keep only the packages of the system:"
        )
    else:
        table = EXAMPLE
        where = "Use this form:"
    return (
        f"No package roots are available. {cause} Set [package_roots] in systemap.toml "
        f'("path" = "module name"). {where}\n{table}'
    )


def package_candidates(root: Path) -> list[tuple[str, str]]:
    """This function gives the package root of each package folder below the repository
    root, with the root rule.

    A package folder has a tsconfig.json file. The search does not enter a package
    folder, a test folder, or a skipped folder.
    """
    out: list[tuple[str, str]] = []
    packages: list[Path] = []
    for folder in config.walk(root, lambda directory: False, config.CANDIDATE_DEPTH):
        inside = any(folder.is_relative_to(package) for package in packages)
        test = any(_test_folder(part) for part in folder.relative_to(root).parts)
        if inside or test or not (folder / TSCONFIG).is_file():
            continue
        packages.append(folder)
        try:
            roots = discover_typescript_roots(folder)
        except ConfigError:
            continue
        prefix = folder.relative_to(root).as_posix()
        out.extend((f"{prefix}/{path}".removesuffix("/."), name) for path, name in roots)
    return out
