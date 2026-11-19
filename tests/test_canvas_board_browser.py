"""The boards of the canvas page in a browser (`page_canvas_board`): the States view and
the sequence as a diagram.

The test drives real canvas pages in the Chromium of Playwright (tests/canvas_board.js):
the self-map of this repository, which has two state machines and 16 sequences, and the
fixture of tests/test_canvas_page.py, which has no state machine. The test skips when Node
or the Playwright package is not there, except when SYSTEMAP_BROWSER_TESTS is "required".

Acceptance values, written before the first run on 2026-11-15:

1. On the self-map, the header shows the States button. A click gives the mode "states"
   and the board with the alpha 1. The canvas draws the name of each state of the first
   state machine and the label of each transition. The board has one target for each
   state and each transition. The caption gives the label of the machine.
2. With the board shown, the wheel on the canvas does not change the camera.
3. The D key opens the Details panel. Its heading is the label of the machine, and it has
   one button for each state and each transition.
4. A click on the button of the first transition: the selection is that transition, the
   caption gives its cause, and the panel has "Show the flow on the map" and "Show the
   sequence". The first button gives the Map view with a layer that shows the flow of the
   transition (the layer of that flow, or All). The second button gives the Sequences view
   with the sequence of the transition.
5. The select of the bar gives the second machine. The canvas draws each of its states,
   and the panel gives its finding.
6. In the Sequences view, "As a diagram" gives the board with the form "diagram" and the
   alpha 1. The canvas draws the name of each component of the steps and the artifact of
   each flow of the steps. "As a diagram" is pressed, and "On the map" is not. After Start
   at step 1 and Next, the step is 2 of n, and the caption gives the sentence of that step.
   "On the map" removes the board.
7. axe-core 4.14.0 finds no serious or critical violation with the States view and its
   panel, and with the sequence diagram. The page has no script error.
8. On the fixture with no state machine, the script hides the States button, and the page
   has no script error.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_canvas_access import AXE_VERSION, no_axe
from test_canvas_browser import browser
from test_canvas_page import _made

from systemap import canvas_data, canvas_page, config, facts_file, nest

ROOT = Path(__file__).resolve().parent
DRIVER = ROOT / "canvas_board.js"
REPO = ROOT.parent


def _drive(mode: str, page: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), mode, str(page)], capture_output=True, text=True, timeout=600
    )
    assert proc.returncode == 0, proc.stderr
    return dict(json.loads(proc.stdout))


@pytest.fixture(scope="module")
def self_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    cfg = config.load(REPO)
    tree = nest.load(cfg)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    out = tmp_path_factory.mktemp("board") / "index.html"
    data = canvas_data.build(cfg, tree, facts)
    out.write_text(canvas_page.build(canvas_page.tree_theme(cfg, tree), data), encoding="utf-8")
    return out


@pytest.fixture(scope="module")
def states_run(self_page: Path) -> dict[str, Any]:
    return _drive("--states", self_page)


@pytest.fixture(scope="module")
def diagram_run(self_page: Path) -> dict[str, Any]:
    return _drive("--diagram", self_page)


def test_the_states_view_draws_the_machine(states_run: dict[str, Any]) -> None:
    """Acceptance 1, 2 and 3."""
    out = states_run
    first = out["machines"][0]
    assert out["errors"] == [] and out["button"] is True
    shown = out["open"]
    assert shown["mode"] == "states" and shown["board"]["a"] == 1
    assert shown["board"]["machine"] == first["id"]
    for state in first["st"]:
        assert state["id"] in shown["texts"]
    for t in first["tr"]:
        assert t["l"] in shown["texts"]
    assert shown["hits"] == len(first["st"]) + len(first["tr"])
    assert shown["caption"]["k"] == first["n"]
    assert out["wheel"] == shown["camera"]
    panel = out["list"]["panel"]
    assert panel["title"] == first["n"]
    assert len(panel["buttons"]) == len(first["st"]) + len(first["tr"])


def test_a_transition_leads_to_its_flow_and_its_sequence(states_run: dict[str, Any]) -> None:
    """Acceptance 4."""
    out = states_run
    t = out["machines"][0]["tr"][0]
    chosen = out["transition"]
    assert chosen["board"]["tr"] == 0 and chosen["caption"]["s"] == t["c"]
    src, dst, artifact = out["flows"][t["f"]]
    assert f"Show the flow on the map: {src} to {dst}, {artifact}" in chosen["panel"]["buttons"]
    assert any(b.startswith("Show the sequence: ") for b in chosen["panel"]["buttons"])
    assert out["flow"]["mode"] == "map" and out["flow"]["board"]["a"] == 0
    assert out["flow"]["layer"] in ("system", "control", "all")
    assert out["sequence"]["mode"] == "sequences"
    assert out["sequence"]["seq"]["id"] == out["sq"][t["q"]]


def test_the_select_gives_the_second_machine(states_run: dict[str, Any]) -> None:
    """Acceptance 5."""
    second = states_run["machines"][1]
    shown = states_run["second"]
    assert shown["board"]["machine"] == second["id"]
    for state in second["st"]:
        assert state["id"] in shown["texts"]
    assert shown["panel"]["title"] == second["n"]


def test_a_sequence_shows_as_a_diagram(diagram_run: dict[str, Any]) -> None:
    """Acceptance 6."""
    out = diagram_run
    assert out["errors"] == []
    assert out["map"]["board"]["a"] == 0 and out["map"]["board"]["form"] == "map"
    shown = out["diagram"]
    assert shown["board"]["a"] == 1 and shown["board"]["form"] == "diagram"
    assert out["pressed"] == ["false", "true"]
    seq = out["sq"][shown["seq"]["id"] and [q["id"] for q in out["sq"]].index(shown["seq"]["id"])]
    for step in seq["s"]:
        if step["f"] >= 0:
            src, dst, artifact = out["flows"][step["f"]]
            assert src in shown["texts"] and dst in shown["texts"]
            assert artifact in shown["texts"]
    step = out["step"]
    assert step["seq"]["steps"] is True and step["seq"]["s"] == 1
    assert step["caption"]["s"] == seq["s"][1]["y"]
    assert out["back"]["board"]["a"] == 0 and out["back"]["board"]["form"] == "map"


def test_axe_core_finds_no_issue_with_a_board(
    states_run: dict[str, Any], diagram_run: dict[str, Any]
) -> None:
    """Acceptance 7."""
    for found in (states_run["axe"], diagram_run["axe"]):
        if found is None:
            no_axe("axe-core is not in NODE_PATH")
        assert found["version"] == AXE_VERSION
        assert found["violations"] == []


def test_a_page_with_no_state_machine_hides_the_view(tmp_path: Path) -> None:
    """Acceptance 8."""
    nested = _made(tmp_path, '[render]\npage = "canvas"\n') / "docs" / "map" / "index.html"
    out = _drive("--none", nested)
    assert out["errors"] == [] and out["hidden"] is True
    assert out["state"]["board"]["machine"] is None
