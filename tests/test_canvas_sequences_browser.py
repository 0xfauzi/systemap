"""The Sequences view of the canvas page in a browser (`page_canvas_sequences`).

The test drives real canvas pages in the Chromium of Playwright (tests/canvas_sequences.js):
the fixture of tests/canvas_sequenced.py (a top map and the nested map Gateway, each with
sequences), the same fixture with a step that names no flow (`_minus_page`), and the
self-map of this repository (16 sequences and 69 steps). The test skips when Node, the
Playwright package or axe-core is not there, except when SYSTEMAP_BROWSER_TESTS is
"required" (the CI job canvas-browser). Then it fails.

Acceptance values, written before the first run:

3. From the top map, a choice of a sequence of the nested map Gateway in the listbox (the
   arrow keys and Enter) moves the camera to the fit of Gateway: the camera is
   `systemapCanvas.fit("Gateway")`, and the frame of the map is in the free box of the
   screen (the screen less the bands of `layout().gutters`). The flows of the map with an
   alpha of 0.4 or more in the frame are exactly the flows of the steps, and the other
   flows have the alpha 0.16. The step numbers are on exactly the flows of the steps. In
   the Steps mode, after Start at step 1, each Next and Previous, the cards of the flow of
   the step are in the free box, the count gives "Step k of n", and the live region gives
   "Step k of n:" and the sentence of the step. A step with no flow frames its acting
   components. On the self-map, for each sequence, in the Whole route and at each step,
   the flows with an alpha of 0.4 or more are exactly the flows of the steps, the flows of
   the later steps have the alpha 0.4, and the flows of the earlier steps and of the
   current step have the alpha 1.
4. Each change fades: without reduced motion, the alpha of each card, flow and mark of the
   route changes by 0.25 or less between two frames, and a change by 1 takes 160 ms or more
   (a tolerance of 5 percent for the time of the frames). With the reduced motion of the
   system and of the page, each value is a value of the end of a change (no value between),
   and the camera after one frame is the camera at the end of each move.
5. Each control of the toolbar that is not disabled is reachable by Tab from the view
   button, has a name and a visible focus outline of 2 px or more. In the listbox, the
   arrow keys, Home, End, +, - and F move the keyboard focus between the options and do not
   move the camera. Escape closes the list, gives the focus to the chooser, and does not go
   out of the map (`goOut`). On the canvas, an arrow key still moves the camera.
   Added on 2026-11-07 (U4 in bench/jev/README.md): after Enter on Start at step 1, on Next
   to the last step and on End sequence, the keyboard focus is on Next, Previous and Start
   at step 1. It does not go to the body of the page.
6. axe-core 4.14.0 finds no serious or critical violation with the toolbar shown in the
   Whole route, in the Steps mode and with the list open, at 1440 x 900 and 390 x 844
   pixels, in the light and the dark scheme. At 390 x 844 with a touch screen, each control
   of the toolbar and each option is 44 x 44 pixels or more, the scroll width is 390
   pixels, the scroll position is 0, the toolbar does not scroll, and the list is in the
   screen. The page has no script error.
"""

from __future__ import annotations

import functools
import json
import subprocess
from pathlib import Path
from typing import Any

import canvas_sequenced
import pytest
from conftest import write_tree
from test_canvas_access import AXE_VERSION, no_axe
from test_canvas_browser import browser

from systemap import canvas_data, canvas_page, config, facts_file, nest
from systemap.cli import main

ROOT = Path(__file__).resolve().parent
DRIVER = ROOT / "canvas_sequences.js"
REPO = ROOT.parent
DIM, LATER = 0.16, 0.4


def _drive(*args: str) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), *args], capture_output=True, text=True, timeout=600
    )
    assert proc.returncode == 0, proc.stderr
    return dict(json.loads(proc.stdout))


def _built(root: Path) -> tuple[config.Config, nest.Tree, dict[str, Any]]:
    write_tree(root, canvas_sequenced.files())
    for command in ("place", "extract", "render"):
        assert main(["--root", str(root), command]) == 0
    cfg = config.load(root)
    return cfg, nest.load(cfg), facts_file.read_facts(cfg.facts_path, cfg.root)


@pytest.fixture(scope="module")
def fixture_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("seq")
    _built(root)
    return root / "docs" / "map" / "index.html"


@pytest.fixture(scope="module")
def minus_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The fixture with a second step in `serve` that names no flow and has the acting
    component Views. A model check refuses such a step, so it is put in the canvas data."""
    root = tmp_path_factory.mktemp("minus")
    cfg, tree, facts = _built(root)
    data = canvas_data.build(cfg, tree, facts)
    serve = data["maps"][1]["sq"][0]
    serve["s"].insert(1, {"f": -1, "a": ["Views"], "y": "The views make the page."})
    out = root / "minus.html"
    out.write_text(canvas_page.build(canvas_page.tree_theme(cfg, tree), data), encoding="utf-8")
    return out


@pytest.fixture(scope="module")
def self_page(tmp_path_factory: pytest.TempPathFactory) -> Path:
    cfg = config.load(REPO)
    tree = nest.load(cfg)
    data = canvas_data.build(cfg, tree, facts_file.read_facts(cfg.facts_path, cfg.root))
    out = tmp_path_factory.mktemp("self") / "index.html"
    out.write_text(canvas_page.build(canvas_page.tree_theme(cfg, tree), data), encoding="utf-8")
    return out


def _data(page: Path) -> dict[str, Any]:
    text = page.read_text(encoding="utf-8")
    body = text.split('<script type="application/json" id="canvas-data">', 1)[1]
    return dict(json.loads(body.split("</script>", 1)[0]))


def _steps(page: Path, map_id: str, seq: str) -> list[dict[str, Any]]:
    m = next(x for x in _data(page)["maps"] if x["id"] == map_id)
    return list(next(j for j in m["sq"] if j["id"] == seq)["s"])


def _close(a: dict[str, float], b: dict[str, float]) -> bool:
    return all(abs(a[k] - b[k]) <= 1e-6 * max(1.0, abs(b[k])) for k in ("x", "y", "k"))


def _in_free_box(box: list[float], run: dict[str, Any]) -> bool:
    g = run["layout"]["gutters"]
    w, h = run["width"], run["height"]
    x, y, bw, bh = box
    return (
        x >= g["x"] - 1
        and y >= g["top"] - 1
        and x + bw <= w - g["x"] + 1
        and y + bh <= h - g["bottom"] + 1
    )


def _flows_shown(drawn: dict[str, Any], minimum: float) -> set[int]:
    return {int(i) for i, a in drawn["flows"].items() if a >= minimum - 1e-9}


def _expected(steps: list[dict[str, Any]], at: int | None) -> dict[int, float]:
    """The alpha of each flow of the route in the Whole route (`at` None) or at step `at`."""
    out: dict[int, float] = {}
    for k, st in enumerate(steps):
        if st["f"] < 0:
            continue
        a = LATER if at is not None and k > at else 1.0
        out[st["f"]] = max(out.get(st["f"], 0.0), a)
    return out


def _route_frame(drawn: dict[str, Any], want: dict[int, float]) -> None:
    alphas = {int(i): a for i, a in drawn["flows"].items()}
    assert {i for i, a in alphas.items() if a >= LATER - 1e-9} == set(want)
    assert all(abs(alphas[i] - a) < 1e-9 for i, a in want.items()), (alphas, want)
    assert all(abs(a - DIM) < 1e-9 for i, a in alphas.items() if i not in want)
    numbered = {m["f"] for m in drawn["marks"] if m["kind"] != "wide" and m["a"] > 0}
    assert numbered == set(want)


@pytest.mark.parametrize("phone", [False, True])
def test_a_choice_moves_the_camera_and_shows_the_route(fixture_page: Path, phone: bool) -> None:
    """Acceptance 3."""
    found = _drive(
        "--choose", str(fixture_page), "Gateway", "serve", *(["--phone"] if phone else [])
    )
    assert found["errors"] == []
    assert all(_close(c, found["cams"][0]) for c in found["cams"])
    chosen = found["chosen"]
    assert chosen["seq"]["map"] == "Gateway" and chosen["chain"] == ["Gateway"]
    assert _close(chosen["camera"], chosen["fit"])
    assert _in_free_box(chosen["frame"], chosen)
    assert chosen["said"].startswith("Sequence: Serve a request.")
    steps = _steps(fixture_page, "Gateway", "serve")
    _route_frame(chosen["drawn"], _expected(steps, None))
    runs = found["steps"]
    assert [r["seq"]["s"] for r in runs] == [0, 1, 0]
    for run in runs:
        k, n = run["seq"]["s"], len(steps)
        assert run["count"] == f"Step {k + 1} of {n}"
        assert run["said"].endswith(f"Step {k + 1} of {n}: {steps[k]['y']}")
        assert len(run["cards"]) == 2 and all(run["inside"]), run["cards"]
        if "drawn" in run:
            _route_frame(run["drawn"], _expected(steps, k))
            assert [m["f"] for m in run["drawn"]["marks"] if m["kind"] == "wide"] == [steps[k]["f"]]


def test_a_step_with_no_flow_frames_its_acting_components(minus_page: Path) -> None:
    """Acceptance 3: the step with the flow index -1."""
    found = _drive("--choose", str(minus_page), "Gateway", "serve")
    assert found["errors"] == []
    middle = found["steps"][1]
    assert middle["seq"]["s"] == 1
    assert [c["id"] for c in middle["cards"]] == ["Views"] and all(middle["inside"])
    assert middle["said"].endswith("Step 2 of 3: The views make the page.")


def test_each_route_of_the_self_map_shows_its_flows(self_page: Path) -> None:
    """Acceptance 3, on the self-map."""
    found = _drive("--routes", str(self_page), "")
    assert found["errors"] == []
    m = _data(self_page)["maps"][0]
    assert len(found["routes"]) == len(m["sq"]) == 16
    count = 0
    for run, seq in zip(found["routes"], m["sq"], strict=True):
        assert run["whole"]["seq"]["id"] == seq["id"]
        _route_frame(run["whole"]["drawn"], _expected(seq["s"], None))
        assert len(run["steps"]) == len(seq["s"])
        for k, step in enumerate(run["steps"]):
            assert step["seq"]["s"] == k
            _route_frame(step["drawn"], _expected(seq["s"], k))
            count += 1
    assert count == 69


@functools.cache
def _faded(page: Path) -> dict[str, Any]:
    return _drive("--fade", str(page), "Gateway", "serve")


def test_each_change_fades(fixture_page: Path) -> None:
    """Acceptance 4, without reduced motion."""
    run = _faded(fixture_page)["none"]
    assert run["errors"] == []
    assert run["runs"] >= 10
    assert 0 < run["most"] <= 0.25
    assert run["msPerUnit"] >= 160 * 0.95


@pytest.mark.parametrize("motion", ["system", "page"])
def test_with_reduced_motion_each_change_occurs_at_one_time(
    fixture_page: Path, motion: str
) -> None:
    """Acceptance 4, with reduced motion."""
    run = _faded(fixture_page)[motion]
    assert run["errors"] == []
    assert set(run["values"]) <= {0, DIM, 0.32, LATER, 1}
    for move in run["moves"]:
        assert _close(move["one"], move["two"]), move


def _check_tabs(order: list[dict[str, Any]], ids: list[str]) -> None:
    """Tab goes through the controls `ids` of the toolbar, each with a name and a visible
    focus outline, and then to the Find button of the header (`page_canvas_find`)."""
    inside = [x for x in order if "id" in x]
    assert [x["id"] for x in inside] == ids
    assert all(
        x["name"] and x["visible"] and x["width"] >= 2 and x["style"] != "none" for x in inside
    )
    assert order[-1] == {"out": "find-open"}


def test_the_keys_of_the_toolbar_and_the_listbox(fixture_page: Path) -> None:
    """Acceptance 5."""
    found = _drive("--keys", str(fixture_page), "Gateway")
    assert found["errors"] == []
    _check_tabs(found["whole"], ["cseq-pick", "cseq-whole", "cseq-steps", "cseq-start"])
    _check_tabs(found["steps"], ["cseq-pick", "cseq-whole", "cseq-steps", "cseq-next", "cseq-end"])
    keys = found["list"]
    before = keys["before"]["cam"]
    assert keys["opened"]["list"] and keys["opened"]["at"] == "option"
    focus = [k["focus"] for k in keys["keys"]]
    assert len(set(focus)) > 1
    for step in [
        keys["opened"],
        *keys["keys"],
        keys["escaped"],
        keys["escapedAgain"],
        keys["right"],
    ]:
        assert _close(step["cam"], before) and step["chain"] == ["Gateway"]
    assert all(k["list"] and k["at"] == "option" for k in keys["keys"])
    assert not keys["escaped"]["list"] and keys["escaped"]["at"] == "cseq-pick"
    assert keys["right"]["at"] == "cseq-whole"
    assert not _close(found["canvas"]["cam"], before)
    assert found["focus"] == {"start": "cseq-next", "last": "cseq-prev", "end": "cseq-start"}


def test_access_and_the_phone(fixture_page: Path) -> None:
    """Acceptance 6."""
    found = _drive("--access", str(fixture_page), "Gateway", "serve")
    for run in found["runs"]:
        assert run["errors"] == []
        _check_axe(run)
        if run["screen"] == "390x844":
            _check_phone(run)


def _check_axe(run: dict[str, Any]) -> None:
    for name, axe in run["axe"].items():
        if axe is None:
            no_axe(f"the access test needs axe-core {AXE_VERSION} for Node")
        assert axe["version"] == AXE_VERSION, name
        bad = [v for v in axe["violations"] if v["impact"] in ("serious", "critical")]
        assert bad == [], (run["screen"], run["scheme"], name, bad)


def _check_phone(run: dict[str, Any]) -> None:
    small = [b for b in run["boxes"] if b["w"] < 44 or b["h"] < 44]
    assert run["boxes"] and small == []
    s = run["scroll"]
    assert (s["scrollWidth"], s["scrollX"], s["bar"]) == (390, 0, 0)
    assert s["list"] <= 390
