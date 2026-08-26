"""systemap: the map your coding agent draws of your system.

Facts are read out of the code with `ast`; the meaning is authored by a
coding agent following the shipped skill and reviewed by a person; the map
draws what exists today; the checker refuses an incomplete or stale map;
and one generator draws every picture so nothing drifts.
"""

from __future__ import annotations

from systemap.model import (
    AGENT_KINDS,
    KINDS,
    STANDARD_KINDS,
    Component,
    Container,
    Flow,
    Invariant,
    Journey,
    Layer,
    Meaning,
    Model,
    Region,
    Step,
    all_layers,
    build_state,
)

__version__ = "1.0.3"

__all__ = [
    "AGENT_KINDS",
    "KINDS",
    "STANDARD_KINDS",
    "Component",
    "Container",
    "Flow",
    "Invariant",
    "Journey",
    "Layer",
    "Meaning",
    "Model",
    "Region",
    "Step",
    "__version__",
    "all_layers",
    "build_state",
]
