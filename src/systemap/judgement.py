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
(`kind`), every model-sdk line for one import (`module_sdk`). An answer
that matches no line is
reported as stale, so answers cannot rot. `--strict` makes the CLI exit
1 while any line is open, for a workflow.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from systemap.config import LINE_KINDS, Answer, ConfigError
from systemap.extract import entry_label
from systemap.model import Component, Meaning, Model, claimed, flow_layers, is_symbol

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


def sdk_of(name: str, sdks: Iterable[str]) -> str:
    """The SDK an imported dotted name belongs to, or empty."""
    for sdk in sdks:
        if name == sdk or name.startswith(sdk + "."):
            return sdk
    return ""


def model_sdk_imports(
    model: Model, facts: dict[str, Any], sdks: Iterable[str] = MODEL_SDKS
) -> list[str]:
    """Every module that imports a model SDK from a component that is not an agent.

    The facts record each module's third-party imports; the agentic layers
    exist for the parts that run a model. A module that imports one and
    sits in a plain component, a store or a tool is either an agent the
    map does not show or a call the reader should know about. A component
    marked `calls_model` has answered: the map says it calls a model once.
    """
    components = facts.get("components", {})
    owner = _owner_of(model, facts)
    runs_a_model = {c.id for c in model.components if c.model_end}
    sdk_list = list(sdks)
    out: list[str] = []
    for module in sorted(components):
        p = owner.get(module)
        if not p or p in runs_a_model:
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
) -> list[str]:
    """Every line the maintainer should read, in the order above."""
    return (
        single_module(model, facts)
        + mis_folds(model, meaning, facts)
        + no_sentence(model, meaning)
        + thin_layers(model, meaning)
        + entry_points_without_journey(model, meaning, facts)
        + crossing_imports_without_flow(model, facts)
        + model_sdk_imports(model, facts, sdks)
    )


# ---- answers: the exact line, or a family of lines with one reason ------------

CROSSING_LINE = re.compile(
    r"^crossing import: module \S+ \(component (\S+)\) imports module \S+ "
    r"\(component (\S+)\) and no flow joins "
)
SDK_LINE = re.compile(r"^model sdk: module \S+ imports (\S+) and its component ")
# How each kind's lines begin; the entry point line carries no colon.
KIND_PREFIX = {kind: f"{kind}: " for kind in LINE_KINDS} | {"entry point": "entry point "}


def answers(answer: Answer, line: str) -> bool:
    """Does one answer cover this line?"""
    if answer.items:
        return line in answer.items
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


def apply_answers(lines: list[str], answer_list: Iterable[Answer]) -> Answered:
    """Suppress every line the configuration answers; report the rest and the stale."""
    given = list(answer_list)
    covered = [line for line in lines if any(answers(a, line) for a in given)]
    stale: list[str] = []
    for a in given:
        if a.items:
            stale += [item for item in a.items if item not in lines]
        elif not any(answers(a, line) for line in lines):
            stale.append(a.label)
    return Answered(
        open=[line for line in lines if line not in covered],
        answered=len(covered),
        stale=stale,
    )


def report(lines: list[str] | Answered) -> list[str]:
    """The lines the CLI prints."""
    result = lines if isinstance(lines, Answered) else Answered(lines, 0, [])
    open_lines = result.open
    tail = ""
    if result.answered:
        tail += f", {result.answered} answered"
    if result.stale:
        tail += f", {len(result.stale)} stale"
    if not open_lines:
        head = f"judgement: nothing to confirm{tail}"
    else:
        noun = "item" if len(open_lines) == 1 else "items"
        head = f"judgement: {len(open_lines)} {noun} for the maintainer to confirm{tail}"
    out = [head] + [f"  {line}" for line in open_lines]
    out += [
        f"  stale answer: '{item}' no longer appears; remove it from [judgement] answered"
        for item in result.stale
    ]
    return out
