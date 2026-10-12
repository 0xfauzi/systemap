# Concepts

This page gives the terms of a systemap map and their meanings in this project.

A map has two parts: source facts that a program extracts, and a model that a person or an agent writes.
The examples come from the small project in [Get started](getting-started.html).

## Facts and model

The **facts** are records that `systemap extract` makes from the source files.
They contain modules, public names, imports, test references, and entry points.
The command writes them to `docs/map/map.json`.
The facts do not show which modules together do one task. They also do not show the direction of a connection.

The **model** is a Python module, usually `map/model.py`.
It exports `MODEL` and `MEANING`. A person or a coding agent writes it.
The model gives the components, the flows, the sequences, and the invariants.

The renderer makes the page and the figures from the facts and the model.
The checks compare the model with the facts.

## Component

A **component** is the system part that a map assigns to source modules or symbols.
A card on the map shows one component.

- `implemented_by` gives the source of the component: a module (`"shop.orders"`), a package pattern (`"shop.ui.*"`), or a symbol (`"shop.cli:main"`).
- `entry` gives one public symbol of those modules.
- `does` gives the task of the component in one or two sentences.
- `MEANING.plain` gives a short name that the card shows below the identifier.

Each module that is not an empty package marker must have exactly one component, or a recorded ignore under `[coverage]`.

| `kind` | Meaning | Card mark |
|---|---|---|
| `component` | A system part that does work. | Standard border. |
| `store` | Stored software data. | A line below its name. |
| `actor` | A person or system outside the mapped source. It has no modules. | Dashed border. |
| `agent` | A part that calls a model and acts on the model output. | Inner ring. |
| `tool` | A capability that an agent calls. | Notched corner. |
| `context` | Stored content that goes into the input of a model. | Dotted border. |

## Flow and artifact

A **flow** is a directed relation with one artifact and two component endpoints.
The **artifact** is the named data or control item that the flow carries.
This flow carries the artifact `order` from `OrderFiles` to `CommandLine`:

```python
Flow("OrderFiles", "CommandLine", "order", "data")
```

The standard flow kinds are `data`, `control`, `context`, and `tool`.
A model declares each other kind in `flow_kinds` and gives it a layer.
A map has one flow, or no flow, for each ordered pair of components.
Each flow has one relation sentence in `MEANING.relations`, written from the source component.

## Sequence and entry point

An **entry point** is a command, route, or public symbol where a run can start.
Extraction finds console scripts, `python -m` modules, `main` functions, subcommands, and the public functions of a package root:

```text
$ systemap facts --entry-points
entry points: 2. A sequence specifies each applicable entry point. The target is a console-script function or a subcommand script.
  shop (console script): shop.cli, target main
  main() in shop.cli: shop.cli, target main
```

A **sequence** is the ordered set of steps that starts at an entry point.
The schema uses the names `Journey` and `journeys` for a sequence.
Each step gives the acting components (`acts`), the measurement components (`measures`), one flow (`edge`), and one sentence (`say`).
The `covers` field gives the exact entry points that the sequence covers.

```python
Journey(
    id="print-total",
    label="Print the total of an order",
    starts="shop",
    covers=('["console_script","shop.cli","main","shop"]',),
    steps=(
        Step(("Person",), (), ("Person", "CommandLine"), "The person gives an order path."),
        Step(("OrderFiles",), (), ("OrderFiles", "CommandLine"), "The store reads the order."),
        Step(("Orders",), (), ("CommandLine", "Orders"), "The command calculates the total."),
    ),
)
```

A person or an agent writes the steps. A sequence does not record a run of the program.

## Layer

A **layer** is a map view that shows a specified set of components and flows.
Each layer asks one question. The page derives the standard layers from the model:

| Layer | Question | Flows |
|---|---|---|
| Structure | Which components are in each region and container? | None. |
| System context | Which actors connect to the system? | Flows with an actor at one end. |
| Data flow | Which artifacts move between components? | Flows of the kind `data`. |
| Control flow | Which components cause other components to act? | Flows of the kind `control`. |

`MEANING.layer_overrides` can put one flow in a different layer.
A model with an `agent` component, or with a component that has `calls_model=True`, also gets the Agents, Context, and Tools layers.
A model can add custom layers in `MEANING.layers`. The page also has All, which shows all flows.
A layer selects the flows. It does not change their colors: each line has the color of its flow kind.

## Region and container

A **container** is a map boundary for a process, a host, or a source directory.
A **region** is a group of components and its bounds on the map. Each region is in a container.
Actors are in containers, not in regions.
`systemap place` calculates the position of each component in its region.

## Invariant

An **invariant** is a source-supported rule that applies to specified components.
Its text cites the source of the rule, such as a file and line or a document heading.

```python
Invariant(1, "The writer records each result once (docs/ledger.md).", governs=("Writer", "Ledger"))
```

The page shows the invariants as rules in the Details panel. The panel of a component gives its rules.

## Evidence states

Each flow has one evidence state. The renderer and the checks calculate it from the stored source snapshot.

| Stored value | Condition | Line on the map |
|---|---|---|
| `observed` | The flow records source records and a review digest. They agree with the current source and the current claim. At least one source record is in a module of an endpoint. | Solid line. The page shows "current source review". |
| `structural` | An import connects the components, a module is shared, or the sentence names a configured mechanism. | Short dashes. |
| `external` | An actor is at one end. The flow crosses the source boundary. | Solid line. |
| `declared` | No source review and no structural fact support the flow. | Long dashes. |

The stored value `observed` is an identifier. It does not mean that a program ran.
The page legend, the Details panel, and `systemap describe` use the words "current source review".
A current source review is a recorded source review whose source records still agree with the stored source snapshot.

Structural evidence does not show the direction or the artifact of a flow. No evidence state records a run of the program.
`systemap describe` counts the states:

```text
evidence: 2 observed (current source review), 0 structural (an import, a shared module, or a configured mechanism), 1 external (an actor endpoint), 0 declared (no source review or structural evidence)
```

The [reference](reference.html#what-does-systemap-check-reject) gives the source record format and the command that prints the digests.

## Review states

A component can record a `source_review` digest after a person or an agent examines its source and its claims.
Each source component has one review state:

| State | Condition |
|---|---|
| `missing` | The component has no `source_review` value. |
| `stale` | The `source_review` value is not the current digest of its source and its claims. |
| `current` | The `source_review` value is the current digest. |

`systemap judgement` counts the states on one line, for example `source reviews: 0 current, 0 stale, 3 missing`.
A stale review is a `stale source review` finding, so `judgement --strict` fails.
A missing review is not a finding.
`systemap delta` gives a `source review` line for each changed component whose review is not current.

## Findings and answers

A **finding** is one line that a command prints about the map. The line starts with its kind, such as `single module` or `crossing import`.

- A `systemap check` finding rejects the map. The command exits 1.
- A `systemap judgement` finding is a possible map error that a person or an agent must examine.
- A `systemap delta` line gives a change and the necessary map action.

Under the first finding of each kind, a `why` row and a `do` row explain it. The `--brief` option removes these rows.
`systemap explain` prints the full explanation of a kind:

```text
$ systemap explain "crossing import"
crossing import
  meaning: A module of one component imports a module of another component. No flow connects these components.
  importance: The code has a connection that the map does not show. This connection can affect a change to the system.
  action: Add the flow and its description. Or put the modules in one component, or record why the import does not make a flow necessary.
```

For a `judgement` finding, change the map, or record an answer under `[judgement] answered` in `systemap.toml`.
Each answer has a reason. A finding line is also an identifier, so an exact answer quotes the full line.

- An **exact answer** uses `item` for one line or `items` for a list of lines. It must also have an `evidence` digest.
- A **family answer** uses `kind`, `crossing`, `crossing_into`, `crossing_from`, or `module_sdk`. It must have `policy = true`.

An exact answer without its digest stays pending. The command prints the current digest:

```text
  pending answer: 'single module: CommandLine contains only shop.cli' must have a new source review. The evidence digest is "fc793b1d03fd7039044613f8fee204af0bb50731369b21320091473a6951982e"
```

Examine the source before you copy the digest into the answer:

```toml
[judgement]
answered = [
    { item = "single module: CommandLine contains only shop.cli", reason = "The command line is a separate part: it reads the arguments and prints the result.", evidence = "fc793b1d03fd7039044613f8fee204af0bb50731369b21320091473a6951982e" },
    { kind = "thin layer", policy = true, reason = "This small program has no control flows." },
]
```

When the source evidence changes, the digest changes and the finding opens again.
An answer that matches no finding is stale. `judgement` reports it, but the exit code does not change:

```text
$ systemap judgement --strict
judgement: No possible map error to examine, 4 answered, 1 stale
  stale answer: 'single module: Reports contains only shop.reports' is now missing. Remove it from [judgement] answered.
  policy answer: kind = "thin layer" covers 1 lines at this snapshot. 1 lines are outside the source-review baseline.
source reviews: 0 current, 0 stale, 3 missing
```

An answer does not change the map. It records the reason that the map stays as it is.
The [reference](reference.html#what-does-the-second-pass-find) gives each `judgement` finding and each answer form.
