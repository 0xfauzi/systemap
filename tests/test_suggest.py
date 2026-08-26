"""`systemap suggest`: a first grouping from the facts alone, to argue with.

Nothing said how many components a map should have; the skill now states
a target, and this command prints a starting point from the package
structure and the import graph, never the answer.
"""

from __future__ import annotations

from pathlib import Path

import fixture_workspace
import pytest
from conftest import init_two_cards, write_tree

from systemap import skill, suggest
from systemap.cli import main


def run(*argv: str) -> int:
    return main(list(argv))


def test_camel_ids() -> None:
    assert suggest.camel("wharf_server.render.emit") == "RenderEmit"
    assert suggest.camel("wharf_server") == "WharfServer"
    assert suggest.camel("pkg.my-thing.x") == "MyThingX"


def test_proposals_on_the_workspace_fixture() -> None:
    facts = fixture_workspace.facts()
    groups, alone = suggest.proposals(facts)
    ids = [p.id for p in groups]
    assert ids == [
        "WharfContracts",
        "WharfServer",
        "Artifacts",
        "Config",
        "Content",
        "Gateway",
        "Layout",
        "Lineage",
        "Measure",
        "Orchestration",
        "Prompts",
        "Render",
        "RenderEmit",
        "Sandbox",
        "Style",
    ]
    by_id = {p.id: p for p in groups}
    assert by_id["RenderEmit"].package == "wharf_server.render.emit"
    assert len(by_id["RenderEmit"].modules) == 23
    assert by_id["WharfServer"].modules == (
        "wharf_server.edit",
        "wharf_server.hashing",
        "wharf_server.mirror",
        "wharf_server.quality",
    )
    assert alone == [
        "wharf_server.component_generator.library",
        "wharf_server.orchestration.agents.wharf.agent",
    ]
    # Every non-marker module is in exactly one proposal or alone.
    placed = [m for p in groups for m in p.modules] + alone
    assert len(placed) == len(set(placed)) == 144 - 18
    lines = suggest.lines(facts)
    assert lines[0] == "suggest: a first grouping to argue with, never the answer"
    assert "never the answer" in lines[0] and "three to ten modules" in lines[1]
    assert "N/10 and N/3" in lines[1]
    assert lines[2] == (
        "proposals: 15, from 144 modules (2 alone in their package, 18 empty package "
        "markers left out)"
    )
    assert "    more than 10 modules: split it by purpose" in lines
    assert lines.index("    more than 10 modules: split it by purpose") == (
        lines.index(next(line for line in lines if line.startswith("  WharfContracts"))) + 1
    )
    assert "crossing imports between proposals: 0 pairs" in lines


def test_two_packages_that_shorten_to_one_id_keep_their_path() -> None:
    facts = {
        "components": {
            "a.gateway": {
                "file": "a/gateway/__init__.py",
                "names": [{"name": "x", "kind": "object"}],
            },
            "a.gateway.app": {"file": "a/gateway/app.py"},
            "b.gateway": {
                "file": "b/gateway/__init__.py",
                "names": [{"name": "y", "kind": "object"}],
            },
            "b.gateway.app": {"file": "b/gateway/app.py"},
        }
    }
    groups, alone = suggest.proposals(facts)
    assert [p.id for p in groups] == ["AGateway", "BGateway"] and alone == []


def test_suggest_command_lists_crossings_between_proposals(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
            "pkg/writer.py": "def write(request: str) -> str:\n    return request\n",
            "pkg/store/__init__.py": "",
            "pkg/store/ledger.py": "from pkg.reader import read\n\n\nclass Ledger:\n    pass\n",
            "pkg/store/rows.py": "from pkg.store.ledger import Ledger\n\n\ndef rows() -> None:\n    pass\n",
            "pkg/lone/__init__.py": "",
            "pkg/lone/only.py": "def only() -> None:\n    pass\n",
        },
    )
    init_two_cards(tmp_path, "--no-ci")
    capsys.readouterr()
    assert run("--root", str(tmp_path), "suggest") == 1
    assert capsys.readouterr().out == "no facts at docs/map/map.json\nrun: systemap extract\n"
    assert run("--root", str(tmp_path), "extract") == 0
    capsys.readouterr()
    assert run("--root", str(tmp_path), "suggest") == 0
    out = capsys.readouterr().out
    assert out.startswith("suggest: a first grouping to argue with, never the answer\n")
    assert (
        "proposals: 2, from 8 modules (1 alone in their package, 3 empty package markers "
        "left out)\n"
        "  Pkg (pkg): 2 modules: pkg.reader, pkg.writer\n"
        "  Store (pkg.store): 2 modules: pkg.store.ledger, pkg.store.rows\n"
        "alone in their package, to fold into a neighbour: pkg.lone.only\n"
        "crossing imports between proposals: 1 pairs\n"
        "  Store -> Pkg: 1 (pkg.store.ledger -> pkg.reader)\n"
    ) in out


def test_the_skill_states_the_target_and_runs_suggest_and_the_check_together() -> None:
    text = skill.text()
    assert "three to ten" in text and "N/10 and N/3" in text
    assert "`systemap suggest`" in text and "never the\n   answer" in text
    assert "| `systemap suggest` |" in text
    # The check step runs the check and the strict judgement together, and says why.
    step = text[text.index("3. **check**") : text.index("4. **judgement**")]
    assert "`systemap check && systemap judgement --strict`" in step
    assert "reopens the crossing-import lines" in step
    second = skill.files()["references/second-pass.md"]
    assert "`systemap check && systemap judgement --strict`" in second
    for form in (
        '{ crossing_into = "',
        '{ crossing_from = "',
        '{ crossing = ["Page", "Figures", "Describe"]',
    ):
        assert form in second, form
