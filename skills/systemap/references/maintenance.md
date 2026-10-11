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
   Exit 0 means no decision is necessary. Exit 1 means action is necessary.
   With `TYPESAFE_API_KEY`, Jev can identify rewritten moves and suggest owners for unclaimed modules.
   Before you accept a suggested move, read both source files.
2. Act on the lines under `A decision is necessary` in `map/model.py` and `systemap.toml`.
   Keep unaffected component assignments and positions.
   For a new component, use `systemap place`.
   If its region has no free position, use `systemap place --all`.
   This command keeps positions with `pinned=True`.
3. For each `source review` line, examine the changed modules against all component claims.
   Include its description, interface, flows, sequences, and invariants.
   Correct claims that no longer agree with source.
   Only then record the current `source_review` digest.
4. Run `systemap refresh`, then `systemap check && systemap judgement --strict`.
   Act on newly open lines or record supported reasons under `[judgement] answered`.
   Do these commands again after further model changes.
5. If delta identifies more than one-third of the components, do the full loop in SKILL.md.
6. Do the language acceptance procedure in `references/language.md`.

An added or removed module assignment also opens source review again.
This includes modules matched by an `implemented_by` wildcard.
The command below prints current component digests. It does not examine the claims for you.
The script must import systemap.
If systemap is a uv tool and not a project dependency, the script can fail to import it.
If the script fails, show the failure to the maintainer.

```sh
uv run python - <<'PY'
from pathlib import Path
from systemap import card_review, config, extract, nest

cfg = config.load(Path.cwd())
facts = extract.build(cfg)
for current_map in nest.load(cfg).maps:
    for card in current_map.model.components:
        if card.implemented_by:
            print(current_map.id, card.id, card_review.digest(card, current_map.model, current_map.meaning, facts))
PY
```

A missing or unparsable module gives `None`.
Correct extraction before you record the digest.
A subsequent source or claim change reopens the finding.

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
| `evidence lost` | The flow no longer has its recorded support. | Examine current source and correct or renew the claim. |
| `source evidence lost` | Source records no longer support an observed claim. | Examine references, direction, and artifact before renewal. |
| `structural evidence lost` | An import or configured mechanism is missing. | Examine the flow against current source. |
| `source review` | Component source or claims changed. | Examine all claims before renewal of `source_review`. |
| `move candidate` | Removed and added modules share public names without sufficient identity evidence. | Compare source. If the module task stayed the same, change the claim to the added module. If not, remove the claim and assign the added module. The line is then not a decision. |
| `jev move`, `jev owner` | Jev suggests a move or an owner that delta did not find. | Read the source before you use the suggestion. These lines do not change the delta decisions or the exit code. |

Lines under `No action is necessary for these changes` record changes without a required decision.
A pattern-matched addition or removal can still have a separate source-review finding.

## Optional plan before code changes

With `TYPESAFE_API_KEY`, use `systemap plan "<task>"` before a change.
Jev compares the task with component functions and selects likely affected components.
Read their flows, sequences, and invariants before you edit the source.
The plan is stored under `.systemap/plans/`.
After the change, use `systemap plan --check ID --base REF`.
This comparison identifies affected components that the plan did not select.
Record unexpected effects in the pull request.

The experiment covered 86% of affected components over 80 bug reports, with 2.1 selected components per report.
On a repository not used for threshold selection, coverage was 71%.
These are recorded experiment results, not a guarantee for a new repository.
See `bench/jev/README.md` in the systemap source repository for methods and limits.

## Pull request workflow

The generated workflow runs `delta --base <base commit> --format markdown` for each pull request.
It writes one comment and updates that comment after each push.
The job fails while a line has an unanswered decision.
The comment first gives the decision and the action for each open line.
Then it gives the components, flows, sequences, and invariants that changed since the base commit.
A Mermaid diagram shows only the changed flows.
A closed section contains the lines for which no action is necessary.
To see the comment before a push, run `systemap delta --base REF --format markdown`.

## Completion

Give the maintainer a completion report with these lines:

```text
Delta: <delta header>
Actions: <the action for each finding>
Coverage: <coverage result from systemap check>
Judgement: <final systemap judgement --strict result>
Uncertainty: <each unresolved source or language uncertainty>
```
