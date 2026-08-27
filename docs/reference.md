# Reference

Every rule, command and configuration key, in full. [README.md](README.md) is the short version.

## How it refuses to lie

`systemap check` runs every rule below, prints each failure under its rule
with the fix, and exits 1 if any rule failed.

| rule | what it catches |
|---|---|
| coverage | a module in the facts that no component claims, or that two claim; an ignore that names nothing, or only empty package markers (an `__init__` with no public names and no imports, which the rule leaves out on its own) |
| entry | a component naming a module the facts do not have, no module, or an entry none of its modules defines (a store or a context card may leave `entry` empty); a symbol claim (`"pkg.mod:name"`) of a module the facts do not have, of a name the module does not define, or of a module nobody claims |
| interface | an `interface` line whose leading identifier (the token before `(`, `.`, `->` or whitespace; both parts of `Class.method`) is not a name the component's modules define, a re-export included; refused with the closest defined name |
| nesting | the map inside a card claiming a module the card does not, leaving one of the card's modules unclaimed, claiming one twice, or naming an actor that is not a card of the map above; an actor that opens a map |
| placement | a card outside its band, two cards overlapping, a flow of a kind neither standard nor declared, two flows on one ordered pair, a context or tool flow whose agent end is neither an agent nor `calls_model`, a flow or invariant naming something the model does not have, two invariants with one number |
| routes | a route through a card it does not connect, or across a band it neither starts nor ends in |
| labels | a label that touches a card, a header or another label (both labels named, and the fix that applies: the gutter is full, named by its neighbours and the region to open up, or the label is wider than its seat); a container or region header wider than its box, a `sub` that needs more than two lines, or a header touching a card; a card whose name or plain word does not fit its budget, stated in the refusal (nothing on the map is elided) |
| type size | any text below 11 px at native scale |
| meaning | a sentence, verb, override or journey step naming something the model does not have, a flow with no sentence, a custom layer taking a standard id |
| wheel | a relationship wheel whose labels touch each other or the centre |
| stale | a facts file, a page (one per map) or a figure older than the tree or the model |

Exit codes: `0` current, `1` a check failed, `2` the configuration or the
model cannot be used. A module that genuinely has no place on the map is
ignored under `[coverage]` in the configuration, and every ignore needs a
reason.

The check verifies the cards against the code; it cannot verify that an
edge exists, so every edge says whether the code backs it. The state is
computed from the facts at render and at check time, never authored:

| evidence | when | how it shows |
|---|---|---|
| `observed` | a module of one end imports a module of the other, in either direction; or the two ends share a module (one claims a symbol inside a module the other claims, the shape of a tool defined beside its agent), and then the panel says `observed: shared module`; or the flow's sentence or artifact names a mechanism the repository lists under `[flows] observed_by` (a subprocess, a queue, a file), and then the panel says `observed by: queue` | a solid line; the panel says `observed: an import joins them` |
| `external` | an actor is at either end: the edge is outside the code | a solid line; the panel says `external: outside the code` |
| `declared` | nothing in the facts joins the two | a dashed line on the page and in every figure; the panel says `declared: no import behind it`; `systemap judgement` prints a `declared flow` line until the agent finds the evidence, names the mechanism in the sentence, or removes the edge |

## The second pass

The check refuses contradictions; it cannot refuse omissions. `systemap
judgement` finds those mechanically, so what was missed is found rather
than remembered. It prints one line per thing to look at, and the agent
either changes the model or writes down why not:

| line | what it asks |
|---|---|
| single module | a component that claims one module: a real part, or an over-split? |
| possible mis-fold | a module whose dotted path shares no word with its component's id, `does`, plain word or `interface`, in a component of several modules, and whose package holds none of the others: folded into the wrong part? |
| no sentence | a flow with no relation sentence |
| thin layer | a reading that lights fewer than two components, including a standard kind never used |
| entry point X has no journey | an entry point in the facts (a console script, a subcommand, a main, a public function of the package root) that no journey names |
| crossing import | module A of component P imports module B of component Q and no flow joins P and Q, in either direction: an edge the code has and the map does not |
| declared flow | a flow no import backs, whose sentence and artifact name no mechanism from `[flows] observed_by`: an edge the map has and the code does not; find the evidence, name the mechanism, or remove it |
| model sdk | module X imports a model SDK or an agent framework (anthropic, openai, google.adk and the rest of a built-in list, extended or reduced by `[facts] model_sdks`) and its component is neither an agent nor marked `calls_model` |

A report, not a gate: it exits 0, or 1 with `--strict` while any line is
open, for CI. The list has memory: a line answered under `[judgement]
answered` in `systemap.toml` is suppressed and counted (`judgement: 3
items for the maintainer to confirm, 21 answered`), and an answer that
matches no line is reported as stale, so answers cannot rot. An answer
names the exact line (`item`, or `items` for several) or a family with
one reason: `crossing = ["A", "B", ...]` for every crossing import between
any two of the ids, `crossing_into = "A"` for every one into A,
`crossing_from = "A"` for every one out of it, `kind = "single module"`
(or `"declared flow"`, or any other kind) for every line of a kind,
`module_sdk = "google.adk"` for every model sdk line of an import. The answers are what the maintainer reads, and they
live beside the model. Before any of it, `systemap suggest` prints a
first grouping from the facts alone (one proposal per package with two
or more modules, and the imports between proposals) as a starting point
to argue with, never the answer; the skill's target is three to ten
modules per component, N/10 to N/3 cards for N modules.

## Past forty cards

One canvas cannot hold a large repository legibly, and past about forty
cards the readings stop being readings. A component may carry
`map="gateway.py"`, a path relative to its model file naming a second
model module that exports `MODEL` and `MEANING` like any model. The map
inside draws that one card: its cards claim exactly the modules the
card claims, no more and no fewer, each once (symbol claims allowed,
empty package markers left out), and its actors are cards of the map
above, the ones around the card, so its edges to the outside have
somewhere to land. The card claims the modules once for coverage; the
check's nesting rule holds the map inside to them and refuses any
difference with the modules named, and a sub-map's actor that is not a
card above.

Every command walks the tree. `check` runs every rule on every map, a
sub-map's lines prefixed by its id (`Gateway: map layout: clean ...`);
`refresh` and `render` write one page per map, the top at
`docs/map/index.html` and the map inside a card at
`docs/map/Gateway/index.html`, each linking to the other; `figure --map
Gateway` draws one (and a `[[figures]]` entry takes `map`); `place`
writes positions into every map's file; `describe` and `judgement`
prefix their lines the same way, and an `item` answer quotes the line
as printed while a bulk form covers every map; `delta` compares each
map over the modules its card claims, so a moved module names its card
and its map's file; `suggest` says when a map is past forty cards and
names the cards with the most modules as the candidates to open. A map
inside a map is `Gateway/Routes`.

systemap's own map is not nested: 18 cards is below the threshold. The
worked example is the fixture in
[`tests/test_nested.py`](tests/test_nested.py): one top map of five
cards, two of which open a map.

## The model in one screen

The agent writes one Python module. Everything in it is a frozen dataclass.
This is an excerpt of systemap's own model, two cards and one edge; the
standard kinds need no declaring and the page derives the standard
readings:

```python
from systemap import Component, Flow, Meaning, Model, Region

MODEL = Model(
    canvas=(900, 420),
    containers=(),
    regions=(Region("gather", "GATHER", (24, 40, 400, 340)),
             Region("draw", "DRAW", (460, 40, 416, 340))),
    components=(
        Component(id="FactsExtractor", region="gather",
                  does="Walks the package's syntax tree and writes the facts.",
                  implemented_by=("systemap.extract",), entry="build"),
        Component(id="Schematic", region="draw",
                  does="Draws the cards, the routes and the interaction script.",
                  implemented_by=("systemap.schematic", "systemap.theme"), entry="render"),
    ),
    flows=(Flow("FactsExtractor", "Schematic", "map.json", "data"),),
    flow_kinds=(),
)

MEANING = Meaning(
    plain={"FactsExtractor": "what reads the code", "Schematic": "what draws the map"},
    relations={("FactsExtractor", "Schematic"):
               "The facts say which modules each card stands for, for the line the panel prints."},
)
```

The cards carry no `x` and `y`: `systemap place` writes them, `systemap
place --all` writes them again after a card is added or removed, and a
card marked `pinned=True` keeps the place a person gave it. The full
schema, with one worked
example of every part, is in the skill
the agent reads: [`SKILL.md`](src/systemap/skill/SKILL.md) and its
[`references/`](src/systemap/skill/references/).

## Commands

| command | what it does |
|---|---|
| `systemap init [--no-ci]` | write the config, an empty starter model, the skill directory, and a workflow pinned to this version; never overwrites; prints the sentence for the agent |
| `systemap extract [--check]` | read the facts out of the tree into `docs/map/map.json`: every module's surface, public names (a package `__init__` lists what it re-exports), imports inside and outside the package, tests, entry points; `--check` exits 1 when they no longer match the tree |
| `systemap facts` | read the facts back one view at a time, so nobody opens the JSON: `--modules` (one line per module: the first sentence of its docstring, then public names, imports and tests counted), `--docstrings` (the first sentence alone), `--module NAME` (its record, rendered: docstring, names with kinds, imports, imported by, external, test count; never a test's name), `--names NAME` (its public names with kinds), `--entry-points` (each with its target), `--external` (every third-party import and who imports it), `--imports NAME` (what it imports and what imports it) |
| `systemap place [--all] [--print] [--keep-order]` | a position for every card without one, written into the model in place (only the `x=` and `y=` values, the boxes and the canvas move), on every map of the tree: regions on a two-column grid with the corridors the router needs, in the region order the search scores best (every order tried when there are at most six regions, a greedy start and pairwise swaps past that; each laid out and estimated by the bends its edges need, the twelve best and the order as listed routed with the real router and scored by label collisions, then refused routes, then bends, then length; the chosen order and its score printed: `region order: layout, contracts, ...; 40 bends, 7,909 units; 720 orders tried, 13 routed`), cards on the grid inside, ordered by barycentre sweeps over the flows; a card with `x` and `y` is kept; `--all` lays every card out again and keeps only the cards marked `pinned=True`; `--keep-order` lays the regions as listed and skips the search; deterministic, stdlib only; `--print` prints instead |
| `systemap check` | every rule in the table above, on every map of the tree; exit 1 with each fix named |
| `systemap render [--check] [--base REF]` | the page; `--check` exits 1 when it is stale; `--base` adds a change map against a ref |
| `systemap figure --out FILE` | one figure from the same generator: the system, a plan's reach (`--components A,B`), or a change (`--base REF`); `--layer ID` draws one reading only (that layer's edges, every card, the legend reduced to it); `--map ID` draws the map inside a card; a `.svg` name writes the bare drawing |
| `systemap refresh` | extract, check, render one page per map, and every configured figure, then check what it wrote; "already current: the page matches the model's rendered fields and the facts" when there is nothing to do; exit 1 when the check fails |
| `systemap suggest` | a first grouping to argue with, never the answer: one proposed card per package with two or more modules, its modules, and the crossing imports between proposals, from the facts alone; with a model, when a map is past forty cards and which cards hold the most modules, the candidates to open a map inside |
| `systemap judgement [--strict] [--kind KIND] [--verbose]` | the second-pass list: thin components, odd folds, edges without a sentence, thin layers, entry points without a journey, crossing imports without a flow (one line per pair of cards, counting the modules; `--verbose` lists the imports under it), flows no import backs, model SDK imports outside an agent; answered lines suppressed and counted; `--kind KIND` prints one kind when the list runs long; exit 0, or 1 with `--strict` while a line is open |
| `systemap delta --base REF [--head REF] [--format markdown]` | what a change did to the map, from the facts at two commits read out of git: modules moved, added and removed with the card each belongs to (on every map it is drawn on, and the map's file), a new module no card claims, entry and interface names that vanished, new imports across a card boundary with no flow, flows the code stopped backing; each line names its fix; exit 0 when nothing needs a decision, 1 when something does; `--format markdown` is the pull-request comment |
| `systemap describe` | what a look at the picture would tell an agent that cannot look: how many cards are pinned, placed, and positioned for the look only, cards per region, the region order and what the drawing costs under it (bends and length; label collisions and refused routes when there are any), bends and length per edge worst first with the gutter each label sits in, seats used of seats available per gutter (each named by the cards on either side and its coordinates), edges observed, external and declared, cards and edges per reading |
| `systemap serve [--port 8765]` | serve the output directory over HTTP on the loopback address and print the URL; the page's script does not run from a `file://` address |
| `systemap skill [--dir PATH] [--print]` | reinstall the skill directory, or print `SKILL.md` |

`--root DIR`, before or after the command, names the project when it is
not the current directory.

## Configuration

`systemap.toml` at the repository root, or a `[tool.systemap]` table in
`pyproject.toml`. Every key is optional; unknown keys are refused.

| key | default | meaning |
|---|---|---|
| `name` | `[project] name`, then the git repository's directory, then the directory name | the page title |
| `[package_roots]` | every top-level package or `src/<pkg>`, in the root and in every `[tool.uv.workspace]` member | `"path" = "import name"` |
| `tests_dir` | every directory named `tests` or `test` | one directory or a list; tests that import a module count as its guards |
| `model` | `map/model.py` | the module exporting `MODEL` and `MEANING` |
| `out_dir` | `docs/map` | where the facts, the page and the figures go |
| `facts_file` | `map.json` | the facts file's name inside `out_dir` |
| `spec_path` | none | a document whose `##` headings are recorded as spec sections |
| `planes` | none | second-level package names recorded as their own plane in the facts |
| `outside_label` | `OUTSIDE THE SYSTEM` | the index heading for actors outside every region |
| `[coverage]` | none | `ignore = [{module = "pkg.mod", reason = "..."}]`, or `module = "pkg.sub.*"` for a subtree; an ignore needs a reason; an empty package marker needs none |
| `[facts]` | none | `model_sdks = [...]`: import names added to the built-in list the `model sdk` judgement line reads; a leading `-` removes a built-in name (`"-google.adk"`) |
| `[flows]` | none | `observed_by = ["subprocess", "queue", ...]`: the mechanisms other than an import that join the repository's parts; a flow whose sentence or artifact names one is observed by it rather than declared |
| `[judgement]` | none | `answered = [{item = "<a judgement line>", reason = "..."}]`, or `items = [...]`, `crossing = ["A", "B", ...]`, `crossing_into = "A"`, `crossing_from = "A"`, `kind = "single module"` or `module_sdk = "google.adk"` with one reason for a family of lines; an answer needs a reason, a stale one is reported |
| `[theme]` | warm | colour tokens laid over the default scheme; `scheme = "warm"`, `"graphite"` or `"paper"` picks the default (the page offers all three; `dark` and `light`, the 0.11 names, still pick graphite and paper); `[theme.paper]` lays tokens over one scheme; `[theme.layers]` names a colour per layer id, standard ids included; `[theme.marks]` picks the mark per agent kind |
| `[[figures]]` | none | figures `refresh` regenerates: `out`, `mode` (`system` or `reach`), `components`, `caption`, `interactive`, `layer` (one reading's id: only that layer's edges), `map` (the id of the map inside a card); an `out` ending in `.svg` is the bare drawing |

