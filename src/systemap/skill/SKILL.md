---
name: systemap
description: Map a repository with systemap, the map a coding agent draws of a system. Use when asked to "map this repository", "draw the system map", "update the map", write or refresh map/model.py, group modules into components, or make `systemap check` pass. Runs `systemap extract`, drafts the model (components, flows, journeys, invariants), runs `systemap check` until clean, renders with `systemap refresh`, then makes a second pass with `systemap judgement` until a full pass changes nothing, and hands the maintainer the judgement answers.
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
command from the repository root: prefixed with `uv run` when systemap is a
development dependency, bare when it is installed as a tool. `--root DIR`
names the project when you are not in it. If there is no `systemap.toml`,
run `systemap init` first.

## The loop

The first draft will be wrong in ways the checker cannot see: an edge the
code has and the map does not, a grouping by directory rather than by
purpose, an entry point with no walk through it. The check catches
contradictions; it cannot catch omissions. The second pass is the point of
this skill, not a formality after it.

1. **extract**: `systemap extract`. Read the facts file it writes (by default
   `docs/map/map.json`): one record per module under `components`, and the
   `entry_points`. Every module in it must end up claimed by one component.
2. **draft**: write `map/model.py` from the facts and the repository's own
   words (the README, the design documents). `references/schema.md` has
   every field; `references/example.md` is a complete small model.
3. **check**: `systemap check`. Fix every line it prints; repeat until only
   `stale` remains (the page has not been rendered yet).
4. **judgement**: `systemap judgement`. Act on every line, or write down why
   not. Never pass a line over in silence.
5. **render**: `systemap refresh`. Look at `docs/map/figures/system.svg`, and
   open `docs/map/index.html` if you can: routes through cards, labels that
   touch, a region holding one card, a layer that lights nothing.
6. **second pass**: follow `references/second-pass.md`: walk every crossing
   import, every entry point, every rule the documents state, and look at
   the figure again. Expect to find missed edges and wrong groupings. Go
   to 3.
7. **stop**: when check is clean, judgement is empty or every remaining line
   has an answer, and a full second pass changed nothing.
8. **hand back**: the judgement lines with your answer to each, the
   coverage line, and the list of edges you inferred rather than read.

## What goes in the model

- A component is something a reader would point at and name. A module is
  not a part; a component usually holds several, and a module that does
  two things belongs with the one it is for. `implemented_by` names its
  modules and `entry` one public module-level name they define (a
  function, a class, an object such as `app`); both must be in the facts. Kinds: `component`, `store`, `actor` (a person or system
  outside the code), and for agentic systems `agent`, `tool`, `context`.
- A flow is one artifact moving from one component to another. Its kind is
  `data` (an artifact moves) or `control` (one part drives another), the
  agent kinds `context` and `tool`, or one of your own, declared in
  `flow_kinds` and given a layer. The map draws the flows you declare, not
  every import; `references/layers.md` says how to choose.
- One sentence per flow in `relations`, read from the source side. A plain
  name per component in `plain`: the words a newcomer would use.
- Journeys: one per entry point that matters, tracing the components it
  passes through. Invariants: rules the repository states about itself,
  each citing its source. `references/journeys-and-invariants.md`.
- Positions are hand-placed on a grid: columns 190 apart, rows 92 apart,
  cards 150 wide (56 tall; 52 for a store or context; 44 for an actor).
  The gutters are the corridors the edges run along. The check decides.

## Commands

| command | what it does |
|---|---|
| `systemap init` | configuration, starter model, this skill, a workflow; never overwrites; `--no-ci` skips the workflow |
| `systemap extract` | the facts, into the facts file; `--check` exits 1 when they no longer match the tree |
| `systemap check` | every rule; exit 0 clean, 1 with each failure and its fix named, 2 when the configuration or the model cannot be used |
| `systemap judgement` | the list to act on or answer; always exit 0 |
| `systemap refresh` | extract, check, render the page and every configured figure; `already current` when there is nothing to do |
| `systemap figure --out FILE` | one figure from the same generator: `--mode system`, or `--components A,B` for a plan's reach |
| `systemap skill` | reinstall this directory; `--print` writes SKILL.md to stdout |

## What to hand back

1. Every `systemap judgement` line, each with what you did or why you left
   it. The entry point and crossing import lines are read first.
2. The coverage line from `systemap check` (`coverage: N/N modules mapped`)
   and its last line.
3. The edges you inferred from imports rather than read in the documents,
   and the groupings that could go another way.
4. The files to commit: `map/model.py`, `systemap.toml` if you changed it,
   and the output directory (`docs/map/` by default).

## Rules

- No code or test counts anywhere. The map explains what the system does,
  not how much code it has.
- The map draws what exists today. Every module a component names is in
  the facts; nothing on the map is a plan.
- Prose is for emphasis. The relationships live on the edges: one sentence
  per flow, one verb per direction. If it matters, it is an edge.
- Never write an `entry` you did not find in the facts.
- Run `systemap check` after every move; a card outside its band or a
  route through a card is refused, not warned about.

## References

Read each when the loop reaches it:

- `references/schema.md`: every dataclass and field, one paragraph each,
  and the rules the check applies. Read before the draft.
- `references/example.md`: one complete worked model that passes the
  check, with the configuration beside it. Read with the schema.
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
