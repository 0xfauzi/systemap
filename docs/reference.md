# Reference

This document gives the rules, commands, and configuration keys.
[README.md](README.md) gives the introduction.
If a check has a finding, first read its rule below.
The command descriptions and configuration keys follow the rules.

## What does `systemap check` reject?

`systemap check` executes the rules below.
Each finding appears under its rule with a correction.
The command exits 1 if a rule rejects the map.

| Rule | Rejected condition |
|---|---|
| coverage | No component claims a module, or two components claim it. An ignore identifies no module or only empty package markers. An empty marker is an `__init__` with no public names or imports. The rule automatically excludes these markers. |
| entry | A component claims no module or an absent module. Its modules do not define its entry name. Stores and context components can have an empty `entry`. A symbol claim (`"pkg.mod:name"`) identifies an absent module or name, or a module with no owner. |
| interface | The first identifier of an `interface` is absent from the component's public names and re-exports. The identifier ends at `(`, `.`, `->`, or whitespace. Both parts of `Class.method` must be available. The finding gives the nearest defined name. |
| nesting | A nested map claims an extra module, omits a parent claim, or claims a module twice. Its actor is absent from the parent map. An actor opens a map. |
| placement | A component is outside its region, or components have an overlap. A flow kind is neither standard nor declared. Two flows have the same ordered pair. A context or tool flow has an incorrect agent endpoint. That endpoint must be an agent or a `calls_model` component. A flow or invariant identifies an absent item. Two invariants have the same number. |
| routes | A route crosses an unrelated component or an unrelated region. |
| labels | Text does not fit or touches an obstacle. The conditions are below. |
| type size | Text is smaller than 11 px at native scale. |
| meaning | A sentence, verb, override, or sequence step identifies an absent item. A flow has no sentence. A custom layer uses a standard id. |
| stale | Facts, a page, or a figure are older than the source tree or model. Each map has a page. |

The labels rule rejects these conditions:

- A label touches a component, header, or other label.
  The finding shows the two labels and the applicable correction.
  For a full gutter, it shows the adjacent components and the region
  that must have more space. If not, the label can be wider than its seat.

- A container or region header is wider than its box.
  A `sub` uses more than two lines, or a header touches a component.

- A component's name or plain text does not fit its budget.
  The finding gives the budget. The map does not remove text to add an ellipsis.

Exit code `0` shows a map with no stale outputs.
Exit code `1` shows a rejected check.
Exit code `2` shows unusable configuration, an unusable model, or an unusable option value.
To keep a module out of map coverage, add an ignore under `[coverage]`.
Each ignore must have a reason.

The check compares components with the code.
An import alone cannot show a flow's direction or artifact.
The renderer and the checks use the evidence state of the stored source snapshot:

| Evidence | Condition | Indication |
|---|---|---|
| `observed` | `source_refs` resolve to extracted source hashes. At least one reference is in a module of the source or target component. `review_digest` agrees with the current flow claim and sentence. | A solid line. The page shows "current source review". |
| `structural` | An import connects the components, a module is shared, or a configured mechanism is in the sentence. These facts do not show direction, artifact, or execution. | A dashed line. The panel identifies the structural fact. `judgement` asks for source review. |
| `external` | An actor is at one end. The flow crosses the code boundary. | A solid line. The panel identifies the endpoint outside the source code. |
| `declared` | No source review or structural fact gives evidence for the flow. | A dashed line. `systemap judgement` prints a `declared flow` finding. |

The stored value `observed` is an identifier. It does not mean that a program ran.
The page legend, the Details panel, and `systemap describe` use the words "current source review".
A current source review is a recorded source review whose source records still agree with the stored source snapshot.

For `observed`, a flow records `source_refs` and a `review_digest`.
A reference has the form `module[:symbol]@<source_sha256>`.
At least one reference must be in a module of the source component or the target component.
A package pattern or a symbol claim in `implemented_by` also puts a component in a module.
An actor has no modules. For a flow with an actor end, use a module of the other end.
If no reference is in an endpoint module, the flow is not `observed`.
`systemap judgement` then prints a `no endpoint source` finding.
The command below prints the `source_sha256` of each module and the `review_digest` of each flow.
It does not examine the claims for you. Examine the source before you record the values.

```sh
uv run python - <<'PY'
from pathlib import Path
from systemap import config, evidence, extract, nest

cfg = config.load(Path.cwd())
facts = extract.build(cfg)
for module, record in sorted(facts["components"].items()):
    print(f"source_sha256 {module} {record.get('source_sha256')}")
for current_map in nest.load(cfg).maps:
    for flow in current_map.model.flows:
        digest = evidence.flow_claim_digest(flow, current_map.meaning)
        print(f"review_digest {current_map.prefix}{flow.src} -> {flow.dst} {digest}")
PY
```

A source change gives a new `source_sha256`.
A change to the flow or its relation sentence gives a new `review_digest`.

## What does the second pass find?

The check rejects contradictions.
It cannot show all omissions.
`systemap judgement` uses mechanical rules to find possible omissions.
For each finding, change the model or record the reason for its stored state.

| Finding identifier | Question or condition |
|---|---|
| single module | A component claims one module. Does the module have a different function? |
| possible mis-fold | A module's dotted path has no word in common with its component's id, `does`, plain text, or `interface`. The component has multiple modules. No other module is in the same package. Is the assignment incorrect? |
| no sentence | A flow has no relation sentence. |
| thin layer | A layer contains fewer than two components. This includes an unused standard kind. |
| entry point X has no journey | The entry point's identity is absent from each examined sequence's `covers`. |
| crossing import | Module A in component P imports module B in component Q. No flow connects P and Q in either direction. |
| declared flow | A flow has no source review or structural evidence. Find source evidence or change the claim. |
| flow review | An import, shared module, or mechanism word is available. Direction and artifact must have a source review. |
| no endpoint source | A flow has `source_refs`, but no reference is in a module of its source or target component. Add a reference from an endpoint module or change the flow. |
| stale source review | A component has a `source_review` digest that is not the current digest of its source and claims. Examine the source and the claims again. Then record the current digest. |
| model sdk | A module imports a model SDK or agent framework. Its component is neither an agent nor `calls_model`. Examples are anthropic, openai, and google.adk. `[facts] model_sdks` can add or remove names from the built-in list. |

Without `--strict`, the report exits 0.
With `--strict`, it exits 1 while a finding is open.

Each source component has one review state:
`missing` (no `source_review`), `stale` (`source_review` is not the current digest), or `current`.
`systemap delta` and `systemap judgement` use the same state.
A stale review is a `stale source review` finding, so `judgement --strict` fails on it.
A missing review is not a finding. Many maps have no `source_review` values, and these maps pass `judgement --strict`.
The report counts the three states on one line, for example `source reviews: 16 current, 0 stale, 0 missing`.
`[judgement] answered` in `systemap.toml` contains recorded answers.
Accepted answers suppress findings and increase the answered count.
The report can print `judgement: 3 possible map errors to examine, 21 answered`.
An answer that matches no finding is stale.

An answer can show exact lines or a family of lines:

- `item` shows one exact line.

- `items` shows multiple exact lines with one reason.

- `crossing = ["A", "B", ...]` shows crossings between any two listed ids.

- `crossing_into = "A"` shows crossings into A.

- `crossing_from = "A"` shows crossings from A.

- `kind = "single module"` shows all lines of that kind.
  `"declared flow"` and other kinds use the same form.

- `module_sdk = "google.adk"` shows all model-sdk findings for that import.

The maintainer examines these answers adjacent to the model.
Before the second pass, `systemap suggest` gives proposed module groups.
It gives one proposal for each package with two or more modules, and the imports
between proposals. Examine these proposals against the source.
A component must have one clear function. Module quantity alone does not identify a component.

An exact `item` or `items` answer includes `evidence = "<SHA-256 digest>"`.
When source or import evidence changes, the finding opens again.
`judgement` prints the current digest for examination.
An exact answer without evidence stays pending until source review.

A family answer is a policy for a family of lines and must have `policy = true`.
The report counts current matches and matches outside the optional
`reviewed = ["<line>", ...]` baseline.
A family answer without `policy = true` stays pending.

## What questions does Jev answer?

`systemap audit` is optional.
CI does not execute this command.
The command sends individual semantic questions to TypeSafe's Jev model.
It prints a finding when Jev's answer does not agree with the map.
The mechanical `judgement` rules use names and imports instead.

The development experiments selected thresholds on five mapped repositories in
`bench/jev`. Three holdout maps used the same thresholds: systemap, scorecard,
and a first map of httpie.
The table gives measured results from the recorded prompts.

The prompts changed for ASD-STE100 after these measurements. The changed prompts have no new benchmark measurements.
All measured repositories are Python repositories. No TypeScript result was measured.
Do not use the recorded scores as results for the changed prompts or your system.

| line | what it asks | development maps | holdout maps |
|---|---|---|---|
| jev mis-fold | The component for each module claim. A line prints when the claimed component has P < 0.05. | 95% of incorrect component assignments found. 4% of correct assignments gave incorrect findings. The word rule for `possible mis-fold` found 32%. | 93% found. 1% of correct assignments gave incorrect findings. |
| jev owner | The same question for a module without a component claim. One component prints at confidence 0.9 or more. Otherwise, three print. | 56% of modules get one component. 98% of those answers are correct. | 60% of modules get one component. 100% of those answers are correct. |
| jev sentence | Does the component sentence agree with its modules? A line prints below P 0.2. | 67% of incorrect sentences found. 1% of correct sentences gave incorrect findings. Small source changes can cause no finding. | 61% found. 2% of correct sentences gave incorrect findings. |
| jev flow | Does the code connection agree with the flow claim? A line prints below P 0.2. **`audit` sends these questions only with `--kind "jev flow"`.** | 66% of incorrect claims found. 2% of correct claims gave incorrect findings. Evidence excludes instance calls. This exclusion can cause an incorrect finding. | 54% found. 4% of correct claims gave incorrect findings. The result was more than 10 points below development. It failed the default-question threshold. |
| jev governs | Does a rule apply to a component outside its scope? A line prints at P 0.8 or more. | 31% of applicable components found. 1% of other components proposed. | 38% of applicable components found. 1% of other components proposed. |


No question goes to Jev without `TYPESAFE_API_KEY`.
`audit --dry-run` counts the questions and shows the data to send.
The data contains module names, docstrings, public names, internal imports, component ids,
sentences, invariants, and source lines at connections between components.
With a key, the dry run gets the model list to count cached answers. It sends no map data.

A `jev flow` question gets the source lines that use a name from the other component.
For a whole-module, namespace, or default import, systemap reads the import statement for the local name.
For TypeScript, it compares the last part of the import path with the file name of the target module.
A flow without such lines gets no question. The report gives the count of these flows.

Each Jev answer must agree with its question: a choice from the offered options,
and numbers from 0 to 1. An answer that does not agree stops the command with a message.
The cache does not keep that answer.

The cache is `.systemap/jev-cache.json`.
Its key includes the model, release date, state, and question.
A map without changes uses cached answers at no additional cost.
A new model release causes new questions.
If the model list is not available and the cache has every answer for the last known
release, the command uses the cache. The usage line says so.

Audit answers use `[judgement] answered` with `item`, `items`, or a kind such as
`"jev flow"`. `audit` reads only answers for the kinds in its report.
A kind excluded from the report does not make its answer stale.
`judgement` ignores all audit answers.

The `jev mis-fold` and `jev owner` lines do not contain the component that Jev selects.
The detail row gives that component. Thus a new model release that changes only that component
does not open an answer again. Earlier versions put that component at the end of the line,
for example `jev mis-fold: Writer claims pkg.emit, which reads like Reader`.
An answer with the earlier line text matches the current line, with the same evidence digest.

`systemap triage "<issue>"` gives the three components likely to change in an
issue fix. The report includes their modules and adjacent components.
On 80 closed issues from two repositories, the component of the pull request with the fix was first
in 80% of predictions. It was in the first three in 88%.

With the key set, `delta` automatically sends questions to Jev.
`--jev` explicitly sends questions and gives a reason if the request cannot complete.
`--no-jev` sends nothing.
If delta has no question for Jev, it sends nothing and prints no Jev line.

Jev answers are suggestions for source examination. They are not evidence.
They do not change the delta lines or the exit code.
Thus a run with Jev, a run without a key, and a run in CI give the same result.
The suggestions print under their own heading.
If Jev does not answer, a `delta --jev:` line gives the reason under a different heading.

Jev examines removed modules that delta did not pair with added modules.
Delta first compares source, public names, and filenames.
A pair that Jev selects with confidence of at least 0.8 prints as a `jev move` line, for example
`jev move: pkg.ledger -> pkg.accounts.book (read as the same module by Jev, confidence 0.94)`.
Jev also suggests a component for each module that no component claims, as a `jev owner` line.

With earlier prompts on Python repositories, delta found 66 renames.
Jev selected 17 more pairs, and 16 of them were correct.
An agent wrote reference labels from commits without Jev's answers.
The records are in `bench/jev`.

A `move candidate` line has a necessary action while a component specifies the removed module
in `implemented_by`. It also has a necessary action while an added module has no claim and no ignore.
Read the two source files. Then change the claims.
The line then moves to the changes with no necessary action.

`suggest --jev` groups modules from pair answers.
Pairs have an import connection or the same package.
Its groups were better than package-only groups on three of five development maps.
They were not better on the other two.
The measured first-map run saved no turns.
Thus, the command stays optional.

Without a key, `judgement` prints an audit hint to stderr.
`delta` prints a hint when a module was removed and another was added.
Each hint gives a result that was measured with earlier prompts on Python repositories.
`[jev] enabled = false` stops the hints and automatic delta questions.

## What do you do above forty components?

A large repository can exceed the capacity of one readable canvas.
Above approximately forty components, each layer can contain almost all
components. Layer selection then gives little separation.

A component can have `map="gateway.py"`.
This path is relative to its model file.
The target module exports `MODEL` and `MEANING`.
The nested map shows the parent component's internal structure.

Each parent module must have one claim, without duplicates, in the nested map.
No extra module is permitted.
Symbol claims are permitted.
Empty package markers are excluded.
Nested actors must be components from the parent map.
Coverage counts the parent component one time.

The nesting rule rejects differences and shows each module or actor.

Commands use all maps in the map tree:

- `check` executes all rules on each map.
  A nested finding has its map id, as in `Gateway: map layout: clean ...`.

- `refresh` and `render` write one page per map.
  The top page is `docs/map/index.html`.
  The nested page is `docs/map/Gateway/index.html`.
  Each page has a link to the other.

- `figure --map Gateway` renders one map.
  A `[[figures]]` entry also accepts `map`.

- `place` writes positions in each model file.

- `describe` and `judgement` use map-id prefixes.
  An `item` answer contains the printed line.
  A family answer can apply to all maps.

- `delta` compares each map's claimed modules.
  A moved module shows its component and model file.

- `suggest` shows maps above forty components.
  It lists the components with the most modules as possible nested maps.

A second nested level uses an id such as `Gateway/Routes`.
The self-map in the recorded experiment had no nested map.
Its 18 components were below the threshold.
The fixture in [`tests/test_nested.py`](tests/test_nested.py) has five top-level
components. Two open nested maps.

## What does a model contain?

The agent writes one model file in Python syntax with the frozen dataclasses of `systemap`.
systemap reads the file as data. It does not run the file as Python code.
This example contains two components and one flow from the self-map.
A model does not declare the standard flow kinds.
The page derives standard layers.

```python
from systemap import Component, Flow, Meaning, Model, Region

MODEL = Model(
    canvas=(900, 420),
    containers=(),
    regions=(Region("gather", "GATHER", (24, 40, 400, 340)),
             Region("draw", "DRAW", (460, 40, 416, 340))),
    components=(
        Component(id="FactsExtractor", region="gather",
                  does="Reads the package syntax tree and writes facts.",
                  implemented_by=("systemap.extract",), entry="build"),
        Component(id="Schematic", region="draw",
                  does="Renders components, routes, and the interaction script.",
                  implemented_by=("systemap.schematic", "systemap.theme"), entry="render"),
    ),
    flows=(Flow("FactsExtractor", "Schematic", "map.json", "data"),),
    flow_kinds=(),
)

MEANING = Meaning(
    plain={"FactsExtractor": "what reads the code", "Schematic": "what renders the map"},
    relations={("FactsExtractor", "Schematic"):
               "The schematic reads module facts to show flow evidence for mapped components."},
)
```

The example has no `x` or `y` values.
`systemap place` writes these positions.
After component additions or removals, `systemap place --all` writes new
positions. A component with `pinned=True` keeps its selected position.

A model file can contain only these statements:

- The module docstring and `from __future__ import annotations`.
- `from systemap import ...` or `from systemap.model import ...` for the model classes
  and for `AGENT_KINDS`, `KINDS`, and `STANDARD_KINDS`.
- `import NAME` for the file `NAME.py` in the same directory, such as `import journeys`.
  `NAME.VALUE` gives a value from that file. The same rules apply to that file.
  systemap refuses a symbolic link to a file outside the directory, and an import cycle.
- `NAME = value` and `NAME: annotation = value`. systemap does not read the annotation.
- A type alias for annotations, such as `Steps = tuple[Step, ...]`.

A value is a `str`, `int`, `float`, `bool`, or `None` constant, a minus sign before
a number, or a `tuple`, `list`, `set`, or `dict` of values.
A value can also be a call of a model class with positional and keyword values,
or a name that an earlier statement in the same file defines.
systemap refuses all other syntax before it makes a value. Examples are functions,
classes, comprehensions, f-strings, operators, indexes, `**` and `*` in a call, and other imports.
The message gives the file, the line, and the refused syntax.

The reader also has limits: 512 KiB and 16 files for one model with the files that it imports,
100,000 values, 32 levels of nested values, and 8,000,000 parts and characters in one value
when each name in it is written out. Move a part of a larger map into a nested map.

If you know that the code in a repository is safe, set `SYSTEMAP_TRUST_MODEL_CODE=1`
in the environment of the command. Then systemap runs each model file as Python code,
as version 2.0 did. Only the value `1` gives this permission.
systemap does not read this permission from `systemap.toml`, because the repository controls that file.

The full schema and examples are in
[`SKILL.md`](src/systemap/skill/SKILL.md) and its
[`references/`](src/systemap/skill/references/).

## Which command do you use?

All commands accept `--root DIR` before or after the command.
This option shows a project outside the current directory.
Exit codes are `0` for current, `1` for stale or rejected, and `2` for unusable
configuration, model, or option value.
The line after an error tells you which input to correct.
The input is a command option, `systemap.toml` or the model module, a `tsconfig.json` file, or a Git ref.

### `systemap init [--no-ci | --strict-ci]`

Writes `systemap.toml`, an initial model, the skill directory, and a GitHub
workflow. The workflow pins this version.
The command does not replace files.
It prints the instruction for your agent.
`--no-ci` does not include the workflow.

The workflow has the variable `SYSTEMAP_CI`. Its default value is `advisory`:
a map finding gives a warning annotation, and the job passes.
With `--strict-ci`, the value is `strict`: a map finding makes the job fail.
You can change the value in the workflow file later.
If systemap cannot run (exit code 2 or more), the job fails with both values.

If the repository has no Python package and a directory has a `tsconfig.json` file,
`init` selects TypeScript.
If the repository root has no `tsconfig.json` file, `init` writes no package roots.
Then set `[package_roots]` for each application package.

### `systemap extract [--check]`

Reads the source tree and writes `docs/map/map.json`.
Module records contain public surface, public names, internal imports, external
imports, test references, and entry points.
Package `__init__` records include re-exports.
The other commands read this file.

- `--check` exits 1 if stored facts differ from the source tree.
  It also exits 1 if a model claim names a module that the source tree does not have.
  The report gives the two problem groups separately.
  For stale facts, run `systemap extract`.
  For a model claim, correct the model. A new extraction does not correct it.

### `systemap facts`

Prints stored facts one view at a time.
With no option, it prints the extraction summary.

- `--modules` prints one row per module.
  Each row gives the first docstring sentence and counts of names, imports,
  and tests.

- `--docstrings` prints the first sentence only.

- `--module NAME` prints the module's docstring, names and kinds, imports,
  importers, external imports, and test count. It does not print test names.

- `--names NAME` prints public names and kinds.

- `--entry-points` prints entry points and their targets.

- `--external` prints third-party imports and their importers.

- `--imports NAME` prints imports and importers for one module.

### `systemap place [--all] [--print] [--keep-order]`

A component must have a position before you render the map.
This command writes positions for unpositioned components on all maps.
The command keeps positions already in the model.
Only `x=`, `y=`, boxes, and the canvas change.

Regions use a two-column grid with routing corridors.
The search selects the region order with the best score.
Barycenter sweeps through flows select component order within regions.
With six or fewer regions, the search tries every order.
For more regions, it uses a greedy start and pairwise swaps.

A bend estimate scores each candidate.
The router renders the best twelve estimates and the model's listed order.
It scores label collisions, rejected routes, bends, and length, in that order.
The report gives the selected order and score:

    region order: layout, contracts, ...; 40 bends, 7,909 units; 720 orders tried, 13 routed

The procedure is deterministic and uses only the standard library.

- `--all` writes new positions except for `pinned=True` components.
  Use it after you add or remove components.

- `--keep-order` uses the listed region order without a search.

- `--print` prints positions without file changes.

### `systemap render [--check] [--base REF]`

Writes the page from the facts and model.

- `--check` exits 1 if the page is stale.

- `--base REF` adds a change map relative to that revision.
  The page link `#changes`, for example `index.html#changes`, opens the Changes view.
  The Changes panel lists the map changes: the components, flows, sequences, and rules
  that the change added, removed, or changed in the model.
  The list compares the committed model at the merge base with the model on disk.
  A new digest for the same cited module or symbol is not a flow change.
  If the base model does not load, the panel gives the reason.

### `systemap check [--brief]`

Executes all rules on all maps.
A rejected map causes exit 1.
Each finding gives a correction.
Two rows below a rejected rule give its effect and the necessary action.

- `--brief` does not include these two rows.

### `systemap figure --out FILE`

Uses the page generator to render one figure for a document.

- `--components A,B` renders a plan's reach.

- `--base REF` renders a change.

- `--layer ID` renders that layer's flows and all components.
  The legend contains only that layer.

- `--map ID` selects a nested map.

- An `--out` filename with a `.svg` suffix writes the drawing without a frame.

### `systemap refresh`

Executes extraction and the checks, and renders the page and the configured figures,
in dependency order. Then it does a check of the written outputs.
A result without changes prints
`map: The page agrees with the rendered model fields and the facts.`
A rejected check causes exit 1, and the command renders nothing.
`-q` or `--quiet` prints only errors and check results.

### `systemap suggest [--jev]`

Proposes the first module groups for revision.
From facts alone, it gives one component per package with two or more modules.
It lists modules and imports across proposals.
With a model, it also shows maps above forty components and large
components that can become nested maps.

- `--jev` uses Jev's module-pair answers instead of package groups.
  Set `TYPESAFE_API_KEY` for this option.

### `systemap judgement [--strict] [--kind KIND] [--verbose] [--brief]`

Prints the second-pass findings.
These include single-module components, possible incorrect assignments, missing
sentences, thin layers, uncovered entry points, crossing imports, unreviewed
flows, source records outside the flow endpoints, stale component source reviews,
and model SDK imports outside agents.
A line after the findings counts the component source reviews by state: current, stale, and missing.
A crossing-import row gives one component pair and a module count.
Accepted answers under `[judgement] answered` suppress findings.
The first finding of each kind has rows about its effect and necessary action.

- `--strict` exits 1 while a finding is open. If not, the exit code is 0.

- `--kind KIND` prints one kind.

- `--verbose` prints imports below each crossing-import row.

- `--brief` does not include the two explanation rows.

### `systemap delta --base REF [--head REF] [--comment FILE --pr N] [--jev | --no-jev]`

Compares extracted facts from two Git commits.
Python and TypeScript use the configured language adapter, as the working tree
does. The report shows moved, added, and removed modules with their
components and model files.
Delta reads the committed files. The Git attributes `export-subst` and
`export-ignore` do not change them.

Findings include unclaimed new modules, removed entry and interface names,
new crossing imports without flows, and flows with lost evidence.
Each finding gives a correction.
An answer for a new crossing import must agree with the `judgement` rule.
An exact answer must have the current evidence digest. A family answer must have `policy = true`.
The exit code is 0 if the map is current, or 1 if it is necessary to update the map.

The lines with a necessary action come first, under `The map needs an update (N):`.
The lines with no necessary action follow.
If no line has a necessary action, the last line starts with `The map is current.`
If not, the last line tells you to do the actions and gives the next command.

Before its last line, the text report gives adjacent components.
These have flows to the component with the most changes.
This list gives context, not a finding.
The list does not print if the component with the most changes connects to more
than one-third of the map.

- `--comment FILE --pr N` writes the pull-request comment to `FILE` if `[delta] page_url` is set.
  The comment has one link to the Changes view of the page for pull request `N`.
  If it is necessary to update the map, one more line says so and gives the number of lines.

  The first comment line is `<!-- systemap delta -->`. CI finds the comment with it and changes that comment.
  Without `page_url`, the command writes no file.
  The comment does not change the delta lines or the exit code.

- `TYPESAFE_API_KEY` or `--jev` enables Jev suggestions for modules with changed
  names and content, and for unclaimed modules. The suggestions do not change
  the delta lines or the exit code.

- `--no-jev` sends nothing.

- The Jev cost goes to stderr.

### `systemap describe`

Prints measured map geometry for an agent that cannot see the page.
The report includes position counts, components per region, region order,
layout score, bends and length for each flow path, label gutters, and gutter seat usage.
It also gives evidence-state counts, and the component and flow counts for each layer.
Position counts distinguish pinned, placed, and temporary display positions.
Flow paths with the worst geometry come first.
A gutter line counts the labels that the flow paths put in that gutter.

The sequence section gives steps, the entry point where each sequence starts, steps without import
evidence, unconfirmed agent drafts, and covered entry counts.

### `systemap audit [--dry-run] [--kind KIND]...`

Sends questions about semantic claims to Jev.
The finding kinds are `jev mis-fold`, `jev owner`, `jev sentence`, and
`jev governs`. `--kind "jev flow"` also sends questions about flow claims.
Answers use the cache.
The command exits 0 for a completed report, or 1 if it cannot complete.
Set `TYPESAFE_API_KEY` before you run the command.

- Use `--kind KIND` again to select another question kind.

- `--dry-run` lists proposed questions and does not send them.

### `systemap plan "<task>" [--check ID] [--base REF]`

Predicts components likely to change in a task.
Jev compares the task with each component's function.
The projection includes components with probability of at least 0.05.
The report includes flows, sequences, and rules for each component.
It lists six of each, then gives a count.
The projection is in `.systemap/plans/<id>.json`.

The measured threshold of 0.05 is in `bench/jev/plan_eval.py`.
Set `TYPESAFE_API_KEY` before you run the command.

- `--check ID --base REF` compares the projection with changed components
  since `REF`. The default base is `origin/main`.
  It exits 1 for changed components outside the plan.

- `-` instead of a task reads stdin.

### `systemap triage TEXT`

Predicts the three components likely to change in an issue fix.
The report includes their modules and adjacent components.
`-` reads stdin. The text limit is 2,000 characters.
Set `TYPESAFE_API_KEY` before you run the command.

### `systemap journeys [--limit N] [--dry-run]`

Writes a sequence for an entry point with no examined sequence.
For multiple same-kind entries in one component, it can write a grouped
sequence. Its `covers` field records the examined entry identities.
An examination must add a new entry to that list before the entry counts as covered.

`[agent] command` reads source from the entry point.
The agent gives components in the execution path and a sentence for each step.
Each request contains the language policy of the `[writing]` profile.
The command rejects a step with no authored flow and gives a finding.
The command does not write that step.

Accepted sequences enter the model with `drafted=True`.
The command writes them into the `JOURNEYS = (...)` tuple of the model.
The tuple can have a type annotation, as in the model from `init`.
`judgement` prints `drafted journey` until a person examines the sequence and
removes the mark.

By default, the command writes no more than three sequences.

- `--limit N` writes no more than N sequences.

- `--dry-run` lists proposed sequences without file changes.

- With no `[agent] command`, the command also lists proposals and gives the
  reason it cannot write them.

### `systemap history [--since WHEN] [--every DAYS] [--top N] [--ref REF]`

Reads source samples across repository history.
The defaults are `1 year ago`, one sample every 14 days, and the five largest
windows (`--top` default 5). Each window compares two samples.
Facts use the cache `.systemap/facts/<sha>-<scope>.json`.

Each window shows module and entry additions or removals, component size
changes, and new crossing imports.
It shows the commits that added new modules.
All samples use the component assignments in the selected map.
Thus, a moved module counts under its component in the selected map.
TypeScript samples include `.ts`, `.tsx`, tests, and package entry points.

- `--ref REF` starts from that branch or commit instead of `HEAD`.

### `systemap explain [KIND]`

Prints one finding kind's meaning, effect on the map, and necessary action.
With no kind, it lists all printed kinds and their one-line meanings.
An unknown kind causes exit 1.

### `systemap serve [--port 8765]`

Supplies the output directory through HTTP on the loopback address.
The command prints the URL.
If the port is not available, the command exits 2.
Then use `--port 0` to select an available port, or give a different port.
The server answers only a request whose Host header is `127.0.0.1` or `localhost` with the server port.
Thus a web page that makes its own domain name point at 127.0.0.1 cannot read the map.
`systemap live` has the same rule.

### `systemap live [--port 8765] [--base REF] [--no-watch] [--json]`

Renders the page of the working tree and supplies it through HTTP on the loopback address.
The facts come from the source files in memory. The models come from the model files.
The command writes the pages and `change.svg` into a temporary directory and deletes it when it stops.
It does not write the output directory, the facts file, or a tracked file.
For the comparison, it can add the facts of the merge base to the cache in `.systemap/facts/`,
as `systemap render --base` does.

Each time that the command renders the page, the page gets a new version number.
The command renders one version at a time.
If a request occurs while the command renders, the command renders one more version after the current version.
If the command cannot render a version, the last page stays and the command gives the error.
Examples are a model file that does not load, a source syntax error, and an extraction error.
If the first version fails, the page gives the error.

- `--base REF` sets the base of the Changes view.
  The default is the first of `origin/HEAD`, `origin/main`, `main`, `origin/master`, and `master`
  that has a merge base with HEAD. If no ref has one, the page has no revision comparison.
  The Changes view compares the working tree with that merge base.
  The comparison includes the commits since the merge base, the edits that are not in a commit,
  and the untracked files that Git does not ignore.

- Without `--no-watch`, the command scans the configuration files, the model files,
  and the source and test files one time each second.
  When a scan finds a change and the next scan finds no more change, the command renders the page again.

- `--no-watch` stops the scan. Then the command renders the page again only after `POST /refresh`.

- `--json` writes one JSON object on a line for each event. Without it, the command writes short text lines.

- `--port 0` selects an available port. If the port is not available, the command exits 2.

The browser loads the page again after each version and keeps the view of the reader.
DESIGN.md gives the parts of the view that the page keeps.

| Request | Answer |
|---|---|
| `GET /` | The page of the top map. Nested maps are at `<map id>/index.html`. |
| `GET /change.svg` | The change figure. If the comparison has no change, the system figure. |
| `GET /events` | Server-sent events. `rendered` with `{"version": N}` after each version. `error` with `{"version": N, "text": "..."}` if the command cannot render a version. A new connection first gets `rendered` with the version of the page on disk. |
| `POST /refresh` | Asks for a version. The answer is 202 with `{"queued": true}`. |
| `GET /status` | The state as JSON: `version`, `state` (`rendering`, `ready`, or `error`), `seconds`, `updates`, `lines` (each with `text` and `action`), `components`, `error`, `url`, `svg`, `svg_bytes`, `base`, and `comparison_base`. |

`version` in `GET /status` is the number of the last version that started.
`updates` is the number of map update lines: the `systemap delta` lines that need an action,
for the working tree and the merge base. `action` is the action of the line kind from `systemap explain`.
`components` are the changed components of the top map.
`svg` is the absolute path of `change.svg`. `seconds` is the time of the last good version.

| JSON line | When |
|---|---|
| `{"event": "serving", "url": "...", "base": "...", "comparison_base": "..."}` | One time, when the server is ready. |
| `{"event": "rendering", "version": N}` | When a version starts. |
| `{"event": "rendered", "version": N, "seconds": S, "updates": K, "components": [...], "svg": "...", "svg_bytes": B}` | When a version is on the page. |
| `{"event": "error", "version": N, "text": "..."}` | When the command cannot render a version. |
| `{"event": "stopped"}` | When the command stops after Ctrl-C or SIGTERM. The exit code is 0. |

On this repository, one version takes about 7 to 8 seconds.
Thus the command waits until the files stop changing before it renders the page.
[bench/jev/README.md](../bench/jev/README.md) gives the measurements.

### `systemap skill [--dir PATH] [--print]`

Reinstalls the skill directory from `init`: `SKILL.md` and `references/`.

- `--dir PATH` writes to another directory.

- `--print` writes `SKILL.md` to stdout.

## What can you configure?

Use `systemap.toml` at the repository root or `[tool.systemap]` in
`pyproject.toml`. All keys are optional.
Unknown keys are rejected.

| Key | Default | Meaning |
|---|---|---|
| `language` | `python` | The source language. Select `python` or `typescript`. The `[writing]` table sets the writing rules for map text. `init` detects an unambiguous TypeScript repository. TypeScript must have the `systemap[typescript]` extra. |
| `name` | `[project] name`, Git repository directory, then directory name | The page title. |
| `[package_roots]` | Python packages, or `src` then repository root for TypeScript | `"path" = "module name"`. Discovery includes a directory with the name `build` or `dist` if it has an `__init__.py` file. Each configured path must be a directory. A key after the `[package_roots]` line is part of this table, so put the top-level keys above it. |
| `tests_dir` | All directories with the name `tests` or `test` | One directory or a list. Import references associate tests with modules. |
| `test_patterns` | none | Additional repository-relative test globs. Extraction and `delta` use the same patterns. |
| `model` | `map/model.py` | The model file that gives `MODEL` and `MEANING`. systemap reads it as data and does not run it. A file in the same directory can contain sequences or flows (`import journeys`). [What does a model contain?](#what-does-a-model-contain) gives the permitted syntax. |
| `out_dir` | `docs/map` | The directory for facts, pages, and figures. |
| `facts_file` | `map.json` | The facts filename inside `out_dir`. |
| `spec_path` | none | A document with `##` headings that identify specification sections. |
| `planes` | none | Second-level package names with different planes in the facts. |
| `outside_label` | `EXTERNAL COMPONENTS` | The index heading for actors outside all regions. |
| `[coverage]` | none | `ignore = [{module = "pkg.mod", reason = "..."}]` excludes a module. `module = "pkg.sub.*"` excludes a subtree. An ignore must have a reason. No ignore is necessary for empty package markers. |
| `[facts]` | none | `model_sdks = [...]` adds import names to the built-in SDK list. A `-` at the start removes a built-in name (`"-google.adk"`). |
| `[flows]` | none | `observed_by = ["subprocess", "queue", ...]` identifies mechanism words as structural evidence. A word does not show evidence for a flow. |
| `[judgement]` | none | `answered = [{item = "<a judgement line>", reason = "...", evidence = "<SHA-256 digest>"}]` records an exact answer. `items = [...]` uses one digest for a group. Family forms are `crossing = ["A", "B", ...]`, `crossing_into = "A"`, `crossing_from = "A"`, `kind = "single module"`, and `module_sdk = "google.adk"`. They must have `policy = true`. `reviewed = ["<line>", ...]` records the baseline. The report counts new matches. All answers must have reasons. The report identifies stale answers. Audit kinds use this table too. This includes `"jev flow"`. |
| `[jev]` | `model = "jev-latest"`, `cache = ".systemap/jev-cache.json"`, `enabled = true` | The model and cache for `audit`, `triage`, `plan`, `delta`, and `suggest --jev`. `enabled = false` stops automatic delta questions and hints. |
| `[agent]` | `command` unset, `timeout = 300`, `cache = ".systemap/agent-cache.json"` | The command for sequence generation. It reads the question from stdin, for example `command = "claude -p --output-format json"`. With no command, nothing executes and the reason is printed. |
| `[delta]` | none | `page_url = "https://example.org/pr-{number}/"` gives the URL of the map page that the repository publishes for each pull request. The pull request number replaces `{number}`. With this value, `systemap delta --comment FILE --pr N` writes a comment with one link to the Changes view of that page. Without it, the command writes no comment. The URL must start with `https://` or `http://`. It must not contain `#`, because the link adds `#changes`. |
| `[writing]` | `profile = "plain"` | The writing profile for the map text that a person reads. `plain` selects the common writing rules of the skill's language policy. A person or a program can examine these rules without a dictionary. `asd-ste100` also selects the full ASD-STE100 Issue 9 rules. These rules need the official ASD dictionary. The skill reads this value. `systemap journeys` puts the policy of this profile in each agent request, so a different profile gets a new answer. A different value or key gives a configuration error. `init` writes `profile = "plain"`. |
| `[theme]` | `dark` | Color-token overrides. `scheme = "dark"` (Ink) or `scheme = "light"` (Paper) selects the default palette. The page offers both palettes. The earlier names `warm`, `graphite`, and `clay` give a configuration error. `[theme.light]` overrides one palette. `[theme.layers]` sets a color per layer ID, also for standard IDs. `[theme.marks]` selects a mark per agent kind. The `bg`, `raised`, `change`, and `reach` tokens, the `[theme.layers]` values, and the `layer_palette` items must be colors in the form `#RRGGBB`. |
| `[[figures]]` | none | Figures for `refresh`. Keys are `out`, `mode` (`system` or `reach`), `components`, `caption`, `interactive`, `layer`, and `map`. `layer` selects that layer's flows. `map` identifies a nested map. An `out` with `.svg` suffix writes the drawing alone. |

The environment of a command can set two values. A repository file cannot set them.

| Variable | Meaning |
|---|---|
| `TYPESAFE_API_KEY` | The key for Jev questions. Without it, no question goes to Jev. |
| `SYSTEMAP_TRUST_MODEL_CODE` | With the value `1`, systemap runs the model files as Python code. Without it, systemap reads them as data. Set it only for a repository with safe code. |

TypeScript discovery does not include `.d.ts`, `.d.mts`, and `.d.cts` declaration files.
The `external` imports do not include Node.js built-in modules, such as `node:fs` and `path`.
A re-export from an npm package keeps the package name and gives no unknown record.
A missing npm package in `tsconfig.json` `extends` gives an `unknown surface`
finding. Extraction continues with the compiler options that it can read.

In each file of the `extends` chain, `${configDir}` at the start of a path uses
the top-level `tsconfig.json` directory. This applies to `baseUrl`, `paths`,
`rootDir`, and `outDir`, as it does in `tsc`.
A plain relative path uses the directory of the file that declares it.

Without `rootDir`, the source root follows the project's `tsc` rule:

- TypeScript 5 uses the longest common directory of selected non-declaration
  files. The `files`, `include`, and `exclude` options select files.
  These files include tests.

- TypeScript 6 and later use the `tsconfig.json` directory.

- `composite` uses the `tsconfig.json` directory on all versions.

The version comes from `node_modules/typescript/package.json`, then the
`typescript` range in `package.json`.
If the two files do not give a version, systemap tries the two roots.
A compiled target maps to a module only if one root gives a match and the other does not.
Two matches leave the target unmapped.

`check` prints unknown records without rejection.
Each unknown record must have a correction or accepted answer under
`[judgement] answered` before `judgement --strict` accepts it.
