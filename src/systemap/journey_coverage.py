"""Exact entry coverage and journey migration diagnostics.

A reviewed journey names each entry by kind, module, target, and local name.
A display name or sentence cannot cover an entry because those words may
also describe a different route or task.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from typing import Any

from systemap.evidence import mentioned
from systemap.extract import entry_identity, entry_label
from systemap.model import Journey, Meaning

# Past this many uncovered ways in of one kind into one card, they are asked
# about together: a hundred routes into one card is one question, not a hundred.
TOGETHER_AT = 4


def reviewed_entries(meanings: Iterable[Meaning]) -> set[str]:
    """Entry identities explicitly reviewed by a nonempty walk on any map."""
    out: set[str] = set()
    for meaning in meanings:
        for journey in meaning.journeys:
            if not journey.steps:
                continue
            out.update(journey.covers)
    return out


def ways_in_without_journey(
    meaning: Meaning,
    facts: dict[str, Any],
    text: str | None = None,
    skip: Collection[str] = (),
    owner: dict[str, str] | None = None,
    covered: Collection[str] | None = None,
) -> list[dict[str, str]]:
    """The ways in without an exact reviewed identity in their inventory."""
    points: list[dict[str, str]] = facts.get("entry_points", [])
    del text, owner
    reviewed = set(covered) if covered is not None else reviewed_entries((meaning,))
    scripts = {p["module"]: p for p in points if p["kind"] == "console_script"}
    components = facts.get("components", {})
    return [
        p
        for p in points
        if p["module"] not in skip
        and not _same_script(p, scripts, components)
        and entry_identity(p) not in reviewed
    ]


def _same_script(
    p: dict[str, str], scripts: dict[str, dict[str, str]], components: dict[str, Any]
) -> bool:
    """Is this way in a console script under another name?"""
    module = p["module"]
    if p["kind"] == "main_function":
        return scripts.get(module, {}).get("target") == "main"
    if p["kind"] == "main_module":
        return any(m in scripts for m in components.get(module, {}).get("uses", {}))
    return False


def crowd_label(how_many: int, kind: str, card: str) -> str:
    """A crowd of ways in, named: `190 routes into HttpApi`.

    `systemap journeys` names a crowd the same way, so the walk it writes and
    the line it answers read as the same thing.
    """
    return f"{how_many} {kind}s into {card}"


def _entry_lines(points: list[dict[str, str]], owner: dict[str, str]) -> list[str]:
    """One line per way in, or one line per card for the kinds that come in crowds.

    The order the facts list them in is kept, so a report does not reshuffle
    itself when one way in is answered.
    """
    crowds: dict[tuple[str, str], list[dict[str, str]]] = {}
    for p in points:
        crowds.setdefault((p["kind"], owner.get(p["module"], "")), []).append(p)
    out: list[str] = []
    said: set[tuple[str, str]] = set()
    for p in points:
        key = (p["kind"], owner.get(p["module"], ""))
        found, who = crowds[key], key[1]
        where = f" (component {who})" if who else ""
        if len(found) <= TOGETHER_AT or not who:
            out.append(f"entry point {entry_label(p)} has no journey{where}")
            continue
        if key not in said:
            said.add(key)
            said_as = crowd_label(len(found), p["kind"], who)
            out.append(f"entry point {said_as} have no journey{where}")
    return out


def journey_problems(
    meaning: Meaning, facts: dict[str, Any], cards: Collection[str] = ()
) -> list[str]:
    """Unconfirmed walks, stale identities, and legacy coverage to review."""
    drafted = [
        f"drafted journey: {j.id} ({j.label}) was written by an agent and not yet confirmed"
        for j in meaning.journeys
        if j.drafted
    ]
    points = facts.get("entry_points", [])
    ways = {p["name"] for p in points} | {entry_label(p) for p in points}
    ways |= set(cards)
    known = {entry_identity(point) for point in points}
    coverage = [
        line
        for journey in meaning.journeys
        for line in _coverage_lines(journey, points, cards, known)
    ]
    return (
        drafted
        + coverage
        + [
            f"journey start: {j.id} starts at {j.starts}, which the facts have no way in for"
            for j in meaning.journeys
            if j.starts and j.starts not in ways
        ]
    )


def _coverage_lines(
    journey: Journey, points: list[dict[str, str]], cards: Collection[str], known: set[str]
) -> list[str]:
    out = []
    if not journey.steps:
        out.append(f"journey start: {journey.id} has no steps; an empty walk covers no way in")
    out.extend(
        f"journey start: {journey.id} covers {identity}, which the facts have no way in for"
        for identity in journey.covers
        if identity not in known
    )
    if journey.steps and not journey.covers:
        out.extend(_legacy_lines(journey, points, cards))
    return out


def _legacy_lines(
    journey: Journey, points: list[dict[str, str]], cards: Collection[str]
) -> list[str]:
    if not journey.starts:
        return _word_candidates(journey, points)
    matches = [point for point in points if journey.starts in (point["name"], entry_label(point))]
    if len(matches) == 1:
        return [
            f"journey start: {journey.id} uses a legacy start; "
            f"confirm covers=({entry_identity(matches[0])!r},)"
        ]
    if len(matches) > 1:
        return [
            f"journey start: {journey.id} starts at {journey.starts}, "
            "which matches multiple ways in; add exact covers"
        ]
    if journey.starts in cards:
        return [
            f"journey start: {journey.id} starts at card {journey.starts}; "
            "add exact covers for reviewed ways in"
        ]
    return []


def _word_candidates(journey: Journey, points: list[dict[str, str]]) -> list[str]:
    words = "\n".join((journey.id, journey.label, *(step.say for step in journey.steps)))
    candidates = [
        point
        for point in points
        if mentioned(point["name"], words) or mentioned(entry_label(point), words)
    ]
    if not candidates:
        return []
    sample = ", ".join(entry_identity(point) for point in candidates[:3])
    more = f" and {len(candidates) - 3} more" if len(candidates) > 3 else ""
    return [
        f"journey start: {journey.id} mentions {sample}{more}; "
        "confirm exact covers after reviewing the source"
    ]
