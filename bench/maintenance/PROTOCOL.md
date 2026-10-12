# Map maintenance cost: benchmark protocol

This protocol measures the cost of map maintenance with the systemap 2.0.0 workflow.
It was written on 2026-10-12, before any run.
No run was made, and no money was spent.
A run starts only after the maintainer approves the items in the last section.

## What does the benchmark measure?

The benchmark replays 30 to 50 merged pull requests from four repositories, in their merge order.
Many of these pull requests do not change a part of the map.
For each pull request, the benchmark records these values:

- The agent cost: the dollars, turns, and minutes of each agent session.
- The model calls: the number of agent sessions and Jev requests.
- The exit code of each CI job of the 2.0.0 workflow.
- The ground truth: a human examination tells if a map update was necessary.
- A false block: CI failed, but no map update was necessary.
- A missed change: CI passed, but a map update was necessary.
- The human review time for each map update.

## Which workflow is under test?

The workflow under test is systemap 2.0.0 with the CI workflow that `systemap init` 2.0.0 writes.
Install the release from PyPI (`systemap==2.0.0`) or from the Git tag `v2.0.0`.
On 2026-10-12, this checkout has no `v2.0.0` tag. The last tag that `git tag` gives is `v1.2.0`.
Before a run, make sure that the release is available. If it is not available, stop.

The CI workflow has these five jobs:

1. `systemap extract --check`
2. `systemap check`
3. `systemap judgement --strict`
4. `systemap render --check`
5. `systemap delta --base BASE --head HEAD`

The workflow has no secret. Thus `TYPESAFE_API_KEY` is not set, and `delta` sends no Jev request.
Run all jobs and all agent sessions without `TYPESAFE_API_KEY`.
The harness must make sure that the variable is not set. Then the Jev request count is zero.

## How are the repositories and pull requests selected?

Select four public repositories that agree with these conditions:

- The source is Python or TypeScript, with 50 or more modules.
- The repository has no `systemap.toml`, no `map/` directory, and no `docs/map/` directory.
- The default branch has 10 or more merged pull requests after the start date.

Select the repositories before you read their pull requests.
Do not select a repository because of its pull requests.
This repository is not a candidate, because its maintainers wrote the map rules.
The repository `0xfauzi/kstrl` is a candidate, because it has the three recorded maintenance runs.

For each repository, select the first 10 merged pull requests after the start date.
Use the first-parent history of the default branch.
A squash commit or a merge commit identifies each pull request.
Replay a commit from a bot account or a direct push, but do not score it.

When the replay is complete, count the scored pull requests in each ground truth class.
If a class has fewer than 10 pull requests, replay the next 2 pull requests of each repository.
Do this again until each class has 10 pull requests, or until there are 50 scored pull requests.

## How does the replay work?

The replay keeps one map current through the sequence of pull requests.
Each pull request starts from the map that the previous pull request left.
The map files are `systemap.toml`, `map/`, `docs/map/`, `.claude/skills/systemap/`, and `.github/workflows/systemap.yml`.

Make the first map:

1. Clone the repository with its full history: `git clone --filter=blob:none URL`.
2. Find `S`, the first parent of the merge commit of the first selected pull request.
3. Make the first map at `S` with systemap 2.0.0 and the first-map sentence of `bench/run.sh`.
4. If `systemap check` or `systemap judgement --strict` fails on the first map, stop. Record the failure.
5. Commit the map files on a new branch `replay`. This commit is `R`.

The first-map sentence is "Map this repository with systemap. Follow the systemap skill."

For each commit in the first-parent history, `M` is the commit and `R` is the last replay commit.
Do these steps in this sequence:

1. Make the commit `H` with the tree of `M` and the map files of `R`:

   ```sh
   git checkout --detach R
   git read-tree -u --reset M
   git checkout R -- systemap.toml map docs/map .claude/skills/systemap .github/workflows/systemap.yml
   git commit -m "replay: M"
   ```

2. If the commit is scored, the examiners record the ground truth for `H` before step 3.
3. Run the five CI jobs on `H`. Use `--base R --head H` for `delta`. Record each exit code and output.
4. If all jobs pass, record zero model calls. Then go to step 9.
5. If no job other than jobs 1 and 4 fails, run `systemap refresh` and commit the result.
   Then run the five jobs again. This is a refresh block.
   If all jobs pass now, go to step 9. If a job still fails, do step 6.
6. If job 2, 3, or 5 fails, start one agent session with the maintenance sentence and the base `R`.
7. After the session, commit all changes as the commit `A`. Run the five jobs again and record each exit code.
8. If `A` changes `map/` or `systemap.toml`, the reviewer examines the change.
9. If the reviewer rejects the change, or if the ground truth gives a missed change, repair the map.
10. The last commit of these steps becomes the new `R`.

The maintenance sentence is "The code changed. Update the map with systemap: follow the systemap skill's maintenance path, with base R."
`bench/run.sh` gave this sentence to the three recorded maintenance runs.
Each session uses the settings of `bench/run.sh`: `claude -p`, `--permission-mode acceptEdits`, and its tool list.
Each session also uses `--output-format stream-json`, `--max-turns 120`, and one model for all sessions.
`bench/summary.py` reads the dollars, turns, and minutes from the session log.

A repair session gets the maintenance sentence and the list of necessary changes from the ground truth.
Record its cost in the `repair` field. The acceptance values do not include repair sessions.
If CI fails after the repair, stop the replay of that repository and record the reason.

## How do the examiners make the ground truth?

Two examiners give a class to each scored pull request. Each examiner works alone.
An examiner gets the title and description of the pull request, `git diff M^1 M`, and the map at `R`.
An examiner does not see the CI output, the delta output, the agent output, or the other class.
An examiner knows the systemap map format from `SKILL.md` and `references/schema.md`.

The examiner answers this question:
"Does this pull request make a map item incorrect, or does it make a map item necessary?"
The map items are components, module assignments, entry points, interfaces, flows, relation sentences, descriptions, sequence steps, and invariants.
A flow is incorrect if its endpoints, its direction, or its artifact is incorrect.
An error that was in the map before the pull request does not count.
A change to the generated facts file or page alone does not count.

The class is `update`, with the list of items, or `no update`.
Record the minutes of each examination.
Record the class and its SHA-256 digest before the CI jobs of that pull request start.

Calculate the raw agreement and Cohen's kappa from the two classes before a discussion.
Then the two examiners and the maintainer agree on a final class. Record the three classes.
If only one person can examine, record one class. Then the report gives no kappa and no result for A6.

The final class also gives a type for each necessary change.
A structural change is a change that a line in the delta finding table of `references/maintenance.md` identifies.
Examples are an added, removed, or moved module, a missing entry symbol, and a new crossing import.
A semantic change is a different necessary change, for example a changed flow artifact or a changed sentence.

## How is the review time measured?

The review population contains each pull request with a commit `A` that changes `map/` or `systemap.toml`.
The reviewer is not an examiner of that pull request.
The reviewer knows the systemap map format.

1. Open `git diff H A -- map systemap.toml` and the Changes view of `systemap serve`.
2. Start the time measurement.
3. Examine the change against the source change of the pull request.
4. Record `accept` or `reject`, with a reason.
5. Stop the time measurement. Record the minutes with one decimal place.

## What does each replay step record?

The harness writes one JSON line for each replayed commit to `bench/maintenance/results.jsonl`.

| Field | Value |
|---|---|
| `repository` | The repository URL. |
| `pr` | The pull request number, or `null` for a commit that is not scored. |
| `scored` | `true` or `false`. |
| `merge`, `base`, `head`, `after` | The commits `M`, `R`, `H`, and `A`. `after` is `null` without a session. |
| `files` | The number of changed files in `M`. |
| `ci` | The exit code of each of the five jobs on `H`. |
| `refresh_block` | `true` if step 5 ran. |
| `ci_after_refresh` | The exit codes after the refresh, or `null`. |
| `session` | The `bench/summary.py` values: dollars, turns, minutes, model, run, and first tool. `null` without a session. |
| `ci_after` | The exit codes after the session, or `null`. |
| `jev_requests` | The number of Jev requests. |
| `truth` | The final class, its items and types, the two examiner classes, and the examination minutes. |
| `review` | The minutes and the decision, or `null`. |
| `repair` | The `bench/summary.py` values of the repair session, or `null`. |
| `false_block` | `model` (job 2, 3, or 5 failed), `refresh` (no job other than jobs 1 and 4 failed), or `null`. |
| `missed` | `structural`, `semantic`, or `null`. |

A false block is a scored pull request with the class `no update` and a failed CI job.
A missed change is a scored pull request with the class `update` and five passed CI jobs.
Record the results in `bench/jev/README.md`, with the failures and the stopped steps.

## What are the acceptance values?

These values were written on 2026-10-12, before any run.
Do not change a value after the pilot starts.

| ID | Measurement | Population | Acceptance value | Source |
|---|---|---|---|---|
| A1 | Model calls: agent sessions and Jev requests | Each scored pull request with the class `no update` | 0 on each pull request | The external review of 2.0.0: "no model calls for a pull request with no architecture change". |
| A2 | Dollars of the agent session | Scored pull requests with the class `update` and a session | Median less than 1.00 dollar | The external review of 2.0.0: "under 1 dollar for a typical update". This protocol uses the median for "typical". |
| A3 | Review minutes | The review population | Median less than 2.0 minutes | The external review of 2.0.0: "under 2 minutes of human review". |
| A4 | False blocks of type `model` | Scored pull requests with the class `no update` | 0 | A1. The 2.0.0 workflow starts an agent session for each such block. |
| A5 | Missed structural changes | Scored pull requests with the class `update` | 0 | README: "CI rejects the pull request while it is necessary to update the map." The delta finding table in `references/maintenance.md`. |
| A6 | Cohen's kappa of the two examiner classes | All scored pull requests | 0.60 or more | This protocol, from the scale of Landis and Koch (1977). The maintainer must approve it. |

These measurements have no acceptance value. The report gives their counts and values only:

- False blocks of type `refresh`.
- Missed semantic changes.
- The turns and minutes of each session.
- The number of rejected updates and repair sessions.

The maintainer can set a value for each of these measurements before the pilot starts.

A1 and A4 need 10 or more pull requests with the class `no update`.
A2 needs 10 or more pull requests with the class `update` and a session.
A3 needs 10 or more reviews.
With fewer pull requests, the report gives the values but no acceptance result.
If A6 fails, the report gives the values of A1, A2, A4, and A5, but no acceptance result for them.
A3 does not use the ground truth.

With n pull requests and no failure, the 95% upper limit of the failure rate is approximately 3/n.
This is the rule of three. With 10 pull requests, the limit is 30%. With 20 pull requests, the limit is 15%.

For comparison only, `docs/benchmarks.md` gives the earlier limits for a medium pull request: 15 turns and 2 dollars.
All three recorded maintenance runs exceeded these limits.
That document also says that the 15-turn limit came from an incorrect assumption.

## What does the full run cost?

This section gives an estimate from recorded runs. It is not a measurement.

`docs/benchmarks.md` gives three recorded maintenance sessions on `0xfauzi/kstrl` (111 modules).
They used systemap 0.11.0 and the model `claude-opus-5[1m]`.

| Value | Pull request 237 | Pull request 213 | Pull request 184 | Mean |
|---|---|---|---|---|
| Dollars | 2.31 | 4.39 | 2.50 | 3.07 |
| Turns | 51 | 63 | 46 | 53.3 |
| Minutes | 6.4 | 11.3 | 5.8 | 7.8 |

In `bench/results.jsonl`, the first maps with `claude-opus-5[1m]` cost from 3.43 dollars (78 modules) to 25.49 dollars (144 modules).
Thus four first maps cost from 13.72 to 101.96 dollars.

The estimate has one agent session for each scored pull request.
The procedure starts no more than one session for each replayed commit, before repairs.
The low value uses the mean session cost (3.07) and the lowest first-map cost.
The high value uses the highest session cost (4.39) and the highest first-map cost.

| Scored pull requests | Sessions, low | Sessions, high | Total, low | Total, high |
|---|---|---|---|---|
| 30 | 92.00 | 131.70 | 105.72 | 233.66 |
| 40 | 122.67 | 175.60 | 136.39 | 277.56 |
| 50 | 153.33 | 219.50 | 167.05 | 321.46 |

The estimate has these limits:

- The recorded sessions come from one repository and three pull requests.
- They used systemap 0.11.0 and the reverse comparison direction. Each of the three pull requests needed a map update.
- A pull request with no session has no model cost. The real number of sessions is not known before the run.
  If fewer pull requests start a session, the real cost is less than the table gives.
- The estimate does not include repair sessions or sessions on commits that are not scored. One such session can cost as much as one maintenance session.
- A different model gives a different cost. The httpie first map cost 3.43 dollars with `claude-opus-5[1m]` and 1.14 dollars with `claude-sonnet-5-5`.
- The estimate does not include human time. The pilot measures the examination and review minutes.

### Pilot

The pilot replays 5 pull requests from one repository.
Its cost is at most one first map (25.49) and five sessions (21.95), thus at most 47.44 dollars.
The pilot finds harness errors and measures the number of sessions and the human minutes.
After the pilot, write a new estimate. Do not change the acceptance values.

## What must the maintainer approve before a run?

1. The spend limit for the pilot and for the full run. The harness stops when the recorded dollars reach the limit.
2. The model for all sessions. The recorded rows used `claude-opus-5[1m]`.
3. The four repositories, the start date, and the rule that adds pull requests.
4. The acceptance values and the definitions of this protocol: the median for "typical", the classes, the change types, and the kappa value.
5. The people: two examiners and one reviewer, and their time. With fewer people, the limits of the ground truth section apply.
6. The harness. It is not written. `bench/run.sh` appends to `bench/results.jsonl`, and `bench/table.py` makes `docs/benchmarks.md` from that file.
   The replay harness must write to `bench/maintenance/results.jsonl` instead. Its tests must use recorded logs and must not call a model.
7. A computer where `git` and `gh` can read the repositories. On 2026-10-11, a Claude Code session could not use GitHub GraphQL (`bench/jev/README.md`).
8. The release under test: `systemap==2.0.0` or the tag `v2.0.0`.

These rules stop a run:

- When the recorded dollars reach the spend limit, stop. Record the last complete pull request.
- If a step cannot complete, show the failure and stop. Do not use a different step instead.
- A session that stops at `--max-turns` counts with its cost. Record `cut off` and repair the map.

## What is not in this protocol?

- The changes after 2.0.0, for example a judgement finding for a stale source review. A second run can use the same pull requests.
- An acceptance value for the first map. The report gives its cost only.
- Jev. All runs are without `TYPESAFE_API_KEY`.
