"""The work of the `*` re-export resolver for deep and looped `*` graphs.

Findings g1full-1 and g1full-2: a diamond of `export *` files made the resolver work
for an exponential time, and a long chain of `export *` files stopped it with a
`RecursionError`.

Acceptance values:

- A diamond of depth 12: the resolver examines the bindings of a pair of a module and
  a name not more than four times for each pair. The old resolver examined them for
  each path through the diamond.
- A diamond of depth 40 (80 modules): the resolver completes in less than 10 s, with
  the TypeScript rule and with the Python rule.
- A chain of 3000 `*` re-exports: the resolver completes without a `RecursionError`.
- A loop of `*` re-exports: each module gets the names of the other modules of the
  loop, with their defining modules.
- A two-way loop of 100 modules: the resolver examines the records of a module not
  more than 2 * 100 * 100 times in total. The resolver of commit cd5fb1d calculated
  the loop again for each module, with full passes until no set changed.
- In a loop, a `*` record with `star_export_names` limits the names that go through it,
  and the names have the order of the records.
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from systemap import reexports


def _diamond(depth: int, rebinds: bool) -> dict[str, Any]:
    """Give `depth` layers of two modules. Each module re-exports `*` from the two
    modules of the next layer. Each module of the last layer defines one function."""
    components: dict[str, Any] = {}
    for layer in range(depth):
        for side in range(2):
            names: list[dict[str, Any]]
            if layer == depth - 1:
                names = [{"name": f"x{side}", "kind": "function"}]
            else:
                names = [_star(f"p.l{layer + 1}_{target}", rebinds) for target in range(2)]
            components[f"p.l{layer}_{side}"] = {"package": "p", "names": names}
    return components


def _star(source: str, rebinds: bool) -> dict[str, Any]:
    entry: dict[str, Any] = {"name": "*", "kind": "reexport", "reexport_of": source, "star": True}
    if rebinds:
        entry["rebinds"] = True
    return entry


class _CountingResolver(reexports._Resolver):
    """This resolver counts the calls that examine the bindings of a name."""

    def __init__(self, components: dict[str, Any]) -> None:
        self.calls = 0
        super().__init__(components)

    def _bindings(self, module: str, name: str) -> list[dict[str, Any]]:
        self.calls += 1
        return super()._bindings(module, name)


@pytest.mark.parametrize("rebinds", [False, True])
def test_a_diamond_examines_each_binding_a_fixed_number_of_times(rebinds: bool) -> None:
    components = _diamond(12, rebinds)
    resolver = _CountingResolver(components)
    names = {module: resolver.names(module) for module in components}
    pairs = len(components) * 2
    # The old resolver examined the bindings for each path: 2 to the power of the depth.
    assert resolver.calls <= 4 * pairs
    top = {entry["name"]: entry["defined_in"] for entry in names["p.l0_0"]}
    assert top == {"x0": "p.l11_0", "x1": "p.l11_1"}


@pytest.mark.parametrize("rebinds", [False, True])
def test_a_deep_diamond_resolves_in_a_short_time(rebinds: bool) -> None:
    components = _diamond(40, rebinds)
    began = time.monotonic()
    reexports.resolve_reexports(components)
    # The old resolver used 108 s for depth 20 and approximately 2.4 times more for
    # each layer. The new resolver uses less than 0.1 s for depth 40.
    assert time.monotonic() - began < 10
    top = {entry["name"]: entry["defined_in"] for entry in components["p.l0_0"]["names"]}
    assert top == {"x0": "p.l39_0", "x1": "p.l39_1"}
    assert "unknown" not in components["p.l0_0"]


def test_a_long_star_chain_does_not_stop_the_resolver() -> None:
    count = 3000
    components: dict[str, Any] = {}
    for index in range(count - 1):
        star = {"name": "*", "kind": "reexport", "reexport_of": f"p.m{index + 1}", "star": True}
        components[f"p.m{index}"] = {"package": "p", "names": [star]}
    components[f"p.m{count - 1}"] = {"package": "p", "names": [{"name": "x", "kind": "function"}]}
    # The old resolver stopped with a RecursionError at a chain of 300 modules.
    reexports.resolve_reexports(components)
    assert components["p.m0"]["names"] == [
        {
            "name": "x",
            "kind": "function",
            "reexport_of": "p.m1",
            "defined_in": f"p.m{count - 1}",
            "defined_as": "x",
        }
    ]


def test_a_star_loop_gives_each_module_the_names_of_the_loop() -> None:
    count = 50
    components: dict[str, Any] = {}
    for index in range(count):
        star = {
            "name": "*",
            "kind": "reexport",
            "reexport_of": f"p.m{(index + 1) % count}",
            "star": True,
        }
        names = [{"name": f"x{index}", "kind": "function"}, star]
        components[f"p.m{index}"] = {"package": "p", "names": names}
    reexports.resolve_reexports(components)
    for index in range(count):
        record = components[f"p.m{index}"]
        found = {entry["name"]: entry.get("defined_in") for entry in record["names"]}
        expected = {f"x{other}": f"p.m{other}" for other in range(count) if other != index}
        assert found == {**expected, f"x{index}": None}
        assert "unknown" not in record


def test_a_loop_of_named_reexports_gives_no_definition() -> None:
    components: dict[str, Any] = {
        "p.a": {"package": "p", "names": [{"name": "y", "kind": "reexport", "reexport_of": "p.b"}]},
        "p.b": {"package": "p", "names": [{"name": "y", "kind": "reexport", "reexport_of": "p.a"}]},
    }
    reexports.resolve_reexports(components)
    for module, source in (("p.a", "p.b"), ("p.b", "p.a")):
        assert components[module]["names"] == [
            {
                "name": "y",
                "kind": "unknown",
                "reexport_of": source,
                "defined_in": None,
                "defined_as": None,
            }
        ]


def _ring(count: int, steps: tuple[int, ...]) -> dict[str, Any]:
    """Give a loop of `count` modules. Module `i` defines `x<i>` and re-exports `*` from
    module `i + step` for each step."""
    components: dict[str, Any] = {}
    for index in range(count):
        names: list[dict[str, Any]] = [{"name": f"x{index}", "kind": "function"}]
        for step in steps:
            names.append(_star(f"p.m{(index + step) % count}", False))
        components[f"p.m{index}"] = {"package": "p", "names": names}
    return components


class _VisitingResolver(reexports._Resolver):
    """This resolver counts the calls that examine the records of one module."""

    def __init__(self, components: dict[str, Any]) -> None:
        self.visits = 0
        super().__init__(components)

    def _gather(self, *args: Any) -> Any:
        self.visits += 1
        return super()._gather(*args)

    def _steps(self, *args: Any) -> Any:
        self.visits += 1
        return super()._steps(*args)


def test_a_two_way_star_loop_examines_each_module_a_fixed_number_of_times() -> None:
    count = 100
    resolver = _VisitingResolver(_ring(count, (1, -1)))
    names = {module: resolver.names(module) for module in resolver.raw}
    # The resolver of commit cd5fb1d calculated the loop again for each module, with
    # full passes until no set changed: 752601 calls for 100 modules, and 100.74 s
    # for 200 modules. Each module now examines each module of the loop one time.
    assert resolver.visits <= 2 * count * count
    # Each name comes through two `*` records, so the names other than x0 are ambiguous.
    assert {entry["name"] for entry in names["p.m0"]} == {f"x{index}" for index in range(count)}


def test_the_names_of_a_star_loop_have_the_order_of_the_records() -> None:
    count = 50
    components = _ring(count, (1,))
    reexports.resolve_reexports(components)
    order = [entry["name"] for entry in components["p.m0"]["names"]]
    assert order == [f"x{index}" for index in range(count)]


def test_a_limited_star_record_in_a_loop_limits_the_names_that_go_through_it() -> None:
    limited = {**_star("p.c", False), "star_export_names": ["xc"]}
    components: dict[str, Any] = {
        "p.a": {"package": "p", "names": [_name("xa"), _star("p.b", False)]},
        "p.b": {"package": "p", "names": [_name("xb"), limited]},
        "p.c": {"package": "p", "names": [_name("xc"), _name("xd"), _star("p.a", False)]},
    }
    reexports.resolve_reexports(components)

    def summary(module: str) -> list[tuple[str, Any, Any]]:
        names = components[module]["names"]
        return [(e["name"], e.get("defined_in"), e.get("star_export", True)) for e in names]

    assert summary("p.a") == [("xa", None, True), ("xb", "p.b", True), ("xc", "p.c", True)]
    assert summary("p.b") == [
        ("xb", None, True),
        ("xc", "p.c", True),
        ("xd", "p.c", False),
        ("xa", "p.a", False),
    ]
    assert summary("p.c") == [
        ("xc", None, True),
        ("xd", None, True),
        ("xa", "p.a", True),
        ("xb", "p.b", True),
    ]


def _name(name: str) -> dict[str, Any]:
    return {"name": name, "kind": "function"}
