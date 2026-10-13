"""The figure and the page put authored text into HTML only as safe text.

Acceptance (Codex result cli-3): an authored layer label, layer question, layer
description, figure caption, map ID, output directory name, or facts file name that
contains HTML markup is in the figure as text. The figure contains no element from the
markup. A figure SVG ID that is not a safe HTML ID gives ArgumentError, or ConfigError
from a [[figures]] entry. A child map preview whose card ID is not a safe HTML ID gets
a safe SVG ID. A theme value that contains < > & or " (< > & for a font value) gives
ValueError, because the page and the figures use theme values without conversion.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from conftest import Sample

from systemap import figure, nest, page
from systemap import theme as theme_mod
from systemap.config import ArgumentError, ConfigError, Figure
from systemap.model import Layer, all_layers

MARKUP = "<img src=x onerror=alert(1)>"
SAFE = "&lt;img src=x onerror=alert(1)&gt;"


def _with_layer(sample: Sample) -> Sample:
    """Give the sample with one custom layer whose text is HTML markup."""
    layer = Layer("custom", f"Label {MARKUP}", f"Question {MARKUP}?", f"sub {MARKUP}")
    meaning = dataclasses.replace(sample.meaning, layers=(*sample.meaning.layers, layer))
    t = theme_mod.resolve({}, all_layers(sample.model, meaning))
    return dataclasses.replace(sample, meaning=meaning, theme=t)


def test_a_layer_label_in_the_legend_is_text(sample: Sample) -> None:
    s = _with_layer(sample)
    html, _ = figure.make(s.cfg, s.model, s.meaning, s.theme, s.facts)
    assert f"Label {SAFE}</span>" in html
    assert "<img" not in html


def test_the_layer_caption_is_text(sample: Sample) -> None:
    s = _with_layer(sample)
    html, _ = figure.make(s.cfg, s.model, s.meaning, s.theme, s.facts, layer="custom")
    assert f"Label {SAFE}: Question {SAFE}? Sub {SAFE}. This figure shows one layer." in html
    assert "<img" not in html


def test_a_given_caption_and_the_names_in_the_default_caption_are_text(sample: Sample) -> None:
    html, _ = figure.make(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, caption=MARKUP
    )
    assert f">{SAFE}</figcaption>" in html and "<img" not in html
    cfg = dataclasses.replace(sample.cfg, out_dir=f"out{MARKUP}", facts_file=f"f{MARKUP}.json")
    html, _ = figure.make(
        cfg, sample.model, sample.meaning, sample.theme, sample.facts, map_id=f"A/B{MARKUP}"
    )
    assert f"Inside B{SAFE}: " in html
    assert f"<code>out{SAFE}/f{SAFE}.json</code>" in html
    assert "<img" not in html


def test_an_unsafe_svg_id_is_refused(sample: Sample) -> None:
    for svg_id in ('x"><img src=x>', "1map", "", "a b"):
        with pytest.raises(ArgumentError):
            figure.make(
                sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, svg_id=svg_id
            )
    tree = nest.Tree(
        (
            nest.Map(
                "", Path("map/model.py"), "map/model.py", sample.model, sample.meaning, sample.theme
            ),
        )
    )
    with pytest.raises(ConfigError):
        figure.configured(
            sample.cfg, tree, tree.top, sample.facts, Figure(out="f.html", svg_id='x"y')
        )
    html, _ = figure.make(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, svg_id="map-2_b"
    )
    assert 'id="map-2_b"' in html


def test_a_preview_of_a_card_with_an_unsafe_id_gets_a_safe_svg_id(sample: Sample) -> None:
    child = nest.Map(
        f"Card{MARKUP}",
        Path("map/child.py"),
        "map/child.py",
        sample.model,
        sample.meaning,
        sample.theme,
        parent="",
        card=f"Card{MARKUP}",
    )
    svg = page.preview(sample.cfg, child, sample.facts)
    assert svg.startswith('<svg id="preview-')
    assert "<img" not in svg and "onerror" not in svg.split(">", 1)[0]
    plain = dataclasses.replace(child, id="Gateway", card="Gateway")
    assert page.preview(sample.cfg, plain, sample.facts).startswith('<svg id="preview-Gateway"')


def test_a_theme_value_with_html_marks_is_refused(sample: Sample) -> None:
    layers = all_layers(sample.model, sample.meaning)
    for tokens in (
        {"line": "red</style><script>alert(1)</script>"},
        {"ink_2": '#fff" onclick="alert(1)'},
        {"state": {"built": ["#1C1A17", "#37332D", "built <b>"]}},
        {"font_ui": "Inter</style>"},
    ):
        with pytest.raises(ValueError, match="theme value"):
            theme_mod.resolve(tokens, layers)
    font = theme_mod.resolve({"font_ui": '"Inter", sans-serif'}, layers)
    assert font["font_ui"] == '"Inter", sans-serif'
