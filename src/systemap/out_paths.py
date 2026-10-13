"""The output path check keeps each configured output file in the output directory.

The configuration and the model give the names of the facts file, the pages, and the
figures. A name such as `../../x` or an absolute path can identify a file that is not in
the output directory. Each command examines the path before it writes the file. The
`--out` option of `systemap figure` is not a configured name. This check does not apply
to it.
"""

from __future__ import annotations

from pathlib import Path

from systemap import repo_files
from systemap.config import Config, ConfigError


def checked(cfg: Config, path: Path) -> Path:
    """Give the path if it is in the output directory. If it is not, give ConfigError."""
    return _inside(cfg.out_path, path, cfg.rel(path), cfg.out_dir)


def served(out: Path, name: str) -> Path:
    """Give the path of a file of `systemap live` if it is in its directory `out`.

    If the path is not in the directory, give ConfigError."""
    return _inside(out, out / name, name, str(out))


def _inside(out: Path, path: Path, shown: str, directory: str) -> Path:
    if not repo_files.inside(out, path):
        raise ConfigError(
            f"The output file {shown} is not in the output directory {directory}. "
            f"Correct the file name in the configuration or the model."
        )
    return path
