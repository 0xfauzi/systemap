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
    possible mis-fold .. a module whose dotted path shares no word with
                         the component's id, does, plain word or interface,
                         in a component of several modules, and whose
                         package holds none of the component's other
                         modules: it may be folded into the wrong part
    no sentence ........ a flow with no relation sentence, or a blank one
    thin layer ......... a flow layer (data, control, the agent kinds, or
                         the model's own) that lights fewer than two
                         components: the map may not be worth looking at
                         that way at all, or a standard kind was never used
    entry point ........ an entry point in the facts (a console script, a
                         subcommand, a main, a public function of the
                         package root) that no journey mentions: a walk
                         the reader may need and the map does not have
    crossing import .... a module of one component imports a module of
                         another and no flow joins the two components, in
                         either direction: an edge the code has and the
                         map does not. One line per ordered pair of
                         components, with how many modules of the first
                         import the second (`--verbose` lists them), so
                         a pair joined in sixteen places is one question,
                         not sixteen. The main tool of the second pass.
    declared flow ...... a flow no import backs, in either direction, and
                         whose sentence and artifact name none of the
                         mechanisms `[flows] observed_by` lists: an edge
                         the map has and the code does not. The agent
                         finds the evidence, names the mechanism in the
                         sentence, or removes the edge
    model sdk .......... a module imports a model SDK or an agent framework
                         (a built-in list, extended or reduced by `[facts]
                         model_sdks`) and its component is neither an agent
                         nor marked `calls_model`: the mechanical prompt for
                         the agentic layers. Setting `calls_model=True` on a
                         single-shot call site answers the line

An ignored module is not a question: its reason is on record under
`[coverage]`, and the check prints the count. It is not listed here.

The list has memory. A line the maintainer has answered lives in the
configuration, under `[judgement] answered`, with its reason; it is
suppressed here and counted, so the same line does not come back every
run and the answer is in the repository, not in a chat. An answer names
the exact line (`item`, or `items` for several), or a whole family with
one reason: every crossing-import line between any two of some
components in either direction (`crossing`), every one into a component
(`crossing_into`) or out of it (`crossing_from`), every line of one kind
(`kind`, `declared flow` included), every model-sdk line for one import
(`module_sdk`). An answer
that matches no line is
reported as stale, so answers cannot rot. `--strict` makes the CLI exit
1 while any line is open, for a workflow; `--kind KIND` prints the open
lines of one kind, and the exit code still reads them all.

The list runs on every map of the tree (`run_tree`). A sub-map's lines
carry its id in front (`Gateway: single module: ...`), so an `item`
answer quotes the line as printed; the bulk forms read the line behind
the prefix. An entry point, and a model sdk import, is asked about once,
on the deepest map whose card claims its module, against the journeys
of every map.
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
    return share_a_word(words(a), words(b))


def share_a_word(xs: set[str], ys: set[str]) -> bool:
    """`shares_a_word` over two word sets already split."""
    for x in xs:
        for y in ys:
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
    return [m for m in component.implemented_by if not m.endswith(".*") and not is_symbol(m)]


def single_module(model: Model, facts: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for c in model.components:
        if c.kind == "actor":
            continue
        modules = _modules_of(c, facts)
        if len(modules) == 1:
            out.append(f"single module: {c.id} is only {modules[0]}")
    return out


def package_of(module: str) -> str:
    """The package a module sits in: its path minus the last segment, or itself."""
    head, _, _ = module.rpartition(".")
    return head or module


def share_a_package(a: str, b: str) -> bool:
    """Do two modules sit in one package, or is one the other's package?"""
    return package_of(a) == package_of(b) or a == package_of(b) or b == package_of(a)


def mis_folds(model: Model, meaning: Meaning, facts: dict[str, Any]) -> list[str]:
    """Modules that may be folded into the wrong component.

    The line fires only when three things hold at once. Every word of the
    module's dotted path is a stranger to the component: none is shared
    with its id, its `does`, its plain word or its `interface`. The
    component claims more than one module (one module is the `single
    module` line's business). And the module's package holds none of the
    component's other modules and is not itself one of them, so it is not
    merely a differently named file among its neighbours. Comparing the
    id with the last path segment alone fired on most of a real map's
    modules; a component's prose names what it holds far more often than
    its id does.
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
                f"possible mis-fold: {c.id} claims {module} (no word shared with the "
                f"component, and no other module of it in {package_of(module)})"
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
            out.append(f"thin layer: {layer.id} lights {n} {noun}")
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
    """Entry points without reviewed coverage, grouped by kind and card."""
    owner = _owner_of(model, facts)
    return _entry_lines(ways_in_without_journey(meaning, facts, text, skip, owner, covered), owner)


Pair = tuple[str, str]


def crossing_pairs(
    components: dict[str, Any], owner: dict[str, str]
) -> dict[Pair, list[tuple[str, str]]]:
    """(P, Q) -> the (module, target) imports of P's modules into Q's, P and Q distinct.

    Read from raw facts records and an owner table, so `delta` can ask
    the same question of the facts at another commit.
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
    """The one line for a pair: how many modules of P import Q."""
    n = len({module for module, _target in imports})
    return (
        f"crossing import: {p} imports {q} in {n} module{'s' if n != 1 else ''} and no flow "
        "joins them"
    )


def crossing_imports(model: Model, facts: dict[str, Any]) -> dict[Pair, list[tuple[str, str]]]:
    """Every pair of components an import joins that no flow does, with the imports."""
    components = facts.get("components", {})
    joined = {frozenset(f.edge) for f in model.flows}
    return {
        pair: imports
        for pair, imports in crossing_pairs(components, _owner_of(model, facts)).items()
        if frozenset(pair) not in joined
    }


def crossing_imports_without_flow(model: Model, facts: dict[str, Any]) -> list[str]:
    """One line per ordered pair of components an import joins and no flow does.

    The facts record what each module imports. When a module of P imports
    a module of Q and the model has no flow P -> Q or Q -> P, the code has
    an edge the map does not. It may be one the reader needs, or one the
    map leaves out on purpose; either way it is looked at, not guessed.
    The line counts the modules of P that import Q; `crossing_detail`
    lists them for `--verbose`.
    """
    return [
        crossing_line(p, q, imports) for (p, q), imports in crossing_imports(model, facts).items()
    ]


def crossing_detail(model: Model, facts: dict[str, Any], prefix: str = "") -> dict[str, list[str]]:
    """line as printed -> the imports behind it, one `module imports target` each."""
    return {
        prefix + crossing_line(p, q, imports): [f"{m} imports {t}" for m, t in imports]
        for (p, q), imports in crossing_imports(model, facts).items()
    }


def crossing_detail_tree(tree: nest.Tree, facts: dict[str, Any]) -> dict[str, list[str]]:
    """`crossing_detail` for every map, each line carrying its map's prefix."""
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
    """Every flow the facts do not back: one line each, with the three ways out.

    The dual of the crossing-import line. A flow between two components
    neither of whose modules imports the other's, and whose sentence and
    artifact name no mechanism from `[flows] observed_by`, is a claim the
    code does not make. With no facts nothing can be observed, so nothing
    is listed; the CLI says the list reads the model alone.
    """
    if not facts.get("components"):
        return []
    return [
        f"declared flow: {f.src} -> {f.dst} ({f.artifact}): no import joins them; find the "
        "evidence, name the mechanism in the sentence, or remove it"
        for f in evidence.declared(model, meaning, facts, observed_by)
    ]


def sdk_of(name: str, sdks: Iterable[str]) -> str:
    """The SDK an imported dotted name belongs to, or empty."""
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
    """Every module that imports a model SDK from a component that is not an agent.

    The facts record each module's third-party imports; the agentic layers
    exist for the parts that run a model. A module that imports one and
    sits in a plain component, a store or a tool is either an agent the
    map does not show or a call the reader should know about. A component
    marked `calls_model` has answered: the map says it calls a model once.
    `skip` names the modules a map inside a card asks about instead.
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
    """The built-in SDK list with the configuration's additions and removals.

    An entry adds an import name; an entry with a leading `-` removes one
    of the built-in names (`-google.adk`, when the repository's own rule
    says what counts as an agent). Removing a name that is not on the
    list is refused: a silent no-op would hide a misspelling.
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
    """Every line the maintainer should read for one map, in the order above.

    `journeys_text` and `skip` are what `run_tree` passes for a map in a
    tree: every map's journeys, and the modules a map below asks about.
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
    """Flows whose direction and artifact still need current source review."""
    states = evidence.of_model(model, meaning, facts, observed_by)
    return [
        f"flow review: {flow.src} -> {flow.dst} ({flow.artifact}) has structural "
        "evidence but no source-reviewed claim; cite current source for direction "
        "and artifact or revise the flow"
        for flow in model.flows
        if states[flow.edge].state == evidence.STRUCTURAL or states[flow.edge].unresolved_refs
    ]


def run_tree(
    tree: nest.Tree,
    facts: dict[str, Any],
    sdks: Iterable[str] = MODEL_SDKS,
    observed_by: Iterable[str] = (),
) -> list[str]:
    """Every line for every map, a sub-map's each carrying its id in front.

    An entry point or a model sdk import in a module a card opens a map
    on is that map's question, not the card's, so the top map skips the
    modules its opening cards claim, and a sub-map asks only about the
    modules its own cards claim. A journey on any map covers an entry
    point: a walk through the top map traces the card as a whole.
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
    """Digest the evidence an exact answer reviewed, keyed by its printed line.

    Crossing imports use only the participating modules. Other lines use the
    map source and mapped facts because their supporting dependency set is not
    narrower. A changed uncommitted source file therefore changes the digest.
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
    """The digest to record for one exact decision, including an items group."""
    chosen = list(items)
    if len(chosen) == 1:
        return evidence.get(chosen[0], "unavailable")
    state = [(line, evidence.get(line, "unavailable")) for line in chosen]
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()


CROSSING_LINE = re.compile(
    r"^crossing import: (\S+) imports (\S+) in \d+ modules? and no flow joins"
)
SDK_LINE = re.compile(r"^model sdk: module \S+ imports (\S+) and its component ")
# How each kind's lines begin; the entry point line carries no colon.
KIND_PREFIX = {kind: f"{kind}: " for kind in LINE_KINDS} | {"entry point": "entry point "}


def unprefixed(line: str) -> str:
    """A sub-map's line without the `<map>: ` in front of it; any other line as it is."""
    if any(line.startswith(prefix) for prefix in KIND_PREFIX.values()):
        return line
    _head, sep, rest = line.partition(": ")
    if sep and any(rest.startswith(prefix) for prefix in KIND_PREFIX.values()):
        return rest
    return line


def answers(answer: Answer, line: str) -> bool:
    """Does one answer cover this line?

    An exact item is the line as printed, a sub-map's prefix included;
    the bulk forms read the line behind the prefix, so one `kind` or
    `crossing` answer covers every map.
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
    """The list once the configuration's answers are applied.

    `open` is what is still to confirm, `answered` how many lines an
    answer suppressed, and `stale` every answer (an exact item, or a
    bulk form named as written) no line matches: the model or the code
    moved on and the answer should go.
    """

    open: list[str]
    answered: int
    stale: list[str]
    pending: list[str] = field(default_factory=list)
    policies: list[str] = field(default_factory=list)


def apply_answers(
    lines: list[str], answer_list: Iterable[Answer], evidence: Mapping[str, str] | None = None
) -> Answered:
    """Suppress every line the configuration answers; report the rest and the stale."""
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
        f"{answer.label} covers {len(matches)} current lines; {new} outside its reviewed baseline"
    )


def _answer_issue(answer: Answer, evidence: Mapping[str, str] | None) -> str | None:
    if evidence is None:
        return None
    if answer.items:
        digest = answer_digest(answer.items, evidence)
        if answer.evidence and answer.evidence == digest and digest != "unavailable":
            return None
        return f"'{answer.label}' needs renewed review; current evidence = \"{digest}\""
    if answer.policy:
        return None
    return f"'{answer.label}' needs policy = true to cover a family of lines"


def _stale_answers(given: list[Answer], lines: list[str]) -> list[str]:
    stale: list[str] = []
    for answer in given:
        if answer.items:
            stale.extend(item for item in answer.items if item not in lines)
        elif not any(answers(answer, line) for line in lines):
            stale.append(answer.label)
    return stale


def of_kind(lines: list[str], kind: str) -> list[str]:
    """The lines of one kind, on any map."""
    return [line for line in lines if unprefixed(line).startswith(KIND_PREFIX[kind])]


def kind_of(line: str) -> str:
    """Which kind of line this is, by the prefix it was printed with."""
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
    """The lines the CLI prints.

    `detail` (from `--verbose`) is what a line stands for, printed under
    it: the imports behind a crossing-import line. `kind` (from `--kind`)
    prints the open lines of that kind alone; the head still counts them
    all, since the exit code does.

    `teach` prints why the kind matters and what to do about it, from
    `systemap.explain`, under the first line of each kind rather than
    under every one: the same two sentences ten times over is noise, and
    a report a reader skips teaches nothing. `--brief` turns it off.
    """
    result = lines if isinstance(lines, Answered) else Answered(lines, 0, [])
    shown = of_kind(result.open, kind) if kind else result.open
    out = [_head(result, kind, len(shown))]
    out += _shown(shown, detail, teach)
    out += [
        f"  stale answer: '{item}' no longer appears; remove it from [judgement] answered"
        for item in result.stale
    ]
    out += [f"  pending answer: {item}" for item in result.pending or []]
    out += [f"  policy answer: {item}" for item in result.policies or []]
    return out


def _head(result: Answered, kind: str, showing: int) -> str:
    """The first line: what is open, what was answered, and what is being shown."""
    tail = ""
    if result.answered:
        tail += f", {result.answered} answered"
    if result.stale:
        tail += f", {len(result.stale)} stale"
    if not result.open:
        head = f"judgement: nothing to confirm{tail}"
    else:
        noun = "item" if len(result.open) == 1 else "items"
        head = f"judgement: {len(result.open)} {noun} for the maintainer to confirm{tail}"
    if kind:
        head += f"; showing the {showing} {kind} {'line' if showing == 1 else 'lines'}"
    return head


def _shown(shown: list[str], detail: dict[str, list[str]] | None, teach: bool) -> list[str]:
    """Each line, what it stands for with `--verbose`, and its kind taught once."""
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
