"""Type rules of the map page: the fonts, the type scale and the smallest sizes.

The page contains one font, a subset of Inter, as a data URI. It loads no font files.
Map text with a measured width keeps its font: flow labels and container descriptions
use the system sans font, and card descriptions use Arial or a font with the same
measured character widths. Running text is 12px or more, and no page text is less
than 11px. DESIGN.md gives the font stacks of theme.py.
"""

from __future__ import annotations

import base64
import hashlib
import re
import xml.etree.ElementTree as ET
from importlib import resources
from pathlib import Path

from conftest import Sample

from systemap import page, page_font
from systemap import theme as theme_mod
from systemap.schematic import render as render_schematic
from systemap.schematic_cards import NAME_ADVANCE, PLAIN_FONT, container_header

DESIGN = Path(__file__).resolve().parents[1] / "DESIGN.md"
SIZE = r"(\d+(?:\.\d+)?)px"


def page_html(sample: Sample) -> str:
    return page.build(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {"has_change": False}
    )


def page_css(sample: Sample) -> str:
    return "".join(re.findall(r"<style>(.*?)</style>", page_html(sample), flags=re.S))


def rule(css: str, selector: str) -> str:
    """Give the declarations of the first rule with exactly this selector."""
    found = re.search(r"(?:^|[}])" + re.escape(selector) + r"\{([^}]*)\}", css)
    assert found, selector
    return found[1]


def font_sizes(css: str) -> list[float]:
    """Give each font size in px from `font-size` and from the `font` shorthand."""
    sizes = [float(s) for s in re.findall(r"font-size:" + SIZE, css)]
    for value in re.findall(r"(?<![-\w])font:([^;}]*)", css):
        match = re.search(r"(?:^|\s)" + SIZE + r"(?:/|\s)", value)
        if match:
            sizes.append(float(match[1]))
    return sizes


def design_typography() -> dict[str, dict[str, str]]:
    """Give the typography entries of the DESIGN.md front matter."""
    front = DESIGN.read_text(encoding="utf-8").split("\n---\n", 1)[0]
    block = re.search(r"^typography:\n((?:  .*\n)+)", front, flags=re.M)
    assert block
    entries: dict[str, dict[str, str]] = {}
    name = ""
    for line in block[1].splitlines():
        if not line.startswith("    "):
            name = line.strip().rstrip(":")
            entries[name] = {}
            continue
        key, _, value = line.strip().partition(": ")
        if len(value) > 1 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        entries[name][key] = value
    return entries


def test_the_page_contains_one_font_and_loads_no_font_files(sample: Sample) -> None:
    css = page_css(sample)
    assert css.count("@font-face") == 1
    assert css.startswith(page_font.FACE)
    assert '@font-face{font-family:"systemap Inter";src:url(data:font/woff2;base64,' in css
    assert "font-weight:400 700;font-display:block}" in css
    assert "url(http" not in css and "@import" not in css


def test_the_embedded_font_is_the_recorded_subset() -> None:
    """scripts/inter_subset.py writes the font and its size and SHA-256 value together."""
    data = base64.b64decode(page_font.WOFF2_BASE64, validate=True)
    assert data[:4] == b"wOF2"
    assert len(data) == page_font.WOFF2_BYTES
    assert hashlib.sha256(data).hexdigest() == page_font.WOFF2_SHA256


def test_the_font_has_each_character_of_the_sans_text(sample: Sample) -> None:
    """A character outside the subset shows in a different font. A new one needs a new subset.

    The left, up and down arrows and the command key symbol show only in keyboard keys,
    which use the monospace font. Inter has no U+21C4, so the system sans font shows it."""
    html = page_html(sample)
    font = set(page_font.CHARACTERS)
    assert {chr(c) for c in range(32, 127)} <= font
    assert {"·", "→", "−"} <= font
    assert "content:'\\2212'" in html, "an open section shows a minus sign"
    used = {c for c in html if ord(c) > 126}
    assert used - font <= {"←", "↑", "↓", "⌘", "⇄"}


def test_the_package_contains_the_font_license() -> None:
    text = (resources.files("systemap") / "fonts" / "Inter-OFL.txt").read_text(encoding="utf-8")
    assert text.startswith("Copyright (c) 2016-2018 The Inter Project Authors")
    assert "SIL OPEN FONT LICENSE Version 1.1" in text
    assert page_font.__doc__ and "fonts/Inter-OFL.txt" in page_font.__doc__


def test_measured_map_text_keeps_the_system_sans_font(sample: Sample) -> None:
    """The renderer gives each character of a flow label and a container description a width.

    Inter is wider than that width for most characters. On the page, a text class gets its
    sans font from --fs, so the rule sets --fs on these text elements. A separate figure
    does not contain Inter and does not need the rule."""
    args = (sample.model, sample.meaning, sample.theme, sample.facts)
    svg, _detail = render_schematic(*args, variables=True)
    rule = f"#schematic .view>text,#schematic .flowlbl text{{--fs:{theme_mod.SYSTEM_SANS}}}"
    assert rule in svg
    figure, _detail = render_schematic(*args)
    assert "--fs:" not in figure
    # The direct text children of the view are the container labels and descriptions.
    ns = "{http://www.w3.org/2000/svg}"
    view = ET.fromstring(svg).find(f".//{ns}g[@class='view']")
    assert view is not None
    texts = [e for e in view if e.tag == f"{ns}text"]
    expected = sum(1 + len(container_header(box)[1]) for box in sample.model.containers)
    assert len(texts) == expected == 3
    labels = [g for g in view.iter(f"{ns}g") if "flowlbl" in g.get("class", "").split()]
    assert labels and all(g.find(f"{ns}text") is not None for g in labels)


def test_no_page_text_is_less_than_eleven_pixels(sample: Sample) -> None:
    sizes = font_sizes(page_css(sample))
    assert sizes, "the page sets font sizes"
    assert min(sizes) >= 11


def test_running_text_is_twelve_pixels_or_more(sample: Sample) -> None:
    css = page_css(sample)
    for selector in (".pal__s", ".readpanel .fg-flow small", ".read__step small"):
        assert min(font_sizes(selector + "{" + rule(css, selector) + "}")) >= 12, selector
    body = rule(css, "body")
    assert "font-size:13px" in body


def test_a_layer_name_in_the_guide_steps_uses_the_sans_font(sample: Sample) -> None:
    assert "var(--fs)" in rule(page_css(sample), ".read__step small")


def test_card_descriptions_use_the_measured_font(sample: Sample) -> None:
    svg, _detail = render_schematic(sample.model, sample.meaning, sample.theme, sample.facts)
    assert PLAIN_FONT == 'Arial,"Liberation Sans",Arimo,sans-serif'
    assert (
        f'[data-layer="job"] text{{font-family:{PLAIN_FONT};'
        "font-kerning:none;font-variant-ligatures:none}"
    ) in svg


def test_the_name_advance_is_not_less_than_the_measured_mono_width() -> None:
    """DejaVu Sans Mono, the Linux default, has 1233 of 2048 units for each character."""
    assert NAME_ADVANCE >= 1233 / 2048


def test_design_md_gives_the_font_stacks_of_the_theme(sample: Sample) -> None:
    entries = design_typography()
    families = {name: entry["fontFamily"] for name, entry in entries.items()}
    stacks = {theme_mod.SANS, theme_mod.SYSTEM_SANS, theme_mod.MONO, PLAIN_FONT}
    assert set(families.values()) == stacks
    assert theme_mod.SANS == f"{page_font.FAMILY},{theme_mod.SYSTEM_SANS}"
    assert families["body"] == theme_mod.SANS
    assert families["flow-label"] == families["container-description"] == theme_mod.SYSTEM_SANS
    assert families["card-name"] == theme_mod.MONO
    assert families["card-plain"] == PLAIN_FONT
    css = page_css(sample)
    assert f"font-size:{entries['body']['fontSize']}" in rule(css, "body")
    assert f"--fs:{theme_mod.SANS};" in css
    assert f"--fm:{theme_mod.MONO};" in css
