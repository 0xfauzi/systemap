from __future__ import annotations

import json
import re

from systemap import check, extract, figure, page
from systemap import theme as theme_mod
from systemap.config import Config
from systemap.model import Meaning, Model
from systemap.schematic import render as render_schematic


def test_page_is_small_and_self_contained(
    example_cfg: Config, example_model: tuple[Model, Meaning]
) -> None:
    model, meaning = example_model
    t = theme_mod.resolve(example_cfg.theme, meaning.layers)
    facts = extract.read_facts(example_cfg.facts_path)
    assert facts, "the example ships its facts"
    html = page.build(example_cfg, model, meaning, t, facts, {"has_change": False})
    assert len(html.encode("utf-8")) < 300 * 1024
    assert "<script src" not in html
    assert "<link" not in html
    assert "<img" not in html
    assert "@import" not in html
    assert "url(http" not in html
    assert "fetch(" not in html
    # The only URLs on the page are the SVG namespace and the tracker links.
    for url in set(re.findall(r"https?://[^\s\"'<)]+", html)):
        assert url.startswith(("http://www.w3.org/", example_cfg.issue_url.split("{")[0])), url
    assert "<title>kstrl system map</title>" in html
    assert "OUTSIDE THE FACTORY" in html
    assert 'id="schematic"' in html


def test_schematic_reports_layout_and_detail(
    example_cfg: Config, example_model: tuple[Model, Meaning]
) -> None:
    model, meaning = example_model
    t = theme_mod.resolve(example_cfg.theme, meaning.layers)
    facts = extract.read_facts(example_cfg.facts_path)
    svg, detail = render_schematic(model, meaning, t, facts, issue_url=example_cfg.issue_url)
    data = json.loads(detail)
    meta = data["_meta"]
    assert meta["collisions"] == []
    assert len(meta["edges"]) == len(model.flows)
    assert [layer["id"] for layer in meta["layers"]] == [layer.id for layer in meaning.layers]
    states = {cid: rec["state"] for cid, rec in data.items() if cid != "_meta"}
    assert states["Pipeline"] == "built"
    assert states["Operator"] == "actor"
    assert "planned" in states.values(), "a roadmap item with no code yet draws as a ghost"
    assert data["Sense"]["tracker"] == "R10.1"
    assert data["Sense"]["issues"] == [
        {"n": "222", "url": "https://github.com/0xfauzi/kstrl/issues/222"}
    ]
    assert data["Reviewer"]["rules"] == [1, 2, 3, 6, 12]
    assert svg.count('class="node ') == len(model.components)
    assert "font-size:10" not in svg


def test_check_passes_on_example(example_cfg: Config, example_model: tuple[Model, Meaning]) -> None:
    model, meaning = example_model
    t = theme_mod.resolve(example_cfg.theme, meaning.layers)
    facts = extract.read_facts(example_cfg.facts_path)
    problems, _notes, counts = check.run(model, meaning, t, facts, example_cfg.issue_url)
    assert problems == []
    assert counts == (0, 0)


def test_default_theme_colours_every_layer(example_model: tuple[Model, Meaning]) -> None:
    _, meaning = example_model
    t = theme_mod.resolve({}, meaning.layers)
    assert set(t["layers"]) == {layer.id for layer in meaning.layers}
    assert len(set(t["layers"].values())) == len(meaning.layers)
    custom = theme_mod.resolve({"layers": {"work": "#123456"}, "accent": "#ABCDEF"}, meaning.layers)
    assert custom["layers"]["work"] == "#123456"
    assert custom["accent"] == "#ABCDEF"
    assert "--accent:#ABCDEF" in theme_mod.css_vars(custom)


def test_reach_figure(example_cfg: Config, example_model: tuple[Model, Meaning]) -> None:
    model, meaning = example_model
    t = theme_mod.resolve(example_cfg.theme, meaning.layers)
    facts = extract.read_facts(example_cfg.facts_path)
    html, collisions = figure.make(
        example_cfg,
        model,
        meaning,
        t,
        facts,
        components=("Sense", "Pipeline"),
        interactive=True,
    )
    assert collisions == []
    assert html.startswith('<figure data-generated="systemap"')
    assert "in the plan's reach" in html
    assert "IN REACH" in html
    assert "svg.systemap" in html
