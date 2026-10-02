"""Text and Markdown rendering for a computed change report."""

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
        f"{d.changed} modules changed, {d.added} added, {d.removed} removed, {d.moved} moved; "
        f"{len(d.named)} of {d.cards} cards named"
    )


FULL_LOOP = (
    "more than a third of the cards are named: the skill says to run the full loop "
    "instead of acting line by line"
)


def report(d: Delta, teach: bool = True) -> list[str]:
    """The lines the CLI prints: the header, each group, and what to run.

    `teach` says why each kind of line matters and what to do, once under
    the first line of that kind; `--brief` turns it off."""
    span = f"{_label(d.base_ref, d.base)} -> {_label(d.head_ref, d.head)}"
    if not d.has_change:
        pair = f"{_label(d.base_ref, d.base)} and {_label(d.head_ref, d.head)}"
        return [f"delta: no module changed between {pair}; the map is unaffected"]
    out = [f"delta: {span}: {_counts(d)}"]
    # One report teaches a kind once, whichever group it first appears in.
    taught: set[str] = set()
    if d.open:
        out.append(f"needs a decision ({len(d.open)}):")
        out += _lines_taught(d.open, teach, taught)
    if d.quiet:
        out.append(f"changed, nothing to do ({len(d.quiet)}):")
        out += _lines_taught(d.quiet, teach, taught)
    out += near_lines(d, teach)
    if d.past_a_third:
        out.append(FULL_LOOP)
    if d.open:
        out.append(f"act on each line above, then run: {NEXT}")
    else:
        out.append("nothing to decide: the map already covers this change. run: systemap refresh")
    return out


def near_lines(d: Delta, teach: bool = True) -> list[str]:
    """The cards beside the change, which is context and not a finding.

    It is printed even when nothing needs a decision, because the question it
    answers ("what sits against what I changed") is asked most often then.
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
            f"  {d.seed} holds most of what changed, and a flow joins it to "
            f"{len(d.near)} of the {d.cards} cards, so naming them would say nothing",
        ]
    out = [
        "next to the change:",
        f"  {d.seed} holds most of what changed; one flow away sit {_all_named(d.near)}",
    ]
    return out + (explain.rows("next to the change") if teach else [])


def _all_named(cards: tuple[str, ...]) -> str:
    """The cards as a sentence ends them: all of them, however many there are."""
    if len(cards) == 1:
        return cards[0]
    return ", ".join(cards[:-1]) + f" and {cards[-1]}"


def _near_markdown(d: Delta) -> list[str]:
    """The same neighbourhood, in a pull-request comment, said once."""
    lines = near_lines(d, teach=False)
    if not lines:
        return []
    said = lines[1].strip()
    return ["**Next to the change**", "", f"{said[0].upper()}{said[1:]}.", ""]


def _why_each_kind(lines: list[Line]) -> list[str]:
    """In a pull-request comment the teaching is said once per kind, under the
    group, so a comment with a dozen lines does not repeat itself a dozen times."""
    kinds: list[str] = []
    for line in lines:
        if line.kind not in kinds and explain.lesson(line.kind) is not None:
            kinds.append(line.kind)
    if not kinds:
        return []
    out = ["<details><summary>Why these matter, and what to do</summary>", ""]
    for kind in kinds:
        found = explain.lesson(kind)
        assert found is not None
        out += [f"- **{kind}**: {found.why} {found.do}"]
    return [*out, "", "</details>", ""]


def _lines_taught(lines: list[Line], teach: bool, taught: set[str]) -> list[str]:
    """Each line, with its kind taught once under the first line of that kind."""
    out: list[str] = []
    for line in lines:
        out.append(f"  {line.text}")
        if teach and line.kind not in taught:
            taught.add(line.kind)
            out += explain.rows(line.kind)
    return out


def markdown(d: Delta, figure: str = "") -> str:
    """The same report as a pull-request comment; `figure` is the committed map's URL."""
    span = f"`{_label(d.base_ref, d.base)}` to `{_label(d.head_ref, d.head)}`"
    out = [MARKER, "## What this change does to the map", ""]
    if not d.has_change:
        out += [
            f"No module changed between {span.replace(' to ', ' and ')}; the map is unaffected.",
            "",
        ]
        return "\n".join(out)
    out += [f"{span}: {_counts(d)}.", ""]
    if d.open:
        out += [f"**Needs a decision ({len(d.open)})**", ""]
        out += [f"- `{line.text}`" for line in d.open]
        out += ["", *_why_each_kind(d.open)]
    if d.quiet:
        out += [f"**Changed, nothing to do ({len(d.quiet)})**", ""]
        out += [f"- `{line.text}`" for line in d.quiet]
        out.append("")
    out += _near_markdown(d)
    if d.past_a_third:
        out += [f"> {FULL_LOOP[0].upper()}{FULL_LOOP[1:]}.", ""]
    head_short = d.head[:7] or d.head_ref
    base_short = d.base[:7] or d.base_ref
    if figure:
        out += [f"![the map at {head_short}]({figure})", ""]
        out.append(
            f"The committed map at `{head_short}`; the change map itself is "
            f"`systemap figure --mode change --base {base_short} --out change.svg`."
        )
    else:
        out.append(
            f"No committed figure to show at `{head_short}`; the change map is "
            f"`systemap figure --mode change --base {base_short} --out change.svg`."
        )
    if d.open:
        out.append(f"Act on each line, then run `{NEXT}`.")
    else:
        out.append(
            "Nothing to decide: the map already covers this change. "
            "`systemap refresh` brings the facts up to date."
        )
    out.append("")
    return "\n".join(out)
