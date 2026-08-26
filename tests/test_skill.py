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
    assert "[judgement] answered" in text and 'items = ["<line>", ...]' in text
    assert text.index("figures/structure.svg") < text.index("figures/system.svg")
    assert "open `docs/map/index.html`" not in text
    # Layout is the hard part and the skill says so: the draft step names the
    # layout reference, the render step runs describe before opening anything.
    assert text.index("references/layout.md") < text.index("**check**")
    assert "systemap describe" in text
    assert text.index("systemap describe") < text.index("systemap serve")
    assert "one to three words" in text
    second = skill.files()["references/second-pass.md"]
    assert "[judgement] answered" in second
    # Every answer form, with an example each: the exact line, several,
    # a crossing pair, a kind, a model sdk import.
    for form in ("{ item = ", "{ items = [", '{ crossing = ["', '{ kind = "', '{ module_sdk = "'):
        assert form in second, form
    # The count of forms the text states is the count of rows the block shows.
    block = re.search(r"```toml\n(.*?)```", second, re.S)
    assert block is not None
    rows = re.findall(r"^\s+\{ (\w+) = ", block.group(1), re.M)
    assert rows == [
        "item",
        "items",
        "crossing",
        "crossing_into",
        "crossing_from",
        "kind",
        "module_sdk",
    ]
    assert "Seven forms" in second and len(rows) == 7
    # The crossing-import line as the judgement prints it, and the flags.
    assert "`crossing import: P\n   imports Q in N modules and no flow joins them`" in second
    assert "systemap judgement --verbose" in second and '--kind "crossing import"' in second
    pitfalls = skill.files()["references/pitfalls.md"]
    assert "outside the\nrepository (for example /tmp)" in pitfalls
    assert "every CI command the repository runs, not only pre-commit" in pitfalls
    assert "by the repository's own rule" in second
    assert "that definition wins" in second
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


def test_step_four_lists_every_answer_form_and_every_line_kind() -> None:
    """F20: the forms with their constraints, and the seven kinds, one sentence each."""
    text = skill.text()
    step = text[text.index("4. **judgement**") : text.index("5. **render**")]
    for form in (
        '- `item = "<line>"`: the exact line',
        '- `items = ["<line>", ...]`: several exact lines',
        '- `crossing = ["A", "B", ...]`: every crossing import between any two',
        '- `crossing_into = "A"`: every crossing import into A; one id.',
        '- `crossing_from = "A"`: every crossing import out of A; one id.',
        '- `kind = "<kind>"`: every line of one kind',
        '- `module_sdk = "<import>"`: every model sdk line',
    ):
        assert form in step, form
    assert "two or more different ids" in step and "not empty" in step
    from systemap.config import LINE_KINDS

    rows = [line for line in step.splitlines() if line.strip().startswith("| `")]
    assert [row.split("`")[1] for row in rows] == list(LINE_KINDS)
    mis_fold = next(row for row in rows if "possible mis-fold" in row)
    assert "shares no word with the card's id" in mis_fold
    assert "folded into the wrong card" in mis_fold
    assert "move it to the card whose purpose it serves" in mis_fold
    for row in rows:
        assert row.count("|") == 4, row


def test_the_document_reread_is_bounded() -> None:
    """F19: one pass over what the repository points a newcomer at, then stop."""
    text = skill.text()
    for step in ("6. **second pass**", "7. **stop**"):
        assert step in text
    second_pass = text[text.index("6. **second pass**") : text.index("8. **hand back**")]
    assert "one pass over what the\n   repository points a newcomer at" in second_pass
    assert (
        "README, AGENTS.md, CLAUDE.md, a docs\n   index or the first level of docs/" in second_pass
    )
    assert "govern parts that are not in the tree" in second_pass
    assert "the documents left unread govern nothing in the\n   tree" in second_pass
    reference = skill.files()["references/second-pass.md"]
    assert "Not the whole docs tree" in reference
    assert "first\n   level of docs/" in reference
    assert "govern parts that are not in the tree" in reference


def test_schema_defines_state_the_wheel_and_the_pair_rule() -> None:
    """F21 and F6: the words the check and the page print, defined where they are read."""
    schema = skill.files()["references/schema.md"]
    assert "`built` is its only value" in schema
    assert "shows `outside`" in schema
    assert "the relationship wheel is drawn for a card when it is\nclicked, one per card" in schema
    assert "17 wheels" in schema
    assert "One flow per ordered pair" in schema
    assert "draw the other\ndirection as its own flow" in schema
    assert "empty package marker" in schema
    assert 'module = "pkg.vendor.*"' in schema


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
            # The configuration the example needs: none. The package root is
            # an empty package marker the coverage rule leaves out on its own.
            "systemap.toml": "",
        },
    )
    assert main(["--root", str(tmp_path), "refresh"]) == 0
    assert main(["--root", str(tmp_path), "check"]) == 0
    out = capsys.readouterr().out
    assert "coverage: 5 of 5 modules mapped, 1 of them an empty package marker" in out
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
