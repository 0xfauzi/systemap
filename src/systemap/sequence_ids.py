"""The sequence identifier check: each sequence of a map has its own id.

The page selects a sequence by its id, and `systemap journeys` refuses a draft with an id
that the map uses. The model check gives one problem for each repeated id.

This module imports no model class when it runs, because `model` imports this module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from systemap.model import Meaning


def problems(meaning: Meaning) -> list[str]:
    """Give one problem for each sequence with the id of a previous sequence."""
    named = [journey.id for journey in meaning.journeys]
    return [
        f"journey {name} is the id of two sequences. Give each sequence its own id"
        for k, name in enumerate(named)
        if name in named[:k]
    ]
