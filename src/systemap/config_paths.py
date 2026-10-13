"""The configured file names that must stay in the output directory.

The commands write the facts file only in the output directory (`out_paths`). A
`facts_file` name with a `..` part or an absolute path names a file outside it. A read of
that file does not read the facts of this map. These functions give a ValueError for such
a name. The configuration reader changes it to a ConfigError.
"""

from __future__ import annotations

from typing import Any

from systemap import repo_files

FACTS_FILE = "map.json"


def facts_file(raw: dict[str, Any], where: str) -> str:
    """Give the facts file name, relative to the output directory."""
    name = raw.get("facts_file", FACTS_FILE)
    if not isinstance(name, str):
        raise ValueError(f"{where}: facts_file must be a string.")
    if not repo_files.plain(name):
        raise ValueError(
            f"{where}: facts_file {name} is not in the output directory. "
            "Give a path relative to out_dir, without a .. part."
        )
    return name
