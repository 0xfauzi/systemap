# Get started

This page tells you how to install systemap and make the first map of a small Python project with a coding agent.

All command output on this page comes from that example project.

## What you need

- Python 3.11 or later, and `uv`.
- A Git repository with Python or TypeScript source code.
- A coding agent that can read files and run commands, for example Claude Code.

## Install systemap

```sh
uv tool install systemap
```

For a TypeScript repository, install the `typescript` extra. It adds the tree-sitter parser.

```sh
uv tool install 'systemap[typescript]'
```

To add systemap to the development dependencies of your project, use `uv add --dev systemap`.
Then run each command with `uv run systemap`.

## Write the initial files

At the root of your repository, run `systemap init`. These are the first lines of the output:

```text
$ systemap init
wrote systemap.toml
wrote map/model.py
wrote docs/map/.gitkeep
wrote .github/workflows/systemap.yml
The command wrote .claude/skills/systemap/ (SKILL.md and 9 references)
```

- `docs/map/` is the output directory for the facts, the page, and the figures.
- The [CI workflow](pull-requests-and-ci.html) is advisory: a map finding gives a warning, and the job passes. `--strict-ci` writes a workflow that fails on a map finding. `--no-ci` writes no workflow.
- If a configuration, model, or workflow file exists, `init` keeps it. `init` writes the skill directory again each time.
- The output also gives a note for a repository that uses mypy or deptry. Your project does not need systemap as a dependency.

## Give the instruction to your agent

The output ends with the instruction for your coding agent. Give it to the agent:

> Make a map of this repository with systemap. Obey the systemap skill and its writing rules.

The agent extracts the facts, gives each module a component, and writes the flows and the sequences.
It does the checks until they pass. Then it gives a completion report.
Read the report. Correct each claim that you do not agree with.
[Coding agents](coding-agents.html) gives the full procedure.

The example project has three modules, an empty package marker, and one test file.
Its `pyproject.toml` file declares the console script `shop = "shop.cli:main"`.
In this project, the agent wrote three components, one actor, three flows, and one sequence in `map/model.py`.
`systemap place` calculates the positions of the components.
[Concepts](concepts.html) gives the terms, and the [reference](reference.html#what-does-a-model-contain) gives a complete small model.

## Run the first refresh

`systemap refresh` extracts the facts, does the checks, and renders the page and the configured figures:

```text
$ systemap refresh
map: The refresh uses the working tree.
map: The command updated docs/map/map.json, docs/map/index.html, docs/map/figures/structure.svg, docs/map/figures/system.svg
map: Commit docs/map/ to record this system state.
```

If the model has no components, the refresh stops with exit code 1:

```text
$ systemap refresh
The model has no components. Read the skill instructions.
```

## Run the checks

`systemap check` compares the map with the code:

```text
$ systemap check
map routes: 0 flow paths across components other than their endpoints, 0 across regions other than their endpoint regions.
coverage: 4 of 4 modules mapped, 1 an empty package marker
map layout: has no errors (4 components, 3 orthogonal flow paths with labels, no text size less than 11px)
```

If a rule rejects the map, or an output is stale, the command exits 1. Each finding gives a correction.

`systemap judgement` prints possible map errors for a person or an agent to examine.
These are the first lines of the output:

```text
$ systemap judgement
judgement: 8 possible map errors to examine
  single module: CommandLine contains only shop.cli
```

For each line, change the map, or record an answer under `[judgement] answered` in `systemap.toml`.
[Concepts](concepts.html#findings-and-answers) tells how to record an answer.
With `--strict`, the command exits 1 while a line stays open.

In the example, the agent changed the map for some lines and recorded answers for the other lines.
Then the strict command passed. This is the first line of the output:

```text
$ systemap judgement --strict
judgement: No possible map error to examine, 4 answered
```

A result without open findings does not show that each claim is correct. See [Limits](limits.html).

## Open the page

```text
$ systemap serve
The server serves docs/map at http://127.0.0.1:8765/. Use Ctrl-C to stop the server.
```

Open the URL in a browser. [Read the map](reading-the-map.html) tells how to use the page.
The [live example](../map/) is the map of systemap itself.
For a different port, see the [reference](reference.html#systemap-serve-port-8765).

## Commit the map

Commit `map/model.py`, `systemap.toml`, and `docs/map/` with the source code.
Then the workflow from `init` compares the map with the source on each push to `main` and on each pull request.

## Next steps

- [Concepts](concepts.html): the terms of the map.
- [Coding agents](coding-agents.html): the skill and the Claude Code plugin.
- [Pull requests and CI](pull-requests-and-ci.html): `systemap delta` and the workflow.
- [The live map](live-map.html): the map of the working tree.
