"""The page draws through tokens; a figure that leaves it carries literals.

Every colour the page's drawing, panel, legend and controls take from the
theme is written as `var(--token)`, and the tokens' values appear in the
`:root` block alone, so the page can carry several tables and switch
them at runtime. A standalone figure (`systemap figure`, a README image)
has no table to read and keeps the literal colours. Both are asserted
here on the rendered output, not on the tables.

Two schemes, Ink (`dark`, the default) and Paper (`light`), each a full
table. Only the flow kinds, the selection and the change have a hue; every
other token is one of the neutrals. Every text token reads at 4.5:1 on the
map, the surfaces and the card, and every line at 3:1 on the map. The
colour distances between kinds (CIEDE2000) were measured outside the test
suite, with the colour scripts that DESIGN.md names.

The picker: the page carries both tables, stamps the root before the
first paint (the stored pick, else light when the system prefers light,
else the configured default), and a pick restamps the root and is kept in
this browser when storage allows. A removed scheme name such as `clay` is
a configuration error that names the schemes.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import Sample
from test_keyboard import DRIVER, SELF_MAP, needs_node, sample_page

from systemap import figure, page, page_assets, page_changes
from systemap import theme as theme_mod
from systemap.model import DERIVED_LAYERS, all_layers
from systemap.schematic import interactive_script, panel_css
from systemap.schematic import render as render_schematic

HEX = re.compile(r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?\b")
SCHEMES = ["dark", "light"]


def outside_the_root_blocks(html: str) -> str:
    """The page less the places a literal colour belongs: the `:root`
    blocks that set the tokens, the favicon, which is not themed, and the
    swatch of each scheme in the picker, which shows that scheme's map colour
    in both schemes."""
    text = re.sub(r":root[^{]*\{[^}]*\}", "", html)
    text = re.sub(r'<link rel="icon" href="[^"]*">', "", text)
    text = re.sub(r'\[data-scheme="\w+"\] i\{background:#[0-9a-fA-F]{6}\}', "", text)
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
    assert 'stroke="var(--l-' in svg, "a flow line is drawn in its kind's layer token"
    assert "stroke:var(--map)" in svg, "the halo behind a label is the map token"
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
    # Some are set per element by the page itself, in an inline style or
    # with setProperty: a layer swatch's colour, a subject card's stroke, and
    # layout values such as a reveal delay. They are not theme tokens.
    per_element = set(re.findall(r"setProperty\(\s*['\"](--[\w-]+)['\"]", rest))
    per_element |= set(re.findall(r"style[=:]\s*['\"](--[\w-]+):", rest))
    # The Changes script sets the reveal delays per element. A page without a
    # comparison does not include that script, but its style rules name them.
    per_element |= set(re.findall(r"setProperty\(\s*['\"](--[\w-]+)['\"]", page_changes.SCRIPT))
    assert {"--c", "--subject"} <= per_element, sorted(per_element)
    assert named - declared <= per_element, sorted(named - declared - per_element)
    assert {
        "--card-built",
        "--actor",
        "--box-host",
        "--lt-data",
        "--l-data",
        "--map",
        "--grid",
        "--card",
        "--card-line",
        "--on-accent",
        "--hl",
        "--hl-soft",
        "--on-change",
        "--brand",
    } <= declared


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
    for token in ("--change", "--reach"):
        assert f"var({token})" in svg, token


def test_the_ground_is_neutral_and_the_same_in_every_view(sample: Sample) -> None:
    """A container is a 1 px solid frame with no fill. A region is a 1 px
    dashed border in the region token, with a number ring. Both keep their
    screen width at each zoom, as the borders of the design boards do."""
    for mode in ("system", "change"):
        svg, _ = render_schematic(
            sample.model, sample.meaning, sample.theme, sample.facts, mode=mode, variables=True
        )
        assert re.search(
            r'fill="var\(--box-\w+\)" stroke="var\(--box-\w+-line\)" stroke-width="1" '
            r'vector-effect="non-scaling-stroke"',
            svg,
        ), mode
        assert (
            'stroke="var(--region)" stroke-width="1" stroke-dasharray="3 3" '
            'vector-effect="non-scaling-stroke"'
        ) in svg, mode
    for t in theme_mod.SCHEMES.values():
        assert {fill for _stroke, fill in t["container"].values()} == {"none"}


def test_a_derived_layer_keeps_the_kind_colour_of_each_line(sample: Sample) -> None:
    """System context, Structure and Agents select lines; they do not
    colour them. A line in the System context figure has its kind's colour."""
    t = sample.theme
    svg, detail = render_schematic(
        sample.model, sample.meaning, t, sample.facts, layer="system", variables=False
    )
    edges = json.loads(detail)["_meta"]["edges"]
    drawn = re.findall(r'<path id="schematic-f(\d+)"[^>]*? stroke="([^"]+)"', svg)
    assert drawn, "the System context figure draws its lines"
    for index, stroke in drawn:
        assert stroke == t["layers"][edges[int(index)]["layer"]], index
        assert stroke != t["layers"]["system"]


def tokens_named(text: str) -> set[str]:
    return set(re.findall(r"var\((--[\w-]+)[,)]", text))


def test_a_standalone_figure_keeps_literal_colours(sample: Sample) -> None:
    # A figure keeps two custom properties: the subject card's stroke, which
    # the script sets per node, and a legend swatch color, which the swatch
    # sets inline. Both take a literal in a figure.
    html, _ = figure.make(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, interactive=True
    )
    assert tokens_named(html) == {"--subject", "--c"}
    assert len(HEX.findall(html)) > 50
    assert f'stroke="{sample.theme["layers"]["data"]}"' in html
    bare, _ = figure.make(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, bare=True
    )
    assert tokens_named(bare) == {"--subject"} and HEX.findall(bare)
    assert f'fill="{sample.theme["map"]}"/>' in bare, "the image ground is the map colour"
    reading, _ = figure.make(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, layer="control"
    )
    assert tokens_named(reading) == {"--subject"} and HEX.findall(reading)
    # The panel and the script of a figure carry the literals too. Only a
    # swatch color, set inline with a literal, is a custom property.
    assert set(re.findall(r"var\((--[\w-]+)", panel_css(sample.theme))) <= {"--c"}
    assert "var(" not in interactive_script(sample.theme, "f", "p", '{"_meta":{}}')


def test_the_palette_answers_one_table_two_ways(sample: Sample) -> None:
    t = sample.theme
    literal = theme_mod.Palette(t)
    tokens = theme_mod.Palette(t, variables=True)
    assert literal["accent"] == t["accent"] and tokens["accent"] == "var(--accent)"
    assert literal["map"] == t["map"] and tokens["map"] == "var(--map)"
    assert tokens["card_line"] == "var(--card-line)" and tokens["hl"] == "var(--hl)"
    assert literal.layer("data") == t["layers"]["data"]
    assert tokens.layer("data") == "var(--l-data)"
    assert tokens.tag("data") == "var(--lt-data)"
    assert literal.tag("data") == theme_mod.mix(t["raised"], t["layers"]["data"], theme_mod.TAG_MIX)
    assert literal.state("built") == tuple(t["state"]["built"])
    assert tokens.state("built") == (
        "var(--card-built)",
        "var(--card-built-line)",
        "source recorded",
    )
    assert tokens.container("server") == ("var(--box-server-line)", "var(--box-server)")
    assert literal.container("server") == tuple(t["container"]["server"])
    # An actor is a dashed card border on the map ground.
    assert tokens.actor() == ("var(--actor)", "var(--card-line)")
    assert literal.actor() == (t["map"], t["card_line"])
    # The root block sets the same derived values the literal palette answers.
    css = theme_mod.css_vars(t)
    assert f"--actor:{literal.actor()[0]};" in css
    assert f"--lt-data:{literal.tag('data')};" in css
    assert f"--changed-fill:{literal.changed_fill()};" in css
    assert f"--box-server:{t['container']['server'][1]};" in css
    assert f"--card:{t['card']};--card-line:{t['card_line']};" in css


# ---- the two schemes -----------------------------------------------------------


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


def kind_colours(t: dict[str, object]) -> dict[str, str]:
    """Every flow kind layer and custom kind colour, by name. A derived layer
    is not a kind: its colour is the card border of its subject cards."""
    layers = t["layers"]
    assert isinstance(layers, dict)
    out = {
        f"layer {lid}": str(colour) for lid, colour in layers.items() if lid not in DERIVED_LAYERS
    }
    palette = t["layer_palette"]
    assert isinstance(palette, list)
    out.update({f"palette {k}": str(colour) for k, colour in enumerate(palette)})
    return out


# Every surface that text can show on: the page, the header and panel, a
# pressed control, the map and a card.
TEXT_GROUNDS = ("bg", "surface", "raised", "map", "card")
# A kind colour is a line on the map and a swatch in the legend and panel.
# The colour measurement held it to 4.5:1 on the map; it keeps 4.5:1 on the
# map and a card, and 3:1 (a line) on the other grounds.
KIND_TEXT_GROUNDS = ("map", "card")


def test_contrast_is_the_wcag_formula() -> None:
    assert contrast("#ffffff", "#000000") == 21
    assert round(contrast("#767676", "#ffffff"), 2) == 4.54


@pytest.mark.parametrize("scheme", SCHEMES)
def test_every_text_token_clears_four_and_a_half_to_one_on_every_ground(scheme: str) -> None:
    t = theme_mod.SCHEMES[scheme]
    short = {
        f"{name} on {ground}": round(contrast(str(t[name]), str(t[ground])), 2)
        for name in theme_mod.TEXT_TOKENS
        for ground in TEXT_GROUNDS
    }
    assert all(ratio >= 4.5 for ratio in short.values()), {
        name: ratio for name, ratio in short.items() if ratio < 4.5
    }


@pytest.mark.parametrize("scheme", SCHEMES)
def test_every_kind_colour_clears_the_map_and_the_line_floor(scheme: str) -> None:
    t = theme_mod.SCHEMES[scheme]
    ratios = {
        f"{name} on {ground}": (round(contrast(colour, str(t[ground])), 2), floor)
        for name, colour in kind_colours(t).items()
        for ground in TEXT_GROUNDS
        for floor in [4.5 if ground in KIND_TEXT_GROUNDS else 3.0]
    }
    assert all(ratio >= floor for ratio, floor in ratios.values()), {
        name: ratio for name, (ratio, floor) in ratios.items() if ratio < floor
    }


@pytest.mark.parametrize("scheme", SCHEMES)
def test_text_on_a_filled_tag_and_on_the_highlighter_clears_four_and_a_half(scheme: str) -> None:
    """ACTS and the step number are on the accent, CHANGED is on the change
    fill, and selected card text is on the highlighter fill."""
    t = theme_mod.SCHEMES[scheme]
    pairs = {f"{text} on {fill}": (t[text], t[fill]) for text, fill in theme_mod.ON_FILL.items()}
    pairs["ink on hl_soft"] = (t["ink"], t["hl_soft"])
    pairs["ink_2 on hl_soft"] = (t["ink_2"], t["hl_soft"])
    if scheme == "light":
        pairs["ink on hl"] = (t["ink"], t["hl"])
    ratios = {label: contrast(ink, fill) for label, (ink, fill) in pairs.items()}
    assert all(ratio >= 4.5 for ratio in ratios.values()), ratios


@pytest.mark.parametrize("scheme", SCHEMES)
def test_every_line_clears_three_to_one_on_the_map(scheme: str) -> None:
    """Card borders, region borders and the neutral line are lines, held to 3:1."""
    t = theme_mod.SCHEMES[scheme]
    lines = {key: str(t[key]) for key in ("card_line", "region", "flow")}
    ratios = {key: round(contrast(colour, str(t["map"])), 2) for key, colour in lines.items()}
    assert all(ratio >= 3 for ratio in ratios.values()), ratios


@pytest.mark.parametrize("scheme", SCHEMES)
def test_actor_and_inspector_text_clear_four_and_a_half_on_actual_fills(scheme: str) -> None:
    """Acceptance: 4.5:1 on actor, raised and inspector surfaces.

    The ground alone misses actor fills and selected connection rows. These
    pairs correspond to the displayed card purpose, row metadata and note.
    """
    t = theme_mod.SCHEMES[scheme]
    palette = theme_mod.Palette(t)
    pairs = {
        "actor purpose": (t["ink_3"], palette.actor()[0]),
        "selected connection metadata": (t["ink_3"], t["raised"]),
        "inspector secondary text": (t["ink_3"], t["surface"]),
        "note text": (t["ink"], t["raised"]),
        "note warning label": (t["warn"], t["raised"]),
    }
    ratios = {label: contrast(ink, fill) for label, (ink, fill) in pairs.items()}
    assert all(ratio >= 4.5 for ratio in ratios.values()), ratios


def oklab_lc(colour: str) -> tuple[float, float]:
    """OKLab lightness and chroma of an sRGB colour (Ottosson's matrices)."""
    lin = []
    for i in (1, 3, 5):
        c = int(colour[i : i + 2], 16) / 255
        lin.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = lin
    lms = (
        0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b,
        0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b,
        0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b,
    )
    l_, m_, s_ = (v ** (1 / 3) for v in lms)
    lightness = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b2 = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return lightness, (a * a + b2 * b2) ** 0.5


def test_paper_surfaces_are_near_neutral_and_lighter_from_map_to_panel_to_card() -> None:
    """Paper is warm but not beige: each surface has an OKLCH chroma of 0.007
    or less. Ink surfaces go to 0.009. The map is the toned sheet, the header and panel are
    lighter, and a card is the lightest, so the cards stand out on the map.
    The highlighter hue is not the hue of the paper. The picker swatch shows
    the map colour of each scheme."""
    paper = theme_mod.LIGHT
    chroma = {key: round(oklab_lc(paper[key])[1], 4) for key in TEXT_GROUNDS}
    assert all(c <= 0.007 for c in chroma.values()), chroma
    light = {key: oklab_lc(paper[key])[0] for key in ("bg", "map", "surface", "card")}
    assert light["bg"] < light["map"] < light["surface"] < light["card"], light
    assert contrast(paper["card"], paper["map"]) >= 1.1
    assert oklab_lc(paper["hl_line"])[1] >= 0.1, "the halo is a clear highlighter yellow"
    for name, t in theme_mod.SCHEMES.items():
        assert f'[data-scheme="{name}"] i{{background:{t["map"]}}}' in page_assets.CSS


def test_every_paper_kind_line_reads_on_the_highlighter_halo() -> None:
    """A selected or current line keeps its kind colour over the halo
    `hl_line`. Each kind colour has 3:1 or more on the halo, as a line."""
    paper = theme_mod.LIGHT
    ratios = {
        name: round(contrast(colour, paper["hl_line"]), 2)
        for name, colour in kind_colours(paper).items()
    }
    assert all(ratio >= 3 for ratio in ratios.values()), ratios


def test_the_schemes_are_ink_and_paper_and_the_default_is_ink() -> None:
    assert list(theme_mod.SCHEMES) == SCHEMES
    assert theme_mod.SCHEME_LABELS == {"dark": "Ink", "light": "Paper"}
    assert theme_mod.DEFAULT_SCHEME == "dark" and theme_mod.LIGHT_SCHEME == "light"
    assert not hasattr(theme_mod, "CLAY")
    keys = {name: set(t) for name, t in theme_mod.SCHEMES.items()}
    assert keys["dark"] == keys["light"]
    kinds = ("data", "control", "context", "tools")
    for name, t in theme_mod.SCHEMES.items():
        assert t["scheme"] == name
        assert t["color_scheme"] == name
        assert set(t["layers"]) == set(theme_mod.STANDARD_LAYERS_DARK)
        assert len({t["layers"][k] for k in kinds}) == len(kinds), "each kind its own colour"
        assert not set(t["layer_palette"]) & set(t["layers"].values()), (
            "a custom layer never takes a standard colour"
        )
        assert len(set(t["layer_palette"])) == len(t["layer_palette"])
        assert t["state"]["built"] == [t["card"], t["card_line"], "source recorded"]
    ink, paper = theme_mod.DARK, theme_mod.LIGHT
    # The measured values of the design boards (tokens.md).
    assert (ink["bg"], ink["surface"], ink["map"], ink["card"]) == (
        "#0F0E0C",
        "#161411",
        "#12110F",
        "#1C1A17",
    )
    assert (ink["accent"], ink["change"], ink["region"], ink["flow"]) == (
        "#FCB442",
        "#D4675B",
        "#6B665D",
        "#66625A",
    )
    assert (ink["layers"]["data"], ink["layers"]["control"], ink["layer_palette"][0]) == (
        "#2CB59A",
        "#B97874",
        "#8A8B22",
    )
    # The Paper surfaces of the 2026-10-11 Paper measurement in bench/jev/README.md.
    assert (paper["bg"], paper["surface"], paper["map"], paper["card"]) == (
        "#F1EFEC",
        "#FCFAF7",
        "#F4F2EF",
        "#FFFEFC",
    )
    assert (paper["accent"], paper["hl"], paper["change"], paper["ink"]) == (
        "#1D1B17",
        "#FFE380",
        "#AC312A",
        "#1D1B17",
    )
    assert (paper["flow"], paper["hl_line"], paper["hl_soft"]) == ("#8E8C85", "#FFE380", "#FFF1BF")
    assert (paper["layers"]["data"], paper["layers"]["control"], paper["layer_palette"][0]) == (
        "#014438",
        "#A05B5A",
        "#493901",
    )


@pytest.mark.parametrize("scheme", SCHEMES)
def test_only_kinds_selection_and_change_have_a_hue(scheme: str) -> None:
    """Five colour roles: the flow kinds, the selection and the change.
    Status tokens, measurement, derived layers, the reach of a change and
    the change bar are neutrals or the change itself. A derived layer has
    the card border colour, so its subject cards look like other cards."""
    t = theme_mod.SCHEMES[scheme]
    neutral = {t["ink"], t["ink_2"], t["ink_3"]}
    for key in ("good", "warn", "bad", "violet", "steel"):
        assert t[key] in neutral, key
    assert t["steel"] == t["ink_2"]
    for lid in DERIVED_LAYERS:
        assert t["layers"][lid] == t["card_line"], lid
    assert t["reach"] == t["change"]
    assert set(t["delta"].values()) <= neutral | {t["change"]}
    assert {stroke for stroke, _fill in t["container"].values()} <= {t["line_2"], t["card_line"]}
    assert t["ghost"] == [t["card"], t["line_2"]]


def test_overrides_apply_per_scheme_and_bare_keys_to_the_default(sample: Sample) -> None:
    layers = all_layers(sample.model, sample.meaning)
    t = theme_mod.resolve(
        {"accent": "#111111", "light": {"accent": "#222222", "layers": {"data": "#333333"}}},
        layers,
    )
    assert t["scheme"] == "dark" and t["accent"] == "#111111"
    schemes = t["schemes"]
    assert list(schemes) == SCHEMES
    assert schemes["dark"]["accent"] == "#111111"
    assert schemes["light"]["accent"] == "#222222"
    assert schemes["light"]["layers"]["data"] == "#333333"
    assert schemes["light"]["layers"]["record"] == theme_mod.LAYER_PALETTE_LIGHT[0]
    assert "schemes" not in schemes["light"], "a scheme's table is not nested again"
    # With the default moved, the bare keys move with it; a sub-table for
    # the default is laid over them.
    t = theme_mod.resolve(
        {"scheme": "light", "accent": "#111111", "light": {"bad": "#444444"}}, layers
    )
    assert t["scheme"] == "light" and t["accent"] == "#111111" and t["bad"] == "#444444"
    assert t["schemes"]["dark"]["accent"] == theme_mod.DARK["accent"], "bare keys are the default's"
    message = (
        "The theme scheme 'sepia' is not available. The schemes are dark (Ink) and light (Paper)."
    )
    with pytest.raises(ValueError, match=re.escape(message)):
        theme_mod.resolve({"scheme": "sepia"}, layers)
    with pytest.raises(ValueError, match="theme.light must contain a table of CSS tokens"):
        theme_mod.resolve({"light": "#fff"}, layers)


@pytest.mark.parametrize("name", ["clay", "warm", "graphite", "paper", "ink", "Dark"])
def test_removed_and_display_names_are_not_schemes(name: str) -> None:
    """The removed theme names and the page names give a configuration error
    that names the schemes. The configuration uses the keys dark and light."""
    with pytest.raises(ValueError, match=r"is not available\. The schemes are dark \(Ink\)"):
        theme_mod.resolve({"scheme": name}, [])


@pytest.mark.parametrize("tokens", [{"clay": {"accent": "#cf8b6b"}}, {"clay": "#fff"}])
def test_a_table_for_a_removed_scheme_is_an_error(tokens: dict[str, Any]) -> None:
    """`[theme.clay]` does not become an unused token: it is an error."""
    with pytest.raises(ValueError, match="The theme scheme 'clay' is not available"):
        theme_mod.resolve(tokens, [])


def test_a_token_table_is_not_a_scheme(sample: Sample) -> None:
    layers = all_layers(sample.model, sample.meaning)
    t = theme_mod.resolve({"layers": {"data": "#123456"}, "dark": {"marks": {}}}, layers)
    assert t["layers"]["data"] == "#123456"
    with pytest.raises(ValueError, match="The theme scheme 'sepia' is not available"):
        theme_mod.resolve({"sepia": {"accent": "#123456"}}, layers)


# ---- the picker, under the Node driver ------------------------------------------


def drive_theme(html: Path, *flags: str) -> dict[str, Any]:
    args = [shutil.which("node") or "node", str(DRIVER), str(html), "--scenario", "theme", *flags]
    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert proc.returncode == 0, proc.stderr
    report: dict[str, Any] = json.loads(proc.stdout)
    return report


def test_the_page_carries_every_scheme_and_stamps_the_default(sample: Sample) -> None:
    layers = all_layers(sample.model, sample.meaning)
    t = theme_mod.resolve({"light": {"accent": "#123456"}}, layers)
    html = page.build(
        sample.cfg, sample.model, sample.meaning, t, sample.facts, {"has_change": False}
    )
    head = html.split("</head>")[0]
    # The default's table on the bare root, every scheme's under its
    # attribute, and light under the light preference for a root no script
    # stamped; the head script names the default and the two.
    assert head.count(":root{") == 1
    for name in SCHEMES:
        assert f':root[data-theme="{name}"]{{' in head, name
    assert ':root[data-theme="clay"]' not in head
    bare = re.search(r":root\{([^}]*)\}", head)
    dark = re.search(r':root\[data-theme="dark"\]\{([^}]*)\}', head)
    light = re.search(r':root\[data-theme="light"\]\{([^}]*)\}', head)
    media = re.search(
        r"@media \(prefers-color-scheme:light\)\{:root:not\(\[data-theme\]\)\{([^}]*)\}", head
    )
    assert bare and dark and light and media
    assert bare.group(1) == dark.group(1)
    assert media.group(1) == light.group(1)
    assert "--accent:#123456;" in light.group(1) and "--accent:#123456;" not in dark.group(1)
    assert "color-scheme:dark;" in dark.group(1) and "color-scheme:light;" in light.group(1)
    assert 'localStorage.getItem("systemap-theme")' in head
    assert '["dark", "light"].indexOf(s)<0' in head
    assert '\'(prefers-color-scheme: light)\').matches)?"light":"dark"' in head
    assert "document.documentElement.setAttribute('data-theme',s)" in head
    assert head.index("<script>") < head.index("<style>"), "the root is stamped before the styles"
    # The picker in the header, one option per scheme, with the page names.
    header = html.split("</header>")[0]
    assert re.findall(r'<button[^>]*data-scheme="(\w+)"', header) == SCHEMES
    for name, label in theme_mod.SCHEME_LABELS.items():
        assert re.search(rf'data-scheme="{name}"[^>]*>(?:<i></i>)?{label}<', header), label
    assert "Clay" not in header
    # The device theme replaces the configured figure palette on the page.
    t = theme_mod.resolve({"scheme": "light"}, layers)
    html = page.build(
        sample.cfg, sample.model, sample.meaning, t, sample.facts, {"has_change": False}
    )
    head = html.split("</head>")[0]
    bare = re.search(r":root\{([^}]*)\}", head)
    assert bare and "color-scheme:dark;" in bare.group(1)
    assert '\'(prefers-color-scheme: light)\').matches)?"light":"dark"' in head


@needs_node
@pytest.mark.parametrize(
    ("scheme", "flags", "expected"),
    [
        ("dark", ("--stored", "warm"), "dark"),
        ("dark", ("--stored", "clay"), "dark"),
        ("dark", ("--light", "--stored", "clay"), "light"),
        ("dark", ("--light", "--stored", "paper"), "light"),
        ("light", (), "dark"),
        ("dark", (), "dark"),
        ("light", ("--light",), "light"),
        ("light", ("--stored", "dark"), "dark"),
        ("dark", ("--light", "--stored", "dark"), "dark"),
        ("dark", ("--stored", "light"), "light"),
        ("light", ("--stored", "sepia"), "dark"),
        ("light", ("--light", "--stored", "sepia"), "light"),
        ("light", ("--no-storage",), "dark"),
        ("light", ("--light", "--no-storage"), "light"),
    ],
)
def test_the_scheme_on_load(
    sample: Sample, tmp_path: Path, scheme: str, flags: tuple[str, ...], expected: str
) -> None:
    """The page reads the stored selection first. Without a stored selection,
    the page uses the device theme. The controls also operate without storage.
    A stored `clay` from an earlier version is not a scheme any more."""
    report = drive_theme(sample_page(sample, tmp_path, scheme), *flags)
    assert report["onLoad"] == expected, report
    assert report["pickValue"] == expected, "the picker shows what the root carries"
    assert report["options"] == report["blocks"] == SCHEMES


@needs_node
def test_a_pick_restamps_the_root_and_is_kept(sample: Sample, tmp_path: Path) -> None:
    report = drive_theme(sample_page(sample, tmp_path))
    assert report["storedOnLoad"] is None, "nothing is stored until the reader picks"
    assert report["switches"] == [
        {"picked": name, "attr": name, "pickValue": name, "stored": name} for name in SCHEMES
    ]
    # With storage refused the pick still restamps the root; it is not kept.
    report = drive_theme(sample_page(sample, tmp_path), "--no-storage")
    assert report["storedOnLoad"] == "unavailable"
    assert [(s["picked"], s["attr"], s["stored"]) for s in report["switches"]] == [
        (name, name, "unavailable") for name in SCHEMES
    ]


@needs_node
def test_the_self_map_page_stamps_dark_and_switches() -> None:
    assert SELF_MAP.is_file(), "the committed page; run systemap refresh"
    report = drive_theme(SELF_MAP)
    assert report["onLoad"] == "dark"
    assert [s["attr"] for s in report["switches"]] == SCHEMES
    assert drive_theme(SELF_MAP, "--light")["onLoad"] == "light"
