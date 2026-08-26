# The second pass

The first draft is wrong in ways the checker cannot see. The check refuses
contradictions: a card outside its band, a sentence naming a flow the model
lacks, a module claimed by nobody. It cannot refuse an omission: an edge
the code has and the map does not, an edge the map has and the code does
not, a grouping by directory rather than by
purpose, an entry point with no walk through it, a rule the README states
and the model does not carry. The second pass finds those. Expect it to
change the model; a second pass that changes nothing on the first try is
the exception.

## The loop

1. Run `systemap judgement`. Read every line. For each, do one of two
   things: change the model, or answer it in `[judgement] answered` in
   `systemap.toml` with a reason. An answered line is suppressed and
   counted in the header; an answer that matches no line is reported as
   stale, so remove it. Never pass a line over in silence. Seven forms,
   each one table with one reason, one row each below:

   ```toml
   [judgement]
   answered = [
       # item: the exact line as printed (here a declared flow that is real and joined by nothing in the tree)
       { item = "declared flow: Gateway -> Renderer (render job): no import joins them; find the evidence, name the mechanism in the sentence, or remove it", reason = "the job crosses to the render container as an HTTP request; the client is generated at build time and is not in the tree" },
       # items: several exact lines, one reason
       { items = ["single module: Reader is only pkg.reader", "single module: Writer is only pkg.writer"], reason = "two real parts of a two-file package" },
       # crossing: every crossing-import line between any two of these components, either direction
       { crossing = ["Page", "Figures", "Describe"], reason = "the three drawers share the schematic's tables; every pair among them" },
       # crossing_into: every crossing import into one component, whoever imports it
       { crossing_into = "Model", reason = "every part imports the schema for its type names; the model itself reaches each through the edge the map draws" },
       # crossing_from: every crossing import out of one component, whatever it imports
       { crossing_from = "CLI", reason = "the commands import every part they run; the control edges are the ones the map draws" },
       # kind: every line of one kind (single module, possible mis-fold, no sentence,
       # thin layer, entry point, crossing import, declared flow, model sdk)
       { kind = "single module", reason = "a small package with one module per part; each card is a thing a reader would name" },
       # module_sdk: every model sdk line for one import
       { module_sdk = "google.adk", reason = "the framework's tool and session modules import it too; the agents are the cards of kind agent" },
   ]
   ```

   The list can run past what one tool call shows. `systemap judgement
   --kind "crossing import"` prints one kind at a time (the head still
   counts every open line, and `--strict` reads them all).

2. Walk every crossing import. The line reads: `crossing import: P
   imports Q in N modules and no flow joins them`, one line per ordered
   pair of cards; `systemap judgement --verbose` lists the imports under
   it (`module A imports module B`). Open A, find the import, and ask
   what travels or who drives whom. Three outcomes:
   - an edge the reader needs: add a `Flow` with its artifact and kind, and
     its sentence in `relations`;
   - an import the reader does not need on the map (a type imported for an
     annotation, a shared constant): answer the line in the configuration
     saying so;
   - a grouping error: A and B belong in the same component, or A is in
     the wrong one; regroup. This is the most common finding.

3. Walk every declared flow. The line reads: `declared flow: P -> Q
   (artifact): no import joins them`. The map claims an edge the facts
   do not back: no module of P imports a module of Q or the other way
   round, and neither the sentence nor the artifact names a mechanism
   listed under `[flows] observed_by`. Four outcomes:
   - the import is there and the claims are wrong: a module of P or Q
     belongs to another card; regroup, and the edge is observed;
   - the parts are joined by something other than an import (a
     subprocess, a queue, a file on disk, an HTTP call): name it in the
     sentence, and list the word under `[flows] observed_by` in
     `systemap.toml` so every flow that names it is observed by it (the
     panel then says `observed by: queue`);
   - the edge was inferred and is not there: remove the flow and its
     sentence;
   - the edge is real and nothing in the tree joins the two (the other
     end is generated, or reached through a path the facts cannot see):
     answer the line in the configuration, saying what joins them.
   A declared flow draws dashed until one of these is done.

4. Walk every entry point. The line reads: `entry point X has no journey`.
   Either write the journey (references/journeys-and-invariants.md) or
   answer why this entry point does not matter to a reader.

5. Walk every model sdk line: `module X imports <sdk> and its component P
   is not an agent`. Five outcomes: P runs a model and is an agent
   (change its kind, and give it context and tool flows); P calls a model
   once and is deliberately not an agent, by the repository's own rule
   (set `calls_model=True` on it: the flag answers the line, its context
   and tool flows draw, and the Agents reading leaves it out); the import
   is a client the reader should see as a tool flow; it is dead; or the
   line is answered in the configuration, citing the rule. When the
   repository defines what counts as an agent (an AGENTS.md, a design
   rule), that definition wins over the SDK prompt. The built-in list
   matches import prefixes,
   so a framework such as `google.adk` fires for its non-model parts;
   `[facts] model_sdks = ["-google.adk"]` removes the entry, and
   `module_sdk = "google.adk"` answers every line it raised.

6. Walk every rule the documents state. One pass, with the invariant
   list beside you, over the documents the repository points a newcomer
   at: the README, AGENTS.md, CLAUDE.md, and a docs index or the first
   level of docs/. Not the whole docs tree: stop when the rules still
   being found govern parts that are not in the tree (a design for a
   part not yet written, a policy for a service the map does not hold).
   Each rule found is an invariant with a citation, or a note in your
   hand-back saying why not.

7. Look at the rendered figures, `docs/map/figures/structure.svg` (the
   parts in their places) and then `docs/map/figures/system.svg` (every
   edge), and the page: `systemap serve` prints its URL. Look for: a
   route that passes close to a card it does not connect; a label sitting
   in the wrong gutter; a region holding one card (is it a region?); a
   component whose plain words repeat its id; a layer that lights almost
   nothing (is it a reading?); a journey that jumps across the map
   between steps (a missing step?); a dashed edge (a declared flow the
   list above has not settled).

8. Reread every sentence in `relations` from the source side. A sentence
   that could be said of any edge ("A uses B") is not a sentence yet.

9. Run `systemap check && systemap judgement --strict`, then `systemap
   refresh`. Together every round: a layout fix that drops an edge
   reopens the crossing-import lines the edge answered, and the judgement
   in the same round is what sees it. Go to 1.

## Every map

The pass runs on every map of the tree. `systemap judgement` prints a
sub-map's lines with its id in front (`Gateway: single module: ...`);
an `item` answer quotes the line as printed, prefix included, and a
bulk form (`kind`, `crossing`, `module_sdk`, ...) covers every map. A
crossing import between two cards of one sub-map is that map's
question; one between a card inside and a card outside is the top
map's, between the two cards there. An entry point, or a model sdk
import, is asked about once, on the deepest map whose card claims its
module, and a journey on any map covers it.

## The stop condition

Stop when all three hold:

- `systemap check` is clean: `coverage: N of N modules mapped` and
  `map layout: clean`, no `stale` line after `refresh`.
- `systemap judgement --strict` exits 0: every remaining line is answered
  in `[judgement] answered`, and no answer is stale. The workflow `init`
  writes runs it after `check`.
- A full pass through steps 1 to 8 changed nothing in `map/model.py`.

Then hand back (SKILL.md, "What to hand back"): the answers are already in
`systemap.toml`.
