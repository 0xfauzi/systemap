"""The guide pages in site/pages/ obey the page contract of the site and the mechanical writing rules.

site/build.py renders each page as guide/<slug>.html. The first line is the title and
the first paragraph is the summary. A program cannot show the meanings of words or that
a claim agrees with the code. These tests examine only the rules that a program can
examine: the file names, the title and the summary, the page length, em dashes,
semicolons and contractions in prose, and the links between guide pages.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PAGES = Path(__file__).resolve().parent.parent / "site" / "pages"
NAME = re.compile(r"(\d\d)-([a-z0-9]+(?:-[a-z0-9]+)*)\.md")
# The site specification asks for pages under about 250 lines.
MAX_LINES = 250
# The pages that the build makes from docs/*.md. A guide page can link to them.
REFERENCE_SLUGS = {"reference", "benchmarks"}
CONTRACTION = re.compile(r"\b[A-Za-z]+'(t|re|ve|ll|d|m)\b")
GUIDE_LINK = re.compile(r"\]\(([a-z0-9-]+)\.html(?:#[a-z0-9-]+)?\)")
# The coordinator updates this paragraph after the model loader changes.
LOADER_MARK = "<!-- loader: update after the merge -->"


def _pages() -> list[Path]:
    return sorted(PAGES.glob("*.md"))


def _prose(text: str) -> str:
    """Give the text without fenced code blocks, code spans, and HTML comments."""
    text = re.sub(r"^```.*?^```", "", text, flags=re.M | re.S)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", text)


def test_the_site_has_guide_pages() -> None:
    assert len(_pages()) >= 8


@pytest.mark.parametrize("path", _pages(), ids=lambda p: p.name)
def test_page_has_a_name_a_title_and_a_summary(path: Path) -> None:
    assert NAME.fullmatch(path.name), path.name
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("# ")
    assert lines[1] == ""
    assert lines[2] and not lines[2].startswith(("#", "-", "|", "```", "<")), lines[2]
    assert len(lines) <= MAX_LINES


@pytest.mark.parametrize("path", _pages(), ids=lambda p: p.name)
def test_prose_has_no_dash_semicolon_or_contraction(path: Path) -> None:
    prose = _prose(path.read_text(encoding="utf-8"))
    assert "\u2014" not in prose
    assert "\u2013" not in prose
    assert ";" not in prose
    assert not CONTRACTION.search(prose), CONTRACTION.search(prose)


def test_links_name_a_guide_page_or_the_reference() -> None:
    slugs = {m[2] for p in _pages() if (m := NAME.fullmatch(p.name))} | REFERENCE_SLUGS
    for path in _pages():
        for target in GUIDE_LINK.findall(path.read_text(encoding="utf-8")):
            assert target in slugs, f"{path.name}: {target}.html"


def test_trust_page_marks_the_loader_paragraph() -> None:
    (trust,) = PAGES.glob("*-trust-and-security.md")
    assert LOADER_MARK in trust.read_text(encoding="utf-8")
