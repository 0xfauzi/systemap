"""The list a maintainer must confirm before the map is trusted.

The facts are mechanical and the check is mechanical, but the model is
judgement: where one component ends and the next begins, what an edge
means, which question a layer answers. A person reviews that judgement.
This module makes the review list mechanical to produce, so the agent
that drafted the model cannot skip it and the maintainer does not have to
hunt for the calls that could have gone another way.

It is a report, never a gate: the CLI always exits 0. Each line names one
thing to look at:

    single module ...... a component that claims exactly one module: it
                         may be a real part, or an over-split
    possible mis-fold .. a module whose name shares no word with the
                         component that claims it: it may be folded into
                         the wrong part
    no sentence ........ a flow with no relation sentence, or a blank one
    thin layer ......... a layer that lights fewer than two components:
                         it may not be a reading of the map at all
    ignored ............ a module the coverage rule leaves unmapped, with
                         the reason the configuration gives
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from systemap.config import Ignore
from systemap.model import Component, Meaning, Model, claimed, module_matches

MIN_STEM = 4


def words(name: str) -> set[str]:
    """The lower-case words in a CamelCase or snake_case name."""
    parts = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z]+", name)
    return {p.lower() for p in parts if p}


def shares_a_word(a: str, b: str) -> bool:
    """Do two names share a word?

    Deliberately simple: two words count as shared when they are equal,
    or when one is a prefix of the other and the shorter is at least four
    letters ("extract" and "extractor", "route" and "router"). It will
    miss synonyms ("Ledger" and "store") and it will accept a coincidence;
    the line it produces is a thing to look at, not a verdict.
    """
    for x in words(a):
        for y in words(b):
            if x == y:
                return True
            short, long = (x, y) if len(x) <= len(y) else (y, x)
            if len(short) >= MIN_STEM and long.startswith(short):
                return True
    return False


def _modules_of(component: Component, facts: dict[str, Any]) -> list[str]:
    """The modules a component claims: from the facts when there are any."""
    if facts.get("components"):
        return claimed(component, facts["components"])
    return [m for m in component.implemented_by if not m.endswith(".*")]


def single_module(model: Model, facts: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for c in model.components:
        if c.kind == "actor":
            continue
        modules = _modules_of(c, facts)
        if len(modules) == 1:
            out.append(f"single module: {c.id} is only {modules[0]}")
    return out


def mis_folds(model: Model, facts: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for c in model.components:
        for module in _modules_of(c, facts):
            leaf = module.rsplit(".", 1)[-1]
            if not shares_a_word(c.id, leaf):
                out.append(f"possible mis-fold: {c.id} claims {module} (no shared word)")
    return out


def no_sentence(model: Model, meaning: Meaning) -> list[str]:
    return [
        f"no sentence: {f.src} -> {f.dst} ('{f.artifact}')"
        for f in model.flows
        if not (meaning.relations.get(f.edge) or "").strip()
    ]


def thin_layers(model: Model, meaning: Meaning) -> list[str]:
    on_layer: dict[str, set[str]] = {layer.id: set() for layer in meaning.layers}
    for f in model.flows:
        try:
            layer_id = meaning.layer_for(f.edge, f.kind)
        except KeyError:
            continue
        on_layer.setdefault(layer_id, set()).update((f.src, f.dst))
    out: list[str] = []
    for layer in meaning.layers:
        n = len(on_layer.get(layer.id, set()))
        if n < 2:
            noun = "component" if n == 1 else "components"
            out.append(f"thin layer: {layer.id} lights {n} {noun}")
    return out


def ignored(facts: dict[str, Any], ignores: Iterable[Ignore]) -> list[str]:
    modules = sorted(facts.get("components", {}))
    out: list[str] = []
    for ignore in ignores:
        hit = [m for m in modules if module_matches(ignore.module, m)] or [ignore.module]
        for m in hit:
            out.append(f"ignored: {m} ({ignore.reason})")
    return out


def run(
    model: Model, meaning: Meaning, facts: dict[str, Any], ignores: Iterable[Ignore] = ()
) -> list[str]:
    """Every line the maintainer should read, in the order above."""
    return (
        single_module(model, facts)
        + mis_folds(model, facts)
        + no_sentence(model, meaning)
        + thin_layers(model, meaning)
        + ignored(facts, ignores)
    )


def report(lines: list[str]) -> list[str]:
    """The lines the CLI prints."""
    if not lines:
        return ["judgement: nothing to confirm"]
    noun = "item" if len(lines) == 1 else "items"
    return [f"judgement: {len(lines)} {noun} for the maintainer to confirm"] + [
        f"  {line}" for line in lines
    ]
