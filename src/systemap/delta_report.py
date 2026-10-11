"""The report generator formats map changes as text or Markdown.

The text report gives the delta lines in groups. The pull request comment gives the
decision first, then the map changes, a picture of the changed flows, and the lines that
need no action.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from systemap import delta_picture, explain
from systemap.delta_model import ADDED, CHANGED, REMOVED, SOURCE, Item, MapChange

if TYPE_CHECKING:
    from systemap.delta import Delta, Line

MARKER = "<!-- systemap delta -->"
NEXT = "systemap refresh && systemap check && systemap judgement --strict"
FULL_LOOP_SHARE = 1 / 3


# ---- the two reports -------------------------------------------------------------------


def _label(ref: str, sha: str) -> str:
    short = sha[:7]
    if ref and short and not ref.startswith(short) and ref != sha:
        return f"{ref} ({short})"
    return ref or short


def _counts(d: Delta) -> str:
    modules = "module" if d.changed == 1 else "modules"
    return (
        f"{d.changed} {modules} changed, {d.added} added, {d.removed} removed, {d.moved} "
        f"moved. {len(d.named)} of {d.cards} components specified"
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
        out.append(f"A decision is necessary ({len(d.open)}):")
        out += _lines_taught(d.open, teach, taught)
    if d.quiet:
        out.append(f"No action is necessary for these changes ({len(d.quiet)}):")
        out += _lines_taught(d.quiet, teach, taught)
    out += near_lines(d, teach)
    if d.past_a_third:
        out.append(FULL_LOOP)
    if d.open:
        out.append(f"Do the action for each diagnostic. Then use {NEXT}")
    else:
        out.append("No decision is necessary. The map includes this change. Use systemap refresh.")
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


def _sentence(text: str) -> str:
    """This function starts a text with a capital letter and ends it with one full stop."""
    said = text.strip().rstrip(".")
    return f"{said[0].upper()}{said[1:]}."


def _why_each_kind(lines: list[Line]) -> list[str]:
    """This function gives one explanation for each diagnostic kind in a comment."""
    kinds: list[str] = []
    for line in lines:
        if line.kind not in kinds and explain.lesson(line.kind) is not None:
            kinds.append(line.kind)
    if not kinds:
        return []
    out = ["<details><summary>Diagnostic reasons and actions</summary>", ""]
    for kind in kinds:
        found = explain.lesson(kind)
        assert found is not None
        out += [f"- **{kind}**: {found.why} {found.do}"]
    return [*out, "", "</details>", ""]


def _lines_taught(lines: list[Line], teach: bool, taught: set[str]) -> list[str]:
    """This function gives diagnostic lines and one explanation for each kind."""
    out: list[str] = []
    for line in lines:
        out.append(f"  {line.text}")
        if teach and line.kind not in taught:
            taught.add(line.kind)
            out += explain.rows(line.kind)
    return out


# ---- the pull request comment ---------------------------------------------------------

COMPONENT_GROUPS = (
    (ADDED, "Added"),
    (REMOVED, "Removed"),
    (CHANGED, "Changed claims"),
    (SOURCE, "Changed source"),
)
FLOW_GROUPS = ((ADDED, "Added"), (REMOVED, "Removed"), (CHANGED, "Changed"))
SEQUENCE_GROUPS = (*FLOW_GROUPS, ("", "With a changed step"))
INVARIANT_GROUPS = (*FLOW_GROUPS, ("", "For a changed component"))
# A group names this many items. The rest of the group is a count.
MOST_NAMED = 10


def _module_counts(d: Delta) -> str:
    modules = "module" if d.changed == 1 else "modules"
    return f"{d.changed} {modules} changed, {d.added} added, {d.removed} removed, {d.moved} moved"


def _decision(d: Delta) -> list[str]:
    """This function gives the decision first: the open lines with their actions."""
    if not d.open:
        return ["**No decision is necessary.** The map includes this change.", ""]
    out = [
        f"**A decision is necessary ({len(d.open)}).** Do the action in each line. Then use "
        f"`{NEXT}`.",
        "",
        *[f"- `{line.text}`" for line in d.open],
        "",
        *_why_each_kind(d.open),
    ]
    return out + ([f"> {_sentence(FULL_LOOP)}", ""] if d.past_a_third else [])


def _named(item: Item, code: bool, detail: bool) -> str:
    name = f"`{item.name}`" if code else item.name
    return f"{name} ({', '.join(item.detail)})" if detail and item.detail else name


def _first_named(names: tuple[str, ...]) -> str:
    """This function names the first MOST_NAMED items and counts the other items."""
    if len(names) <= MOST_NAMED:
        return _all_named(names)
    return f"{', '.join(names[:MOST_NAMED])} and {len(names) - MOST_NAMED} more"


def _every(items: tuple[Item, ...], total: int, words: str) -> str:
    """This function gives one sentence if each item of a type has a changed part."""
    touched = sum(1 for item in items if not item.how)
    return f"All {total} {words}." if total > 1 and touched == total else ""


def _row(
    title: str,
    items: tuple[Item, ...],
    groups: tuple[tuple[str, str], ...],
    code: bool = False,
    detail: bool = True,
    every: str = "",
) -> str:
    """This function gives one list row with a group for each type of change.

    The every parameter replaces the list of items with a changed part.
    """
    parts = []
    for how, label in groups:
        named = tuple(_named(i, code, detail) for i in items if i.how == how)
        if named:
            parts.append(every if every and not how else f"{label}: {_first_named(named)}.")
    return f"- **{title}**: {' '.join(parts) or 'No change.'}"


def _rules(change: MapChange) -> list[str]:
    """This function gives the text of each invariant in the invariant row."""
    if not change.invariants:
        return []
    out = ["<details><summary>Invariant text</summary>", ""]
    out += [f"- {item.name}: {item.detail[0]}" for item in change.invariants]
    return [*out, "", "</details>", ""]


def _map_rows(d: Delta, change: MapChange) -> list[str]:
    """This function gives the components, flows, sequences, and invariants that changed."""
    span = f"`{_label(d.base_ref, d.base)}` to `{_label(d.head_ref, d.head)}`"
    out = [f"**Map changes from {span}**: {_module_counts(d)}.", ""]
    if change.error:
        why = change.error.strip().rstrip(".")
        out += [f"The comparison shows only changed source, because {why}.", ""]
    out += [
        _row("Components", change.components, COMPONENT_GROUPS),
        _row("Flows", change.flows, FLOW_GROUPS, code=True),
        _row(
            "Sequences",
            change.sequences,
            SEQUENCE_GROUPS,
            every=_every(change.sequences, change.sequence_count, "sequences have a changed step"),
        ),
        _row(
            "Invariants",
            change.invariants,
            INVARIANT_GROUPS,
            detail=False,
            every=_every(
                change.invariants, change.invariant_count, "invariants are for a changed component"
            ),
        ),
        "",
    ]
    return out + _rules(change)


def _quiet(d: Delta) -> list[str]:
    """This function gives the lines that need no action, in a closed section."""
    if not d.quiet:
        return []
    head = f"No action is necessary for these changes ({len(d.quiet)})"
    out = [f"<details><summary>{head}</summary>", "", *[f"- `{line.text}`" for line in d.quiet]]
    return [*out, "", "</details>", ""]


def _full_map(figure: str, committed: str, head_short: str) -> list[str]:
    """This function gives the committed figure of the full map, if there is one."""
    if figure:
        return [f"The full map at `{head_short}`: [{committed or 'figure'}]({figure})."]
    if committed:
        return [f"The full map at `{head_short}` is in `{committed}`."]
    return []


def markdown(
    d: Delta, change: MapChange | None = None, figure: str = "", committed: str = ""
) -> str:
    """This function formats a pull request comment.

    The change parameter supplies the map comparison. Without it, the comment has no
    map rows and no picture. The figure parameter supplies a URL of the committed full
    map. The committed parameter supplies the path of that figure.
    """
    out = [MARKER, "## What this change does to the map", ""]
    if not d.has_change and not (change and change.model_changed):
        pair = f"`{_label(d.base_ref, d.base)}` and `{_label(d.head_ref, d.head)}`"
        said = "The map has no change." if change else "The map has no source-fact change."
        return "\n".join([*out, f"No module changed between {pair}. {said}", ""])
    out += _decision(d)
    if change is not None:
        out += _map_rows(d, change) + delta_picture.mermaid(change)
    out += _quiet(d)
    out += _full_map(figure, committed, d.head[:7] or d.head_ref)
    return "\n".join([*out, ""])
