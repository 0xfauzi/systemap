# Model and facts schema

## Contents

- The model file
- Model
- Container
- Region
- Component: source and interface, kind and appearance, positions and text, nested map
- Flow
- The contract file: Contract, Invariant, ImportRule
- Journey
- Step
- Layer
- Meaning
- Structural checks
- The facts file: the file, each module, each entry point, and the extract summary

The model uses frozen dataclasses exported by `systemap`.
`map/model.py` exports `MODEL` as a `Model` and `MEANING` as a `Meaning`.
`map/contract.py` exports `CONTRACT` as a `Contract`.
Default values identify optional fields.
Use names and prose under the writing profile in `references/language.md`.
Keep schema keys and source symbols exact.

## The model file

systemap reads the model file as data. It does not run the file as Python code.
Write only these statements:

- The module docstring and `from __future__ import annotations`.
- `from systemap import ...` for the model classes and `AGENT_KINDS`, `KINDS`, and `STANDARD_KINDS`.
- `import NAME` for the file `NAME.py` in the same directory, such as `import journeys`.
  Then use `NAME.VALUE` for a value from that file.
- `NAME = value` and `NAME: annotation = value`. systemap does not read the annotation.
- A type alias for annotations, such as `Steps = tuple[Step, ...]`.

A value is a `str`, `int`, `float`, `bool`, or `None` constant, or a `tuple`, `list`, `set`, or `dict` of values.
A value can also be a minus sign before a number, a model class call, or a name that an earlier statement defines.
Write each position, digest, and source record as a literal value.
Do not write functions, loops, comprehensions, f-strings, operators, indexes, or other imports.
systemap refuses other syntax and gives the file and the line.
If systemap refuses a statement, write the value as a literal value.

The maintainer can set `SYSTEMAP_TRUST_MODEL_CODE=1` to run model code in a repository with safe code.
Do not set this value to make a refused model file load.
For a model file from an earlier version, tell the maintainer about `systemap convert`. It writes the same model with literal values only.

## Model

`Model(canvas, containers, regions, components, flows, flow_kinds, invariants=(), import_rules=())`

`canvas` gives `(width, height)` in SVG coordinate units.
Write the invariants and the import rules in the contract file, not in `Model`.
The other collections are tuples of the dataclasses below.
`flow_kinds` contains custom kinds only.
A declaration is not necessary for the standard kinds `data`, `control`, `context`, and `tool`.
If there are no custom kinds, use `()`.

## Container

`Container(id, label, box, sub="", tone="host")`

A container is a map boundary for a process, host, or source directory.
`box` gives `(x, y, width, height)`.
`sub` gives a short boundary description below the label.
`tone` selects theme colors for `host`, `client`, `server`, or `isolated`.
Put actors in containers, not regions.

## Region

`Region(id, label, box, container=None)`

A region is a component group for one function, phase, or team within a container.
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
Some entry points do not start one public name, for example a package bin or a `__main__` module.
For such an entry point of the modules, `entry` can be its name or label from `systemap facts --entry-points`.
If the modules define no public name and start no entry point, `entry` can be empty.
An entry supplied by any kind still receives the normal source check.

`interface` is optional. It starts with an existing public symbol or re-export.
Examples are `read(source) -> Request` and `Ledger.record / Ledger.history`.
The checker reads the first identifier. An identifier can contain Unicode letters.
It ends at the first character that an identifier cannot contain, such as `(`, `.`, `-`, or whitespace.
For `Class.method`, both the class and its public method must exist.

Keep literal signatures exact. Write any additional description under the writing profile.

An empty package marker has no public names, internal imports, external imports, or top-level execution.
The coverage check includes these markers without a manual exclusion.
An exclusion for markers alone is not necessary and receives a finding.
For actual exclusions, record a reason:

```toml
[coverage]
ignore = [
    { module = "pkg.compat", reason = "Compatibility code has no separate function on this map." },
    { module = "pkg.vendor.*", reason = "This directory contains third-party source code." },
]
```

`source_review` records a SHA-256 digest after source examination.
Examine the description, interface, connected flows, sequences, and invariants before you write it.
Then run `systemap review ID` to write it. Do not write the digest with a script.
Delta keeps a changed component under `The map needs an update` until the digest agrees with the current claims and source.
If the value is not the current digest, `systemap judgement` gives a `stale source review` finding.
Refresh does not write this digest. See `references/maintenance.md` for the procedure.

### Kind and appearance

| kind | function | card mark |
|---|---|---|
| `component` | A system part that does work. | Standard outline. |
| `store` | Stored software data. | A second line at the bottom of the card. |
| `actor` | A person or system outside the mapped source. | Dashed outline. |
| `agent` | A model-calling part that acts on model output. | Inner ring. |
| `tool` | A capability that an agent calls. | Notched corner. |
| `context` | Stored content that enters a model context window. | Dotted outline and a second line at the bottom of the card. |

Source cards have the evidence state `built`. Actors show `outside`.
This means the source identities exist. It does not show every authored description.

`calls_model=True` identifies a model call without agent classification.
Context flows can end there and tool flows can start there.
The Context and Tools layers include those flows. The Agents layer does not include that component.
The flag also answers its `model sdk` finding.

### Positions and text

`region` puts a source component in a region. `container` puts an actor in a container.
`x` and `y` give the top-left corner.
Card width is 150 units.
Height is 56 units for components, agents, and tools, 52 for stores and context, and 44 for actors.

Leave positions unset. Run `systemap place`.
`pinned=True` keeps a position during `systemap place --all`.

Card names and short descriptions have measured text limits.
A component, agent, or tool can show a long CamelCase name on two lines.
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

Its actors use the identifiers of adjacent components on the parent map.
An actor cannot have a nested map.

The parent card keeps its flows and shows a second card behind it.
The inspector has a preview and an open button.
Double-click or a second Enter also opens the nested map.
`docs/map/Gateway/index.html` has a parent link.
A nested map can also have nested maps, with identifiers such as `Gateway/Routes`.
See `references/layout.md` for thresholds and commands.

## Flow

`Flow(src, dst, artifact, kind, source_refs=(), review_digest="", id="")`

A flow carries one artifact from component `src` to component `dst`.
Use an artifact noun phrase of one to three words.
Standard kinds are `data`, `control`, `context`, and `tool`.
Declare other kinds in `flow_kinds`.

A context destination must be an agent or `calls_model` component.
A tool source must be an agent or `calls_model` component.
Every flow must have a relation sentence.

The flow identifier is the `id`. A flow without an `id` has the identifier `SRC->DST`.
Use the identifier as the key in `relations`, `layer_overrides`, and `verb_overrides`.
The `(src, dst)` pair is also a correct key, but only for a pair that one flow connects.
Represent the other direction as a separate flow with its own sentence.

One flow per ordered pair is permitted without an `id`.
Two or more flows can connect one ordered pair only if each of these flows has its own `id`.
An `id` contains only letters, digits, `_`, `.`, and `-`.
Each flow then has its own sentence, review digest, finding lines, and label on the map.
A finding line names such a flow as `SRC -> DST [ID]`.

```python
FLOWS = (
    Flow("OrderService", "OrderQueue", "order", "data", id="submit-order"),
    Flow("OrderService", "OrderQueue", "cancel", "control", id="cancel-order"),
)
RELATIONS = {
    "submit-order": "The service puts a new order in the queue.",
    "cancel-order": "The service tells the queue to remove an order.",
}
```

An import, common module, or configured mechanism gives `structural` evidence only.
`observed` must have current `source_refs` and a `review_digest` that agrees with the flow, the relation sentence, and the source in `source_refs`.
At least one reference must be in a module of the source or target component.
An actor has no modules. For a flow with an actor end, use a module of the other end.
If no reference is in an endpoint module, the flow is not `observed`, and `systemap judgement` gives a `no endpoint source` finding.
The page shows `observed` as "current source review". It is a recorded source review, not a record of program execution.
A reference has the form `module[:symbol]@<source_sha256>`.
The facts file gives the `source_sha256` of each module in `components`. The section "The facts file" gives its fields.
`systemap review --flow 'SRC->DST'` writes the current `review_digest` of one flow.
Use `--flow ID` for a flow with an `id`. The `SRC->DST` form is correct only for a pair that one flow connects.
It does not examine the claims for you. Examine the source before you record the values.

A source change gives a new `source_sha256`.
A change to the flow or its relation sentence gives a new `review_digest`.
The `review_digest` also contains the `source_refs` with the digest of each module.
Thus a change to a module in `source_refs` makes the flow review not current, also when the claim does not change.
A new digest in `source_refs` does not record a review. Examine the flow again. Then run `systemap review --flow`.
A flow without `source_refs`, or with a source record that does not agree with the facts, has no current review.

systemap 2.0.0 records a `review_digest` that contains only the claim.
`systemap refresh` and `systemap extract` replace that digest one time with a digest of the claim and the current `source_refs`.
The review stays current, with the label "review earlier than source tracking".
The label shows that the digest does not identify the examined source.
After the replacement, a change to a module in `source_refs` makes the review not current.
Digests identify recorded source and claims. They do not show the claim's meaning automatically.

`external` has an actor endpoint. `declared` has no examined source or structural support.
Structural and declared flows use dashed lines. Examine their source evidence.

```toml
[flows]
observed_by = ["subprocess", "queue", "facts file"]
```

These configured words classify structural mechanisms only. They do not give observed evidence.

## The contract file

`Contract(invariants=(), import_rules=())`

The contract file gives the rules of the map. It is in the folder of the model file.
For `map/model.py`, the file is `map/contract.py`. For a nested map in `map/gateway.py`, the file is `map/gateway_contract.py`.
The file uses the same statements as the model file and exports `CONTRACT`.
Change the components, flows, and sequences freely. Change a rule only with a reason.
Each rule must have a `reason`. A rule without a reason gives a `contract reason` line.
Write the reason from the code, the documentation, or the commit history.
If a reviewer refuses a change to a rule, add the cause to the reason of the rule that stays.

A map from before the contract file can give the rules in `Model(..., invariants=..., import_rules=...)`.
The first `systemap refresh` or `systemap extract` moves them to the contract file one time.
If the two files give rules, systemap refuses the map.

```python
from systemap import Contract, Invariant

INVARIANTS = (
    Invariant(
        1,
        "The writer never reads the input itself (README, Design).",
        governs=("Writer",),
        reason="The reader is the only component that reads the input (README, Design).",
    ),
)

CONTRACT = Contract(invariants=INVARIANTS)
```

## Invariant

`Invariant(n, text, governs=(), reason="")`

An invariant gives a source-supported repository rule.
`n` must be unique. `text` includes a file and line or a document heading citation.
`governs` contains the directly affected component identifiers.
`reason` gives the cause of the rule. The reason is not a claim of a component.
The page and component inspector show the applicable rules.

## ImportRule

`ImportRule(id, kind, src=(), dst=(), reason="", invariant=None)`

An import rule gives a permitted relation between components.
`systemap check` and `systemap rules` compare each rule with the resolved imports in the facts.
`id` must be unique. `kind` must be one of these values:

| `kind` | The result is `fail` if |
|---|---|
| `forbid_import` | A module of a `src` component imports a module of a `dst` component. |
| `allow_imports` | A module of a `src` component imports a module of a component that is not in `src` or `dst`. |
| `forbid_cycle` | The imports between the `src` components make a cycle. An empty `src` selects all components. |

`reason` gives the cause of the rule. `invariant` gives the number of the related invariant.
The rules do not examine external packages, because the import facts do not contain them.

```python
IMPORT_RULES = (
    ImportRule(
        "reader-alone",
        "forbid_import",
        src=("Reader",),
        dst=("Writer",),
        reason="The reader does not use the writer.",
    ),
)
```

Put the tuple in `Contract(..., import_rules=IMPORT_RULES)`.
The result is `unknown` if no resolved import is against the rule, but the facts possibly do not contain all imports of a rule module.
This occurs when a module did not parse, or when a module has unresolved imports.
`allow_imports` also gives `unknown` for an import of a module with no component.
`check` prints an `unknown` result as a warning. `unknown = "fail"` in `[rules]` makes it an error.

## Journey

`Journey(id, label, steps, starts="", drafted=False, covers=())`

The schema term `Journey` represents a sequence of ordered steps.
`id` is its stable identifier. `label` is the selector text.
`starts` is a display label for the entry point and a migration hint for the old format.

`covers` contains exact entry identities as JSON array strings in `[kind, module, target, name]` order.
A nonempty sequence covers only those identities.
`drafted=True` means the agent answer still has no source examination.

## Step

`Step(acts, measures, edge=("", ""), say="", flow="", source_refs=())`

`acts` identifies the components that act.
`measures` identifies components that monitor or record the step. If none applies, use `()`.
`flow` is the identifier of an existing flow, for example `flow="cancel-order"`.
`edge` is the `(src, dst)` pair of an existing flow. Use it only for a pair that one flow connects.
Give `flow` or `edge`. If two or more flows connect the pair, `flow` is necessary.
`say` gives one sentence about the action and result, under the writing profile.

`source_refs` is optional. It has the same `module[:symbol]@<source_sha256>` form as for a flow.
Each record must resolve in the current facts.
Each record must also be in a module of an acting or measured component of the step.
If a record does not agree with these rules, `systemap judgement` gives a `step source` finding.
`systemap journeys` refuses an agent step with such a record.

## Layer

`Layer(id, label, question="", sub="")`

Declare only custom layers. Do not use a standard layer identifier for a custom layer:
`structure`, `system`, `data`, `control`, `agents`, `context`, `tools`, and `all`.
The theme supplies layer colors. Custom layers use its palette in order.

The page has the Ink and Paper themes. Their scheme keys are `dark` and `light`.
The `scheme` field selects the palette for figures.
The initial theme uses the device theme.
The page uses a stored selection when one exists.
Theme overrides use `[theme]` or `[theme.<scheme>]`:

```toml
[theme]
scheme = "dark"
[theme.layers]
record = "#8A8B22"
[theme.light]
accent = "#1D1B17"
```

## Meaning

`Meaning(plain, layers=(), layer_of_kind={}, relations={}, journeys=(), layer_overrides={}, verbs={}, verb_overrides={})`

| field | contents |
|---|---|
| `plain` | One short display name for every component identifier. |
| `layers` | Custom layers, after standard layers. |
| `layer_of_kind` | A layer identifier for each custom flow kind. |
| `relations` | One sentence per flow, from the source component. The key is the flow identifier or the `(src, dst)` pair. |
| `journeys` | The tuple of sequences. |
| `layer_overrides` | A different layer for a specified flow. The key is the same as in `relations`. |
| `verbs` | Source and destination direction verbs for a layer, such as `("sends to", "receives from")`. |
| `verb_overrides` | Direction verbs for one flow. The key is the same as in `relations`. |

## Structural checks

The checker rejects these conditions:

- Missing positions, cards that overlap, and components outside their region or container.
- Unknown flow endpoints, invalid kinds, and invalid context or tool endpoints.
- A flow with the same component at its two ends.
- Two flows on one ordered pair without an `id` on each, an incorrect `id`, and an `id` on two flows.
- A pair key in `relations`, `layer_overrides`, or `verb_overrides` for a pair with two or more flows.
- A step with an unknown flow, or with the pair of two or more flows.
- Unknown invariant components and duplicate invariant numbers.
- Import rules with a duplicate id, an unknown `kind` value, an unknown component, or an unknown invariant.
- Imports against an import rule.
- Routes through unrelated cards or regions.
- Labels that touch cards, headers, or other labels.
- Text that exceeds its box or is below the minimum type size of 11 units.
- Missing relation sentences, plain names, or layer assignments.
- Unknown sequence components or edges and invalid overrides.
- Unassigned or multiply assigned modules, and coverage exclusions that are stale or not necessary.
- Missing source modules, public entries, interface symbols, or necessary source claims.
- Nested-map coverage differences, invalid external actors, or nested maps on actors.
- Stale facts, pages, or configured figures.

The inspector has one selection control for each flow connected to the component.
Each control shows the artifact, direction, layer, and evidence state.
Structural checks without failures do not show source meaning or that the text obeys the language policy.

## The facts file

`systemap extract` writes `docs/map/map.json` by default.
These fields come from `systemap.facts_file.FIELDS`.

**The file**

- `version`: The facts format is 13, with portable syntax hashes, compiler provenance, the digests of the configuration values that extraction reads, module completeness, the folder package in `package`, `call_sites`, `types`, `type_only`, `same_as`, and decorators in the `api` fingerprints. Each re-export has `defined_in` and `defined_as`. Each unknown record has a `cause`: `read`, `encoding`, `syntax`, `declaration`, `target`, `declaration file`, `script file`, `package`, `binding`, or `reexport`. `extract --check` marks older formats stale.
- `built_at_commit`: The commit read during extraction (`HEAD`), or empty outside Git. The page prints `facts from <sha>`. Extraction occurs before the commit that records the facts.
- `packages`: The import names of package roots.
- `provenance`: The parser, the compiler settings, and the extraction inputs. A change to the extraction inputs makes a new source review necessary, even without source-file changes. A parser or compiler change alone does not, because these values can be different on another computer. `files` has, for each configuration file that extraction reads, the digest of the values that extraction reads from it. Comments and other values do not change the digest. `installed` has these digests for the files in an installed package folder, for example `node_modules`. A new or changed installed digest is an input change. An installed file that is not on this computer is not a change.
- `tests_dirs`: Root-relative test directories: configured `tests_dir`, or every directory with the name `tests` or `test`.
- `spec_sections`: The `##` headings in `spec_path`, with `level` and `title`.
- `entry_points`: One record for each entry point, with the fields below.
- `entry_point_issues`: Package entry targets or Python decorators with unresolved framework bindings. Each record has `kind`, `name`, `target`, `reason`, and `cause`. A record for a group of targets also has `count`, the number of targets, and `target` is the first target. The list is empty if there are none.
- `test_file_issues`: Test files that could not be read or parsed. Each record has `file`, and a `problem` with `line`, `reason`, `source`, and `cause`. The test functions of these files are not known. `check` prints these records and does not fail. The Python adapter does not write an empty list.
- `config_issues`: The configuration packages that a configuration file extends, and that the adapter cannot read. Each record has `file`, `reference`, and `cause`. Only the TypeScript adapter writes this field, for an npm package in the `extends` key of a tsconfig file. The list is empty if there are none.
- `components`: One module record for each dotted name, with the fields below.

**Each module, under `components`**

- `id`: The dotted module name.
- `file`: The root-relative source path.
- `package`: The dotted name of the package that contains the module. The language adapter writes it. A dot in a file name does not change it. A Python `__init__` module is in the parent package of its own package. A package root gives its own name.
- `plane`: The second module-name segment if `planes` includes it, or `core`.
- `loc`: The file line count.
- `sha`: The first twelve hex digits of the source SHA-1. This is the change-detector key.
- `source_sha256`: The full SHA-256 of UTF-8 source text with normalized newlines, for source references.
- `syntax_sha`: The parsed-syntax digest for source review. Comments and text format do not change it.
- `docstring`: The first paragraph of the module description, with a length limit. The Python adapter reads the module docstring. The TypeScript adapter reads the first documentation comment.
- `functions`: Public functions with `name` and `signature`. A function with overload signatures has one record for each signature, and one record in `names`.
- `classes`: Public class declarations other than errors, with `name` and public method signatures in `methods`. A type declaration that is not a class is in `types`.
- `errors`: Public classes with Error or Exception in their names or bases. They use the same fields as classes.
- `types`: Public type declarations that are not classes, with `name`, `category`, and public method signatures in `methods`. The category is `interface`, `enum`, or `type_alias`. The TypeScript adapter records the three categories. The Python adapter records the `type` statement as `type_alias`. Python 3.11 cannot parse this statement.
- `constants`: The first 14 UPPER_CASE assignments, with `name` and `value`.
- `names`: Public module-level names in source order, with `kind`: `function`, `class`, `error`, `type` (a record in `types`), `constant` (UPPER_CASE), or `object` (other assignments such as `app`). TypeScript uses `unknown` for unresolved kinds. A package `__init__` includes local re-exports, with `reexport_of` and the kind in their source module. A full-module import uses kind `module`. Each re-export and each local alias has `defined_in` and `defined_as`: the module and the symbol that define it, through all re-exports and aliases. `defined_as` is `*` for a full module. The two values are `null` if the defining module is not known. A `*` re-export of the module does not give a name that has `star_export` set to `false`. A name with `star_export` set to `null` can be in the `*` re-export or not. The TypeScript adapter sets `false` for `default`. The Python adapter sets the value from `__all__`. The `__all__` of a package also applies to the names of its `*` re-exports. A Python name that is not in `__all__` stays in `names`, because an import of that name can use it. `type_only` is `true` for a type-only export. A type-only export is not an entry point, because the emitted code has no value for it. A name without `type_only` is not type-only. Python has no type-only export. `entry` and `interface` can use these names.
- `api`: Full export identities for public-surface comparisons: exported name, display bucket, and declaration fingerprint. The fingerprint includes decorators. It does not include callable bodies. A `*` re-export has the name `*`, because one module cannot supply the names that it gives.
- `executes`: Python-only: a top-level call makes a package initializer nonempty.
- `empty_marker`: `true` for a module that only marks a package and holds no code: a Python `__init__.py` file or a TypeScript `index` file without statements. A Python docstring, `pass`, `__future__` import, and literal value for a dunder name such as `__all__` are not statements for this rule. Coverage does not include these modules.
- `unknown`: TypeScript surface entries with unresolved syntax or kinds. Each has a source line, reason, short source excerpt, and `cause`. A parse record also has `parser`, the parser version. The finding line gives only the reason. The line, the excerpt, and the parser version go into rows below the line.
- `uses`: Imported local modules with the names taken from each. `*` means the full module.
- `call_sites`: The local names that the module gets from a name of a module in `uses`, and the lines that use them. Each record has `local`, `target`, `name` (`*` for the full module), `bound`, `line`, and `uses`. `bound` is `import` for a name that an import statement makes, or for a re-export without a local name, such as `export { a } from`. It is `value` for a name that gets its value or type from that name, such as `ledger` after `ledger = Ledger()`. `line` is the binding line. Each use is `[line, function line, property]`. The function line is the line of the named function or method that contains the use, or 0. The property is the attribute that the use reads, or an empty string. The value is `null` if the source did not parse.
- `imports`: The keys of `uses`.
- `imported_by`: Local modules that import this module.
- `external`: Third-party dotted import names, such as `anthropic` or `google.adk`. Standard-library and local-package imports are excluded. `model sdk` findings read this field.
- `tests_total`: The number of test functions with an import reference to this module.
- `tests_primary`: The number of those functions in a file with the module name.
- `tests`: Up to 25 test names, with primary tests first.
- `tests_digest`: A digest of every qualified test identity. It also includes hidden identities.
- `parse_error`: Python source read or parse errors, with line, parser version, and `cause`. Other systemap modules read `completeness`.
- `completeness`: The read condition of the module, with the same meaning for each language. `parsed` is `false` if the extractor could not read or parse all of the source, and `line`, `reason`, and `cause` then give the first problem. Such a module does not reject the map. `unresolved_imports` lists each local import, as the source writes it, that has no module in the facts. A local import is a relative import, a path, a TypeScript path alias, or a name below a package root. If `parsed` is `false`, the import list is not known and is `null`. Third-party packages, standard-library modules, Node.js built-in modules, and imports with a calculated module name are not in the list.

**Each entry point, under `entry_points`**

- `kind`: `console_script`, `main_module`, `main_function`, `subcommand`, `public_function`, `route`, `command`, `task`, or `plugin`.
- `name`: The script name, `python -m` command, `main`, subcommand name, route, command name, plugin hook, or function name.
- `module`: The module that defines the entry point.
- `target`: The console-script function, the console script for a subcommand, or the registered function. It is empty for other kinds.
- `label`: The display name that the language adapter gives to the entry point. A sequence can name it in `starts`.
- `symbol`: The name in `module` that the entry point starts, such as the console-script function or a public function. It is an empty string when the entry point starts no single name, for example a package bin or a `__main__` module that starts the full module, or a subcommand. A symbol claim includes the entry point only when the module and this name agree. If the field is missing, the name is not known. Then no symbol claim includes the entry point.
- `same_as`: The identity of a different entry point that starts the same operation. The language adapter writes it only from an accurate indication. The Python adapter writes it for a console script, a `main` function, or a command that starts the same function as an entry point before it. An import binding of the function is permitted if it is the only module-level binding of the name, other than in an `except` clause. The Python adapter also writes it for a `__main__` module that imports that function and uses it at the module level, not in a function body. Coverage then counts the two entry points as one. An empty string tells that the adapter found no such entry point. Then this entry point must have a sequence. If the field is missing, the value is not known. Then the entry point also must have a sequence.

**The extract summary**

The numbers from `systemap extract` describe source facts.
They do not describe the purposes of the map components.
`modules` counts records under `components`.
`functions`, `classes`, `types`, and `errors` give the sums of those module fields.
`tests` gives the sum of `tests_total`. Thus the count has one item for each pair
of a test function and a module that it imports. A test function that imports three
modules counts three times. The count for test files with the module name gives the
sum of `tests_primary`.

`empty package markers` counts the records with `empty_marker` set to true.
Coverage automatically excludes these records.
