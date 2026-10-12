# Concepts

This page gives the terms of a systemap map and their meanings in this project.

## Facts and model

- **Facts**: records that `systemap extract` makes from the source files. They give modules, public names, imports, test references, and entry points. They do not show which modules do one task together, or the direction of a connection.
- **Model**: a Python module, usually `map/model.py`, that a person or a coding agent writes. It gives the components, flows, sequences, and invariants.

## Component

A **component** is the system part that a map assigns to source modules or symbols. A card on the map shows one component.
`implemented_by` gives its modules (`"shop.orders"`), package patterns (`"shop.ui.*"`), or symbols (`"shop.cli:main"`).

Each module that is not an empty package marker must have exactly one component, or a recorded ignore under `[coverage]`.

| `kind` | Meaning | Card mark |
|---|---|---|
| `component` | A system part that does work. | Standard border. |
| `store` | Stored software data. | A line below its name. |
| `actor` | A person or system outside the mapped source. | Dashed border. |
| `agent` | A part that calls a model and acts on the output. | Inner ring. |
| `tool` | A capability that an agent calls. | Notched corner. |
| `context` | Stored content for the input of a model. | Dotted border. |

## Flow and artifact

A **flow** is a directed relation with one artifact and two component endpoints.
The **artifact** is the named data or control item that the flow carries.

```python
Flow("OrderFiles", "CommandLine", "order", "data")
```

- The standard flow kinds are `data`, `control`, `context`, and `tool`. A model declares each other kind in `flow_kinds` and gives it a layer.
- A map has one flow, or no flow, for each ordered pair of components.

## Sequence and entry point

An **entry point** is a command, route, or public symbol where a run can start.

A **sequence** is the ordered set of steps that starts at an entry point. The schema uses `Journey` for a sequence.
Each step gives the acting components (`acts`), the measurement components (`measures`), one flow (`edge`), and one sentence (`say`).
`covers` gives the entry points that the sequence covers.
A sequence does not record a run of the program.

## Layer

A **layer** is a map view that shows a specified set of components and flows.

| Layer | Flows |
|---|---|
| Structure | None. |
| System context | Flows with an actor at one end. |
| Data flow | The `data` flows. |
| Control flow | The `control` flows. |
| All | All flows. |

A model with an `agent` or `calls_model=True` component also has the Agents, Context, and Tools layers.

## Region and container

- **Container**: a map boundary for a process, a host, or a source directory.
- **Region**: a group of components and its bounds on the map. Each region is in a container.

## Invariant

An **invariant** is a source-supported rule that applies to specified components. Its text cites the source of the rule.

## Evidence states

systemap calculates the evidence state of each flow from the stored source snapshot.

| Stored value | Condition | Line |
|---|---|---|
| `observed` | The source records and the review digest of the flow agree with the current source and claim. At least one record is in a module of an endpoint. | Solid. |
| `structural` | An import connects the components, a module is shared, or the sentence names a configured mechanism. | Short dashes. |
| `external` | An actor is at one end. | Solid. |
| `declared` | No source review and no structural fact support the flow. | Long dashes. |

The page calls `observed` "current source review". It does not mean that a program ran.
The [reference](reference.html#what-does-systemap-check-reject) gives the source record format.

## Review states

A component can record a `source_review` digest after an examination of its source and claims.
Its state is `missing` (no value), `stale` (not the current digest), or `current`.
A stale review is a finding. A missing review is not a finding.

## Findings and answers

A **finding** is one line that a command prints about the map. It starts with its kind, such as `single module`.
A `check` finding rejects the map. A `judgement` finding is a possible map error.
`systemap explain KIND` gives the meaning of a kind and the necessary action.

For a `judgement` finding, change the map, or record an answer with a reason in `systemap.toml`:

```toml
[judgement]
answered = [
    { item = "single module: CommandLine contains only shop.cli", reason = "The command line is a separate part: it reads the arguments and prints the result.", evidence = "fc793b1d03fd7039044613f8fee204af0bb50731369b21320091473a6951982e" },
    { kind = "thin layer", policy = true, reason = "This small program has no control flows." },
]
```

- An **exact answer** quotes the full line in `item`, or lines in `items`. It must have the `evidence` digest that `judgement` prints. Examine the source before you copy the digest.
- A **family answer** uses `kind`, `crossing`, `crossing_into`, `crossing_from`, or `module_sdk`. It must have `policy = true`.

When the source evidence changes, the finding opens again. An answer does not change the map.
The [reference](reference.html#what-does-the-second-pass-find) gives each finding and each answer form.
