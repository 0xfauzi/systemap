"""The skill supplies the coding-agent procedure for map creation and maintenance.

The extractor supplies mechanical facts. The agent writes meaning from source evidence.
The skill specifies ASD-STE100 Issue 9 for map names, descriptions, and documentation.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

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


def write(directory: Path) -> Path:
    """Write the packaged skill directory and return the SKILL.md path.

    Remove obsolete Markdown files from references so the installed skill agrees with
    the package.
    """
    shipped = files()
    for rel, content in shipped.items():
        path = directory / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    for stale in (directory / REFERENCES).glob("*.md"):
        if f"{REFERENCES}/{stale.name}" not in shipped:
            stale.unlink()
    return directory / FILE_NAME
