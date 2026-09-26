"""What each line means, why it matters, and what to do: the teaching under the report.

A line systemap prints is short, so that it can be answered word for word
and so a long report stays readable. Short is not the same as clear. Under
each line, these three sentences say what was found, why it matters to
someone keeping an accurate view of the system, and what to do next.

The line itself never changes here. It is the name of the finding: the
maintainer quotes it in `[judgement] answered`, and some are read back by
code. This module adds to it and replaces nothing.

`systemap explain <kind>` prints one entry whole. Every command that prints
lines prints the `why` and the `do` under each one, and `--brief` leaves
them out for someone who already knows them.
"""

from __future__ import annotations

from dataclasses import dataclass

INDENT = "      "


@dataclass(frozen=True)
class Lesson:
    """One kind of line, taught: what it is, why it matters, what to do."""

    means: str
    why: str
    do: str

    def rows(self, indent: str = INDENT) -> list[str]:
        return [f"{indent}why: {self.why}", f"{indent}do:  {self.do}"]


# ---- the lines `systemap judgement` prints ----------------------------------------

JUDGEMENT = {
    "single module": Lesson(
        means="A card claims one module, so the card and the file say the same thing.",
        why=(
            "A card per file tells a reader nothing the file tree does not already tell "
            "them, and the map then grows as fast as the code does."
        ),
        do=(
            "Keep the card if a reader would point at it and name it on its own. Otherwise fold "
            "the module into the card whose job it serves."
        ),
    ),
    "possible mis-fold": Lesson(
        means=(
            "A module sits in a card that shares no word with it, and none of that card's other "
            "modules is in its package."
        ),
        why=(
            "A card is a promise that its modules do one job. A module that does another job "
            "hides inside that promise, and the next reader trusts the card instead of the code."
        ),
        do=(
            "Read the module and move it to the card whose job it carries out, or answer why it "
            "belongs where it is, so the next run does not ask again."
        ),
    ),
    "no sentence": Lesson(
        means="A flow is drawn between two cards, but nothing says what it means.",
        why=(
            "An arrow on its own tells a reader that two parts touch, not what passes between "
            "them. The sentence is where the map stops being a diagram and starts explaining."
        ),
        do=(
            "Write one sentence from the sending side, naming what travels and why the receiving "
            "card needs it."
        ),
    ),
    "thin layer": Lesson(
        means="A layer of the map holds fewer than two cards, so it shows almost nothing.",
        why=(
            "A layer is a promise that the system can be looked at that way. A layer with one "
            "card in it makes that promise and does not keep it."
        ),
        do=(
            "Add the flows that layer is for, or answer that this system does not have that "
            "view, which is itself worth knowing."
        ),
    ),
    "entry point": Lesson(
        means="Something can start a run here, and no journey walks from it.",
        why=(
            "An entry point is where a person or another system meets yours. If no journey walks "
            "from it, the map cannot answer the first question a newcomer asks: what happens when "
            "I do this?"
        ),
        do=(
            "Write the journey, step by step, from the entry point to where the result lands. Or "
            "answer why this way in does not matter to a reader."
        ),
    ),
    "journey start": Lesson(
        means="A journey says it starts at a way in the facts do not have.",
        why=(
            "The point of naming the way in is that the map can say which ways in are walked "
            "and which are not. A name nothing matches leaves a real way in looking covered."
        ),
        do=(
            "Name the way in as the facts name it (`systemap facts --entry-points` lists them), "
            "or leave `starts` empty."
        ),
    ),
    "drafted journey": Lesson(
        means="`systemap journeys` wrote this walk, and nobody has read it yet.",
        why=(
            "An agent read the code and wrote what it found. It is a draft, and a draft that "
            "nobody checks is how a map starts saying things its maintainer never agreed to."
        ),
        do=(
            "Walk it against the code. Fix what is wrong, then set `drafted=False` on it, or "
            "answer the line with what you checked."
        ),
    ),
    "crossing import": Lesson(
        means=(
            "Modules of one card import modules of another, and no flow on the map joins those "
            "two cards."
        ),
        why=(
            "The code has a connection the map does not show. Every reader who trusts the map "
            "will be "
            "surprised by it, and every change that follows it will look unrelated."
        ),
        do=(
            "Draw the flow and write its sentence, regroup the modules if the two cards are "
            "really one, or answer that the import carries nothing a reader needs."
        ),
    ),
    "declared flow": Lesson(
        means=(
            "A flow is drawn that no import backs, and its sentence names no mechanism that "
            "would carry it."
        ),
        why=(
            "A map that draws connections it has no evidence for is asking to be believed. "
            "Once one edge is unsupported, a reader cannot tell which of the others are real."
        ),
        do=(
            "Find the code that carries it, or name the mechanism (a queue, a file, a "
            "subprocess) in the sentence and list it under `[flows] observed_by`. If neither "
            "exists, remove the flow."
        ),
    ),
    "model sdk": Lesson(
        means="A module calls a model SDK, and its card is not marked as one that calls a model.",
        why=(
            "Where a system calls a model is the thing a reader most wants marked. Unmarked, "
            "the cost, the latency and the failure mode of that call are invisible on the map."
        ),
        do=(
            "Make the card an agent or set `calls_model`, draw the flow to the model, or answer "
            "citing the rule your repository follows."
        ),
    ),
    "unknown surface": Lesson(
        means=(
            "The TypeScript reader found a module or package target it could not map with "
            "confidence."
        ),
        why=(
            "If an unreadable export or import is treated as absent, the facts hide a real part "
            "of the public surface or its connections."
        ),
        do=(
            "Read the source excerpt. Add support for its syntax, or narrow the configured source "
            "roots when the file is not part of the application."
        ),
    ),
}

# ---- the lines `systemap delta` prints --------------------------------------------

DELTA = {
    "moved": Lesson(
        means="A module is at a new path, and systemap worked out which old module it was.",
        why=(
            "A card that still names the old path claims a module that no longer exists, so the "
            "map quietly stops covering that code."
        ),
        do="Rename the claim in the model, or claim the new module in the card it now belongs to.",
    ),
    "added": Lesson(
        means="A module is new since the base commit.",
        why=(
            "A module no card claims is a part of the system the map does not show. It is how "
            "a map stops being complete, and a map that is nearly complete is one a reader has "
            "to check."
        ),
        do=(
            "Name it in the card whose job it carries out, or ignore it with a reason under "
            "`[coverage]`."
        ),
    ),
    "removed": Lesson(
        means="A module the map names is gone from the tree.",
        why=(
            "A claim on code that no longer exists makes the card look bigger than it is, and "
            "the coverage count stops meaning anything."
        ),
        do="Drop the claim from the card, or remove the card if its job left with the module.",
    ),
    "next to the change": Lesson(
        means=(
            "The cards one flow away from the card this change landed in most, whichever way "
            "the artifact travels."
        ),
        why=(
            "A diff shows the code that changed. It does not show what sits against it, and "
            "the parts that break are usually the ones that already exchanged something with "
            "it. This "
            "is the short version of that question: 6 cards at the median over 359 pull "
            "requests, holding a card the change really touched in 72% of them."
        ),
        do=(
            "Read it as context, not as a warning. If something is wrong after this change, "
            "look here first; if nothing is, there is nothing to do."
        ),
    ),
    "entry vanished": Lesson(
        means="A card names an entry that its modules no longer define.",
        why=(
            "The entry is the one public name a reader is told to start from. When it is gone, "
            "the card sends every newcomer to a name that is not there."
        ),
        do="Set the entry to a public name the card's modules define today.",
    ),
    "interface vanished": Lesson(
        means="A card names an interface its modules no longer define.",
        why=(
            "The interface is what other parts are promised. A promise the code dropped is worse "
            "than no promise, because callers still believe it."
        ),
        do="Point the interface at what the card offers now, or drop it if it offers nothing.",
    ),
    "new crossing import": Lesson(
        means="This change added an import across a card boundary that no flow joins.",
        why=(
            "This is the moment an architecture changes: two parts that did not depend on each "
            "other now do. Decided here, it is a design choice; found later, it is a surprise."
        ),
        do=(
            "Draw the flow with its sentence if the connection is meant, move the code if it is "
            "not, or answer that it carries nothing a reader needs."
        ),
    ),
    "evidence lost": Lesson(
        means="A flow that an import used to back has no import behind it any more.",
        why=(
            "Either the connection is gone and the map is now drawing something that does not "
            "happen, or it moved to a mechanism the map cannot see."
        ),
        do=(
            "Remove the flow, or name the mechanism that carries it now in its sentence and "
            "under `[flows] observed_by`."
        ),
    ),
}

# ---- the lines `systemap audit` prints, from Jev's answers ------------------------

AUDIT = {
    "jev mis-fold": Lesson(
        means="Jev answers that this module does the job of a different card.",
        why=(
            "The word rule behind `possible mis-fold` only sees names. Jev read the code, so it "
            "catches a module that was folded in by habit rather than by purpose."
        ),
        do=(
            "Read the module against both cards and move it, or answer why it belongs. It is a "
            "question, not a verdict."
        ),
    ),
    "jev owner": Lesson(
        means="No card claims this module, and Jev says which card it reads like.",
        why="Until it is claimed, part of the system is missing from the view the map gives.",
        do=(
            "Claim it in the card named, or in one of the closest three, or ignore it with "
            "a reason."
        ),
    ),
    "jev sentence": Lesson(
        means="Jev answers that the card's sentence probably does not describe its modules.",
        why=(
            "The sentence is what a reader believes without opening the code. A sentence that "
            "drifted from its modules teaches them something untrue."
        ),
        do="Reread the modules and rewrite the sentence, or answer why it still holds.",
    ),
    "jev flow": Lesson(
        means=(
            "Jev answers that the code where these two cards meet probably does not carry "
            "what the flow claims."
        ),
        why=(
            "An edge that the code does not carry is a connection the reader will look for and "
            "not find."
        ),
        do=(
            "Find the call that carries it. A call made through an instance is not in Jev's "
            "evidence, so a real flow can be doubted for that alone: answer it when that is why."
        ),
    ),
    "jev governs": Lesson(
        means="Jev answers that this rule governs a card the rule does not name.",
        why=(
            "A rule lists the cards whose code must keep it true. A card missing from that list "
            "can break the rule with nobody warned."
        ),
        do=(
            "Add the card to the rule's `governs` when a change to it could break the rule, "
            "or answer why it cannot."
        ),
    ),
}

# ---- what `systemap check` refuses -------------------------------------------------

CHECK = {
    "coverage": Lesson(
        means="Some module is claimed by no card, or by two.",
        why=(
            "Coverage is what lets the map say `this is the system` rather than `this is some of "
            "it`. A module claimed twice makes two cards look bigger than they are."
        ),
        do=(
            "Claim every module once, or ignore it with a reason under `[coverage]` in "
            "`systemap.toml`."
        ),
    ),
    "map layout": Lesson(
        means="A card, label, region or route breaks a rule the drawing has to keep.",
        why=(
            "The picture is read at a glance. Text too small to read, or an edge crossing a "
            "region it has nothing to do with, teaches the wrong thing before any caption can "
            "correct it."
        ),
        do="Run `systemap place` after adding or removing a card, then fix what the check names.",
    ),
    "map routes": Lesson(
        means="An edge is drawn through a card it does not connect, or across a region it does "
        "not belong to.",
        why=(
            "A reader follows a line with their eye. A line that passes through a card suggests "
            "a relationship that is not there."
        ),
        do=(
            "Give the routes room: move a card, or let `systemap place --all` lay the map "
            "out again."
        ),
    ),
    "nesting": Lesson(
        means="A map inside a card does not claim exactly that card's modules.",
        why=(
            "The map inside a card is a promise that the card is the whole of what is below it. "
            "If they differ, two maps describe the same code differently."
        ),
        do="Claim exactly the card's modules in the sub-map, and make its actors the cards around.",
    ),
    "entry": Lesson(
        means="A card names an entry its modules do not define.",
        why="The entry is where a reader starts reading the card; it has to exist.",
        do="Name a public name one of the card's modules defines.",
    ),
    "interface": Lesson(
        means="A card names an interface its modules do not define.",
        why="The interface is what the card promises other parts; it has to exist.",
        do="Name what the card's modules offer today.",
    ),
    "stale": Lesson(
        means="The rendered page or the facts no longer match the model or the tree.",
        why="A map that is not rebuilt describes the code as it was, not as it is.",
        do="Run `systemap refresh`, then commit the output directory.",
    ),
}

LESSONS: dict[str, Lesson] = {**JUDGEMENT, **DELTA, **AUDIT, **CHECK}


def lesson(kind: str) -> Lesson | None:
    return LESSONS.get(kind)


def rows(kind: str, indent: str = INDENT) -> list[str]:
    """The `why` and `do` rows for a kind; nothing when the kind is not taught here."""
    found = LESSONS.get(kind)
    return found.rows(indent) if found else []


def whole(kind: str) -> list[str]:
    """One entry as `systemap explain` prints it."""
    found = LESSONS.get(kind)
    if found is None:
        known = ", ".join(sorted(LESSONS))
        return [f"explain: there is no line kind called {kind!r}.", f"  the kinds are: {known}"]
    return [
        f"{kind}",
        f"  what it means: {found.means}",
        f"  why it matters: {found.why}",
        f"  what to do:     {found.do}",
    ]
