"""The derived layers, the standard kinds, and the agent kinds.

Two readings are derived from the topology (Structure, System context),
two belong to the standard kinds (data, control), and three more appear
only when the model has an agent (Agents, Context, Tools). The drawing
marks an agent, a tool and a context card without a colour, and the check
refuses a context or tool flow whose agent end is not an agent.
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

import pytest
from conftest import TWO_CARD_MODEL, Sample, sample_model, write_tree

from systemap import check, page
from systemap import theme as theme_mod
from systemap.cli import main
from systemap.config import Config
from systemap.extract import build as build_facts
from systemap.model import (
    Component,
    Container,
    Flow,
    Journey,
    Meaning,
    Model,
    Region,
    Step,
    all_layers,
    flow_layers,
    problems,
    reading,
)
from systemap.schematic import interactive_script, kind_rows, layer_rows
from systemap.schematic import render as render_schematic

AGENT_TREE: dict[str, str] = {
    "bot/__init__.py": "",
    "bot/planner.py": (
        'def plan(goal: str) -> list[str]:\n    """Ask the model for steps."""\n    return [goal]\n'
    ),
    "bot/shell.py": "def run(command: str) -> str:\n    return command\n",
    "bot/memory.py": "class Memory:\n    def recall(self) -> str:\n        return ''\n",
    "bot/prompt.py": "SYSTEM_PROMPT = 'be brief'\n\n\ndef render() -> str:\n    return SYSTEM_PROMPT\n",
}


def agent_model() -> tuple[Model, Meaning]:
    model = Model(
        canvas=(900, 400),
        containers=(
            Container("outside", "OUTSIDE", (16, 16, 186, 368), tone="host"),
            Container("bot", "BOT", (222, 16, 662, 368), sub="one process", tone="server"),
        ),
        regions=(
            Region("think", "THINK", (240, 50, 626, 130), container="bot"),
            Region("act", "ACT", (240, 210, 626, 130), container="bot"),
        ),
        components=(
            Component("User", "Gives a goal.", kind="actor", container="outside", x=34, y=96),
            Component(
                "Planner",
                "Runs the model on the goal and acts on the steps it returns.",
                implemented_by=("bot.planner",),
                entry="plan",
                kind="agent",
                region="think",
                x=460,
                y=90,
            ),
            Component(
                "Prompt",
                "The system prompt the planner reads first.",
                implemented_by=("bot.prompt",),
                entry="render",
                kind="context",
                region="think",
                x=270,
                y=90,
            ),
            Component(
                "Memory",
                "What the planner remembers between turns.",
                implemented_by=("bot.memory",),
                entry="Memory",
                kind="context",
                region="act",
                x=270,
                y=250,
            ),
            Component(
                "Shell",
                "Runs a command the planner asks for.",
                implemented_by=("bot.shell",),
                entry="run",
                kind="tool",
                region="act",
                x=650,
                y=250,
            ),
        ),
        flows=(
            Flow("User", "Planner", "goal", "data"),
            Flow("Prompt", "Planner", "system prompt", "context"),
            Flow("Memory", "Planner", "recall", "context"),
            Flow("Planner", "Shell", "command", "tool"),
            Flow("Planner", "Memory", "note", "data"),
        ),
        flow_kinds=(),
    )
    meaning = Meaning(
        plain={
            "User": "the person with a goal",
            "Planner": "the agent",
            "Prompt": "what it is told first",
            "Memory": "what it remembers",
            "Shell": "what it can run",
        },
        relations={
            ("User", "Planner"): "The user gives the planner a goal.",
            ("Prompt", "Planner"): "The system prompt enters the planner's window first.",
            ("Memory", "Planner"): "The planner reads its memory at the start of a turn.",
            ("Planner", "Shell"): "The planner runs shell commands to act.",
            ("Planner", "Memory"): "The planner writes a note at the end of a turn.",
        },
        journeys=(
            Journey(
                "turn",
                "One turn of the planner",
                steps=(
                    Step(("User",), (), ("User", "Planner"), "A goal arrives."),
                    Step(("Planner",), (), ("Prompt", "Planner"), "The prompt is read."),
                    Step(("Planner",), (), ("Planner", "Shell"), "A command runs."),
                ),
            ),
        ),
    )
    return model, meaning


@pytest.fixture
def agentic(tmp_path: Path) -> Sample:
    write_tree(tmp_path, AGENT_TREE)
    cfg = Config(root=tmp_path, name="bot", package_roots=(("bot", "bot"),))
    model, meaning = agent_model()
    facts = build_facts(cfg)
    return Sample(cfg, model, meaning, theme_mod.resolve({}, all_layers(model, meaning)), facts)


# ---- the standard layers ---------------------------------------------------------


def test_layer_order_and_first_layer(sample: Sample) -> None:
    html = page.build(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {"has_change": False}
    )
    buttons = [
        line.split('data-layer-btn="')[1].split('"')[0]
        for line in html.splitlines()
        if "data-layer-btn=" in line
    ]
    assert buttons == ["structure", "system", "data", "control", "record", "memory", "all"]
    assert ">Structure</button>" in html and ">System context</button>" in html
    assert ">Data flow</button>" in html and ">Control flow</button>" in html
    assert "six layers" in html
    # Every layer but Structure draws a line, so the legend has a swatch for it.
    rows = layer_rows(sample.theme, sample.model, sample.meaning)
    assert [r[0] for r in rows] == ["system", "data", "control", "record", "memory"]
    # No agent, so no agent layers and no kind marks.
    assert kind_rows(sample.theme, sample.model) == []
    assert 'data-layer-btn="agents"' not in html and ">Agents</button>" not in html


def test_a_flow_of_an_undeclared_kind_fails(sample: Sample) -> None:
    model = dataclasses.replace(
        sample.model, flows=(*sample.model.flows, Flow("Reader", "Writer", "x", "measure"))
    )
    found = "\n".join(problems(model, sample.meaning))
    assert "flow Reader -> Writer has kind measure, which is neither standard" in found
    declared = dataclasses.replace(model, flow_kinds=(*model.flow_kinds, "measure"))
    # Declared, the custom kind still needs a layer of its own.
    found = "\n".join(problems(declared, sample.meaning))
    assert "neither standard" not in found
    assert "flow Reader -> Writer has kind measure with no layer" in found


def test_standard_kinds_need_no_declaration(tmp_path: Path) -> None:
    # The starter model init writes uses the data kind with an empty flow_kinds.
    write_tree(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
            "pkg/writer.py": "def write(request: str) -> str:\n    return request\n",
        },
    )
    assert main(["--root", str(tmp_path), "init", "--no-ci"]) == 0
    text = (tmp_path / "map/model.py").read_text()
    assert "COMPONENTS: tuple[Component, ...] = ()" in text
    assert "FLOW_KINDS: tuple[str, ...] = ()" in text
    assert "LAYERS: tuple[Layer, ...] = ()" in text
    assert 'Flow("Reader", "Writer", "request", "data")' in TWO_CARD_MODEL
    (tmp_path / "map/model.py").write_text(TWO_CARD_MODEL)
    assert main(["--root", str(tmp_path), "refresh"]) == 0
    assert main(["--root", str(tmp_path), "check"]) == 0
    html = (tmp_path / "docs/map/index.html").read_text()
    assert 'data-layer-btn="structure"' in html


# ---- the agent kinds --------------------------------------------------------------


def test_agent_layers_appear_only_with_an_agent(agentic: Sample) -> None:
    ids = [layer.id for layer in all_layers(agentic.model, agentic.meaning)]
    assert ids == ["structure", "system", "data", "control", "agents", "context", "tools"]
    assert [layer.id for layer in flow_layers(agentic.model, agentic.meaning)] == [
        "data",
        "control",
        "context",
        "tools",
    ]
    labels = {layer.id: layer.label for layer in all_layers(agentic.model, agentic.meaning)}
    assert labels["system"] == "System context" and labels["context"] == "Context"
    assert labels["agents"] == "Agents" and labels["tools"] == "Tools"
    assert agentic.model.agentic
    sample_model_, _ = sample_model()
    assert not sample_model_.agentic


def test_agent_model_checks_clean_and_draws_the_marks(agentic: Sample) -> None:
    assert problems(agentic.model, agentic.meaning) == []
    result = check.run(
        agentic.model, agentic.meaning, agentic.theme, agentic.facts, agentic.cfg.coverage_ignore
    )
    assert result.problems == [] and result.entry == []
    assert result.ok
    svg, detail = render_schematic(agentic.model, agentic.meaning, agentic.theme, agentic.facts)
    data = json.loads(detail)
    assert data["Planner"]["kind"] == "agent"
    assert data["Shell"]["kind"] == "tool"
    assert data["Prompt"]["kind"] == "context"
    # The marks: an agent's inner ring, a tool's notch, a context's dotted border.
    assert svg.count('class="node__mark"') == 2, "one ring and one notch"
    assert 'stroke-dasharray="1.5 2.5"' in svg, "the context cards are dotted"
    assert svg.count('stroke-dasharray="1.5 2.5"') == 2
    assert [layer["id"] for layer in data["_meta"]["layers"]][4:] == ["agents", "context", "tools"]
    edges = {(e["from"], e["to"]): e for e in data["_meta"]["edges"]}
    assert edges[("Prompt", "Planner")]["layer"] == "context"
    assert edges[("Planner", "Shell")]["layer"] == "tools"
    assert edges[("Planner", "Shell")]["out"] == "invokes"
    assert edges[("Prompt", "Planner")]["in"] == "reads"
    assert kind_rows(agentic.theme, agentic.model) == [
        ("agent", "ring"),
        ("tool", "notch"),
        ("context", "dotted"),
    ]
    html = page.build(
        agentic.cfg,
        agentic.model,
        agentic.meaning,
        agentic.theme,
        agentic.facts,
        {"has_change": False},
    )
    for label in ("Agents", "Context", "Tools"):
        assert f">{label}</button>" in html
    assert "lg--mark-ring" in html and "lg--mark-notch" in html and "lg--mark-dotted" in html


def test_context_and_tool_flows_need_an_agent_end(agentic: Sample) -> None:
    demoted = dataclasses.replace(
        agentic.model,
        components=tuple(
            dataclasses.replace(c, kind="component") if c.id == "Planner" else c
            for c in agentic.model.components
        ),
    )
    found = "\n".join(problems(demoted, agentic.meaning))
    assert (
        "flow Prompt -> Planner has kind context but Planner is not an agent; a context "
        "flow ends at the agent whose window it enters: set Planner's kind to agent, or "
        "give the flow the kind data"
    ) in found
    assert (
        "flow Planner -> Shell has kind tool but Planner is not an agent; a tool flow "
        "starts at the agent that invokes it: set Planner's kind to agent, or give the "
        "flow the kind control"
    ) in found
    # The wrong end: a context flow leaving the agent is refused too.
    backwards = dataclasses.replace(
        agentic.model, flows=(*agentic.model.flows, Flow("Planner", "Prompt", "x", "context"))
    )
    found = "\n".join(problems(backwards, agentic.meaning))
    assert "flow Planner -> Prompt has kind context but Prompt is not an agent" in found


def test_agent_kinds_are_cards_that_claim_code(agentic: Sample) -> None:
    # An agent, a tool and a context card are code in the tree like any
    # other component: the entry rule applies to them.
    missing = dataclasses.replace(
        agentic.model,
        components=tuple(
            dataclasses.replace(c, entry="absent") if c.id == "Shell" else c
            for c in agentic.model.components
        ),
    )
    lines = check.check_entry(missing, agentic.facts)
    assert lines == ["Shell names entry absent which none of its modules defines (bot.shell)"]


# ---- a figure of one agent reading marks its subjects and dims the rest ----------


def cards_drawn(svg: str) -> dict[str, tuple[set[str], str]]:
    """id -> (the node's classes, its box stroke) for every card in an SVG."""
    found = re.findall(
        r'<g class="node ([^"]*)" data-id="([^"]+)"[^>]*>\s*<rect class="node__box"[^>]*?stroke="([^"]+)"',
        svg,
    )
    return {cid: (set(classes.split()), stroke) for classes, cid, stroke in found}


def with_log(sample: Sample) -> Sample:
    """The agent model plus a plain card no flow touches, in the act region."""
    log = Component(
        "Log",
        "Writes what happened.",
        implemented_by=("bot.shell",),
        entry="run",
        region="act",
        x=460,
        y=250,
    )
    model = dataclasses.replace(sample.model, components=(*sample.model.components, log))
    meaning = dataclasses.replace(sample.meaning, plain={**sample.meaning.plain, "Log": "the log"})
    return dataclasses.replace(sample, model=model, meaning=meaning)


def test_context_and_tool_cards_are_subjects_of_their_readings(agentic: Sample) -> None:
    for layer, subjects in (
        ("agents", ["Planner"]),
        ("context", ["Prompt", "Memory"]),
        ("tools", ["Shell"]),
        ("system", ["User"]),
        ("data", []),
    ):
        assert reading(agentic.model, agentic.meaning, layer)[1] == subjects, layer


def test_a_layer_figure_colours_its_subjects_and_dims_the_untouched(agentic: Sample) -> None:
    a = with_log(agentic)
    hue = a.theme["layers"]
    built = a.theme["state"]["built"][1]

    def draw(layer: str) -> dict[str, tuple[set[str], str]]:
        svg, _ = render_schematic(a.model, a.meaning, a.theme, a.facts, layer=layer)
        return cards_drawn(svg)

    cards = draw("agents")
    assert cards["Planner"][1] == hue["agents"] and "subject" in cards["Planner"][0]
    assert "quiet" in cards["Log"][0], "no edge of the reading touches it"
    for cid in ("User", "Prompt", "Memory", "Shell"):
        assert "quiet" not in cards[cid][0], cid
        assert cards[cid][1] != hue["agents"], cid
    cards = draw("context")
    for cid in ("Prompt", "Memory"):
        assert cards[cid][1] == hue["context"] and "subject" in cards[cid][0], cid
    assert "quiet" not in cards["Planner"][0], "the context edges end at the agent"
    for cid in ("Shell", "User", "Log"):
        assert "quiet" in cards[cid][0], cid
    cards = draw("tools")
    assert cards["Shell"][1] == hue["tools"] and "subject" in cards["Shell"][0]
    for cid in ("Prompt", "Memory", "User", "Log"):
        assert "quiet" in cards[cid][0], cid
    cards = draw("system")
    assert cards["User"][1] == hue["system"]
    assert "quiet" in cards["Log"][0] and "quiet" not in cards["Planner"][0]
    # Structure is about every card: nothing coloured, nothing dimmed. The
    # whole map, likewise.
    for layer in ("structure", ""):
        svg, _ = render_schematic(a.model, a.meaning, a.theme, a.facts, layer=layer)
        cards = cards_drawn(svg)
        assert not any("quiet" in c or "subject" in c for c, _s in cards.values()), layer
        assert cards["Planner"][1] == built
    # The mark takes the stroke with it: the agent's ring in the Agents reading.
    svg, _ = render_schematic(a.model, a.meaning, a.theme, a.facts, layer="agents")
    ring = re.search(r'class="node__mark" x="465\.0"[^>]*stroke="([^"]+)"', svg)
    assert ring is not None and ring.group(1) == hue["agents"]


def test_the_page_colours_subjects_the_same_way(agentic: Sample) -> None:
    svg, detail = render_schematic(agentic.model, agentic.meaning, agentic.theme, agentic.facts)
    assert ".node.subject .node__box{stroke:var(--subject)}" in svg
    script = interactive_script(agentic.theme, "schematic", "panel", detail)
    assert "n.style.setProperty('--subject', subject ? LCOL[L] : '')" in script
    assert "subject:subject" in script
    meta = json.loads(detail)["_meta"]
    assert meta["readings"]["context"]["subjects"] == ["Prompt", "Memory"]
    assert meta["readings"]["tools"]["subjects"] == ["Shell"]
