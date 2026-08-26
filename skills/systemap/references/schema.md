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

`Component(id, does, interface="", implemented_by=(), entry="", kind="component", region=None, container=None, x=None, y=None, note="", calls_model=False, map=None)`

One card on the map. `id` is a code name in CamelCase, unique on the map.
`does` says what it is for in plain words, one or two sentences, with no
counts of lines, files or tests.

`interface` is the one line by which other parts reach it, shown in the
detail panel (the click) under `does` as the card's signature. It starts
with a public name one of the component's modules defines, a re-export or
a name claimed by symbol included: `read(source) -> Request`,
`Ledger.record / Ledger.history`, `app (the framework's App)`. The check
reads the leading identifier, the token before `(`, `.`, `->` or
whitespace, and for `Class.method` both parts, the method among the
class's public methods in the facts; a line that starts with anything
else is refused with the closest defined name. It is optional: a card
with none shows no signature.

`implemented_by` names the modules that are it: a module exactly
(`"pkg.reader"`) or a package followed by `.*` (`"pkg.ui.*"`) for the
package and everything beneath it. Every module named must be in the facts,
and every module in the facts must be claimed by exactly one component, or
ignored with a reason under `[coverage]` in `systemap.toml`, by exact name
or as a subtree with the same `.*` form:

```toml
[coverage]
ignore = [
    { module = "pkg.compat", reason = "a shim with no place on the map" },
    { module = "pkg.vendor.*", reason = "third-party code carried in the tree" },
]
```

An `__init__.py` with no public names and no imports the facts record (the
package's own modules, or third-party ones) is an empty package marker: `systemap extract` lists every one in its summary, and the
coverage rule leaves them out on its own, so they need no ignore (an
ignore that names only markers is refused as not needed). The coverage
line counts them among the mapped: `coverage: 144 of 144 modules mapped,
5 of them ignored with a reason, 9 of them empty package markers`.

A third form claims one public name inside a module another card owns:
`"pkg.mod:name"`, a symbol claim, for a part that lives in its neighbour's
file (a tool defined beside the agent that invokes it; see
`references/layers.md`). A symbol claim counts for no module in the
coverage rule and conflicts with no claim: the module's owner is whoever
claims the module. The check refuses a symbol claim of a module the facts
do not have, of a name the module does not define, or of a module nobody
claims.

`entry` is one public module-level name the claimed modules define: a
function, a class, or an object such as `app` or `root_agent`; copy it from
`systemap facts --module NAME`, under `names`. For a card that claims only
symbols, the entry is one of them. The panel shows it as `entry: name
(module)`, the module being the one that defines it. The check refuses an
entry no claimed module or symbol defines and a component that names no
module. Two exceptions: an actor claims no code, and a `store` or
`context` card may leave `entry` empty (a constants table, a namespace
with no way in), when its modules alone say it exists and the panel
reads `entry: none (a namespace)`; an entry it does give is checked like
any other.

On the page every card has a `state`, and `built` is its only value: the
check refuses a component whose modules or entry are not in the facts, so
what is drawn exists (an actor, which claims no code, shows `outside`).

`kind` is `component` (does work), `store` (holds state; drawn with a rule
under its name), `actor` (a person or a system outside the code; dashed),
`agent` (runs a model and acts on its output; inner ring), `tool` (a
capability an agent invokes; notched corner) or `context` (a store whose
content enters an agent's window; dotted). `region` places anything but an
actor; `container` places an actor. `x` and `y` are the card's top-left
corner; cards are 150 wide, and 56 tall (52 for a store or a context card,
44 for an actor). Leave them out: `systemap place` writes them, on the
grid inside the card's region, and the check refuses a card that has
none until it does. `place` keeps a card that has them; `place --all`
lays every card out again. `pinned` (default `False`) says a person
chose the position: `place --all` keeps a pinned card where it is and
lays the rest out around it (`references/layout.md`).

The card has a text budget, and the check refuses what does not fit rather
than cutting it: the `id` fits about 20 characters on one line (a
component, agent or tool card wraps a longer CamelCase name over two lines
at its words; a store, a context card and an actor do not), and the plain
word about 26 characters per line, on two lines for a component, store,
context, agent or tool card and one for an actor (one for a component under
a two-line name). The refusal states the budget: `actor cards fit about 26
characters on one line; this one has 34`. Nothing on the map is elided.

`note` is a caveat the reader sees: the panel shows it
as a line under the signature, and the card carries a dot in its top
corner on the map and in every figure, with the note as its hover text.

`calls_model` marks a single-shot call site: a component that calls a
model once and is not an agent by the repository's own rule. A context
flow may end at it and a tool flow start from it, the Context and Tools
readings light those flows, the panel reads `component, calls a model`,
and the `model sdk` judgement line for its modules is answered by the
flag. The Agents reading stays agents only.

`map` opens a map of the card's own, for a card whose modules exceed ten
or any card once a map is past forty (`references/layout.md`, "When to
open a map inside a card"): a path relative to the model file
(`map="gateway.py"` beside `map/model.py`) to a module that exports
`MODEL` and `MEANING` like any model. The map inside draws that card
alone: its cards claim exactly the modules the card claims, no more and
no fewer, each once (a symbol claim counts for no module, an empty
package marker is left out); its actors are cards of the map it is
inside, the ones around the card, so its edges to the outside have
somewhere to land. The card claims the modules once, for coverage; the
check's nesting rule holds the map inside to them, naming each module
that differs. On the page the card stands on a second card, its panel
reads `opens: Gateway (5 cards)` over a preview of the map inside and a
button that opens it in place (a double-click on the card or a second
Enter does the same), and the map's own page at
`docs/map/Gateway/index.html` links back to it for whoever opens it
directly. An actor cannot open a map. A map inside a map is named
`Gateway/Routes`.

## Flow

`Flow(src, dst, artifact, kind)`

One artifact travelling from `src` to `dst`, both component ids. `artifact`
is what moves, as the label on the line: a file, a record, a message, a
call. `kind` is `data`, `control`, `context` (then `dst` must be an agent
or a `calls_model` component), `tool` (then `src` must be one), or one of
`flow_kinds`. Every flow needs a sentence in `relations`.

One flow per ordered pair: `(src, dst)` is the key of the sentence, the
verb and the spoke on the wheel, so the check refuses a second flow from
A to B. When two things travel the same way, pick the artifact that
matters to the reader; when something travels back, draw the other
direction as its own flow with its own sentence.

Every flow has an evidence state, read from the facts at render and at
check time and never written: `observed` when a module of `src` imports
a module of `dst` or the other way round, or when the sentence or the
artifact names a mechanism listed under `[flows] observed_by` in
`systemap.toml` (then the panel says `observed by: queue`); `external`
when either end is an actor; `declared` when nothing in the facts joins
the two. A declared flow draws dashed on the page and in every figure,
the panel says `declared: no import behind it`, and `systemap judgement`
prints one `declared flow` line for it.

```toml
[flows]
observed_by = ["subprocess", "queue", "facts file"]
```

## Invariant

`Invariant(n, text, governs=())`

A numbered rule the repository states about itself, with its source in the
text (a file and line, or a document heading), and the ids of the
components it directly governs. Each rule has its own number; the check
refuses two rules with one number, quoting both. The page lists invariants
and the panel of a governed component points at them.

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

Placement: a card with no position, a card outside its band, two cards
overlapping, a region outside
its container, a flow naming an unknown component or a kind that is neither
standard nor declared, two flows on one ordered pair, a context or tool flow whose agent end is neither an
agent nor a `calls_model` component, an invariant governing an unknown id, two invariants with one
number. Routes: an edge through a card it does not connect or across a
band it neither starts nor ends in. Labels: a label touching a card, a
header or another label (both labels named), a container or region header
wider than its box or a `sub` that needs more than two lines, a header
touching a card, a card whose name or plain word does not fit its budget.
Type size: anything below 11px. Meaning: a flow with no sentence or no
layer, a component with no plain word, a journey step naming an unknown id
or edge, an override naming an unknown edge, a custom layer taking a
standard id. Wheel: the relationship wheel is drawn for a card when it is
clicked, one per card, a spoke per flow that touches it with the verb
read from the card (the clean line counts them: `17 cards, 47 orthogonal
labelled edges, 17 wheels`); one whose labels touch each other or the
centre is refused. Coverage: a module claimed by nobody or by two, an ignore
naming no module or only empty package markers. Entry: a module not in the facts, an
entry not defined, a component with no module, no entry on any kind but
a store or a context card. Interface: a line that
starts with a name none of the component's modules defines, or
`Class.method` where the class has no such public method. Nesting: the
map inside a card claiming a module the card does not claim, leaving one
of the card's modules unclaimed, claiming one twice, or naming an actor
that is not a card of the map above (or is the card itself); an actor
that opens a map. Stale: facts, a page (one per map) or a figure older
than the tree or the model.

## The facts file

`docs/map/map.json` by default, written by `systemap extract`. Every field,
from the extractor's own table (`systemap.extract.FIELDS`):

**The file**

- `version`: the facts format; 2, since a package `__init__` records the names it re-exports; `extract --check` reports a file of an older format as stale.
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
- `functions`: public functions: `name` and `signature`.
- `classes`: public classes that are not errors: `name` and `methods` (public method signatures).
- `errors`: public classes named or based on Error or Exception, the same fields.
- `constants`: UPPER_CASE assignments: `name` and `value`, the first 14.
- `names`: every public module-level name in source order, with its `kind`: `function`, `class`, `error`, `constant` (UPPER_CASE) or `object` (any other assignment, such as `app` or `root_agent`). A package `__init__` also lists every name it imports from the package's own modules, with `reexport_of` naming the module that defines it and the kind that module gives it (`module` for a submodule imported whole). A component's `entry` and `interface` may name any of them.
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

**The extract summary**

The counts `systemap extract` prints, each mapped to a field above, and none of
them for the map: `modules` counts the records under `components`; `functions`,
`classes` and `errors` sum each module's field of that name; `tests` sums
`tests_total`, and the number in a file named after the module `tests_primary`;
`empty package markers` lists every `__init__` record with no public `names`
and nothing under `imports` or `external`, which the coverage rule leaves out on
its own.
