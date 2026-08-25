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
    thin layer ......... a flow layer (data, control, the agent kinds, or
                         the model's own) that lights fewer than two
                         components: it may not be a reading of the map at
                         all, or a standard kind was never used
    entry point ........ an entry point in the facts (a console script, a
                         subcommand, a main, a public function of the
                         package root) that no journey mentions: a walk
                         the reader may need and the map does not have
    crossing import .... a module of one component imports a module of
                         another and no flow joins the two components, in
                         either direction: an edge the code has and the
                         map does not. The main tool of the second pass.
    ignored ............ a module the coverage rule leaves unmapped, with
                         the reason the configuration gives
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from systemap.config import Ignore
from systemap.extract import entry_label
from systemap.model import Component, Meaning, Model, claimed, flow_layers, module_matches

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
    layers = flow_layers(model, meaning)
    on_layer: dict[str, set[str]] = {layer.id: set() for layer in layers}
    for f in model.flows:
        try:
            layer_id = meaning.layer_for(f.edge, f.kind)
        except KeyError:
            continue
        on_layer.setdefault(layer_id, set()).update((f.src, f.dst))
    out: list[str] = []
    for layer in layers:
        n = len(on_layer.get(layer.id, set()))
        if n < 2:
            noun = "component" if n == 1 else "components"
            out.append(f"thin layer: {layer.id} lights {n} {noun}")
    return out


def _owner_of(model: Model, facts: dict[str, Any]) -> dict[str, str]:
    """module -> the id of the component that claims it, for every claimed module."""
    components = facts.get("components", {})
    out: dict[str, str] = {}
    for c in model.components:
        for module in claimed(c, components):
            out.setdefault(module, c.id)
    return out


def _journey_text(meaning: Meaning) -> str:
    """Every word the journeys say: ids, labels and step sentences, in one string."""
    parts: list[str] = []
    for j in meaning.journeys:
        parts.extend([j.id, j.label])
        parts.extend(step.say for step in j.steps)
    return "\n".join(parts).lower()


def mentioned(name: str, text: str) -> bool:
    """Is `name` in `text` as a whole word, case blind?"""
    return re.search(rf"(?<![\w-]){re.escape(name.lower())}(?![\w-])", text.lower()) is not None


def entry_points_without_journey(
    model: Model, meaning: Meaning, facts: dict[str, Any]
) -> list[str]:
    """Every entry point in the facts that no journey mentions.

    An entry point is covered when a journey's id, label or a step
    sentence names it as a whole word: the console script by its name,
    a subcommand by its word, a function by its name. A `main` function
    a console script targets, and a `__main__` module that imports a
    console script's module, are that script under another name and
    are not asked about twice.
    """
    points: list[dict[str, str]] = facts.get("entry_points", [])
    text = _journey_text(meaning)
    scripts = {p["module"]: p for p in points if p["kind"] == "console_script"}
    components = facts.get("components", {})
    owner = _owner_of(model, facts)
    out: list[str] = []
    for p in points:
        module = p["module"]
        if p["kind"] == "main_function" and scripts.get(module, {}).get("target") == "main":
            continue
        if p["kind"] == "main_module":
            imported = set(components.get(module, {}).get("uses", {}))
            if any(m in scripts for m in imported):
                continue
        if mentioned(p["name"], text):
            continue
        who = owner.get(module)
        where = f" (component {who})" if who else ""
        out.append(f"entry point {entry_label(p)} has no journey{where}")
    return out


def crossing_imports_without_flow(model: Model, facts: dict[str, Any]) -> list[str]:
    """Every import across a component boundary with no flow between the two.

    The facts record what each module imports. When a module of P imports
    a module of Q and the model has no flow P -> Q or Q -> P, the code has
    an edge the map does not. It may be one the reader needs, or one the
    map leaves out on purpose; either way it is looked at, not guessed.
    """
    components = facts.get("components", {})
    owner = _owner_of(model, facts)
    joined = {frozenset(f.edge) for f in model.flows}
    out: list[str] = []
    for module in sorted(components):
        p = owner.get(module)
        if not p:
            continue
        for target in sorted(components[module].get("uses", {})):
            q = owner.get(target)
            if not q or q == p or frozenset((p, q)) in joined:
                continue
            out.append(
                f"crossing import: module {module} (component {p}) imports module {target} "
                f"(component {q}) and no flow joins {p} and {q}"
            )
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
        + entry_points_without_journey(model, meaning, facts)
        + crossing_imports_without_flow(model, facts)
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
