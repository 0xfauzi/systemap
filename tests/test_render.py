from __future__ import annotations

import json
import re

from conftest import Sample, sample_model

from systemap import check, figure, page
from systemap import theme as theme_mod
from systemap.model import all_layers
from systemap.schematic import render as render_schematic


def test_page_is_small_and_self_contained(sample: Sample) -> None:
    assert sample.facts["components"], "the extractor read the sample tree"
    html = page.build(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {"has_change": False}
    )
    assert len(html.encode("utf-8")) < 300 * 1024
    assert "<script src" not in html
    assert "<link" not in html
    assert "<img" not in html
    assert "@import" not in html
    assert "url(http" not in html
    assert "fetch(" not in html
    # The only URL on the page is the SVG namespace.
    for url in set(re.findall(r"https?://[^\s\"'<)]+", html)):
        assert url.startswith("http://www.w3.org/"), url
    assert "<title>sample system map</title>" in html
    assert "OUTSIDE THE SYSTEM" in html
    assert 'id="schematic"' in html


def test_schematic_reports_layout_and_detail(sample: Sample) -> None:
    model, meaning = sample.model, sample.meaning
    svg, detail = render_schematic(model, meaning, sample.theme, sample.facts)
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
    assert (result.coverage.mapped, result.coverage.total, result.coverage.ignored) == (4, 4, 1)
    assert result.ok
    lines = check.report(sample.model, result)
    assert "coverage: 4/4 modules mapped, 1 ignored" in lines
    assert any(line.startswith("map layout: clean") for line in lines)
    # A label on a shorter segment was once a note on a clean check; it is
    # not a rule, so it is not printed.
    assert not any("note:" in line for line in lines)
    assert not hasattr(result, "notes")


def test_default_theme_colours_every_layer() -> None:
    model, meaning = sample_model()
    layers = all_layers(model, meaning)
    t = theme_mod.resolve({}, layers)
    assert set(t["layers"]) == {layer.id for layer in layers}
    assert len(set(t["layers"].values())) == len(layers), "every layer has its own hue"
    # The standard layers are named in the scheme; the model's own take the
    # palette from its first entry, whatever their position.
    assert t["layers"]["data"] == theme_mod.STANDARD_LAYERS_DARK["data"]
    assert t["layers"]["record"] == theme_mod.LAYER_PALETTE[0]
    assert t["layers"]["memory"] == theme_mod.LAYER_PALETTE[1]
    custom = theme_mod.resolve({"layers": {"record": "#123456"}, "accent": "#ABCDEF"}, layers)
    assert custom["layers"]["record"] == "#123456"
    assert custom["layers"]["memory"] == theme_mod.LAYER_PALETTE[0]
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
    assert "in the plan's reach" in html
    assert "IN REACH" in html
    assert "svg.systemap" in html
    assert "endstate" not in html and "planned" not in html


def test_light_scheme_derives_from_the_same_palette() -> None:
    model, meaning = sample_model()
    layers = all_layers(model, meaning)
    dark = theme_mod.resolve({}, layers)
    light = theme_mod.resolve({"scheme": "light"}, layers)
    assert dark["bg"] == theme_mod.GRAPHITE and dark["ink"] == theme_mod.INK
    assert light["bg"] == theme_mod.PAPER and light["ink"] == theme_mod.INK_ON_PAPER
    assert dark["accent"] == theme_mod.AMBER and dark["reach"] == theme_mod.AMBER
    assert dark["steel"] == theme_mod.STEEL
    assert dark["layers"]["data"] == theme_mod.STANDARD_LAYERS_DARK["data"]
    assert light["layers"]["data"] == theme_mod.STANDARD_LAYERS_LIGHT["data"]
    # The same token names exist in both schemes, so an override written
    # for one applies to the other.
    assert set(dark) == set(light)
    assert set(dark["state"]) == set(light["state"])
    assert set(dark["container"]) == set(light["container"])
    assert set(dark["layers"]) == set(light["layers"])
    assert dark["marks"] == light["marks"] == theme_mod.KIND_MARKS
    custom = theme_mod.resolve({"scheme": "light", "accent": "#ABCDEF"}, layers)
    assert custom["accent"] == "#ABCDEF"
    assert custom["bg"] == theme_mod.PAPER
    assert "color-scheme:light" in theme_mod.css_vars(light)
