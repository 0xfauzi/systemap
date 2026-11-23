# Work on systemap

systemap makes a map of a software system. The map shows components, flows,
and sequences. A component is a part of the system. A flow carries an artifact
between components. A sequence shows the steps that start at an entry point.

## Language requirement

You must use the ASD-STE100 Issue 9 style for all text that a person reads.
This requirement includes all new names and all map updates.
It includes component names, flow artifacts, layers, sequences, invariants,
explanations, command help, errors, agent answers, and documentation.

Before you write text, read
[the language policy](src/systemap/skill/references/language.md).
Use the ASD-STE100 style rules and the project word list in that policy.
The project does not use the official ASD dictionary.
Use each word with one meaning and one part of speech.
Use technical terms only with the meanings in the project glossary.
Say that the text follows the ASD-STE100 style. Do not say that it obeys the official standard.

Do not change commands, schema keys, source symbols, or quoted evidence.
These technical identities are not permission to write new text in unrestricted English.
Do not change recorded measurements or historical command output.
Do not change the meaning of a claim to make its words shorter.

Before you write or examine documentation, read `~/.claude/WRITING.md` in full.
Use literal words. Do not use emoji or em dashes.

## Findings and explanations

A finding line is also an identifier. The configuration can contain the full line under `[judgement] answered`.
Do not change finding identifiers without an explicit migration.

### The identity of a finding

A recorded answer must stay applicable while its finding stays the same. Thus the finding line contains only the parts that identify the finding:

- the kind and the map prefix,
- the names of the component, the module, the file, the flow, or the entry point,
- the target and the names that the finding is about,
- the text of the finding kind that does not change.

A finding line must not contain a value that changes when the finding stays the same. Examples are a line number, a column, a source excerpt, a parser version, and a time. Put such a value in a row below the line and in a field of `judgement --json`.

The evidence digest finds a change to the cited facts or claims. The finding line does not have to find it.
For a structural finding, the cited facts are the names, the imports, and the entry points, not the full source file.
A comment, a function body, or a test does not change them.

A count is also such a value. Put a count in a row below the line, as the `crossing import` line and the `package_export` line do.

Use one migration path, `answer_migrations.py`, for each changed line form. Give each earlier form one pattern and one test.

For each new finding kind, add three sentences to `explain.py`:

- What the finding tells the reader.
- Why the finding is important to the map.
- What the reader must do.

The `--brief` option removes these explanations.

## Measurements and failures

Use `uv` for all Python commands. Keep dependencies in `pyproject.toml`.

Before an experiment, write its acceptance value in its docstring.
Record all results in `bench/jev/README.md`, including failures.
Do not invent measurements. When a value is unknown, say that a measurement is necessary.

If a command cannot do the specified work, show the failure and stop.
Do not silently substitute a different answer.

## Required checks

Do these checks before a commit:

```sh
uv run pytest
uv run pre-commit run --all-files
uv run mypy src --strict
uv run systemap refresh
uv run systemap check
uv run systemap judgement
```

The pre-commit checks include ruff, complexity, and file length. Pre-commit does not operate mypy. Thus, operate mypy independently, as CI does.
New or increased cognitive complexity must not exceed 15.
Cyclomatic complexity must not increase.
Python files must not exceed 800 lines. `SKILL.md` must not exceed 240 lines.
The three skill directories must have identical contents.

Add each new source module to a component.

Jev is the TypeSafe model for decisions that source facts cannot give.
Tests must use recorded answers and injected agents. Tests must not call Jev or a coding agent.
Before you complete the work, examine the text against the ASD-STE100 style rules, the project word list, and the project glossary.
Automated tests do not show correct word meanings or language compliance.
