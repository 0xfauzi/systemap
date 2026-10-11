"""The Node harness runs the generated page keyboard controls.

Acceptance: each component flow has one button in the inspector. Focus on a
button previews its flow. Escape closes the inspector and returns focus to
the card. Sequence arrows select the current step.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import Sample

from systemap import page
from systemap import theme as theme_mod
from systemap.model import all_layers

ROOT = Path(__file__).resolve().parent.parent
DRIVER = ROOT / "tests" / "page_driver.js"
SELF_MAP = ROOT / "docs" / "map" / "index.html"

needs_node = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node is not on PATH; the keyboard test drives the page's script under Node",
)


def drive(html: Path, reduced: bool = False) -> dict[str, object]:
    args = [shutil.which("node") or "node", str(DRIVER), str(html)]
    if reduced:
        args.append("--reduced")
    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert proc.returncode == 0, proc.stderr
    report: dict[str, object] = json.loads(proc.stdout)
    return report


def sample_page(sample: Sample, tmp_path: Path, scheme: str = "dark") -> Path:
    tokens = theme_mod.resolve({"scheme": scheme}, all_layers(sample.model, sample.meaning))
    html = page.build(
        sample.cfg, sample.model, sample.meaning, tokens, sample.facts, {"has_change": False}
    )
    out = tmp_path / f"{scheme}.html"
    out.write_text(html, encoding="utf-8")
    return out


def counted(n_components: int, n_actors: int) -> str:
    out = f"{n_components} component{'' if n_components == 1 else 's'}"
    if n_actors:
        out += f" and {n_actors} actor{'' if n_actors == 1 else 's'}"
    return out


def check_counts(report: dict[str, object]) -> None:
    """The header summary and the readout count the same way: the cards that
    are code as components, the actors named apart when there are any."""
    kinds = report["kinds"]
    assert isinstance(kinds, dict) and kinds
    n_actors = sum(1 for k in kinds.values() if k == "actor")
    header = report["header"]
    assert isinstance(header, str)
    assert f": {counted(len(kinds) - n_actors, n_actors)}, " in header, header
    assert n_actors > 0, "the sample and the self-map both have actors"
    readouts = report["readouts"]
    assert isinstance(readouts, dict) and len(readouts) >= 3
    n_components = len(kinds) - n_actors
    plural = "" if n_components == 1 else "s"
    assert str(readouts["structure"]).startswith(f"{n_components} component{plural}")
    for layer, says in readouts.items():
        if layer != "structure":
            assert re.match(r"\d+ flows? (· \d+ groups? )?(· \d+ actors?)?", str(says)), says
    assert any("actor" in str(says) for says in readouts.values())


def check_journey_foot(j: dict[str, object]) -> None:
    """Under the step: where the walk starts, what backs this step, and
    whether an agent wrote it and nobody has read it against the code."""
    foot = j["foot"]
    assert isinstance(foot, str)
    assert j["stepEvidence"] and str(j["stepEvidence"]) in foot
    if j["starts"]:
        assert str(j["starts"]) in foot, "the walk says which way in it begins at"
    assert ("not yet confirmed" in foot) is j["drafted"]


def check_keyboard(report: dict[str, object]) -> None:
    layers = report["layers"]
    assert isinstance(layers, list) and len(layers) >= 3
    assert report["readings"] == layers, "the readings table follows the layers"
    # The tabs start with System context; the arrows walk the tabs.
    tabs = report["buttons"]
    assert tabs == ["system", *[layer for layer in layers if layer != "system"], "all"]
    assert isinstance(tabs, list)
    assert report["initialLayer"] == tabs[0]
    arrows = report["arrows"]
    assert isinstance(arrows, list)
    assert [a["layer"] for a in arrows] == [tabs[1], tabs[2], tabs[1], tabs[0], "all"]
    for a in arrows:
        assert a["pressed"] == [a["layer"]], "one layer button reads pressed"
    assert report["arrowInSelectPrevented"] is False
    assert report["layerAfterSelectArrow"] == "all", "the select keeps its arrows"
    check_counts(report)

    order = report["nodeOrder"]
    assert isinstance(order, list) and order
    keys = [(n["y"], n["x"]) for n in order]
    assert keys == sorted(keys), "cards are written row by row, left to right"
    for n in order:
        assert n["tabindex"] == "0" and n["role"] == "button", n
        assert str(n["label"]).startswith(f"{n['id']}, "), n
    assert report["svgTabindex"] == "0"

    enter = report["enter"]
    assert isinstance(enter, dict)
    assert enter["prevented"] is True
    assert enter["focus"] == enter["id"]
    assert enter["drawerHidden"] is False and enter["panelOn"] is True
    assert enter["panelState"] == "open"
    assert enter["choices"] == enter["edges"] and enter["edges"] > 1
    assert enter["choicesFocusable"] is True
    assert enter["hash"] == f"#{enter['id']}"
    assert enter["activeElement"] == enter["id"], "focus stays on the card"
    assert isinstance(report["peekOnFocus"], int) and report["peekOnFocus"] >= 0

    escape = report["escape"]
    assert isinstance(escape, dict)
    assert escape["prevented"] is True
    assert escape["focus"] == ""
    assert escape["drawerHidden"] is True and escape["panelOn"] is False
    assert escape["panelEmpty"] is True
    assert escape["activeElement"] == enter["id"], "focus returns to the card"
    assert escape["hash"] == "", "the hash is cleared with the selection"
    assert report["spaceOpens"] is True

    j = report["journey"]
    assert isinstance(j, dict) and j["count"] >= 1
    steps = j["steps"]
    # The select opens the whole route; the right arrow starts the steps.
    assert j["mode"] == "trace" and j["whole"]["whole"] is True
    assert j["started"] == f"Step 1 of {steps}" and j["stripHidden"] is False
    assert j["afterRight"] == (f"Step 2 of {steps}" if steps > 1 else f"Step 1 of {steps}")
    assert j["layerMatchesStep"] is True, "the active layer follows the exact journey edge"
    assert j["afterLeft"] == f"Step 1 of {steps}"
    assert j["afterLeftAtStart"] == f"Step 1 of {steps}"
    assert j["stepButtons"] == steps
    check_journey_foot(j)
    # Escape goes back to the whole route, then ends the sequence.
    assert j["escapeOnce"]["whole"] is True and j["stripHiddenAfterOne"] is True
    assert j["ended"] is None and j["modeAfter"] == "understand"


@needs_node
def test_sample_page_from_the_keyboard(sample: Sample, tmp_path: Path) -> None:
    report = drive(sample_page(sample, tmp_path))
    check_keyboard(report)
    enter = report["enter"]
    assert isinstance(enter, dict) and enter["viewEventsForFraming"] > 2, (
        "with motion allowed the framing animates"
    )


@needs_node
def test_self_map_page_from_the_keyboard() -> None:
    assert SELF_MAP.is_file(), "the committed page; run systemap refresh"
    check_keyboard(drive(SELF_MAP))


@needs_node
def test_reduced_motion_frames_without_animation(sample: Sample, tmp_path: Path) -> None:
    report = drive(sample_page(sample, tmp_path), reduced=True)
    check_keyboard(report)
    # Enter frames twice (the figure in the visible map, then the page
    # beside the drawer once it is laid out): two views, no tween between.
    enter = report["enter"]
    assert isinstance(enter, dict) and enter["viewEventsForFraming"] == 2, (
        "prefers-reduced-motion: the view is set, never animated"
    )
    assert "smooth" not in report["scrolls"]


@pytest.mark.parametrize("scheme", list(theme_mod.SCHEMES))
def test_focus_ring_and_reduced_motion_in_every_scheme(
    sample: Sample, tmp_path: Path, scheme: str
) -> None:
    html = sample_page(sample, tmp_path, scheme).read_text(encoding="utf-8")
    accent = theme_mod.SCHEMES[scheme]["accent"]
    assert f"color-scheme:{theme_mod.SCHEMES[scheme]['color_scheme']};" in html
    assert f"--accent:{accent};" in html
    assert ":focus-visible{outline:2px solid var(--ink);outline-offset:3px}" in html
    assert "#schematic .node:focus-visible .node__halo{display:inline;stroke-width:2}" in html
    assert "#schematic .flow.peek{stroke-opacity:1;stroke-width:2.6}" in html
    assert (
        "@media (prefers-reduced-motion:reduce){*{transition:none!important;"
        "animation:none!important}}" in html
    )
    assert (
        "@media (prefers-reduced-motion:reduce){#schematic *{transition:none!important;"
        "animation:none!important}}" in html
    )
    assert "Tab selects cards and flow paths. Enter opens their data." in html


def test_the_schemes_accents_differ() -> None:
    accents = {t["accent"] for t in theme_mod.SCHEMES.values()}
    assert len(accents) == len(theme_mod.SCHEMES)
