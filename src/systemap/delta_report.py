"""The report generator formats map changes as text.

The text report gives the delta lines in two groups: the lines that need an action in
the map, and the lines that need no action. Its last line gives the next command.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from systemap import explain

if TYPE_CHECKING:
    from systemap.delta import Delta, Line

NEXT = "systemap refresh && systemap check && systemap judgement --strict"
# The heads of the text report: the map needs a change, or the map agrees with the source.
NEEDS_UPDATE = "The map needs an update"
CURRENT = "The map is current."
FULL_LOOP_SHARE = 1 / 3


# ---- the text report -------------------------------------------------------------------


def _label(ref: str, sha: str) -> str:
    short = sha[:7]
    if ref and short and not ref.startswith(short) and ref != sha:
        return f"{ref} ({short})"
    return ref or short


def _counts(d: Delta) -> str:
    modules = "module" if d.changed == 1 else "modules"
    return (
        f"{d.changed} {modules} changed, {d.added} added, {d.removed} removed, {d.moved} "
        f"moved. {len(d.named)} of {d.cards} components have changes"
    )


FULL_LOOP = (
    "The change includes more than one third of the components. Use the full skill "
    "maintenance procedure."
)


def report(d: Delta, teach: bool = True) -> list[str]:
    """This function gives a CLI change report with diagnostic groups and actions.

    The teach option adds one explanation for each kind.
    """
    span = f"{_label(d.base_ref, d.base)} -> {_label(d.head_ref, d.head)}"
    if not d.has_change:
        pair = f"{_label(d.base_ref, d.base)} and {_label(d.head_ref, d.head)}"
        return [f"delta: no module changed between {pair}. The map has no source-fact change"]
    out = [f"delta: {span}: {_counts(d)}"]
    # One report teaches a kind once, whichever group it first appears in.
    taught: set[str] = set()
    if d.open:
        out.append(f"{NEEDS_UPDATE} ({len(d.open)}):")
        out += _lines_taught(d.open, teach, taught)
    if d.quiet:
        out.append(f"No action is necessary for these changes ({len(d.quiet)}):")
        out += _lines_taught(d.quiet, teach, taught)
    out += near_lines(d, teach)
    if d.past_a_third:
        out.append(FULL_LOOP)
    if d.open:
        out.append(f'Do the action in each line under "{NEEDS_UPDATE}". Then run {NEXT}')
    else:
        out.append(f"{CURRENT} Run systemap refresh to write the facts and the page again.")
    return out


def near_lines(d: Delta, teach: bool = True) -> list[str]:
    """This function lists components connected to the primary changed component as
    context.

    This list is not a prediction of runtime impact.
    """
    if not (d.seed and d.near):
        return []
    if len(d.near) > d.cards * FULL_LOOP_SHARE:
        # A card joined to a third of the map has no neighbourhood: the list
        # would be the map. Measured over 359 pull requests, this silences
        # 18% of them and the rest hold 5 cards at the median, 8 at the
        # ninetieth (`bench/jev/near.py`).
        return [
            "next to the change:",
            (
                f"  {d.seed} has the most changed modules. It has flows to {len(d.near)} of "
                f"the {d.cards} components, so the list gives no useful context."
            ),
        ]
    out = [
        "next to the change:",
        (
            f"  {d.seed} has the most changed modules. Its connected components are "
            f"{_all_named(d.near)}"
        ),
    ]
    return out + (explain.rows("next to the change") if teach else [])


def _all_named(cards: tuple[str, ...]) -> str:
    """This function gives all component names as a list in a sentence."""
    if len(cards) == 1:
        return cards[0]
    return ", ".join(cards[:-1]) + f" and {cards[-1]}"


def _lines_taught(lines: list[Line], teach: bool, taught: set[str]) -> list[str]:
    """This function gives diagnostic lines and one explanation for each kind."""
    out: list[str] = []
    for line in lines:
        out.append(f"  {line.text}")
        if teach and line.kind not in taught:
            taught.add(line.kind)
            out += explain.rows(line.kind)
    return out
