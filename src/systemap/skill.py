"""The skill supplies the coding-agent procedure for map creation and maintenance.

The extractor supplies mechanical facts. The agent writes meaning from source evidence.
The skill specifies the writing rules of each writing profile for map names and descriptions.
The "plain" profile is the default. The "asd-ste100" profile adds ASD-STE100 Issue 9.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from systemap import repo_files
from systemap.config import ConfigError

DEFAULT_DIR = ".claude/skills/systemap"
FILE_NAME = "SKILL.md"
REFERENCES = "references"


def files() -> dict[str, str]:
    """This function indexes all packaged skill files by relative path, with SKILL.md
    first.
    """
    root = resources.files("systemap").joinpath("skill")
    out = {FILE_NAME: root.joinpath(FILE_NAME).read_text(encoding="utf-8")}
    refs = root.joinpath(REFERENCES)
    for entry in sorted(refs.iterdir(), key=lambda e: e.name):
        if entry.name.endswith(".md"):
            out[f"{REFERENCES}/{entry.name}"] = entry.read_text(encoding="utf-8")
    return out


def text() -> str:
    """This function reads the packaged SKILL.md."""
    return files()[FILE_NAME]


def check(directory: Path, root: Path) -> None:
    """Give ConfigError if a symbolic link puts a skill file outside the directory `root`.

    The command does this check before it writes a file."""
    for rel in (*files(), REFERENCES):
        path = directory / rel
        if not repo_files.inside(root, path):
            raise ConfigError(
                f"The skill file {path} is not in {root}, because of a symbolic link. Remove "
                f"the symbolic link, or give a different directory with systemap skill --dir."
            )


def write(directory: Path, root: Path | None = None) -> Path:
    """Write the packaged skill directory and return the SKILL.md path.

    Each file must be in `root` (the default is `directory`) after the resolution of
    symbolic links. Remove obsolete Markdown files from references so the installed skill
    agrees with the package.
    """
    check(directory, directory if root is None else root)
    shipped = files()
    for rel, content in shipped.items():
        path = directory / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    for stale in (directory / REFERENCES).glob("*.md"):
        if f"{REFERENCES}/{stale.name}" not in shipped:
            stale.unlink()
    return directory / FILE_NAME
