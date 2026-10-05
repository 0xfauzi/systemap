"""systemap makes a map of a software system.

The extractor reads facts from source code. A coding agent writes the meaning with the
systemap skill. A maintainer examines the claims. The page generator uses the facts and
model.
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

__version__ = "1.2.0"

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
