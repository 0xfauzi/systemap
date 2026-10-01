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
   Exit 0 when nothing needs a decision; exit 1 while a line does.
   With `TYPESAFE_API_KEY` set, `delta --base <ref>` also pairs a
   module renamed and rewritten at once (a `moved:` line that says Jev
   read them as one, with its confidence; read both files before
   renaming the claim) and names the card each unclaimed module reads
   like (`jev owner: ...`); the claim is still yours to write.
2. Act only on the lines under `needs a decision`, in `map/model.py` and
   `systemap.toml`. Do not redraw the map, regroup cards the lines do not
   name, or move a card by hand; a card added for a new module is
   placed by `systemap place` into a free slot of its region, and when
   the region has none, `systemap place --all` lays every card out
   again, keeping the ones marked `pinned=True`.
   Adding or removing a claimed module also reopens source review, including
   a module matched by an `implemented_by` wildcard. For a `source review`
   line, read the changed modules and check the card's description, interface,
   flows, journeys and invariants. Correct any claim
   that no longer holds. Then compute its current digest and write it as the
   card's `source_review` value. This command prints digests for every card:

   ```sh
   uv run python - <<'PY'
   from pathlib import Path
   from systemap import card_review, config, extract, nest

   cfg = config.load(Path.cwd())
   facts = extract.build(cfg)
   for current_map in nest.load(cfg).maps:
       for card in current_map.model.components:
           if card.implemented_by:
               print(current_map.id, card.id, card_review.digest(card, current_map.model, current_map.meaning, facts))
   PY
   ```

   A missing or unparsable claimed module prints `None`: repair extraction
   before recording a review. A later source or claim change reopens the line.
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
the hand-back, with the step that used them.

## The lines

| line | what it says | what to do |
|---|---|---|
| `moved: A -> B (same content)`, or `(same public names)` | a module is at a new path | rename it in the named card's `implemented_by`; when no card claims the new path, name it in the card it serves |
| `added: M, claimed by CARD` | a new module a `pkg.*` pattern already claims | nothing |
| `added: M, claimed by no card` | a new module with no place on the map: coverage lost | name it in the card it serves, or ignore it with a reason under `[coverage]` |
| `removed: M; CARD names it` | a module is gone and a card still names it | drop it from `implemented_by`; a card left with no module goes too, with its flows and sentences |
| `removed: M; the [coverage] ignore that names it is stale` | the module went and the ignore stayed | remove the ignore |
| `entry vanished` | the card's `entry` is no longer defined by its modules | set `entry` to a public name they define |
| `interface vanished` | the name the interface line starts with is gone | start the line with a name they define, or leave it empty |
| `new crossing import` | an import now crosses a card boundary and no flow joins the two cards | add the flow with its sentence, or answer it under `[judgement] answered`, as in the second pass |
| `evidence lost` | a reviewed flow no longer has structural support | review the changed source and revise or renew the flow claim |
| `source evidence lost` | a reviewed flow falls back to structural or external evidence | review its source references, direction and artifact, then renew the review |
| `structural evidence lost` | an import or declared mechanism behind a flow disappeared | review the flow against current source |
| `source review` | claimed modules or parsed code changed and the card's current review digest is absent or stale | review its description, interface, flows, journeys and invariants, then record `source_review` |
| `move candidate` | removed and added modules share public names without enough identity evidence | compare their source before treating either as a move |

A line under `changed, nothing to do` is on record and needs no decision; a
`removed` module that a pattern claimed, or an added module a pattern
claims, is such a line. Its card can still have a separate `source review`
line because the set of claimed modules changed.

## The sentence

An agent given a mapped repository after a change is told:

> The code changed. Update the map with systemap: follow the systemap
> skill's maintenance path, with base <ref>.

## Before the work: project it onto the map

With `TYPESAFE_API_KEY` set, say what you are about to do before you do it:

    systemap plan "make the reader stream its input instead of buffering it"

Jev reads the task against every card's purpose and names the cards the work
will most likely change; around each, the map prints the flows, walks and
rules it sits in. Read those before writing code: a rule that governs the
card, or a journey that passes through it, is what the work usually breaks.
The projection is written under `.systemap/plans/`, and when the work is
done, `systemap plan --check <id> --base <ref>` names every card that changed
and was not projected. That is not a failure; it is where the system did
something the plan did not see, and it is worth a sentence in the pull
request.

The cut is measured: over 80 real bug reports the projection covered 86% of
the cards their fix touched while naming 2.1 cards, and 71% on a repository
no threshold was chosen on (`bench/jev`).

## In a pull request

The workflow `systemap init` writes runs `delta --base <the base commit>
--format markdown` on every pull request and posts the report as one
comment, updated in place on every push, with the committed map at the
head commit under the lines. The job fails while a line needs a decision and
the comment names each fix, so the map is maintained in the pull request
that changed the code, not after it.

## What to hand back

The `delta` header (modules changed, cards named), each line acted on and
how, the coverage line from `systemap check`, the last line of `systemap
judgement --strict`, and the turn count against the budget.
