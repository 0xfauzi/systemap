# When the code changed

A map exists, the check passed, and then a pull request moved the code.
The first-draft loop is the wrong tool for that: it redraws the map at
first-draft cost to absorb a change that touched two cards. This path acts
on the change alone.

## The path

1. `systemap delta --base <ref>`. In a pull request the ref is the base
   branch (`main`); otherwise the commit the map was last refreshed at
   (`built_at_commit` in the facts file). The facts at both commits are
   read out of git, never from the working copy, and compared in the
   map's terms: one line per thing the change did, each naming its fix.
   Exit 0 when nothing needs a person; exit 1 while a line does.
2. Act only on the lines under `needs a person`, in `map/model.py` and
   `systemap.toml`. Do not redraw the map, regroup cards the lines do not
   name, or move a card by hand; a card added for a new module is
   placed by `systemap place` into a free slot of its region, and when
   the region has none, `systemap place --all` lays every card out
   again, keeping the ones marked `pinned=True`.
3. `systemap refresh`, then `systemap check && systemap judgement --strict`.
   The refresh brings the facts, the page and the figures up to date; the
   check refuses what is still wrong; the judgement asks about the edges
   the change opened. Act on those lines as in the first-draft loop (a
   change to the model, or an answer under `[judgement] answered`) and
   run the three again until every one exits 0.
4. When `delta` names more than about a third of the cards, its report
   says so. That change is a redesign, not maintenance: say so in the
   hand-back and run the full loop in SKILL.md instead, from its step 1.

Budget: 15 turns for a small or a medium change. An overrun is named in
the hand-back, with the step that ate it.

## The lines

| line | what it says | what to do |
|---|---|---|
| `moved: A -> B (same content)`, or `(same public names)` | a module is at a new path | rename it in the named card's `implemented_by`; when no card claims the new path, name it in the card it serves |
| `added: M, claimed by CARD` | a new module a `pkg.*` pattern already claims | nothing |
| `added: M, claimed by no card` | a new module with no place on the map: coverage lost | name it in the card it serves, or ignore it with a reason under `[coverage]` |
| `removed: M; CARD names it` | a module is gone and a card still names it | drop it from `implemented_by`; a card left with no module goes too, with its flows and sentences |
| `removed: M; the [coverage] ignore that names it is stale` | the ignore outlived the module | remove the ignore |
| `entry vanished` | the card's `entry` is no longer defined by its modules | set `entry` to a public name they define |
| `interface vanished` | the name the interface line starts with is gone | start the line with a name they define, or leave it empty |
| `new crossing import` | an import now crosses a card boundary and no flow joins the two cards | add the flow with its sentence, or answer it under `[judgement] answered`, as in the second pass |
| `evidence lost` | a flow an import backed is backed by nothing now | find the evidence, name the mechanism in the sentence, or remove the flow, as for a `declared flow` line |

A line under `changed, nothing to do` is on record and needs nobody; a
`removed` module that a pattern claimed, or an added module a pattern
claims, is such a line.

## The sentence

An agent given a mapped repository after a change is told:

> The code changed. Update the map with systemap: follow the systemap
> skill's maintenance path, with base <ref>.

## In a pull request

The workflow `systemap init` writes runs `delta --base <the base commit>
--format markdown` on every pull request and posts the report as one
comment, updated in place on every push, with the committed map at the
head commit under the lines. The job fails while a line needs a person and
the comment names each fix, so the map is maintained in the pull request
that changed the code, not after it.

## What to hand back

The `delta` header (modules changed, cards named), each line acted on and
how, the coverage line from `systemap check`, the last line of `systemap
judgement --strict`, and the turn count against the budget.
