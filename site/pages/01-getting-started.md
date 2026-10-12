# Get started

This page tells you how to install systemap and make the first map of a small Python project with a coding agent.

The agent writes the map. Then the commands compare the map with the source code.
All command output on this page comes from that example project.

## What you need

- Python 3.11 or later, and `uv`.
- A Git repository with Python or TypeScript source code.
- A coding agent that can read files and run commands, for example Claude Code.

## Install systemap

Install the command as a uv tool:

```sh
uv tool install systemap
```

You can also add systemap to the development dependencies of your project with `uv add --dev systemap`.
Then run each command with `uv run systemap`.

For a TypeScript repository, install the parser extra:

```sh
uv tool install 'systemap[typescript]'
```

The systemap package has no required dependencies. The `typescript` extra adds the tree-sitter parser.

## Write the initial files

Go to the root of your repository. Then run `systemap init`:

```text
$ systemap init
wrote systemap.toml
wrote map/model.py
wrote docs/map/.gitkeep
wrote .github/workflows/systemap.yml
The command wrote .claude/skills/systemap/ (SKILL.md and 9 references)
note: map/model.py imports the systemap tool package:
  mypy --strict: the import has # type: ignore[import-not-found, unused-ignore]
  deptry: add these lines to pyproject.toml
    [tool.deptry.per_rule_ignores]
    DEP001 = ["systemap"]
    DEP003 = ["systemap"]
  run all repository CI commands on the map files
Next, give this instruction to your coding agent:
  Make a map of this repository with systemap. Obey the systemap skill and its writing rules.
```

| File | Contents |
|---|---|
| `systemap.toml` | The configuration. In the example, `init` found the package root `"src/shop" = "shop"`. |
| `map/model.py` | The model. It has one container, four regions, and no components. |
| `docs/map/.gitkeep` | The output directory for the facts, the page, and the figures. |
| `.github/workflows/systemap.yml` | The CI workflow. [Pull requests and CI](pull-requests-and-ci.html) gives its jobs. |
| `.claude/skills/systemap/` | The skill for the coding agent: `SKILL.md` and its reference files. |

The workflow is advisory by default: a map finding gives a warning, and the job passes.
Use `--strict-ci` to write a workflow that fails on a map finding.
Use `--no-ci` to write no workflow.

If a configuration, model, or workflow file exists, `init` keeps it.
`init` writes the skill directory again each time.
Your project does not need systemap as a dependency. The note in the output is for a repository that uses mypy or deptry.

The [reference](reference.html#systemap-init-no-ci-strict-ci) gives the options of `init`.

## Give the instruction to your agent

The last line of the output is the instruction for your coding agent:

> Make a map of this repository with systemap. Obey the systemap skill and its writing rules.

Give this instruction to the agent.
The skill tells the agent to extract the source facts and give each module a component.
Then the agent writes the flows and the sequences, and does the checks until they pass.
After a second examination of the source, the agent gives a completion report.
[Coding agents](coding-agents.html) gives the full procedure.

When the agent stops, read its completion report.
The report gives the recorded answers and the uncertain claims.
Correct each claim that you do not agree with.

## What the agent writes

The example project has three modules, an empty package marker, and one test file.
Its `pyproject.toml` file declares the console script `shop = "shop.cli:main"`.

```text
src/shop/__init__.py
src/shop/cli.py
src/shop/orders.py
src/shop/store.py
tests/test_orders.py
```

`systemap extract` reads the source files and writes the facts to `docs/map/map.json`.
`systemap facts` prints the facts one view at a time:

```text
$ systemap facts --modules
modules: 4. Each line gives the first docstring sentence and the public name, import, and test counts.
  shop: empty package marker
  shop.cli: The command line reads an order and prints the total. (1 name, 2 imports, 0 tests)
  shop.orders: Order arithmetic. (1 name, 0 imports, 1 test)
  shop.store: The order store reads order files. (1 name, 0 imports, 0 tests)
```

The agent gives each module a component in `map/model.py`.
The example model has three components, one actor, three flows, and one sequence. This is one of the components:

```python
Component(
    id="Orders",
    does="Calculates the total of the order lines.",
    interface="total(order) -> float",
    implemented_by=("shop.orders",),
    entry="total",
    region="run",
),
```

The agent does not write `x` and `y` values. `systemap place` calculates the positions:

```text
$ systemap place
place: The command wrote map/model.py: 4 components placed, 0 kept. The command set all boxes and the canvas
  region order: run, keep. 2 bends, 210 units. 2 orders examined, 2 routed
run: systemap check
```

[Concepts](concepts.html) gives the meaning of each model term.
The [reference](reference.html#what-does-a-model-contain) gives a complete small model.

## Run the first refresh

`systemap refresh` extracts the facts and does the checks.
Then it renders the page and the configured figures:

```text
$ systemap refresh
map: The refresh uses the working tree.
map: The command updated docs/map/map.json, docs/map/index.html, docs/map/figures/structure.svg, docs/map/figures/system.svg
map: Commit docs/map/ to record this system state.
```

Before the agent writes components, the refresh stops with exit code 1:

```text
$ systemap refresh
The model has no components. Read the skill instructions.
```

## Run the checks

`systemap check` compares the map with the code.
It rejects contradictions, such as a module without a component or a route across an unrelated component:

```text
$ systemap check
map routes: 0 flow paths across components other than their endpoints, 0 across regions other than their endpoint regions.
coverage: 4 of 4 modules mapped, 1 an empty package marker
map layout: has no errors (4 components, 3 orthogonal flow paths with labels, no text size less than 11px)
```

| Exit code | Result |
|---|---|
| `0` | No rule rejects the map, and the outputs are current. |
| `1` | A rule rejects the map, or an output is stale. Each finding gives a correction. |
| `2` | systemap cannot use the configuration, the model, or a command option. |

`systemap judgement` prints possible map errors. A person or an agent must examine each one:

```text
$ systemap judgement
judgement: 8 possible map errors to examine
  single module: CommandLine contains only shop.cli
      why: A component for each file gives no information that the file tree does not give.
      do:  Keep the component if it has a different task. Otherwise, put the module in the component for its task.
  single module: Orders contains only shop.orders
  single module: OrderFiles contains only shop.store
  thin layer: control shows 0 components
      why: A layer with one component gives little information about the connections in the system.
      do:  Add the flows for this layer, or give the reason that this layer is not necessary.
  entry point shop (console script) has no sequence (component CommandLine)
      why: An entry point starts a system operation. Without a sequence, the map does not give the steps of this operation.
      do:  Write the sequence from the entry point to the result. Or give the reason that no sequence is necessary.
  journey start: print-total uses a legacy start. Examine the source. Then set covers=('["console_script","shop.cli","main","shop"]',)
      why: If an entry point name is incorrect, the map cannot show which entry points have sequences.
      do:  Use the entry point name from `systemap facts --entry-points`, or leave `starts` empty.
  flow review: OrderFiles -> CommandLine (order) has structural evidence but no source review. Give source references for direction and artifact, or change the flow.
      why: This structure does not give evidence of the direction, data, or runtime behavior. Source references must agree with the source and claim.
      do:  Read the source. Record the source references with correct digests. If the claim is incorrect, change the flow.
  flow review: CommandLine -> Orders (order) has structural evidence but no source review. Give source references for direction and artifact, or change the flow.
source reviews: 0 current, 0 stale, 3 missing
hint: Set TYPESAFE_API_KEY to use systemap audit. Then Jev reads each module and its component. It gives a list of the modules that are probably in an incorrect component. Set [jev] enabled = false in systemap.toml to stop this hint.
```

For each line, change the map, or record an answer under `[judgement] answered` in `systemap.toml`.
[Concepts](concepts.html#findings-and-answers) tells how to record an answer.
Without `--strict`, the command exits 0. With `--strict`, it exits 1 while a line stays open.

In the example, the agent recorded source records for the two internal flows and set `covers` on the sequence.
It recorded answers for the other lines. Then the strict command passed:

```text
$ systemap judgement --strict
judgement: No possible map error to examine, 4 answered
  policy answer: kind = "thin layer" covers 1 lines at this snapshot. 1 lines are outside the source-review baseline.
source reviews: 0 current, 0 stale, 3 missing
hint: Set TYPESAFE_API_KEY to use systemap audit. Then Jev reads each module and its component. It gives a list of the modules that are probably in an incorrect component. Set [jev] enabled = false in systemap.toml to stop this hint.
```

A result without open findings does not show that each claim is correct.
[Limits](limits.html) tells what the checks do not show.

## Open the page

`systemap serve` supplies the output directory on the loopback address:

```text
$ systemap serve
The server serves docs/map at http://127.0.0.1:8765/. Use Ctrl-C to stop the server.
```

Open the URL in a browser. [Read the map](reading-the-map.html) tells how to use the page.
The [live example](../map/) is the map of systemap itself.

If port 8765 is not available, the command exits 2. Then use `--port 0` to select an available port.

## Commit the map

Commit `map/model.py`, `systemap.toml`, and `docs/map/` with the source code.
Then the workflow from `init` compares the map with the source on each push to `main` and on each pull request.

## Next steps

- [Concepts](concepts.html): the terms of the map.
- [Coding agents](coding-agents.html): the skill, the Claude Code plugin, and the writing profile.
- [Pull requests and CI](pull-requests-and-ci.html): `systemap delta` and the workflow.
- [The live map](live-map.html): the map of the working tree while you change the code.
