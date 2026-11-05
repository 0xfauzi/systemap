"""`judgement_evidence.names` finds the same names as the earlier pattern for each name.

The earlier procedure made one regular expression for each name and each line. The new
procedure finds names in the words of the line. Random texts and names compare the two,
with dots, hyphens, colons, slashes, non-ASCII letters and sentence ends.
"""

from __future__ import annotations

import random
import re

import pytest

from systemap import judgement_evidence


def old_names(name: str, text: str) -> bool:
    return re.search(rf"(?<![\w.-]){re.escape(name)}(?![\w-]|\.\w)", text) is not None


PARTS = ["pkg", "a", "b", "user", "user-service", "é", "x1", "_p", "Gateway", "Routes"]
GLUE = [".", " ", "-", ":", "/", ". ", "..", ", ", "(", ")", "->", " imports ", ".-"]


def _text(rng: random.Random) -> str:
    return "".join(rng.choice(PARTS) + rng.choice(GLUE) for _ in range(rng.randint(0, 9)))


def _name(rng: random.Random) -> str:
    joined = rng.choice([".", "-", "/", ":"]).join(
        rng.choice(PARTS) for _ in range(rng.randint(1, 3))
    )
    return joined if rng.random() < 0.9 else "." + joined


@pytest.mark.parametrize("seed", range(500))
def test_names_agrees_with_the_earlier_pattern(seed: int) -> None:
    rng = random.Random(seed)
    text = _text(rng)
    for _ in range(12):
        name = _name(rng)
        assert judgement_evidence.names(name, text) == old_names(name, text), (name, text)
    for word in re.findall(r"[\w.-]+", text):  # each name that the text holds
        assert judgement_evidence.names(word, text) == old_names(word, text), (word, text)


def test_the_cases_of_the_docstring() -> None:
    text = "crossing import: pkg.a imports pkg.ab. See pkg.a-b and pkg.a."
    for name, found in [
        ("pkg.a", True),
        ("pkg.ab", True),
        ("pkg", False),
        ("pkg.a-b", True),
        ("a", False),
    ]:
        assert judgement_evidence.names(name, text) is found is old_names(name, text)
