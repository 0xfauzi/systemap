from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET

from conftest import Sample, sample_model

from systemap import check, figure, page
from systemap import theme as theme_mod
from systemap.model import DERIVED_LAYERS, all_layers
from systemap.schematic import render as render_schematic


def test_page_is_small_and_self_contained(sample: Sample) -> None:
    assert sample.facts["components"], "the extractor read the sample tree"
    html = page.build(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {"has_change": False}
    )
    # 300 KiB, the Inter subset in the page (18,452 bytes) and 4,076 bytes of additional space.
    # bench/jev/README.md "Map page font" gives the measurements and the decision.
    # The assurance levels add 2,367 bytes. The limit is the next whole KiB above the
    # measured page (bench/jev/README.md, "Assurance levels on the page").
    # The fast route search of the group lines adds 3,465 bytes (bench/jev/README.md,
    # "The route search of the group lines on a large map").
    assert len(html.encode("utf-8")) < 328 * 1024
    assert "<script src" not in html
    # the one <link> is the favicon, inline as a data URI; nothing is fetched
    assert '<link rel="icon" href="data:image/svg+xml,' in html
    assert html.count("<link") == 1
    assert 'href="http' not in html.split("</head>")[0]
    assert "<img" not in html
    assert "@import" not in html
    assert "url(http" not in html
    assert "fetch(" not in html
    # The only URL on the page is the SVG namespace.
    for url in set(re.findall(r"https?://[^\s\"'<)]+", html)):
        assert url.startswith("http://www.w3.org/"), url
    assert "<title>sample system map</title>" in html
    assert "EXTERNAL COMPONENTS" in html
    assert 'id="schematic"' in html
    stage_style = re.search(r"\.stage\{([^}]+)\}", html)
    assert stage_style and "width:100%" in stage_style[1].split(";")


def test_page_styles_have_no_comments_or_line_breaks(sample: Sample) -> None:
    """The build removes CSS comments and line breaks, and keeps the space between values."""
    html = page.build(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {"has_change": False}
    )
    style = html.split("<style>", 1)[1].split("</style>", 1)[0]
    assert "/*" not in style
    assert "\n" not in style
    assert page._compact_css("a{b:1px\n  2px;\n}\n/* c */\nd,\ne{f:0}") == "a{b:1px 2px;}d,e{f:0}"


def test_schematic_reports_layout_and_detail(sample: Sample) -> None:
    model, meaning = sample.model, sample.meaning
    svg, detail = render_schematic(model, meaning, sample.theme, sample.facts)
    assert ET.fromstring(svg).attrib["preserveAspectRatio"] == "xMidYMid meet"
    data = json.loads(detail)
    meta = data["_meta"]
    assert meta["collisions"] == []
    assert len(meta["edges"]) == len(model.flows)
    assert [layer["id"] for layer in meta["layers"]] == [
        layer.id for layer in all_layers(model, meaning)
    ]
    assert meta["layers"][0]["id"] == "structure", "the page opens on Structure"
    states = {cid: rec["state"] for cid, rec in data.items() if cid != "_meta"}
    assert states["Reader"] == "built"
    assert states["Ledger"] == "built"
    assert states["User"] == "actor"
    assert set(states.values()) == {"built", "actor"}, "what is drawn exists"
    assert "tracker" not in data["Writer"] and "issues" not in data["Writer"]
    assert data["Writer"]["rules"] == [1, 2]
    assert svg.count('class="node ') == len(model.components)
    assert "planned" not in svg and "endstate" not in svg
    assert "font-size:10" not in svg


def test_check_passes_on_sample(sample: Sample) -> None:
    result = check.run(
        sample.model,
        sample.meaning,
        sample.theme,
        sample.facts,
        sample.cfg.coverage_ignore,
    )
    assert result.problems == []
    assert (result.through, result.across) == (0, 0)
    assert result.coverage.problems == ()
    assert (result.coverage.mapped, result.coverage.total, result.coverage.ignored) == (5, 5, 0)
    assert result.coverage.markers == 1, "the package root is an empty package marker"
    assert result.ok
    lines = check.report(sample.model, result)
    assert "coverage: 5 of 5 modules mapped, 1 an empty package marker" in lines
    assert any(line.startswith("map layout: has no errors") for line in lines)
    # A label on a shorter segment was once a note on a clean check; it is
    # not a rule, so it is not printed.
    assert not any("note:" in line for line in lines)
    assert not hasattr(result, "notes")


def test_default_theme_colours_every_layer() -> None:
    model, meaning = sample_model()
    layers = all_layers(model, meaning)
    t = theme_mod.resolve({}, layers)
    assert set(t["layers"]) == {layer.id for layer in layers}
    # A derived layer selects lines and has no line color of its own.
    kinds = [lid for lid in t["layers"] if lid not in DERIVED_LAYERS]
    assert len({t["layers"][k] for k in kinds}) == len(kinds), "every kind layer has its own hue"
    # The standard layers are named in the scheme; the model's own take the
    # palette from its first entry, whatever their position.
    assert t["scheme"] == theme_mod.DEFAULT_SCHEME == "dark"
    assert t["layers"]["data"] == theme_mod.STANDARD_LAYERS_DARK["data"]
    assert t["layers"]["record"] == theme_mod.LAYER_PALETTE_DARK[0]
    assert t["layers"]["memory"] == theme_mod.LAYER_PALETTE_DARK[1]
    custom = theme_mod.resolve({"layers": {"record": "#123456"}, "accent": "#ABCDEF"}, layers)
    assert custom["layers"]["record"] == "#123456"
    assert custom["layers"]["memory"] == theme_mod.LAYER_PALETTE_DARK[0]
    assert custom["accent"] == "#ABCDEF"
    assert "--accent:#ABCDEF" in theme_mod.css_vars(custom)


def test_reach_figure(sample: Sample) -> None:
    html, collisions = figure.make(
        sample.cfg,
        sample.model,
        sample.meaning,
        sample.theme,
        sample.facts,
        components=("Parser", "Writer"),
        interactive=True,
    )
    assert collisions == []
    assert html.startswith('<figure data-generated="systemap"')
    assert "components in the plan" in html
    assert "IN REACH" in html
    assert "svg.systemap" in html
    assert not re.search(r'class="node[^\"]*\b(?:endstate|planned)\b', html)


def test_the_two_schemes_share_one_token_table() -> None:
    model, meaning = sample_model()
    layers = all_layers(model, meaning)
    dark = theme_mod.resolve({"scheme": "dark"}, layers)
    light = theme_mod.resolve({"scheme": "light"}, layers)
    assert dark["bg"] == theme_mod.DARK["bg"] and dark["ink"] == theme_mod.DARK["ink"]
    assert light["bg"] == theme_mod.LIGHT["bg"] and light["ink"] == theme_mod.LIGHT["ink"]
    assert dark["reach"] == dark["change"] and light["reach"] == light["change"]
    assert dark["layers"]["data"] == theme_mod.STANDARD_LAYERS_DARK["data"]
    assert light["layers"]["data"] == theme_mod.STANDARD_LAYERS_LIGHT["data"]
    # The same token names exist in both schemes, so an override written
    # for one applies to the other.
    assert set(light) == set(dark)
    assert set(light["state"]) == set(dark["state"])
    assert set(light["container"]) == set(dark["container"])
    assert set(light["layers"]) == set(dark["layers"])
    assert light["marks"] == dark["marks"] == theme_mod.KIND_MARKS
    custom = theme_mod.resolve({"scheme": "light", "accent": "#ABCDEF"}, layers)
    assert custom["accent"] == "#ABCDEF"
    assert custom["bg"] == theme_mod.LIGHT["bg"]
    assert "color-scheme:light" in theme_mod.css_vars(light)
    assert "color-scheme:dark" in theme_mod.css_vars(dark)
    assert theme_mod.resolve({"scheme": "light"}, layers)["scheme"] == "light"
    assert theme_mod.resolve({"scheme": "dark"}, layers)["scheme"] == "dark"
