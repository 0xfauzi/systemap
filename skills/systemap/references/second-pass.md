# Examine source claims after the draft

## Contents

- Source examination procedure
- Answer records
- Every nested map
- Completion conditions
- Decision provider source questions

The structural check finds contradictions, not every omission or incorrect meaning.
Examine each component assignment and flow claim against source.
Include modules that have no judgement finding.
A shared package, word, or import does not show a common component function.

Use the language policy in `references/language.md` for all steps of this procedure.
Keep exact finding identifiers when you record answers.

## Source examination procedure

1. Run `systemap judgement`. Read each line.
   Correct the model or record a source-supported reason under `[judgement] answered`.
   Remove stale answers after a new examination of their evidence.
   Do not leave unanswered lines.
2. Examine every assigned module from `systemap facts --modules`.
   Compare its source description and public symbols with the component's `does`, `plain`, and `interface`.
   If the facts do not show its function, read the module source.
   If another component has the correct function, change the assignment.
   If both assignments are incorrect, correct the component definitions first.
   Record uncertain assignments and their source evidence for the maintainer.
3. Examine every crossing import with `systemap judgement --verbose`.
   Find the source import. Identify the data transfer or call direction.
   Add a supported flow, record why no flow is necessary, or correct the component assignments.
   Type annotations and shared constants can be imports without a useful map flow.
4. Examine every declared or structural flow.
   Find the source that gives its direction and artifact.
   If the import belongs to a different component, correct the module assignments.
   For a subprocess, queue, file, or HTTP operation, identify the mechanism in the relation sentence.

   A configured word in `[flows] observed_by` gives structural evidence only.
   Record current source references and a claim digest only after source examination.
   Remove unsupported flows and their relation sentences.
   If the extractor cannot see a real connection, record that specific limit.
   A judgement answer must not change the flow's evidence state.
5. Examine each entry point without sequence coverage.
   Write a source-supported sequence or record why the sequence is not necessary.
   Use `references/journeys-and-invariants.md` for exact entry identities and step coverage.
6. Examine each `model sdk` finding.
   When it exists, use the repository's own agent definition.
   Set `kind="agent"` for an agent or `calls_model=True` for another model-calling component.
   Add the applicable context and tool flows.
   If the import is a client capability, unused code, or a non-model framework module, record that evidence.

   Import prefixes also match framework tool and session modules.
   `[facts] model_sdks = ["-google.adk"]` removes that built-in prefix.
   A `module_sdk = "google.adk"` policy answers the findings for that import and keeps the prefix.
7. Read the repository's rules beside the invariant list.
   Read README, AGENTS.md, CLAUDE.md, the documentation index, and the first level of docs/.
   If new rules apply only to source outside the repository, do not read more documents.
   Add each applicable rule with a source citation or record why it is not an invariant.
8. Examine `docs/map/figures/structure.svg`. Then examine `docs/map/figures/system.svg`.
   If a browser is available, use `systemap serve` to open the page.
   Examine near-crossing routes, labels in incorrect positions, isolated regions, empty layers, and sequence gaps.
   Read each relation sentence from the source component.
   Correct generic sentences that do not give the actual action and result.
9. Run `systemap check && systemap judgement --strict`. Then run `systemap refresh`.
   A removed flow can open a crossing-import finding again. Do the judgement check after every layout change.
10. If the model changed, do this procedure again. Before completion, do the language acceptance procedure.

## Answer records

Seven forms are available. Each table has one reason.
These values are examples. Replace each quoted line and digest with actual output after source examination.

```toml
[judgement]
answered = [
    { item = "<exact printed line>", reason = "The source operation uses an HTTP client outside the extracted package.", evidence = "<current evidence digest>" },
    { items = ["<first exact line>", "<second exact line>"], reason = "Each component has a different function in this small package.", evidence = "<current evidence digest>" },
    { crossing = ["Page", "Figures", "Describe"], policy = true, reason = "These components use shared diagram tables without another artifact transfer." },
    { crossing_into = "Model", policy = true, reason = "Components import the schema for type annotations." },
    { crossing_from = "CLI", policy = true, reason = "Commands import the components that their control flows call." },
    { kind = "single module", policy = true, reason = "Each component has a different function in this small package." },
    { module_sdk = "google.adk", policy = true, reason = "The framework also has tool and session modules without model calls." },
]
```

An exact answer must have the SHA-256 evidence digest for the current finding.
A placeholder or old digest is not sufficient.
The digest contains the facts that the finding cites: the names, the imports, and the entry points.
A comment, a function body, or a test does not open the answer again.
A line about a flow or a source review also contains the source files.
`judgement` gives no line about a test file.
A broad answer is a permanent policy only with `policy = true`.
Use `reviewed = ["<printed line>", ...]` to record its examined baseline.
The report counts current matches outside that baseline.
Do not use a broad policy to avoid source examination.

For long lists, use `systemap judgement --kind "crossing import"`.
The header still counts all unanswered lines. `--strict` also reads all lines.

## Every nested map

Do this procedure for every map in the tree.
Nested finding lines include the map identifier, for example `Gateway: single module: ...`.
An exact `item` answer includes that prefix.
Broad forms such as `kind`, `crossing`, and `module_sdk` apply across maps.

An import between two internal components belongs to their nested map.
An import across its boundary belongs to the applicable components on the parent map.
Entry points and SDK imports use the deepest map with the applicable source assignment.
A sequence on any map can cover an exact entry identity.

## Completion conditions

The work must agree with all of these conditions:

- `systemap check` has complete coverage and no layout failures.
- After `refresh`, there must be no `stale` finding.
- `systemap judgement --strict` exits 0, with no unanswered findings or stale answers.
- A complete source examination causes no more model changes.
- Documentation that you did not read has no rules for source in the repository.
- The language acceptance procedure is complete for all changed names and sentences.

Give the maintainer the completion report from SKILL.md, with the recorded answers and evidence limits.

## Decision provider source questions

With `TYPESAFE_API_KEY`, run `systemap audit` after check and judgement pass.
The decision provider (Jev or OpenAI) can find differences between the source and authored claims.
Each answer is a question for source examination, not source evidence.

| line | action |
|---|---|
| `decision mis-fold` | Read the module. Correct its assignment or record the source reason. |
| `decision owner` | Give the module a component assignment with source evidence or record a coverage exclusion. |
| `decision sentence` | Compare the description with source. Correct it or record why it is correct. |
| `decision flow` | Find the source call and artifact. Instance calls can be missing from the provider input. |
| `decision governs` | Examine if a component change can make the invariant incorrect. Change `governs` only with source support. |

The audit asks the `decision flow` question only with `--kind "decision flow"`.
Its recorded experiment found fewer incorrect flows on maps not used for threshold selection.
Use that limit when you examine its answers.
Record audit answers under `[judgement] answered` with a reason.
`audit --dry-run` shows inputs without a model call.
Repeated identical requests can use the cache.
