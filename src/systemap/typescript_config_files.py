"""The TypeScript configuration files are the files that the TypeScript adapter reads
for its settings.

They are package.json and tsconfig.json near the source folders, the package.json file
of the installed TypeScript package, and each tsconfig file that a tsconfig file names
in `extends` or `references`. An `extends` or `references` target can have a different
name, such as `tsconfig.base.json`. The live watcher watches these files.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from systemap import config, config_walk
from systemap.typescript_config import (
    SOURCE_SKIP,
    _config_reference,
    _extends_references,
    _read_config,
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
