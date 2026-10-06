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
        "systemap describe",
    ):
        assert command in text, command
    assert "README, AGENTS.md, CLAUDE.md, docs/" in text
    assert "[judgement] answered" in text and 'items = ["<line>", ...]' in text
    assert text.index("figures/structure.svg") < text.index("figures/system.svg")
    assert "open `docs/map/index.html`" not in text
    assert text.index("references/layout.md") < text.index("**check**")
    assert text.index("systemap describe") < text.index("systemap serve")
    assert "one to three words" in text
    second = skill.files()["references/second-pass.md"]
    assert "[judgement] answered" in second
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
    assert "systemap judgement --verbose" in second
    assert '--kind "crossing import"' in second
    assert "repository's own agent definition" in second
    assert "systemap serve" in second and "model sdk" in second
    pitfalls = skill.files()["references/pitfalls.md"]
    assert "outside the repository" in pitfalls and "/tmp" in pitfalls
    assert "run every CI command that applies" in pitfalls
    for step in (
        "extract",
        "draft",
        "check",
        "judgement",
        "render",
        "source review",
        "stop",
        "completion",
    ):
        assert f"**{step}**" in text, step
    assert "Source examination is necessary" in text
    assert "## Completion" in text and "## References" in text
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
    assert "\u2014" not in whole
    scrubbed = whole.replace(".claude/skills", "").replace("CLAUDE.md", "")
    assert "claude" not in scrubbed.lower()
    assert "codex" not in whole.lower()
    for word in ("planned", "tracker", "end state"):
        assert word not in whole


def test_step_four_lists_every_answer_form_and_every_line_kind() -> None:
    text = skill.text()
    step = text[text.index("4. **judgement**") : text.index("5. **render**")]
    for form in (
        'item = "<line>"',
        'items = ["<line>", ...]',
        'crossing = ["A", "B", ...]',
        'crossing_into = "A"',
        'crossing_from = "A"',
        'kind = "<kind>"',
        'module_sdk = "<import>"',
    ):
        assert form in step, form
    assert "two or more different identifiers" in step and "nonempty" in step
    assert "evidence digest" in step and "policy = true" in step
    from systemap.config import LINE_KINDS

    rows = [line for line in step.splitlines() if line.strip().startswith("| `")]
    assert [row.split("`")[1] for row in rows] == list(LINE_KINDS)
    mis_fold = next(row for row in rows if "possible mis-fold" in row)
    assert "no common name word or package" in mis_fold
    assert "Examine its function" in mis_fold and "correct component assignment" in mis_fold
    for row in rows:
        assert row.count("|") == 4, row


def test_the_document_reread_is_bounded() -> None:
    text = skill.text()
    second_pass = text[text.index("6. **source review**") : text.index("8. **completion**")]
    for phrase in (
        "README, AGENTS.md, CLAUDE.md, the documentation index, and the first level of docs/",
        "Stop further document reading when new rules apply only to source outside the repository",
        "Unread documentation must have no rules for source in this repository",
    ):
        assert phrase in second_pass
    reference = skill.files()["references/second-pass.md"]
    assert "first level of docs/" in reference
    assert (
        "Stop further document reading when new rules apply only to source outside the repository"
        in reference
    )
    assert "Unread documentation has no rules for source in the repository" in reference


def test_schema_defines_state_the_flow_list_and_the_pair_rule() -> None:
    schema = skill.files()["references/schema.md"]
    assert "evidence state `built`" in schema and "Actors show `outside`" in schema
    assert "one selection control for each flow connected to the component" in schema
    assert "artifact, direction, layer, and evidence state" in schema
    assert "One flow per ordered pair is permitted" in schema
    assert "other direction as a separate flow" in schema
    assert "empty package marker" in schema
    assert 'module = "pkg.vendor.*"' in schema
    assert "does not show source meaning or language compliance" in schema


def test_layers_reference_covers_the_agentic_kinds() -> None:
    layers = skill.files()["references/layers.md"]
    assert "## Agentic systems" in layers
    for word in ('kind="agent"', 'kind="tool"', 'kind="context"', "Structure", "System context"):
        assert word in layers, word
    assert "repository's own agent definition has precedence" in layers
    method = skill.files()["references/journeys-and-invariants.md"]
    assert "agent turn" in method and "entry_points" in method


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
    assert "coverage: 5 of 5 modules mapped, 1 an empty package marker" in out
    assert "map layout: has no errors" in out
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


def test_language_policy_is_mandatory_and_installed(tmp_path: Path) -> None:
    files = skill.files()
    policy = files["references/language.md"]
    text = skill.text()
    assert text.index("## Mandatory language requirement") < text.index("## The loop")
    for phrase in (
        "ASD-STE100 Issue 9",
        "every new map and every map update",
        "official ASD rules and dictionary",
        "approved meanings and parts of speech",
        "component names, artifacts, layers, sequences, steps, invariants",
    ):
        assert phrase in text
    assert "Procedural sentences must not exceed 20 words" in policy
    assert "Descriptive sentences must not exceed 25 words" in policy
    assert "Do not add an ordinary word to the glossary" in policy
    assert "source symbols" in policy and "recorded experiment output" in policy
    target = tmp_path / "skills" / "systemap"
    skill.write(target)
    assert (target / "references/language.md").read_text() == policy
