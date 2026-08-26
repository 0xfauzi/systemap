"""The page draws through tokens; a figure that leaves it carries literals.

Every colour the page's drawing, panel, legend and controls take from the
theme is written as `var(--token)`, and the tokens' values appear in the
`:root` block alone, so the page can carry several tables and switch
them at runtime. A standalone figure (`systemap figure`, a README image)
has no table to read and keeps the literal colours. Both are asserted
here on the rendered output, not on the tables.
"""

from __future__ import annotations

import re

import pytest
from conftest import Sample

from systemap import figure, page
from systemap import theme as theme_mod
from systemap.model import all_layers
from systemap.schematic import interactive_script, panel_css
from systemap.schematic import render as render_schematic

HEX = re.compile(r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?\b")


def outside_the_root_blocks(html: str) -> str:
    """The page less the places a literal colour belongs: the `:root`
    blocks that set the tokens, and the favicon, which is not themed."""
    text = re.sub(r":root[^{]*\{[^}]*\}", "", html)
    text = re.sub(r'<link rel="icon" href="[^"]*">', "", text)
    return text


def map_svg(html: str) -> str:
    start = html.index('<svg id="schematic"')
    return html[start : html.index("</svg>", start) + 6]


def test_the_page_draws_through_variables_only(sample: Sample) -> None:
    html = page.build(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {"has_change": False}
    )
    svg = map_svg(html)
    assert HEX.findall(svg) == [], "the map's SVG names tokens, never values"
    assert 'fill="var(--' in svg and 'stroke="var(--' in svg
    assert "fill:var(--l-" in svg, "an edge label is drawn in its layer's token"
    assert "stroke:var(--bg)" in svg, "the halo behind a label is the ground token"
    css = panel_css(sample.theme, variables=True)
    assert HEX.findall(css) == [], "the panel's CSS names tokens, never values"
    assert css in html
    # The whole page, less the root block and the favicon, carries no
    # literal colour: the legend, the controls and the scripts included.
    rest = outside_the_root_blocks(html)
    assert HEX.findall(rest) == [], HEX.findall(rest)[:8]
    assert html.count(":root{") == 1
    root = re.search(r":root\{([^}]*)\}", html)
    assert root is not None
    # Every token the drawing names is set in the root block.
    named = set(re.findall(r"var\((--[\w-]+)[,)]", rest))
    declared = set(re.findall(r"(--[\w-]+):", root.group(1)))
    # Two are set per element by the page itself: a layer button's colour
    # and a subject card's stroke.
    assert named - declared == {"--c", "--subject"}, sorted(named - declared)
    assert {"--card-built", "--actor", "--box-host", "--lt-data", "--l-data"} <= declared


def test_the_change_map_draws_through_variables_only(sample: Sample) -> None:
    svg, _detail = render_schematic(
        sample.model,
        sample.meaning,
        sample.theme,
        sample.facts,
        changed={"Parser"},
        changed_modules={"pkg.parser"},
        adjacent={"Writer"},
        mode="change",
        svg_id="changemap",
        gained={"Parser": {"operations": 2, "types": 1, "refusals": 0, "tests": 3}},
        variables=True,
    )
    assert HEX.findall(svg) == []
    for token in ("--change", "--reach", "--ghost", "--d-operations", "--d-tests"):
        assert f"var({token})" in svg, token


def tokens_named(text: str) -> set[str]:
    return set(re.findall(r"var\((--[\w-]+)[,)]", text))


def test_a_standalone_figure_keeps_literal_colours(sample: Sample) -> None:
    # The one custom property a figure keeps is the subject card's stroke,
    # which the script sets per node with a literal in a figure.
    html, _ = figure.make(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, interactive=True
    )
    assert tokens_named(html) == {"--subject"}
    assert len(HEX.findall(html)) > 50
    assert f'stroke="{sample.theme["layers"]["data"]}"' in html
    bare, _ = figure.make(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, bare=True
    )
    assert tokens_named(bare) == {"--subject"} and HEX.findall(bare)
    reading, _ = figure.make(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, layer="control"
    )
    assert tokens_named(reading) == {"--subject"} and HEX.findall(reading)
    # The panel and the script of a figure carry the literals too.
    assert "var(" not in panel_css(sample.theme)
    assert "var(" not in interactive_script(sample.theme, "f", "p", '{"_meta":{}}')


def test_the_palette_answers_one_table_two_ways(sample: Sample) -> None:
    t = sample.theme
    literal = theme_mod.Palette(t)
    tokens = theme_mod.Palette(t, variables=True)
    assert literal["accent"] == t["accent"] and tokens["accent"] == "var(--accent)"
    assert literal.layer("data") == t["layers"]["data"]
    assert tokens.layer("data") == "var(--l-data)"
    assert tokens.tag("data") == "var(--lt-data)"
    assert literal.tag("data") == theme_mod.mix(t["raised"], t["layers"]["data"], theme_mod.TAG_MIX)
    assert literal.state("built") == tuple(t["state"]["built"])
    assert tokens.state("built") == ("var(--card-built)", "var(--card-built-line)", "built")
    assert tokens.container("server") == ("var(--box-server-line)", "var(--box-server)")
    assert literal.container("server") == tuple(t["container"]["server"])
    assert tokens.actor() == ("var(--actor)", "var(--ink-3)")
    # The root block sets the same derived values the literal palette answers.
    css = theme_mod.css_vars(t)
    assert f"--actor:{literal.actor()[0]};" in css
    assert f"--lt-data:{literal.tag('data')};" in css
    assert f"--changed-fill:{literal.changed_fill()};" in css
    assert f"--box-server:{t['container']['server'][1]};" in css


# ---- the three schemes ---------------------------------------------------------


def luminance(colour: str) -> float:
    """Relative luminance, as WCAG 2 defines it."""
    parts = []
    for i in (1, 3, 5):
        c = int(colour[i : i + 2], 16) / 255
        parts.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = parts
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def text_tokens(t: dict[str, object]) -> dict[str, str]:
    """Every token that is read as text somewhere on the page, by name."""
    out = {name: str(t[name]) for name in theme_mod.TEXT_TOKENS}
    layers = t["layers"]
    assert isinstance(layers, dict)
    out.update({f"layer {lid}": str(colour) for lid, colour in layers.items()})
    palette = t["layer_palette"]
    assert isinstance(palette, list)
    out.update({f"palette {k}": str(colour) for k, colour in enumerate(palette)})
    return out


def test_contrast_is_the_wcag_formula() -> None:
    assert contrast("#ffffff", "#000000") == 21
    assert round(contrast("#767676", "#ffffff"), 2) == 4.54


@pytest.mark.parametrize("scheme", list(theme_mod.SCHEMES))
def test_every_text_token_clears_four_and_a_half_to_one_on_its_ground(scheme: str) -> None:
    t = theme_mod.SCHEMES[scheme]
    ground = str(t["bg"])
    short = {name: round(contrast(colour, ground), 2) for name, colour in text_tokens(t).items()}
    assert all(ratio >= 4.5 for ratio in short.values()), {
        name: ratio for name, ratio in short.items() if ratio < 4.5
    }


def test_the_schemes_are_three_full_tables_and_the_default_is_warm() -> None:
    assert list(theme_mod.SCHEMES) == ["warm", "graphite", "paper"]
    assert theme_mod.DEFAULT_SCHEME == "warm" and theme_mod.LIGHT_SCHEME == "paper"
    keys = {name: set(t) for name, t in theme_mod.SCHEMES.items()}
    assert keys["warm"] == keys["graphite"] == keys["paper"]
    for name, t in theme_mod.SCHEMES.items():
        assert t["scheme"] == name
        assert t["color_scheme"] == ("light" if name == "paper" else "dark")
        assert set(t["layers"]) == set(theme_mod.STANDARD_LAYERS_WARM)
        assert len(set(t["layers"].values())) == len(t["layers"]), (
            "every standard layer its own hue"
        )
        assert not set(t["layer_palette"]) & set(t["layers"].values()), (
            "a custom layer never takes a standard hue"
        )
    warm = theme_mod.WARM
    assert warm["bg"] == "#161310" and warm["accent"] == "#e5a84f" and warm["ink"] == "#ece5d8"
    assert warm["state"]["built"] == ["#27221a", "#8a7d63", "built"]
    assert warm["container"]["isolated"] == ["#6b4a3d", "#1d1613"]
    assert list(warm["layers"].values()) == [
        "#d9cdb2",
        "#82a7ba",
        "#e39a86",
        "#dd9bbd",
        "#b48ec9",
        "#86c9a9",
        "#b7c27c",
    ]
    assert warm["layer_palette"][0] == "#e3b778"
    assert theme_mod.PAPER["accent"] == "#99621c"


def test_overrides_apply_per_scheme_and_bare_keys_to_the_default(sample: Sample) -> None:
    layers = all_layers(sample.model, sample.meaning)
    t = theme_mod.resolve(
        {"accent": "#111111", "paper": {"accent": "#222222", "layers": {"data": "#333333"}}},
        layers,
    )
    assert t["scheme"] == "warm" and t["accent"] == "#111111"
    schemes = t["schemes"]
    assert list(schemes) == ["warm", "graphite", "paper"]
    assert schemes["warm"]["accent"] == "#111111"
    assert schemes["graphite"]["accent"] == theme_mod.GRAPHITE["accent"], (
        "bare keys are the default's"
    )
    assert schemes["paper"]["accent"] == "#222222"
    assert schemes["paper"]["layers"]["data"] == "#333333"
    assert schemes["paper"]["layers"]["record"] == theme_mod.LAYER_PALETTE_PAPER[0]
    assert "schemes" not in schemes["paper"], "a scheme's table is not nested again"
    # With the default moved, the bare keys move with it; a sub-table for
    # the default is laid over them.
    t = theme_mod.resolve(
        {"scheme": "light", "accent": "#111111", "paper": {"bad": "#444444"}}, layers
    )
    assert t["scheme"] == "paper" and t["accent"] == "#111111" and t["bad"] == "#444444"
    assert t["schemes"]["warm"]["accent"] == theme_mod.WARM["accent"]
    with pytest.raises(
        ValueError, match="unknown theme scheme 'sepia'; the schemes are warm, graphite, paper"
    ):
        theme_mod.resolve({"scheme": "sepia"}, layers)
    with pytest.raises(ValueError, match="theme.warm must be a table of tokens"):
        theme_mod.resolve({"warm": "#fff"}, layers)
