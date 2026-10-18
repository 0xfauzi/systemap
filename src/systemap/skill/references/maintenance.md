# Update a map after source changes

## Contents

- Update procedure
- Delta findings
- Optional plan before code changes
- Pull request workflow
- Completion

For an existing map, use delta to identify the necessary changes.
A full first-draft procedure is not necessary for a small change.
The language policy in `references/language.md` applies to every changed name and sentence.

## Update procedure

1. Run `systemap delta --base REF`.
   For a pull request, use the base branch or base commit.
   Otherwise, use `built_at_commit` from the last facts snapshot.
   Delta reads committed source at both revisions, not the working tree.
   It compares the changes with the map claims.

   Exit 0 means that the map is current. Exit 1 means that you must update the map.
   With `--decide` and the key of the provider, the decision provider can identify rewritten moves and suggest owners for unclaimed modules.
   A key alone sends no question. `[jev] enabled = true` in `systemap.toml` selects the provider without `--decide`. `--jev` is the previous name of `--decide`.
   Before you accept a suggested move, read both source files.
2. Act on the lines under `The map needs an update` in `map/model.py` and `systemap.toml`.
   Keep unaffected component assignments and positions.
   For a new component, use `systemap place`.
   If its region has no free position, use `systemap place --all`.
   This command keeps positions with `pinned=True`.
3. For each `source review` line, examine the changed modules against all component claims.
   Include its description, interface, flows, sequences, and invariants.
   Correct claims that no longer agree with source.
   Only then run `systemap review ID` to record the current `source_review` digest.
4. Run `systemap refresh`. Then run `systemap check && systemap judgement --strict`.
   Act on newly open lines or record supported reasons under `[judgement] answered`.
   After more model changes, do these commands again.
5. If delta identifies more than one-third of the components, do the full loop in SKILL.md.
6. Do the language acceptance procedure in `references/language.md`.

An added or removed module assignment also opens source review again.
This includes modules matched by an `implemented_by` wildcard.

Each component has one review state:

- `missing`: the component has no `source_review` value.
- `stale`: the `source_review` value is not the current digest.
- `current`: the `source_review` value is the current digest.

Delta and judgement use the same state.
Delta gives a `source review` line for a changed component that is not `current`.
Judgement gives a `stale source review` finding for each `stale` component, so `judgement --strict` fails.
Judgement counts `missing` components on its `source reviews:` line. A missing review is not a finding, unless `[judgement] require_reviews = true`.

`systemap review ID` writes the current digest into `source_review` of the component ID.
It does not examine the claims for you. Examine all the claims before you use it.
One command writes one component. The command has no option for all components.
`systemap review --dry-run ID` prints the digest and the file, and it writes nothing.
A flow digest is one of the claims of its two endpoint components.
Record flow digests with `systemap review --flow 'SRC->DST'` before component digests.

If a claimed module is missing or the parser cannot read it, the component has no digest.
Then the command stops with exit 1 and writes nothing.
Correct extraction before you record the digest.
If the source or the claims change after that, the finding opens again.

## Delta findings

| line | meaning | action |
|---|---|---|
| `moved` | A module has a new path. | Change `implemented_by` after you examine module identity. |
| `added`, already claimed | An existing pattern includes the new module. | Examine its assignment and any separate source-review finding. |
| `added`, unclaimed | A new module has no component assignment. | Assign it or record a coverage exclusion with a reason. |
| `removed`, explicitly claimed | A component still refers to a removed module. | Remove that claim. Remove empty components and their flows as applicable. |
| `removed`, excluded | A coverage exclusion refers to a removed module. | Remove the stale exclusion. |
| `entry vanished` | The public entry symbol is missing. | Select a public symbol from the claimed modules. |
| `interface vanished` | The interface refers to a missing symbol. | Use an existing symbol or an empty interface value. |
| `new crossing import` | An import crosses components without a flow. | Add a supported flow, change assignments, or record why no flow is necessary. |
| `evidence lost` | The flow no longer has its recorded support. | Examine current source. Then correct or renew the claim. |
| `source evidence lost` | Source records no longer support a claim that had a current source review. | Examine references, direction, and artifact before renewal. |
| `structural evidence lost` | An import or configured mechanism is missing. | Examine the flow against current source. |
| `source review` | Component source or claims changed. | Examine all claims before renewal of `source_review`. |
| `move candidate` | Removed and added modules have the same public names without sufficient identity evidence. | Compare source. If the module task stayed the same, change the claim to the added module. If not, remove the claim. Then assign the added module. After that, no action is necessary for the line. |
| `decision move`, `decision owner` | The decision provider suggests a move or an owner that delta did not find. | Read the source before you use the suggestion. These lines do not change the delta lines or the exit code. |

Lines under `No action is necessary for these changes` record changes for which no map action is necessary.
A pattern-matched addition or removal can still have a separate source-review finding.

## Optional plan before code changes

With `TYPESAFE_API_KEY`, use `systemap plan "<task>"` before a change.
Jev compares the task with component functions and selects likely affected components.
Read their flows, sequences, and invariants before you change the source.
The plan is stored under `.systemap/plans/`.

After the change, use `systemap plan --check ID --base REF`.
This comparison identifies affected components that the plan did not select.
Record unexpected effects in the pull request.

The experiment covered 86% of affected components over 80 bug reports, with 2.1 selected components per report.
On a repository not used for threshold selection, coverage was 71%.
These are recorded experiment results. A new repository can have different results.
See `bench/jev/README.md` in the systemap source repository for methods and limits.

## Pull request workflow

The generated workflow runs `delta --base <base commit> --head <head commit>` for each pull request.
The job log gives each line and its action.
If the map is not current, the job gives a warning and passes.
With `systemap init --strict-ci`, the job fails.

The workflow writes the architecture summary as one pull request comment, and changes it after each push.
The summary gives the contract changes, the map changes, the rule results, and the assurance level of each row.
For a pull request from a fork, the workflow writes the summary only to the job summary.
With `[delta] page_url` in `systemap.toml`, the comment also has a link to the Changes view of the page.
The page shows the map changes. Make that page with `systemap render --base REF`.

## Completion

Give the maintainer a completion report with these lines:

```text
Delta: <delta header>
Actions: <the action for each finding>
Coverage: <coverage result from systemap check>
Judgement: <final systemap judgement --strict result>
Uncertainty: <each unresolved source or language uncertainty>
```
