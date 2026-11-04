"""The map path, the page title, the hint and the keys of the navigation between maps."""

from __future__ import annotations

import re

from systemap import page_csp, page_motion, page_nav
from systemap.model import Component
from systemap.schematic_cards import opens_label


def test_the_title_gives_the_map_id_and_the_level() -> None:
    assert page_nav.title("demo", "") == "demo system map"
    assert page_nav.title("demo", "Gateway") == "demo system map: Gateway (level 1)"
    assert page_nav.title("demo", "Gateway/Routes") == "demo system map: Gateway/Routes (level 2)"


def test_the_heading_is_the_last_segment() -> None:
    assert page_nav.heading("demo", "") == "demo"
    assert page_nav.heading("demo", "Gateway/Routes/Auth") == "Auth"


def test_the_path_has_one_link_for_each_ancestor() -> None:
    assert page_nav.path("demo", "") == ""
    nav = page_nav.path("demo", "Gateway/Routes/Auth")
    links = re.findall(r'<a class="crumb" href="([^"]+)">.*?</span>([^<]+)</a>', nav)
    assert links == [
        ("../../../index.html", "demo"),
        ("../../index.html", "Gateway"),
        ("../index.html", "Routes"),
    ]
    assert nav.count('aria-current="page"') == 1
    assert '<li class="sr-only"><span aria-current="page">Auth</span></li></ol></nav>' in nav
    assert nav.startswith('<nav class="crumbs" id="mappath" aria-label="Map path" ')
    assert 'data-up="../index.html#Auth"' in nav
    # One separator for each ancestor, hidden from screen readers; the phone mark also.
    assert nav.count('<span class="crumb__sep" aria-hidden="true">/</span>') == 3
    assert nav.count('<span class="crumb__back" aria-hidden="true">&lt; </span>') == 3


def test_model_text_in_the_path_is_escaped_and_the_fragment_is_quoted() -> None:
    nav = page_nav.path('a"<b>', 'x"y/c d')
    assert "<b>" not in nav and "a&quot;&lt;b&gt;" in nav
    assert 'data-up="../index.html#c%20d"' in nav
    assert page_nav.up_href("") == ""


def test_the_hint_names_the_keys_that_apply() -> None:
    assert page_nav.hint("", False) == ""
    assert "Double-click" in page_nav.hint("", True) and "U" not in page_nav.hint("", True)
    both = page_nav.hint("Gateway", True)
    assert both.startswith('<p class="hint sr-only">Double-click')
    assert both.endswith("Press U to go to the parent map.</p>")


def test_the_keys_sheet_lists_u_and_t_before_the_question_mark() -> None:
    sheet = page_motion.keys_sheet(page_nav.keys("Gateway", True))
    keys = re.findall(r"<dt>(.*?)</dt>", sheet)
    assert keys[-4:] == ["<kbd>U</kbd>", "<kbd>T</kbd>", "<kbd>?</kbd>", "<kbd>Esc</kbd>"]
    assert "<dd>Go to the parent map</dd>" in sheet
    assert "<dd>Open the map tree</dd>" in sheet
    assert "<kbd>U</kbd>" not in page_motion.keys_sheet()


def test_the_keys_sheet_lists_only_the_keys_that_operate_on_the_page() -> None:
    assert page_nav.keys("", False) == ()
    assert page_nav.keys("", True) == (page_nav.TREE_KEY,)
    assert page_nav.keys("Gateway", False) == (page_nav.UP_KEY,)


def test_the_policy_permits_no_frame() -> None:
    policy = page_csp.policy("<html></html>")
    assert "frame-src 'none'" in policy and "frame-src 'self'" not in policy


def test_the_card_label_tells_that_the_card_opens_a_map() -> None:
    plain = Component("Store", "keeps rows")
    card = Component("Gateway", "serves requests", map="gateway.py")
    assert opens_label(plain, {}) == ""
    assert opens_label(card, {}) == ", opens the map Gateway"
    one = {"Gateway": {"name": "Gateway", "href": "Gateway/index.html", "cards": 1}}
    assert opens_label(card, one) == ", opens the map Gateway with 1 component"
    twelve = {"Gateway": {"name": "Gateway", "href": "", "cards": 12}}
    assert opens_label(card, twelve) == ", opens the map Gateway with 12 components"
