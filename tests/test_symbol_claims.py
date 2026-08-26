"""Symbol claims: `implemented_by=("pkg.mod:name",)` for a part inside another card's module.

A framework may put an agent and its tools in one file. The module is
claimed once, by the agent's card; the tool card claims a public name
inside it. A symbol claim counts for no module in the coverage rule and
conflicts with no claim; the entry rule checks that the module is in the
facts, defines the name, and is claimed by some card.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest
from conftest import TWO_CARD_MODEL, write_tree

from systemap import check, extract, judgement
from systemap.cli import main
from systemap.model import Component, Model, claimed, defines_entry, module_matches, symbol_claims
from systemap.schematic import lives_in

AGENT_FILE = {
    "bot/__init__.py": "",
    "bot/agent.py": (
        "def search(term: str) -> str:\n    return term\n\n\n"
        "def write_file(path: str, text: str) -> None:\n    pass\n\n\n"
        "root_agent = object()\n"
    ),
    "bot/memory.py": "class Memory:\n    def recall(self) -> str:\n        return ''\n",
}

MODEL = (
    TWO_CARD_MODEL.replace('label="PKG"', 'label="BOT"')
    .replace(
        """COMPONENTS = (
    Component(
        id="Reader",
        region="core",
        does="Reads the input and turns it into a request.",
        interface="read(source) -> Request",
        implemented_by=("pkg.reader",),
        entry="read",
        x=COL["c1"],
        y=ROW["r1"],
    ),
    Component(
        id="Writer",
        region="core",
        does="Takes a request and writes the result.",
        interface="write(request) -> Result",
        implemented_by=("pkg.writer",),
        entry="write",
        x=COL["c2"],
        y=ROW["r1"],
    ),
)
""",
        """COMPONENTS = (
    Component(
        id="Reader",
        region="core",
        does="Runs the model on the request and calls its tools.",
        implemented_by=("bot.agent", "bot.memory"),
        entry="root_agent",
        kind="agent",
        x=COL["c1"],
        y=ROW["r1"],
    ),
    Component(
        id="Writer",
        region="core",
        does="Looks a term up for the agent.",
        implemented_by=("bot.agent:search",),
        entry="search",
        kind="tool",
        x=COL["c2"],
        y=ROW["r1"],
    ),
)
""",
    )
    .replace(
        'Flow("Reader", "Writer", "request", "data")', 'Flow("Reader", "Writer", "query", "tool")'
    )
)


def run(*argv: str) -> int:
    return main(list(argv))


def scaffold(root: Path) -> None:
    write_tree(root, AGENT_FILE)
    assert run("--root", str(root), "init", "--no-ci") == 0
    (root / "map/model.py").write_text(MODEL)


def edit(root: Path, old: str, new: str) -> None:
    model = root / "map/model.py"
    text = model.read_text()
    assert old in text, old
    model.write_text(text.replace(old, new))


def test_a_symbol_claim_passes_and_counts_for_no_module(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    scaffold(tmp_path)
    assert run("--root", str(tmp_path), "refresh") == 0
    assert run("--root", str(tmp_path), "check") == 0
    out = capsys.readouterr().out
    # Two modules, both claimed by the agent; the tool's symbol adds nothing and takes nothing.
    assert "coverage: 3 of 3 modules mapped, 1 of them an empty package marker" in out
    assert "map layout: clean (2 cards" in out
    detail = json.loads((tmp_path / "docs/map/map.json").read_text())
    assert {n["name"] for n in detail["components"]["bot.agent"]["names"]} >= {
        "search",
        "root_agent",
    }
    page = (tmp_path / "docs/map/index.html").read_text()
    assert "bot/agent.py:search" in page, "the panel names the file and the symbol"


def test_a_symbol_of_a_module_nobody_claims_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    scaffold(tmp_path)
    assert run("--root", str(tmp_path), "extract") == 0
    # The agent lets go of bot.agent: the tool's symbol has no owner, and the module is unmapped.
    edit(tmp_path, 'implemented_by=("bot.agent", "bot.memory"),', 'implemented_by=("bot.memory",),')
    edit(tmp_path, 'entry="root_agent",', 'entry="Memory",')
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert (
        "Writer claims symbol bot.agent:search of a module nobody claims; a symbol claim "
        "needs the module's owner on the map"
    ) in out
    assert "unmapped: bot.agent (no component claims it)" in out


def test_a_symbol_the_module_does_not_define_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    scaffold(tmp_path)
    assert run("--root", str(tmp_path), "extract") == 0
    edit(tmp_path, 'implemented_by=("bot.agent:search",),', 'implemented_by=("bot.agent:lookup",),')
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "Writer claims symbol bot.agent:lookup which bot.agent does not define" in out
    edit(tmp_path, 'implemented_by=("bot.agent:lookup",),', 'implemented_by=("bot.gone:search",),')
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert "Writer claims symbol bot.gone:search of a module not in the facts" in out
    # extract --check reports the module half of the claim, as for any claim.
    assert run("--root", str(tmp_path), "extract", "--check") == 1
    assert "Writer names module bot.gone which is not in the facts" in capsys.readouterr().out


def test_a_symbol_card_needs_an_entry_among_its_symbols(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    scaffold(tmp_path)
    assert run("--root", str(tmp_path), "extract") == 0
    edit(tmp_path, 'entry="search",', 'entry="write_file",')
    assert run("--root", str(tmp_path), "check") == 1
    out = capsys.readouterr().out
    assert (
        "Writer names entry write_file which none of its modules defines (bot.agent:search)"
    ) in out
    edit(tmp_path, 'entry="write_file",', "")
    assert run("--root", str(tmp_path), "check") == 1
    assert "Writer names no entry; its modules are bot.agent:search" in capsys.readouterr().out
    # Two symbols, the entry one of them: fine.
    edit(
        tmp_path,
        'implemented_by=("bot.agent:search",),',
        'implemented_by=("bot.agent:search", "bot.agent:write_file"),\n        entry="write_file",',
    )
    assert run("--root", str(tmp_path), "refresh") == 0
    assert run("--root", str(tmp_path), "check") == 0


def test_symbol_claims_in_the_model_helpers() -> None:
    tool = Component(
        "Search", "looks up", implemented_by=("bot.agent:search", "bot.extra"), entry="search"
    )
    assert symbol_claims(tool) == [("bot.agent", "search")]
    assert not module_matches("bot.agent:search", "bot.agent")
    assert not module_matches("bot.agent:search", "bot.agent:search")
    assert claimed(tool, ["bot.agent", "bot.extra"]) == ["bot.extra"]
    facts = {
        "components": {
            "bot.agent": {"names": [{"name": "search", "kind": "function"}]},
            "bot.extra": {"names": []},
        }
    }
    assert defines_entry(tool, facts)
    assert not defines_entry(dataclasses.replace(tool, entry="other"), facts)
    assert lives_in(["bot.agent:search"]) == "bot/agent.py:search"
    assert lives_in(["bot.agent", "bot.agent:search"]) == "bot/agent.py, bot/agent.py:search"
    assert lives_in(["a.b.c:x", "a.b.d", "a.b.e", "a.b.f"]) == "a/b/ (4 modules)"
    # The judgement's single-module line reads modules, not symbols, without facts.
    model = Model(
        canvas=(1, 1), containers=(), regions=(), components=(tool,), flows=(), flow_kinds=()
    )
    assert judgement.single_module(model, {}) == ["single module: Search is only bot.extra"]
    # Coverage: the symbol claim is neither an owner nor a conflict.
    owner = Component("Agent", "runs", implemented_by=("bot.agent",), entry="search")
    both = Model(
        canvas=(1, 1), containers=(), regions=(), components=(owner, tool), flows=(), flow_kinds=()
    )
    cov = check.check_coverage(both, facts, ())
    assert cov.problems == () and cov.mapped == 2
    drift = extract.mapping_drift(facts, both, {"bot"})
    assert [line for line in drift if not line.startswith("layout:")] == []
