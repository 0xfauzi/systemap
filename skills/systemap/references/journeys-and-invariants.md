# Source support for sequences and invariants

Sequences and invariants are optional schema contents.
A model without sequences has no sequence selector.
A model without invariants has no invariant list.
Each sequence and invariant must have source support.
Use the mandatory language policy in `language.md` for every name and sentence.

## Entry points and sequences

`systemap extract` records entry points under `entry_points` in the facts file.
An entry point is a place where a program operation can start.
The extractor reads these source forms:

- Console scripts from `[project.scripts]` and `[tool.poetry.scripts]`.
- Plugin hooks from `[project.entry-points]`.
- `__main__` modules and `main` functions.
- Argparse subcommands with a literal `add_parser("name", ...)` value.
- Public functions exported by the package root.
- Framework routes, including `@app.get`, Flask `@app.route`, and Django `urlpatterns`.
- Click and Typer commands, Cleo command classes, and Django `management/commands/*`.
- Background tasks with `@shared_task` or `@app.task`.

Write one sequence for each entry point that matters to a reader.
Start with the actor and the component that receives the input.
Then show the flows and the destination of the result.
Each `Step` contains `acts`, `measures`, `edge`, and `say`.
Use an empty tuple for `measures` when no component records or monitors the step.
Use `starts` as the entry point display label.
After source examination, add the exact entry identities to `covers`.
`systemap facts --entry-points` shows the available identities.
A label, sentence, or old `starts` value does not establish coverage.

A console script and its imported `main` or `__main__` can have the same entry identity.
For many entry points of one kind in one component, use one sequence for the common operation.
Set `starts` to the component identifier, for example `starts="HttpApi"`.
List each examined entry identity in `covers`.
New entry points do not automatically receive coverage from that sequence.

With `[agent] command`, `systemap journeys` asks the agent for a draft sequence.
The agent reads one entry point or two or three entries from a group.
The prompt makes ASD-STE100 mandatory for the identifier, label, and step sentences.
The command rejects steps with unknown components or missing flows.
Accepted drafts have `drafted=True` and a `drafted journey` finding.
Examine each step against the source. Correct errors before removal of the draft flag.

A sequence is not necessary for some entry points.
Examples include a debug hook, a test-only function, or a version command.
Record the reason under `[judgement] answered`.
If an entry point cannot be explained from source, tell the maintainer.
Do not invent a sequence.

For a model-calling system, write one sequence per agent turn when applicable.
Show the context input, model output, tool calls, and stored result.

## Invariants and source rules

An invariant is a repository rule that applies to specified components.
Use these sources in this order:

1. Repository documentation: README, AGENTS.md, CLAUDE.md, and docs/.
   Cite the file and heading, for example `(README, Principles)`.
2. Source clauses that reject an input and give a reason.
   Cite the file and line, for example `(pkg/ledger.py:42)`.
3. Assertions in source code. Cite the file and line.
4. Tests that state a rule, for example `test_every_record_is_written_once`.
   Cite the test file.

Write the rule in ASD-STE100 without a change to its meaning.
Keep an exact external quotation when its identity is necessary.
Put the citation in the invariant text.
List directly affected component identifiers in `governs`.
A proposed rule is not an existing invariant. Put proposals in the completion note.

## Structural checks and their limits

The check rejects sequence steps with missing flows or unknown component identifiers.
It also rejects invariants that refer to unknown components.
It cannot establish that a sequence is useful or that an invariant is true.
The source examination procedure compares these claims with code and documentation.
Complete language acceptance only after that examination.
