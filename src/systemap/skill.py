"""What `systemap skill` writes: the agent skill that drafts the model.

The facts are mechanical and `systemap extract` reads them. The meaning
tier (which modules form a component, its plain name, what each edge
means, the layers, the journeys, the invariants) takes judgement. That
judgement is drafted by a coding agent following the skill below and
reviewed by a person, which is why the skill ends by handing back the list
of calls it made. The text is the package's own and is overwritten on every
run, so an upgrade refreshes it.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_DIR = ".claude/skills/systemap"
FILE_NAME = "SKILL.md"

SKILL = """---
name: systemap
description: Draft or refresh a repository's system map model for systemap. Use when asked to map a system, write or update map/model.py, group modules into components, or make `systemap check` pass coverage.
---

# Drafting the map's model

systemap draws a map of a Python system from two inputs. The first is the
facts: which modules exist, what each one exports, which tests import it.
`systemap extract` reads those out of the code, and nothing you write
changes them. The second is the model: which modules together make one
thing a reader would point at and name, what that thing is for, what moves
between things, and what each connection means. That takes judgement, and
it is your job here. You draft it; the maintainer reviews every judgement
call before it is trusted.

The model is a Python module (by default `map/model.py`) exporting two
values, `MODEL` and `MEANING`, built from the dataclasses `systemap`
exports. If the file does not exist, run `systemap init` first: it writes
a small starter you can read for the shape, and `systemap.toml` beside it.

## The workflow, in order

1. Run `systemap extract` and read the facts file it names (by default
   `docs/map/map.json`). Every module in it must end up claimed by exactly
   one component, so that list is your checklist.

2. Read the repository's own words before you invent any: the README,
   the design documents, any roadmap. Use its vocabulary for names, and
   note every rule it states about itself; those become invariants later.

3. Group the modules into components. A component is something a reader
   would point at and name: "the part that reads input", "the ledger".
   Each `Component` carries:
   - `does`: what it is for, in plain words, one or two sentences.
   - `interface`: how other parts reach it, as one line (a signature, a
     file it writes, a command).
   - `implemented_by`: the modules that are it. Name a module exactly, or
     a package followed by `.*` to claim the package and everything
     beneath it. Each module belongs to one component only.
   - `entry`: one real public function or class from those modules. The
     build state (built, partial, planned) is derived by looking that name
     up in the facts, so it must exist in the code.
   - `kind`: `component` for a thing that does work, `store` for a thing
     that holds state, `actor` for a person or a system outside the code.
   Describe what the component does for the system. Its size is not a
   description: no counts of lines, files or tests anywhere in the model.

4. Write the flows. A `Flow` is one artifact moving from one component to
   another (a request, a record, a signal), with a `kind` that says what
   sort of movement it is. Every kind you use is listed in `flow_kinds`
   and mapped to a layer in the next step.

5. Write the layers. A layer is one reading of the map, and it is best
   written as the question a reader asks: what does the work, what
   measures it, what feeds back, where do I stand, what earns trust, what
   learns, what is recorded. Use the ones the repository's own vocabulary
   supports; a small system may have two. Map each flow kind to a layer in
   `layer_of_kind`, and move a single edge with `layer_overrides` when its
   kind's layer is the wrong reading for it. Then give every component a
   plain name in `plain`: the words a newcomer would use for it.

6. For every edge, write one sentence in `relations` saying what the
   source is to the target, read from the source side. Give each layer a
   verb pair in `verbs`: the verb printed when the reader clicks the
   source ("hands to") and the one printed when they click the target
   ("receives from"). Use `verb_overrides` when one edge needs its own
   pair.

7. Write journeys: a few ordered walks through the map that a reader can
   step through one edge at a time. Good ones are a change from spec to
   merge; a failure and its retry; the operator steering. Each `Step`
   names what acts, what measures, the edge it traces, and one sentence
   saying what happens there.

8. Copy invariants from the repository's own rules, with the source (file
   and line, or the document heading) in the text so a reader can check
   it. Name the components each rule governs. A rule the repository did
   not state is not an invariant; it is a proposal, and belongs in your
   list for the maintainer.

9. A planned component, one whose code has not landed, carries the
   tracker item that will build it in `tracker` (an issue number, a
   roadmap id) and no invented `entry`. Leave `entry` empty until the code
   exists; the map draws the card as a ghost until then.

10. Run `systemap check` and fix what it names until coverage reads N/N
    and the layout passes. Positions are hand-placed: `x` and `y` per
    card on a grid, cards 150 wide. The check decides whether the
    placement is clean (every card in its band, no two overlapping, no
    edge through a card it does not connect). Move cards until it passes.
    If a module genuinely has no place on the map (a `__main__` shim, a
    vendored file), add it to `[coverage] ignore` in `systemap.toml` with
    a reason, and list it for the maintainer.

11. Return to the maintainer the list of judgement calls: groupings that
    could go another way, edges you inferred from imports rather than read
    in the documents, invariants whose source you are unsure of, and every
    ignore you added. A person confirms each one before the map is
    trusted.

## Rules

- No code or test counts anywhere. The map explains what the system does,
  not how much code it has.
- The map explains the system, not the code: a reader should understand
  what happens without opening a file.
- Every planned item names its tracker.
- Prose is for emphasis only. The relationships live on the edges: one
  sentence per flow, one verb per direction. If something matters, it is
  an edge, not a paragraph.
- Positions are hand-placed and the layout check decides. Run
  `systemap check` after every move.
"""


def write(directory: Path) -> Path:
    """Write SKILL.md into `directory`, creating it, and return the file's path."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / FILE_NAME
    path.write_text(SKILL, encoding="utf-8")
    return path
