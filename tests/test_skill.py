"""The shipped skill: its worked example is a model that passes the check.

The skill is the document the agent reads instead of the package source,
so its example must be true. The test lifts the model out of the markdown,
writes it beside the modules it names, and runs the real check on it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from conftest import SAMPLE_TREE, write_tree

from systemap import skill
from systemap.cli import main


def worked_example() -> str:
    blocks = re.findall(r"```python\n(.*?)```", skill.text(), re.S)
    assert len(blocks) == 1, "the skill carries exactly one python block: the worked example"
    return blocks[0]


def test_skill_front_matter_and_vocabulary() -> None:
    text = skill.text()
    assert text.startswith("---\nname: systemap\ndescription: ")
    for command in ("systemap extract", "systemap check", "systemap refresh", "systemap judgement"):
        assert command in text, command
    assert "## What to hand back" in text
    assert "## The schema" in text
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
        assert part in text, part
    assert "\u2014" not in text, "no em dashes"
    assert "claude" not in text.lower().replace(".claude/skills", "")
    assert "codex" not in text.lower()


def test_worked_example_passes_check(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_tree(tmp_path, SAMPLE_TREE)
    write_tree(
        tmp_path,
        {
            "map/model.py": worked_example(),
            "systemap.toml": (
                'issue_url = "https://example.invalid/issues/{n}"\n'
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
    for cid in ("User", "Reader", "Parser", "Planner", "Ledger", "Writer"):
        assert f'"{cid}"' in page, cid
