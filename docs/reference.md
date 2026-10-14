# Reference

This document gives the rules, commands, and configuration keys.
[README.md](../README.md) gives the introduction.
If a check has a finding, first read its rule below.
The command descriptions and configuration keys follow the rules.

## What does `systemap check` reject?

`systemap check` executes the rules below.
Each finding appears under its rule with a correction.
The command exits 1 if a rule rejects the map.

| Rule | Rejected condition |
|---|---|
| coverage | No component claims a module, or two components claim it. An ignore identifies no module or only empty package markers. An empty marker is a Python `__init__.py` file or a TypeScript `index` file that holds no code. The rule automatically excludes these markers. |
| entry | A component claims no module or an absent module. Its modules do not define its entry name. An entry can also be the name or label of an entry point of its modules that does not start one public name. Stores and context components can have an empty `entry`. A component can also have an empty `entry` if its modules define no public name and start no entry point. A symbol claim (`"pkg.mod:name"`) identifies an absent module or name, or a module with no owner. |
| interface | The first identifier of an `interface` is absent from the component's public names and re-exports. An identifier can contain Unicode letters. It ends at the first character that an identifier cannot contain, such as `(`, `.`, `-`, or whitespace. Both parts of `Class.method` must be available. The finding gives the nearest defined name. |
| nesting | A nested map claims an extra module, omits a parent claim, or claims a module twice. Its actor is absent from the parent map. An actor opens a map. |
| placement | A component is outside its region, or components have an overlap. A flow kind is neither standard nor declared. A flow has the same component at the two ends. Two flows have the same ordered pair, and one of them has no `id`. Two flows have the same `id`, or an `id` contains a character other than a letter, a digit, `_`, `.`, or `-`. A context or tool flow has an incorrect agent endpoint. That endpoint must be an agent or a `calls_model` component. A flow or invariant identifies an absent item. Two invariants have the same number. Two regions or two containers have the same id, or a region and a container have the same id. |
| routes | A route crosses an unrelated component or an unrelated region. |
| labels | Text does not fit or touches an obstacle. The conditions are below. |
| type size | Text is smaller than 11 px at native scale. |
| meaning | A sentence, verb, override, or sequence step identifies an absent item. A sentence, verb, or override uses the `(SRC, DST)` key of a pair with two or more flows. A sequence step names such a pair with `edge`. A flow has no sentence, or its sentence contains only spaces. A step has no `say`. A custom layer uses a standard id. The heading of these findings is `map meaning`. |
| import rules | A resolved import is against an import rule of the model. The result of the rule is `fail`. A rule has a duplicate id, an unknown `kind` value, an unknown component, or an unknown invariant. The heading of these rule findings is `import rule fields`. |
| stale | Facts, a page, or a figure are older than the source tree or model. Each map has a page. |

A source module or test file that the extractor cannot read or parse does not reject the map.
systemap is not a syntax checker, and a parser limit must not stop `check` for correct source.
`check` prints such a module in the `source inventory unresolved` group, with the fix line of its cause.
Each result that reads the module is not known, and not a pass:

- The component that claims the module has no source review digest. Thus `judgement` gives a `stale source review` line for it.
- An import rule that reads the module gives `unknown`.
- A missing entry, interface, or symbol name of the component is not known. `check` and `delta` do not report it.

A meaning error, an import rule field error, or a placement error stops the check before it renders the map.
Then the `map layout` line says that the check did not render the map.
The `map layout` heading contains only the findings of positions, routes, labels, and text size.

An import rule can also have the result `unknown`.
This result occurs if no resolved import is against the rule, but the facts possibly do not contain all imports of a rule module.
`check` prints each `unknown` result as a warning and does not reject the map.
Set `unknown = "fail"` in `[rules]` to make `check` reject the map for this result.

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
| `external` | An actor is at one end. The flow crosses the code boundary. | A solid line. The panel identifies the endpoint outside the source code. The panel also shows the `source_refs` and each reference that does not resolve. `systemap review` refuses a reference that does not resolve. |
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
The facts file (`docs/map/map.json` by default) gives the `source_sha256` of each module in `components`.
`systemap review --flow 'SRC->DST'` writes the current `review_digest` of one flow.
For a flow with an `id`, use `systemap review --flow ID`.
It does not examine the claims for you. Examine the source before you record the values.

A source change gives a new `source_sha256`.
A change to the flow or its relation sentence gives a new `review_digest`.

## How do two flows connect one pair of components?

Each flow has an identifier. The identifier is the `id` of the flow.
A flow without an `id` has the identifier `SRC->DST`.
Thus, a model without ids keeps its digests, keys, and finding lines.

Two or more flows can connect one ordered pair only if each of these flows has its own `id`.
An `id` contains only letters, digits, `_`, `.`, and `-`.
In this example, the service sends two artifacts to the queue:

```python
FLOWS = (
    Flow("OrderService", "OrderQueue", "order", "data", id="submit-order"),
    Flow("OrderService", "OrderQueue", "cancel", "control", id="cancel-order"),
)
RELATIONS = {
    "submit-order": "The service puts a new order in the queue.",
    "cancel-order": "The service tells the queue to remove an order.",
}
STEP = Step(acts=("OrderService",), measures=(), flow="cancel-order",
            say="The service tells the queue to remove the order.")
```

The map shows each flow as a different line with its own label.
Each flow has its own sentence, `source_refs`, `review_digest`, and decision request.
A finding line names a flow with an `id` as `SRC -> DST [ID]`.
`systemap review --flow submit-order` writes the digest of that flow only.

The keys of `relations`, `layer_overrides`, and `verb_overrides` are flow identifiers.
A `(SRC, DST)` key is also correct, but only for a pair that one flow connects.
A sequence step names its flow with `flow="ID"`.
A step with `edge=(SRC, DST)` is correct only for a pair that one flow connects.
On the page, each flow in the map data has an `id` key with its identifier. The other keys do not change.

A sequence step can have `source_refs` in the same form as a flow.
Each record must resolve in the current facts.
Each record must be in a module of an acting or measured component of the step.
`systemap judgement` gives a `step source` finding for each record that does not agree.

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
| entry point X has no sequence (component C) | The identity of the entry point is not in the `covers` of an examined sequence. If more than 4 entry points of one kind in one component have no sequence, one line gives them, for example `entry point 6 routes into C have no sequence (component C)`. C is the component of the module that the entry point names. The function that it starts can be in a different component, for example a console script that names a function that its package imports. |
| crossing import | Module A in component P imports module B in component Q. No flow connects P and Q in either direction. |
| declared flow | A flow has no source review or structural evidence. Find source evidence or change the claim. |
| flow review | An import, shared module, or mechanism word is available. Direction and artifact must have a source review. |
| no endpoint source | A flow has `source_refs`, but no reference is in a module of its source or target component. Add a reference from an endpoint module or change the flow. |
| step source | A record in the `source_refs` of a sequence step does not resolve in the current facts. Or, the record is in no module of an acting or measured component of the step. Cite a current record or change the step. |
| stale source review | A component has a `source_review` digest that is not the current digest of its source and claims. Examine the source and the claims again. Then record the current digest with `systemap review ID`. |
| missing source review | Only with `[judgement] require_reviews = true`. A source component has no `source_review` digest. Examine the source and the claims. Then record the digest with `systemap decisions` or `systemap review ID`. |
| model sdk | A module imports a model SDK or agent framework. Its component is neither an agent nor `calls_model`. Examples are anthropic, openai, and google.adk. `[facts] model_sdks` can add or remove names from the built-in list. |

Without `--strict`, the report exits 0.
With `--strict`, it exits 1 while a finding is open.

Each source component has one review state:
`missing` (no `source_review`), `stale` (`source_review` is not the current digest), or `current`.
`systemap delta` and `systemap judgement` use the same state.
A stale review is a `stale source review` finding, so `judgement --strict` fails on it.
A missing review is not a finding. Many maps have no `source_review` values, and these maps pass `judgement --strict`.
With `[judgement] require_reviews = true`, a missing review is a `missing source review` finding, so `judgement --strict` fails on it.
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

The evidence digest of a line contains only the evidence that the line names:

- For each component that the line names, the map claims of the component.
  These claims are the component fields, the plain name, and the flows, sequences, and invariants that name the component.
  The `source_review` value, the flow review digests, and the source digests in `source_refs` are not claims.
- For each module that the line names, and each module of a named component, the module facts and the source file.
- For a `crossing import` line, the imports between the two components and the source of the two modules of each import.
- For an `entry point` line, the entry point records of its modules. A record has the `kind`, `module`, `target`, and `name` values.
- For an `unknown surface` line of a module or a test file, the records of the line and the text of each cited source line.
  The records do not include the line number and the parser version.
  A new line above the statement does not change this evidence. A change to the statement changes it.
  A record without a line number uses the module evidence.

Thus a change to a different component, or to a `source_review` value, does not open the finding again.
A line that names no component and no module uses the full evidence: the model files and all modules.
The model files are the model file and each model file that it imports.
An `entry point` line with the full evidence also has all entry point records.

Migration from facts format 10: the evidence of an `unknown surface` line of a module or a test file changed.
Thus each of these exact answers is pending one time after the update.

Migration: the full evidence of a model file that imports other model files changed.
The evidence of each `entry point` line also changed.
Thus each of these exact answers is pending one time after the update.

Migration from systemap 1.2.0: an exact answer in 1.2.0 had no `evidence` digest.
Thus each exact answer from 1.2.0 is pending until you write its digest.
A family answer from 1.2.0 must also get `policy = true`.

`judgement` prints the new digest in the `pending answer` line.
Examine the source again. Then write the new digest in `evidence`.

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
| decision mis-fold | The component for each module claim. A line prints when the claimed component has P < 0.05. | 95% of incorrect component assignments found. 4% of correct assignments gave incorrect findings. The word rule for `possible mis-fold` found 32%. | 93% found. 1% of correct assignments gave incorrect findings. |
| decision owner | The same question for a module without a component claim. One component prints at confidence 0.9 or more. Otherwise, three print. | 56% of modules get one component. 98% of those answers are correct. | 60% of modules get one component. 100% of those answers are correct. |
| decision sentence | Does the component sentence agree with its modules? A line prints below P 0.2. | 67% of incorrect sentences found. 1% of correct sentences gave incorrect findings. Small source changes can cause no finding. | 61% found. 2% of correct sentences gave incorrect findings. |
| decision flow | Does the code connection agree with the flow claim? A line prints below P 0.2. **`audit` sends these questions only with `--kind "decision flow"`.** | 60% of incorrect claims found. 2.5% of correct claims gave incorrect findings. The evidence is the lines that the `call_sites` fact gives, with instance calls. | 52% found. 2% of correct claims gave incorrect findings. The result was within 10 points of development. No TypeScript result was measured, so the question is not a default question. |
| decision governs | Does a rule apply to a component outside its scope? A line prints at P 0.8 or more. | 31% of applicable components found. 1% of other components proposed. | 38% of applicable components found. 1% of other components proposed. |


No question goes to Jev without `TYPESAFE_API_KEY`.
`audit --dry-run` counts the questions and shows the data to send.
The data contains module names, docstrings, public names, internal imports, component ids,
sentences, invariants, and source lines at connections between components.
With a key, the dry run gets the model list to count cached answers. It sends no map data.

A `decision flow` question gets its source lines from the `call_sites` fact of the modules at the two ends of the flow.
The fact has the same form for Python and TypeScript. The context has these lines, in this sequence, until it has 60 lines:

1. The import lines and the lines that use a name from the other component.
2. The lines that read a property of a local name that gets its value from an imported name, such as `ledger.record(parts)` after `ledger = Ledger()`.
3. The line of the function or method that contains each of these lines.

Then the context gives at most 12 lines from the facts of the target modules.
These lines are the signature of each imported function, class, or method that a selected line uses, and the first sentence of each module description.
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
Two commands can write the cache at the same time.
A save holds a lock on the file `jev-cache.json.lock` and keeps the entries of the two commands.

Audit answers use `[judgement] answered` with `item`, `items`, or a kind such as
`"decision flow"`. `audit` reads only answers for the kinds in its report.
A kind excluded from the report does not make its answer stale.
`judgement` ignores all audit answers.

The `decision mis-fold` and `decision owner` lines do not contain the component that the provider selects.
The detail row gives that component. Thus a new model release that changes only that component
does not open an answer again. Earlier versions put that component at the end of the line,
for example `jev mis-fold: Writer claims pkg.emit, which reads like Reader`.
Previous versions also used the `jev` names.
An answer with the earlier line text matches the current line, with the same evidence digest.

`systemap triage "<issue>"` gives the three components likely to change in an
issue fix. The report includes their modules and adjacent components.
On 80 closed issues from two repositories, the component of the pull request with the fix was first
in 80% of predictions. It was in the first three in 88%.

`delta` sends questions to Jev only when you select Jev.
To select Jev, give `--decide`, or set `[jev] enabled = true` in `systemap.toml`.
`[jev] enabled = true` also must have `TYPESAFE_API_KEY`.
A key alone does not select Jev. Without a selection, `delta` sends no data to Jev.
If the request cannot complete, `--decide` gives the cause.
`--no-decide` sends nothing, also with `[jev] enabled = true`.
`--jev` and `--no-jev` are the previous names of these options.
If delta has no question for Jev, it sends nothing and prints no Jev line.

Jev answers are suggestions for source examination. They are not evidence.
They do not change the delta lines or the exit code.
Thus a run with Jev, a run without a key, and a run in CI give the same result.
The suggestions print under their own heading.
If Jev does not answer, a `delta --decide:` line gives the reason under a different heading.

Jev examines removed modules that delta did not pair with added modules.
Delta first compares source, public names, and filenames.
A pair that Jev selects with confidence of at least 0.8 prints as a `decision move` line, for example
`decision move: pkg.ledger -> pkg.accounts.book (read as the same module by Jev, confidence 0.94)`.
Jev also suggests a component for each module that no component claims, as a `decision owner` line.

With earlier prompts on Python repositories, delta found 66 renames.
Jev selected 17 more pairs, and 16 of them were correct.
An agent wrote reference labels from commits without Jev's answers.
The records are in `bench/jev`.

A `move candidate` line has a necessary action while a component specifies the removed module
in `implemented_by`. It also has a necessary action while an added module has no claim and no ignore.
Read the two source files. Then change the claims.
The line then moves to the changes with no necessary action.

`suggest --decide` groups modules from pair answers.
Pairs have an import connection or the same package.
Its groups were better than package-only groups on three of five development maps.
They were not better on the other two.
The measured first-map run saved no turns.
Thus, the command stays optional.

Without a key, `judgement` prints an audit hint to stderr.
`delta` prints a hint when a module was removed, a different module was added, and Jev is not selected.
The `delta` hint tells how to select Jev. It prints with a key and without a key.
Each hint gives a result that was measured with earlier prompts on Python repositories.
`[jev] enabled = false` stops the hints.

## Which decision provider answers the questions?

A decision provider is the model API that answers the questions of `audit`, `triage`, `plan`, `suggest --decide`, and `delta --decide`.
The default provider is TypeSafe's Jev.
The second provider is OpenAI Decisions (`POST https://api.openai.com/v1/decisions`, model `gpt-6-luna`, public beta).

To select OpenAI, give `--provider openai` to the command, or set `[decisions] provider = "openai"` in `systemap.toml`.
`--provider jev` selects Jev, also when the configuration selects OpenAI.
A key in the environment does not select a provider.
With `OPENAI_API_KEY` set and no selection, no request goes to OpenAI.
If the selected provider does not give the answers, the command gives the cause and stops. It does not use the other provider.

OpenAI gets the same data as Jev:

- The evidence of each question, as JSON text in the `input` field: module names, docstrings, public names, internal imports, component ids, component sentences, invariants, source lines at connections between components, and the issue or task text.
- The question text and the options: component ids with their sentences, or the new module names of `delta`.

Use `audit --dry-run --provider openai` to count the questions and the characters before you send them.

The thresholds of OpenAI come from the Jev bench rows in `bench/jev` (2026-10-13).
Each threshold was selected on the five development maps.
On the holdout maps, each figure had to be 10 points or less from the development figure.
A question type that did not satisfy this rule has no OpenAI threshold. The command does not send that question, and it gives the cause.

| question type | OpenAI threshold | development maps | holdout maps |
|---|---|---|---|
| decision mis-fold | not available | 82.1% found at P < 0.02, 3.1% incorrect findings | 61.5% found. More than 10 points below development. |
| decision owner | confidence 0.99 or more | 9.5% of modules get one component, 100% correct | 4.7%, 100% correct |
| decision sentence | P < 0.3 | 81.0% of incorrect sentences found, 1.3% incorrect findings | 75.0% found, 0.0% incorrect findings |
| decision flow | P < 0.02 (only with `--kind "decision flow"`) | 27 of 80 incorrect claims found (33.8%). 2 of 80 correct claims gave incorrect findings (2.5%). | 18 of 48 found (37.5%). 3 of 48 correct claims gave incorrect findings (6.2%). |
| decision governs | P 0.99 or more | 19.8% of applicable components found, 1.1% of other components proposed | 17.2% found, 6.0% proposed |
| triage | not available | 82.5% first-component rate | 69.2%. More than 10 points below development. |
| plan | not available | 0.73 of changed components covered at 0.5 | 0.39 covered |
| `suggest --decide`, `delta --decide` moves | not available | not measured | No holdout rows exist. |

The owner question of `delta --decide` uses the `decision owner` threshold.
The `decision flow` threshold came from a second measurement on 2026-10-13. It used the flow context from the `call_sites` fact, as the command does.
All measured repositories are Python repositories. No TypeScript result was measured.
The finding kinds have the same names for each provider. These names are identifiers in `[judgement] answered`.
[How do you change to the new finding names?](#how-do-you-change-to-the-new-finding-names) gives the previous names.

An OpenAI answer must agree with its question, as a Jev answer must.
A refusal for one question gives no finding for that question. The report gives the count of refused questions.

The cache is `.systemap/openai-cache.json`. It does not keep a refusal.
Its key includes the provider name, the model, the evidence, and the question. Thus OpenAI does not use a Jev answer.

The cost line on stderr has the same form for each provider, for example `openai: 1 sent, 0 from the cache; 290 input and 0 output tokens; gpt-6-luna`.
OpenAI charges $0.10 for each 1M input tokens and does not charge for output.
The 1,636 bench requests used 1,211,893 input tokens ($0.12).
The 256 requests of the second flow measurement used 213,942 input tokens ($0.02).

## How do you change to the new finding names?

In this release, the diagnostic kinds of a decision provider have new names.
The previous names started with `jev`. The new names start with `decision`, because Jev or OpenAI can give the answers.

| previous name | new name |
|---|---|
| `jev mis-fold` | `decision mis-fold` |
| `jev owner` | `decision owner` |
| `jev sentence` | `decision sentence` |
| `jev flow` | `decision flow` |
| `jev governs` | `decision governs` |
| `jev move` | `decision move` |

This release also reads the previous names:

- An exact answer (`item` or `items`) with a previous name is an answer for the line with the new name.
- A family answer, for example `kind = "jev flow"`, is an answer for the lines of the new diagnostic kind.
- `audit --kind "jev flow"` selects the new diagnostic kind and prints a warning.
- `systemap explain "jev flow"` gives the text of the new diagnostic kind.

`audit` and `judgement` print one warning to stderr for each previous name in `[judgement] answered`.
The warning gives the new name. Only this release reads the previous names.

The evidence digest of a line is the same for the previous name and the new name.
systemap calculates the digest of a line from the same line with its previous name.
Thus an exact answer with one item keeps its `evidence` value after you change the name.
But the digest of an `items` group also contains the text of each item.
Thus a group with changed names gets a new digest, and `audit` prints a `pending answer` line.

The `unknown surface` line for a source parse error also has a new form, because a line must not name one language.
The earlier line ended with `under Python 3.11.10`. The new line ends with `(parser version 3.11.10)`.
In this release, an answer item in the earlier form is an answer for the line in the new form.
The evidence digest of the item does not change.

Two other `unknown surface` lines also have a new form for the same cause:

| Earlier text in the line | New text in the line |
|---|---|
| `the npm tsconfig package could not be read` | `the configuration package could not be read` |
| `The parser could not parse the TypeScript syntax.` | `The parser could not parse the source syntax.` |

The same rule applies to these two lines.

The `entry point` line for a group of entry points gave the kind identifier, for example
`entry point 7 public_functions into Api have no sequence (component Api)`.
The new line gives the `kind` value with a space in place of each `_`: `entry point 7 public functions into Api have no sequence (component Api)`.
The same rule applies to this line. A kind without `_`, for example `route`, does not change.

The `unknown surface` line for a TypeScript parse error also changed.
Its source excerpt is the line of the error and the line before it, because the error can be one token, such as `','`.
From facts format 11, the excerpt and the parser version are in rows below the line.
The line ends with `The parser could not parse the source syntax.`
An answer item in an earlier form applies to the current line of the same module.

The parser can also refuse correct syntax.
tree-sitter-typescript 0.23.2 refuses a generic function call with a `typeof import()` type argument and a comma after the last argument.
For example, `f<typeof import('./a')>(g(),)` is correct TypeScript.
At 2026-10-13, PyPI and npm have no grammar version after 0.23.2.

`judgement` prints one warning to stderr for each item in the earlier form. The warning gives the new line.

The `unknown surface` line for a re-export target outside the extracted module set also changed (facts format 10).
The earlier line had the location `:1`, and a statement with two or more names gave one equal line for each name.
The new line ends with the names, for example `Names: Shape, Size.` The `at:` row gives the line of the statement.
An answer item in the earlier form can apply to a current line.
The map, the module, the file, and the target must agree with one and only one current line.
The evidence digest must agree.
A target that is a declaration file has a different line with the cause `declaration file`.
An answer item in the earlier form does not apply to that line, because the meaning changed.
Thus `judgement` gives the earlier item as a stale answer.
The command prints no warning for an item in the earlier form of this line.

Facts format 11 removes each value from an `unknown surface` line that changes while the finding stays the same.
A recorded answer then stays applicable when a line is added above the cited statement.

| Earlier text in the line | New text in the line |
|---|---|
| `module M (src/a.ts:254): ...` | `module M (src/a.ts): ...` |
| `test file tests/a.spec.ts:3: ...` | `test file tests/a.spec.ts: ...` |
| `... Source excerpt: '<text>' (parser version <version>)` | `...` |
| `... source could not be parsed: SyntaxError (parser version 3.11.10)` | `... source could not be parsed: SyntaxError` |

The judgement report gives these values in rows below the line, and `judgement --json` gives them in `open[].sources`.
An answer item in an earlier form applies to the line in the new form.
`judgement` prints one warning to stderr for each item in an earlier form. The warning gives the new line.
Two records with different line numbers can give the same line. Then one answer applies to the two records.

`--decide` is the new name of `--jev` in `delta` and `suggest`. `--no-decide` is the new name of `--no-jev`.
The previous options stay for one release. They send the same requests as the new options.
`[jev] enabled` and the other keys of the `[jev]` table do not change.

The printed text gives the name of the provider that gave the answers.
For example, `delta --decide --provider openai` prints `OpenAI suggestions`. With Jev, it prints `Jev suggestions`.

To change a configuration to the new names, do these steps:

1. In `systemap.toml`, replace each previous name in `[judgement] answered` with its new name.
2. If you changed an `items` group, use `systemap audit`.
3. Examine the source of each `pending answer` line again. Then record the digest from that line.
4. Replace `--jev` with `--decide` and `--no-jev` with `--no-decide` in scripts and CI files.
5. Use `systemap judgement --strict`. Make sure that it prints no warning.

## What do you do above forty components?

A large repository can exceed the capacity of one readable canvas.
Above approximately forty components, each layer can contain almost all
components. Layer selection then gives little separation.

A component can have `map="gateway.py"`.
This path is relative to its model file.
The target module exports `MODEL` and `MEANING`.
The nested map shows the parent component's internal structure.
The component ID is also the directory name of the nested page.
Thus the ID must not contain `/` or `\`, and it must not be `.` or `..`.

Each parent module must have one claim, without duplicates, in the nested map.
No extra module is permitted.
Only one component can open a nested model file.
The map tree rejects a second component that opens the same file.
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

- An `unknown surface` line about a module occurs one time, in the map that owns the module.
  An `unknown surface` line about the repository occurs one time, in the top map.
  Migration: an earlier exact answer for such a line can have a different map prefix.
  If its `item` without the prefix agrees with one current line, the answer applies to that line.

- `delta` compares each map's claimed modules.
  A moved module shows its component and model file.

- `suggest` shows maps above forty components.
  It lists the components with the most modules as possible nested maps.

A second nested level uses an id such as `Gateway/Routes`.
The self-map in the recorded experiment had no nested map.
Its 18 components were below the threshold.
The fixture in [`tests/test_nested.py`](../tests/test_nested.py) has five top-level
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

A model can also contain import rules.
`systemap check` and `systemap rules` compare each rule with the resolved imports in the facts.
This rule gives `fail` if a module of `FactsExtractor` imports a module of `Schematic`:

```python
from systemap import ImportRule

IMPORT_RULES = (
    ImportRule(
        "facts-first",
        "forbid_import",
        src=("FactsExtractor",),
        dst=("Schematic",),
        reason="Extraction does not use the drawing.",
    ),
)
```

Give the tuple to `Model(..., import_rules=IMPORT_RULES)`.
The schema file of the skill tells about the three `kind` values: `forbid_import`, `allow_imports`, and `forbid_cycle`.
The page does not show import rules.

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
as version 1.2.0 did. Only the value `1` gives this permission.
systemap does not read this permission from `systemap.toml`, because the repository controls that file.
To write a model file with code again as literal values, use `systemap convert`.

The page and the figures use some model names as CSS names and SVG IDs.
Thus systemap refuses these names when it reads the model, and the command exits 2:

- A custom layer ID that contains a character other than a letter, a digit, `_`, or `-`.
- The component IDs `_meta` and `__proto__`. The page data uses these keys.

The full schema and examples are in
[`SKILL.md`](../src/systemap/skill/SKILL.md) and its
[`references/`](../src/systemap/skill/references/).

## Which command do you use?

All commands accept `--root DIR` before or after the command.
This option shows a project outside the current directory.
Exit codes are `0` for current, `1` for stale or rejected, and `2` for unusable
configuration, model, or option value.
The line after an error tells you which input to correct.
The input is a command option, `systemap.toml` or the model module, a `tsconfig.json` file, or a Git ref.

A command reads and writes a cache file or an output file only in the repository.
If the file or one of its folders is a link out of the repository, the command stops with exit code `1`.
A FIFO or a device at the file also stops the command with exit code `1`.
The error gives the file and the cause.
Remove the file or the link. Then use the command again.

A write replaces a link in the repository. It does not write to the target of the link.
The configured cache files, `out_dir`, and `model` must be paths in the repository, without a `..` part.
An absolute path or a path with a `..` part gives exit code `2`.

### `systemap init [--no-ci | --strict-ci]`

Writes `systemap.toml`, an initial model, the skill directory, and a GitHub
workflow. The workflow pins this version.
The command does not replace `systemap.toml`, the model, or the workflow.
If `pyproject.toml` has a `[tool.systemap]` table and `systemap.toml` is missing,
the command does not write `systemap.toml`, because the commands read that file before the table.
Then it writes the model at the `model` path of the table.
It writes the skill directory again on each run.
If a symbolic link puts a file in a location that is not in the repository, the command writes no file and exits 2.
It prints the instruction for your agent.
`--no-ci` does not include the workflow.

The workflow has the variable `SYSTEMAP_CI`. Its default value is `advisory`:
a map finding gives a warning annotation, and the job passes.
With `--strict-ci`, the value is `strict`: a map finding makes the job fail.
You can change the value in the workflow file later.
If systemap cannot run (exit code 2 or more), the job fails with both values.

If the repository has no Python package and a directory has a `tsconfig.json` file,
`init` selects TypeScript.
For TypeScript, `init` selects the package root with this rule, in this sequence:

1. The repository root must have a `tsconfig.json` file.
2. If each `include` entry of `tsconfig.json` names a folder, and one of these folders has source, that folder is the root.
   An entry such as `source/**/*` names the folder `source`.
   A test folder or a type-test folder does not count.
   An entry that names a file, such as `vite.config.ts`, stops this step.
3. Then the root is `src` if it has source, then the repository root.

For example, the ky repository has `"include": ["source"]`. Thus `init` writes `"source" = "ky"`.
A configuration without `[package_roots]` uses the same rule.

If the rule selects no root, `init` writes no package roots and prints the cause.
It also prints the `[package_roots]` table to write in `systemap.toml`.
The table has one line for each folder with a `tsconfig.json` file, with the same rule in that folder.
Keep only the lines of the packages of the system.
`extract` and the other commands print the same text until you set the table.

`init` also writes `test_patterns` for the TypeScript type tests that it finds.
A type test is a file that only `tsc` examines, for example with tsd or `expectTypeOf`.
These files are test files, not modules of the map:

- A folder with the name `test-d`, the default folder of tsd, or the folder in the `tsd.directory` key of `package.json`.
- A folder with a name such as `__tests_dts__`: `__test` or `__tests`, more text, and `__`.
- A file with a name that ends in `.test-d.ts` or `.spec-d.ts`, as tsd and Vitest typecheck use.

The `test_patterns` key shows the rule in the configuration. You can change it there.

### `systemap extract [--check]`

Reads the source tree and writes `docs/map/map.json`.
Module records contain public surface, public names, internal imports, external
imports, test references, and entry points.
Package `__init__` records include re-exports.
The other commands read this file.

Each language adapter also writes these facts with the same meaning for Python and TypeScript:

- `package`: the folder package of the module. A dot in a file name does not make a package.
- `completeness`: `parsed`, `line`, `reason`, and `unresolved_imports`.
  If the module did not parse, `unresolved_imports` is null, because the value is not known.
  A component with a module that did not parse gets no source review digest. An import rule for that module gives `unknown`.
- `call_sites`: the lines that use each imported name, and the lines that use a local name that gets its value from an imported name.
  The `decision flow` question reads this fact.
- `classes` and `types`: `classes` holds only class declarations.
  `types` holds each other type declaration, with its name, its category (`interface`, `enum`, or `type_alias`), and its methods.
- `defined_in` and `defined_as` on each re-export: the module and the symbol that define it.
- `same_as` on each entry point: the identity of a different entry point with the same start, or an empty string.
  A missing value is not known. Then the entry point must have its own sequence.
- `symbol` on each entry point: the name in its module that the entry point starts, or an empty string.

- `cause` on each unknown record: the cause that gives the `fix:` line, for example `declaration file` or `script file`.

The facts file has a format number in its `version` key. The current format is 12.
A facts file of an earlier format is stale. Then `check` and `extract --check` exit 1.
After an upgrade of systemap, run `systemap refresh`.

A test file that systemap cannot read or parse gives a `test_file_issues` record, for Python and for TypeScript.
The record is not known. It does not reject the map. `check` and `refresh` print it with its cause and its `fix:` line.

systemap reads `systemap.toml`, `pyproject.toml`, `package.json`, and each `tsconfig.json` file only in the repository.
A configuration file that is a link out of the repository, or that is not a regular file, gives a configuration error.
The error gives the path and the cause.
A missing configuration file gives an empty table, as before.
A `tsconfig.json` target in the `node_modules` folder of the repository stays permitted.

- `--check` exits 1 if stored facts differ from the source tree.
  The facts file includes a digest of the values that extraction reads from each configuration file.
  Thus a change to such a value is also a difference.
  A comment, the text format, or a value that extraction does not read is not a difference.
  A file in an installed package folder, for example `node_modules`, is a difference only if it is on this computer.
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

The module description is the first paragraph of the Python module docstring, or of the first TypeScript comment before the first statement.
An untagged TypeScript comment directly before a variable declaration describes that variable, not the module.
To give a module description there, separate the comment with a blank line or use a documentation tag.
The tags `@module` and `@packageDocumentation` identify a module comment in a `/** ... */` block.
The description excludes the tag and its module name.
Headers before imports retain their descriptions without a tag.
A license notice is not a description.
A text is a notice if it starts with `Copyright`, `©`, `(c)`, `SPDX-`, `Licensed under`, `@license`, or `@preserve`, in capital or small letters.
For TypeScript, a comment that starts with `/*!` or `//!` is also a notice.
The `//` comments directly below a notice are part of the notice.
Then the next TypeScript comment can give the description.

### `systemap place [--all] [--print] [--keep-order]`

A component must have a position before you render the map.
This command writes positions for unpositioned components on all maps.
The command keeps positions already in the model.
Only `x=`, `y=`, boxes, and the canvas change.
The command changes keyword values and positional values.
After the write, the command loads the model file again.
It compares each position, box, and the canvas with the calculated values.
If the command cannot load the file or a value is different, it restores the previous file contents.
This error causes exit 1.
For example, a box in an imported file is different, because the command changes only the model file.

Regions use a two-column grid with routing corridors.
The search selects the region order with the best score.
Barycenter sweeps through flows select component order within regions.
With six or fewer regions, the search tries every order.
For more regions, it uses a greedy start and pairwise swaps.

A bend estimate scores each candidate.
The router renders the best twelve estimates and the model's listed order.
It scores label collisions, rejected routes, bends, and length, in that order.
The report gives the selected order and score. This line is from `systemap place --all --print` in this repository:

    region order: draw, gather, mean, keep, operate. 159 bends, 32,562 units. 120 orders examined, 13 routed

The procedure is deterministic and uses only the standard library.

- `--all` writes new positions except for `pinned=True` components.
  Use it after you add or remove components.

- `--keep-order` uses the listed region order without a search.

- `--print` prints positions without file changes.

Before the command calculates positions, it examines the flows and the `kind` value of each component.
A flow to an unknown component, or an unknown `kind` value, causes exit 1.
The error gives the flow or the component. `systemap describe` also examines them.

### `systemap render [--check] [--base REF]`

Writes the page from the facts and model.
Without facts and without package roots, `render`, `facts`, and `figure` give the package-root error of `extract` and exit 2.
Thus they do not tell you to use `systemap extract` when `extract` cannot operate.

- `--check` exits 1 if the page is stale.
  It renders the page with the same options and compares the two pages.
  Thus a page that `render --base REF` wrote is stale for `render --check` without `--base REF`.

- `--base REF` adds a change map relative to that revision.
  The page link `#changes`, for example `index.html#changes`, opens the Changes view.
  The Changes panel lists the map changes: the components, flows, sequences, and rules
  that the change added, removed, or changed in the model.
  The list compares the committed model at the merge base with the model on disk.
  A new digest for the same cited module or symbol is not a flow change.
  If the base model does not load, the panel gives the reason.
  The source text has the same rules as the extraction: UTF-8, with or without a byte order mark.
  If systemap cannot read a changed source file, the changes of its module are not known.
  The panel gives the read problem. A missing file is a removal.
  Each revision resolves the imports of its test files with the files of that revision:
  its configuration files, module paths, and modules.
  If systemap cannot read or parse a changed test file at a revision, the panel gives the file and the problem.
  The page has no test changes for that file.
  The panel also gives each changed path that the Git tree reader refuses, with its cause.
  The changes of such a path are not known.

- `--pr N` gives the pull request title of the change map. `gh pr view` gives the title.
  If `gh` cannot give the data, the command writes one note with the cause to stderr.
  The page then has no pull request title.

### `systemap check [--brief]`

Executes all rules on all maps.
A rejected map causes exit 1.
Each finding gives a correction.
Two rows below a rejected rule give its effect and the necessary action.
Each condition that rejects the map prints its lines.

- `--brief` does not include these two rows.

The `unknown surface` group gives the records that the extractor could not read or connect.
These records do not reject the map.
The adapter writes the cause of each record in the `cause` field.
Below each line, the `at:`, `excerpt:`, and `parser version:` rows give the values that are not in the line, as `systemap judgement` gives them.
The group gives one `fix:` line for each cause that occurs:

| Cause | Condition |
|---|---|
| `read` | systemap could not read the file, or the repository rules refused it. |
| `encoding` | The file is not UTF-8 text. |
| `syntax` | The parser could not parse the source. |
| `declaration` | The parser read the syntax, but it has no record for the declaration or export form. |
| `target` | A reference has a target that is not a module in the facts. An example is a package bin target that is not in the repository. |
| `declaration file` | A re-export target is a declaration file, such as a TypeScript `.d.ts` file. A declaration file gives only types and has no module. The line gives the names of the statement. |
| `script file` | A package bin target is a JavaScript file in the repository with no source module. The extractor does not read it, and `[package_roots]` cannot make it a module. |
| `package` | A configuration file extends a configuration package that systemap could not read. |
| `binding` | The framework binding of a registration is not known. |
| `reexport` | The names that a re-export gives are not known. |
| `not known` | The record has no cause, because the facts have an older format. |

### `systemap figure --out FILE`

Uses the page generator to render one figure for a document.

- `--components A,B` renders a plan's reach.

- `--base REF` renders a change.

- `--layer ID` renders that layer's flows and all components.
  The legend contains only that layer.

- `--map ID` selects a nested map.

- An `--out` filename with a `.svg` suffix writes the drawing without a frame.

- A relative `--out` path is relative to the output directory.
  Its folder must be in the repository after the resolution of links. If it is not, the command exits 1.
  The command replaces a link at the `--out` path with a file. It does not write to the target of the link.

- `--svg-id ID` sets the HTML ID of the drawing. The default is `lessonmap`.
  The ID must start with a letter and contain only letters, digits, `-`, and `_`.

The figure shows the layer names, the caption, and the other model and configuration text as text, not as HTML.

### `systemap refresh`

Executes extraction and the checks, and renders the page and the configured figures,
in dependency order. Then it does a check of the written outputs.
A result without changes prints
`map: The page agrees with the rendered model fields and the facts.`
A rejected check causes exit 1, and the command renders nothing.
The last line gives the necessary action. If a second refresh gives the same result, the action is not `refresh`.
If an output is stale after the command wrote it, the heading is `stale after refresh`.
An example is a configured figure with the path of the page.
After a check without errors, the command prints the `source inventory unresolved` group and the `unknown surface` group, as `systemap check` does.
After a check without errors, the command examines the import rules, as `systemap check` does.
It prints the rule results. A rule with the result `fail` causes exit 1.
With `[rules] unknown = "fail"`, a rule with the result `unknown` also causes exit 1.
The command writes its outputs before it examines the rules.
`-q` or `--quiet` prints only errors and check results.

### `systemap suggest [--decide]`

Proposes the first module groups for revision.
From facts alone, it gives one component per package with two or more modules.
It lists modules and imports across proposals.
With a model, it also shows maps above forty components and large
components that can become nested maps.

- `--decide` uses the module-pair answers of the decision provider instead of package groups.
  Set `TYPESAFE_API_KEY` for this option. `--jev` is the previous name of `--decide`. It stays for one release.

- `--provider jev|openai` selects the decision provider.
  OpenAI has no measured threshold for the pair question. Thus `--provider openai` sends nothing and exits 1.

### `systemap judgement [--strict] [--kind KIND] [--verbose] [--brief] [--json] [--order-by-drift]`

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
  A model without components also gives exit 1 with `--strict`, as `systemap check` does.

- `--kind KIND` prints one kind.

- `--verbose` prints imports below each crossing-import row.

- `--brief` does not include the two explanation rows.

- Below each `unknown surface` line, a `cause:` row gives the cause that the adapter wrote.
  After the lines, the report gives one `fix:` line for each cause, as `systemap check` does.
  `--brief` does not remove these rows.

- Below the `cause:` row, the line of a module record or a test file record gives its source rows.
  An `at:` row gives the file and the line of each cited statement.
  An `excerpt:` row gives the source excerpt. A `parser version:` row gives the version of the parser that refused the source.
  A finding line is the identity of the finding. Thus it does not contain these values (facts format 11).
  If two statements of one module give the same line, the line occurs one time with two `at:` rows.

- If the decision store has unknown decision requests, the report gives each one after the review counts.
  The row `unknown request ID: CLAIM` gives the claim. The report does not say that the claim is correct.
  The `systemap decisions` section tells about decision requests.

- `--json` writes one JSON object to stdout for software, for example a CI step.
  The object has no explanation text. `--brief` and `--verbose` do not change it.
  The exit codes are the same as in the text mode, with and without `--strict`.
  Notices for a person go to stderr.

- With `--json`, `--kind KIND` selects the rows of `open`. The counts include all kinds.
  For a model without components, the lists are empty.
  The exit code is 1 with `--strict`, and 0 without it.

- `--order-by-drift` sends one Jev question for each open `stale source review` line.
  The answer is the drift score: the probability that the claims of the component agree with its changed source.
  The report puts the stale lines in sequence from the lowest drift score.
  The other lines do not move.
  A `drift score:` row below each stale line gives the score.
  With `--json`, each stale row has `drift`, and the object has `drift_order`.

  The option does not close a line, and it does not change a source review or an answer.
  The open lines and the exit code are the same with and without the option.
  The score has no threshold, because no measurement gives one (`bench/jev/README.md`, test 7).
  Examine each stale component, also the components at the end of the sequence.
  Set `TYPESAFE_API_KEY` for this option. Without the option, `judgement` sends no request.

  The question gives the claims that the `source_review` digest contains, and one part of the source.
  Git finds the last commit that added the recorded `source_review` digest below the folder of the model file.
  The source part is the diff of the module files of the component, from that commit to the working tree.
  If Git cannot find the commit, or the diff is empty, the source part is the current text of the module files.
  Each source part has a limit of 12,000 characters.
  A new file that is not in Git is not in the diff.

  A refusal or a request error gives `no score`. A line without a score goes to the end of the stale lines.
  A `drift sequence:` row gives the quantity of questions without a score and the cause.
  The answers go into the Jev cache. Thus, the next command sends no question.
  It reads the model list one time, as each Jev command does.

The JSON object has these fields:

| Field | Type | Contents |
|---|---|---|
| `schema_version` | integer | The version of this schema. The value is 3. Version 2 added `open[].cause`. Version 3 added `open[].sources`. |
| `open` | list of objects | One object for each finding that has no accepted answer. The sequence is the sequence of the text report. |
| `open[].line` | string | The full finding line. It is the identifier for `item` in `[judgement] answered`. |
| `open[].kind` | string | The kind of the finding, for example `single module`. The value is an empty string if the kind is not known. |
| `open[].detail` | list of strings | The imports of a crossing-import finding, as `--verbose` prints them. For other kinds, the list is empty. |
| `open[].evidence` | string or null | The digest that an exact answer for this one line must have in `evidence`. The value is null if the evidence is not available. |
| `open[].cause` | string or null | The cause of an `unknown surface` finding, for example `syntax` or `declaration file`. The `systemap check` section gives the causes. For other kinds, the value is null. |
| `open[].sources` | list of objects or null | The source records of an `unknown surface` finding of a module or a test file. Each object has `file`, `line`, `excerpt`, and `parser`. A value that the record does not give is null. For other findings, the value is null. |
| `open[].drift` | object | Only with `--order-by-drift`, and only in a `stale source review` row. `probability` is the drift score, or null for `no score`. `source` is `diff` or `text`: the form of the source part. |
| `answered.count` | integer | The quantity of findings that accepted answers close. |
| `answered.answers` | list of objects | One object for each accepted answer. |
| `answered.answers[].answer` | string | The selector of the answer, as the stale-answer row gives it. |
| `answered.answers[].items` | list of strings | The exact lines of an `item` or `items` answer. For a family answer, the list is empty. |
| `answered.answers[].reason` | string | The `reason` of the answer. |
| `answered.answers[].lines` | list of strings | The findings that the answer closes. |
| `stale_answers` | list of strings | Each exact item or family selector that agrees with no finding. |
| `source_reviews` | object or null | The keys `current`, `stale`, and `missing`, with the quantity of source components in each review state. The value is null if no facts are available or no source component exists. |
| `require_reviews` | boolean | The value of `[judgement] require_reviews`. With true, a missing source review is an open finding. |
| `kinds` | object | One key for each finding kind. Each value has `open` and `answered`, with the quantity of findings of that kind. |
| `drift_order` | object | Only with `--order-by-drift`. `questions` is the quantity of questions. `no_score` is the quantity of questions without a score. `reason` is the cause, or an empty string. |
| `unknown_requests` | list of objects | The unknown decision requests, with the fields of `unknown_requests` in `systemap decisions status --json`. Without a decision store, the list is empty. |

The `evidence` digest is for an answer with one line.
An `items` answer for more than one line has a different digest.
The text report prints that digest in the pending-answer row.

### `systemap rules [--brief] [--json]`

Prints the result of each import rule: `pass`, `fail`, or `unknown`.
`systemap check` prints the same results.
A `fail` result gives each import against the rule, as source module and target module.
An `unknown` result gives each module with imports that are possibly not in the facts, and the cause.

The causes are a module that did not parse, unresolved imports, and an import of a module with no component.
The command exits 1 for a `fail`, for an incorrect rule, or for missing facts.
It also exits 1 for an `unknown` result with `[rules] unknown = "fail"`.
The `ok` value of `--json` agrees with the exit code. Missing facts are an item of `problems`.

- `--brief` does not include the two explanation rows.

- `--json` writes one JSON object to stdout for software.
  The keys are `ok`, `unknown_policy`, `problems`, `counts`, and `rules`.
  Each item of `rules` has `map`, `id`, `kind`, `src`, `dst`, `reason`, `invariant`, and `result`.
  It also has `imports` (`source`, `target`) and `unknown` (`module`, `cause`, `detail`).
  The `cause` values are `no_facts`, `no_read_state`, `not_parsed`, `unresolved_not_known`, `unresolved_imports`, and `no_component`.

### `systemap delta --base REF [--head REF] [--comment FILE --pr N] [--decide | --no-decide]`

Compares extracted facts from two Git commits.
Python and TypeScript use the configured language adapter, as the working tree
does. The report shows moved, added, and removed modules with their
components and model files.
Delta reads the committed files. The Git attributes `export-subst` and
`export-ignore` do not change them.
Delta compares the head with the merge base of the two refs.
If Git finds no merge base, the command gives an error and exits 2.
Delta does not use a different commit as the base.
Delta does not write a committed path that contains `..`, a backslash, or a colon.
Thus the facts at a commit are the same on each platform.
Before the report, delta gives each refused path and its cause under `Not in this comparison`.
The changes of a refused path are not known. A refused module is not a removed module.

The first line gives the module counts. Then `N of M components have changes` gives the quantity of components that the delta lines name.

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
  If `FILE` is a link, the command replaces the link. It does not write to the target of the link.
  If `FILE` is in the repository, each folder of `FILE` must be in the repository.

- `--decide` enables the suggestions of the decision provider for modules with changed
  names and content, and for unclaimed modules. The suggestions do not change
  the delta lines or the exit code. `[jev] enabled = true` in `systemap.toml`
  and the key of the provider also enable them. A key alone does not enable them.
  The heading of the suggestions names the provider, for example `Jev suggestions`.

- `--no-decide` sends nothing.

- `--jev` and `--no-jev` are aliases: the previous names of `--decide` and `--no-decide`. They stay for one release.

- `--provider jev|openai` selects the decision provider of `--decide`.
  With `openai`, `[jev] enabled = true` must have `OPENAI_API_KEY`.
  OpenAI has no measured threshold for the move question. Thus delta sends only the owner questions and gives the cause.

- `--brief` prints the lines without the explanation rows. `systemap explain KIND` gives the full explanation.

- The cost of the decision provider goes to stderr.

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

Sends questions about semantic claims to the decision provider.
The finding kinds are `decision mis-fold`, `decision owner`, `decision sentence`, and
`decision governs`. `--kind "decision flow"` also sends questions about flow claims.
`--kind` also accepts the previous `jev` names for one release, with a warning.
Answers use the cache.
The command exits 0 for a completed report, or 1 if it cannot complete.

Set `TYPESAFE_API_KEY` for Jev, or `OPENAI_API_KEY` for OpenAI, before you run the command.

- Use `--kind KIND` again to select another question kind.

- `--dry-run` lists proposed questions and does not send them.

- `--provider jev|openai` selects the decision provider.
  With `openai`, the command does not send the `decision mis-fold` questions and gives the cause.

- `--brief` prints the findings without the explanation rows.

### `systemap plan "<task>" [--check ID] [--base REF]`

Predicts components likely to change in a task.
Jev compares the task with each component's function.
The projection includes components with probability of at least 0.05.
The report includes flows, sequences, and rules for each component.
It lists six of each, then gives a count.
The projection is in `.systemap/plans/<id>.json`.
The ID has three parts: the date, a digest of the full task, and the first four words of the task.
The same task on the same date gives the same ID.
If the plan file of the ID contains a different task, the command does not replace it. It exits 1 and gives the file.

The measured threshold of 0.05 is in `bench/jev/plan_eval.py`.
Set `TYPESAFE_API_KEY` before you run the command.

- `--check ID --base REF` compares the projection with changed components
  since `REF`. The default base is `origin/main`.
  The current model gives the components of each module.
  A component of a module claims the module, or a symbol in the module.
  If the current model does not claim a removed module, the model at the `REF` commit gives its component.
  It exits 1 for changed components outside the plan.

- `-` instead of a task reads stdin.

- `--provider jev|openai` selects the decision provider.
  OpenAI has no measured threshold for plan. Thus `--provider openai` sends nothing and exits 1.

### `systemap triage TEXT`

Predicts the three components likely to change in an issue fix.
The report includes their modules and adjacent components.
`-` reads stdin. The text limit is 2,000 characters.
Set `TYPESAFE_API_KEY` before you run the command.

- `--provider jev|openai` selects the decision provider.
  The OpenAI triage measurement did not satisfy the holdout rule. Thus `--provider openai` sends nothing and exits 1.

### `systemap journeys [--limit N] [--dry-run]`

Writes a sequence for an entry point with no examined sequence.
For multiple same-kind entries in one component, it can write a grouped
sequence. Its `covers` field records the examined entry identities.
An examination must add a new entry to that list before the entry counts as covered.

`[agent] command` reads source from the entry point.
The agent gives components in the execution path and a sentence for each step.
Each request contains the language policy of the `[writing]` profile.
The command rejects a step with no authored flow and gives a finding.
The command also rejects a step source record that does not resolve.
It rejects a step source record in no module of an acting or measured component of the step.
The command does not write that step.
The agent cache keeps only an answer that gives an accepted sequence.
Thus, after a rejected answer, the next command sends the question to the agent again.

The agent can write no more than 200,000 bytes to stdout.
If it writes more, the command stops the agent, and the request does not complete.
If a request does not complete, the command writes the accepted sequences of the other requests.
Then it names each request that did not complete and exits 1.
A rejected draft is also a request that did not complete.

Accepted sequences enter the model with `drafted=True`.
The command writes them into the `JOURNEYS = (...)` tuple of the model.
The tuple can have a type annotation, as in the model from `init`.
If the model does not import `Journey` or `Step`, the command adds an import from `systemap`.
Before the write, the model reader reads the changed model, as for each other command.
If the reader refuses it, or the changed `MEANING` does not contain each accepted sequence,
the command writes no file and exits 1.
`judgement` prints `drafted journey` until a person examines the sequence and
removes the mark.

By default, the command writes no more than three sequences.

- `--limit N` writes no more than N sequences. N must be 1 or more.

- `--dry-run` lists proposed sequences without file changes.

- With no `[agent] command`, the command also lists proposals and gives the
  reason it cannot write them.

### `systemap history [--since WHEN] [--every DAYS] [--top N] [--ref REF]`

Reads source samples across repository history.
The defaults are `1 year ago`, a minimum interval of 14 days between two adjacent samples (`--every`),
and the five largest windows (`--top` default 5). Each window compares two samples.
A sample is the first commit after the minimum interval from the previous sample.
The last sample is the ref, also if the interval before it is smaller.
Thus a repository with a small number of commits gives intervals of more than `--every` days.
Facts use the cache `.systemap/facts/<sha>-<scope>.json`.

Each window shows module and entry additions or removals, component size
changes, and new and removed crossing imports.
It shows the commits that added the files of new modules.
A commit that only changes such a file is not in the list.
All samples use the component assignments in the selected map.
Thus, a moved module counts under its component in the selected map.
TypeScript samples include `.ts`, `.tsx`, tests, and package entry points.

- `--ref REF` starts from that branch or commit instead of `HEAD`.
  Git must resolve `REF` to a commit. A value that starts with `-` is not an option to Git.
  If Git cannot resolve `REF`, or if a Git command fails, the command exits 2.

### `systemap explain [KIND]`

Prints one finding kind's meaning, effect on the map, and necessary action.
With no kind, it lists all printed kinds and their one-line meanings.
An unknown kind causes exit 1.

### `systemap convert`

Writes each model file that systemap refuses again, with literal values only.
The command must run each refused file one time, so it needs `SYSTEMAP_TRUST_MODEL_CODE=1`.
Examine the code of the model files before you set this value.
Without the value, the command writes nothing and exits 2 if a model file is refused.
If all model files have literal values only, it writes nothing and exits 0.

For each refused file, the command reads the new text with the reader that runs no code.
It writes the file only if that reader gives the same model as the old file.
Fields with their default values are not in the new text.
If the old file imported a file beside it, the command names that file. The new file does not import it.

### `systemap review ID | --flow ID | --flow 'SRC->DST' [--map ID] [--dry-run]`

Writes the current review digest of one target into the model file.
`systemap review ID` writes `source_review` of the component ID.
`systemap review --flow ID` writes `review_digest` of the flow with that identifier.
`systemap review --flow 'SRC->DST'` writes `review_digest` of the flow from SRC to DST.
The `SRC->DST` form is correct only for a pair that one flow connects.
Put the `SRC->DST` value between quotation marks, because the shell reads `>` as a redirection.
If the map has no flow with the `ID`, the command stops with exit 2.
`--map ID` selects a nested map.
`--dry-run` prints the digest and the file, and it writes nothing.

The command does not examine claims.
Before you use it, examine the source and all the claims of the target.
One command writes one target.
The command has no option for all targets, because a person or an agent must examine each claim separately.

The command reads the source in the working tree.
`systemap judgement` reads the stored facts, so run `systemap refresh` before `systemap judgement`.
A flow digest is one of the claims of its two endpoint components.
Thus, a new flow digest makes a current review of an endpoint stale, and the command tells you.
Record flow digests before component digests.

The command writes the value into the file that defines the target.
This file can be a file that the model file imports.
The command changes only the value, or it adds one keyword argument.
It keeps the comments and the format of the file.
It writes the file only if the reader that runs no code gives the same model with only the new value.
If the value is the current digest, the command writes nothing.

The command stops with exit 1 and writes nothing in these conditions:

- The map has no such component or flow, or two or more flows connect the `SRC->DST` pair.
- The component has no current digest. It claims no module, a claimed module is missing, or the parser cannot read a claimed module.
- The flow has no `source_refs`, or a source record does not agree with the current source.
- systemap cannot read the model file as data. Use `systemap convert` first.
- The command finds no literal call for the target, or more than one.

### `systemap decisions pending | submit FILE | status`

These commands give the claims of the map to a coding agent in its current session.
The agent examines each claim against the source code and sends a verdict.
systemap examines each verdict and records the correct verdicts.
The commands send no request to a model. An API key is not necessary.
The skill procedure is in `references/decisions.md`.

The commands read the facts file. If the facts file does not agree with the source code, the commands stop with exit 1.
Run `systemap refresh` first.

A decision request has one of three types:

| Type | Claim | Result of `supported` |
|---|---|---|
| `judgement` | An open judgement line. The claim digest is the SHA-256 digest of the line. | An exact answer in `[judgement] answered`, with the summary as the reason, the current evidence digest, and the citations. |
| `source_review` | A source component with a missing or stale source review. The claim digest is the review digest. | The current `source_review` digest, as `systemap review ID` writes it. |
| `flow_review` | A flow with `source_refs` and a `review_digest` that is not current. The claim digest is the flow claim digest. | The current `review_digest`, as `systemap review --flow` writes it. |

A judgement line that a review digest closes is not a different decision request.
These lines are `stale source review` and `missing source review` for a component with a `source_review` request.
They are also `flow review` and `declared flow` for a flow with a `flow_review` request.

The `id` of a decision request contains the type, the target, and the first 16 characters of the claim digest.
If the claim does not change, the `id` stays the same in a different session.
A source change that does not change a judgement line does not change its `id`.

The decision store keeps one record for each target. The record does not use the claim digest.
The target of a component is its ID, and the target of a flow is `SRC->DST`.
The target of a judgement line is its kind and the names of the components and modules in the line, for example `single module: Reader pkg.reader`.
If two current lines have the same kind and names, or a line names nothing, the target is the full line.

#### `systemap decisions pending [--json]`

Gives the pending decision requests. The command exits 0.
An unknown decision request is not pending. The `unknown` count gives the quantity.

The JSON object has these fields:

| Field | Type | Contents |
|---|---|---|
| `schema_version` | integer | The version of this schema. The value is 1. |
| `verdicts` | list of strings | `supported`, `contradicted`, and `insufficient_evidence`. |
| `max_contradicted` | integer | The value of `[decisions] max_contradicted`. |
| `requests` | list of objects | One object for each pending decision request. |
| `requests[].id` | string | The identifier for `request_id` in a verdict. |
| `requests[].type` | string | `judgement`, `source_review`, or `flow_review`. |
| `requests[].map` | string | The ID of the nested map. The top map has an empty string. |
| `requests[].target` | string | The judgement line, the component ID, or the flow as `SRC->DST`. |
| `requests[].claim` | string | The claim text. For a component, it includes the flows, invariants, and sequences that name it. |
| `requests[].claim_digest` | string or null | The current claim digest. The value is null if the component has no current digest. |
| `requests[].files` | list of objects | The source files of the claim, with `file` (the path from the repository root), `module`, and `sha256` (the source hash of the full file). |
| `requests[].verdicts` | list of strings | The permitted verdicts. |
| `requests[].attempts` | integer | The quantity of `contradicted` verdicts for the target since the last change of its source. |
| `requests[].blocked` | string | If not empty, the cause that prevents `supported`, and the necessary step. |
| `requests[].identity` | string | The target in the decision store: the component ID, the flow, or the kind and names of a judgement line. |
| `unknown` | integer | The quantity of unknown decision requests. |

For a judgement line, the files are the files of the components and the modules that the line names.
If the line names no component or module, the list is empty.

#### `systemap decisions submit FILE`

Reads a JSON list of verdicts from FILE, or from stdin for `-`.
Each verdict is an object with only these fields:

| Field | Type | Contents |
|---|---|---|
| `request_id` | string | The `id` of a pending decision request. |
| `verdict` | string | `supported`, `contradicted`, or `insufficient_evidence`. |
| `citations` | list of objects | The source lines that the agent read. Each citation has `file`, `start_line`, `end_line`, and `sha256`. |
| `summary` | string | One or more sentences about the source code. The writing profile applies. |

The command first examines all verdicts.
If one verdict is incorrect, the command writes no file, gives each error, and exits 1.
The command rejects a verdict in these conditions:

- The `request_id` is not a current decision request, or the decision request is unknown. A claim change gives a new `id`.
- The file has two verdicts for one `request_id`.
- A `file` is an absolute path, a Windows drive or UNC path, or contains `..` or a backslash.
- A `file` is not a regular file, or is not a source file in the facts.
- A `file` is a symbolic link to a file that is not in the repository.
- A line span is not in the file, or `start_line` is more than `end_line`.
- A `sha256` is not the SHA-256 digest of the current file content.
- A `supported` verdict has no citation in a file of the claim. For a flow, these are the files of the two endpoint components. For a judgement line without files, one citation is necessary.
- A `supported` verdict has a decision request with a `blocked` value, or the review command cannot write the digest.
- A `supported` verdict for a component has a flow of that component with a `contradicted` or unknown verdict.

Then the command writes, in this sequence:

1. The `review_digest` of each `supported` flow.
2. The `source_review` of each `supported` component. A flow digest is one of the claims of its endpoint components. Thus, the flow digests come first.
3. One exact answer for each `supported` judgement line. A review digest can close a judgement line. Thus the command finds the open lines and their evidence digests after the review digests.
4. The decision store, `.systemap/decisions.json`. Git does not record this file.

A `contradicted` verdict adds one to the `contradicted` count of the target.
The agent must correct the map and send a new verdict.
At `[decisions] max_contradicted` verdicts, the decision request becomes unknown.
After one `insufficient_evidence` verdict, the decision request is unknown.
A `supported` verdict sets the count to zero.

A change of the map claim does not set the count to zero, and does not make an unknown decision request pending.
Thus an agent that changes the map after each `contradicted` verdict stops at the limit.
A change of a source file of the target makes the decision request pending again, with a count of zero.
A file that the map change adds to the target, or removes from it, is not a source change.
To start all counts again, delete `.systemap/decisions.json`.

#### `systemap decisions status [--json]`

Gives the counts and the unknown decision requests.
The command exits 0 if no decision request is pending or unknown. If not, it exits 1.
An unknown decision request does not show that its claim is correct, and the text does not say that it is correct.

| Field | Type | Contents |
|---|---|---|
| `schema_version` | integer | The version of this schema. The value is 1. |
| `pending` | integer | The quantity of pending decision requests. |
| `supported` | integer | The quantity of `supported` verdicts in the decision store. Remove the decision store to start a new count. |
| `unknown` | integer | The quantity of unknown decision requests. |
| `unknown_requests` | list of objects | One object for each unknown decision request, with `id`, `type`, `map`, `target`, `claim`, `claim_digest`, `verdict` (the last verdict), `attempts`, and `summary` (the last summary). |

### `systemap serve [--port 8765]`

Supplies the output directory through HTTP on the loopback address.
The command prints the URL.
If the port is not available, the command exits 2.
Then use `--port 0` to select an available port, or give a different port.
The server answers only a request whose Host header is `127.0.0.1` or `localhost` with the server port.
Thus a web page that makes its own domain name point at 127.0.0.1 cannot read the map.
The server answers 404 for a symbolic link to a file that is not in the output directory.
`systemap live` has the same rules.
If the output directory is not in the repository after the resolution of links, the command exits 1. The server does not start.

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
If the command cannot write the pages of a version, the command gives the error, and the next version renders.
After a good version, the command removes the pages of the maps that the version does not have.

- `--base REF` sets the base of the Changes view.
  The default is the first of `origin/HEAD`, `origin/main`, `main`, `origin/master`, and `master`
  that has a merge base with HEAD. If no ref has one, the page has no revision comparison.
  The Changes view compares the working tree with that merge base.
  The comparison includes the commits since the merge base, the edits that are not in a commit,
  and the untracked files that Git does not ignore.

- Without `--no-watch`, the command scans the configuration files, the model files,
  and the source and test files one time each second.
  The scan includes the language configuration files below each package root, such as `packages/web/src/lib/package.json`.
  It also includes these files in the folders between a package root and the repository root, such as `packages/web/tsconfig.json`.
  The scan skips the same folders as the source extraction of the language. For TypeScript, it does not skip a folder with the name `build` or `dist`.
  The scan includes each test file that extraction reads, also a file that `test_patterns` selects out of the package roots and the test directories.
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
| `{"event": "stopped"}` | When the command stops after Ctrl-C or SIGTERM, or Ctrl-Break on Windows. The exit code is 0. |

On this repository, one version takes about 7 to 8 seconds.
Thus the command waits until the files stop changing before it renders the page.
[bench/jev/README.md](../bench/jev/README.md) gives the measurements.

### `systemap skill [--dir PATH] [--print]`

Reinstalls the skill directory from `init`: `SKILL.md` and `references/`.

- `--dir PATH` writes to another directory.

Each skill file must be in the repository (in `PATH` with `--dir`) after the resolution of symbolic links.
If a file is not, the command writes no file and exits 2.

- `--print` writes `SKILL.md` to stdout.

## What can you configure?

Use `systemap.toml` at the repository root or `[tool.systemap]` in
`pyproject.toml`. All keys are optional.
Unknown keys are rejected.

| Key | Default | Meaning |
|---|---|---|
| `language` | found from the source | The source language. Select `python` or `typescript`. Without the key, the language adapters examine the configured package roots, or they find their own package roots. If the source of both languages is available, the configuration stops and tells you to set this key. If no source of a known language is available, each command that reads source stops with the same instruction. The `[writing]` table sets the writing rules for map text. TypeScript must have the `systemap[typescript]` extra. |
| `name` | the package name (`[project] name` in pyproject.toml for Python, `name` in package.json for TypeScript), Git repository directory, then directory name | The page title. |
| `[package_roots]` | Python packages, or for TypeScript the one source folder of the `tsconfig.json` `include` entries, then `src`, then the repository root (see `systemap init`) | `"path" = "module name"`. Discovery includes a directory with the name `build` or `dist` if it has an `__init__.py` file. Each configured path must be a directory in the repository. A key after the `[package_roots]` line is part of this table, so put the top-level keys above it. |
| `tests_dir` | All directories with the name `tests` or `test` | One directory or a list. Import references associate tests with modules. |
| `test_patterns` | none | Additional repository-relative test globs. Extraction and `delta` use the same patterns. For TypeScript, `init` writes the type-test folders and files that it finds (see `systemap init`). |
| `model` | `map/model.py` | The model file that gives `MODEL` and `MEANING`. systemap reads it as data and does not run it. A file in the same directory can contain sequences or flows (`import journeys`). [What does a model contain?](#what-does-a-model-contain) gives the permitted syntax. |
| `out_dir` | `docs/map` | The directory for facts, pages, and figures. |
| `facts_file` | `map.json` | The facts filename inside `out_dir`. A path that is not in `out_dir` gives exit code 2. |
| `spec_path` | none | A document with `##` headings that identify specification sections. |
| `planes` | none | Second-level package names with different planes in the facts. |
| `outside_label` | `EXTERNAL COMPONENTS` | The index heading for actors outside all regions. |
| `[coverage]` | none | `ignore = [{module = "pkg.mod", reason = "..."}]` excludes a module. `module = "pkg.sub.*"` excludes a subtree. An ignore must have a reason. No ignore is necessary for empty package markers. |
| `[facts]` | none | `model_sdks = [...]` adds import names to the SDK list of the language adapter. A `-` at the start removes a name of that list (`"-google.adk"`). The Python list contains Python import names, and the TypeScript list contains npm package names. |
| `[flows]` | none | `observed_by = ["subprocess", "queue", ...]` identifies mechanism words as structural evidence. A word does not show evidence for a flow. |
| `[rules]` | `unknown = "warn"` | `unknown = "fail"` makes `systemap check` and `systemap rules` exit 1 for an import rule with the result `unknown`. With `"warn"`, the commands print the result and do not reject the map. A different value or key gives a configuration error. |
| `[judgement]` | none | `answered = [{item = "<a judgement line>", reason = "...", evidence = "<SHA-256 digest>"}]` records an exact answer. `items = [...]` uses one digest for a group. Family forms are `crossing = ["A", "B", ...]`, `crossing_into = "A"`, `crossing_from = "A"`, `kind = "single module"`, and `module_sdk = "google.adk"`. They must have `policy = true`. `reviewed = ["<line>", ...]` records the baseline. The report counts new matches. All answers must have reasons. The report identifies stale answers. Audit kinds use this table too. This includes `"decision flow"`. The previous `jev` names stay correct for one release, with a warning. |
| `[judgement] require_reviews` | `false` | With `true`, each source component without a `source_review` digest gives a `missing source review` finding. Thus `judgement --strict` fails on a missing review. |
| `[judgement] answered` citations | none | An exact answer can have `citations = [{file = "pkg/a.py", start_line = 1, end_line = 9, sha256 = "<digest>"}]`. `systemap decisions submit` writes them. An answer without citations stays correct. |
| `[decisions]` | `provider = "jev"`, `max_contradicted = 3` | `provider` is the decision provider of `audit`, `triage`, `plan`, `delta --decide`, and `suggest --decide`: `"jev"` or `"openai"`. The `--provider` option of a command replaces this value. A key in the environment does not select a provider. [Which decision provider answers the questions?](#which-decision-provider-answers-the-questions) gives the data that goes to OpenAI. `max_contradicted` is the quantity of `contradicted` verdicts for one target of `systemap decisions` before the decision request becomes unknown. The value is a limit on repeated work, not a measured value. It must be an integer of 1 or more. A `[decision]` table gives a configuration error that tells you to use `[decisions] provider`. |
| `[jev]` | `model = "jev-latest"`, `cache = ".systemap/jev-cache.json"`, `enabled` unset | The model and cache for `audit`, `triage`, `plan`, `delta`, and `suggest --decide`. With `enabled = true` and `TYPESAFE_API_KEY`, `delta` sends questions to Jev without `--decide`. With `enabled` unset, `delta` sends no question without `--decide`, also with a key. `enabled = false` stops the hints. |
| `[openai]` | `model = "gpt-6-luna"`, `cache = ".systemap/openai-cache.json"` | The OpenAI Decisions model and the cache of its answers. systemap uses them only when you select OpenAI. |
| `[agent]` | `command` unset, `timeout = 300`, `cache = ".systemap/agent-cache.json"` | The command for sequence generation. It reads the question from stdin, for example `command = "claude -p --output-format json"`. With no command, nothing executes and the reason is printed. |
| `[delta]` | none | `page_url = "https://example.org/pr-{number}/"` gives the URL of the map page that the repository publishes for each pull request. The pull request number replaces `{number}`. With this value, `systemap delta --comment FILE --pr N` writes a comment with one link to the Changes view of that page. Without it, the command writes no comment. The URL must start with `https://` or `http://`. It must contain `{number}` and no other `{` or `}`. It must not contain `#` or a space character, because the link adds `#changes`. |
| `[writing]` | `profile = "plain"` | The writing profile for the map text that a person reads. `plain` selects the common writing rules of the skill's language policy. A person or a program can examine these rules without a dictionary. `asd-ste100` also selects the full ASD-STE100 Issue 9 rules. These rules need the official ASD dictionary. The skill reads this value. `systemap journeys` puts the policy of this profile in each agent request, so a different profile gets a new answer. A different value or key gives a configuration error. `init` writes `profile = "plain"`. |
| `[theme]` | `dark` | Color-token overrides. `scheme = "dark"` (Ink) or `scheme = "light"` (Paper) selects the default palette. The page offers both palettes. The earlier names `warm`, `graphite`, and `clay` give a configuration error. `[theme.light]` overrides one palette. `[theme.layers]` sets a color per layer ID, also for standard IDs. `[theme.marks]` selects a mark per agent kind. The `bg`, `raised`, `change`, and `reach` tokens, the `[theme.layers]` values, and the `layer_palette` items must be colors in the form `#RRGGBB`. The page uses theme values in HTML and CSS without conversion. Thus a value cannot contain `<`, `>`, `&`, `"`, `;`, `{`, or `}`. A font value (`font_ui`, `font_mono`) can contain `"`. A `[theme.marks]` value must be `ring`, `notch`, or `dotted`. A key in a theme table, such as `[theme.delta]`, can contain only letters, digits, `_`, and `-`. The page uses these keys in CSS names. |
| `[[figures]]` | none | Figures for `refresh`. Keys are `out`, `mode` (`system` or `reach`), `components`, `caption`, `interactive`, `layer`, and `map`. `layer` selects that layer's flows. `map` identifies a nested map. An `out` with `.svg` suffix writes the drawing alone. An `out` that is not in `out_dir` gives exit code 2. |

The environment of a command can set three values. A repository file cannot set them.

| Variable | Meaning |
|---|---|
| `TYPESAFE_API_KEY` | The key for Jev questions. Without it, no question goes to Jev. |
| `OPENAI_API_KEY` | The key for OpenAI questions. It does not select OpenAI. Without a selection, no question goes to OpenAI. |
| `SYSTEMAP_TRUST_MODEL_CODE` | With the value `1`, systemap runs the model files as Python code. Without it, systemap reads them as data. Set it only for a repository with safe code. |

TypeScript discovery does not include `.d.ts`, `.d.mts`, and `.d.cts` declaration files.
The `external` imports do not include Node.js built-in modules, such as `node:fs` and `path`.

Two types of import name a file of the same package through `package.json`. Thus they are internal imports:

- A self-name import names the package, as `import ky from "ky"` in the ky package.
  The nearest `package.json` above the file must have this `name` and an `exports` key.
- A subpath import starts with `#`, as `#types/hot`. The `imports` key of the nearest `package.json` gives the file.
  A target that names an npm package gives that package in `external`.

An import of a different package of the repository is also an internal import.
The `name` in a `package.json` file of the repository identifies that package.
The module that `[package_roots]` gives for the import must be in the folder of that `package.json` file.
A `[package_roots]` name does not identify a package for other imports.
Thus, if the package `web` has no `exports` key, `import "web"` in that package is an external import.

systemap uses the rules of Node.js and TypeScript for these imports:
[Self-referencing a package using its name](https://nodejs.org/api/packages.html#self-referencing-a-package-using-its-name),
[Subpath imports](https://nodejs.org/api/packages.html#subpath-imports), and
[package.json "imports" and self-name imports](https://www.typescriptlang.org/docs/handbook/modules/reference.html).

The conditions are `types`, `node`, `import`, and `default`. A `.cts` file uses `require` and not `import`.
systemap does not read `moduleResolution` or `customConditions`.

A target in `outDir` maps to its source file, as for a package entry point.
A declaration file has no module. Thus an import with a declaration file as its target is an unresolved local import.
An import without a target, for example a `#` name that `imports` does not have, is also an unresolved local import.

The suffix of an import selects the source suffix, as in `tsc`.
`.js` selects `.ts` or `.tsx`, `.mjs` selects `.mts`, and `.cjs` selects `.cts`.
An import without a suffix selects `.ts` or `.tsx`.
If `tsc` cannot resolve a relative import, the import has no target.
A `paths` alias names its first target file that is available, as in `tsc`.
If no module has that file, the import is an unresolved local import. A different target does not replace it.
An import path with a NUL character has no target.

A source file that systemap cannot read keeps its module record, with a read problem.
A `package.json` file that systemap cannot read gives a configuration error.
This also applies to a `package.json` file without a JSON object.

A TypeScript test name contains the names of the `describe` or `suite` functions that contain the test.
The text ` > ` is between two names, as in `orders > saves an order`.
If a file has two tests with the same name, the second name gets ` #2`.
If a different test of the file has that name, the name gets the next number that no test of the file has.
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
  An `include` pattern can select files that are not in the `tsconfig.json`
  directory, but only files in the repository.
  The selected files include tests and the source files that these files import.

- TypeScript 6 and later use the `tsconfig.json` directory.

- `composite` uses the `tsconfig.json` directory on all versions.

Each source file uses the compiler options of one `tsconfig.json` project.
The nearest `tsconfig.json` file gives the project if its files or their imports contain the file.
Then the first project in `references` that selects the file gives the project.
Then the first project in `references` with files that import the file gives the project.
These imports can go through other files.
These imports include relative imports, `paths` aliases, self-name imports, and subpath imports.
An import of a different package of the repository does not add a file to a project.
`tsc` reads the declaration output of that package for such an import.

The version comes from `node_modules/typescript/package.json`, then the
`typescript` range in `package.json`. This also applies if the repository root has no `tsconfig.json` file.
If the two files do not give a version, systemap tries the two roots.
A compiled target maps to a module only if one root gives a match and the other does not.
Two matches leave the target unmapped.

`check` prints unknown records without rejection.
Each unknown record must have a correction or accepted answer under
`[judgement] answered` before `judgement --strict` accepts it.
