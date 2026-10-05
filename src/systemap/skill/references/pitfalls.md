# Known map and tooling errors

Read these cases before the draft and when many judgement lines stay open.
Apply `language.md` to all new names and sentences.

## Module assignments

One component per module can give a dependency graph without useful system functions.
A component must have a function that a reader can identify.
Some single-module components are correct. Examine each `single module` finding.
Assign a module by its function, not only its directory.
A directory such as `pkg/util/` can contain modules for different components.

## Facts and quantities

Use `systemap facts` instead of the complete facts JSON.
Select `--modules`, `--docstrings`, `--module NAME`, `--names NAME`, `--entry-points`, `--external`, or `--imports NAME`.
Keep code and test counts out of component descriptions and sequence sentences.
These counts do not tell the reader what the system does.

## Flow claims

An artifact must identify the item that moves or the operation that starts.
`Flow("A", "B", "uses", "data")` does not identify an artifact.
Write a relation sentence about the actual action from the source component.
A generic sentence such as "A sends data to B" can omit the important behavior.

An import, common module, or configured mechanism does not show a flow's direction or artifact.
Read the relevant source before you record an observed flow.
Keep declared and structural evidence explicit.
Remove claims that the source does not support.
A judgement answer does not convert a declared flow into observed evidence.

## Entry points and sequences

Copy public source symbols from the facts for `entry`.
A helper function can pass a structural check without being the correct public entry point.
Select the symbol that callers use.
Every sequence step must refer to an existing flow.
If a necessary flow is missing, examine the source and correct the model.
Do not skip a step to avoid a missing-flow finding.

## Layers and invariants

A custom layer must answer a different question with source evidence.
Do not add a layer only to show a directory name again.
An invariant must have a source citation.
A proposed rule belongs in the maintainer note, not the current invariant list.

## Positions and nested maps

Leave new `x` and `y` values unset. Run `systemap place`.
After component additions or removals, run `systemap place --all`.
Use `pinned=True` only for a position that must stay fixed.
Read `layout.md` for region, route, and label decisions.
Use the measured layout report from `systemap describe`.
For maps above forty components or components above ten modules, examine the nested-map suggestion.
A nested map must cover exactly the parent's modules.

## Recorded answers

Put reasons in `[judgement] answered` in `systemap.toml`, not only in a chat message.
Use `items` for exact lines with one shared reason.
Use separate records when the reasons differ.
Exact answers must have current evidence digests.
Broad policies must have `policy = true` and a clear explanation.
Do not use a broad policy to hide an unexamined claim.

## Temporary scripts and repository checks

If a temporary script is necessary, put it outside the repository (for example /tmp).
Do not commit temporary measurements beside the model.
Use the commands that already supply layout measurements and bulk answer records.

Run the repository formatter on `map/model.py`.
Then run every CI command that applies to the map files, not only pre-commit.
The generated model imports systemap as a tool without a required project dependency.
Its type-ignore comment handles `mypy --strict` when that tool package is unavailable to the checker.
For deptry, use the DEP001 and DEP003 exclusions printed by `systemap init`.
A successful pre-commit run does not establish that all CI checks pass.
