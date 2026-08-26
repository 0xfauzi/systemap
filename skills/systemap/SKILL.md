---
name: systemap
description: Map a repository with systemap, the map a coding agent draws of a system. Use when asked to "map this repository", "draw the system map", "update the map", write or refresh map/model.py, group modules into components, or make `systemap check` pass. Runs `systemap extract`, drafts the model (components, flows, journeys, invariants), places the cards with `systemap place`, runs `systemap check` until clean, renders with `systemap refresh`, then makes a second pass with `systemap judgement` until a full pass changes nothing, and answers the remaining judgement lines in `[judgement] answered` in systemap.toml for the maintainer.
license: MIT
compatibility: Requires Python 3.11+ and the systemap package (uv tool install systemap)
---

# Mapping a repository with systemap

You are drawing a map of this repository's system. systemap draws it from
two inputs. The facts (which modules exist, what each exports, which tests
import it, where a run starts) are read out of the code by `systemap
extract`; nothing you write changes them. The model (which modules together
make one thing a reader would point at and name, what moves between things,
what each connection means) takes judgement, and that is your job here. You
draft it; the maintainer reviews every call before it is trusted.

The model is one Python module, by default `map/model.py`, exporting `MODEL`
and `MEANING`, built from the dataclasses `systemap` exports. Run every
command from the repository root (`--root DIR` names another project);
`systemap` and `uv run systemap` both resolve when the tool is installed.
If there is no `systemap.toml`, run `systemap init` first.

## The loop

The first draft will be wrong in ways the checker cannot see: an edge the
code has and the map does not, a grouping by directory rather than by
purpose, an entry point with no walk through it. The check catches
contradictions, not omissions; the second pass is the point of this skill.

1. **extract**: `systemap extract`, also when `systemap.toml` exists but
   the facts file does not. Then read the facts through `systemap facts`,
   never the JSON (hundreds of kilobytes on a real tree): `--modules` is
   one line per module (name, public names, imports, tests), `--module
   NAME` one record, `--entry-points` where a run starts, `--external`
   every third-party import and who imports it, `--imports NAME` what a
   module imports and what imports it. Every module must end up claimed
   by one component, except the empty package markers the summary lists.
2. **draft**: `systemap suggest` prints a first grouping from the facts
   alone, one proposal per package with two or more modules and the
   imports between proposals: a starting point to argue with, never the
   answer. Then write `map/model.py` from the facts and the repository's
   own words: its README, AGENTS.md, CLAUDE.md, docs/. Write the
   components and the flows with no `x` and `y`, then run `systemap
   place`: it lays the regions out with the corridors the edges need,
   puts every card on the grid, and writes the positions into the file;
   a card given `x` and `y` is pinned and never moved. `references/schema.md`
   has every field; `references/example.md` is a complete small model;
   `references/layout.md` says what is still yours to decide.
3. **check**: `systemap check && systemap judgement --strict`, together,
   every round. Fix every line the check prints and act on or answer every
   judgement line; repeat until only `stale` remains (the page has not
   been rendered yet) and the judgement exits 0. Together, because a
   layout fix that drops an edge reopens the crossing-import lines that
   edge answered, and only the judgement sees that; run in the same
   round, a fix on one side cannot quietly undo the other.
4. **judgement**: `systemap judgement`. Act on every line, or answer it in
   `[judgement] answered` in `systemap.toml` with a reason: one table per
   answer, one form each (`references/second-pass.md` shows them written):
   - `item = "<line>"`: the exact line as printed, without the indent.
   - `items = ["<line>", ...]`: several exact lines, one reason; not empty.
   - `crossing = ["A", "B", ...]`: every crossing import between any two of
     the ids, either direction; two or more different ids.
   - `crossing_into = "A"`: every crossing import into A; one id.
   - `crossing_from = "A"`: every crossing import out of A; one id.
   - `kind = "<kind>"`: every line of one kind, named as in the table.
   - `module_sdk = "<import>"`: every model sdk line for that import name.

   An answered line is suppressed and counted; an answer that matches no
   line is reported as stale, so remove it. Never pass a line over in
   silence. The eight kinds of line:

   | kind | what it says | what to do |
   |---|---|---|
   | `single module` | a card claims one module | keep it if a reader would name it; else fold it into a neighbour |
   | `possible mis-fold` | a module of a several-module card shares no word with the card's id, `does`, plain word or `interface`, and its package holds none of the card's other modules: it may be folded into the wrong card | move it to the card whose purpose it serves, or answer why it belongs |
   | `no sentence` | a flow has no relation sentence | write one, from the source side |
   | `thin layer` | a reading lights fewer than two cards; a standard kind never used counts | add the flows the reading is for, or answer that the system has none |
   | `entry point` | an entry point in the facts that no journey names | write the journey, or answer why it does not matter to a reader |
   | `crossing import` | a module of one card imports a module of another and no flow joins the two | add the edge with its sentence, regroup, or answer that the import carries nothing the reader needs |
   | `declared flow` | a flow no import backs, whose sentence and artifact name no mechanism from `[flows] observed_by` | find the import and fix the claims; name the mechanism in the sentence and list it under `[flows] observed_by`; or remove the flow. Answer only an edge that is real and joined by nothing in the tree |
   | `model sdk` | a module imports a model SDK and its card is neither an agent nor `calls_model` | make it an agent, set `calls_model`, draw the tool flow, or answer citing the repository's rule |
5. **render**: `systemap refresh`, then `systemap describe`: the picture in
   numbers (cards per region, bends per edge worst first, seats per gutter,
   what each reading lights). Open the page only if you can: `systemap
   serve` prints its URL; `docs/map/figures/structure.svg` is the parts in
   their places and `docs/map/figures/system.svg` every edge. Look for a
   snaking edge, a full gutter, a region holding one card, a reading that
   lights nothing.
6. **second pass**: follow `references/second-pass.md`: walk every crossing
   import, every declared flow, every entry point, every rule the
   documents state, and look at
   the figure again. The document reread is one pass over what the
   repository points a newcomer at (README, AGENTS.md, CLAUDE.md, a docs
   index or the first level of docs/), and it stops when the rules still
   being found govern parts that are not in the tree. Expect to find
   missed edges and wrong groupings. Go to 3.
7. **stop**: when check is clean, `judgement --strict` exits 0 (every
   remaining line answered in the configuration), a full second pass
   changed nothing, and the documents left unread govern nothing in the
   tree.
8. **hand back**: the answers are in `systemap.toml`; add the coverage line
   and the groupings that could go another way.

## What goes in the model

- A component is something a reader would point at and name. A module is
  not a part; a component usually holds three to ten, and a repository of
  N modules usually lands between N/10 and N/3 cards: the `single module`
  line pushes from below, `possible mis-fold` and `crossing import` from
  above. A module that does two things belongs with the one it is for.
  `implemented_by` names its modules, or a symbol `pkg.mod:name` for a
  part that lives inside another card's module; `entry` is one public name
  they define (a function, a class, an object such as `app`); both must be
  in the facts. Kinds: `component`, `store`, `actor` (a person or system
  outside the code), and for agentic systems `agent`, `tool`, `context`.
- A flow is one artifact moving from one component to another. Its kind is
  `data` (an artifact moves) or `control` (one part drives another), the
  agent kinds `context` and `tool`, or one of your own, declared in
  `flow_kinds` and given a layer. The map draws the flows you declare, not
  every import; `references/layers.md` says how to choose, and how the
  facts' `external` imports and the `model sdk` judgement line find agents.
- Every flow carries an evidence state read from the facts, never from
  you: `observed` when an import joins its two ends either way or its
  sentence or artifact names a mechanism listed under `[flows] observed_by`
  (a subprocess, a queue, a file); `external` when an actor is at either
  end; `declared` otherwise. A declared flow draws dashed and is asked about.
- One sentence per flow in `relations`, read from the source side. A plain
  name per component in `plain`: the words a newcomer would use.
- Journeys: one per entry point that matters, tracing the components it
  passes through. Invariants: rules the repository states about itself,
  each citing its source. `references/journeys-and-invariants.md`.
- Positions: leave `x` and `y` out and run `systemap place`. It lays the
  regions out on a two-column grid with corridors between them (an edge
  may not cross a region it does not belong to) and puts every card on
  the grid inside its region, the parts that talk together. A card with
  `x` and `y` is pinned and never moved; you decide which region a card
  is in, the order of the regions, and when to pin (`references/layout.md`).
  An artifact label is a noun phrase of one to three words, never a
  sentence. The check decides.

## Commands

| command | what it does |
|---|---|
| `systemap init` | configuration, starter model, this skill, a workflow; never overwrites; `--no-ci` skips the workflow |
| `systemap extract` | the facts, into the facts file; `--check` exits 1 when they no longer match the tree |
| `systemap facts` | the facts read back: `--modules`, `--module NAME`, `--entry-points`, `--external`, `--imports NAME`; never open the JSON |
| `systemap place` | a first position for every card without one, written into the model; a card with `x` and `y` is pinned; with no card pinned the regions, containers and canvas are laid out too; `--print` prints instead |
| `systemap check` | every rule; exit 0 clean, 1 with each failure and its fix named, 2 when the configuration or the model cannot be used |
| `systemap suggest` | a first grouping from the facts alone: one proposal per package with two or more modules, and the imports between proposals; to argue with, never the answer |
| `systemap judgement` | the list to act on or answer; answers live under `[judgement]` in `systemap.toml`; `--strict` exits 1 while a line is open, for CI |
| `systemap describe` | what a look at the picture would tell you: cards per region, bends and length per edge, seats per gutter, cards and edges per reading |
| `systemap refresh` | extract, check, render the page and every configured figure, then check what it wrote; `already current` when there is nothing to do |
| `systemap figure --out FILE` | one figure from the same generator: `--mode system`, `--layer ID` for one reading, or `--components A,B` for a plan's reach |
| `systemap serve` | serve the output directory over HTTP and print the URL; the page does not run from a file:// address |
| `systemap skill` | reinstall this directory; `--print` writes SKILL.md to stdout |

## What to hand back

1. Every `systemap judgement` line you did not act on, answered in
   `[judgement] answered` in `systemap.toml` with its reason (in the
   repository, not in a chat); `judgement` then prints `nothing to confirm`.
2. The coverage line from `systemap check` and its last line.
3. The groupings that could go another way. The edges the facts do not
   back are the `declared flow` lines: fixed, answered, or removed.
4. The files to commit: `map/model.py`, `systemap.toml`, `docs/map/`.

## Rules

- No code or test counts anywhere: the map says what, never how much.
- The map draws what exists today: every module a component names is in
  the facts; nothing on the map is a plan.
- Prose is for emphasis; the relationships live on the edges.
- Run `systemap check && systemap judgement --strict` after every move:
  the check refuses, it does not warn, and the judgement sees what a
  layout fix reopened.

## References

Read each when the loop reaches it:

- `references/schema.md`: every dataclass and field, one paragraph each,
  and the rules the check applies. Read before the draft.
- `references/example.md`: one complete worked model that passes the
  check, with the configuration beside it. Read with the schema.
- `references/layout.md`: what `systemap place` does, what is still yours
  to decide (a card's region, the regions' order, when to pin), and how
  to read `systemap describe`. Read before the draft, and again when the
  check names a route or a label.
- `references/layers.md`: the derived layers, the standard kinds, adding a
  kind of your own, and agentic systems. Read when choosing a flow's kind
  or a component's kind.
- `references/journeys-and-invariants.md`: where journeys and invariants
  come from and how each cites its source. Read at the draft and again at
  the second pass.
- `references/second-pass.md`: the review loop and the stop condition.
  Read at step 6, every time round.
- `references/pitfalls.md`: mistakes seen on first drafts. Read before the
  draft, and again when judgement runs long.
