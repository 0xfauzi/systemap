"""The shipped skill: its worked example is a model that passes the check.

The skill is the document the agent reads instead of the package source,
so its example must be true. The test lifts the model out of
references/example.md, writes it beside the modules it names, and runs
the real check on it. The rest of the directory is checked for the words
it must and must not carry.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from conftest import SAMPLE_TREE, write_tree

from systemap import skill
from systemap.cli import main


def worked_example() -> str:
    blocks = re.findall(r"```python\n(.*?)```", skill.files()["references/example.md"], re.S)
    assert len(blocks) == 1, "the example carries exactly one python block: the worked model"
    return blocks[0]


def test_skill_front_matter_and_vocabulary() -> None:
    text = skill.text()
    assert text.startswith("---\nname: systemap\ndescription: ")
    for command in (
        "systemap extract",
        "systemap check",
        "systemap refresh",
        "systemap judgement",
        "systemap serve",
    ):
        assert command in text, command
    # The repository's own words, not "the README" alone; the answers live in
    # the configuration, in bulk where the reason is shared; both figures, the
    # Structure reading first.
    assert "its README, AGENTS.md, CLAUDE.md, docs/" in text
    assert "[judgement] answered" in text and "items = [...]" in text
    assert text.index("figures/structure.svg") < text.index("figures/system.svg")
    assert "open `docs/map/index.html`" not in text
    # Layout is the hard part and the skill says so: the draft step names the
    # layout reference, the render step runs describe before opening anything.
    assert text.index("references/layout.md") < text.index("**check**")
    assert "systemap describe" in text
    assert text.index("systemap describe") < text.index("systemap serve")
    assert "one to three words" in text
    second = skill.files()["references/second-pass.md"]
    assert "[judgement] answered" in second and "items = [...]" in second
    assert "systemap serve" in second
    assert "model sdk" in second
    assert "## The loop" in text
    assert "## What to hand back" in text
    assert "## References" in text
    # The loop says plainly that the first draft is wrong and the second pass is the point.
    assert "first draft will be wrong" in text
    assert "second pass is the point" in text
    for step in (
        "extract",
        "draft",
        "check",
        "judgement",
        "render",
        "second pass",
        "stop",
        "hand back",
    ):
        assert f"**{step}**" in text, step
    schema = skill.files()["references/schema.md"]
    for part in (
        "Container(",
        "Region(",
        "Component(",
        "Flow(",
        "Invariant(",
        "Layer(",
        "Meaning(",
        "Journey(",
        "Step(",
    ):
        assert part in schema, part
    whole = "\n".join(skill.files().values())
    assert "\u2014" not in whole, "no em dashes"
    # Nothing vendor-specific: the skill directory's path and the name of a
    # file a repository may keep its own words in are the two file names allowed.
    scrubbed = whole.replace(".claude/skills", "").replace("CLAUDE.md", "")
    assert "claude" not in scrubbed.lower()
    assert "codex" not in whole.lower()
    for word in ("planned", "tracker", "end state"):
        assert word not in whole, f"the skill no longer speaks of {word}"


def test_layers_reference_covers_the_agentic_kinds() -> None:
    layers = skill.files()["references/layers.md"]
    assert "## Agentic systems" in layers
    for word in ('kind="agent"', 'kind="tool"', 'kind="context"', "Structure", "System context"):
        assert word in layers, word
    method = skill.files()["references/journeys-and-invariants.md"]
    assert "one journey per agent's turn" in method
    assert "entry_points" in method


def test_worked_example_passes_check(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_tree(tmp_path, SAMPLE_TREE)
    write_tree(
        tmp_path,
        {
            "map/model.py": worked_example(),
            "systemap.toml": (
                "[coverage]\n"
                'ignore = [{ module = "pkg", reason = "the package root only marks the directory" }]\n'
            ),
        },
    )
    assert main(["--root", str(tmp_path), "refresh"]) == 0
    assert main(["--root", str(tmp_path), "check"]) == 0
    out = capsys.readouterr().out
    assert "coverage: 4/4 modules mapped, 1 ignored" in out
    assert "map layout: clean" in out
    assert "stale" not in out
    page = (tmp_path / "docs/map/index.html").read_text()
    for cid in ("User", "Reader", "Parser", "Ledger", "Writer"):
        assert f'"{cid}"' in page, cid


def test_write_installs_the_directory_and_removes_a_stale_reference(tmp_path: Path) -> None:
    target = tmp_path / "skills" / "systemap"
    (target / "references").mkdir(parents=True)
    (target / "references" / "old.md").write_text("gone in this version")
    path = skill.write(target)
    assert path == target / "SKILL.md"
    written = sorted(p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file())
    assert written == sorted(skill.files())
    assert not (target / "references" / "old.md").exists()
