"""The three things the deeper commands are built on: the agent door, the walk, the teaching.

`systemap.agent` runs a command the maintainer named and caches what it
wrote; `systemap.graph` walks the map; `systemap.explain` holds a lesson for
every kind of line. No test here runs a real agent: each passes its own
`run_command`, as the Jev tests pass a recorded transport.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from systemap import agent, config, delta, explain, graph
from systemap.config import load as load_config
from systemap.model import (
    Component,
    Container,
    Flow,
    Invariant,
    Journey,
    Meaning,
    Model,
    Region,
    Step,
)

# ---- the agent door ---------------------------------------------------------------


def recorder(answers: list[str]) -> tuple[agent.Run, list[str]]:
    """A transport that answers from a list and records the questions it was asked."""
    asked: list[str] = []

    def run(command: str, question: str, cwd: Path, timeout: float) -> str:
        asked.append(question)
        return answers[min(len(asked) - 1, len(answers) - 1)]

    return run, asked


def test_the_agent_is_asked_once_and_remembered(tmp_path: Path) -> None:
    run, asked = recorder(["The parser now hands tokens to the store."])
    one = agent.Agent("agent -p", tmp_path, agent.Cache(tmp_path / "c.json"), run_command=run)
    first = one.ask("What does this change mean?", {"cards": ["Parser"]})
    assert first == "The parser now hands tokens to the store."
    assert "Parser" in asked[0] and "What does this change mean?" in asked[0]
    again = agent.Agent("agent -p", tmp_path, agent.Cache(tmp_path / "c.json"), run_command=run)
    assert again.ask("What does this change mean?", {"cards": ["Parser"]}) == first
    assert len(asked) == 1, "the second run read the cache"
    assert again.usage.cached == 1 and again.usage.called == 0
    assert "1 from the cache" in again.usage.line()
    # a different question is a different answer
    one.ask("What does this change mean?", {"cards": ["Store"]})
    assert len(asked) == 2


def test_a_json_answer_is_unwrapped(tmp_path: Path) -> None:
    run, _asked = recorder(['{"type": "result", "result": "Two journeys pass through it."}'])
    one = agent.Agent("agent -p", tmp_path, agent.Cache(None), run_command=run)
    assert one.ask("q") == "Two journeys pass through it."


def test_without_a_command_nothing_runs_and_the_reason_is_said(tmp_path: Path) -> None:
    (tmp_path / "systemap.toml").write_text('name = "x"\nmodel = "map/model.py"\n')
    cfg = load_config(tmp_path)
    assert cfg.agent_command == "" and not agent.has_agent(cfg)
    with pytest.raises(agent.AgentError, match="no agent is set"):
        agent.from_cfg(cfg)


def test_a_failing_command_is_reported_never_answered(tmp_path: Path) -> None:
    def broken(command: str, question: str, cwd: Path, timeout: float) -> str:
        raise agent.AgentError("the agent exited 2: no such model")

    one = agent.Agent("agent -p", tmp_path, agent.Cache(None), run_command=broken)
    with pytest.raises(agent.AgentError, match="exited 2"):
        one.ask("q")


def test_the_agent_table_is_read_and_checked(tmp_path: Path) -> None:
    toml = tmp_path / "systemap.toml"
    toml.write_text(
        'name = "x"\nmodel = "map/model.py"\n'
        '[agent]\ncommand = "claude -p"\ntimeout = 90\ncache = ".systemap/a.json"\n'
    )
    cfg = load_config(tmp_path)
    assert cfg.agent_command == "claude -p" and cfg.agent_timeout == 90.0
    assert cfg.agent_cache_path == tmp_path / ".systemap/a.json"
    toml.write_text('name = "x"\n[agent]\ntimeout = 0\n')
    with pytest.raises(config.ConfigError, match="agent.timeout"):
        load_config(tmp_path)
    toml.write_text('name = "x"\n[agent]\nmodel = "x"\n')
    with pytest.raises(config.ConfigError, match="agent has unknown key: model"):
        load_config(tmp_path)


# ---- the walk ---------------------------------------------------------------------


def card(cid: str) -> Component:
    return Component(id=cid, does=f"{cid} does its job", implemented_by=(f"pkg.{cid.lower()}",))


MODEL = Model(
    canvas=(600, 300),
    containers=(Container("system", "SYSTEM", (0, 0, 600, 300)),),
    regions=(Region("work", "WORK", (10, 10, 580, 280), container="system"),),
    flow_kinds=(),
    components=(card("Reader"), card("Parser"), card("Store"), card("Report")),
    flows=(
        Flow("Reader", "Parser", "text", "data"),
        Flow("Parser", "Store", "tokens", "data"),
        Flow("Store", "Report", "rows", "data"),
        Flow("Reader", "Report", "status", "control"),
    ),
    invariants=(
        Invariant(1, "every token is unique", ("Store",)),
        Invariant(2, "a report names its source", ("Report", "Reader")),
    ),
)
WALKED = Journey(
    id="import",
    label="import a file",
    steps=(
        Step(("Reader",), (), ("Reader", "Parser"), "the reader hands the text over"),
        Step(("Parser",), (), ("Parser", "Store"), "the parser stores what it read"),
    ),
)
MEANING = Meaning(plain={}, journeys=(WALKED,))


def test_the_walk_follows_flows_forward_and_counts_the_hops() -> None:
    found = graph.walk(MODEL, ["Reader"])
    assert found.depth_of == {"Reader": 0, "Parser": 1, "Report": 1, "Store": 2}
    assert found.reached == ["Parser", "Report", "Store"]
    assert found.at(1) == ["Parser", "Report"]
    assert ("Parser", "Store") in found.edges
    # backwards is not a ripple: nothing reaches Reader from Store
    assert graph.walk(MODEL, ["Store"]).reached == ["Report"]


def test_a_flow_that_carries_nothing_new_stops_the_walk() -> None:
    def keep(flow: Flow, depth: int) -> bool:
        return flow.artifact != "tokens"

    found = graph.walk(MODEL, ["Reader"], keep=keep)
    assert found.reached == ["Parser", "Report"], "Store is past the flow that was pruned"


def test_the_walk_stops_at_the_depth_it_is_given() -> None:
    assert graph.walk(MODEL, ["Reader"], max_depth=1).reached == ["Parser", "Report"]


def test_what_walks_through_a_flow_and_what_governs_a_card() -> None:
    through = graph.journeys_through(MEANING, [("Parser", "Store")])
    assert [(j.id, steps) for j, steps in through] == [("import", [1])]
    assert graph.journeys_through(MEANING, [("Store", "Report")]) == []
    rules = graph.rules_over(MODEL, ["Store", "Report"])
    assert [(r.n, named) for r, named in rules] == [(1, ["Store"]), (2, ["Report"])]
    assert [r.n for r in graph.rules_on(MODEL)["Reader"]] == [2]


# ---- the teaching -----------------------------------------------------------------


def test_every_kind_of_line_is_taught() -> None:
    for kind in (*config.LINE_KINDS, *config.AUDIT_KINDS, *delta.KINDS):
        found = explain.lesson(kind)
        assert found is not None, f"{kind} has no lesson in explain.py"
        assert found.means and found.why and found.do
        assert found.why.endswith((".", "?")) and found.do.endswith(".")


def test_a_lesson_prints_as_two_rows_under_the_line() -> None:
    rows = explain.rows("single module")
    assert len(rows) == 2
    assert rows[0].startswith("      why: ") and rows[1].startswith("      do:  ")
    assert explain.rows("not a kind") == []


def test_explain_prints_one_entry_whole_and_names_the_kinds_it_knows() -> None:
    out = explain.whole("crossing import")
    assert out[0] == "crossing import"
    assert any("why it matters" in line for line in out)
    missing = explain.whole("nonsense")
    assert "there is no line kind" in missing[0] and "crossing import" in missing[1]


# ---- the teaching, under the lines and on its own ----------------------------------


def test_explain_lists_every_kind_and_prints_one_whole(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from systemap.cli import main

    assert main(["--root", str(tmp_path), "explain"]) == 0
    out = capsys.readouterr().out
    assert "the kinds of line systemap prints" in out
    for kind in ("crossing import", "coverage", "jev owner", "new crossing import"):
        assert f"  {kind}: " in out
    assert main(["--root", str(tmp_path), "explain", "crossing import"]) == 0
    whole = capsys.readouterr().out
    assert whole.startswith("crossing import\n")
    assert "why it matters:" in whole and "what to do:" in whole
    # a kind nobody prints is refused, and the refusal names the ones there are
    assert main(["--root", str(tmp_path), "explain", "nonsense"]) == 1
    assert "there is no line kind" in capsys.readouterr().out


def test_a_failing_check_group_is_taught_and_a_passing_one_is_not() -> None:
    from systemap import check as check_mod

    clean = ["map routes: 0 edges through a card they do not connect"]
    assert check_mod._taught(clean) == clean, "a rule that passed is one line"
    failing = ["coverage: 1 module is claimed by no card", "  pkg.extra"]
    taught = check_mod._taught(failing)
    assert taught[0] == failing[0]
    assert taught[1].startswith("      why: ") and taught[2].startswith("      do:  ")
    assert taught[3] == "  pkg.extra"
