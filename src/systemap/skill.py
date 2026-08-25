"""The agent skill: the procedure a coding agent follows to map a repository.

The facts are mechanical and `systemap extract` reads them. The meaning
tier (which modules form a component, its plain name, what each edge
means, the layers, the journeys, the invariants) takes judgement. That
judgement is drafted by a coding agent following the skill and reviewed
by a person, which is why the skill ends by handing back the list of
calls it made.

The text lives in the package as `skill/SKILL.md`, so the wheel carries
it and this module only installs or prints it. `systemap init` installs it
by default and `systemap skill` reinstalls it; the file is overwritten on
every run, so an upgrade of the package refreshes it.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

DEFAULT_DIR = ".claude/skills/systemap"
FILE_NAME = "SKILL.md"


def text() -> str:
    """The skill, as shipped in the package."""
    return resources.files("systemap").joinpath("skill", FILE_NAME).read_text(encoding="utf-8")


def write(directory: Path) -> Path:
    """Write SKILL.md into `directory`, creating it, and return the file's path."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / FILE_NAME
    path.write_text(text(), encoding="utf-8")
    return path
