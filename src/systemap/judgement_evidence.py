"""The evidence digests bind exact judgement answers to source data.

The evidence of a judgement line is the evidence that the line names. For each component
that the line names, the evidence has the map claims of the component
(`card_review.claims`). For each module that the line names, and each module of a named
component, the evidence has the module facts and the digest of the source file. A change
to a different component, or to a `source_review` value, does not change the evidence.

A line that names no component and no module has the full evidence: the digest of the
model file, and the facts and source of all modules. A crossing-import line has the
imports between the two components and the source of the two modules of each import.

This module uses only language-neutral facts: the module records and their `file` fields.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from systemap import card_review, nest, repo_files
from systemap.model import Component, claimed, is_symbol
from systemap.source_text import text_digest


def _source_hash(root: Path, record: dict[str, Any]) -> str:
    """This function hashes source bytes because saved facts can predate an uncommitted
    edit. CRLF and LF checkouts of the same text give the same digest.
    """
    name = record.get("file")
    if not isinstance(name, str):
        return "unknown source"
    try:
        return text_digest(repo_files.read_bytes(root, name))
    except OSError:
        return "missing source"


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


def full_state(components: dict[str, Any], root: Path, model_hash: str) -> Any:
    """Give the evidence of a line that names nothing: the model file and all modules."""
    return {
        "model": model_hash,
        "facts": [
            (name, _answer_facts(record), _source_hash(root, record))
            for name, record in sorted(components.items())
        ],
    }


def line_state(m: nest.Map, facts: dict[str, Any], root: Path, line: str) -> Any:
    """Give the evidence of a line that names components or modules, or None.

    None tells the caller to use `full_state`.
    """
    components = facts.get("components", {})
    cards = named_cards(m, line)
    modules = sorted(set(line_modules(m, line, facts)))
    if not cards and not modules:
        return None
    return {
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
