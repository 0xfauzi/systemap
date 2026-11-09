"""The claim index gives the same modules as the comparison of each pattern with each module.

`model.claimed` used `model.covers` for each pattern and each module. The index must give
the same modules in the same order, for module names only and for module records with
and without the `package` fact (a dot in a file name is not a package).
"""

from __future__ import annotations

import random
from collections.abc import Iterator

import pytest

from systemap import claim_index, model


def old_claimed(patterns: tuple[str, ...], modules: object) -> list[str]:
    """The procedure before the index, kept here as the reference."""
    return [m for m in modules if any(model.covers(p, m, modules) for p in patterns)]  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def fresh() -> Iterator[None]:
    claim_index.clear()
    yield
    claim_index.clear()


def _modules(rng: random.Random) -> dict[str, dict[str, object]]:
    parts = ["a", "b", "ab", "c", "user", "user.service", "x"]
    out: dict[str, dict[str, object]] = {}
    for _ in range(rng.randint(0, 40)):
        name = ".".join(rng.choice(parts) for _ in range(rng.randint(1, 4)))
        roll = rng.random()
        if roll < 0.3:
            out[name] = {}  # no package fact: the dotted name gives the package
        elif roll < 0.6:
            out[name] = {"package": name.rpartition(".")[0]}
        elif roll < 0.8:
            out[name] = {"package": rng.choice(["a", "a.b", "user", "", "ab"])}
        else:
            out[name] = {"package": 7}  # an older record: not a string
    return out


def _patterns(rng: random.Random, modules: list[str]) -> tuple[str, ...]:
    heads = ["a", "a.b", "ab", "user", "user.service", "c.x", "zz", ""] + modules[:5]
    out = []
    for _ in range(rng.randint(0, 5)):
        head = rng.choice(heads)
        kind = rng.random()
        out.append(head + ".*" if kind < 0.5 else head + ":name" if kind < 0.6 else head)
    return tuple(out)


@pytest.mark.parametrize("seed", range(400))
def test_the_index_gives_the_old_result(seed: int) -> None:
    rng = random.Random(seed)
    records = _modules(rng)
    patterns = _patterns(rng, list(records))
    assert claim_index.claimed(patterns, records) == old_claimed(patterns, records)
    names = list(records)
    assert claim_index.claimed(patterns, names) == old_claimed(patterns, names)
    assert claim_index.claimed(patterns, iter(names)) == old_claimed(patterns, list(names))


def test_a_name_that_occurs_two_times_is_given_two_times() -> None:
    names = ["a.x", "b", "a.x"]
    for patterns in (("a.*",), ("a.x",), ("b", "a.x")):
        assert claim_index.claimed(patterns, names) == old_claimed(patterns, names)


def test_model_claimed_uses_the_index() -> None:
    records = {"pkg.a": {"package": "pkg"}, "pkg.a.b": {"package": "pkg.a"}, "other": {}}
    comp = model.Component(id="C", does="x", implemented_by=("pkg.*",))
    assert model.claimed(comp, records) == ["pkg.a", "pkg.a.b"]
    assert len(claim_index.kept()) == 1


def test_a_different_collection_gets_its_own_index() -> None:
    first = {"a.x": {}}
    second = {"a.x": {}, "a.y": {}}
    assert claim_index.claimed(("a.*",), first) == ["a.x"]
    assert claim_index.claimed(("a.*",), second) == ["a.x", "a.y"]
    first["a.z"] = {}  # a new module changes the size, so the index is made again
    assert claim_index.claimed(("a.*",), first) == ["a.x", "a.z"]


def test_at_most_limit_indexes_are_kept() -> None:
    for i in range(claim_index.LIMIT + 3):
        claim_index.claimed(("m.*",), [f"m.{i}"])
    assert len(claim_index.kept()) <= claim_index.LIMIT


def test_a_used_index_is_kept_when_other_collections_come() -> None:
    """The index used last stays, so a collection in use all the time is not built again."""
    main = ["m.0", "m.1"]
    claim_index.claimed(("m.*",), main)
    for i in range(claim_index.LIMIT * 2):
        claim_index.claimed(("m.*",), [f"m.{i}"])
        claim_index.claimed(("m.*",), main)  # in use again: it goes to the end
    assert any(source is main for source, *_ in claim_index._kept)
