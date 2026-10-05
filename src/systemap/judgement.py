"""The judgement report gives possible map errors for maintainer decisions.

The report includes component grouping, flow descriptions, layer contents, entry
coverage, imports, and source evidence. Each line has a stable kind prefix. The
configuration can answer an exact line or a family of lines. Exact answers must have an
evidence digest. Family answers must have an explicit policy. The report shows unmatched
answers as stale.

Each nested diagnostic has its map ID as a prefix. Exact answers include this prefix.
family selectors use the diagnostic after the prefix. Entry point and SDK questions
belong to the deepest applicable map. Sequences from all maps supply entry coverage. The
CLI exits 1 with --strict if a line remains open. otherwise, the report exits 0.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from systemap import evidence, explain, judgement_evidence, nest
from systemap.config import LINE_KINDS, Answer, ConfigError
from systemap.evidence import mentioned, owners
from systemap.extract import unknown_fact_lines
from systemap.journey_coverage import (
    TOGETHER_AT as TOGETHER_AT,
)
from systemap.journey_coverage import (
    _entry_lines,
    journey_problems,
    reviewed_entries,
    ways_in_without_journey,
)
from systemap.journey_coverage import (
    crowd_label as crowd_label,
)
from systemap.model import Component, Meaning, Model, claimed, flow_layers, is_symbol

__all__ = ["mentioned"]

MIN_STEM = 4
# Import names that mark a module as calling a model or running an agent
# framework. Dotted where the namespace is shared. A cloud SDK that also
# reaches a model (boto3) is too coarse to list. Each matches as a prefix
# of the import written, so a framework fires for its non-model parts too;
# `[facts] model_sdks` removes one with a leading `-`.
MODEL_SDKS: tuple[str, ...] = (
    "anthropic",
    "openai",
    "google.generativeai",
    "google.adk",
    "litellm",
    "langchain",
    "langgraph",
    "llama_index",
    "mistralai",
    "cohere",
    "typesafe_sdk",
    "vertexai",
)


def words(name: str) -> set[str]:
    """This function separates lower-case words from a CamelCase or snake_case name."""
    parts = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z]+", name)
    return {p.lower() for p in parts if p}


def shares_a_word(a: str, b: str) -> bool:
    """This function compares names for equal words or equal prefixes of at least four
    letters.

    It does not identify synonyms. A same word can be a coincidence, so the result must
    have a source review.
    """
    return share_a_word(words(a), words(b))


def share_a_word(xs: set[str], ys: set[str]) -> bool:
    """This function compares two word sets with shares_a_word."""
    for x in xs:
        for y in ys:
            if x == y:
                return True
            short, long = (x, y) if len(x) <= len(y) else (y, x)
            if len(short) >= MIN_STEM and long.startswith(short):
                return True
    return False


def _modules_of(component: Component, facts: dict[str, Any]) -> list[str]:
    """This function gives component module claims, from the facts if facts are available."""
    if facts.get("components"):
        return claimed(component, facts["components"])
    return [m for m in component.implemented_by if not m.endswith(".*") and not is_symbol(m)]


def single_module(model: Model, facts: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for c in model.components:
        if c.kind == "actor":
            continue
        modules = _modules_of(c, facts)
        if len(modules) == 1:
            out.append(f"single module: {c.id} contains only {modules[0]}")
    return out


def package_of(module: str) -> str:
    """This function gives the parent package, or the module itself if it has no parent."""
    head, _, _ = module.rpartition(".")
    return head or module


def share_a_package(a: str, b: str) -> bool:
    """This function finds whether two modules have the same package or one is the package
    of the other.
    """
    return package_of(a) == package_of(b) or a == package_of(b) or b == package_of(a)


def mis_folds(model: Model, meaning: Meaning, facts: dict[str, Any]) -> list[str]:
    """This function finds modules with possible component grouping errors.

    The module name has no same word with the component ID, description, plain name, or
    interface. The component has multiple modules, and no other component module has a
    same package with the selected module.
    """
    out: list[str] = []
    for c in model.components:
        modules = _modules_of(c, facts)
        if len(modules) < 2:
            continue
        own = words(c.id) | words(c.does) | words(meaning.plain.get(c.id, "")) | words(c.interface)
        for module in modules:
            if share_a_word(words(module), own):
                continue
            if any(share_a_package(module, m) for m in modules if m != module):
                continue
            out.append(
                f"possible mis-fold: {c.id} has the module claim {module} (no same word with "
                f"the component, and no other component module in {package_of(module)})"
            )
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
            out.append(f"thin layer: {layer.id} shows {n} {noun}")
    return out


# module -> the id of the component that claims it; the one definition is
# the evidence module's, which the declared-flow line reads too.
_owner_of = owners


def entry_points_without_journey(
    model: Model,
    meaning: Meaning,
    facts: dict[str, Any],
    *,
    text: str | None = None,
    covered: Collection[str] | None = None,
    skip: Collection[str] = (),
) -> list[str]:
    """This function groups entry points without sequence coverage by kind and component."""
    owner = _owner_of(model, facts)
    return _entry_lines(ways_in_without_journey(meaning, facts, text, skip, owner, covered), owner)


Pair = tuple[str, str]


def crossing_pairs(
    components: dict[str, Any], owner: dict[str, str]
) -> dict[Pair, list[tuple[str, str]]]:
    """This function indexes module imports across distinct component pairs.

    It uses source facts and an owner table so the delta can use the same rule at
    another commit.
    """
    out: dict[Pair, list[tuple[str, str]]] = {}
    for module in sorted(components):
        p = owner.get(module)
        if not p:
            continue
        for target in sorted(components[module].get("uses", {})):
            q = owner.get(target)
            if q and q != p:
                out.setdefault((p, q), []).append((module, target))
    return out


def crossing_line(p: str, q: str, imports: list[tuple[str, str]]) -> str:
    """This function gives one diagnostic for a component pair and its importing-module
    count.
    """
    n = len({module for module, _target in imports})
    return (
        f"crossing import: {p} imports {q} in {n} module{('s' if n != 1 else '')} and "
        f"no flow connects them"
    )


def crossing_imports(model: Model, facts: dict[str, Any]) -> dict[Pair, list[tuple[str, str]]]:
    """This function gives component pairs with an import connection and no flow
    connection.
    """
    components = facts.get("components", {})
    joined = {frozenset(f.edge) for f in model.flows}
    return {
        pair: imports
        for pair, imports in crossing_pairs(components, _owner_of(model, facts)).items()
        if frozenset(pair) not in joined
    }


def crossing_imports_without_flow(model: Model, facts: dict[str, Any]) -> list[str]:
    """This function gives one diagnostic for each ordered component pair with imports but
    no flow.

    The count includes modules of the source component that import the destination
    component. The verbose detail lists these imports.
    """
    return [
        crossing_line(p, q, imports) for (p, q), imports in crossing_imports(model, facts).items()
    ]


def crossing_detail(model: Model, facts: dict[str, Any], prefix: str = "") -> dict[str, list[str]]:
    """This function indexes imports by their full printed crossing-import diagnostic."""
    return {
        prefix + crossing_line(p, q, imports): [f"{m} imports {t}" for m, t in imports]
        for (p, q), imports in crossing_imports(model, facts).items()
    }


def crossing_detail_tree(tree: nest.Tree, facts: dict[str, Any]) -> dict[str, list[str]]:
    """This function gives crossing-import detail for all maps with their diagnostic
    prefixes.
    """
    out: dict[str, list[str]] = {}
    for m in tree.maps:
        out.update(crossing_detail(m.model, facts, m.prefix))
    return out


def declared_flows(
    model: Model,
    meaning: Meaning,
    facts: dict[str, Any],
    observed_by: Iterable[str] = (),
) -> list[str]:
    """This function gives flows without source reviews or structural evidence.

    An import in either direction or a configured mechanism can supply structural
    evidence. Without facts, the report lists no flow evidence questions.
    """
    if not facts.get("components"):
        return []
    return [
        (
            f"declared flow: {f.src} -> {f.dst} ({f.artifact}): no import connects them. "
            f"Find the evidence, give the mechanism in the description, or remove the flow."
        )
        for f in evidence.declared(model, meaning, facts, observed_by)
    ]


def sdk_of(name: str, sdks: Iterable[str]) -> str:
    """This function finds the configured SDK for an import name, or gives an empty string."""
    for sdk in sdks:
        if name == sdk or name.startswith(sdk + "."):
            return sdk
    return ""


def model_sdk_imports(
    model: Model,
    facts: dict[str, Any],
    sdks: Iterable[str] = MODEL_SDKS,
    *,
    skip: Collection[str] = (),
) -> list[str]:
    """This function finds model SDK imports in components without model-call markers.

    The component kind agent or calls_model marker lets the component import the SDK.
    The skip list assigns module questions to nested maps.
    """
    components = facts.get("components", {})
    owner = _owner_of(model, facts)
    runs_a_model = {c.id for c in model.components if c.model_end}
    sdk_list = list(sdks)
    out: list[str] = []
    for module in sorted(components):
        p = owner.get(module)
        if not p or p in runs_a_model or module in skip:
            continue
        hit = sorted({sdk_of(n, sdk_list) for n in components[module].get("external", [])} - {""})
        for sdk in hit:
            out.append(
                f"model sdk: module {module} imports {sdk} and its component {p} is not an agent"
            )
    return out


def sdk_list(configured: Iterable[str]) -> tuple[str, ...]:
    """This function updates the built-in SDK list from configuration.

    A name adds an SDK. A name with a leading hyphen removes an SDK. An attempt to
    remove a missing name gives a configuration error.
    """
    out = list(MODEL_SDKS)
    for entry in configured:
        if entry.startswith("-"):
            name = entry[1:]
            if name not in out:
                raise ConfigError(
                    f"[facts] model_sdks removes {name}, which is not on the list "
                    f"({', '.join(out)})"
                )
            out.remove(name)
        elif entry not in out:
            out.append(entry)
    return tuple(out)


def run(
    model: Model,
    meaning: Meaning,
    facts: dict[str, Any],
    sdks: Iterable[str] = MODEL_SDKS,
    observed_by: Iterable[str] = (),
    *,
    journeys_text: str | None = None,
    covered: Collection[str] | None = None,
    skip: Collection[str] = (),
) -> list[str]:
    """This function gives the judgement diagnostics for one map.

    The journeys_text and skip arguments supply nested-map sequence data and excluded
    modules.
    """
    return (
        single_module(model, facts)
        + mis_folds(model, meaning, facts)
        + no_sentence(model, meaning)
        + thin_layers(model, meaning)
        + entry_points_without_journey(
            model, meaning, facts, text=journeys_text, covered=covered, skip=skip
        )
        + journey_problems(meaning, facts, [c.id for c in model.components])
        + crossing_imports_without_flow(model, facts)
        + declared_flows(model, meaning, facts, observed_by)
        + flow_review(model, meaning, facts, observed_by)
        + model_sdk_imports(model, facts, sdks, skip=skip)
        + unknown_fact_lines(facts)
    )


def flow_review(
    model: Model,
    meaning: Meaning,
    facts: dict[str, Any],
    observed_by: Iterable[str] = (),
) -> list[str]:
    """This function finds flows whose direction or artifact must have a source review."""
    states = evidence.of_model(model, meaning, facts, observed_by)
    return [
        (
            f"flow review: {flow.src} -> {flow.dst} ({flow.artifact}) has structural "
            f"evidence but no source review. Give source references for direction and "
            f"artifact, or change the flow."
        )
        for flow in model.flows
        if states[flow.edge].state == evidence.STRUCTURAL or states[flow.edge].unresolved_refs
    ]


def run_tree(
    tree: nest.Tree,
    facts: dict[str, Any],
    sdks: Iterable[str] = MODEL_SDKS,
    observed_by: Iterable[str] = (),
) -> list[str]:
    """This function gives judgement diagnostics for all maps with map prefixes.

    Module-specific questions belong to the deepest applicable map. Sequences from all
    maps supply entry point coverage.
    """
    covered = reviewed_entries(m.meaning for m in tree.maps)
    components = facts.get("components", {})
    out: list[str] = []
    for m in tree.maps:
        skip = {mod for c in m.model.opening for mod in claimed(c, components)}
        if not m.top:
            skip |= set(components) - set(_owner_of(m.model, facts))
        lines = run(m.model, m.meaning, facts, sdks, observed_by, covered=covered, skip=skip)
        out += [m.prefix + line for line in lines]
    return out


# ---- answers: the exact line, or a family of lines with one reason ------------


def evidence_for_tree(
    tree: nest.Tree, facts: dict[str, Any], root: Path, lines: list[str]
) -> dict[str, str]:
    """This function hashes source evidence for exact answers and indexes it by printed
    diagnostic.

    Crossing-import evidence includes only the participating modules. Other evidence
    includes map source and mapped facts. An uncommitted source edit changes the digest.
    """
    components = facts.get("components", {})
    out: dict[str, str] = {}
    for m in tree.maps:
        out.update(_map_answer_evidence(m, facts, components, root, lines))
    return out


def _map_answer_evidence(
    m: nest.Map,
    facts: dict[str, Any],
    components: dict[str, Any],
    root: Path,
    lines: list[str],
) -> dict[str, str]:
    model_hash = hashlib.sha256(m.path.read_bytes()).hexdigest()
    crossings = {
        m.prefix + crossing_line(p, q, imports): imports
        for (p, q), imports in crossing_imports(m.model, facts).items()
    }
    out: dict[str, str] = {}
    for key in lines:
        if not key.startswith(m.prefix):
            continue
        state = judgement_evidence.answer_state(components, root, model_hash, crossings.get(key))
        encoded = json.dumps(state, sort_keys=True, default=str).encode()
        out[key] = hashlib.sha256(encoded).hexdigest()
    return out


def answer_digest(items: Iterable[str], evidence: Mapping[str, str]) -> str:
    """This function gives the evidence digest for an exact answer or group of exact items."""
    chosen = list(items)
    if len(chosen) == 1:
        return evidence.get(chosen[0], "unavailable")
    state = [(line, evidence.get(line, "unavailable")) for line in chosen]
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()


CROSSING_LINE = re.compile(
    "^crossing import: (\\S+) imports (\\S+) in \\d+ modules? and no flow connects"
)
SDK_LINE = re.compile(r"^model sdk: module \S+ imports (\S+) and its component ")
# How each kind's lines begin; the entry point line carries no colon.
KIND_PREFIX = {kind: f"{kind}: " for kind in LINE_KINDS} | {"entry point": "entry point "}


def unprefixed(line: str) -> str:
    """This function removes a nested-map prefix if the remainder is a known diagnostic."""
    if any(line.startswith(prefix) for prefix in KIND_PREFIX.values()):
        return line
    _head, sep, rest = line.partition(": ")
    if sep and any(rest.startswith(prefix) for prefix in KIND_PREFIX.values()):
        return rest
    return line


def answers(answer: Answer, line: str) -> bool:
    """This function selects a diagnostic with one answer.

    Exact items include the printed map prefix. Family selectors use the diagnostic
    without that prefix.
    """
    if answer.items:
        return line in answer.items
    line = unprefixed(line)
    if answer.crossing is not None:
        found = CROSSING_LINE.match(line)
        return found is not None and {found[1], found[2]} <= set(answer.crossing)
    if answer.crossing_into:
        found = CROSSING_LINE.match(line)
        return found is not None and found[2] == answer.crossing_into
    if answer.crossing_from:
        found = CROSSING_LINE.match(line)
        return found is not None and found[1] == answer.crossing_from
    if answer.kind:
        return line.startswith(KIND_PREFIX[answer.kind])
    if answer.module_sdk:
        found = SDK_LINE.match(line)
        return found is not None and found[1] == answer.module_sdk
    return False


@dataclass(frozen=True)
class Answered:
    """This record contains open diagnostics, accepted counts, stale answers, pending
    reviews, and policy notices.
    """

    open: list[str]
    answered: int
    stale: list[str]
    pending: list[str] = field(default_factory=list)
    policies: list[str] = field(default_factory=list)


def apply_answers(
    lines: list[str], answer_list: Iterable[Answer], evidence: Mapping[str, str] | None = None
) -> Answered:
    """This function accepts supported answers and gives open diagnostics, stale answers,
    and pending reviews.
    """
    given = list(answer_list)
    accepted, pending, policies = _accepted_answers(lines, given, evidence)
    covered = [line for line in lines if any(answers(a, line) for a in accepted)]
    stale = _stale_answers(given, lines)
    return Answered(
        open=[line for line in lines if line not in covered],
        answered=len(covered),
        stale=stale,
        pending=pending,
        policies=policies,
    )


def _accepted_answers(
    lines: list[str], given: list[Answer], evidence: Mapping[str, str] | None
) -> tuple[list[Answer], list[str], list[str]]:
    pending: list[str] = []
    policies: list[str] = []
    accepted: list[Answer] = []
    for a in given:
        matches = [line for line in lines if answers(a, line)]
        if not matches:
            continue
        issue = _answer_issue(a, evidence)
        if issue is None:
            accepted.append(a)
            if evidence is not None and not a.items:
                policies.append(_policy_line(a, matches))
        else:
            pending.append(issue)
    return accepted, pending, policies


def _policy_line(answer: Answer, matches: list[str]) -> str:
    new = sum(line not in answer.reviewed for line in matches)
    return (
        f"{answer.label} covers {len(matches)} lines at this snapshot. {new} lines are "
        f"outside the source-review baseline."
    )


def _answer_issue(answer: Answer, evidence: Mapping[str, str] | None) -> str | None:
    if evidence is None:
        return None
    if answer.items:
        digest = answer_digest(answer.items, evidence)
        if answer.evidence and answer.evidence == digest and digest != "unavailable":
            return None
        return (
            f''''{answer.label}' must have a new source review. The evidence digest is "{digest}"'''
        )
    if answer.policy:
        return None
    return f"'{answer.label}' must have policy = true for a family of lines."


def _stale_answers(given: list[Answer], lines: list[str]) -> list[str]:
    stale: list[str] = []
    for answer in given:
        if answer.items:
            stale.extend(item for item in answer.items if item not in lines)
        elif not any(answers(answer, line) for line in lines):
            stale.append(answer.label)
    return stale


def of_kind(lines: list[str], kind: str) -> list[str]:
    """This function gives diagnostics of one kind across all maps."""
    return [line for line in lines if unprefixed(line).startswith(KIND_PREFIX[kind])]


def kind_of(line: str) -> str:
    """This function identifies a diagnostic kind from its stable prefix."""
    bare = unprefixed(line)
    for kind, prefix in KIND_PREFIX.items():
        if bare.startswith(prefix):
            return kind
    return ""


def report(
    lines: list[str] | Answered,
    detail: dict[str, list[str]] | None = None,
    kind: str = "",
    teach: bool = True,
) -> list[str]:
    """This function formats judgement diagnostics for the CLI.

    The detail argument supplies verbose import lines. The kind argument selects one
    visible kind, but the counts include all kinds. The teach option gives one
    explanation for each visible kind.
    """
    result = lines if isinstance(lines, Answered) else Answered(lines, 0, [])
    shown = of_kind(result.open, kind) if kind else result.open
    out = [_head(result, kind, len(shown))]
    out += _shown(shown, detail, teach)
    out += [
        f"  stale answer: '{item}' is now missing. Remove it from [judgement] answered."
        for item in result.stale
    ]
    out += [f"  pending answer: {item}" for item in result.pending or []]
    out += [f"  policy answer: {item}" for item in result.policies or []]
    return out


def _head(result: Answered, kind: str, showing: int) -> str:
    """This function formats the open, accepted, stale, and visible diagnostic counts."""
    tail = ""
    if result.answered:
        tail += f", {result.answered} answered"
    if result.stale:
        tail += f", {len(result.stale)} stale"
    if not result.open:
        head = f"judgement: No decision is necessary{tail}"
    else:
        noun = "item" if len(result.open) == 1 else "items"
        head = f"judgement: {len(result.open)} {noun} for maintainer decisions{tail}"
    if kind:
        head += f". The report shows {showing} {kind} {('line' if showing == 1 else 'lines')}"
    return head


def _shown(shown: list[str], detail: dict[str, list[str]] | None, teach: bool) -> list[str]:
    """This function gives each diagnostic with optional import detail and one explanation
    for each kind.
    """
    out: list[str] = []
    taught: set[str] = set()
    for line in shown:
        out.append(f"  {line}")
        if detail:
            out += [f"    {item}" for item in detail.get(line, [])]
        here = kind_of(line)
        if teach and here and here not in taught:
            taught.add(here)
            out += explain.rows(here)
    return out
