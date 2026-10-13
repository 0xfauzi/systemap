"""The configured paths that the commands write must be in the repository.

The configuration gives the cache files (`[jev] cache`, `[openai] cache`, `[agent] cache`),
the output directory (`out_dir`), the model file (`model`), and the facts file
(`facts_file`, in the output directory). A pull request can change the configuration.
Then CI writes these files. An absolute path, or a path with a `..` part, names a file
that is not in the repository. These functions give a ValueError for such a path. The
configuration reader changes it to a ConfigError at load time.

A link out of the repository at a folder of a configured path is a different problem.
`file_write` and `nest` refuse it when a command reads or writes the file.
"""

from __future__ import annotations

from typing import Any

from systemap import repo_files

FACTS_FILE = "map.json"
# The configured paths below the repository root: (table, key). An empty table is the top.
WRITTEN = (
    ("", "out_dir"),
    ("", "model"),
    ("jev", "cache"),
    ("openai", "cache"),
    ("agent", "cache"),
)


def names(raw: dict[str, Any], where: str) -> dict[str, str]:
    """Refuse a written path out of the repository. Give the facts file name."""
    for table, key in WRITTEN:
        held = raw.get(table, {}) if table else raw
        value = held.get(key) if isinstance(held, dict) else None
        if isinstance(value, str) and value.strip() and not repo_files.plain(value.strip()):
            name = f"{table}.{key}" if table else key
            raise ValueError(
                f"{where}: {name} {value} is not in the repository. "
                "Give a path relative to the repository root, without a .. part."
            )
    return {"facts_file": facts_file(raw, where)}


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
