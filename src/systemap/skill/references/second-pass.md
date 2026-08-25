# The second pass

The first draft is wrong in ways the checker cannot see. The check refuses
contradictions: a card outside its band, a sentence naming a flow the model
lacks, a module claimed by nobody. It cannot refuse an omission: an edge
the code has and the map does not, a grouping by directory rather than by
purpose, an entry point with no walk through it, a rule the README states
and the model does not carry. The second pass finds those. Expect it to
change the model; a second pass that changes nothing on the first try is
the exception.

## The loop

1. Run `systemap judgement`. Read every line. For each, do one of two
   things: change the model, or write one line saying why not. Never pass
   a line over in silence.

2. Walk every crossing import. The line reads: `module A (component P)
   imports module B (component Q) and no flow joins P and Q`. Open A, find
   the import, and ask what travels or who drives whom. Three outcomes:
   - an edge the reader needs: add a `Flow` with its artifact and kind, and
     its sentence in `relations`;
   - an import the reader does not need on the map (a type imported for an
     annotation, a shared constant): answer the line saying so;
   - a grouping error: A and B belong in the same component, or A is in
     the wrong one; regroup. This is the most common finding.

3. Walk every entry point. The line reads: `entry point X has no journey`.
   Either write the journey (references/journeys-and-invariants.md) or
   answer why this entry point does not matter to a reader.

4. Walk every rule the documents state. Reread the README's principles and
   the design documents with the invariant list beside them. Each rule is
   an invariant with a citation, or a line in your answers saying why not.

5. Look at the rendered figure, `docs/map/figures/system.svg`, and the page
   if you can open it. Look for: a route that passes close to a card it
   does not connect; a label sitting in the wrong gutter; a region holding
   one card (is it a region?); a component whose plain words repeat its
   id; a layer that lights almost nothing (is it a reading?); a journey
   that jumps across the map between steps (a missing step?).

6. Reread every sentence in `relations` from the source side. A sentence
   that could be said of any edge ("A uses B") is not a sentence yet.

7. Run `systemap check`, then `systemap refresh`. Go to 1.

## The stop condition

Stop when all three hold:

- `systemap check` is clean: `coverage: N/N modules mapped` and
  `map layout: clean`, no `stale` line after `refresh`.
- `systemap judgement` is empty, or every remaining line has an answer
  written next to it.
- A full pass through steps 1 to 6 changed nothing in `map/model.py`.

Then hand back (SKILL.md, "What to hand back").
