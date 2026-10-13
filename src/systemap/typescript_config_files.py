"""The TypeScript configuration files are the files that the TypeScript adapter reads
for its settings.

They are package.json and tsconfig.json near the source folders, the package.json file
of the installed TypeScript package, and each tsconfig file that a tsconfig file names
in `extends` or `references`. An `extends` or `references` target can have a different
name, such as `tsconfig.base.json`. The live watcher watches these files. The digest
of the extraction inputs has only the values that extraction reads from these files.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from systemap import config, config_walk, repo_files
from systemap.typescript_config import (
    INPUT_KEYS,
    SOURCE_SKIP,
    _config_reference,
    _extends_references,
    _read_config,
    installed_major,
)

NAMES = ("package.json", "tsconfig.json")
# typescript_major reads the version of the installed TypeScript package.
TYPESCRIPT_PACKAGE = Path("node_modules", "typescript", "package.json")


def typescript_config_paths(root: Path, folders: Iterable[Path]) -> list[Path]:
    """Give the configuration files that the TypeScript adapter reads for the folders.

    A path can name a file that does not exist. The result does not include a file that
    a tsconfig file does not name.
    """
    near = config_walk.nearby(root, folders, NAMES, SOURCE_SKIP | config.OUTPUT_DIRS)
    found = dict.fromkeys([*near, root / TYPESCRIPT_PACKAGE])
    base = root.resolve()
    for start in (path for path in near if path.name == "tsconfig.json" and path.is_file()):
        for path in linked_configs(start, root):
            # The watcher does not watch a file outside the repository: extraction refuses it.
            if path.is_relative_to(base):
                found[root / path.relative_to(base)] = None
    return list(found)


def linked_configs(start: Path, root: Path) -> list[Path]:
    """Give the start file, the tsconfig files that it names in `extends` or `references`,
    and the files that those files name. Each path is resolved and occurs one time.

    A file that cannot be read names no file. Thus a file that is not valid JSON, or a
    cycle, does not stop the result. The function reads only regular files in the
    repository. It does not open a file outside the repository or a FIFO.
    """
    found: dict[Path, None] = {}
    queue = [start.resolve()]
    for current in queue:
        if current not in found:
            found[current] = None
            queue += _named(current, root)
    return list(found)


def _named(path: Path, root: Path) -> list[Path]:
    try:
        data = _read_config(path, root)
    except ValueError:
        return []
    return [*_extends_targets(data, path), *_reference_targets(data, path)]


def _extends_targets(data: dict[str, Any], path: Path) -> list[Path]:
    try:
        references = _extends_references(data, path)
    except ValueError:
        return []
    out: list[Path] = []
    for reference in references:
        try:
            out.append(_config_reference(path.parent, reference))
        except ValueError:
            # A missing relative target: a new file at this path changes the settings.
            if reference.startswith("."):
                name = reference if reference.endswith(".json") else reference + ".json"
                out.append((path.parent / name).resolve())
    return out


def _reference_targets(data: dict[str, Any], path: Path) -> list[Path]:
    """Give the `references` targets, also a target that does not exist, as tsc reads
    them: a path without `.json` names the tsconfig.json file in that folder."""
    references = data.get("references")
    out: list[Path] = []
    for reference in references if isinstance(references, list) else ():
        raw = reference.get("path") if isinstance(reference, dict) else None
        if isinstance(raw, str):
            target = path.parent / raw
            out.append((target if raw.endswith(".json") else target / "tsconfig.json").resolve())
    return out


# The keys of a tsconfig file that extraction reads (`_compiler_options` and
# `_project_config` in typescript_config). Other keys do not change the facts.
READ_KEYS = ("extends", "references", *INPUT_KEYS)
READ_OPTIONS = ("paths", "baseUrl", "rootDir", "rootDirs", "outDir", "composite")


def typescript_extraction_inputs(root: Path, folders: Iterable[Path]) -> dict[Path, bytes]:
    """Give each configuration file that extraction reads, with a stable text of the values
    that extraction reads from it.

    The installed TypeScript package gives only its major version. A tsconfig file gives
    the keys in READ_KEYS and READ_OPTIONS, without comments and text format. A
    package.json file of the repository gives its full text. A tsconfig file that cannot
    be read gives its full text. A file that is not present has no entry.
    """
    package = root / TYPESCRIPT_PACKAGE
    found: dict[Path, bytes] = {}
    for path in typescript_config_paths(root, folders):
        if not repo_files.present(path):
            continue
        if path == package:
            found[path] = _stable({"major": installed_major(root)})
        elif path.name == "package.json":
            found[path] = _full_text(path, root)
        else:
            found[path] = _tsconfig_values(path, root)
    return found


def _tsconfig_values(path: Path, root: Path) -> bytes:
    try:
        data = _read_config(path, root)
    except ValueError:
        return _full_text(path, root)
    options = data.get("compilerOptions")
    values = {key: data[key] for key in READ_KEYS if key in data}
    if isinstance(options, dict):
        values["compilerOptions"] = {key: options[key] for key in READ_OPTIONS if key in options}
    else:
        values["compilerOptions"] = options
    return _stable(values)


def _full_text(path: Path, root: Path) -> bytes:
    try:
        return repo_files.read_bytes(root, repo_files.relative(root, path))
    except OSError as exc:
        raise config.ConfigError(f"The parser could not read {path}: {exc}") from exc


def _stable(values: object) -> bytes:
    return json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
