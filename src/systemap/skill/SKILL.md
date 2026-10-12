---
name: systemap
description: Makes or updates a system map from repository source code. Use it for map/model.py, systemap.toml, component assignments, flows, sequences, invariants, and map checks. Also use it when a person asks for a map or diagram of repository components and flows. Use it when a line from systemap check, judgement, audit, or delta identifies a necessary action. It extracts source facts, writes the model in ASD-STE100, gives positions to components, examines source claims, renders the map, and records answers to findings. Use systemap delta for source changes after the first map.
license: MIT
compatibility: Python 3.11+ and the systemap package (uv tool install systemap). Delta and history use Git. Jev commands use TYPESAFE_API_KEY and network access.
---

# Make or update a system map

A map has source facts and an authored model.
`systemap extract` reads modules, exports, imports, and entry points from source code.
The model gives component assignments for source modules and identifies each flow artifact.
A maintainer must examine these claims against source code. A structural check without failures does not show that a claim is correct.
The model is a Python module, usually `map/model.py`, with `MODEL` and `MEANING`.

Run commands from the repository root. Use `--root DIR` for another repository.
If the `systemap` command is missing, tell the maintainer. `uv tool install systemap` or `uv add --dev systemap` installs it.
For a TypeScript repository, the `systemap[typescript]` package is necessary.
If `systemap.toml` is missing, run `systemap init`.

## Mandatory language requirement

You must use ASD-STE100 Issue 9 for all names and all text that a person reads.
This requirement applies to every new map and every map update.
It includes component names, artifacts, layers, sequences, steps, invariants, explanations, and recorded reasons.
Before you write, read [references/language.md](references/language.md) and the official ASD rules and dictionary.
Use approved meanings and parts of speech. Use technical terms only with their glossary meanings.

Do not change commands, schema keys, identifiers, or quoted source evidence.
If the official reference is not available, tell the maintainer. Do not complete language acceptance.
Do not use an automated word-list check as the only evidence that the text obeys the standard.

## Jev answers

Jev is the TypeSafe model for questions that imports and names cannot answer.
With `TYPESAFE_API_KEY`, use `suggest --jev` and `audit`.
The `delta` and `triage` commands can also use Jev.

Without a key, use source examination in `references/second-pass.md`.
If Jev fails, show the failure. Then use the same source examination procedure.
Tell the maintainer which procedure you used. Examine modules without findings also.

## The loop

A first draft can omit flows or give a module an incorrect component assignment.
Structural checks cannot find every omission. Source examination is necessary.
Copy these lines into your answer. Mark each step when it is complete.

```text
- [ ] 1 extract: The facts are current.
- [ ] 2 draft: Each nonempty module has a component assignment. All components have positions.
- [ ] 3 check: The check has no failures. A `stale` finding can stay until step 5.
- [ ] 4 judgement: No judgement line or `jev` line stays without an action or an answer.
- [ ] 5 render: The page and figures are current, and you examined both figures.
- [ ] 6 source review: A complete source examination causes no model changes.
- [ ] 7 stop: The work agrees with each stop condition.
- [ ] 8 completion: The maintainer has the completion report.
```

1. **extract**: Run `systemap extract`. Read its output through `systemap facts`.
   Do not open the complete facts JSON for routine examination.
   Use `--docstrings` for source descriptions and `--names NAME` for public symbols.
   Use `--entry-points` for sequence inputs and `--module NAME` for a complete module record.
   Give every nonempty module a component assignment.
2. **draft**: If Jev is available, use `systemap suggest --jev`.
   Otherwise, use `systemap suggest`. Examine the proposed assignments against source.
   Read the repository's own documentation: its README, AGENTS.md, CLAUDE.md, docs/.
   Read `references/schema.md`, `references/example.md`, `references/layout.md`, and `references/pitfalls.md`.
   Also read `references/layers.md` and `references/journeys-and-invariants.md`.

   Write components and flows without `x` and `y`. Run `systemap place`.
   The command searches region orders and compares route collisions, refusals, bends, and length.
   Do not replace this search with a helper script.
   After component additions or removals, run `systemap place --all`.
   This command keeps only positions marked `pinned=True`.
3. **check**: After each change, run `systemap check && systemap judgement --strict`.
   Correct each check failure. Act on or answer each judgement line.
   Before you render, the check can have only a `stale` finding. If you remove a flow, crossing-import findings can open again. Do the judgement check again.
4. **judgement**: Run `systemap judgement`. Record an answer for each open line in `systemap.toml`.
   Use `[judgement] answered` with a reason and one of these forms:

   - `item = "<line>"`: the full line without indentation.
   - `items = ["<line>", ...]`: a nonempty list of full lines with one reason.
   - `crossing = ["A", "B", ...]`: all crossing imports between two or more different identifiers, in either direction.
   - `crossing_into = "A"`: all crossing imports into one component.
   - `crossing_from = "A"`: all crossing imports from one component.
   - `kind = "<kind>"`: all lines of one finding kind.
   - `module_sdk = "<import>"`: all model SDK lines for one import name.

   Exact answers must have a current evidence digest. Broad answers must have `policy = true`.
   Do not leave unanswered lines. Examine source again for each stale answer.

   | kind | finding | action |
   |---|---|---|
   | `single module` | A component has one module. | If the component is a different system part, keep it. If not, put its modules in the applicable component. |
   | `possible mis-fold` | A module and its component have no common name word or package. | Examine its function. Give it the correct component assignment or record the reason. |
   | `no sentence` | A flow has no relation sentence. | Write its action from the source component. |
   | `thin layer` | A layer has fewer than two components or no flows of its standard kind. | Add flows with source evidence or record why none apply. |
   | `entry point` | An entry point has no sequence coverage. | Write its sequence or record why it is not necessary. |
   | `journey start` | A sequence starts at an unknown entry point. | Use the facts label or an empty `starts` value. |
   | `drafted journey` | An agent sequence still has no source examination. | Examine every step. Correct errors before removal of `drafted=True`. |
   | `crossing import` | Components have imports between them but no flow. | Examine the imports. Add a flow with source evidence, change assignments, or record why no flow is necessary. |
   | `declared flow` | A flow has no structural or source evidence. | Examine source support. Add source records or remove the flow. |
   | `flow review` | A flow has structural evidence or stale source records. | Examine direction and artifact against current source. Renew the record or correct the claim. |
   | `no endpoint source` | No source record of a flow is in a module of its source or target component. | Add a source record from an endpoint module that sends or receives the artifact, or change the flow. |
   | `stale source review` | The `source_review` digest of a component is not the current digest. | Examine its source and all its claims again. Then record the current digest. |
   | `model sdk` | A module imports a model SDK without a model-calling component. | Use `kind="agent"` or `calls_model=True` as applicable. Add context and tool flows with source evidence. |
   | `unknown surface` | The extractor could not read source syntax, configuration, or an export with sufficient confidence. | Correct the extractor, source, or configuration. Otherwise, record the specific limit. |

   When Jev is available, run `systemap audit`. Act on or answer its `jev ...` lines.
5. **render**: Run `systemap refresh`. Then run `systemap describe`.
   The description gives component counts, route bends, gutter use, and layer contents.

   Run `systemap serve`. Open its URL.
   Examine `docs/map/figures/structure.svg` before `docs/map/figures/system.svg`.
   Find routes with many bends, full gutters, isolated regions, and empty layers.
6. **source review**: Do the procedure in `references/second-pass.md`.
   Examine every module assignment, crossing import, declared flow, entry point, and applicable invariant.
   Read README, AGENTS.md, CLAUDE.md, the documentation index, and the first level of docs/.
   If new rules apply only to source outside the repository, do not read more documents.
   Examine the figure again. If anything changes, return to step 3.
7. **stop**: If a check fails or `judgement --strict` does not exit 0, do not complete the work.
   With Jev, the audit must also have no unanswered lines.
   A complete source examination must cause no more model changes.
   Documentation that you did not read must have no rules for source in this repository. Complete the language acceptance procedure in `references/language.md`.
8. **completion**: Give the maintainer the completion report. The Completion section gives its lines.

## Source changes after the first map

Use `references/maintenance.md` for a map already in use.
Do not replace the full model for a small source change.

1. Run `systemap delta --base REF` against the base branch.
   Each line identifies a change and the necessary map action.
   A `hint:` or `delta --jev:` line means Jev did not supply answers. Tell the maintainer.
2. Act on these lines in `map/model.py` and `systemap.toml`.
3. Run `systemap refresh`. Then run `systemap check && systemap judgement --strict`.
4. If delta identifies more than one-third of the components, do the full loop.
5. Do the language acceptance procedure for every changed name and sentence.

## Model contents

A component is a system part with one clear function.
Use source functions for component assignments, not only directories.
`implemented_by` lists modules or exact `pkg.mod:name` symbols.
`entry` identifies one public symbol from those modules.
The kinds are `component`, `store`, `actor`, `agent`, `tool`, and `context`.
An actor is a person or system outside the mapped source.

A flow carries one artifact between two components.
Standard kinds are `data`, `control`, `context`, and `tool`.
Each other kind must have a declaration in `flow_kinds` and a layer assignment.
Use one to three words for an artifact noun phrase. Write one relation sentence from the source component.
Write one short name in `plain` for each component.

Every flow has an evidence state:

- `structural`: an import, common module, or configured observation gives structural evidence for a relation only.
- `observed`: a current source review. Current source records and a claim digest support direction and artifact. At least one record is in a module of an endpoint.
- `external`: one endpoint is an actor.
- `declared`: no structural evidence or examined source supports the flow.

Structural and declared flows use dashed lines. Examine their source evidence. An import alone does not show an artifact or its direction. Never renew a digest without source examination.

Write sequences for the entry points that are important to a reader.
`starts` is a display label. `covers` contains exact examined entry identities.
Examine coverage for each newly found entry point.

Invariants come from repository rules, source clauses, assertions, or tests.
Cite the source of each invariant. Do not put a proposed rule in the recorded invariant list.

Select the region for each component. Use `systemap place` for positions.
A route must not cross an unrelated region.
Use `pinned=True` only for a position that must stay fixed.

A component with more than ten modules can have a nested map.
Maps with more than forty components also receive a nested-map suggestion.
`map="gateway.py"` identifies a model beside the parent model.
Its internal components must cover all of the parent's module claims, without additions.
Its actors represent adjacent components. Commands examine every nested map.

## Commands

| command | result |
|---|---|
| `systemap init` | Write missing configuration, initial model, skill, and CI workflow. With `--no-ci`, do not write the workflow. With `--strict-ci`, the workflow fails on a map finding. |
| `systemap extract` | Write source facts. `--check` exits 1 for stale facts. |
| `systemap facts` | Show one source view: `--modules`, `--docstrings`, `--module NAME`, `--names NAME`, `--entry-points`, `--external`, or `--imports NAME`. |
| `systemap place` | Write positions for components without positions. `--all` keeps only pinned positions. `--keep-order` keeps region order. `--print` shows positions without file changes. |
| `systemap render` | Write the page. `--check` exits 1 for stale output. |
| `systemap check` | Examine map consistency and coverage. Exit 0 means success, 1 means failed checks, and 2 means that the command cannot use the configuration or model. |
| `systemap suggest` | Show initial package assignments. `--jev` uses Jev answers. Examine all proposals against source. |
| `systemap judgement` | Show possible map errors. Correct each one or record an answer. `--strict` exits 1 for unanswered lines. `--kind KIND` shows only the lines of that kind. `--verbose` lists crossing imports. |
| `systemap audit` | Ask Jev about source meaning. Record its answers under `[judgement]`. |
| `systemap delta --base REF` | Compare source and map claims across revisions. Exit 1 means that you must update the map. With `[delta] page_url`, `--comment FILE --pr N` writes a link comment. `--no-jev` prevents model calls. |
| `systemap triage "<issue>"` | Ask Jev for three components that the issue can affect, with modules and adjacent components. |
| `systemap describe` | Show components per region, bends and length per route, gutter use, and layer contents. |
| `systemap refresh` | Extract facts, do checks, render configured output, and examine the result. |
| `systemap figure --out FILE` | Make one figure. Use `--mode system`, `--layer ID`, `--map ID`, or `--components A,B` as applicable. |
| `systemap journeys` | Ask the configured agent for draft sequences. The command rejects invalid steps. Examine each draft before removal of `drafted=True`. |
| `systemap plan "<task>"` | Ask Jev which components the task can affect. `--check ID --base REF` compares a saved plan with source changes. |
| `systemap history` | Show source changes at older commits, assigned to the current components. |
| `systemap explain KIND` | Show the meaning, reason, and action for a finding kind. `--brief` removes explanations from other command output. |
| `systemap serve` | Serve the output over HTTP and show its URL. |
| `systemap skill` | Install the complete skill again. `--print` writes SKILL.md to stdout. |

## Completion

If you did not act on a judgement or audit line, record it with its reason in `systemap.toml`.
Give the maintainer a completion report with these lines:

```text
Check: <final systemap check result, with its coverage result>
Judgement: <final systemap judgement --strict result>
Audit: <final systemap audit result, or "Jev not available">
Procedure: <Jev or source examination, and each Jev failure>
Examined module assignments: <count>
Open questions: <each assignment that the maintainer must examine>
Recorded answers: <each answer in systemap.toml, with its reason>
Evidence limits: <each recorded extractor, source, or Jev limit>
Uncertainty: <each uncertain component assignment, source claim, or ASD-STE100 word>
Proposed rules: <each proposed invariant outside the invariant list>
```

Commit `map/model.py`, `systemap.toml`, and `docs/map/` with the source changes.
The map must show current source, not proposed components.
Do not put code or test counts on map components. Keep relationships on flows. Do not replace them with prose.

## References

- `references/language.md`: mandatory ASD-STE100 rules, technical glossary, and language acceptance procedure. Read it before every text change.
- `references/schema.md`: dataclasses, fields, and structural checks. Read it before the draft.
- `references/example.md`: a complete small model and configuration. Read it with the schema.
- `references/layout.md`: automatic positions, pinned positions, routes, and descriptions. Read it before placement.
- `references/layers.md`: derived layers, standard kinds, and model-calling systems. Read it before flow assignments.
- `references/journeys-and-invariants.md`: source support for sequences and invariants. Read it before the draft and source review.
- `references/second-pass.md`: full source examination and completion conditions. Read it at step 6.
- `references/pitfalls.md`: known assignment and tool errors. Read it before the draft.
- `references/maintenance.md`: delta actions and the one-third rule. Read it for a map already in use.
