# The schema

Everything is a frozen dataclass imported from `systemap`. Fields are
listed in order; a default means the field is optional. `map/model.py`
exports `MODEL` (a `Model`) and `MEANING` (a `Meaning`).

## Model

`Model(canvas, containers, regions, components, flows, flow_kinds, invariants=())`

The hand-authored topology of one system. `canvas` is `(width, height)` of
the drawing in canvas units. `containers`, `regions`, `components`, `flows`
and `invariants` are tuples of the dataclasses below. `flow_kinds` is the
tuple of the model's own flow kinds; `data`, `control`, `context` and
`tool` are standard and need no declaring, so a model with no kind of its
own passes `()`.

## Container

`Container(id, label, box, sub="", tone="host")`

A hard boundary: a process, a host, a directory the system may not cross.
`box` is `(x, y, width, height)`. `sub` is one line under the label saying
what the boundary means. `tone` is `host`, `client`, `server` or
`isolated`; it picks the stroke and fill from the theme. Actors are placed
in a container, never in a region.

## Region

`Region(id, label, box, container=None)`

A soft band inside a container: a phase, a concern, a team. `container`
names the container it sits inside, and the check refuses a region drawn
outside it. Components, stores, agents, tools and context cards are placed
in a region.

## Component

`Component(id, does, interface="", implemented_by=(), entry="", kind="component", region=None, container=None, x=0, y=0, note="")`

One card on the map. `id` is a code name in CamelCase, unique on the map.
`does` says what it is for in plain words, one or two sentences, with no
counts of lines, files or tests. `interface` is the one line by which other
parts reach it: a signature, a file it writes, a command.

`implemented_by` names the modules that are it: a module exactly
(`"pkg.reader"`) or a package followed by `.*` (`"pkg.ui.*"`) for the
package and everything beneath it. Every module named must be in the facts,
and every module in the facts must be claimed by exactly one component (or
ignored with a reason under `[coverage]` in `systemap.toml`).

`entry` is one public module-level name the claimed modules define: a
function, a class, or an object such as `app` or `root_agent`; copy it from
the facts file's `names`. The check refuses an entry no claimed module
defines and a component that names no module. An actor is the exception:
it claims no code.

`kind` is `component` (does work), `store` (holds state; drawn with a rule
under its name), `actor` (a person or a system outside the code; dashed),
`agent` (runs a model and acts on its output; inner ring), `tool` (a
capability an agent invokes; notched corner) or `context` (a store whose
content enters an agent's window; dotted). `region` places anything but an
actor; `container` places an actor. `x` and `y` are the card's top-left
corner; cards are 150 wide, and 56 tall (52 for a store or a context card,
44 for an actor). `note` is a caveat the reader sees on the card.

## Flow

`Flow(src, dst, artifact, kind)`

One artifact travelling from `src` to `dst`, both component ids. `artifact`
is what moves, as the label on the line: a file, a record, a message, a
call. `kind` is `data`, `control`, `context` (then `dst` must be an agent),
`tool` (then `src` must be an agent), or one of `flow_kinds`. Every flow
needs a sentence in `relations`.

## Invariant

`Invariant(n, text, governs=())`

A numbered rule the repository states about itself, with its source in the
text (a file and line, or a document heading), and the ids of the
components it directly governs. The page lists invariants and the panel of
a governed component points at them.

## Journey

`Journey(id, label, steps)`

An ordered walk through the map a reader steps through one edge at a time.
`label` is what the selector shows. Write one per entry point that
matters; `systemap judgement` names the entry points no journey mentions.

## Step

`Step(acts, measures, edge, say)`

One step of a journey. `acts` are the ids that act, `measures` the ids that
measure it (`()` when nothing does, and the page says so in red), `edge`
the `(src, dst)` of a flow the model has, and `say` one sentence saying what
happens there.

## Layer

`Layer(id, label, question="", sub="")`

One reading of the map the reader can switch to, best written as the
question it answers. Only the model's own layers are declared here; the
standard layers are derived and their ids (`structure`, `system`, `data`,
`control`, `agents`, `context`, `tools`) and `all` may not be reused.

## Meaning

`Meaning(plain, layers=(), layer_of_kind={}, relations={}, journeys=(), layer_overrides={}, verbs={}, verb_overrides={})`

The hand-authored meaning of the topology. `plain` maps every component id
to its plain words. `layers` are the model's own layers, in the order they
follow the standard ones. `layer_of_kind` maps each custom flow kind to a
layer id. `relations` maps every `(src, dst)` to one sentence, read from the
source side. `journeys` is the tuple of journeys. `layer_overrides` moves
one edge to another layer. `verbs` gives, per layer id, the verb printed
when the reader clicks the source and the verb when they click the target
(`("hands to", "receives from")`); the standard layers have verbs already.
`verb_overrides` does the same for one edge.

## What the check refuses

Placement: a card outside its band, two cards overlapping, a region outside
its container, a flow naming an unknown component or a kind that is neither
standard nor declared, a context or tool flow whose agent end is not an
agent, an invariant governing an unknown id. Routes: an edge through a card
it does not connect or across a band it neither starts nor ends in. Labels:
a label touching a card, a header or another label (both labels named), a
container or region header wider than its box or a `sub` that needs more
than two lines, a header touching a card. Type size: anything below 11px.
Meaning: a flow with no sentence or no layer, a component with no plain
word, a journey step naming an unknown id or edge, an override naming an
unknown edge, a custom layer taking a standard id. Wheel: a relationship
wheel whose labels touch each other or the centre. Coverage: a
module claimed by nobody or by two. Entry: a module not in the facts, an
entry not defined, a component with no module. Stale: facts, page or figure
older than the tree or the model.

## The facts file

`docs/map/map.json` by default, written by `systemap extract`. Every field,
from the extractor's own table (`systemap.extract.FIELDS`):

**The file**

- `version`: the facts format; 1.
- `built_at_commit`: the commit the tree was at, or empty outside git.
- `packages`: the import names of the package roots.
- `tests_dirs`: the directories test files were read from, relative to the root: the configured `tests_dir`, or every directory named `tests` or `test`.
- `spec_sections`: the `##` headings of `spec_path`, each with `level` and `title`.
- `entry_points`: where a run can start: one record per point, fields below.
- `components`: one record per module, keyed by its dotted name, fields below.

**Each module, under `components`**

- `id`: the dotted module name.
- `file`: the path relative to the root.
- `package`: the first segment of the name.
- `plane`: the second segment when `planes` names it, else `core`.
- `loc`: lines in the file.
- `sha`: twelve hex digits of the source's SHA-1: the change detector's key.
- `docstring`: the first paragraph of the module docstring, capped.
- `functions`: public functions: `name`, `signature`, `doc` (the first docstring line).
- `classes`: public classes that are not errors: `name`, `doc`, `methods` (public method signatures).
- `errors`: public classes named or based on Error or Exception, the same fields.
- `constants`: UPPER_CASE assignments: `name` and `value`, the first 14.
- `names`: every public module-level name in source order, with its `kind`: `function`, `class`, `error`, `constant` (UPPER_CASE) or `object` (any other assignment, such as `app` or `root_agent`); a component's `entry` may name any of them.
- `uses`: the package's modules this one imports, each with the names taken from it, or `*` for the whole module.
- `imports`: the keys of `uses`.
- `imported_by`: the package's modules that import this one.
- `external`: third-party modules imported, as the dotted names written in the import (`anthropic`, `google.adk`); the standard library and the package's own modules are left out. The judgement's `model sdk` line reads it.
- `tests_total`: how many test functions import this module.
- `tests_primary`: how many of those sit in a file named after the module.
- `tests`: the names of up to 25 of those tests, primary first.

**Each entry point, under `entry_points`**

- `kind`: `console_script`, `main_module`, `main_function`, `subcommand` or `public_function`.
- `name`: the script name, the `python -m` line, `main`, the subcommand word, or the function name.
- `module`: the module that defines it.
- `target`: the function a console script names, or the console script a subcommand belongs to; else empty.
