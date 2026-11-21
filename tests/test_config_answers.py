"""The answer reader validates the module role keys of an answer before judgement.

Acceptance values (specification section 5.3):

1. Each static text of section 5.3 is the full message, with the location and the label.
2. A correct `helper`, `handoff` and `mixed` answer gives an `Answer` with `role`,
   `symbol` and `handoff`. A `helper` answer without a symbol is not a static error.
3. An answer without the three keys gives the same `Answer` as before, with empty values.
4. The configuration reader changes each ValueError to a ConfigError with the same text.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from systemap import config, config_answers
from systemap.config import ConfigError

DIGEST = "a" * 64
WHERE = "systemap.toml: judgement.answered[1]"
USE = "module use: other components import pkg.html and no flow connects them to its component"
NESTED_USE = "Orm: " + USE
OTHER = "crossing import: A imports B and no flow connects them"


def entry(**keys: Any) -> dict[str, Any]:
    return {"reason": "The module formats text in the code of the caller.", **keys}


def read(*entries: dict[str, Any]) -> tuple[config_answers.Answer, ...]:
    return config_answers.judgement_answered(
        {"judgement": {"answered": list(entries)}}, "systemap.toml"
    )


def refused(item: dict[str, Any]) -> str:
    with pytest.raises(ValueError) as caught:
        read(item)
    return str(caught.value)


def test_a_helper_answer_keeps_its_role_and_symbol() -> None:
    (answer,) = read(entry(item=USE, role="helper", symbol="escape", evidence=DIGEST))
    assert (answer.role, answer.symbol, answer.handoff) == ("helper", "escape", ())


def test_a_helper_answer_without_a_symbol_is_not_a_static_error() -> None:
    (answer,) = read(entry(item=USE, role="helper"))
    assert (answer.role, answer.symbol) == ("helper", "")


def test_a_handoff_answer_can_have_a_symbol() -> None:
    (answer,) = read(entry(item=NESTED_USE, role="handoff", symbol="send"))
    assert (answer.role, answer.symbol, answer.handoff) == ("handoff", "send", ())


def test_a_mixed_answer_keeps_the_handoff_names() -> None:
    (answer,) = read(entry(item=USE, role="mixed", handoff=["Serializer", "Deserializer"]))
    assert (answer.role, answer.symbol) == ("mixed", "")
    assert answer.handoff == ("Serializer", "Deserializer")


def test_an_answer_without_the_keys_has_empty_values() -> None:
    (answer,) = read(entry(item=OTHER, evidence=DIGEST))
    assert answer == config_answers.Answer(
        items=(OTHER,), reason=entry()["reason"], evidence=DIGEST
    )


@pytest.mark.parametrize(
    "selector",
    [
        {"items": [USE]},
        {"kind": "crossing import", "policy": True},
        {"crossing": ["A", "B"], "policy": True},
    ],
)
@pytest.mark.parametrize("key", [{"role": "helper"}, {"symbol": "x"}, {"handoff": ["x"]}])
def test_the_keys_are_permitted_only_with_item(
    selector: dict[str, Any], key: dict[str, Any]
) -> None:
    assert refused(entry(**selector, **key)) == (
        f"{WHERE} role, symbol, and handoff are permitted only with item."
    )


@pytest.mark.parametrize("item", [USE, NESTED_USE])
def test_a_module_use_item_must_have_a_role(item: str) -> None:
    assert refused(entry(item=item, symbol="escape")) == (
        f'{WHERE} ({item}) must contain role: "helper", "handoff", or "mixed".'
    )


@pytest.mark.parametrize("key", [{"role": "helper"}, {"symbol": "x"}, {"handoff": ["x"]}])
def test_the_keys_are_refused_on_an_item_of_a_different_kind(key: dict[str, Any]) -> None:
    assert refused(entry(item=OTHER, **key)) == (
        f"{WHERE} role is permitted only for a module use line."
    )


@pytest.mark.parametrize("role", ["Helper", "", 1, ["helper"]])
def test_a_bad_role_value_is_refused(role: Any) -> None:
    assert refused(entry(item=USE, role=role)) == (
        f'{WHERE} role must be "helper", "handoff", or "mixed".'
    )


@pytest.mark.parametrize("symbol", ["", "two names", ["escape"], 3])
def test_a_symbol_must_be_one_name(symbol: Any) -> None:
    assert refused(entry(item=USE, role="helper", symbol=symbol)) == (
        f"{WHERE} symbol must be one name without spaces."
    )


@pytest.mark.parametrize("role", ["helper", "handoff"])
def test_handoff_is_permitted_only_with_mixed(role: str) -> None:
    assert refused(entry(item=USE, role=role, handoff=["send"])) == (
        f'{WHERE} handoff is permitted only with role "mixed".'
    )


@pytest.mark.parametrize("handoff", [None, [], "Serializer", ["two names"], [""], [1]])
def test_mixed_must_have_a_list_of_names(handoff: Any) -> None:
    keys = {} if handoff is None else {"handoff": handoff}
    assert refused(entry(item=USE, role="mixed", **keys)) == (
        f'{WHERE} role "mixed" must have handoff: a list of one or more names of the module.'
    )


def test_mixed_with_a_symbol_is_refused() -> None:
    assert refused(entry(item=USE, role="mixed", handoff=["send"], symbol="send")) == (
        f'{WHERE} symbol is not permitted with role "mixed". Put the names in handoff.'
    )


def test_the_configuration_reader_gives_a_config_error(tmp_path: Path) -> None:
    (tmp_path / "systemap.toml").write_text(
        f'[judgement]\nanswered = [{{ item = "{OTHER}", role = "helper", reason = "r" }}]\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigError) as caught:
        config.load(tmp_path)
    assert str(caught.value).endswith(
        "judgement.answered[1] role is permitted only for a module use line."
    )
    assert config.Answer is config_answers.Answer
    assert config.LINE_KINDS is config_answers.LINE_KINDS
