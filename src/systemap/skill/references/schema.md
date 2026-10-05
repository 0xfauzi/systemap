# Model and facts schema

The model uses frozen dataclasses exported by `systemap`.
`map/model.py` exports `MODEL` as a `Model` and `MEANING` as a `Meaning`.
Default values identify optional fields.
Use ASD-STE100 names and prose as specified in `language.md`.
Keep schema keys and source symbols exact.

## Model

`Model(canvas, containers, regions, components, flows, flow_kinds, invariants=())`

`canvas` gives `(width, height)` in SVG coordinate units.
The other collections are tuples of the dataclasses below.
`flow_kinds` contains custom kinds only.
The standard kinds `data`, `control`, `context`, and `tool` have no declaration requirement.
Use `()` when there are no custom kinds.

## Container

`Container(id, label, box, sub="", tone="host")`

A container is a map boundary for a process, host, or source directory.
`box` gives `(x, y, width, height)`.
`sub` gives a short boundary description below the label.
`tone` selects theme colors for `host`, `client`, `server`, or `isolated`.
Put actors in containers, not regions.

## Region

`Region(id, label, box, container=None)`

A region groups components by function, phase, or team within a container.
`container` identifies that parent container.
The region box must stay inside its container.
Components, stores, agents, tools, and context cards use regions.

## Component

`Component(id, does, interface="", implemented_by=(), entry="", kind="component", region=None, container=None, x=None, y=None, note="", calls_model=False, map=None, pinned=False, source_review="")`

A component is one system part with a clear function.
Its card shows its unique `id`, usually in CamelCase.
Select new identifier words under the language policy.
`does` gives one or two sentences about the function, without code or test counts.
`plain` in Meaning gives its short display name.

### Source and interface

`implemented_by` contains exact module names, package patterns, or source symbols:

- `"pkg.reader"` gives one module a component assignment.
- `"pkg.ui.*"` gives the package and its descendant modules a component assignment.
- `"pkg.mod:name"` refers to a public symbol within a separately assigned module.

Every nonempty module must have exactly one module assignment or a coverage exclusion.
A symbol claim does not count as a module assignment.
It must identify an existing public symbol in an assigned module.
An actor has no source claims.

`entry` identifies one public module-level function, class, or object.
Copy its exact name from `systemap facts --module NAME`.
For symbol-only components, use one of their claimed symbols.
Stores and context cards can have an empty `entry` for a namespace without a public entry point.
Other source components must have an entry.
An entry supplied by any kind still receives the normal source check.

`interface` is optional. It starts with an existing public symbol or re-export.
Examples are `read(source) -> Request` and `Ledger.record / Ledger.history`.
The checker reads the leading identifier before `(`, `.`, `->`, or whitespace.
For `Class.method`, both the class and its public method must exist.
Keep literal signatures exact. Write any additional description in ASD-STE100.

An empty package marker has no public names, internal imports, external imports, or top-level execution.
The coverage check includes these markers without a manual exclusion.
An exclusion for markers alone is unnecessary and receives a finding.
For actual exclusions, record a reason:

```toml
[coverage]
ignore = [
    { module = "pkg.compat", reason = "Compatibility code has no separate function on this map." },
    { module = "pkg.vendor.*", reason = "This directory contains third-party source code." },
]
```

`source_review` records a SHA-256 digest after source examination.
Examine the description, interface, incident flows, sequences, and invariants before you write it.
Delta keeps a changed component under `needs a decision` until the digest agrees with the current claims and source.
Refresh does not write this digest. See `maintenance.md` for the procedure.

### Kind and appearance

| kind | function | card mark |
|---|---|---|
| `component` | A system part that does work. | Standard outline. |
| `store` | Stored software data. | A line below its name. |
| `actor` | A person or system outside the mapped source. | Dashed outline. |
| `agent` | A model-calling part that acts on model output. | Inner ring. |
| `tool` | A capability that an agent calls. | Notched corner. |
| `context` | Stored content that enters a model context window. | Dotted outline. |

Source cards have the evidence state `built`. Actors show `outside`.
This means the source identities exist. It does not show every authored description.
`calls_model=True` identifies a model call without agent classification.
Context flows can end there and tool flows can start there.
The Context and Tools layers include those flows. The Agents layer does not include that component.
The flag also answers its `model sdk` finding.

### Positions and text

`region` places a source component. `container` places an actor.
`x` and `y` give the top-left corner.
Card width is 150 units.
Height is 56 units for components, agents, and tools, 52 for stores and context, and 44 for actors.
Leave positions unset and run `systemap place`.
`pinned=True` keeps a position during `systemap place --all`.

Card names and short descriptions have measured text limits.
A component, agent, or tool can split a long CamelCase name into two lines.
Other kinds use one name line.
The short description uses two lines except for actors or a component with a two-line name.
The checker gives the actual available dimensions when text does not fit.
Do not remove part of an identifier or invent a shorter source name.

`note` gives a source limitation or other necessary qualification.
The inspector shows it below the interface.
A dot on the card also gives the note as hover text.

### Nested map

`map="gateway.py"` identifies a model beside the parent model.
The nested model exports `MODEL` and `MEANING`.
Its internal components must cover exactly the parent's modules, each once.
Symbol claims do not add module coverage. Empty package markers are excluded.
Its actors use adjacent parent-map component identifiers.
An actor cannot have a nested map.

The parent card keeps its flows and shows a second card behind it.
The inspector has a preview and an open button.
Double-click or a second Enter also opens the nested map.
`docs/map/Gateway/index.html` has a parent link.
A further nested map can have identifier `Gateway/Routes`.
See `layout.md` for thresholds and commands.

## Flow

`Flow(src, dst, artifact, kind, source_refs=(), review_digest="")`

A flow carries one artifact from component `src` to component `dst`.
Use an artifact noun phrase of one to three words.
Standard kinds are `data`, `control`, `context`, and `tool`.
Other kinds must be declared in `flow_kinds`.
A context destination must be an agent or `calls_model` component.
A tool source must be an agent or `calls_model` component.
Every flow must have a relation sentence.

One flow per ordered pair is permitted.
The pair is the key for its sentence, direction verbs, and connection diagram.
For multiple transfers in one direction, select the artifact that matters most to the reader.
Represent the other direction as a separate flow with its own sentence.

An import, common module, or configured mechanism gives `structural` evidence only.
`observed` must have current `source_refs` and a matching `review_digest` for the flow and relation sentence.
A reference has the form `module[:symbol]@<source_sha256>`.
Digests identify recorded source and claims. They do not show the claim's meaning automatically.
`external` has an actor endpoint. `declared` has no examined source or structural support.
Structural and declared flows use dashed lines. Examine their source evidence.

```toml
[flows]
observed_by = ["subprocess", "queue", "facts file"]
```

These configured words classify structural mechanisms only. They do not establish observed evidence.

## Invariant

`Invariant(n, text, governs=())`

An invariant gives a source-supported repository rule.
`n` must be unique. `text` includes a file and line or a document heading citation.
`governs` contains the directly affected component identifiers.
The page and component inspector show the applicable rules.

## Journey

`Journey(id, label, steps, starts="", drafted=False, covers=())`

The schema term `Journey` represents a sequence of ordered steps.
`id` is its stable identifier. `label` is the selector text.
`starts` is an entry display label and an old-format migration hint.
`covers` contains exact entry identities as JSON array strings in `[kind, module, target, name]` order.
A nonempty sequence covers only those identities.
`drafted=True` means the agent answer still has no source examination.

## Step

`Step(acts, measures, edge, say)`

`acts` identifies the components that act.
`measures` identifies components that monitor or record the step. Use `()` when none applies.
`edge` is the `(src, dst)` pair of an existing flow.
`say` gives one ASD-STE100 sentence about the action and result.

## Layer

`Layer(id, label, question="", sub="")`

Declare only custom layers. Standard layer identifiers cannot be reused:
`structure`, `system`, `data`, `control`, `agents`, `context`, `tools`, and `all`.
The theme supplies layer colors. Custom layers use its palette in order.
The page has Warm, Graphite, and Paper schemes.
Theme overrides use `[theme]` or `[theme.<scheme>]`:

```toml
[theme]
scheme = "warm"
[theme.layers]
record = "#e3b778"
[theme.paper]
accent = "#8a5a1a"
```

## Meaning

`Meaning(plain, layers=(), layer_of_kind={}, relations={}, journeys=(), layer_overrides={}, verbs={}, verb_overrides={})`

| field | contents |
|---|---|
| `plain` | One short display name for every component identifier. |
| `layers` | Custom layers, after standard layers. |
| `layer_of_kind` | A layer identifier for each custom flow kind. |
| `relations` | One sentence per `(src, dst)` pair, from the source component. |
| `journeys` | The tuple of sequences. |
| `layer_overrides` | A different layer for a specified flow pair. |
| `verbs` | Source and destination direction verbs for a layer, such as `("sends to", "receives from")`. |
| `verb_overrides` | Direction verbs for one flow pair. |

## Structural checks

The checker rejects these conditions:

- Missing positions, overlapping cards, and components outside their region or container.
- Unknown flow endpoints, invalid kinds, duplicate ordered pairs, and invalid context or tool endpoints.
- Unknown invariant components and duplicate invariant numbers.
- Routes through unrelated cards or regions.
- Labels that touch cards, headers, other labels, or the center of a connection diagram.
- Text that exceeds its box or is below the minimum type size of 11 units.
- Missing relation sentences, plain names, or layer assignments.
- Unknown sequence components or edges and invalid overrides.
- Unassigned or multiply assigned modules and stale or unnecessary coverage exclusions.
- Missing source modules, public entries, interface symbols, or required source claims.
- Nested-map coverage differences, invalid external actors, or nested maps on actors.
- Stale facts, pages, or configured figures.

A connection diagram has one spoke per incident flow.
Its direction verbs use the selected component as the point of reference.
Passing these checks does not show source meaning or language compliance.

## Facts file

`systemap extract` writes `docs/map/map.json` by default.
The exported `systemap.extract.FIELDS` table describes its records.
The tables below give each field's purpose.

## The facts file

`systemap extract` writes `docs/map/map.json` by default.
The following fields come from `systemap.extract.FIELDS`.

**The file**

- `version`: The facts format is 4, with portable syntax hashes and compiler provenance. `extract --check` marks older formats stale.
- `built_at_commit`: The commit read during extraction (`HEAD`), or empty outside Git. The page prints `facts from <sha>`. Extraction precedes the commit recording facts.
- `packages`: The import names of package roots.
- `provenance`: The parser and extraction inputs. A change makes a new source review necessary, even without source-file changes.
- `tests_dirs`: Root-relative test directories: configured `tests_dir`, or every directory named `tests` or `test`.
- `spec_sections`: The `##` headings in `spec_path`, with `level` and `title`.
- `entry_points`: One record per entry point, with the fields below.
- `entry_point_issues`: Package entry targets or Python decorators with unresolved framework bindings. Empty if there are none.
- `test_file_issues`: TypeScript test files with unresolved imports or names after a parse error. Empty if there are none.
- `config_issues`: TypeScript npm tsconfig packages in `extends` that cannot be read. Empty if there are none.
- `components`: One module record per dotted name, with the fields below.

**Each module, under `components`**

- `id`: The dotted module name.
- `file`: The root-relative source path.
- `package`: The first module-name segment.
- `plane`: The second module-name segment if `planes` includes it. If not, `core`.
- `loc`: The file line count.
- `sha`: The first twelve hex digits of the source SHA-1. This is the change-detector key.
- `source_sha256`: The full SHA-256 of UTF-8 source text with normalized newlines, for source references.
- `syntax_sha`: The parsed-syntax digest, without comments or formatting, for source review.
- `docstring`: The first module-docstring paragraph, with a length limit.
- `functions`: Public functions with `name` and `signature`.
- `classes`: Public classes excluding errors, with `name` and public method signatures in `methods`.
- `errors`: Public classes with Error or Exception in their names or bases. They use the same fields as classes.
- `constants`: The first 14 UPPER_CASE assignments, with `name` and `value`.
- `names`: Public module-level names in source order, with `kind`: `function`, `class`, `error`, `constant` (UPPER_CASE), or `object` (other assignments such as `app`). TypeScript uses `unknown` for unresolved kinds. A package `__init__` includes local re-exports with `reexport_of` and their defining kind. A full-module import uses kind `module`. `entry` and `interface` can use these names.
- `api`: Full export identities for public-surface comparisons: exported name, display bucket, and declaration fingerprint. The fingerprint excludes callable bodies.
- `executes`: Python-only: a top-level call makes a package initializer nonempty.
- `unknown`: TypeScript surface entries with unresolved syntax or kinds. Each has a source line, reason, and short source excerpt.
- `uses`: Imported local modules with the names taken from each. `*` means the full module.
- `imports`: The keys of `uses`.
- `imported_by`: Local modules that import this module.
- `external`: Third-party dotted import names, such as `anthropic` or `google.adk`. Standard-library and local-package imports are excluded. `model sdk` findings read this field.
- `tests_total`: The number of test functions with an import reference to this module.
- `tests_primary`: The number of those functions in a file named for this module.
- `tests`: Up to 25 test names, with primary tests first.
- `tests_digest`: A digest of every qualified test identity, including hidden identities.
- `parse_error`: Python source read or parse errors, with line and parser version.

**Each entry point, under `entry_points`**

- `kind`: `console_script`, `main_module`, `main_function`, `subcommand`, or `public_function`.
- `name`: The script name, `python -m` command, `main`, subcommand name, or function name.
- `module`: The defining module.
- `target`: The console-script function, or the console script for a subcommand. Empty for other kinds.

**The extract summary**

The quantities from `systemap extract` describe source facts.
They do not describe component functions on the map.
`modules` counts records under `components`.
`functions`, `classes`, and `errors` sum the module fields with those names.
`tests` sums `tests_total`. The count for same-name test files sums `tests_primary`.

`empty package markers` counts `__init__` records without public `names`,
`imports`, or `external` entries. Coverage automatically excludes these records.
