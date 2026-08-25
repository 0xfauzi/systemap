"""The agent skill: the procedure a coding agent follows to map a repository.

The facts are mechanical and `systemap extract` reads them. The meaning
tier (which modules form a component, its plain name, what each edge
means, the journeys, the invariants) takes judgement. That judgement is
drafted by a coding agent following the skill and reviewed by a person,
which is why the skill ends by handing back the list of calls it made.

The skill is a directory: `SKILL.md` (when to use it, the loop, what to
hand back, the index of references) and `references/` (the schema, a
worked example, the layers, the journey and invariant method, the second
pass, the pitfalls), each read when the loop reaches it. It ships in the
package under `skill/`, so the wheel carries it and this module only
installs or prints it. `systemap init` installs the directory by default
and `systemap skill` reinstalls it; every file is overwritten on every
run and a reference the package no longer ships is removed, so an
upgrade of the package refreshes the whole directory.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

DEFAULT_DIR = ".claude/skills/systemap"
FILE_NAME = "SKILL.md"
REFERENCES = "references"


def files() -> dict[str, str]:
    """Every file of the skill, relative path -> text, SKILL.md first."""
    root = resources.files("systemap").joinpath("skill")
    out = {FILE_NAME: root.joinpath(FILE_NAME).read_text(encoding="utf-8")}
    refs = root.joinpath(REFERENCES)
    for entry in sorted(refs.iterdir(), key=lambda e: e.name):
        if entry.name.endswith(".md"):
            out[f"{REFERENCES}/{entry.name}"] = entry.read_text(encoding="utf-8")
    return out


def text() -> str:
    """SKILL.md, as shipped in the package."""
    return files()[FILE_NAME]


def write(directory: Path) -> Path:
    """Write the skill directory into `directory` and return SKILL.md's path.

    Every shipped file is written; a `.md` under `references/` that the
    package no longer ships is removed, so the installed directory is the
    shipped one and nothing else.
    """
    shipped = files()
    for rel, content in shipped.items():
        path = directory / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    for stale in (directory / REFERENCES).glob("*.md"):
        if f"{REFERENCES}/{stale.name}" not in shipped:
            stale.unlink()
    return directory / FILE_NAME
