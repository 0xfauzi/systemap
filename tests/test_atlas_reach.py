"""The reach of the Focus view of the atlas page (`REACH` in `atlas_focus`), in Node.

The test runs the script part `REACH` of the page on small graphs, in Node with no browser.
It skips when Node is not there, except when SYSTEMAP_BROWSER_TESTS is "required". Then it
fails.

Acceptance values, written before the first run on 2026-11-19:

1. The graph a -> b -> c -> a, c -> d, e -> a, a -> d has a cycle through a. The reach of a
   in the direction of the flows is b at 1 step, d at 1 step (the direct flow is shorter
   than the path through c) and c at 2 steps. The card a is not in its own reach.
2. The reach of a against the direction of the flows is c and e at 1 step and b at 2
   steps. Again a is not in it.
3. atSteps gives the cards at a count of steps in the order of the reach.
4. A card with no flow has an empty reach, and a card on a loop of two cards (x -> y -> x)
   reaches only the other card.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any

import pytest

from systemap import atlas_focus

CASES = {
    "cycle": (
        [("a", "b"), ("b", "c"), ("c", "a"), ("c", "d"), ("e", "a"), ("a", "d")],
        "a",
    ),
    "none": ([("a", "b")], "z"),
    "pair": ([("x", "y"), ("y", "x")], "x"),
}

HARNESS = """
var cases = CASES_JSON, out = {};
Object.keys(cases).forEach(function (k) {
  var flows = cases[k][0].map(function (p) { return {s: p[0], t: p[1]}; }), id = cases[k][1];
  var dn = reachOf(flows, id, 's', 't'), up = reachOf(flows, id, 't', 's');
  out[k] = {dn: dn, up: up, dn1: atSteps(dn, 1), dn2: atSteps(dn, 2), up1: atSteps(up, 1)};
});
process.stdout.write(JSON.stringify(out));
"""


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        if os.environ.get("SYSTEMAP_BROWSER_TESTS") == "required":
            pytest.fail("Node is necessary for the test of the reach.")
        pytest.skip("the test of the reach needs Node")
    return node


@pytest.fixture(scope="module")
def reach() -> dict[str, Any]:
    script = atlas_focus.REACH + HARNESS.replace("CASES_JSON", json.dumps(CASES))
    proc = subprocess.run(
        [_node(), "-e", script], capture_output=True, text=True, timeout=60, check=False
    )
    assert proc.returncode == 0, proc.stderr
    return dict(json.loads(proc.stdout))


def test_the_reach_follows_the_flows_on_a_cycle(reach: dict[str, Any]) -> None:
    out = reach["cycle"]
    assert out["dn"] == {"b": 1, "d": 1, "c": 2}
    assert "a" not in out["dn"]


def test_the_reach_against_the_flows(reach: dict[str, Any]) -> None:
    out = reach["cycle"]
    assert out["up"] == {"c": 1, "e": 1, "b": 2}
    assert "a" not in out["up"]


def test_the_cards_at_a_count_of_steps(reach: dict[str, Any]) -> None:
    out = reach["cycle"]
    assert out["dn1"] == ["b", "d"]
    assert out["dn2"] == ["c"]
    assert out["up1"] == ["c", "e"]


def test_the_small_cases(reach: dict[str, Any]) -> None:
    assert reach["none"]["dn"] == {}
    assert reach["none"]["up"] == {}
    assert reach["pair"]["dn"] == {"y": 1}
    assert reach["pair"]["up"] == {"y": 1}
