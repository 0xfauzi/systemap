"""Type rules of the map page: the fonts, the type scale and the smallest sizes.

The page uses the fonts of the computer and loads no font files. Card descriptions
use Arial or a font with the same measured character widths. Running text is 12px or
more, and no page text is less than 11px. DESIGN.md gives the font stacks of theme.py.
"""

from __future__ import annotations

import re
from pathlib import Path

from conftest import Sample

from systemap import page
from systemap import theme as theme_mod
from systemap.schematic import render as render_schematic
from systemap.schematic_cards import NAME_ADVANCE, PLAIN_FONT

DESIGN = Path(__file__).resolve().parents[1] / "DESIGN.md"
SIZE = r"(\d+(?:\.\d+)?)px"


def page_css(sample: Sample) -> str:
    html = page.build(
        sample.cfg, sample.model, sample.meaning, sample.theme, sample.facts, {"has_change": False}
    )
    return "".join(re.findall(r"<style>(.*?)</style>", html, flags=re.S))


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
        entries[name][key] = value.strip("'\"")
    return entries


def test_the_page_loads_no_font_files(sample: Sample) -> None:
    css = page_css(sample)
    assert "@font-face" not in css
    assert "woff" not in css


def test_no_page_text_is_less_than_eleven_pixels(sample: Sample) -> None:
    sizes = font_sizes(page_css(sample))
    assert sizes, "the page sets font sizes"
    assert min(sizes) >= 11


def test_running_text_is_twelve_pixels_or_more(sample: Sample) -> None:
    css = page_css(sample)
    for selector in (".ix__match", ".readpanel .fg-flow small", ".read__step small"):
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
    assert set(families.values()) == {theme_mod.SANS, theme_mod.MONO, PLAIN_FONT}
    assert families["body"] == theme_mod.SANS
    assert families["card-name"] == theme_mod.MONO
    assert families["card-plain"] == PLAIN_FONT
    css = page_css(sample)
    assert f"font-size:{entries['body']['fontSize']}" in rule(css, "body")
    assert f"--fs:{theme_mod.SANS};" in css
    assert f"--fm:{theme_mod.MONO};" in css
