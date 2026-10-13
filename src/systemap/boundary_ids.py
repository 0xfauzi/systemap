"""This module finds region and container ids that do not identify one boundary.

A component names its region or container by id, and the layout finds the boundary by
that id. Two regions with the same id, two containers with the same id, or a region and
a container with the same id thus make the component boundary ambiguous.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol


class Boundary(Protocol):
    """A region or a container: a boundary with an id."""

    @property
    def id(self) -> str: ...


def problems(regions: Iterable[Boundary], containers: Iterable[Boundary]) -> list[str]:
    """Give a placement finding for each id that identifies more than one boundary."""
    regions, containers = list(regions), list(containers)
    out = _twice("region", regions) + _twice("container", containers)
    shared = {r.id for r in regions} & {c.id for c in containers}
    out += [
        f"region {rid} has the id of a container. Give each region and container a different id"
        for rid in sorted(shared)
    ]
    return out


def _twice(kind: str, boundaries: list[Boundary]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for boundary in boundaries:
        if boundary.id in seen:
            out.append(
                f"{kind} {boundary.id} is the id of two {kind}s. Give each {kind} a different id"
            )
        seen.add(boundary.id)
    return out
