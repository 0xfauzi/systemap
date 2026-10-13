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
    if not repo_files.inside(cfg.out_path, path):
        raise ConfigError(
            f"The output file {cfg.rel(path)} is not in the output directory {cfg.out_dir}. "
            f"Correct the file name in the configuration or the model."
        )
    return path
