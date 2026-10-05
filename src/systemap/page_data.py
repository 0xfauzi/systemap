"""Source records and map findings from the stored snapshot."""

from __future__ import annotations

import re
from typing import Any

from systemap import explain, extract, judgement, nest, ways_in
from systemap import facts as facts_mod
from systemap.config import Config
from systemap.model import (
    Component,
    Meaning,
    Model,
    claimed,
    module_matches,
    public_names,
    symbol_claims,
)


def review(
    cfg: Config, model: Model, meaning: Meaning, facts: dict[str, Any], prefix: str = ""
) -> dict[str, Any]:
    """Program findings cannot support a model file that the program did not load."""
    lines = judgement.run(
        model, meaning, facts, judgement.sdk_list(cfg.model_sdks), cfg.observed_by
    )
    return review_lines(cfg, [prefix + line for line in lines], model, {})


def tree_review(cfg: Config, tree: nest.Tree, m: nest.Map, facts: dict[str, Any]) -> dict[str, Any]:
    """Use the CLI map tree checks, with child sequences that cover parent entry points."""
    lines = judgement.run_tree(tree, facts, judgement.sdk_list(cfg.model_sdks), cfg.observed_by)
    local = [line for line in lines if line.startswith(m.prefix)]
    if m.top:
        local = [line for line in local if line == judgement.unprefixed(line)]
    try:
        current = judgement.evidence_for_tree(tree, facts, cfg.root, lines)
    except OSError:
        current = {}
    return review_lines(cfg, local, m.model, current, lines)


def review_lines(
    cfg: Config,
    lines: list[str],
    model: Model,
    current: dict[str, str],
    all_lines: list[str] | None = None,
) -> dict[str, Any]:
    """Keep exact findings and use the CLI rules for answers and their evidence."""
    whole = lines if all_lines is None else all_lines
    given = [a for a in cfg.judgement_answered if not a.kind or a.kind in judgement.KIND_PREFIX]
    result = judgement.apply_answers(whole, given, current)
    accepted = [a for a in given if judgement.apply_answers(whole, (a,), current).answered]
    out: dict[str, Any] = {
        "open": [],
        "answered": [],
        "pending": result.pending,
        "policies": result.policies,
    }
    for exact in lines:
        reasons = [a.reason for a in accepted if judgement.answers(a, exact)]
        kind = judgement.kind_of(exact)
        lesson = explain.JUDGEMENT[kind]
        record = {
            "line": exact,
            "parts": [
                c.id
                for c in model.components
                if re.search(r"(?<![\w.-])" + re.escape(c.id) + r"(?![\w.-])", exact)
            ],
            "kind": kind,
            "means": lesson.means,
            "why": lesson.why,
            "do": lesson.do,
            "reasons": reasons,
        }
        out["answered" if reasons else "open"].append(record)
    return out


def _module_record(mid: str, record: dict[str, Any]) -> dict[str, Any]:
    names = record.get("names")
    if names is None:
        names = [{"name": name, "kind": kind} for name, kind in facts_mod.kinds(record)]
    return {
        "id": mid,
        "file": record.get("file", ""),
        "docstring": record.get("docstring", ""),
        "names": [n["name"] for n in names],
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
        and not any(module_matches(claim, module) for module in resolved)
    ]


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
            "points": [ways_in.label(p) for p in points if p.get("module") in owned],
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
        "unknown": extract.unknown_fact_lines(facts),
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
