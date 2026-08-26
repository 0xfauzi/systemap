"""A single-shot call site (`calls_model`) and a store with no entry.

A repository's own rule made its single-shot call sites non-agents, so a
context flow into one was refused and the Context reading lit one edge;
and a constants table had no honest entry to give.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest
from conftest import init_two_cards, write_tree
from test_layers import agent_model

from systemap import check, judgement, skill
from systemap import theme as theme_mod
from systemap.cli import main
from systemap.config import Config
from systemap.extract import build as build_facts
from systemap.model import Component, Flow, all_layers, problems, reading
from systemap.schematic import render as render_schematic

STARTER_MODULES = {
    "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
    "pkg/writer.py": "def write(request: str) -> str:\n    return request\n",
}


def run(*argv: str) -> int:
    return main(list(argv))


def with_call_site(tmp_path: Path) -> tuple[Config, dict, dict]:  # type: ignore[type-arg]
    """The agent model with the Planner a single-shot call site, not an agent."""
    write_tree(
        tmp_path,
        {
            "bot/__init__.py": "",
            "bot/planner.py": "import anthropic\n\n\ndef plan(goal: str) -> list[str]:\n    return [goal]\n",
            "bot/shell.py": "def run(command: str) -> str:\n    return command\n",
            "bot/memory.py": "class Memory:\n    def recall(self) -> str:\n        return ''\n",
            "bot/prompt.py": "SYSTEM_PROMPT = 'be brief'\n\n\ndef render() -> str:\n    return SYSTEM_PROMPT\n",
        },
    )
    cfg = Config(root=tmp_path, name="bot", package_roots=(("bot", "bot"),))
    model, meaning = agent_model()
    model = dataclasses.replace(
        model,
        components=tuple(
            dataclasses.replace(c, kind="component", calls_model=True) if c.id == "Planner" else c
            for c in model.components
        ),
    )
    return cfg, model, meaning


def test_context_and_tool_flows_accept_a_calls_model_component(tmp_path: Path) -> None:
    cfg, model, meaning = with_call_site(tmp_path)
    facts = build_facts(cfg)
    assert problems(model, meaning) == []
    assert model.agentic, "the agent readings appear for a single-shot call site too"
    assert model.component("Planner").model_end and not model.component("Shell").model_end
    theme = theme_mod.resolve({}, all_layers(model, meaning))
    result = check.run(model, meaning, theme, facts, cfg.coverage_ignore)
    assert result.ok, result
    # The Agents reading stays agents only: nothing, here. Context and Tools
    # light every context and tool flow, whichever end runs the model.
    assert reading(model, meaning, "agents") == ([], [])
    context_edges, context_subjects = reading(model, meaning, "context")
    assert [model.flows[i].edge for i in context_edges] == [
        ("Prompt", "Planner"),
        ("Memory", "Planner"),
    ]
    assert context_subjects == ["Prompt", "Memory"]
    tool_edges, tool_subjects = reading(model, meaning, "tools")
    assert [model.flows[i].edge for i in tool_edges] == [("Planner", "Shell")]
    assert tool_subjects == ["Shell"]
    # The flag answers the model sdk line; without it the line is asked.
    assert judgement.model_sdk_imports(model, facts) == []
    unflagged = dataclasses.replace(
        model,
        components=tuple(
            dataclasses.replace(c, calls_model=False) if c.id == "Planner" else c
            for c in model.components
        ),
    )
    assert judgement.model_sdk_imports(unflagged, facts) == [
        "model sdk: module bot.planner imports anthropic and its component Planner is not an agent"
    ]
    found = "\n".join(problems(unflagged, meaning))
    assert (
        "flow Prompt -> Planner has kind context but Planner is not an agent; a context "
        "flow ends at the agent whose window it enters: set Planner's kind to agent, mark "
        "it calls_model=True if it makes a single-shot call, or give the flow the kind data"
    ) in found
    assert (
        "mark it calls_model=True if it makes a single-shot call, or give the flow the kind control"
        in found
    )
    # The panel says so; the card carries no mark, since it is not an agent.
    svg, detail = render_schematic(model, meaning, theme, facts)
    data = json.loads(detail)
    assert data["Planner"]["calls_model"] is True and data["Shell"]["calls_model"] is False
    assert data["Planner"]["kind"] == "component"
    assert svg.count('class="node__mark"') == 1, "the tool's notch alone"
    from systemap.schematic import interactive_script

    assert "calls a model" in interactive_script(theme, "schematic", "panel", detail)


def test_calls_model_in_the_model_module(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/reader.py": "import openai\n\n\ndef read(source: str) -> str:\n    return source\n",
            "pkg/writer.py": "def write(request: str) -> str:\n    return request\n",
        },
    )
    init_two_cards(tmp_path, "--no-ci")
    assert run("--root", str(tmp_path), "extract") == 0
    capsys.readouterr()
    assert run("--root", str(tmp_path), "judgement") == 0
    assert "model sdk: module pkg.reader imports openai" in capsys.readouterr().out
    model = tmp_path / "map/model.py"
    model.write_text(
        model.read_text()
        .replace('entry="read",', 'entry="read",\n        calls_model=True,')
        .replace(
            'Flow("Reader", "Writer", "request", "data")',
            'Flow("Writer", "Reader", "request", "context")',
        )
        .replace('("Reader", "Writer"):', '("Writer", "Reader"):')
        .replace('edge=("Reader", "Writer")', 'edge=("Writer", "Reader")')
    )
    assert run("--root", str(tmp_path), "refresh") == 0
    assert run("--root", str(tmp_path), "check") == 0
    capsys.readouterr()
    assert run("--root", str(tmp_path), "judgement") == 0
    out = capsys.readouterr().out
    assert "model sdk" not in out
    page = (tmp_path / "docs/map/index.html").read_text()
    assert '"calls_model":true' in page
    assert 'data-layer-btn="context"' in page, "the Context reading appears for the call site"


# ---- a store or a context card may be a namespace -----------------------------


def test_entry_is_optional_for_store_and_context_kinds(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    assert run("--root", str(tmp_path), "extract") == 0
    model = tmp_path / "map/model.py"
    text = model.read_text()
    # A component with no entry is refused, as before.
    model.write_text(text.replace('entry="write",', ""))
    assert run("--root", str(tmp_path), "check") == 1
    assert "Writer names no entry; its modules are pkg.writer" in capsys.readouterr().out
    # A store with no entry is a namespace: its modules alone say it exists.
    model.write_text(text.replace('entry="write",', 'kind="store",'))
    assert run("--root", str(tmp_path), "refresh") == 0
    assert run("--root", str(tmp_path), "check") == 0
    capsys.readouterr()
    page = (tmp_path / "docs/map/index.html").read_text()
    assert '"entry":"","entry_module":""' in page
    assert "none (a namespace)" in page
    # An entry a store does give is checked like any other.
    model.write_text(text.replace('entry="write",', 'kind="store",\n        entry="publish",'))
    assert run("--root", str(tmp_path), "check") == 1
    assert "Writer names entry publish which none of its modules defines (pkg.writer)" in (
        capsys.readouterr().out
    )
    # A context card too; an agent, a tool and an actor's rules are unchanged.
    facts = {"components": {"pkg.writer": {"names": [{"name": "write", "kind": "function"}]}}}
    for kind in ("store", "context"):
        card = Component("W", "w", implemented_by=("pkg.writer",), kind=kind, region="core")
        model_ = dataclasses.replace(agent_model()[0], components=(card,), flows=())
        assert check.check_entry(model_, facts) == [], kind
    for kind in ("component", "agent", "tool"):
        card = Component("W", "w", implemented_by=("pkg.writer",), kind=kind, region="core")
        model_ = dataclasses.replace(agent_model()[0], components=(card,), flows=())
        assert check.check_entry(model_, facts) == [
            "W names no entry; its modules are pkg.writer"
        ], kind
    assert check.ENTRY_OPTIONAL == ("store", "context")


def test_the_references_carry_calls_model_and_the_optional_entry() -> None:
    schema = skill.files()["references/schema.md"]
    assert "calls_model=False, map=None)`" in schema
    assert "entry: none (a namespace)" in schema
    assert "The Agents reading stays agents only" in schema
    layers = skill.files()["references/layers.md"]
    assert "`calls_model=True` on a component" in layers
    assert "the Agents reading leaves it out" in layers
    second = skill.files()["references/second-pass.md"]
    assert "Five outcomes" in second and "set `calls_model=True` on it" in second
    unused = Flow  # the schema name the tests above build flows with
    assert unused is Flow
