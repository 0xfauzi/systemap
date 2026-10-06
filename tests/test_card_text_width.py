"""The test requires description widths of 130 units or less at a minimum font height of 11px."""

from __future__ import annotations

from dataclasses import replace
from xml.etree import ElementTree

import pytest
from conftest import Sample

from systemap.schematic import render
from systemap.schematic_cards import PLAIN_WIDTH, TEXT_PX, card_text, plain_inset, plain_width


def test_describe_description_keeps_all_words() -> None:
    assert plain_width("The diagram measurements") == pytest.approx(137.55908203125)
    names, lines, problems = card_text("component", "Describe", "The diagram measurements")
    assert names == ["Describe"]
    assert lines == ["The diagram", "measurements"]
    assert problems == []
    assert all(plain_width(line) <= PLAIN_WIDTH for line in lines)
    assert TEXT_PX == 11


def test_wide_words_use_two_measured_lines() -> None:
    text = "WWW WWW WWW WWW"
    names, lines, problems = card_text("component", "Reader", text)
    assert names == ["Reader"]
    assert lines == ["WWW WWW WWW", "WWW"]
    assert " ".join(lines) == text
    assert all(plain_width(line) <= PLAIN_WIDTH for line in lines)
    assert problems == []


def test_narrow_word_uses_its_measured_width() -> None:
    text = "i" * 40
    assert card_text("component", "Reader", text) == (["Reader"], [text], [])
    assert plain_width(text) <= PLAIN_WIDTH


@pytest.mark.parametrize("text", ["W" * 26, "M" * 26])
def test_wide_word_gives_existing_size_finding(text: str) -> None:
    names, lines, problems = card_text("component", "Reader", text)
    assert names == ["Reader"]
    assert lines == []
    assert problems == [
        "card Reader: plain word does not fit (component cards fit about 26 "
        f"characters on two lines; this one has {len(text)})"
    ]


@pytest.mark.parametrize(
    "text,char",
    [
        ("café", "\u00e9"),
        ("\u4e00", "\u4e00"),
        ("café café", "\u00e9"),
        ("The\u00a0source", "\u00a0"),
        ("The\u2003source", "\u2003"),
        ("The\vsource", "\v"),
        ("The\fsource", "\f"),
    ],
)
def test_unmeasured_character_gives_explicit_diagnostic(text: str, char: str) -> None:
    names, lines, problems = card_text("component", "Reader", text)
    assert names == ["Reader"]
    assert lines == []
    assert problems == [f"card Reader: description width is not measured for character {char!r}"]


@pytest.mark.parametrize("separator", ["\t", "\n", "\r", " \t\n\r"])
def test_ascii_separator_keeps_the_measured_description(separator: str) -> None:
    assert card_text("component", "Reader", f"The{separator}source") == (
        ["Reader"],
        ["The source"],
        [],
    )


def test_final_glyph_overhang_is_inside_the_width() -> None:
    assert plain_width("f") == pytest.approx((569 + 71) * 11 / 2048)
    assert plain_width("_") == pytest.approx((1139 + 23) * 11 / 2048 + 0.2)


@pytest.mark.parametrize(
    "text,overhang,offset", [("A", 3, 0.1), ("_", 31, 0.2), ("j", 94, 0.6), ("w", 3, 0.1)]
)
def test_first_glyph_offset_preserves_the_left_margin(
    text: str, overhang: int, offset: float
) -> None:
    assert plain_inset(text) == offset
    assert plain_inset(text) >= overhang * 11 / 2048
    assert plain_width(text) >= plain_inset(text)


@pytest.mark.parametrize("text,left_bearing", [("A", -3), ("_", -31), ("j", -94), ("w", -3)])
def test_rendered_description_origin_preserves_margin(
    sample: Sample, text: str, left_bearing: int
) -> None:
    meaning = replace(sample.meaning, plain={**sample.meaning.plain, "Parser": text})
    svg, _detail = render(sample.model, meaning, sample.theme, sample.facts)
    node = ElementTree.fromstring(svg).find(".//{*}g[@data-id='Parser']")
    assert node is not None
    box = node.find("{*}rect[@class='node__box']")
    description = node.find("{*}g[@data-layer='job']/{*}text")
    assert box is not None and description is not None
    assert description.text == text
    first_character_left = float(description.attrib["x"]) + left_bearing * 11 / 2048
    assert first_character_left >= float(box.attrib["x"]) + 10
