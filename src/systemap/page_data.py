"""Source records and the revision comparison from the stored snapshot."""

from __future__ import annotations

from typing import Any

from systemap import facts as facts_mod
from systemap import source_facts
from systemap.config import Config
from systemap.model import (
    Component,
    Model,
    claimed,
    covers,
    public_names,
    symbol_claims,
)


def _module_record(mid: str, record: dict[str, Any]) -> dict[str, Any]:
    names = record.get("names")
    if names is None:
        names = [{"name": name, "kind": kind} for name, kind in facts_mod.kinds(record)]
    return {
        "id": mid,
        "file": record.get("file", ""),
        "docstring": record.get("docstring", ""),
        "public_names": names,
        "imports": record.get("imports", []),
        "imported_by": record.get("imported_by", []),
        "external": record.get("external", []),
        "unknown": record.get("unknown", []),
        "tests": record.get("tests", []),
    }


def _unresolved_claims(component: Component, modules: dict[str, Any]) -> list[str]:
    resolved = set(claimed(component, modules))
    symbols = {
        f"{module}:{name}"
        for module, name in symbol_claims(component)
        if module in modules and name in public_names(modules[module])
    }
    return [
        claim
        for claim in component.implemented_by
        if "/" not in claim
        and claim not in symbols
        and not any(covers(claim, module, modules) for module in resolved)
    ]


def _owns(point: dict[str, Any], owned: list[str], symbols: list[tuple[str, str]]) -> bool:
    """True when a module claim includes the module of the entry point, or a symbol claim
    names its module and the name that it starts. An entry point that starts no single
    name (see `source_facts.entry_symbol`) has no symbol claim."""
    module, symbol = point.get("module"), source_facts.entry_symbol(point)
    return module in owned or (bool(symbol) and (module, symbol) in symbols)


def sources(model: Model, facts: dict[str, Any]) -> dict[str, Any]:
    """Give source records. Imports do not show the direction or artifact of a flow."""
    modules = facts.get("components", {})
    points = facts.get("entry_points", [])
    out = {}
    for c in model.components:
        owned = claimed(c, modules)
        symbols = symbol_claims(c)
        related = list(dict.fromkeys([*owned, *(m for m, _n in symbols if m in modules)]))
        out[c.id] = {
            "modules": [_module_record(mid, modules[mid]) for mid in related],
            "claims": list(c.implemented_by),
            "points": [source_facts.entry_label(p) for p in points if _owns(p, owned, symbols)],
            "symbol_claims": [{"module": module, "name": name} for module, name in symbols],
            "unresolved_claims": _unresolved_claims(c, modules),
        }
    return out


def provenance(cfg: Config, facts: dict[str, Any], model_file: str = "") -> dict[str, Any]:
    """Name stored sources. Extraction at HEAD does not imply a clean working tree."""
    return {
        "facts_file": f"{cfg.out_dir}/{cfg.facts_file}",
        "model_file": model_file or cfg.model,
        "revision": facts.get("built_at_commit", ""),
        "extraction": "working tree",
        "uncommitted": "not recorded",
        "unknown": source_facts.unknown_fact_lines(facts),
    }


def comparison(ch: dict[str, Any]) -> dict[str, Any]:
    """Give the revision comparison. Imports do not prove effects on program execution."""
    if not ch.get("has_change") and not ch.get("comparison_requested"):
        return {}
    return {
        "base": ch["base"],
        "head": ch["head"],
        "base_revision": ch.get("base_revision", ""),
        "head_revision": ch.get("head_revision", ""),
        "comparison_base": ch.get("comparison_base", ""),
        "direct": sorted(ch["direct"]),
        "adjacent": sorted(ch["adjacent"]),
        "parts": ch["per_component"],
        "reach_known": ch.get("reach_known", False),
        "unparsed": ch.get("unparsed", []),
    }
