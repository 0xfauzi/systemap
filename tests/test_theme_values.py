"""A theme value that rendering cannot use gives a configuration error, not a crash.

Acceptance (Codex result schematic-9):

- For each theme token and each value of an incorrect type or shape in `BAD`,
  `theme.resolve` gives ValueError, or the page and the interactive figure render
  without an exception. On the base, 60 of these values crash the render (a probe
  found them in `state`, `container`, `ghost`, `delta` and `font_ui`). After the
  repair, the count is zero.
- `[theme] state = 5` on a map with components gives ConfigError from `systemap check`,
  with the cause in the message. The command does not crash.
- The default themes and correct overrides of these tables still resolve.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from conftest import STARTER_MODULES, Sample, init_two_cards, write_tree

from systemap import figure, page
from systemap import theme as theme_mod
from systemap.cli import main
from systemap.model import all_layers

BAD: list[Any] = [
    5,
    1.5,
    "x",
    [],
    {},
    ["a"],
    {"k": 5},
    {"k": "x"},
    {"k": []},
    {"k": ["a"]},
    {"k": ["a", "b"]},
    {"k": ["a", "b", "c"]},
    {"k": ["a", "b", "c", "d"]},
    {"built": 5},
    [5, 5],
    ["a", "b"],
    ["a", "b", "c"],
    None,
    True,
]


def test_no_theme_value_crashes_the_render(sample: Sample) -> None:
    layers = all_layers(sample.model, sample.meaning)
    crashes: list[tuple[str, object, str]] = []
    for key in sorted(theme_mod.DARK):
        for bad in BAD:
            try:
                t = theme_mod.resolve({key: bad}, layers)
            except ValueError:
                continue
            try:
                page.build(
                    sample.cfg, sample.model, sample.meaning, t, sample.facts, {"has_change": False}
                )
                figure.make(
                    sample.cfg, sample.model, sample.meaning, t, sample.facts, interactive=True
                )
            except Exception as exc:  # noqa: BLE001 - the test counts each crash
                crashes.append((key, bad, repr(exc)))
    assert crashes == []


@pytest.mark.parametrize(
    ("tokens", "cause"),
    [
        ({"state": 5}, r"theme value state must be a table"),
        ({"state": {"built": ["#000000", "#FFFFFF"]}}, r"theme value state\.built must be a list"),
        ({"light": {"container": {"host": "none"}}}, r"theme value container\.host must be"),
        ({"ghost": ["#000000"]}, r"theme value ghost must be a list"),
        ({"delta": {"tests": 5}}, r"theme value delta\.tests must be text"),
        ({"font_ui": 5}, r"theme value font_ui must be text"),
        ({"ink": 5}, r"theme value ink must be text"),
    ],
)
def test_the_error_gives_the_key_and_the_cause(
    sample: Sample, tokens: dict[str, Any], cause: str
) -> None:
    with pytest.raises(ValueError, match=cause):
        theme_mod.resolve(tokens, all_layers(sample.model, sample.meaning))


def test_correct_tables_still_resolve(sample: Sample) -> None:
    layers = all_layers(sample.model, sample.meaning)
    t = theme_mod.resolve(
        {
            "state": {"built": ["#000000", "#FFFFFF", "built"]},
            "container": {"host": ["#37332D", "none"]},
            "ghost": ["#1C1A17", "#37332D"],
            "delta": {"tests": "#989184"},
        },
        layers,
    )
    assert t["state"]["built"] == ["#000000", "#FFFFFF", "built"]
    for scheme in theme_mod.SCHEMES:
        theme_mod.resolve({"scheme": scheme}, layers)


@pytest.fixture
def two_card(tmp_path: Path) -> Path:
    write_tree(tmp_path, {"pkg/__init__.py": "", **STARTER_MODULES})
    init_two_cards(tmp_path, "--no-ci")
    assert main(["--root", str(tmp_path), "extract"]) == 0
    return tmp_path


def test_check_reports_a_scalar_state_as_a_configuration_error(
    two_card: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = two_card / "systemap.toml"
    config.write_text(config.read_text(encoding="utf-8") + "\n[theme]\nstate = 5\n")
    assert main(["--root", str(two_card), "check"]) == 2
    err = capsys.readouterr().err
    assert "theme value state must be a table" in err
