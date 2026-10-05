"""The sequence coverage checks use exact entry point identities.

A sequence with a source review specifies each entry point by kind, module, target, and
local name. A display name or description cannot supply exact coverage because the same
words can refer to another entry point.
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
    """This function gives exact entry point identities from nonempty sequences with source
    reviews on all maps.
    """
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
    """This function finds entry points without exact sequence coverage in the inventory."""
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
    """This function identifies an entry point that refers to the same console script under
    another name.
    """
    module = p["module"]
    if p["kind"] == "main_function":
        return scripts.get(module, {}).get("target") == "main"
    if p["kind"] == "main_module":
        return any(m in scripts for m in components.get(module, {}).get("uses", {}))
    return False


def crowd_label(how_many: int, kind: str, card: str) -> str:
    """This function gives a label for a group of entry points, such as 190 routes into
    HttpApi.
    """
    return f"{how_many} {kind}s into {card}"


def _entry_lines(points: list[dict[str, str]], owner: dict[str, str]) -> list[str]:
    """This function gives one diagnostic per entry point or component group, in facts
    order.
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
            out.append(f"entry point {entry_label(p)} has no sequence{where}")
            continue
        if key not in said:
            said.add(key)
            said_as = crowd_label(len(found), p["kind"], who)
            out.append(f"entry point {said_as} have no sequence{where}")
    return out


def journey_problems(
    meaning: Meaning, facts: dict[str, Any], cards: Collection[str] = ()
) -> list[str]:
    """This function finds draft sequences, stale entry identities, and legacy coverage
    that must have a source review.
    """
    drafted = [
        (
            f"drafted journey: {j.id} ({j.label}) has no maintainer source review after "
            f"the agent write."
        )
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
            (
                f"journey start: {j.id} starts at {j.starts}, but the facts contain no such "
                f"entry point."
            )
            for j in meaning.journeys
            if j.starts and j.starts not in ways
        ]
    )


def _coverage_lines(
    journey: Journey, points: list[dict[str, str]], cards: Collection[str], known: set[str]
) -> list[str]:
    out = []
    if not journey.steps:
        out.append(
            f"journey start: {journey.id} has no steps. An empty sequence gives no entry "
            f"point coverage."
        )
    out.extend(
        f"journey start: {journey.id} covers {identity}, but the facts contain no such entry point."
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
            (
                f"journey start: {journey.id} uses a legacy start. Examine the source. Then "
                f"set covers=({entry_identity(matches[0])!r},)"
            )
        ]
    if len(matches) > 1:
        return [
            (
                f"journey start: {journey.id} starts at {journey.starts}, which resolves to "
                f"multiple entry points. Add exact covers."
            )
        ]
    if journey.starts in cards:
        return [
            (
                f"journey start: {journey.id} starts at component {journey.starts}. Add exact "
                f"covers for entry points with a source review."
            )
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
        (
            f"journey start: {journey.id} mentions {sample}{more}. Examine the source. "
            f"Then set exact covers."
        )
    ]
