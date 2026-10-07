"""The page draws through tokens; a figure that leaves it carries literals.

Every colour the page's drawing, panel, legend and controls take from the
theme is written as `var(--token)`, and the tokens' values appear in the
`:root` block alone, so the page can carry several tables and switch
them at runtime. A standalone figure (`systemap figure`, a README image)
has no table to read and keeps the literal colours. Both are asserted
here on the rendered output, not on the tables.

Three schemes, each a full table, every text token at 4.5:1 on its
ground; and the picker: the page carries all three tables, stamps the
root before the first paint (the stored pick, else light when the system
prefers light, else the configured default), and a pick restamps the
root and is kept in this browser when storage allows.
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
    assert tokens.state("built") == (
        "var(--card-built)",
        "var(--card-built-line)",
        "source recorded",
    )
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


@pytest.mark.parametrize("scheme", list(theme_mod.SCHEMES))
def test_actor_and_inspector_text_clear_four_and_a_half_on_actual_fills(scheme: str) -> None:
    """Acceptance: 4.5:1 on actor, raised, warning and inspector surfaces.

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


def test_the_schemes_are_three_full_tables_and_the_default_is_dark() -> None:
    assert list(theme_mod.SCHEMES) == ["dark", "light", "clay"]
    assert theme_mod.DEFAULT_SCHEME == "dark" and theme_mod.LIGHT_SCHEME == "light"
    keys = {name: set(t) for name, t in theme_mod.SCHEMES.items()}
    assert keys["clay"] == keys["dark"] == keys["light"]
    for name, t in theme_mod.SCHEMES.items():
        assert t["scheme"] == name
        assert t["color_scheme"] == ("light" if name == "light" else "dark")
        assert set(t["layers"]) == set(theme_mod.STANDARD_LAYERS_CLAY)
        assert len(set(t["layers"].values())) == len(t["layers"]), (
            "every standard layer its own hue"
        )
        assert not set(t["layer_palette"]) & set(t["layers"].values()), (
            "a custom layer never takes a standard hue"
        )
    clay = theme_mod.CLAY
    assert clay["bg"] == "#111214" and clay["accent"] == "#cf8b6b" and clay["ink"] == "#fbfcfc"
    assert clay["state"]["built"] == ["#17181b", "#85868a", "source recorded"]
    assert clay["container"]["isolated"] == ["#8c6251", "#1b1716"]
    assert list(clay["layers"].values()) == [
        "#d9cdb2",
        "#82a7ba",
        "#e39a86",
        "#dd9bbd",
        "#b48ec9",
        "#86c9a9",
        "#b7c27c",
    ]
    assert clay["layer_palette"][0] == "#e3b778"
    assert theme_mod.LIGHT["accent"] == "#0a0a0a"


def test_overrides_apply_per_scheme_and_bare_keys_to_the_default(sample: Sample) -> None:
    layers = all_layers(sample.model, sample.meaning)
    t = theme_mod.resolve(
        {"accent": "#111111", "light": {"accent": "#222222", "layers": {"data": "#333333"}}},
        layers,
    )
    assert t["scheme"] == "dark" and t["accent"] == "#111111"
    schemes = t["schemes"]
    assert list(schemes) == ["dark", "light", "clay"]
    assert schemes["dark"]["accent"] == "#111111"
    assert schemes["clay"]["accent"] == theme_mod.CLAY["accent"], "bare keys are the default's"
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
    assert t["schemes"]["clay"]["accent"] == theme_mod.CLAY["accent"]
    with pytest.raises(
        ValueError, match="Unknown theme scheme 'sepia'. The schemes are dark, light, clay"
    ):
        theme_mod.resolve({"scheme": "sepia"}, layers)
    with pytest.raises(ValueError, match="theme.clay must contain a table of CSS tokens"):
        theme_mod.resolve({"clay": "#fff"}, layers)


@pytest.mark.parametrize("name", ["warm", "graphite", "paper"])
def test_removed_themes_are_unavailable(name: str) -> None:
    """The removed theme names must give a configuration error."""
    with pytest.raises(ValueError, match="Unknown theme scheme"):
        theme_mod.resolve({"scheme": name}, [])


# ---- the picker, under the Node driver ------------------------------------------


def drive_theme(html: Path, *flags: str) -> dict[str, Any]:
    args = [shutil.which("node") or "node", str(DRIVER), str(html), "--scenario", "theme", *flags]
    proc = subprocess.run(args, capture_output=True, text=True, timeout=120)
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
    # stamped; the head script names the default and the three.
    assert head.count(":root{") == 1
    for name in ("dark", "light", "clay"):
        assert f':root[data-theme="{name}"]{{' in head, name
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
    assert '["dark", "light", "clay"].indexOf(s)<0' in head
    assert '\'(prefers-color-scheme: light)\').matches)?"light":"dark"' in head
    assert "document.documentElement.setAttribute('data-theme',s)" in head
    assert head.index("<script>") < head.index("<style>"), "the root is stamped before the styles"
    # The picker in the header, one option per scheme.
    assert '<div id="scheme" role="group" aria-label="Theme">' in html
    assert re.findall(r'data-scheme="(\w+)"', html.split("</header>")[0]) == [
        "dark",
        "light",
        "clay",
    ]
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
        ("dark", ("--stored", "graphite"), "dark"),
        ("dark", ("--light", "--stored", "paper"), "light"),
        ("clay", (), "dark"),
        ("light", (), "dark"),
        ("dark", (), "dark"),
        ("clay", ("--light",), "light"),
        ("clay", ("--stored", "dark"), "dark"),
        ("clay", ("--light", "--stored", "clay"), "clay"),
        ("clay", ("--stored", "sepia"), "dark"),
        ("clay", ("--light", "--stored", "sepia"), "light"),
        ("clay", ("--no-storage",), "dark"),
        ("clay", ("--light", "--no-storage"), "light"),
    ],
)
def test_the_scheme_on_load(
    sample: Sample, tmp_path: Path, scheme: str, flags: tuple[str, ...], expected: str
) -> None:
    """The page reads the stored selection first. Without a stored selection,
    the page uses the device theme. The controls also operate without storage."""
    report = drive_theme(sample_page(sample, tmp_path, scheme), *flags)
    assert report["onLoad"] == expected, report
    assert report["pickValue"] == expected, "the picker shows what the root carries"
    assert report["options"] == report["blocks"] == ["dark", "light", "clay"]


@needs_node
def test_a_pick_restamps_the_root_and_is_kept(sample: Sample, tmp_path: Path) -> None:
    report = drive_theme(sample_page(sample, tmp_path))
    assert report["storedOnLoad"] is None, "nothing is stored until the reader picks"
    assert report["switches"] == [
        {"picked": name, "attr": name, "pickValue": name, "stored": name}
        for name in ("dark", "light", "clay")
    ]
    # With storage refused the pick still restamps the root; it is not kept.
    report = drive_theme(sample_page(sample, tmp_path), "--no-storage")
    assert report["storedOnLoad"] == "unavailable"
    assert [(s["picked"], s["attr"], s["stored"]) for s in report["switches"]] == [
        (name, name, "unavailable") for name in ("dark", "light", "clay")
    ]


@needs_node
def test_the_self_map_page_stamps_dark_and_switches() -> None:
    assert SELF_MAP.is_file(), "the committed page; run systemap refresh"
    report = drive_theme(SELF_MAP)
    assert report["onLoad"] == "dark"
    assert [s["attr"] for s in report["switches"]] == ["dark", "light", "clay"]
    assert drive_theme(SELF_MAP, "--light")["onLoad"] == "light"


def _relative_luminance(value: str) -> float:
    """The WCAG relative luminance of a #rrggbb colour."""
    digits = value.lstrip("#")[:6]
    channels = [int(digits[i : i + 2], 16) / 255 for i in (0, 2, 4)]

    def linear(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (linear(c) for c in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(one: str, other: str) -> float:
    """The WCAG contrast ratio between two colours, lighter over darker."""
    a, b = _relative_luminance(one), _relative_luminance(other)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


# Colours that are never text or a mark a reader must read: the two rules,
# the unlit edge, the tint behind a selection, and a change map's ghost.
NOT_READ = frozenset({"bg", "surface", "raised", "accent_soft", "line", "line_2", "flow", "ghost"})
# Every surface a token can be drawn on, so a token tuned to the ground
# alone cannot fall below the floor on a panel or a chip.
GROUNDS = ("bg", "surface", "raised")
FLOOR = 4.5


def test_every_scheme_clears_the_text_floor_on_every_surface() -> None:
    for name, scheme in theme_mod.SCHEMES.items():
        grounds = [scheme[key] for key in GROUNDS]
        tokens = {
            key: value
            for key, value in scheme.items()
            if isinstance(value, str) and value.startswith("#") and key not in NOT_READ
        }
        tokens.update({f"layer {k}": v for k, v in scheme["layers"].items()})
        tokens.update({f"palette {i}": v for i, v in enumerate(scheme["layer_palette"])})
        for key, value in tokens.items():
            worst = min(_contrast(value, ground) for ground in grounds)
            assert worst >= FLOOR, (
                f"{name}: {key} ({value}) reads at {worst:.2f} to 1 on the surface "
                f"it contrasts least with; the floor is {FLOOR} to 1"
            )
