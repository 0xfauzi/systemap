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
| interface | The leading identifier of an `interface` is absent from the component's public names, including re-exports. The identifier ends at `(`, `.`, `->`, or whitespace. Both parts of `Class.method` must be available. The finding gives the nearest defined name. |
| nesting | A nested map claims an extra module, omits a parent claim, or claims a module twice. Its actor is absent from the parent map. An actor opens a map. |
| placement | A component is outside its region, or components have an overlap. A flow kind is neither standard nor declared. Two flows have the same ordered pair. A context or tool flow has an incorrect agent endpoint. That endpoint must be an agent or a `calls_model` component. A flow or invariant identifies an absent item. Two invariants have the same number. |
| routes | A route crosses an unrelated component or an unrelated region. |
| labels | Text does not fit or touches an obstacle. The conditions are below. |
| type size | Text is smaller than 11 px at native scale. |
| meaning | A sentence, verb, override, or sequence step identifies an absent item. A flow has no sentence. A custom layer uses a standard id. |
| wheel | Relationship-wheel labels touch each other or the center. |
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
Exit code `2` shows unusable configuration or an unusable model.
To keep a module out of map coverage, add an ignore under `[coverage]`.
Each ignore must have a reason.

The check compares components with the code.
An import alone cannot show a flow's direction or artifact.
Rendering and checking use the evidence for the stored source snapshot state:

| Evidence | Condition | Indication |
|---|---|---|
| `observed` | `source_refs` resolve to extracted source hashes. `review_digest` agrees with the current flow claim and sentence. | A solid line. The panel shows a source review for the stored snapshot. |
| `structural` | An import connects the components, a module is shared, or a configured mechanism is in the sentence. These facts do not show direction, artifact, or execution. | A dashed line. The panel identifies the structural fact. `judgement` asks for source review. |
| `external` | An actor is at one end. The flow crosses the code boundary. | A solid line. The panel identifies the endpoint outside the source code. |
| `declared` | No source review or structural fact gives evidence for the flow. | A dashed line. `systemap judgement` prints a `declared flow` finding. |

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
| model sdk | A module imports a model SDK or agent framework. Its component is neither an agent nor `calls_model`. Examples are anthropic, openai, and google.adk. `[facts] model_sdks` can add or remove names from the built-in list. |

Without `--strict`, the report exits 0.
With `--strict`, it exits 1 while a finding is open.
`[judgement] answered` in `systemap.toml` contains recorded answers.
Accepted answers suppress findings and increase the answered count.
The report can print `judgement: 3 items for maintainer decisions, 21 answered`.
An answer with no matching finding is stale.

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
Before the second pass, `systemap suggest` gives a proposed grouping.
It gives one proposal for each package with two or more modules, plus imports
between proposals. Examine these proposals against the source.
A component must have one clear function. Module quantity alone does not identify a component.

An exact `item` or `items` answer includes `evidence = "<SHA-256 digest>"`.
When source or import evidence changes, the finding opens again.
`judgement` prints the current digest for examination.
An exact answer without evidence stays pending until source review.

A family answer is a standing policy and must have `policy = true`.
The report counts current matches and matches outside the optional
`reviewed = ["<line>", ...]` baseline.
A family answer without `policy = true` stays pending.

## What questions does Jev answer?

`systemap audit` is optional.
CI does not execute this command.
The command sends individual semantic questions to TypeSafe's Jev model.
It prints a finding when Jev's answer disagrees with the map.
The mechanical `judgement` rules use names and imports instead.

The development experiments selected thresholds on five mapped repositories in
`bench/jev`. Three holdout maps used the same thresholds: systemap, scorecard,
and a first map of httpie.
The table gives measured results from the recorded prompts.
This PR changes those prompts for ASD-STE100. The changed prompts have no new benchmark measurements.
Do not use the recorded scores as results for the changed prompts or your system.

| line | what it asks | development maps | holdout maps |
|---|---|---|---|
| jev mis-fold | The component for each module claim. A line prints when the claimed component has P < 0.05. | 95% of incorrect component assignments found. 4% of correct assignments gave incorrect findings. The word rule for `possible mis-fold` found 32%. | 93% found. 1% of correct assignments gave incorrect findings. |
| jev owner | The same question for a module without a component claim. One component prints at confidence 0.9 or more. Otherwise, three print. | 56% of modules get one component. 98% of those answers are correct. | 60% of modules get one component. 100% of those answers are correct. |
| jev sentence | Does the component sentence agree with its modules? A line prints below P 0.2. | 67% of incorrect sentences found. 1% of correct sentences gave incorrect findings. Small source changes can cause no finding. | 61% found. 2% of correct sentences gave incorrect findings. |
| jev flow | Does the code connection agree with the flow claim? A line prints below P 0.2. **Questions require `--kind "jev flow"`.** | 66% of incorrect claims found. 2% of correct claims gave incorrect findings. Evidence excludes instance calls. This exclusion can cause an incorrect finding. | 54% found. 4% of correct claims gave incorrect findings. The result was more than 10 points below development. It failed the default-question threshold. |
| jev governs | Does a rule apply to a component outside its scope? A line prints at P 0.8 or more. | 31% of applicable components found. 1% of other components proposed. | 38% of applicable components found. 1% of other components proposed. |


No question goes to Jev without `TYPESAFE_API_KEY`.
`audit --dry-run` counts the questions and shows the data to send:
module names, docstrings, public names, internal imports, component ids,
sentences, invariants, and source lines at connections between components.

The cache is `.systemap/jev-cache.json`.
Its key includes the model, release date, state, and question.
A map without changes uses cached answers at no additional cost.
A new model release causes new questions.

Audit answers use `[judgement] answered` with `item`, `items`, or a kind such as
`"jev flow"`. `audit` reads only answers for the kinds in its report.
A type excluded from the report does not make its answer stale.
`judgement` ignores all audit answers.

`systemap triage "<issue>"` gives the three components likely to change in an
issue fix. The report includes their modules and adjacent components.
On 80 closed issues from two repositories, the fixing PR's component was first
in 80% of predictions. It was in the first three in 88%.

With the key set, `delta` automatically sends questions to Jev.
`--jev` explicitly sends questions and gives a reason if the request cannot complete.
`--no-jev` sends nothing.
Jev examines removed modules that delta did not pair with added modules.
Delta first compares source, public names, and filenames.
A Jev pairing with confidence of at least 0.8 becomes a move.

The report can print `(read as the same module by Jev, confidence 0.94)`.

On renames in five repositories, the two methods together found 82 renames with source evidence.
Delta alone found 66. Of the 17 added pairings, 16 were correct.
An agent wrote reference labels from commits without Jev's answers.
The records are in `bench/jev`.
A move can change the report and exit code.

Jev also suggests a component for each unclaimed module.

`suggest --jev` groups modules from pair answers.
Pairs have an import connection or the same package.
It exceeded package-only grouping on three of five development maps.
It did not exceed that grouping on the other two.
The measured first-map run saved no turns.
Thus, the command stays optional.

Without a key, `judgement` prints an audit hint to stderr.
`delta` prints a hint when a module was removed and another was added.
Each hint gives a measured result.
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

Commands traverse the map tree:

- `check` executes all rules on each map.
  A nested finding has its map id, as in `Gateway: map layout: clean ...`.

- `refresh` and `render` write one page per map.
  The top page is `docs/map/index.html`.
  The nested page is `docs/map/Gateway/index.html`.
  Each page links to the other.

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

The agent writes one Python module with frozen dataclasses.
This example contains two components and one flow from the self-map.
Standard flow types do not have to be declared.
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

The full schema and examples are in
[`SKILL.md`](src/systemap/skill/SKILL.md) and its
[`references/`](src/systemap/skill/references/).

## Which command do you use?

All commands accept `--root DIR` before or after the command.
This option shows a project outside the current directory.
Exit codes are `0` for current, `1` for stale or rejected, and `2` for unusable
configuration or model.

### `systemap init [--no-ci]`

Writes `systemap.toml`, an initial model, the skill directory, and a GitHub
workflow. The workflow pins this version.
The command does not replace files.
It prints the instruction for your agent.
`--no-ci` does not include the workflow.

### `systemap extract [--check]`

Reads the source tree and writes `docs/map/map.json`.
Module records contain public surface, public names, internal imports, external
imports, test references, and entry points.
Package `__init__` records include re-exports.
The other commands read this file.

- `--check` exits 1 if stored facts differ from the source tree.

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

A component must have a position before rendering.
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

- `--layer ID` renders that layer's edges and all components.
  The legend contains only that layer.

- `--map ID` selects a nested map.

- An `--out` filename with a `.svg` suffix writes the drawing without a frame.

### `systemap refresh`

Executes extraction, checks, page rendering, and configured figure rendering,
in dependency order. Then it does a check of the written outputs.
A result without changes prints
"map: The page agrees with the rendered model fields and the facts."
A rejected check causes exit 1 and prevents rendering.

### `systemap suggest [--jev]`

Proposes a first grouping for revision.
From facts alone, it gives one component per package with two or more modules.
It lists modules and imports across proposals.
With a model, it also shows maps above forty components and large
components that can become nested maps.

- `--jev` uses Jev's module-pair answers instead of package grouping.
  Set `TYPESAFE_API_KEY` for this option.

### `systemap judgement [--strict] [--kind KIND] [--verbose] [--brief]`

Prints the second-pass findings.
These include thin components, possible incorrect assignments, missing
sentences, thin layers, uncovered entry points, crossing imports, unreviewed
flows, and model SDK imports outside agents.
A crossing-import row gives one component pair and a module count.
Accepted answers under `[judgement] answered` suppress findings.
The first finding of each kind has rows about its effect and necessary action.

- `--strict` exits 1 while a finding is open. If not, the exit code is 0.

- `--kind KIND` prints one kind.

- `--verbose` prints imports below each crossing-import row.

- `--brief` does not include the two explanation rows.

### `systemap delta --base REF [--head REF] [--format markdown] [--jev | --no-jev]`

Compares extracted facts from two Git commits.
Python and TypeScript use the configured language adapter, as the working tree
does. The report shows moved, added, and removed modules with their
components and model files.

Findings include unclaimed new modules, removed entry and interface names,
new crossing imports without flows, and flows with lost evidence.
Each finding gives a correction.
The exit code is 0 if no decision is necessary, or 1 if not.

The report ends with adjacent components.
These have flows to the component with the most changes.
This list gives context, not a finding.
The list does not print if the seed component connects to more than one-third of
the map.

- `--format markdown` prints the pull-request comment.

- `TYPESAFE_API_KEY` or `--jev` enables Jev pairing for modules with changed
  names and content. Jev also suggests owners for unclaimed modules.

- `--no-jev` sends nothing.

- The Jev cost goes to stderr.

### `systemap describe`

Prints measured map geometry for an agent that cannot see the page.
The report includes position counts, components per region, region order,
layout score, bends and length per edge, label gutters, and gutter seat usage.
It also gives evidence-state counts and components and edges per layer.
Position counts distinguish pinned, placed, and temporary display positions.
Edges with the worst geometry come first.

The sequence section gives steps, starting entries, steps without import
evidence, unconfirmed agent drafts, and covered entry counts.

### `systemap audit [--dry-run] [--kind KIND]...`

Sends questions about semantic claims to Jev.
The finding kinds are `jev mis-fold`, `jev owner`, `jev sentence`, and
`jev governs`. `--kind "jev flow"` also sends questions about flow claims.
Answers use the cache.
The command exits 0 for a completed report, or 1 if it cannot complete.
Set `TYPESAFE_API_KEY` before you run the command.

- Use `--kind KIND` again to select another question kind.

- `--dry-run` lists proposed questions without sending them.

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
A step with no authored flow is rejected with a finding.
The command does not write that step.
Accepted sequences enter the model with `drafted=True`.
`judgement` prints `drafted journey` until a person examines the sequence and
removes the mark. The default limit is three sequences per invocation.

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
| `language` | `python` | Select `python` or `typescript`. `init` detects an unambiguous TypeScript repository. TypeScript must have the `systemap[typescript]` extra. |
| `name` | `[project] name`, Git repository directory, then directory name | The page title. |
| `[package_roots]` | Python packages, or `src` then repository root for TypeScript | `"path" = "module name"`. |
| `tests_dir` | All directories with the name `tests` or `test` | One directory or a list. Import references associate tests with modules. |
| `test_patterns` | none | Additional repository-relative test globs. Extraction and `delta` use the same patterns. |
| `model` | `map/model.py` | The module that exports `MODEL` and `MEANING`. Its directory enters the import path during execution. Adjacent modules can contain sequences or region components (`import journeys`). Imported modules do not stay cached between executions. |
| `out_dir` | `docs/map` | The directory for facts, pages, and figures. |
| `facts_file` | `map.json` | The facts filename inside `out_dir`. |
| `spec_path` | none | A document with `##` headings that identify specification sections. |
| `planes` | none | Second-level package names with different planes in the facts. |
| `outside_label` | `OUTSIDE THE SYSTEM` | The index heading for actors outside all regions. |
| `[coverage]` | none | `ignore = [{module = "pkg.mod", reason = "..."}]` excludes a module. `module = "pkg.sub.*"` excludes a subtree. An ignore must have a reason. Empty package markers require no ignore. |
| `[facts]` | none | `model_sdks = [...]` adds import names to the built-in SDK list. A leading `-` removes a built-in name (`"-google.adk"`). |
| `[flows]` | none | `observed_by = ["subprocess", "queue", ...]` identifies mechanism words as structural evidence. A word does not show evidence for a flow. |
| `[judgement]` | none | `answered = [{item = "<a judgement line>", reason = "...", evidence = "<SHA-256 digest>"}]` records an exact answer. `items = [...]` uses one digest for a group. Family forms are `crossing = ["A", "B", ...]`, `crossing_into = "A"`, `crossing_from = "A"`, `kind = "single module"`, and `module_sdk = "google.adk"`. They must have `policy = true`. `reviewed = ["<line>", ...]` records the baseline. The report counts new matches. All answers must have reasons. The report identifies stale answers. Audit kinds, including `"jev flow"`, use this table too. |
| `[jev]` | `model = "jev-latest"`, `cache = ".systemap/jev-cache.json"`, `enabled = true` | The model and cache for `audit`, `triage`, `delta`, and `suggest --jev`. `enabled = false` stops automatic delta questions and hints. |
| `[agent]` | `command` unset, `timeout = 300`, `cache = ".systemap/agent-cache.json"` | The command for sequence generation. It reads the question from stdin, for example `command = "claude -p --output-format json"`. With no command, nothing executes and the reason is printed. |
| `[theme]` | warm | Color-token overrides. `scheme = "warm"`, `"graphite"`, or `"paper"` selects the default. The page offers all three. The 0.11 names `dark` and `light` still select graphite and paper. `[theme.paper]` overrides one scheme. `[theme.layers]` sets a color per layer id, including standard ids. `[theme.marks]` selects a mark per agent kind. |
| `[[figures]]` | none | Figures for `refresh`. Keys are `out`, `mode` (`system` or `reach`), `components`, `caption`, `interactive`, `layer`, and `map`. `layer` selects that layer's edges. `map` identifies a nested map. An `out` with `.svg` suffix writes the drawing alone. |

TypeScript discovery does not include `.d.ts` declaration files.
A missing npm package in `tsconfig.json` `extends` gives an `unknown surface`
finding. Extraction continues with the compiler options that it can read.

In each file of the `extends` chain, `${configDir}` at the start of a path uses
the top-level `tsconfig.json` directory. This applies to `baseUrl`, `paths`,
`rootDir`, and `outDir`, as it does in `tsc`.
A plain relative path uses the declaring file's directory.

Without `rootDir`, the source root follows the project's `tsc` rule:

- TypeScript 5 uses the longest common directory of selected non-declaration
  files. The `files`, `include`, and `exclude` options select files, including
  tests.

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
