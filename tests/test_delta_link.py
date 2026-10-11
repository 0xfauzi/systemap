"""The pull request comment is one link to the Changes view, and only if the repository sets it up.

`[delta] page_url` gives the URL of the map page that the repository publishes for each
pull request, with `{number}` for the pull request number. The configuration reader
refuses a value that cannot give that link, with one line that names the key.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import STARTER_MODULES, init_two_cards, write_tree

from systemap import config, delta_link
from systemap.cli import main

URL = "https://example.org/pr-{number}/"


@pytest.fixture
def two_cards(tmp_path: Path) -> Path:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    return tmp_path


def add_config(root: Path, text: str) -> None:
    """Put configuration text at the end of the file."""
    path = root / "systemap.toml"
    path.write_text(path.read_text(encoding="utf-8") + "\n" + text, encoding="utf-8")


# ---- the configuration value ------------------------------------------------------


def test_the_page_url_is_empty_without_the_table(two_cards: Path) -> None:
    assert config.load(two_cards).delta_page_url == ""


def test_the_page_url_loads_with_its_number_placeholder(two_cards: Path) -> None:
    add_config(two_cards, f'[delta]\npage_url = "{URL}"\n')
    assert config.load(two_cards).delta_page_url == URL


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ('delta = "x"', "delta must be a table"),
        ('[delta]\nurl = "x"', "delta has an unknown key: url"),
        ("[delta]\npage_url = 4", "delta.page_url must be a string"),
        ('[delta]\npage_url = "example.org/pr-{number}/"', "must start with https:// or http://"),
        ('[delta]\npage_url = "https://example.org/pr/"', "must contain {number}"),
        ('[delta]\npage_url = "https://example.org/{pr}/{number}/"', "only the {number}"),
        ('[delta]\npage_url = "https://example.org/{number}/#map"', "must not contain #"),
        ('[delta]\npage_url = "https://example.org/{number}/ x"', "must not contain #"),
    ],
)
def test_a_page_url_that_cannot_give_the_link_is_a_configuration_error(
    two_cards: Path, capsys: pytest.CaptureFixture[str], text: str, said: str
) -> None:
    path = two_cards / "systemap.toml"
    body = path.read_text(encoding="utf-8")
    # A top-level key must come before the first table of the file.
    top = text.startswith("delta =")
    path.write_text(f"{text}\n{body}" if top else f"{body}\n{text}\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="systemap.toml: delta"):
        config.load(two_cards)
    assert main(["--root", str(two_cards), "check"]) == 2
    err = capsys.readouterr().err
    assert said in err
    assert "Correct systemap.toml or the model module." in err


# ---- the comment --------------------------------------------------------------------


def test_the_comment_is_the_marker_and_one_link_to_the_changes_view() -> None:
    assert delta_link.comment(URL, 42, 0) == (
        "<!-- systemap delta -->\n"
        "[Open the Changes view of the map](https://example.org/pr-42/#changes)\n"
    )


def test_the_comment_says_when_the_map_needs_an_update() -> None:
    lines = delta_link.comment(URL, 7, 3).splitlines()
    assert lines[1] == "[Open the Changes view of the map](https://example.org/pr-7/#changes)"
    assert lines[2:] == [
        "",
        "The map needs an update (3 lines). The log of the delta job gives the action "
        "for each line.",
    ]
    assert "(1 line)" in delta_link.comment(URL, 7, 1)
