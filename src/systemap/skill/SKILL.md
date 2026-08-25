---
name: systemap
description: Map a repository with systemap, the map a coding agent draws of a system. Use when asked to "map this repository", "draw the system map", "update the map", write or refresh map/model.py, group modules into components, or make `systemap check` pass. Runs `systemap extract`, drafts the model (components, flows, layers, one sentence per edge, journeys, invariants), runs `systemap check` until every module is mapped and the layout is clean, renders the page with `systemap refresh`, and hands the maintainer the judgement list to confirm.
license: MIT
compatibility: Requires Python 3.11+ and the systemap package (uv tool install systemap)
---

# Mapping a repository with systemap

You are drawing a map of this repository's system. systemap draws it from
two inputs. The first is the facts: which modules exist, what each one
exports, which tests import it. `systemap extract` reads those out of the
code, and nothing you write changes them. The second is the model: which
modules together make one thing a reader would point at and name, what
that thing is for, what moves between things, and what each connection
means. That takes judgement, and it is your job here. You draft it; the
maintainer reviews every judgement call before it is trusted.

The model is one Python module, by default `map/model.py`, exporting two
values, `MODEL` and `MEANING`, built from the dataclasses `systemap`
exports. The schema and a worked example of every part are at the end of
this file, so you never need to open the package's source.

Everything you need runs from the repository root. Prefix each command
with `uv run` when systemap is a development dependency of the project, or
run it bare when it is installed as a tool. `--root DIR` names the project
when you are not in it.

## The workflow, in order

1. **Extract the facts.** Run `systemap extract`. It writes the facts file
   (by default `docs/map/map.json`) and prints a summary. Read the file.
   Under `components` there is one record per module: `functions`,
   `classes`, `errors`, `constants` (its public surface), `uses` (which
   modules it imports, and which names), `imported_by`, `tests` (the tests
   that import it) and `docstring`. Every module in that file must end up
   claimed by exactly one component, so the list of module ids is your
   checklist. If the command says no package roots were found, set
   `[package_roots]` in `systemap.toml` (`"path" = "import name"`) and run
   it again. If there is no `systemap.toml`, run `systemap init` first.

2. **Read the repository's own words** before you invent any: the README,
   the design documents, any roadmap. Use its vocabulary for names, and
   note every rule it states about itself; those become invariants in
   step 8.

3. **Group the modules into components.** A component is something a
   reader would point at and name: "the part that reads input", "the
   ledger". A module is not a part; a component usually holds several, and
   a module that does two things belongs with the one it is for. Each
   `Component` carries:
   - `id`: a code name in CamelCase, unique on the map.
   - `does`: what it is for, in plain words, one or two sentences.
     Describe what it does for the system, not how much code it has: no
     counts of lines, files or tests anywhere in the model.
   - `interface`: how other parts reach it, as one line (a signature, a
     file it writes, a command).
   - `implemented_by`: the modules that are it. Name a module exactly
     (`"pkg.reader"`), or a package followed by `.*` (`"pkg.ui.*"`) to
     claim the package and everything beneath it. Each module belongs to
     one component only.
   - `entry`: one real public function or class from those modules. The
     check looks that name up in the facts and refuses one that is not
     there; copy it from the facts file, do not guess it. The map draws
     what exists today: every module named must be in the facts.
   - `kind`: `component` for a thing that does work, `store` for a thing
     that holds state, `actor` for a person or a system outside the code.
     An actor claims no modules and sits in a container, not a region.
   - `region` (or `container` for an actor): the band it is drawn in.

4. **Write the flows.** A `Flow` is one artifact moving from one component
   to another (a request, a record, a signal), with a `kind` that says
   what sort of movement it is. Read the `uses` and `imported_by` lists in
   the facts to find candidates, then keep the ones a reader needs: the
   map draws the flows you declare, not every import. Every kind you use
   is listed in `flow_kinds` and mapped to a layer in the next step.

5. **Write the layers.** A layer is one reading of the map, best written
   as the question a reader asks: what does the work, what measures it,
   what feeds back, where do I stand, what earns trust, what learns, what
   is recorded. Use the ones the repository's own vocabulary supports; a
   small system may have two. Map each flow kind to a layer in
   `layer_of_kind`, and move a single edge with `layer_overrides` when its
   kind's layer is the wrong reading for it. Then give every component a
   plain name in `plain`: the words a newcomer would use for it.

6. **Write one sentence per edge** in `relations`, saying what the source
   is to the target, read from the source side. Give each layer a verb
   pair in `verbs`: the verb printed when the reader clicks the source
   ("hands to") and the one printed when they click the target ("receives
   from"). Use `verb_overrides` when one edge needs its own pair.

7. **Write journeys**: a few ordered walks through the map that a reader
   can step through one edge at a time. Good ones are a change from spec
   to merge; a failure and its retry; the operator steering. Each `Step`
   names what acts, what measures, the edge it traces (which must be a
   flow), and one sentence saying what happens there.

8. **Copy invariants** from the repository's own rules, with the source
   (file and line, or the document heading) in the text so a reader can
   check it. Name the components each rule governs. A rule the repository
   did not state is not an invariant; it is a proposal, and belongs in
   your list for the maintainer.

9. **Place the cards and run the check.** Positions are hand-placed: `x`
   and `y` are the card's top-left corner on the canvas, and cards are
   150 wide (56 tall for a component, 52 for a store, 44 for an actor).
   Put cards on a grid, columns 190 apart and rows 92 apart, so the
   gutters between them are straight corridors for the edges. Run
   `systemap check` and fix what it names until it prints
   `coverage: N/N modules mapped` and `map layout: clean`. It refuses a
   card outside its band, two cards overlapping, an edge through a card
   it does not connect or across a band it neither starts nor ends in, a
   label touching anything, a sentence naming something the model does
   not have, a module the facts do not have, an entry its modules do not
   define, and any module no component claims. Move cards until the
   routes are clean. If a module genuinely has no place on the map (a
   `__main__` shim, a vendored file), add it to `[coverage] ignore` in
   `systemap.toml` with a reason, and list it for the maintainer. One
   line is expected to remain until the next step: `stale`, saying the
   page or a figure has not been rendered. Every other line must go.

10. **Render.** Run `systemap refresh`. It extracts, checks, renders the
    page (`docs/map/index.html`) and every figure the configuration lists,
    or says `already current` when there is nothing to do. Open the page
    if you can and click through the layers once: every layer should
    answer its question with the parts and routes it lights.

11. **Hand back.** Run `systemap judgement` and give the maintainer what
    the last section of this file lists. A person confirms each call
    before the map is trusted.

## The commands at each step

| step | command | what it does |
|---|---|---|
| start | `systemap init` | writes `systemap.toml`, a starter `map/model.py`, this skill, and a workflow that runs the check on every pull request; never overwrites; `--no-ci` skips the workflow |
| 1 | `systemap extract` | reads the facts out of the tree into the facts file |
| 1 | `systemap extract --check` | exit 1 when the facts no longer match the tree |
| 9 | `systemap check` | every rule; exit 0 clean, 1 with each failure and its fix named, 2 when the configuration or the model cannot be used |
| 10 | `systemap render` | the page from the facts and the model; `--check` exits 1 when the committed page is stale |
| 10 | `systemap refresh` | extract, check, render and every configured figure; after it, `systemap check` exits 0 |
| 10 | `systemap figure --out FILE` | one figure from the same generator: `--mode system`, or `--components A,B` for a plan's reach |
| 11 | `systemap judgement` | the list the maintainer must confirm; exit 0 always |
| any | `systemap skill` | reinstall this file; `--print` writes it to stdout |

## What to hand back

Give the maintainer, in this order:

1. The output of `systemap judgement`: components with a single module
   (a possible over-split), modules whose names share no word with the
   component that claims them (a possible mis-fold), flows with no
   sentence, layers with fewer than two components, and every ignore
   with its reason.
2. Your own judgement calls the tool cannot see: groupings that could go
   another way, edges you inferred from imports rather than read in the
   documents, invariants whose source you are unsure of, and anything
   you left out on purpose.
3. The coverage line from `systemap check` (`coverage: N/N modules
   mapped`) and its last line.
4. The files to commit: `map/model.py`, `systemap.toml` if you changed
   it, and the output directory (`docs/map/` by default).

## Rules

- No code or test counts anywhere. The map explains what the system does,
  not how much code it has.
- The map explains the system, not the code: a reader should understand
  what happens without opening a file.
- The map draws what exists today. Every module a component names is in
  the facts; nothing on the map is a plan.
- Prose is for emphasis only. The relationships live on the edges: one
  sentence per flow, one verb per direction. If something matters, it is
  an edge, not a paragraph.
- Positions are hand-placed and the layout check decides. Run
  `systemap check` after every move.
- Nothing is declared done. A card is code in the tree; never write an
  `entry` you did not find in the facts.

## The schema

Everything is a frozen dataclass imported from `systemap`. Fields in
order; a default means the field is optional.

```
Model(canvas, containers, regions, components, flows, flow_kinds, invariants=())
    canvas         (width, height) of the drawing
    containers     tuple[Container, ...]
    regions        tuple[Region, ...]
    components     tuple[Component, ...]
    flows          tuple[Flow, ...]
    flow_kinds     tuple[str, ...]  every kind a flow may use
    invariants     tuple[Invariant, ...]

Container(id, label, box, sub="", tone="host")
    a hard boundary: a process, a host, a directory the system may not cross
    box            (x, y, width, height)
    tone           "host" | "client" | "server" | "isolated"

Region(id, label, box, container=None)
    a soft band inside a container: a phase, a concern, a team
    container      the container id it sits inside; checked to fit

Component(id, does, interface="", implemented_by=(), entry="",
          kind="component", region=None, container=None, x=0, y=0,
          note="")
    kind           "component" | "store" | "actor"
    region         places a component or store; container places an actor
    x, y           top-left corner; cards are 150 wide, 56 / 52 / 44 tall
    note           a caveat the reader sees on the card

Flow(src, dst, artifact, kind)
    one artifact travelling from src to dst, in one dataflow kind

Invariant(n, text, governs=())
    a numbered rule and the component ids it governs

Meaning(plain, layers, layer_of_kind, relations, journeys=(),
        layer_overrides={}, verbs={}, verb_overrides={})
    plain            {component id: plain words}
    layers           tuple[Layer, ...]; the first is on when the page opens
    layer_of_kind    {flow kind: layer id}
    relations        {(src, dst): one sentence, read from the source side}
    journeys         tuple[Journey, ...]
    layer_overrides  {(src, dst): layer id} moves one edge to another layer
    verbs            {layer id: (verb when clicked is src, verb when clicked is dst)}
    verb_overrides   {(src, dst): (verb, verb)} for one edge

Layer(id, label, question="", sub="")
Journey(id, label, steps)
Step(acts, measures, edge, say)
    acts           tuple of component ids that act in this step
    measures       tuple of component ids that measure it; () when nothing does
    edge           (src, dst) of a flow the model has
    say            one sentence
```

Every component is code in the tree: the check refuses a module the
facts do not have and an entry none of the modules defines.

## A worked example of every part

A small pipeline: a person types input, a reader turns it into a request,
a parser splits it, a writer joins the parts and records the result in a
ledger. The modules are `pkg.reader`, `pkg.parser`, `pkg.writer` and
`pkg.ledger`. This model passes `systemap check` against those modules as
written.

```python
"""The system map of pkg: what the parts are and what they are to each other."""

from __future__ import annotations

from systemap import (
    Component,
    Container,
    Flow,
    Invariant,
    Journey,
    Layer,
    Meaning,
    Model,
    Region,
    Step,
)

# The grid: card columns 190 apart, rows 160 apart here because the two
# regions are stacked. Cards on the grid leave straight corridors for edges.
COL = {"c1": 270, "c2": 460, "c3": 650}
ROW = {"r1": 90, "r2": 250}

CONTAINERS = (
    # A hard boundary. The person is outside the system; the code is one process.
    Container("outside", "OUTSIDE", (16, 16, 186, 368), tone="host"),
    Container("system", "SYSTEM", (222, 16, 662, 368), sub="one process", tone="server"),
)

REGIONS = (
    # Soft bands inside the system: the phase that works, the phase that keeps.
    Region("work", "WORK", (240, 50, 626, 130), container="system"),
    Region("keep", "KEEP", (240, 210, 626, 130), container="system"),
)

COMPONENTS = (
    # An actor: outside the code, placed by container, claims no modules.
    Component("User", "Types the input.", kind="actor", container="outside", x=34, y=96),
    # A built component: its entry `read` is a real function in pkg.reader.
    Component(
        id="Reader",
        does="Reads the input and turns it into a request.",
        interface="read(source) -> Request",
        implemented_by=("pkg.reader",),
        entry="read",
        region="work",
        x=COL["c1"],
        y=ROW["r1"],
    ),
    Component(
        id="Parser",
        does="Splits a request into the parts the writer needs.",
        interface="parse(request) -> list[str]",
        implemented_by=("pkg.parser",),
        entry="parse",
        region="work",
        x=COL["c2"],
        y=ROW["r1"],
    ),
    # A store: it holds state. Its entry is a class.
    Component(
        id="Ledger",
        does="Keeps every record ever written.",
        interface="Ledger.record / Ledger.history",
        implemented_by=("pkg.ledger",),
        entry="Ledger",
        kind="store",
        region="keep",
        x=COL["c2"],
        y=ROW["r2"],
    ),
    Component(
        id="Writer",
        does="Joins the parts and records the result.",
        interface="write(parts, ledger) -> str",
        implemented_by=("pkg.writer",),
        entry="write",
        region="keep",
        x=COL["c3"],
        y=ROW["r2"],
    ),
)

# (from, to, the artifact carried, the dataflow kind)
FLOWS = (
    Flow("User", "Reader", "input", "work"),
    Flow("Reader", "Parser", "request", "work"),
    Flow("Parser", "Writer", "parts", "work"),
    Flow("Writer", "Ledger", "record", "record"),
    Flow("Ledger", "Parser", "history", "record"),
)

FLOW_KINDS = ("work", "record")

INVARIANTS = (
    # Copied from the repository's own words, with the source named.
    Invariant(1, "The writer never reads the input itself (README, Design).", governs=("Writer",)),
    Invariant(2, "Every record is written once (docs/ledger.md).", governs=("Writer", "Ledger")),
)

MODEL = Model(
    canvas=(900, 400),
    containers=CONTAINERS,
    regions=REGIONS,
    components=COMPONENTS,
    flows=FLOWS,
    flow_kinds=FLOW_KINDS,
    invariants=INVARIANTS,
)

# ---- meaning: the plain words, the layers, one sentence per flow ---------

PLAIN = {
    "User": "the person typing",
    "Reader": "the part that reads",
    "Parser": "the part that splits",
    "Ledger": "the record book",
    "Writer": "the part that writes",
}

LAYERS = (
    # One reading each, as the question it answers. The first is on at open.
    Layer("work", "Work", question="How does an input become an output?"),
    Layer("record", "Record", question="What is written down?"),
    Layer("memory", "Memory", question="What does the system remember?"),
)

# Every flow kind belongs to one layer; one edge is moved to another.
LAYER_OF_KIND = {"work": "work", "record": "record"}
LAYER_OVERRIDES = {("Ledger", "Parser"): "memory"}

# One sentence per edge, read from the source side.
RELATIONS = {
    ("User", "Reader"): "The user types one input at a time.",
    ("Reader", "Parser"): "The reader hands the parser one request.",
    ("Parser", "Writer"): "The parser gives the writer the parts in order.",
    ("Writer", "Ledger"): "The writer records every result it produces.",
    ("Ledger", "Parser"): "The ledger tells the parser what was written before.",
}

# The verb on a spoke of the wheel: (when the clicked card is the source,
# when it is the target), per layer, and per edge where one edge differs.
VERBS = {
    "work": ("hands to", "receives from"),
    "record": ("records in", "is written by"),
    "memory": ("reminds", "remembers through"),
}
VERB_OVERRIDES = {("User", "Reader"): ("types into", "is typed by")}

JOURNEYS = (
    Journey(
        id="input-to-record",
        label="An input becomes a record",
        steps=(
            Step(("User",), (), ("User", "Reader"), "The user types an input."),
            Step(("Reader",), (), ("Reader", "Parser"), "The reader makes a request."),
            Step(("Parser",), ("Ledger",), ("Parser", "Writer"), "The parser splits it."),
            Step(("Writer",), ("Ledger",), ("Writer", "Ledger"), "The writer records it."),
        ),
    ),
)

MEANING = Meaning(
    plain=PLAIN,
    layers=LAYERS,
    layer_of_kind=LAYER_OF_KIND,
    layer_overrides=LAYER_OVERRIDES,
    relations=RELATIONS,
    verbs=VERBS,
    verb_overrides=VERB_OVERRIDES,
    journeys=JOURNEYS,
)
```

The configuration beside it, `systemap.toml`, needs nothing for this
model to check; one key is worth knowing. A package root module that only
marks the directory is ignored with a reason:

```toml
[coverage]
ignore = [
    { module = "pkg", reason = "the package root only marks the directory as a package" },
]
```
