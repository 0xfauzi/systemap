from __future__ import annotations

import json
import re

from conftest import Sample, sample_model

from systemap import check, figure, page
from systemap import theme as theme_mod
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
    assert [layer["id"] for layer in meta["layers"]] == [layer.id for layer in meaning.layers]
    states = {cid: rec["state"] for cid, rec in data.items() if cid != "_meta"}
    assert states["Reader"] == "built"
    assert states["Ledger"] == "built"
    assert states["User"] == "actor"
    assert set(states.values()) == {"built", "actor"}, "what is drawn exists; nothing is planned"
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


def test_default_theme_colours_every_layer() -> None:
    _, meaning = sample_model()
    t = theme_mod.resolve({}, meaning.layers)
    assert set(t["layers"]) == {layer.id for layer in meaning.layers}
    assert len(set(t["layers"].values())) == len(meaning.layers)
    custom = theme_mod.resolve({"layers": {"work": "#123456"}, "accent": "#ABCDEF"}, meaning.layers)
    assert custom["layers"]["work"] == "#123456"
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
    _, meaning = sample_model()
    dark = theme_mod.resolve({}, meaning.layers)
    light = theme_mod.resolve({"scheme": "light"}, meaning.layers)
    assert dark["bg"] == theme_mod.INK and dark["ink"] == theme_mod.PAPER
    assert light["bg"] == theme_mod.PAPER and light["ink"] == theme_mod.INK
    assert dark["accent"] == theme_mod.AMBER
    assert dark["good"] == theme_mod.TEAL
    assert dark["layers"][meaning.layers[0].id] == theme_mod.TEAL
    # The same token names exist in both schemes, so an override written
    # for one applies to the other.
    assert set(dark) == set(light)
    assert set(dark["state"]) == set(light["state"])
    assert set(dark["container"]) == set(light["container"])
    custom = theme_mod.resolve({"scheme": "light", "accent": "#ABCDEF"}, meaning.layers)
    assert custom["accent"] == "#ABCDEF"
    assert custom["bg"] == theme_mod.PAPER
    assert "color-scheme:light" in theme_mod.css_vars(light)
