# Work on systemap

systemap makes a map of a software system. The map shows components, flows,
and sequences. A component is a part of the system. A flow carries an artifact
between components. A sequence shows the steps that start at an entry point.

## Language requirement

You must use ASD-STE100 Issue 9 for all text that a person reads.
This requirement includes all new names and all map updates.
It includes component names, flow artifacts, layers, sequences, invariants,
explanations, command help, errors, agent answers, and documentation.

Before you write text, read
[the language policy](src/systemap/skill/references/language.md).
Use the official ASD-STE100 rules and dictionary.
Use each approved word only with its approved meaning and part of speech.
Use technical terms only with the meanings in the project glossary.
If the reference is not available, tell the maintainer. Do not give an ASD-STE100 acceptance result.

Do not change commands, schema keys, source symbols, or quoted evidence.
These technical identities are not permission to write new text in unrestricted English.
Do not change recorded measurements or historical command output.
Do not change the meaning of a claim to make its words shorter.

Before you write or examine documentation, read `~/.claude/WRITING.md` in full.
Use literal words. Do not use emoji or em dashes.

## Findings and explanations

A finding line is also an identifier. The configuration can contain the full line under `[judgement] answered`.
Do not change finding identifiers without an explicit migration.
For each new finding kind, add three sentences to `explain.py`:

- What the finding tells the reader.
- Why the finding matters to the map.
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
uv run systemap refresh
uv run systemap check
uv run systemap judgement
```

The checks include ruff, mypy, complexity, file length, and skill copy consistency.
New or increased cognitive complexity must not exceed 15.
Cyclomatic complexity must not increase.
Python files must not exceed 800 lines. `SKILL.md` must not exceed 240 lines.
The three skill directories must have identical contents.
Add each new source module to a component.

Jev is the TypeSafe model for decisions that source facts cannot give.
Tests must use recorded answers and injected agents. Tests must not call Jev or a coding agent.
Before you complete the work, examine the text against ASD-STE100 and the project glossary.
Automated tests do not show correct word meanings or language compliance.
