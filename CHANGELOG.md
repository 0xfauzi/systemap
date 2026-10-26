# Changelog

Release notes give behavior at the named version.
Historical command output and configuration identifiers keep their recorded text.
A component is a system part with module claims in the map.
A sequence is an ordered set of map steps.
An entry point starts work in the system.
A layer is a filtered view of the map.

## Unreleased

### Security

- `systemap journeys` starts the `[agent] command` of the repository only if the environment sets `SYSTEMAP_TRUST_AGENT_COMMAND=1`.
  Previously, a cloned repository could set any command, and `journeys` started it with your permissions and environment variables.
  Without the value, `systemap journeys` starts no program. It names the value and exits 1.
  `journeys --dry-run` needs no value. `SYSTEMAP_TRUST_MODEL_CODE=1` does not give this permission.
  Examine the agent command of the repository. If you trust the repository, set `SYSTEMAP_TRUST_AGENT_COMMAND=1` for one command only.

### Changes

- `systemap extract` reads the JSONC text of a tsconfig file in linear time.
  Previously, an unclosed string or comment made the time quadratic: a file of 80 KB took 52 s.
  Now a file of 1 MB takes less than 0.2 s and gives the same error.
- A tsconfig `include` or `exclude` pattern has a cost that is linear in the length of the pattern.
  Previously, a pattern with 20 stars took 2.1 s for each file.
- One tsconfig load reads each `extends` or `references` file one time.
  Previously, a chain of files that extend the same file took exponential time: a depth of 16 took 39 s.
  Now a depth of 30 takes 0.014 s.
- `systemap live` scans the files in linear time.
  Previously, if `tests_dir` was not set, one scan of 20202 files took 290 s. Now it takes less than 1 s.
- `systemap live` keeps the text of each tsconfig file without comments.
  The watcher removes the comments again only after a change of the file.
- If a scan of `systemap live` takes more than half a second, the next scan starts after two times the time of that scan.
- A NUL character in tsconfig `extends` or `references`, or a tsconfig file with too many nested levels, does not stop the watcher of `systemap live`.
- If a scan of `systemap live` fails, the command writes an `error` event, and the page shows the error.
  The scans continue. `GET /status` gives the error until a scan gives a result again.
- The TypeScript reader reads each nested namespace one time.
  Previously, 20 nested exported namespaces took more than 70 s.
- If namespaces are nested deeper than 16 levels, the TypeScript reader records an unknown declaration.
  The reader does not read the declarations in that namespace.
- A `\u{...}` escape with a very large code point does not stop `systemap extract`.
  The reader treats the escape as not valid.
- `systemap extract` resolves `*` re-exports in a time that increases slowly with the size of the `*` graph.
  Previously, a diamond of 40 files with `export *` made extraction run for 108 s.
  A chain of 300 files with `export *` stopped extraction with a `RecursionError`.
  In a loop of `*` re-exports, each module now examines each module of the loop one time.
- In a loop of `*` re-exports, the order of the names of a module in `map.json` can change one time.
  The names come in the order of the records that give them. The names and the unknown records do not change.
  Thus the evidence digests of these modules can change one time.
- A source file name that is not valid UTF-8 does not stop `systemap extract`, `systemap refresh`, `systemap live` or the CI delta.
  The extractor does not read the file. It records the file with the cause `encoding`.
  The record shows each byte that is not UTF-8 as `\xNN`.
- A test file name that is not valid UTF-8 gives a `test_file_issues` record with the cause `encoding`.
- If a text value in the facts is not valid UTF-8, systemap gives an error that tells the cause. It does not write the facts file.
- Python extraction parses each module one time. Previously, it parsed each module about 10 times.
  A 6 MB module takes 93 s. Previously, it took 168 s.
- The `__main__` alias step reads the bindings of each module one time.
  Previously, it read them again for each use. 2000 uses take 1.7 s. Previously, they took 49 s.
- systemap does not read a source file that is larger than 16 MiB.
  It records the file as unknown, with the cause `size`.
  This limit is a guard for memory, not a measurement of the capacity of systemap.
- The map page finds the routes of the group lines with less work. The routes do not change.
- The map page does the route search of the group lines in small parts when the browser is idle.
  On a map with 72 components, the longest task at load was 10 s to 12 s. Now it is 0.2 s to 0.6 s in the recorded measurements.
- If the route search for a layer does not end in 120 ms, the map shows the group lines of that layer when they are ready.
- `systemap place --all` is faster. The label placement examines only the label boxes and obstacle boxes near each candidate.
  The positions that the command writes do not change.
  On a map with 36 components, the command time decreased from 401 s to 47 s.
- TypeScript relative imports and path aliases can name declaration files, including `.d.ts`, `.d.mts`, and `.d.cts`.
  These files have no module record. An import of an existing declaration file no longer gives an unresolved import finding.
  A re-export from a declaration file still gives an unknown public surface, with the declaration file cause.
- An untagged TypeScript comment directly before a variable declaration no longer gives the module description.
  Separate a module comment with a blank line, or mark its documentation block with `@module` or `@packageDocumentation`.
  The description excludes the tag and its module name. Other file headers retain their descriptions.
  Tagged descriptions keep their text when the tag precedes, follows, or separates summary lines.
- `judgement --order-by-drift` uses the provider selected by `[decisions] provider` or `--provider`.
  Previously, it always sent questions to Jev when `TYPESAFE_API_KEY` was set.
  OpenAI has no measured drift result. When OpenAI is selected, the command sends no data and gives the cause.
  A missing key or a failed request gives no score. The command does not send data to another provider.

## 2.0.0 - 2026-10-13

2.0.0 is the first stable release of systemap.
The earlier versions, 0.8.0 to 1.2.0 on PyPI and in git, are not supported.
The git history keeps their changes.
This section gives each change for a user of 1.2.0, the last version on PyPI.

A decision provider is a service that gives typed answers to typed questions about the map.
Jev and OpenAI Decisions are the two decision providers.
A source review is a recorded examination of the source that supports a claim. The map records it as a digest.

### Changes that can stop a command or change a CI result

Each item gives the change, and then the step that you must do.

- systemap reads a model file as data. It does not run code from the model file.
  In 1.2.0, `check`, `render`, `delta`, and the other commands ran `map/model.py` as Python code.
  A model file can contain only literal values, calls of the model classes, and names that the file defines.
  It can also contain `import NAME` for a file in the same directory, and a type alias such as `Steps = tuple[Step, ...]`.

  For other syntax, the command stops and gives the file, the line, and the refused syntax.
  A model file from `systemap init` loads with no change.

  Step: examine the code of the model file. Then run `SYSTEMAP_TRUST_MODEL_CODE=1 systemap convert` one time.
  The command writes the model with literal values only, and it writes the file only if systemap reads the new text to the same model.
  Set `SYSTEMAP_TRUST_MODEL_CODE=1` only for a repository with safe code. A repository file cannot set it.

- `systemap delta --format markdown` and its Mermaid diagram are removed.
  The workflow from `systemap init` 1.2.0 uses this option. Thus its delta job fails with exit code 2.

  The new workflow writes no map report comment by default. The delta job gives each line and its action in the job log.
  The new workflow is advisory: a map finding gives a warning annotation, and the job passes.

  `systemap init --strict-ci` writes a workflow in which a map finding makes the job fail. The variable `SYSTEMAP_CI` selects the mode.
  If systemap cannot run, the job fails in the two modes.

  Step: remove `.github/workflows/systemap.yml`. Then run `systemap init` again, with `--strict-ci` if CI must fail on a finding.
  `init` keeps your configuration and your model. If you changed the old workflow, compare it with the new file.

- An import between two components does not make a flow `observed`.
  In 1.2.0, an import made a flow `observed` and gave it a solid line.
  A flow is `observed` only if it has `source_refs` that agree with the current source, and a current `review_digest`.
  At least one source record must be in a module of the source component or the target component.
  An import, a shared module, or a `[flows] observed_by` mechanism gives the new state `structural`, with a short dashed line.

  `judgement` gives a `flow review` finding for each `structural` flow. Thus `judgement --strict` exits 1.
  A flow with `source_refs` and no record in an endpoint module gives a `no endpoint source` finding.

  Step: for each `flow review` line, examine the source. Then record the source records, and run `systemap review --flow` for the flow.
  You can also change the flow, or record an answer with a reason.

- A component can record a `source_review` digest after an examination of its source and claims.
  A `source_review` value that is not the current digest gives a `stale source review` finding, and `judgement --strict` exits 1.
  A missing value is not a finding. With `[judgement] require_reviews = true`, a missing value gives a `missing source review` finding.
  `judgement` counts the states on one line, for example `source reviews: 16 current, 0 stale, 0 missing`.

  Step: after each examination, run `systemap review ID` to write the current digest.

- An exact answer (`item` or `items`) in `[judgement] answered` must have an `evidence` digest.
  A family answer (`kind`, `crossing`, `crossing_into`, `crossing_from`, or `module_sdk`) must have `policy = true`.
  An answer without its value is pending. Thus `judgement --strict` exits 1.

  The evidence digest contains only the evidence that its line names: the claims of each named component, and the source of each named module.
  A change of the source or of the claims opens the answer again. A change of a different component does not.

  Step: examine the source for each `pending answer` line. Then write the digest from that line in `evidence`.
  Add `policy = true` to each family answer.

- The finding kinds that started with `jev` now start with `decision`, because Jev or OpenAI can give the answers.
  For example, `jev flow` is now `decision flow`.
  `--decide` and `--no-decide` replace `--jev` and `--no-jev` in `delta`, and `--decide` replaces `--jev` in `suggest`.
  The `entry point` line for a group of entry points gives the kind as words: `7 public functions into Api`, not `7 public_functions into Api`.

  Only this release reads the previous names, line forms, and options. Each previous item in `[judgement] answered` gives one warning.

  Step: replace each previous item with the line that the warning gives.
  [How do you change to the new finding names?](docs/reference.md#how-do-you-change-to-the-new-finding-names) gives the steps.

- `systemap delta` sends questions to a decision provider only on request.
  In 1.2.0, `delta` sent questions to Jev if `TYPESAFE_API_KEY` was set, because `[jev] enabled` was true by default.
  After this change, a key alone sends no request. Without an explicit `[jev] enabled` value, `delta` prints one hint.
  In the tests, a key with no `[jev]` table sent 3 requests before the change, and 0 requests after it.

  Step: to keep the suggestions, give `delta --decide`, or set `[jev] enabled = true` in `systemap.toml`.
  `[jev] enabled = false` stops the hint.

- Maps use the `plain` writing profile by default. The `[writing] profile` key selects `plain` or `asd-ste100`.
  `plain` uses the common writing rules: sentence length, active voice, literal words, and one term for one concept.
  `asd-ste100` adds the full ASD-STE100 Issue 9 rules, which need the official ASD dictionary.
  The instruction from `init` is "Obey the systemap skill and its writing rules."

  Step: to keep the full ASD-STE100 rules, add `profile = "asd-ste100"` in a `[writing]` table.

- The facts format is 12. In 1.2.0, it was 2. A facts file of an earlier format is stale.
  Thus `systemap check` and `systemap extract --check` exit 1 until you extract the facts again.
  The new facts have the same meaning for Python and TypeScript.
  They include `package`, `completeness`, `call_sites`, `types`, `same_as`, `symbol`, and a `cause` on each unknown record.
  `docs/reference.md` gives each fact.

  The extraction inputs include the configuration that extraction reads, with only the values that it reads.
  An example is an extended `tsconfig.json` file in `node_modules`.
  A change of `paths`, `baseUrl`, `include`, or the first number of the TypeScript version makes the facts stale.
  A change of a comment, an npm metadata field, or a workspace member `pyproject.toml` does not.

  Step: run `systemap refresh` after the upgrade, and commit the facts file.
  Then run `systemap check`, and correct each claim that it gives.

- Some Python facts changed. The coverage, crossing import, and entry point findings can change:

  - An empty package marker is a module that has no statement that holds code. A private assignment with a function call makes a source module.
  - Python overload signatures give one public name.
  - A console script, a main function, and a command that start the same function give one entry point.
  - A license notice is not a module description.
  - A Python function fingerprint includes its decorators.
  - The configured `test_patterns` apply to Python, with the same rule as TypeScript.
  - A component `entry` can be the label of an entry point that starts no single public name, such as a `__main__` module.

  Step: run `systemap refresh`, `systemap check`, and `systemap judgement`, and correct each new finding.

- The model check refuses more models:

  - A flow from a component to itself. The line starts with `placement: flow A -> A has the same component at the two ends`.
  - Two sequences with one ID, and two components that open the same nested model file.
  - A component that opens a map with an ID that is not one path segment.
  - Two regions or containers with the same ID.
  - A flow sentence that contains only spaces.
  - A model value with an incorrect type. This gives a configuration error.
  - Two flows without an `id` on different pairs that give the same default identifier, for example `A->B` to `C` and `A` to `B->C`.

  `place` and `describe` exit 1 for a flow to an unknown component, or for an unknown component `kind`.

  Step: correct each flow, sequence, region, and component that `systemap check` gives.

- The facts are stale if the specification sections change.
  `check` then gives the line `specification sections changed since the map was built`.
  An output file that is not UTF-8 text is a stale output in `check` and in `render --check`.

  Step: run `systemap refresh`, and commit the facts file and the outputs.

- The page has two themes: Ink (`scheme = "dark"`, the default) and Paper (`scheme = "light"`).
  The 1.2.0 scheme names `warm`, `graphite`, and `paper` give a configuration error. A `[theme.paper]` table also gives an error.

  Step: in `[theme]`, set `scheme = "dark"` or `scheme = "light"`. Move the values of a `[theme.paper]` table into `[theme.light]`.

- The theme values and the model names go into the page as CSS and HTML. Thus systemap refuses unsafe values:

  - A theme value that contains `<`, `>`, `&`, `"`, `;`, `{`, or `}`. A font value can contain `"`.
  - A key in a theme table that contains a character other than a letter, a digit, `_`, or `-`.
  - A `[theme.marks]` value other than `ring`, `notch`, or `dotted`.
  - A theme value of an incorrect type. A color token, `color_scheme`, and each `delta` value must be text. Each `state` record has 3 texts, and each `container` record has 2 texts. `ghost` has 2 texts.
  - A custom layer ID that contains a character other than a letter, a digit, `_`, or `-`.
  - The component IDs `_meta` and `__proto__`.

  `systemap figure --caption` and `[[figures]] caption` are text, not HTML. The `--svg-id` value must start with a letter.

  Step: correct each value that the error names. Remove HTML from each caption.

- systemap reads and writes files only in the repository or in their specified root:

  - `systemap.toml`, `pyproject.toml`, `package.json`, the model file, and each `tsconfig.json` file must be regular files in the repository.
  - A link out of the repository or a FIFO gives a configuration error with the path and the cause.
  - A `package.json` file that systemap cannot read, or that has no JSON object, gives a configuration error.
  - A `pyproject.toml` file that is not correct TOML gives a configuration error. In 1.2.0, it gave an empty table.
  - A package root that is not in the repository is a configuration error.
  - A configured cache path (`[jev]`, `[openai]`, or `[agent]`), `out_dir`, or `model` that is absolute or that has a `..` part is a configuration error.
  - The facts file and each configured figure must be in `out_dir`. A different path gives exit code 2.
  - A cache file or an output file that is a link to a different folder, a FIFO, or a device gives exit code 1.
  - A `tool` or `tool.systemap` value in `pyproject.toml` that is not a table gives a configuration error.
  - A relative `figure --out` path is relative to the output directory. Its folder must be in the repository, or the command exits 1.
  - `serve` refuses an output directory that is not in the repository, and the server does not start.
  - `figure --out` and `delta --comment FILE` replace a link at the path. They do not write to the target of the link.

  Where the platform permits it, each read and write opens each part of the path without links.
  Thus a folder that changes to a link after the check is refused. Windows keeps the earlier check.

  A `tsconfig.json` target in the `node_modules` folder of the repository stays permitted.
  A missing configuration file gives an empty table.

  Step: put each configuration file, the model, and each package root in the repository.
  Give each configured path relative to the repository root. Remove each link or FIFO that an error names.

- `systemap judgement --strict` exits 1 for a model without components, as `systemap check` does.

  Step: write the components before you use `judgement --strict` in CI.

- Some commands give a different exit code:

  - `delta` exits 2 if Git finds no merge base of the two refs. In 1.2.0, `delta` used the base commit as the merge base.
  - `history` exits 2 if Git cannot resolve `--ref` or if a Git command fails.
  - `place` loads the model file again after its write. If a position is different, it restores the earlier file and exits 1.
  - `journeys --limit` must be 1 or more. `journeys` exits 1 and names each request that did not complete.
    A rejected draft is also a request that did not complete.
    A missing source file, an agent command with an incorrect quotation, or an agent that cannot start gives exit 1.
  - The `ok` value of `rules --json` agrees with the exit code. Missing facts are an item of `problems`.

- `init` writes no `systemap.toml` if `pyproject.toml` has a `[tool.systemap]` table. It writes the model at the `model` path of that table.

- Some printed text changed:

  - `delta` says `The map needs an update (N):` or `The map is current.`
  - `judgement` says `N possible map errors to examine` or `No possible map error to examine`.
  - `check` gives meaning errors under `map meaning`, and import rule field errors under `import rule fields`.
  - The `delta` count text is `N of M components have changes`.
  - The `evidence lost` line of `delta` says "had a current source review" in place of "was observed".

  The finding lines that identify a finding did not change, except the lines that the earlier items give.

### New commands and options

- systemap reads TypeScript. Install the extra: `uv tool install 'systemap[typescript]'`.
  The TypeScript adapter reads `.ts`, `.tsx`, `.mts`, and `.cts` modules, with the `tsconfig.json` project of each file.
  It reads exports, re-exports, imports, test references, and the `bin` and `exports` entries of `package.json`.
  Module resolution, project selection, and the output root agree with `tsc`.
  A test name contains the names of the `describe` or `suite` functions that contain the test, for example `orders > saves an order`.

  For TypeScript, `init` selects the package root from the one source folder of the `tsconfig.json` `include` entries.
  It writes `test_patterns` for the type-test folders and files. If `init` selects no root, it gives the cause and the `[package_roots]` table to write.

  The `language` key selects `python` or `typescript`. Without the key, systemap finds the language from the source files.
  If the evidence for Python and the evidence for TypeScript are equal, the command stops and tells you to set the key.

- `systemap live` renders the map of the working tree and supplies it on 127.0.0.1.
  When a source, model, or configuration file changes, the command renders the map again.
  The browser loads the page again and keeps the view, the layer, the selection, the sequence step, and the camera.
  The Changes view compares the working tree with the merge base of a base ref and HEAD.
  `--json`, `GET /status`, `GET /events`, and `POST /refresh` give the state and the map update lines to other programs.
  The command writes its pages into a temporary directory, not into tracked files.

- The Claude Code plugin shows a live map. In a repository with systemap configuration, one line above the prompt shows `map: not started · Start live map`.
  `Start live map` or `/map` starts `systemap live`. After a turn that changes files, the plugin renders the map again.
  `Show` and `/map` open a pane with the change figure and the map update lines.
  The `command` option sets the command that starts systemap. The `autostart` option is false by default.

- `systemap convert` writes each refused model file again with literal values only.

- `systemap review COMPONENT` writes the current `source_review` digest of one component into the model file.
  `systemap review --flow ID` and `systemap review --flow 'SRC->DST'` write the `review_digest` of one flow.
  The command writes one target for each call, because a person or an agent must examine each claim.
  It does not examine the claims. It keeps the comments and the format of the model file.

- `systemap judgement --json` writes one JSON object for programs. The schema version is 3.
  The object gives each open line with its kind, its detail lines, its `cause`, and its `sources`.
  It also gives the evidence digest that an exact answer must have.
  It also gives the answers, the stale answers, the source review counts, and the counts for each kind.
  The exit codes are the same as in the text mode.

- `systemap decisions pending`, `systemap decisions submit FILE`, and `systemap decisions status` give the claims of the map to a coding agent.
  The agent examines each claim and sends a verdict: `supported`, `contradicted`, or `insufficient_evidence`.
  Each verdict gives citations: the file, the line span, and the SHA-256 digest of the current file.
  systemap examines each citation. Then it records each `supported` verdict as a review digest or as an exact answer.

  These commands send no request to a model.
  At `[decisions] max_contradicted` verdicts of `contradicted` for one target, the decision request becomes unknown.
  The default limit is 3. A change of the map does not set the count to zero. A change of a source file of the target does.

- A model can contain import rules (`ImportRule`). The `kind` values are `forbid_import`, `allow_imports`, and `forbid_cycle`.
  The result of a rule is `pass`, `fail`, or `unknown`.
  `unknown` occurs if a module did not parse, or if the facts possibly do not contain all its imports.
  `systemap check` and `systemap refresh` exit 1 for a `fail` result. `systemap rules [--json]` gives the result of each rule.
  With `[rules] unknown = "fail"`, these commands also exit 1 for an `unknown` result.

- `systemap judgement --order-by-drift` sends one Jev question for each open `stale source review` line.
  The answer is the drift score: the probability that the claims of the component agree with its changed source.
  The report puts the stale lines in sequence from the lowest score.
  The score does not close a line, and it does not change the exit code.
  No measurement gives a threshold for the score. Thus the option has no threshold.

- OpenAI Decisions is a second decision provider (`POST /v1/decisions`, model `gpt-6-luna`).
  To select it, give `--provider openai`, or set `[decisions] provider = "openai"`. Set `OPENAI_API_KEY` too.
  A key alone does not select OpenAI.

  The thresholds come from the Jev bench rows: five development maps and three holdout maps of Python repositories.
  A question kind is available only if each holdout figure is 10 points or less from its development figure.
  The available kinds are `decision owner`, `decision sentence`, `decision flow`, and `decision governs`.

  | kind | threshold | development | holdout |
  |---|---|---|---|
  | `decision owner` | confidence 0.99 or more | 9.5% of modules get one component, 100% correct | 4.7%, 100% correct |
  | `decision sentence` | P < 0.3 | 81.0% of incorrect sentences found, 1.3% incorrect findings | 75.0% found, 0.0% incorrect findings |
  | `decision flow` | P < 0.02 | 27 of 80 incorrect claims found (33.8%), 2 of 80 incorrect findings (2.5%) | 18 of 48 found (37.5%), 3 of 48 incorrect findings (6.2%) |
  | `decision governs` | P 0.99 or more | 19.8% of applicable components found, 1.1% of other components proposed | 17.2% found, 6.0% proposed |

  The other kinds are not available for OpenAI. The command sends no question for them and gives the cause.
  `decision mis-fold` found 82.1% of incorrect component assignments on development, and 61.5% on holdout.
  `triage` put the correct component first in 82.5% on development and 69.2% on holdout.
  `plan` included 0.73 of the changed components on development and 0.39 on holdout.
  The pair question of `suggest --decide` and the move question of `delta --decide` have no holdout rows.

  The `decision flow` threshold of OpenAI comes from a measurement with the context from the `call_sites` fact. The command uses the same context.
  On the same development rows, Jev found 48 of 80 incorrect claims (60.0%) at its threshold P < 0.2.
  The 1,636 bench requests used 1,211,893 input tokens and cost 0.12 dollars.
  The 256 requests of the flow measurement used 213,942 input tokens and cost 0.02 dollars.

- A flow can have an `id`. Two or more flows can then connect one pair of components, for example `submit-order` and `cancel-order`.
  Each of these flows has its own sentence, review digest, and judgement lines, and the map shows each one as a different line.
  A sequence step can name a flow with `flow="ID"`. A step can also have `source_refs`, which `judgement` validates.
  A model without ids keeps its finding lines and digests.

- Each language adapter writes a `call_sites` fact. The Python adapter uses `ast`, and the TypeScript adapter uses tree-sitter.
  The fact gives the lines that use an imported name.
  It also gives the lines that use a local name that gets its value from an imported name, such as `ledger.record(parts)`.

  The `decision flow` question gets its source lines from this fact.
  On the Jev bench rows at P < 0.2, it found 48 of 80 incorrect claims on development. It gave a finding for 2 of 80 correct claims.
  On holdout, it found 25 of 48 incorrect claims, and it gave a finding for 1 of 48 correct claims.
  This result satisfies the acceptance value. The earlier context did not satisfy the same value.

  `decision flow` stays out of the default kinds of `audit`, because no TypeScript row set is available.

- A source module or a test file that the parser cannot read or parse is a not-known record. It does not reject the map.
  A parser can refuse correct source, and systemap is not a syntax checker.
  `check` and `refresh` print the module or the test file in the `source inventory unresolved` group, with its cause and its `fix:` line.
  Each result that reads such a module is not known: the component gets no source review digest, and an import rule gives `unknown`.

- A finding line contains only the parts that identify the finding: no line number, source excerpt, parser version, or time.
  The judgement report gives these values in the `at:`, `excerpt:`, and `parser version:` rows below the line.
  Thus a recorded answer stays applicable when a line is added above the cited statement. A change of the statement opens it again.

- `[delta] page_url` gives the URL of the map page that the repository publishes for each pull request.
  With this value, `systemap delta --comment FILE --pr N` writes one comment with a link to the Changes view.
  The workflow from `init` posts that comment, and changes it after each push, for a pull request from a branch of the same repository.

- The Changes view lists the components, flows, sequences, and rules that a change added, removed, or changed in the model.
  The map page has a Find dialog (Ctrl+K, Cmd+K, or /), the Ink and Paper themes, and a Details panel.

- The website at <https://0xfauzi.github.io/systemap/> has a landing page, eight guide pages, the reference, and the benchmarks.
  The pages make no requests to other sites.

- Output files get the mode of a usual write with the umask. An existing file keeps its mode.

- A name that systemap cannot know is "not known", and it gives no missing-name error.
  Examples are an interface method of a re-export with an unknown definition, and an entry of a module with unknown names.
  A link loop in a Python or TypeScript repository is a module that could not be read. It does not stop extraction.

### Security repairs

- systemap reads a repository file only if it is a regular file in the repository.
  The facts, the configuration, and the model can give an absolute path, a path with a `..` part, or a symbolic link.
  During development, such a path could make `audit` read a file that is not in the repository and send its text to Jev.
  The readers refuse these paths. Extraction records a link to a file that is not in the repository as a module that did not parse.
  In 44 tests, no request body contains a marker from a file that is not in the repository.

- A model value or a Git ref cannot be an option of `git`.
  A `source_review` value must be a 64-character hexadecimal digest before it goes to `git grep`.
  `git grep` gets the commit after `--end-of-options`. The ref resolution of `delta` also uses `--end-of-options`.

- Each file read and each file write stays in the repository or in its specified root.
  A cache file or an output file is read, written, and locked only in its root.
  A link at the cache folder or at a parent folder is refused. A write replaces a link, and it does not write to the target of the link.
  A refused source file gives its cause in the decision request and in the evidence state, not "missing source".

  A guard test, `tests/test_read_guard.py`, reads the syntax tree of each module in `src/systemap`.
  It gives a failure for each file read or write that is not in an allow-list. Each allow-list entry gives its cause.
  When the test was added, it found 47 reads and writes. 19 of them were defects.

- `systemap serve` and `systemap live` answer only a request whose Host header is `127.0.0.1` or `localhost` with the server port.
  A web page that makes its own domain name point at 127.0.0.1 cannot read the map.

### Language repairs

The two language adapters write facts with the same meaning. Shared code reads only these neutral facts.
One `LanguageAdapter` protocol gives the language operations.
A test, `test_no_shared_module_tests_a_language`, finds no language test in the shared modules.

During development, a search found 14 locations in shared code that gave an incorrect result for one language.
Each repair has a Python test and a TypeScript test. These are examples:

- TypeScript entry points showed as empty lines on the page.
- The schematic gave `.py` paths for TypeScript files.
- A dot in a TypeScript file name, such as `user.service.ts`, made a package.
- The TypeScript adapter recorded interfaces, enums, and type aliases in `classes`. The `types` fact holds them.
- `judgement` read a dot in an npm package name as a separator. Each adapter gives its import separator.
- `systemap live` watched `package.json` and `tsconfig.json` in a Python repository. It watches the configuration files of the configured adapter.

### Trials on open-source repositories

Four trials operated systemap on open-source repositories before this release.
For each problem, a test showed the failure before the repair.

| trial | repositories | problems | not repaired |
|---|---|---|---|
| 1 | pallets/click, encode/httpx, sindresorhus/ky, vitejs/vite | 20: 16 that the source shows, and 4 that are not sure | 2 |
| 2 | the same four repositories | 6 | 0 |
| 3 | sindresorhus/ky, vitejs/vite | 8 | 0 |
| 4 | the same four repositories | 2 | 0 |

The most important repairs:

- A source module or a test file that the parser cannot read is not known. It does not reject the map. Before the repair, `check` always gave exit 1 on vite.
- Each unknown record has a cause and a `fix:` line that the user can do.
- A recorded answer stays applicable when lines move above the cited statement.
- TypeScript self-name imports and `#` subpath imports are internal imports. `init` selects the package root from the `tsconfig.json` `include` entries.
- Python overloads give one public name, and one CLI function gives one entry point.
- Output files had mode 0600, and a web server that operates as a different user could not read the page. Output files now get the usual mode.

Two problems of trial 1 are not repaired:

- A comment on a constant can become a TypeScript module description. A measurement is necessary before a change.
- A name that is not in a literal `__all__` stays a public name, because the modules of the package import such names.

### Repairs from the code review

A Codex code review (`gpt-6.1-sol`, high reasoning, read-only) examined the code at d4b1514, before this release.
It gave 101 results: 9 high, 79 moderate, and 13 low.
For each result, a test showed the failure before the repair, and the same test passed after the repair.

| area | results | examples of repairs |
|---|---|---|
| language adapters | 28 | TypeScript resolution agrees with `tsc` for `.mjs`, `.cjs`, failed relative imports, and project selection. Re-exports keep their defining module. Python star re-exports and decorators are recorded. |
| model, evidence, and judgement | 14 | Interface names can contain Unicode letters. An empty relation sentence is a finding. A model value with an incorrect type gives a configuration error. |
| change detection, delta, sequences, plans, and caches | 25 | A file that a side cannot read is not known, not removed. A sequence ID that the map uses is refused. The Jev cache keeps the entries of two writers. |
| commands | 16 | `place` restores the model file after an incorrect write. `refresh` examines the import rules. `live`, `init`, and `skill` write only in their directories. |
| page | 10 | A flow artifact with the name `constructor` does not stop the page script. A removed sequence or flow gives no selection after a live load. |
| schematic | 8 | Theme keys, layer IDs, and component IDs that are not safe are refused. The inline JSON escapes `<!--`. |

These are the Windows repairs:

- The agent runner sends and reads UTF-8 bytes.
- A cache read holds the lock of its cache.
- `place` and `review` write LF line ends.
- Messages give paths with forward slashes.

A second Codex code review examined the code for four types of defect:
a crash, an unsafe access, a silent incorrect result, and a defect that stops a real repository at `systemap check`.
It examined six parts at 13a7f45, and the page and the schematic at dd05bee.
It gave 66 results. For each result, a test showed the failure before the repair, and the same test passed after the repair.

| area | results | examples of repairs |
|---|---|---|
| Python adapter and shared facts | 14 | A link loop is a module that could not be read. An empty `__all__` gives no star names. |
| TypeScript adapter | 14 | A `paths` alias names its first target file that is available, as in `tsc`. Each test of a file gets a different identity. |
| model, evidence, and judgement | 9 | A layer list in place of a tuple does not stop `check`. Two flows with one default identifier give a finding. |
| decision requests | 5 | The claim of a source review request contains each claim of its digest. A result file that is not UTF-8 gives a command error. |
| change detection, sequences, agents, and plans | 10 | Each revision resolves its test imports with its own files. `journeys` reads the changed model before it writes. |
| commands | 6 | `serve` and `figure --out` stay in the repository. A route does not go through an unrelated region when a corridor is available. |
| page | 5 | A child map link encodes the component ID, so model text cannot operate as code. An actor named `constructor` does not stop the page script. Entry-point coverage uses the modules of its map. |
| schematic | 3 | A theme value that rendering cannot use is a configuration error, not a crash. A layer named `__proto__` shows its flows. |

On macOS, a lock open relative to a folder can fail with ENOENT. In a test of 8 processes, 429 of 2400 opens failed.
The lock open tries again after ENOENT. The same test then gave 2400 of 2400 correct opens.

#### Security repairs from the code review

- systemap reads `package.json`, `systemap.toml`, `pyproject.toml`, and each `tsconfig.json` target only in the repository. The live watcher does not watch a path that is not in the repository.
- The Git tree reader refuses a committed path with a backslash, a colon, a `..` part, or a `.git` part.
  It also refuses a link that goes out of the tree. `delta` and the Changes view give each refused path as not known.
- `history` resolves `--ref` to a commit before it calls `git log`. A pull request value that starts with `-` does not go to `gh`. The facts cache accepts only a full commit SHA.
- `live`, `init`, and `skill` write no file through a symbolic link that goes out of their directory. `serve` and `live` answer 404 for a symbolic link to a file that is not in the served directory.
- The figure gives captions, layer names, and model text as text, not as HTML. Theme values, theme keys, layer IDs, and SVG IDs cannot add HTML or CSS.
- The agent runner stops an agent that writes more than 200,000 bytes to stdout.

#### Performance

Each repair below had an acceptance value before the change. `bench/jev/README.md` gives the method and each run.
The times are medians on one macOS computer. The fixtures have 40,000 files in `node_modules` where the table says so.

| measurement | before | after | acceptance value |
|---|---|---|---|
| TypeScript `extract.build`, time with `node_modules` divided by time without | 11.251 to 12.536 | 1.008 to 1.019 | 1.2 or less |
| TypeScript language detection, the same ratio for four calls | 2582.20 to 3911.65 | 1.005 to 1.029 | 1.2 or less |
| Python file list, the same ratio for three calls | 438.81 to 4472.93 for the two calls that read `node_modules` | 0.773 to 1.094 | 1.2 or less |
| Python test file list, the same ratio | 377.36 and 519.63 | 1.001 to 1.012 | 1.2 or less |
| Git tree reader, memory increase for a 256 MiB file, compared with 20 modules | 887 to 898 MiB | 2.0 to 4.1 MiB | 64 MiB or less |
| Git tree reader, time for 2000 modules (4 runs) | 1562 to 2028 ms | 1551 to 1819 ms, a ratio of 1.05 for the medians | a ratio of 1.2 or less |
| render with 5 nested maps, time divided by the time for 1 map | 4.91 | 1.19 and 1.00 | 1.5 or less |
| page label script with sequence marks in a pan, time divided by the time before the mark boxes | 1.80 (first repair) | 0.95 and 0.96 | 1.2 or less |
| live watcher scan on this repository | 1.44 ms | 1.74 and 1.75 ms | 2 times the earlier time or less |

The label script measurement has a small margin when the computer has a high load. A second measurement gave 1.19 and 0.88.
