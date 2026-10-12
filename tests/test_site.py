"""The website in docs/: the build, the committed files, the links, and the tokens.

`site/build.py` is not part of the package, so the tests load it by path.
The test pages in tests/fixtures/site/pages show the guide page rules:
the order, the summary, the heading ids, the links, and the page parts.
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

from systemap import __version__, page_font
from systemap import theme as theme_mod

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
PAGES = Path(__file__).resolve().parent / "fixtures" / "site" / "pages"


@pytest.fixture(scope="module")
def site() -> ModuleType:
    spec = importlib.util.spec_from_file_location("site_build", ROOT / "site" / "build.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["site_build"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def fixture_site(site: ModuleType) -> dict[str, str]:
    files = site.build(site.Inputs(pages_dir=PAGES))
    return {k: v.decode("utf-8") for k, v in files.items() if not k.endswith(".woff2")}


def committed(site: ModuleType) -> dict[str, bytes]:
    names = ["index.html", ".nojekyll"]
    names += [
        p.relative_to(DOCS).as_posix() for d in site.OWNED_DIRS for p in (DOCS / d).rglob("*")
    ]
    return {n: (DOCS / n).read_bytes() for n in names if (DOCS / n).is_file()}


def test_the_committed_site_is_the_build(site: ModuleType) -> None:
    problems = site.differences(site.build(), DOCS)
    assert problems == [], "Run: uv run --group site python site/build.py\n" + "\n".join(problems)


def test_each_committed_link_and_anchor_has_a_target(site: ModuleType) -> None:
    files = committed(site)
    assert "guide/reference.html" in files
    assert site.broken_links(files, site.static_exists(DOCS, set(files))) == []


def test_the_pages_load_nothing_from_another_site(site: ModuleType) -> None:
    files = committed(site)
    css = files["assets/site.css"].decode("utf-8")
    assert "@import" not in css
    assert re.findall(r"url\(([^)]*)\)", css) == ["inter.woff2"]
    for name, data in files.items():
        if name.endswith(".html"):
            text = data.decode("utf-8")
            loads = [u for tag, u in site.urls(text) if tag in site.LOADS]
            assert not [u for u in loads if site.EXTERNAL.match(u)], name


def test_guide_pages_come_in_number_order_with_their_summaries(
    fixture_site: dict[str, str],
) -> None:
    home = fixture_site["guide/index.html"]
    assert home.index("Make the first map") < home.index("Read the map") < home.index("Benchmarks")
    assert "This test page tells the site generator how a guide page looks." in home
    page = fixture_site["guide/first-map.html"]
    assert "<title>Make the first map · systemap</title>" in page
    assert ">Guide · 1 of 2</p>" in page
    assert '<p class="lead">This test page tells' in page
    assert 'href="read-the-map.html" rel="next"' in page
    assert '<a href="first-map.html" aria-current="page">' in page
    assert "<!-- loader: update after the merge -->" in page


def test_heading_ids_follow_the_documented_rule(
    site: ModuleType, fixture_site: dict[str, str]
) -> None:
    assert site.slugify("What does `systemap check` reject?") == "what-does-systemap-check-reject"
    assert site.slugify("systemap init [--no-ci | --strict-ci]") == "systemap-init-no-ci-strict-ci"
    assert site.slugify("[delta] page_url") == "delta-page-url"
    assert site.slugify("?!") == "section"
    page = fixture_site["guide/first-map.html"]
    for hid in ("install-systemap", "install-systemap-2", "systemap-extract-check", "main-2"):
        assert f'id="{hid}"' in page
    assert '<li class="toc__l3"><a href="#systemap-extract-check"><code>' in page


def test_links_go_to_the_site_or_to_the_repository(fixture_site: dict[str, str]) -> None:
    first = fixture_site["guide/first-map.html"]
    assert 'href="reference.html#what-does-systemap-check-reject"' in first
    assert 'href="../map/"' in first
    assert (
        'href="https://github.com/0xfauzi/systemap/blob/main/src/systemap/skill/references/'
        'language.md"' in first
    )
    assert 'href="benchmarks.html"' in fixture_site["guide/read-the-map.html"]
    reference = fixture_site["guide/reference.html"]
    assert 'href="https://github.com/0xfauzi/systemap/blob/main/README.md"' in reference
    assert 'href="https://github.com/0xfauzi/systemap/blob/main/bench/jev/README.md"' in reference


def test_a_link_without_a_target_stops_the_build(site: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "01-page.md").write_text(
        "# Page\n\nSee [the rule](reference.html#no-such-rule) and [this](missing.html).\n",
        encoding="utf-8",
    )
    with pytest.raises(site.SiteError) as error:
        site.build(site.Inputs(pages_dir=tmp_path))
    assert "reference.html#no-such-rule has no id 'no-such-rule'" in str(error.value)
    assert "missing.html has no file" in str(error.value)


@pytest.mark.parametrize(
    ("name", "text", "message"),
    [
        ("1-page.md", "# Page\n\nSummary.\n", "NN-slug.md"),
        ("01-page.md", "Page\n\nSummary.\n", "'# Title'"),
        ("01-page.md", "# Page\n\n## Section\n", "summary paragraph"),
        ("01-reference.md", "# Page\n\nSummary.\n", "reserved"),
    ],
)
def test_a_guide_page_without_its_parts_stops_the_build(
    site: ModuleType, tmp_path: Path, name: str, text: str, message: str
) -> None:
    (tmp_path / name).write_text(text, encoding="utf-8")
    with pytest.raises(site.SiteError, match=re.escape(message)):
        site.build(site.Inputs(pages_dir=tmp_path))


def test_check_finds_a_changed_and_an_extra_file(site: ModuleType, tmp_path: Path) -> None:
    files = site.build()
    site.write(files, tmp_path)
    assert site.differences(files, tmp_path) == []
    (tmp_path / "guide" / "old.html").write_text("old", encoding="utf-8")
    (tmp_path / "index.html").write_text("changed", encoding="utf-8")
    assert site.differences(files, tmp_path) == [
        "differs: index.html",
        "not made by the build: guide/old.html",
    ]
    site.write(files, tmp_path)
    assert not (tmp_path / "guide" / "old.html").exists()


def test_the_site_uses_the_tokens_and_the_font_of_the_map_page(
    fixture_site: dict[str, str], site: ModuleType
) -> None:
    css = fixture_site["assets/site.css"]
    for key in site.SITE_TOKENS:
        for table in (theme_mod.DARK, theme_mod.LIGHT):
            assert f"{theme_mod.CSS_NAMES[key]}:{table[key]};" in css
    assert f"--fs:{theme_mod.SANS};" in css and f"--fm:{theme_mod.MONO};" in css
    assert "--radius-control:6px;" in css and "--space-header:52px;" in css
    assert "--t-layer-question-size:22px;" in css
    font = site.build()["assets/inter.woff2"]
    assert hashlib.sha256(font).hexdigest() == page_font.WOFF2_SHA256
    assert f"Version <code>{__version__}</code>" in fixture_site["index.html"]
