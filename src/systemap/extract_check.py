"""The facts check compares the stored facts with the source tree for `extract --check`.

Stale facts need a new extraction. A model claim for a module that the source tree does
not have, and a model layout problem, need a model correction. A new extraction does not
correct them. The report gives the two groups separately, each with its correction.
"""

from __future__ import annotations

from typing import Any

from systemap import check, extract, nest

# More lines than this in one group give a count line in their place.
SHOWN = 25


def report(
    fresh: dict[str, Any], stored: dict[str, Any], tree: nest.Tree, prefixes: set[str]
) -> tuple[list[str], int]:
    """Give the report lines and the exit code: 0 if the map agrees with the source tree."""
    stale, model = problems(fresh, stored, tree, prefixes)
    if not stale and not model:
        return [f"map: The map agrees with the source tree: {len(fresh['components'])} modules."], 0
    out: list[str] = []
    if stale:
        out += _group("map: The map is stale", stale)
        out.append("run: systemap extract")
    if model:
        lines = [line for group in model.values() for line in group]
        out += _group("map: The model does not agree with the source tree", lines)
        out += [f"Correct {rel}. Then use systemap check." for rel in model]
    return out, 1


def problems(
    fresh: dict[str, Any], stored: dict[str, Any], tree: nest.Tree, prefixes: set[str]
) -> tuple[list[str], dict[str, list[str]]]:
    """Give the stale-facts lines, and the model lines for each model file.

    The drift is the facts' own. Each drift line occurs once, with the first map's prefix."""
    stale: dict[str, str] = {}
    model: dict[str, list[str]] = {}
    for m in tree.maps:
        claims = set(extract.mapping_drift(fresh, m.model, prefixes))
        for line in check.stale_facts(fresh, stored, m.model, prefixes):
            if line in claims:
                model.setdefault(m.rel, []).append(m.prefix + line)
            else:
                stale.setdefault(line, m.prefix + line)
    return list(stale.values()), model


def _group(head: str, lines: list[str]) -> list[str]:
    noun = "problem" if len(lines) == 1 else "problems"
    out = [f"{head} ({len(lines)} {noun}):"]
    out += [f"  {line}" for line in lines[:SHOWN]]
    if len(lines) > SHOWN:
        out.append(f"  ... and {len(lines) - SHOWN} more")
    return out
