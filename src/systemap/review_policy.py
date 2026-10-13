"""The review policy gives a finding for each source component without a source review.

`[judgement] require_reviews = true` selects this policy. The default is false. Then a
missing review is only a count in the judgement report, and a map without reviews can
pass `judgement --strict`. With the policy, each missing review is a finding, so
`judgement --strict` fails until the component has a recorded review.
"""

from __future__ import annotations

from typing import Any

from systemap import card_review, nest

KIND = "missing source review"


def line(card_id: str) -> str:
    """Give the finding line for one component. The line is an answer identifier."""
    return (
        f"{KIND}: {card_id} has no source_review digest. Examine its source and claims. "
        f"Then record the current digest."
    )


def missing_lines(tree: nest.Tree, facts: dict[str, Any]) -> list[str]:
    """Give one finding for each source component with the review state `missing`.

    Without facts, the report gives no review finding, as for stale reviews.
    """
    if not facts.get("components"):
        return []
    return [
        m.prefix + line(card.id)
        for m in tree.maps
        for card in m.model.components
        if card.kind != "actor"
        and card_review.state(card, m.model, m.meaning, facts) == card_review.MISSING
    ]
