"""The page from the keyboard, driven under Node with the readings table.

`tests/page_driver.js` loads a rendered page into a DOM of its own, runs
the page's scripts as written, presses the keys, and reports what the
state did. Node is on every runner the workflow uses; where it is not on
the PATH the test skips and says so, rather than testing a stand-in.

What is asserted: the left and right arrows walk the readings in the
order of the readings table the page carries (`_meta.readings`, decided in
Python) and wrap through All; the cards are written in reading order (row
by row, left to right) and each takes focus; Enter on a focused card opens
its wheel with one focusable spoke per edge; Escape closes the wheel and
hands focus back to the card; a journey takes the arrows while it is on
and Escape ends it; with prefers-reduced-motion the framing sets the view
once per framing, never tweened; the header and the strip count the cards
the same way (components, then actors named apart); and the focus ring is
drawn in the accent token, whose value each scheme's root block sets.
"""

from __future__ import annotations

import json
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
    proc = subprocess.run(args, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    report: dict[str, object] = json.loads(proc.stdout)
    return report


def sample_page(sample: Sample, tmp_path: Path, scheme: str = "warm") -> Path:
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
    """The header and the strip count the same way: the cards that are code
    as components, the actors named apart when there are any."""
    kinds = report["kinds"]
    assert isinstance(kinds, dict) and kinds
    n_actors = sum(1 for k in kinds.values() if k == "actor")
    header = report["header"]
    assert isinstance(header, str)
    assert f": {counted(len(kinds) - n_actors, n_actors)}, " in header, header
    assert n_actors > 0, "the sample and the self-map both have actors"
    strips = report["strips"]
    assert isinstance(strips, dict) and len(strips) >= 3
    for layer, strip in strips.items():
        if layer == "all":
            continue  # All lists the layers, not the cards, and counts nothing
        assert isinstance(strip, dict)
        listed = strip["listed"]
        assert isinstance(listed, list) and listed, layer
        actors = sum(1 for c in listed if c["kind"] == "actor")
        says = strip["says"]
        assert isinstance(says, str)
        assert says.endswith(f". {counted(len(listed) - actors, actors)}; click one."), (
            layer,
            says,
        )
    assert any(
        any(c["kind"] == "actor" for c in s["listed"])  # type: ignore[index]
        for layer, s in strips.items()
        if layer != "all"
    ), "some reading lists an actor, so the actor phrase is exercised"


def check_keyboard(report: dict[str, object]) -> None:
    layers = report["layers"]
    assert isinstance(layers, list) and len(layers) >= 3
    assert report["readings"] == layers, "the arrows walk the readings table"
    assert report["buttons"] == [*layers, "all"]
    assert report["initialLayer"] == layers[0]
    arrows = report["arrows"]
    assert isinstance(arrows, list)
    assert [a["layer"] for a in arrows] == [layers[1], layers[2], layers[1], layers[0], "all"]
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
    assert enter["dock"] in ("left", "right")
    assert enter["spokes"] == enter["edges"] and enter["edges"] > 1
    assert enter["spokesFocusable"] is True
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
    assert j["started"] == f"1/{steps}" and j["stripHidden"] is False
    assert j["afterRight"] == (f"2/{steps}" if steps > 1 else f"1/{steps}")
    assert j["layerUnchanged"] is True, "the arrows step the journey, not the reading"
    assert j["afterLeft"] == f"1/{steps}" and j["afterLeftAtStart"] == f"1/{steps}"
    assert j["stepButtons"] == steps
    assert j["ended"] == "" and j["stripHiddenAfter"] is True
    assert j["selectReset"] == "" and j["journeyState"] is None


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
    assert ":focus-visible{outline:2px solid var(--accent);outline-offset:2px}" in html
    assert (
        "#schematic .node:focus-visible .node__box{stroke:var(--accent);stroke-width:2.6}" in html
    )
    assert ".systemap-w__spoke:focus-visible .systemap-w__name{fill:var(--accent)}" in html
    assert (
        "@media (prefers-reduced-motion:reduce){*{transition:none!important;"
        "animation:none!important}}" in html
    )
    assert "@media (prefers-reduced-motion:reduce){#schematic .flow.hot{animation:none" in html
    assert "From the keyboard: Tab moves across the cards, Enter opens one" in html


def test_the_schemes_accents_differ() -> None:
    accents = {t["accent"] for t in theme_mod.SCHEMES.values()}
    assert len(accents) == len(theme_mod.SCHEMES)
