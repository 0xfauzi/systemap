# systemap

systemap draws a map of a Python system: one interactive page, generated,
committed beside the code, and checked in CI so it cannot drift. The facts
(which modules exist, what each exports, which tests import it) are read out
of the code with `ast`. The meaning (what the parts are, what they are to
each other, why they are shaped that way) is written once, in a small
Python module, and reviewed by the maintainer. Build state is derived, never
declared: a component is built when the entry point it names exists in the
modules it names. One generator draws every picture, so a figure in a design
document can never disagree with the map it cites. The page has layers (one
map, several readings), relationships (click a component, read the sentence
for each neighbour), journeys (step through a path one edge at a time), and
pan and zoom. It fetches nothing.

## Quick start

    uv add systemap
    uv run systemap init
    # edit map/model.py: name your components, place them, write the sentences
    uv run systemap refresh
    open docs/map/index.html

Commit `docs/map/`, and to publish it enable GitHub Pages from the `docs/`
directory of the repository. `init` also writes
`.github/workflows/systemap.yml`, which fails a pull request when the
committed map no longer matches the tree or the model; the fix it names is
`systemap refresh`.

To have a coding agent draft the model instead of writing it by hand, run
`uv run systemap skill` and point the agent at the skill it writes; see
"Where the judgement comes from" below.

## The model

The model module exports two values, `MODEL` and `MEANING`. Everything in
it is a frozen dataclass from `systemap`:

```python
from systemap import (
    Component, Container, Flow, Invariant, Journey, Layer, Meaning, Model, Region, Step,
)

MODEL = Model(
    canvas=(600, 300),
    containers=(Container("system", "SYSTEM", (16, 16, 568, 268), tone="server"),),
    regions=(Region("core", "CORE", (40, 60, 520, 200), container="system"),),
    components=(
        Component(
            id="Reader",
            region="core",
            does="Reads the input and turns it into a request.",
            interface="read(source) -> Request",
            implemented_by=("mypkg.reader",),
            entry="read",
            x=80,
            y=130,
        ),
        Component(
            id="Writer",
            region="core",
            does="Takes a request and writes the result.",
            implemented_by=("mypkg.writer",),
            entry="write",
            x=370,
            y=130,
        ),
    ),
    flows=(Flow("Reader", "Writer", "request", "work"),),
    flow_kinds=("work",),
    invariants=(Invariant(1, "The writer never reads the input itself.", governs=("Writer",)),),
)

MEANING = Meaning(
    plain={"Reader": "the part that reads", "Writer": "the part that writes"},
    layers=(Layer("work", "Work", question="How does an input become an output?"),),
    layer_of_kind={"work": "work"},
    relations={("Reader", "Writer"): "The reader hands the writer one request at a time."},
    verbs={"work": ("hands to", "receives from")},
    journeys=(
        Journey("input-to-output", "An input becomes an output", steps=(
            Step(acts=("Reader",), measures=(), edge=("Reader", "Writer"),
                 say="The reader parses the input and hands the writer a request."),
        )),
    ),
)
```

What each part is:

- `Container`: a hard boundary (a process, a host, a directory the system
  may not cross). `box` is `(x, y, width, height)` on the canvas; `tone` is
  `host`, `client`, `server` or `isolated`.
- `Region`: a soft band inside a container: a phase, a concern. A region
  that names its `container` is checked to sit inside it.
- `Component`: one card. `kind` is `component` (does work), `store` (holds
  state) or `actor` (outside the system; placed by `container` rather than
  `region`). `x`, `y` is the card's top-left corner; cards are 150 wide and
  56, 52 or 44 tall by kind. `implemented_by` names modules: an exact
  module name, or a package followed by `.*` for the package and everything
  beneath it. `entry` is the function or class that makes the component
  real. `tracker` marks a roadmap item whose code has not landed (an issue
  number in it, `#12`, becomes a link through `issue_url`); `note` is a
  caveat the reader sees.
- `Flow`: one artifact travelling from `src` to `dst`, in one dataflow
  `kind`. Every kind must be listed in `flow_kinds` and mapped to a layer.
- `Invariant`: a numbered rule and the components it governs. The page
  lists them and the panel shows a chip per rule.
- `Layer`: one reading of the map, with the question it answers. The first
  layer is on when the page opens.
- `Meaning`: `plain` gives every component a plain word; `layer_of_kind`
  and `layer_overrides` put every flow in exactly one layer; `relations`
  gives one sentence per flow, read from the source side; `verbs` gives the
  verb printed on a spoke of the relationship wheel per layer, in both
  directions, and `verb_overrides` per edge; `journeys` are stepped through
  on the page, each step naming who acts, who measures, and the edge it
  traces.

Build state comes from `systemap.build_state(component, facts)`: `built`
when every named module exists and one defines the entry; `partial` when
modules exist but the entry is missing or some are gone; `planned` when no
module exists, or the component carries a `tracker` and its entry has not
landed. Planned components draw as dashed ghosts; the page's end-state
switch shows them at full strength.

Positions are hand-placed on purpose. A fixed layout means the same system
always draws the same picture, so a change in the drawing is a change in
the system. `systemap check` refuses a card outside its band, two cards
overlapping, a route through a card it does not connect or across a region
it neither starts nor ends in, a label that touches anything, text below
11px, and any sentence, override or journey step that names something the
model does not have.

`systemap check` also refuses an incomplete map. Every module in the facts
must be claimed by exactly one component's `implemented_by`: a module no
component claims is a hole the reader falls through, and a module two
components claim is a lie about who does the work. A module that genuinely
has no place on the map (a `__main__` shim, a vendored file) is listed under
`[coverage]` in the configuration with a reason; an ignore without a reason
is a configuration error. On success the check prints
`coverage: N/N modules mapped`; on failure it prints each unmapped and each
doubly claimed module and exits 1.

## Configuration

`systemap.toml` at the repository root, or a `[tool.systemap]` table in
`pyproject.toml` (the toml file wins when both exist). Every key is
optional.

| key | default | meaning |
|---|---|---|
| `name` | the directory name | the page title |
| `[package_roots]` | every top-level directory (or `src/<dir>`) with an `__init__.py` | table of `"path" = "import name"` |
| `tests_dir` | `tests` | where `test_*.py` files live; tests that import a module count as its guards |
| `model` | `map/model.py` | the module exporting `MODEL` and `MEANING` |
| `out_dir` | `docs/map` | where the facts, the page and the figures go |
| `facts_file` | `map.json` | the facts file's name inside `out_dir` |
| `issue_url` | none | template with `{n}`; a tracker's `#12` becomes a link |
| `spec_path` | none | a document whose `##` headings are recorded as spec sections |
| `planes` | none | second-level package names recorded as their own plane in the facts |
| `outside_label` | `OUTSIDE THE SYSTEM` | the index heading for actors outside every region |
| `[theme]` | a neutral dark scheme | tokens laid over the default theme; `[theme.layers]` names a colour per layer id, the rest take a palette in order |
| `[[figures]]` | none | figures `refresh` regenerates: `out`, `mode` (`system` or `reach`), `components`, `caption`, `interactive` |
| `[coverage]` | none | `ignore = [{ module = "pkg.mod", reason = "..." }]`: modules the coverage rule may leave unmapped; `module` takes the same `.*` suffix as `implemented_by`; every entry needs a reason |

Unknown keys are refused. The full token list is in `systemap/theme.py`.

## Commands

    systemap init                 write systemap.toml, map/model.py, docs/map/.gitkeep,
                                  .github/workflows/systemap.yml (never overwrites)
    systemap extract [--check]    read the facts out of the tree; --check exits 1 when stale
    systemap render [--check]     render the page; --base REF adds a change map
    systemap check                layout, routes, labels, type size, meaning, wheels, coverage
    systemap figure --out FILE    one figure: --static or --interactive, --mode system|change,
                                  --components A,B (a plan's reach) or --base REF --head REF
    systemap refresh              extract, check, render, and every configured figure;
                                  says "already current" when there is nothing to do
    systemap skill [--dir PATH]   write SKILL.md, the agent skill that drafts the model
                                  (default .claude/skills/systemap/; overwrites, so an
                                  upgrade refreshes it)

Exit codes: `0` the map is current or the check passed; `1` the map is
stale or a check failed; `2` the configuration or the model cannot be used.
Every non-zero exit prints one line saying what to run. `--root DIR` names
the project when it is not the current directory.

## CI

The workflow `init` writes runs three checks on every push and pull
request:

    uv run systemap extract --check
    uv run systemap check
    uv run systemap render --check

Each failure names the fix. Commit `docs/map/` after `systemap refresh`;
the diff of the facts file between two commits is a readable record of what
changed about the system.

## Where the judgement comes from

`systemap extract` is mechanical: it reads the modules, their public
surfaces and the tests that import them, and nothing anyone writes changes
what it finds. The model is the judgement tier: which modules together make
one thing a reader would point at, what that thing is for, what moves
between things, and what each connection means. That model is authored by
a coding agent (Claude Code, Codex or similar) following the skill
`systemap skill` writes, and reviewed by a person: the skill ends by
handing back the list of judgement calls it made (groupings that could go
another way, edges inferred rather than read, every ignore it added) so
the maintainer confirms each one. `systemap check` refuses an incomplete
map, so a draft that leaves a module unclaimed cannot be committed as if it
were finished.

## What it does not do

It is not a call graph: the facts record imports and public surfaces, and
the change map uses them for reach, but the map draws the flows a person
declared, not every call. It is not a dependency visualiser: modules are
not cards, components are, and a component is a thing someone decided
exists. It is not a UML tool: there is one diagram type, one layout placed
by hand, and no notation to learn beyond card, line and label. The meaning
is written on purpose and reviewed by a person, because the one thing the
code cannot tell you is why a part is shaped the way it is.

## Development

    uv sync
    uv run pytest -q
    uv run ruff check .
    uv run mypy

## License

MIT.
