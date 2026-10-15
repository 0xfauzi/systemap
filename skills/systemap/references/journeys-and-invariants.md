# Source support for sequences and invariants

Sequences and invariants are optional schema contents.
A model without sequences has no sequence selector.
A model without invariants has no invariant list.
Each sequence and invariant must have source support.
Use the mandatory language policy in `references/language.md` for every name and sentence.

## Entry points and sequences

`systemap extract` records entry points under `entry_points` in the facts file.
An entry point is a place where a program operation can start.
The extractor reads these source forms:

- Console scripts from `[project.scripts]` and `[tool.poetry.scripts]`.
- Plugin hooks from `[project.entry-points]`.
- `__main__` modules and `main` functions.
- Argparse subcommands with a literal `add_parser("name", ...)` value.
- Public functions exported by the package root.
- Framework routes, for example `@app.get`, Flask `@app.route`, and Django `urlpatterns`.
- Click and Typer commands, Cleo command classes, and Django `management/commands/*`.
- Background tasks with `@shared_task` or `@app.task`.

Write one sequence for each entry point that is important to a reader.
Start with the actor and the component that receives the input.
Then show the flows and the destination of the result.
Each `Step` contains `acts`, `measures`, `edge`, and `say`.
If no component records or monitors the step, use an empty tuple for `measures`.

Use `starts` as the display label of the entry point.
After source examination, add the exact entry identities to `covers`.
`systemap facts --entry-points` shows the available identities.
A label, sentence, or old `starts` value does not give coverage.

A console script and its imported `main` or `__main__` can have the same entry identity.
For many entry points of one kind in one component, use one sequence for the common operation.
Set `starts` to the component identifier, for example `starts="HttpApi"`.
List each examined entry identity in `covers`.
New entry points do not automatically receive coverage from that sequence.

With `[agent] command`, `systemap journeys` asks the agent for a draft sequence.
The agent reads one entry point or two or three entries from a group.
The prompt makes the writing profile mandatory for the identifier, label, and step sentences.
The command rejects steps with unknown components or missing flows.
Accepted drafts have `drafted=True` and a `drafted journey` finding.

Examine each step against the source. Correct errors before removal of the draft flag.

A sequence is not necessary for some entry points.
Examples include a debug hook, a test-only function, or a version command.
Record the reason under `[judgement] answered`.
If you cannot explain an entry point from source, tell the maintainer.
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

Write the rule under the writing profile without a change to its meaning.
If the identity of an external quotation is necessary, keep the exact quotation.
Put the citation in the invariant text.
Write the invariant in the contract file, `map/contract.py`, with a `reason`.
The reason gives the cause of the rule from the code, the documentation, or the commit history.
A rule without a reason gives a `contract reason` line. Do not record an answer for it.
List directly affected component identifiers in `governs`.
A proposed rule is not an existing invariant. Put proposals in the completion report.

## Structural checks and their limits

The check rejects sequence steps with missing flows or unknown component identifiers.
It also rejects invariants that refer to unknown components.
It cannot show that a sequence is useful or that an invariant is true.
The source examination procedure compares these claims with code and documentation.
Complete language acceptance only after that examination.
