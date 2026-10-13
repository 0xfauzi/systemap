"""The evidence digests bind exact judgement answers to source data.

The evidence of a judgement line is the evidence that the line names. For each component
that the line names, the evidence has the map claims of the component
(`card_review.claims`). For each module that the line names, and each module of a named
component, the evidence has the module facts and the digest of the source file. A change
to a different component, or to a `source_review` value, does not change the evidence.

A line that names no component and no module has the full evidence: the digest of the
model files (`model_digest`), and the facts and source of all modules. A crossing-import
line has the imports between the two components and the source of the two modules of
each import.

A `step source` line also has the claim of its sequence step: the step record and the
map claims of its acting and measured components. Thus a change to the step changes the
evidence, also when the line names no component.

An `entry point` line also has the entry point records of its modules, or all records
if it has the full evidence. A record gives the kind, the module, the target, and the
name. Thus a new target of an entry point changes the evidence.

An `unknown surface` line of a module or a test file cites one or more statements. Its
evidence is each unknown record without its line number and parser version, and the
text of the source line at that number (`located_state`). A new line above a statement
does not change the evidence. A change to a statement changes the record or the source
line, and thus the evidence.

This module uses only language-neutral facts: the module records, their `file` fields,
and the entry point records.
"""

from __future__ import annotations

import dataclasses
import json
import re
from collections.abc import Collection
from pathlib import Path
from typing import Any

from systemap import card_review, flow_ids, model_load, nest, repo_files, step_refs
from systemap.model import Component, claimed, is_symbol
from systemap.source_facts import Located, entry_identity
from systemap.source_text import text_digest

# The start of an entry point line, after the map prefix (`journey_coverage`).
ENTRY_LINE = "entry point "


def _source_hash(root: Path, record: dict[str, Any]) -> str:
    """This function hashes source bytes because saved facts can predate an uncommitted
    edit. CRLF and LF checkouts of the same text give the same digest.

    A missing file gives "missing source". A file that `repo_files` refuses gives its
    cause, for example "refused source: link out of the repository".
    """
    name = record.get("file")
    if not isinstance(name, str):
        return "unknown source"
    try:
        return text_digest(repo_files.read_bytes(root, name))
    except FileNotFoundError:
        return "missing source"
    except OSError as exc:
        return f"refused source: {repo_files.refusal(exc)}"


def _answer_facts(record: dict[str, Any]) -> dict[str, Any]:
    """This function removes the parser-specific syntax fingerprints from the evidence
    state.
    """
    stable = {key: value for key, value in record.items() if key not in {"syntax_sha", "api"}}
    stable["api"] = [
        {key: value for key, value in item.items() if key != "fingerprint"}
        for item in record.get("api", [])
    ]
    return stable


def names(name: str, text: str) -> bool:
    """Find the exact name as a full word. A dotted name that contains it is not a match."""
    return re.search(rf"(?<![\w.-]){re.escape(name)}(?![\w-]|\.\w)", text) is not None


def map_of(tree: nest.Tree, line: str) -> nest.Map:
    """Give the map of a judgement line: the nested map with the longest prefix, or the top."""
    nested = [m for m in tree.maps if m.id and line.startswith(m.prefix)]
    return max(nested, key=lambda m: len(m.id)) if nested else tree.top


def card_modules(card: Component, facts: dict[str, Any]) -> list[str]:
    """Give the modules of a component: its module claims and the modules of its symbols."""
    components = facts.get("components", {})
    found = claimed(card, components)
    found += [p.partition(":")[0] for p in card.implemented_by if is_symbol(p)]
    return found


def named_cards(m: nest.Map, line: str) -> list[Component]:
    """Give the components of the map that the line names."""
    bare = line[len(m.prefix) :]
    return [card for card in m.model.components if names(card.id, bare)]


def line_modules(m: nest.Map, line: str, facts: dict[str, Any]) -> list[str]:
    """Give the modules of the components and the modules that a judgement line names."""
    bare = line[len(m.prefix) :]
    modules = [module for card in named_cards(m, line) for module in card_modules(card, facts)]
    modules += [name for name in facts.get("components", {}) if names(name, bare)]
    return modules


def model_digest(m: nest.Map) -> str:
    """Give the digest of the model file and each model file that it imports.

    A model file without imports keeps the digest of its text, as before. If the data
    reader refuses the model files, the digest is the digest of the loaded MODEL and
    MEANING values. This occurs only for model code with SYSTEMAP_TRUST_MODEL_CODE=1.
    """
    try:
        paths = model_load.files(m.path, m.rel)
    except model_load.ModelFileError:
        return text_digest(repr((m.model, m.meaning)).encode())
    if len(paths) == 1:
        return text_digest(paths[0].read_bytes())
    files = sorted((path.name, text_digest(path.read_bytes())) for path in paths)
    return text_digest(json.dumps(files).encode())


def entry_points(
    m: nest.Map, facts: dict[str, Any], line: str, modules: Collection[str] | None = None
) -> list[str] | None:
    """Give the entry point records of an `entry point` line, or None for other lines.

    The records are the records of the modules, or all records if `modules` is None.
    """
    if not line[len(m.prefix) :].startswith(ENTRY_LINE):
        return None
    return [
        entry_identity(point)
        for point in facts.get("entry_points", [])
        if modules is None or point.get("module") in modules
    ]


def full_state(
    components: dict[str, Any], root: Path, model_hash: str, points: list[str] | None = None
) -> Any:
    """Give the evidence of a line that names nothing: the model files and all modules.

    For an `entry point` line, `points` gives all entry point records.
    """
    state = {
        "model": model_hash,
        "facts": [
            (name, _answer_facts(record), _source_hash(root, record))
            for name, record in sorted(components.items())
        ],
    }
    if points is not None:
        state["entry_points"] = points
    return state


def line_state(m: nest.Map, facts: dict[str, Any], root: Path, line: str) -> Any:
    """Give the evidence of a line that names components or modules, or None.

    None tells the caller to use `full_state`.
    """
    components = facts.get("components", {})
    cards = named_cards(m, line)
    modules = sorted(set(line_modules(m, line, facts)))
    step = step_claim(m, line)
    if not cards and not modules and step is None:
        return None
    state = {
        "claims": [
            (card.id, card_review.claims(card, m.model, m.meaning))
            for card in sorted(cards, key=lambda card: card.id)
        ],
        "facts": [
            (
                module,
                _answer_facts(components.get(module, {})),
                _source_hash(root, components.get(module, {})),
            )
            for module in modules
        ],
    }
    points = entry_points(m, facts, line, set(modules))
    if points is not None:
        state["entry_points"] = points
    if step is not None:
        state["step"] = step
    return state


def step_claim(m: nest.Map, line: str) -> Any:
    """Give the claim of the sequence step of a `step source` line, or None for other lines.

    The claim is the step record (`flow_ids.journey_record`) and the map claims of the
    acting and measured components of the step."""
    bare = line[len(m.prefix) :]
    for journey in m.meaning.journeys:
        for k, step in enumerate(journey.steps, start=1):
            if not bare.startswith(f"{step_refs.KIND}: journey {journey.id} step {k} "):
                continue
            one = dataclasses.replace(journey, steps=(step,))
            members = set(step.acts) | set(step.measures)
            cards = [card for card in m.model.components if card.id in members]
            return {
                "step": flow_ids.journey_record(one)["steps"][0],
                "claims": [
                    (card.id, card_review.claims(card, m.model, m.meaning)) for card in cards
                ],
            }
    return None


def located_state(root: Path, found: list[Located]) -> Any:
    """Give the evidence of an `unknown surface` line with one or more cited statements,
    or None.

    For each record, the evidence has the record without its line number and parser
    version, and the text of the source line at that number. None tells the caller to use
    the module evidence: the line has no record, or a record has no line number.
    """
    if not found or any(item.line <= 0 for item in found):
        return None
    texts: dict[str, list[str]] = {}
    for item in found:
        if item.file not in texts:
            texts[item.file] = _source_rows(root, item.file)
    return [
        {
            "record": {k: v for k, v in item.record.items() if k not in ("line", "parser")},
            "statement": (
                texts[item.file][item.line - 1].rstrip()
                if item.line <= len(texts[item.file])
                else "missing source"
            ),
        }
        for item in found
    ]


def _source_rows(root: Path, file: str) -> list[str]:
    try:
        return repo_files.read_bytes(root, file).decode("utf-8", "replace").splitlines()
    except OSError:
        return []


def answer_state(
    components: dict[str, Any],
    root: Path,
    model_hash: str,
    imports: list[tuple[str, str]] | None,
) -> Any:
    """Give the full evidence, or the evidence of the imports of a crossing-import line."""
    if imports is None:
        return full_state(components, root, model_hash)
    return [
        (
            source,
            target,
            components[source].get("uses", {}).get(target, []),
            _source_hash(root, components[source]),
            _source_hash(root, components[target]),
        )
        for source, target in imports
    ]
