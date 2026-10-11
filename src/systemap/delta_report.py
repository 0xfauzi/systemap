"""The report generator formats map changes as text or Markdown."""

from __future__ import annotations

from typing import TYPE_CHECKING

from systemap import explain

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
    return (
        f"{d.changed} modules changed, {d.added} added, {d.removed} removed, {d.moved} "
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
        return [f"delta: no module changed between {pair}. the map has no source-fact change"]
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


def _near_markdown(d: Delta) -> list[str]:
    """This function formats the connected-component context for a pull request comment."""
    lines = near_lines(d, teach=False)
    if not lines:
        return []
    said = lines[1].strip()
    return ["**Components connected to the change**", "", f"{said[0].upper()}{said[1:]}.", ""]


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


def _figure_lines(figure: str, committed: str, head_short: str, base_short: str) -> list[str]:
    """This function gives the figure image, or the reason that the comment has none."""
    command = (
        f"The change map command is `systemap figure --mode change --base {base_short} "
        f"--out change.svg`."
    )
    if figure:
        return [
            f"![the map at {head_short}]({figure})",
            "",
            f"The committed map at `{head_short}`. {command}",
        ]
    if committed:
        return [
            f"The map figure `{committed}` is committed at `{head_short}`. The comment shows "
            f"no image because the origin remote is not on GitHub. {command}"
        ]
    return [f"No committed figure is available at `{head_short}`. {command}"]


def markdown(d: Delta, figure: str = "", committed: str = "") -> str:
    """This function formats a pull request comment.

    The figure parameter supplies a committed map URL. The committed parameter supplies
    the path of a committed figure that has no URL.
    """
    span = f"`{_label(d.base_ref, d.base)}` to `{_label(d.head_ref, d.head)}`"
    out = [MARKER, "## What this change does to the map", ""]
    if not d.has_change:
        out += [
            (
                f"No module changed between {span.replace(' to ', ' and ')}. the map has no "
                f"source-fact change."
            ),
            "",
        ]
        return "\n".join(out)
    out += [f"{span}: {_counts(d)}.", ""]
    if d.open:
        out += [f"**A decision is necessary ({len(d.open)})**", ""]
        out += [f"- `{line.text}`" for line in d.open]
        out += ["", *_why_each_kind(d.open)]
    if d.quiet:
        out += [f"**No action is necessary for these changes ({len(d.quiet)})**", ""]
        out += [f"- `{line.text}`" for line in d.quiet]
        out.append("")
    out += _near_markdown(d)
    if d.past_a_third:
        out += [f"> {FULL_LOOP[0].upper()}{FULL_LOOP[1:]}.", ""]
    head_short = d.head[:7] or d.head_ref
    base_short = d.base[:7] or d.base_ref
    out += _figure_lines(figure, committed, head_short, base_short)
    if d.open:
        out.append(f"Do the action for each diagnostic. Then use `{NEXT}`.")
    else:
        out.append(
            "No decision is necessary. The map includes this change. Use `systemap "
            "refresh` to update the facts."
        )
    out.append("")
    return "\n".join(out)
