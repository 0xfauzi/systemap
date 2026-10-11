"""Draw the changed flows of a map comparison as a Mermaid diagram for a pull request.

GitHub draws a fenced `mermaid` block in a comment, so the comment can show the change
without an image file. The diagram has only the flows that the change added, removed,
or changed, and the components at their ends. Each label gives the change in words,
and each line style also shows it.
"""

from __future__ import annotations

from systemap.delta_model import ADDED, CHANGED, REMOVED, SOURCE, Drawn, MapChange

# A diagram with more flows than this is not easy to read in a comment.
MOST_FLOWS = 30
ARROWS = {ADDED: "==>", REMOVED: "-.->", CHANGED: "-->"}
CARD_WORDS = {
    ADDED: "added",
    REMOVED: "removed",
    CHANGED: "changed claims",
    SOURCE: "changed source",
}
# Mermaid entity codes for the characters that can end a label or a code block.
CODES = (
    ("#", "#35;"),
    ('"', "#quot;"),
    ("|", "#124;"),
    ("<", "#lt;"),
    (">", "#gt;"),
    ("`", "#96;"),
)


def _quoted(text: str) -> str:
    """Give a Mermaid label in quotes. The entity codes keep the label in one piece."""
    for raw, code in CODES:
        text = text.replace(raw, code)
    return f'"{text}"'


def _selected(change: MapChange) -> tuple[list[Drawn], list[str]]:
    """Select the flows for the diagram, and give a sentence about the flows it omits.

    If there are too many flows, the diagram shows only the added and removed flows.
    """
    drawn = list(change.drawn)
    if len(drawn) <= MOST_FLOWS:
        return drawn, []
    kept = [f for f in drawn if f.how != CHANGED]
    if not kept or len(kept) > MOST_FLOWS:
        said = f"The comment has no diagram, because {len(drawn)} flows changed."
        return [], [f"{said} A diagram shows a maximum of {MOST_FLOWS} flows.", ""]
    said = f"The diagram shows only the added and removed flows, because {len(drawn)} flows"
    return kept, [f"{said} changed.", ""]


def mermaid(change: MapChange) -> list[str]:
    """Give the diagram of the changed flows. Without a changed flow, there is no diagram.

    The comment rows give the components without a changed flow.
    """
    drawn, said = _selected(change)
    if not drawn:
        return said
    ids: dict[str, str] = {}
    nodes: list[str] = []
    for name in (end for f in drawn for end in (f.src, f.dst)):
        if name not in ids:
            ids[name] = f"n{len(ids)}"
            word = CARD_WORDS.get(change.marks.get(name, ""), "")
            nodes.append(f"  {ids[name]}[{_quoted(f'{name} ({word})' if word else name)}]")
    edges = [
        f"  {ids[f.src]} {ARROWS[f.how]}|{_quoted(f'{f.artifact} ({f.how})')}| {ids[f.dst]}"
        for f in drawn
    ]
    return [*said, "```mermaid", "flowchart LR", *nodes, *edges, "```", ""]
