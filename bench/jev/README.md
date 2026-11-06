# Jev experiments

These experiments measure TypeSafe's Jev model on systemap maps.
The reference data comes from the five first maps in `bench/scratch`, Git history, and GitHub history.
The measurements led to `systemap audit` and `systemap triage`.
Their thresholds come from the curves in `score.py`.

    uv run --project bench/jev python bench/jev/build.py      # labelled rows -> data/ (no API calls; build_flows.py, build_meaning.py hold the rest)
    uv run --project bench/jev python bench/jev/run.py        # every row once -> results/*.jsonl.gz
    uv run --project bench/jev python bench/jev/score.py      # metrics, with today's heuristic beside each
    uv run --project bench/jev python bench/jev/moves.py build|score

`run.py` must have `TYPESAFE_API_KEY`.
It skips rows with recorded answers.
It does not substitute a guessed answer when a call cannot complete.
`bench/run.sh` writes the Git-ignored `bench/scratch` data.
The `data/` directory is made again from that data and is not committed.

The `results/` directory is committed, with compressed files.
The `results/report.txt` file contains the scorer's output from the recorded run.

## What did the accuracy experiments show? (2026-09-26 to 2026-10-02)

These are recorded results from the accuracy work.
They are not new runs.
The [original scripts, reports and captured results](https://github.com/0xfauzi/systemap/tree/0bf26334564e460b3f7626b32bd81ef705491af6/bench/jev)
are available at the revision before cleanup.
The [consolidated review](https://github.com/0xfauzi/systemap/blob/0bf26334564e460b3f7626b32bd81ef705491af6/ACCURACY_FINDINGS_AND_RECOMMENDATIONS.md)
is also available there.

Production regression tests are in `tests/`.
The implementation PR does not include the experiment scripts or the unfinished ownership-evaluation harness.

The selected Python probes had to give the expected result for every selected contract and control.
The first run reproduced 24 gaps, with four controls that gave the expected results.
Added cases increased the gap count to 31, then 32, then 33.
Runs after formatting gave the same results.
The 376 tests from before the work gave the expected results.
After implementation, all 37 Python and 32 TypeScript contracts gave the expected results.

These selected counterexamples examine specific behavior.
They do not measure accuracy for a full map.

A census read 1,381 Python files across eight mapped repositories.
Python 3.11 silently did not include 15 of Mealie's 460 files because they used Python 3.12 syntax.
Python 3.12 read all 460 files and found evidence for five flows again.
Parsed-file coverage increased from 96.74% to 100%.
The reader refactor and added source hashes did not change the counts.

The TypeScript dependency census had to find zero missing targets and zero incorrect targets in the extracted inventory.
The reference targets were compiler-resolved dependencies.
The census agreed with all 1,171 eligible dependencies on these pinned revisions:

| repository | revision |
|---|---|
| Hono | `90d02fb1645c12a65d27f39594d2129db2065ba7` |
| Ky | `0d59458a0a58e1c3d7c6db0ab17ed5c7cd671e47` |
| Zod | `2bf7b0630d5378033e90bcee82cb32b0fe04628e` |

The compiler reference was TypeScript 5.9.3.
Unresolved, external, and unextracted targets were excluded.
This check measured dependency extraction in uninstalled checkouts.
It did not measure semantic ownership or sequence accuracy.

### Why was rename matching by identical content rejected?

The acceptance rule required fewer disagreements with Git, without loss of correct pairs.
The reference set contained 33 commits with renames and 86 Git-labelled renames.
The table compares the production rules with unique identical-content pairs:

| method | correct pairs | Git disagreements | missed reference pairs |
|---|---:|---:|---:|
| current rules | 65 | 4 | 21 |
| unique exact content | 13 | 0 | 73 |

The candidate lost 52 correct pairs, so it was not released.
Git's similarity labels are a reference, not independent semantic truth.
The Python 3.11 run did not complete because a Mealie module was missing. It gave no score.
The scored run used Python 3.12.

### Why was package ownership evidence rejected?

The proposed rule found assignments with at least two package peers in a different component and none in the component claiming the module.
Before the run, the acceptance rule required finding of at least 50% of planted errors.
It also permitted false alarms on at most 3% of unchanged owners in each map set.
The table compares the production rule with the added package evidence:

| map set | rule | planted errors caught | unchanged owners flagged |
|---|---|---:|---:|
| development | current | 61/195 | 2/195 |
| development | with package evidence | 116/195 | 21/195 |
| holdout | current | 32/96 | 1/96 |
| holdout | with package evidence | 52/96 | 23/96 |

The addition exceeded the false-alarm limit on the two sets and was not released.
A package can correctly have modules in different components because the modules have different purposes.
Finished maps supplied the labels.
These results measure agreement with those maps.

### What limits the source-reading ownership pilot?

Claude Opus 5.5 examined eight sampled modules from each of five development maps and three holdout maps.
Each map supplied four planted assignment errors and four unchanged assignments.
The model saw source, module facts, and adjacent component descriptions.
It did not have tools, Jev, reference owners, or component module lists.
Files with more than 25,000 characters were excluded.
Modules without an adjacent component were also excluded.

Before the run, the acceptance rule required finding of at least 60% of planted errors.
It permitted challenges to at most 5% of unchanged assignments.
Planted-error recall also had to exceed the word rule on the two sets.
The table gives the results:

| set | planted caught | reference card chosen | unchanged challenged | word rule caught | word rule challenged |
|---|---:|---:|---:|---:|---:|
| development | 20/20 | 19/20 | 1/20 | 5/20 | 1/20 |
| holdout | 12/12 | 12/12 | 1/12 | 3/12 | 0/12 |
| combined | 32/32 | 31/32 | 2/32 | 8/32 | 1/32 |

The pilot challenged 6.25% of unchanged assignments and exceeded the 5% limit.
Its decisions agreed with the reference on 62/64 cases.
The word rule agreed on 39/64 cases.
This is agreement on a balanced synthetic sample, not an error rate for real maps.
Five systemap cases mixed source snapshots and cached-facts snapshots.
Each batch put all planted cases before unchanged cases.

The two challenged reference owners and one different replacement have unresolved semantic labels.

The first kstrl call gave fenced JSON and was rejected.
The identical prompt was tried again.
Acceptance of the fence did not change the judgement.
Eight scored calls gave a recorded cost of $1.88.
That cost does not include unsuccessful calls or diagnostic calls.

The later offline harness made 437 cases with nonempty modules from 460 Mealie records under Python 3.12.
It excluded 23 empty package markers.
One nested map was recorded but not scored.
There were no independent labels or paired workflow results.
A new holdout and independent source labels are necessary before claims of semantic improvement or changes to defaults.

The implementation gave the expected results for 450 tests on 2026-09-27 and 463 on 2026-09-28.
Pre-commit completed without findings on the two runs.
After the PR review fixes, Python 3.11 gave the expected results for 501 tests, with one expected syntax-version skip.
Python 3.13 gave the expected results for all 502 tests.
Mypy, pre-commit, and strict self-map judgement completed without findings.
These historical counts precede removal of the exploratory harness tests.

The table gives each experiment's label source and question.
The recorded experiment names and questions are kept unchanged.

| experiment | label | question to Jev |
|---|---|---|
| owner | the card that claims the module in the finished map | which card does this module belong to (Choice) |
| where | the card owning a function whose docstring is the query | which card does this described behaviour live in |
| issues | the cards a fixing PR touched (rich, poetry) | which card will the fix for this issue change |
| pairs | same card in the finished map | do these two modules make one part (Noul) |
| flowkind | the flow's kind in the map | which kind is this flow |
| flowverify | the flow's own sentence against another flow's | does the code at the joins carry this claim |
| crossing | a drawn edge against a line answered as incidental | how much does a reader need this edge (Score) |
| sentence | the card's own sentence against a sibling's | does this sentence describe these modules |
| drift | the sentence rewritten in the same commit or run | does the old sentence still hold after this diff |
| drift_head | as drift | the old sentence against the modules at the head |
| governs | the invariant's `governs` list | does this rule govern this card |
| cardkind | the card's kind | what kind of card are these modules |
| answerfit | the answer that covers the crossing line | does this recorded reason cover this import |
| moves | git's rename detection at 50% | which new module is the old one |

## Which repositories are in the holdout set?

`JEV_SET=holdout` makes data, runs experiments, and calculates scores on maps not used to select a threshold.
The maps are systemap's own map, scorecard (`../scorecard`), and the newest finished `bench/run.sh https://github.com/httpie/cli first-map` run.
Data and results go to `holdout/` under `data/` and `results/`.
The scorer prints each experiment at the threshold used by `systemap audit`.

    JEV_SET=holdout uv run --project bench/jev python bench/jev/build.py owner sentence flowverify governs issues
    JEV_SET=holdout uv run --project bench/jev python bench/jev/run.py owner sentence flowverify governs issues
    JEV_SET=holdout uv run --project bench/jev python bench/jev/score.py owner sentence flowverify governs issues

The acceptance rule was set before the run.
Each holdout result had to be within 10 points of the development result.
If not, the default selection must not include that question type.
The `results/holdout/report.txt` file contains the output:

| kind, at the shipped threshold | development | holdout | verdict |
|---|---|---|---|
| mis-fold, planted next door (P<0.05) | 95% caught, 4% flagged | 93%, 1% (n=96) | asked |
| owner (confidence >= 0.9) | 56% answered, 98% right | 60%, 100% | asked |
| sentence (P<0.2) | 67% caught, 1% flagged | 61%, 2% (44 wrong) | asked |
| flow (P<0.2) | 66% caught, 2% flagged | 54%, 4% (48 wrong) | only with `--kind "jev flow"` |
| governs (P>=0.8) | 31% found, 1% suggested | 38%, 1% (58 governed) | asked |
| issues, top-1 (`triage`) | 80% | 79% (39 httpie issues) | shipped |

The follow-up for Test 9 used `bench/run.sh <repo> first-map-jev`.
This was the first map instructed to group with `suggest --jev`.
On httpie 3.2.4, that run took 54 turns, $3.61, and 5.5 minutes.
The plain first map took 46 turns, $3.43, and 4.8 minutes.
There was one run each, recorded in `bench/results.jsonl`.
No saving was measured, so `suggest --jev` stays optional and outside the recipe.

## What did tests 7 and 8 measure?

The maintainer did not select manual labels.
A Claude subagent read the full Git commits and labelled each set one time.
It did not see Jev's answers.
The `results/labels/agent-*.json` files contain a reason for each item.
The scores are in `results/labels/report.txt`.
The `results/labels/label-page/index.html` file is the archived page for manual labels in these tests.
You cannot operate this page from this repository, because no command makes its input file `items.json` and the page must have the host API of claude.ai.

Test 8 examined moves: 20 successors and 12 unrelated cases.
This factual question has evidence in Git, so the agent's labels were accepted as the reference truth.
Delta followed by Jev at P>=0.8 found 82 renames, compared with 66 from delta.
Of Jev's 17 additions, 16 were correct (94%).
The acceptance rule was at least +8 at 90% accuracy or better.
Test 8 met the acceptance rule.

Test 7 examined drift: 12 stale sentences and 48 unchanged sentences.
A model labelled another model's semantic answers, so the result measures agreement, not truth.
AUC was 0.957.
At P(holds)<0.4, 75% of stale sentences were found, with 0.4 false alarms per 10 components.
The result met the numerical acceptance rule. It is not an independent accuracy measurement.
Drift finding stays unbuilt until approximately 15 human labels agree with the agent's labels.

## Does Jev decrease the cost of the first map? (turns.py, draft.py)

The proposed method gave Jev the module-owner questions while the agent wrote only component definitions.
Before implementation, two experiments used the six first maps in `bench/scratch`.
Their results are in `results/draft/`.

`turns.py` measured the tool calls.
The first model write claimed every module in all six runs.
There was no `unmapped:` line at the first check.
Later edits to `implemented_by` were 1% of calls.
Reading and planning were 31%, reading after the draft was 32%, and the check and judgement loop was 25%.
Module assignment did not account for most first-map turns.

`draft.py` sent the owner question for every module against each run's first loadable draft.
The reference was the finished map.
Only 1% of modules changed component between draft and finished map.
Thus, the agent's draft agreed with the finished map on 99%.
Jev agreed on 87%, and on 98% of the 63% with confident answers.

The finished map was the agent's own, so these are agreement figures, not truth.
There were 22 confident disagreements.
Most concerned components split in the draft and merged later.
A few appeared to be incorrect assignments, such as Mealie's `auth_cache` under HttpApi.

There was no measured saving in module assignment.
There was also no evidence that Jev can increase the accuracy of the agent's draft.
Thus, the method was not implemented and the first-map benchmark was not run.
The mis-fold finding in `audit` uses the question that finds the few incorrect assignments.

## What can structure show about a sequence? (2026-09-20)

Two sequence questions were measured on seven maps before release.
These were the six maps in `bench/scratch` and systemap's own map.
A sequence is an ordered set of steps through the map.
An entry point is a route, command, task, or hook that starts work in the system.

`systemap.ways_in` reads routes, commands, tasks, and plugin hooks from the syntax tree.
The table gives discovered entry-point totals before and after the change:

| map | before | after | what the new ones are |
|---|---|---|---|
| paperless-ngx | 0 | 98 | 59 Django routes, 22 Celery tasks, 17 management commands |
| poetry | 3 | 44 | 41 cleo commands |
| mealie | 8 | 203 | 195 FastAPI routes |
| kstrl | 7 | 38 | 31 click commands |
| rich | 6 | 6 | none; its `@group()` is not a command |
| httpie, systemap | 5, 19 | 5, 19 | neither uses a framework this reads |

A manual sample of 30 new records contained 29 entry points with source evidence and one incorrect record.
The incorrect record was Rich's `@group()`.
Thus, a command decorator must be called on something.
The acceptance rule was 90%.

Three rules examined if each step continued from the previous step.
Each rule used the same seven maps.
The table gives the results:

| rule | steps flagged | real, by hand review |
|---|---|---|
| the edges join | 30 | 0 |
| the actors acted the step before | 46 | not reviewed; worse by inspection |
| the actors appeared anywhere earlier | 27 | not reviewed; the same shapes |

The acceptance rule required 80% real gaps.
A sequence can include a subsidiary call and then continue in the component that started the call.
The sequence can be correct although successive edges do not connect.
The structural rules did not show continuity, so no `journey gap` finding was released.

The released `journey start` finding shows a named entry point missing from the facts.
It shows if the name is in the source facts.
It does not show the sequence's behavior.

### Why were import-derived sequences rejected? (paths.py, propose.py)

Before `systemap journeys` told an agent to read source, facts alone proposed a sequence.
The method followed imports from the entry point.
It converted each module to the component that claims it.
It kept component transitions only where the map had a flow.
Before the run, the acceptance rule required a median overlap of 0.60 with manually written sequences.

    uv run --project bench/jev python bench/jev/paths.py

The table gives the measured overlap:

| maps | journeys matched to a way in | median overlap |
|---|---|---|
| systemap and the six first maps | 16 | 0.28 |

The result was below the acceptance rule.
A console-script module imports most of the system, so the proposal included almost every component.
The reference sequence included four components.
Reading the entry function's imports did not help because a command line dispatches through a table.
The proposal was not released.
The `bench/jev/propose.py` file keeps the method, and `paths.py` calculates its score.

`systemap journeys` tells the agent to read source from the entry point.
It compares every proposed step with the map.

## What does the map graph add to imports? (2026-09-20)

The proposed `systemap ripple` command was to find other components affected by a change.
It was not implemented because the map traversal did not exceed imports alone under the acceptance rule.

The first reference plan paired each pull request with a pull request that fixed it within thirty days.
The set contained 2,406 merged pull requests across Rich, Poetry, Mealie, paperless-ngx, and HTTPie.
A strict rule excluded release rollups.
The later request had to say fixes, reverts, regression, or broken by.
It also had to name at most three pull requests, with Python changes in the two requests.
This rule found only 6 pairs.

Six cases could not show a ten-point difference.
Thus, co-change became the reference: components changed in the same pull request.
The starting component owned the file with the most changes.
The question was which other changed components the rule found.
There were 366 qualifying pull requests on six maps.

    uv run --project bench/jev python bench/jev/ripple.py

The table compares map traversals with the import closure:

| rule | recall | precision | cards named | share of the map |
|---|---|---|---|---|
| the cards the flows leave to, one hop | 0.00 | 0.00 | 2 | 0.06 |
| the same, three hops | 0.50 | 0.07 | 13 | 0.37 |
| the cards a flow joins either way, one hop | 0.50 | 0.17 | 5 | 0.14 |
| the same, two hops | 1.00 | 0.09 | 19 | 0.54 |
| one hop either way, plus the journeys through the card | 0.67 | 0.11 | 10 | 0.29 |
| every module the imports reach, as cards | 1.00 | 0.05 | 20 | 0.57 |

These are medians on maps with a median of 35 components.
Before the run, recall had to be within 10 points of the import closure, at no more than half its size.
No method met the acceptance rule.
Two hops in one direction or the other matched import recall but had 95% of its size.
One hop had a quarter of the size but half the recall.
Addition of sequences through the component reached 0.67 at half the size, 33 points below the baseline.

The baseline achieved recall by naming 20 of 35 components: 57% of the map, at 0.05 precision.
One hop was three times more precise at a quarter of the size.
Those results suggest a different question, but they do not meet the recorded acceptance rule.
Thus, ripple was not released.
A future feature must have a useful question and an acceptance rule set before measurement.

## How does a plan compare with the map? (2026-09-20)

`systemap plan` gives a question about which components a task will probably change.
The reference is the issue set used for triage.
It pairs recorded bug reports with components changed by the fixing pull requests (`data/issues.jsonl`, `label.owners`).
The input is the report alone, written before the work.

Before the run, the acceptance rule required coverage of 70% of changed components, with at most 2 extra components per issue.
Jev gives a weight for every component.
Thus, the full threshold curve can be calculated offline from recorded triage answers.

    uv run --project bench/jev python bench/jev/plan_eval.py
    JEV_SET=holdout uv run --project bench/jev python bench/jev/plan_eval.py

The table gives coverage and extra components at each threshold:

| cut | covered (dev) | extra | covered (holdout) | extra |
|---|---|---|---|---|
| 0.50 | 0.69 | 0.16 | 0.46 | 0.13 |
| 0.30 | 0.79 | 0.26 | 0.58 | 0.33 |
| 0.20 | 0.82 | 0.42 | 0.63 | 0.36 |
| 0.10 | 0.86 | 0.69 | 0.66 | 0.59 |
| **0.05** | **0.86** | **1.15** | **0.71** | **0.90** |
| 0.02 | 0.88 | 1.91 | 0.74 | 1.31 |

The development set contained 80 issues, 40 from Rich and 40 from Poetry (`results/report.txt`, issues).
The holdout contained 39 HTTPie issues.
The threshold that met the rules for the two sets was 0.05, which `systemap plan` uses.
It named 2.1 components per task on each set.

The gap between sets was 15 points at that threshold.
That exceeded the 10-point limit used for audit thresholds.
The holdout was one repository.
Thus, the results show that the plan prediction is better on some systems than others.
The command names approximately two components for a maintainer to examine.

## What does a year of changes show in the component in the selected maps? (2026-09-20)

`systemap history` samples past trees and shows changes in the component assignments in the selected map.
Two acceptance rules were set before implementation.
With cached facts, 26 samples during a year of Mealie had to take at most five minutes.
At least three of the five largest windows had to show a change visible in that window's commits.

    uv run --project bench/jev python bench/jev/history_eval.py --repo mealie

The table gives measured sample counts and times:

| repository | samples | cold | warm | windows that moved |
|---|---|---|---|---|
| mealie | 25 | 29.3s | 0.3s | 14 of 24 |
| rich | 8 | 5.8s | 0.0s | 1 of 7 |

The `results/history-<repository>.json` files contain the windows of the two runs.
In `results/history-mealie.json`, 14 of the 24 windows have a change.
That file records 0.3s cold. The repository does not contain the result file of the 29.3s run.

The two runs completed in the permitted time.
Facts at a commit do not change, so the command caches them under `.systemap/facts/`.
The next table gives the five largest Mealie windows and the work they showed:

| what the trend said | the work behind it |
|---|---|
| ImportWorkflow +17 modules, 5 new crossing imports | feat: Unified AI recipe page (#8043) |
| ways in +7, AiService -> Repositories | feat: In-app AI Provider Configuration (#7650) |
| IngredientParser +1, four crossings into Translations | feat: Unit standardization / conversion (#7121) |
| QueryFilter +4 | feat: Query relative dates (#6984) |
| Translations +3 | feat: Customize Ingredient Plural Handling (#7057) |

All five showed changes with source evidence, compared with an acceptance rule of three.
The output named commits that added the new modules, rather than all commits in each window.
Most commits in a fortnight of Mealie were dependency updates.
Those commits made the trend difficult to interpret.
`systemap history` prints the module-creation commits under each window for this reason.

Rich changed little in a year.
Only one window changed, when Unicode width tables were made again.
The command correctly printed little for that period.

## Can Jev find changes to sequence behavior? (2026-09-20)

The proposed feature was a section in `delta`'s pull-request comment.
The proposal was to examine sequence steps through changed components.
The proposal was to give Jev questions about the correctness of step sentences, then tell an agent to rewrite incorrect sentences.
This feature was not implemented.

### Which steps were selected?

The set contained fifteen steps from the benchmark maps.
The maps were written on 2026-08-23/26.
The comparison used each repository's origin on 2026-09-20.
A step qualified when files behind its two components changed by at least twenty lines.
The largest cases per repository were kept, with at most four each.
kstrl, Paperless, Mealie, and Poetry supplied cases.

Rich and HTTPie supplied none because source behind their steps did not change.
`bench/jev/label_set.py` writes the set to `data/label-drift-cases.json`.

### What did the source labels show?

The labels came from reading source at the two commits, not the diff excerpt.
All fifteen sentences stayed correct.
Each label includes its reason in the data file.

Paperless deleted a 610-line query translation module.
The sentence "Tantivy returns ranked hits with the matching text highlighted" stated the backend's behavior.
Mealie removed 194 lines from the recipe repository, but these were `find_suggested_recipes`.
The group and household values in the step were unchanged.
kstrl added 3,584 lines to its verifier.
`run_mechanical_verification` said "All checks run even if earlier ones fail".

The finding concerns sequence abstraction: step sentences state roles, such as "the controller hands the address to the scraper".
A month of source changes did not change those roles in this set.
The labels are the author's, not a maintainer's.
Thus, 15 of 15 is a model's judgement from source.

### What did Jev answer?

Jev saw each step, the two components, commit subjects, file lists, and the capped diff.
It answered the same question for the same fifteen cases.

    uv run --project bench/jev python bench/jev/drift_steps.py

The table gives the findings for the proposed delta output:

| where delta would draw the line | steps it would report | how many would be wrong |
|---|---|---|
| below 0.5 | 2 of 15 | 2 |
| below 0.6 | 6 of 15 | 6 |
| below 0.7 | 12 of 15 | 12 |
| below 0.8 | 15 of 15 | 15 |

Jev's answers ranged from 0.43 to 0.75.
No answer was confident in one direction or the other.
All cases were negative, so every alarm at every threshold was false.
The lowest threshold gave two incorrect findings per fifteen steps.
The higher threshold gave twelve.
No threshold gave useful findings on this set.

On this month's evidence, the proposed pull-request comment gives four false findings to four maintainers and no correct findings.
Thus, the feature was not implemented.
The capped diff is a limit: a larger or differently selected diff can give a different result.
The set has no positive cases, so it measures false alarms only.
It cannot show if the method can find source-behavior drift.
The result suggests that drift can be too infrequent for a useful question on every pull request.

## What further work do the measurements suggest? (2026-09-20)

Three results suggested further experiments.
Each experiment below has an acceptance rule recorded before work started.

### 1. Adjacent components as context

The ripple experiment did not meet its recall acceptance rule.
It also measured these medians for the same 366 pull requests:

| rule | cards named | share of the map | precision |
|---|---|---|---|
| one hop either way over the flows | 5 | 0.14 | 0.17 |
| every module the imports reach | 20 | 0.57 | 0.05 |

Map edges named a quarter as many components as imports.
They were three times as likely to include a component changed by the request.
This is a limited prediction, but it can give a short context list.
The proposed `delta` output was to show components adjacent to the change.
The proposal did not claim that those components were defective.

Before the work, the acceptance rule permitted at most 6 components at the median.
The list also had to contain at least one changed component in 50% or more of the same 366 pull requests.
The experiment must meet the two conditions before release.
The dataset was present before the experiment. The necessary work was a run and an inspection.

The experiment met the acceptance rule and was implemented (2026-09-20, `bench/jev/near.py`).
The measured rule started from the component owning the file with the most changed lines.
It gave 5 components at the median and a hit in 70% of requests.
`delta` reads facts at two commits, without a diff, so it cannot count changed lines.
Thus, it starts from the component with the most changed modules.
That rule was also measured on the 359 pull requests where it applied:

| what would be printed | cards (median) | ninetieth | holds a touched card |
|---|---|---|---|
| one hop from the seed card | 6 | 14 | 0.72 |
| one hop from every changed card | 14 | 21 | not scored: every touched card is a seed |
| every module that card imports | 20 | 32 | 0.77 |

The union of all changed components' neighbours gave fourteen components at the median.
It was too long and was not implemented.
Imports increased the hit rate by five points but gave three times as many components.
This repeats ripple's result.
Thus, the feature gives context, not a claim about additional failures.

Fourteen components at the ninetieth percentile was too long.
A component connected by flows to most of the map gave little useful selection.
`delta` prints no context when the starting component connects to more than a third of the components.
The skill used that threshold before the work to select the full loop instead of individual findings.

This condition removed context for 18% of pull requests.
For the others, the list contained 5 components at the median and 8 at the ninetieth percentile.
The hit rate decreased 3 points to 0.69.

### 2. Growth by component

The five largest `history` windows showed the commits that caused their changes.
The same traversal, with changes added during a year, can show component growth.
Mealie gave this output:

    ImportWorkflow +17   SchemaMigrations +7   QueryFilter +4   Translations +3

No component decreased in size during twelve months.
Repeated growth can mean a shared foundation or poor module assignments.
The map's purpose statements help the reader distinguish those cases.

Before the work, the three fastest-growing components had to show at least one feature commit each.
This had to hold on at least three of four repositories.
The proposed `systemap history --by-card` used numbers that `trend.walk` calculated before the work, so the implementation cost was small.

The experiment did not meet the acceptance rule and was not implemented (2026-09-20, `bench/jev/by_card.py`).
Only two of four repositories met the acceptance rule, compared with the required three.
The table gives the results:

| repo | the three fastest-growing cards | traces to |
|---|---|---|
| mealie | ImportWorkflow +17, SchemaMigrations +7, QueryFilter +4 | all three: "feat: Unified AI recipe page", "feat: Announcements", "feat: Query relative dates" |
| paperless | AppConfig +11, SearchIndex +7, FileParsers +5 | all three: "support ollama embeddings", "Replace Whoosh with tantivy search backend", "Initial document parser plugin framework" |
| poetry | HttpAccess +1, and no other card grew at all | one perf commit, and nothing to rank |
| rich | Measure +23, and no other card grew | one commit titled "f string path", which names nothing |

The aggregate showed work where a system grew.
Poetry gained one module in a year under the map's assignments, so there was no useful growth ranking.
Rich's twenty-three additions were made Unicode tables.
Their commit subject had three words without a useful description.

A new rule with a size threshold can meet its acceptance rule, but that was not the recorded rule.
On the two growing repositories, all three components showed named work.
The `history` windows print that information.
The aggregate added no different answer.

The instrument changed one time before any scoring.
It first showed the newest commits that changed each component's new files.
During a year, these were fixes rather than file-creation commits.
`--diff-filter=A` selected the commit that added each file instead.
The two versions are in the Git history of `by_card.py`.

### 3. One sequence per entry-point group

Discovery increased paperless-ngx from 0 to 98 entry points and Mealie from 8 to 203.
Mealie's 195 new entry points were FastAPI routes.
Each map had four written sequences.
Before the work, `judgement` grouped entry points into one finding per component at four or more of one kind.
At that time, `systemap journeys` wrote one sequence per entry point, at most three per run.

Before the work, a sequence for each group in Mealie and Paperless had to give no findings in the map's checks in at least 70% of attempts.
Every step had to trace a flow in the model.
The number of findings for entry points without sequences also had to decrease from approximately two hundred to fewer than fifteen.
Agent runs were necessary for this experiment, so it was the most expensive of the three and ran last.

The experiment met the acceptance rule and was implemented (2026-09-20, `bench/jev/group_journeys.py`).
Eight of nine groups across Mealie, paperless-ngx, and Poetry gave structurally accepted sequences: 89% against a 70% rule.
For Mealie and Paperless alone, four of five groups gave structurally accepted sequences.
The rejected sequence had a MediaFiles -> Assets step missing from Mealie's flows.
The command printed a finding and wrote nothing for that sequence.

The table records open entry points in groups, rather than all discovered entry points:

| repo | ways in in crowds | crowds | walks the map can hold |
|---|---|---|---|
| mealie | 195 | 2 | 1 |
| paperless | 86 | 3 | 3 |
| poetry | 27 | 4 | 4 |

The recorded `results/group-journeys.json` contains 195 grouped open entry points for Mealie and 86 for Paperless.
Those populations differ from the discovery totals of 203 and 98.

The second acceptance condition was true before the work.
`judgement` had grouped entry points since entry-point discovery was added.
Mealie's 195 open entry points printed as 2 findings.
Paperless's discovered population of 98 printed as 15 findings under that grouping.
The recorded acceptance rule incorrectly assumed ungrouped findings.

Before this change, a sequence could not be written per grouped finding.
`systemap journeys` wrote one per entry point, at most three per run.
Thus, Mealie's entry points had to use sixty-five runs.
The group method used two agent runs for Mealie and three for Paperless.

A group sequence names its component in `starts`.
It cannot name one route while representing all routes without narrowing its claim.
`judgement` treats a component in `starts` as coverage for every entry point claimed by that component.

An earlier run scored 19 of 19.
That is not the recorded result above.
It included individual entry points and used its own question instead of the production question.
The two differences were corrected.
The script calls `journeys.gather`, `journeys.context`, and `journeys.read_answer`.
Thus, the experiment measures the code that runs.

Structural acceptance does not show that the sequence is correct for the source.
All eight accepted sequences fit the map.
Successive steps often included subsidiary calls: of seven successive pairs, two to four started where the previous step ended.
Two answers had nine steps, although the question specified four to eight.
The checks did not examine the two conditions.

The attempted continuity rules showed thirty steps, but manual inspection found no discontinuities with source evidence.
`src/systemap/graph.py` records that result.
A new sequence is written with `drafted=True`.
It prints as a `drafted journey` finding until a person reads it.
The individual-entry-point sequences use the same requirement.

### Why is plan validation missing from this list?

The proposed `plan --check` pull-request workflow was to examine if work outside a plan predicts a later fix.
Fixing pull requests are necessary reference data.
The corpus of five repositories contains only six qualifying pairs.
The feature cannot be measured on that set and is not scheduled.

## Does Python syntax evidence stay the same across supported interpreters?

On 2026-10-02, the portability experiment compared the same 45 systemap source modules under Python 3.11 and 3.13.
The acceptance rule was recorded before execution.
It required zero canonical syntax hash mismatches between interpreters and zero changes to Python 3.11 hashes from before the work.
Comments and formatting edits had to leave hashes unchanged.
A function-body edit had to change the hash on each interpreter.

The original syntax hashes differed for all 45 modules.
Canonical hashes differed for zero modules.
Zero Python 3.11 hashes from before the work changed.
Formatting and comment edits gave zero mismatches on the two interpreters.
Each interpreter found the body edit.

This experiment examines syntax hash portability for this source set and these transformations.
It does not show that every future Python grammar change keeps the same representation.
`syntax_portability.py` records the acceptance rule and prints hashes and control results for repeated-run comparisons.
Run these commands from the repository root:

```sh
uv run --python 3.11 python bench/jev/syntax_portability.py > /tmp/syntax-311.json
uv run --python 3.13 python bench/jev/syntax_portability.py > /tmp/syntax-313.json
```

### Python 3.12 patch versions and f-string format specs (issue #126, 2026-11-02)

CPython 3.12.3 adds `Constant('')` at the end of a format spec that ends with a replacement field, for example `f"{x:<{width}}"`.
A spec that ends with text, for example `f"{x:{w}.{p}f}"` or `f"{x:{w}>}"`, gets no empty constant. CPython 3.11, 3.12.13 and 3.13 do not add it.
Ten spec shapes were parsed on 3.12.3 and 3.13 to find this rule. `SHAPES` in `tests/test_syntax_dump.py` records the result. Thus the source-review digest of such a module was different on 3.12.3.
The change removes each empty string constant from the parts of each f-string before the dump.

Acceptance, written before the run in the docstring of `fstring_digest.py`:

1. With the change, each file gives the same digest on 3.11, 3.12.3, 3.12.13 and 3.13.
2. On 3.11, 3.12.13 and 3.13, the change gives the earlier digest for 100% of the files.

Method: `fstring_digest.py` gives the digest with the change and the count of empty constants for each file.
The change removes exactly these constants, so a file gets a different digest if and only if the count is more than 0.
An earlier form of the script also gave the earlier digest directly. Its run gave the same result for each file.
The files are 443 Python files that Git tracks in this repository, 613 files of the 3.12.13 standard library without `test/`, `lib2to3/` and `site-packages/`, and three control files: 1,059 files.
The control files are the reproduction of the issue, five other format specs with replacement fields (four of them end with a replacement field), and three f-strings without one.
The interpreters are CPython 3.11.18, 3.12.3, 3.12.13 and 3.13.18. Each run uses `uv run --isolated --python VERSION`.

| Interpreter | Files | Files with `Constant('')`, which get a different digest |
|---|---|---|
| 3.11.18 | 1,056 | 0 |
| 3.12.3 | 1,059 | 2 |
| 3.12.13 | 1,059 | 0 |
| 3.13.18 | 1,059 | 0 |

3.11 does not parse 3 standard library files, so the comparison of the four interpreters uses 1,056 files.

Results:

- Acceptance 1 passes. With the change, the four interpreters give the same digest for each of the 1,056 files.
- Acceptance 2 passes. On 3.11, 3.12.13 and 3.13, the change gives the earlier digest for each file.
- On 3.12.3, the two control files with a replacement field in a format spec get a new digest. That digest is the digest of the other interpreters.
- No file of this repository or of the standard library has a format spec that ends with a replacement field.
  The standard library has format specs with replacement fields that end with text, for example in `fractions.py` and `locale.py`. 3.12.3 gives them no empty constant, so their digests do not change.
  A user on 3.12.3 gets new digests only for modules with a format spec that ends with a replacement field.

`tests/test_syntax_dump.py` makes the 3.12.3 tree from the parsed tree. Thus the test gives the same result on each interpreter in CI.
The test also passed with `uv run --isolated` on 3.12.3, 3.12.13 and 3.13. With the `extract.py` of the base commit, 8 tests of `test_syntax_dump.py` and `test_parse_once.py` fail.

Time of the dump. Acceptance, written before the run: the change costs at most 5% more total time of `_dump_python_syntax` over the 443 tracked files, median of 5 rounds.
The rounds alternate between the dump of the base commit and the dump of the change, on 3.11.18, after one round to fill the walk cache.
In 3 runs, the median times were 1.064, 1.028 and 1.046 s for the base commit and 1.078, 1.049 and 1.073 s for the change: 1.014, 1.020 and 1.025 times. The acceptance passes.
The first form of the change built a new list for each f-string. It took 1.030 and 1.066 times the base time. Thus the change now examines the parts first and makes a list only for an f-string with an empty constant.
The time on 3.12 and 3.13 is not measured.

### Facts that also change with the interpreter

The review of this change found two other values that depend on the interpreter. They are not in the source-review digest, and this change does not correct them.
An extraction of this repository on 3.11.18, 3.12.3 and 3.13.18 gave these differences in `docs/map/map.json`:

- On 3.13, the `api` fingerprints of 81 modules are different. They use `ast.dump` without `show_empty`, and 3.13 does not write empty lists by default.
- On 3.12.3, the `constants` previews of 2 modules are different. They use `ast.unparse`, and 3.12.3 writes the quotes of an f-string differently from 3.11. Other 3.12 versions are not measured.

`systemap extract --check` compares these stored facts. Thus a person who extracts on a different interpreter from CI can get a stale result. This needs its own issue.

### Stored syntax values on five interpreters (issue #136, 2026-11-04)

Issue 136 replaces `ast.dump` and `ast.unparse` for each stored value.
The syntax digest and the `api` fingerprints come from the syntax text of systemap (`src/systemap/syntax_text.py`).
The signatures, the `constants` previews and the class bases come from the source text (`src/systemap/source_segment.py`).
An earlier attempt (branch `claude/issue-136`) changed the output of `ast.unparse` for each version. On Python 3.14.6 it stopped with `UnparseError`. This change does not use that method.

Acceptance, written before the first run in the docstring of `stored_syntax.py`:

- (a) With the change, CPython 3.11.18, 3.12.3, 3.12.13, 3.13.18 and 3.14.6 give the same stored values. The repository comparison uses the full `components` section. 0 values differ.
- (b) The extraction time of this repository with the change is at most 1.10 times the time of main. The value is the median of 5 alternating runs on 3.11.18, each in a new process.
- (c) No acceptance value. The script counts the stored values that change one time for a user on each interpreter.

Method: `stored_syntax.py drive` starts each run with `uv run --isolated --python VERSION --project CHECKOUT`.
The repository is a copy of main at 231993f: 178 modules.
The standard library is the 613 files of 3.12.13 without `test/`, `lib2to3/` and `site-packages/`. 3.11 does not parse 3 of them, so the comparison uses 610 files.
The stored values of the 178 modules are 178 syntax digests, 3,821 fingerprints, 664 previews and 1,211 signatures.
The stored values of the 610 files are 610 syntax digests, 7,516 fingerprints, 734 previews and 8,345 signatures.

Main was measured first. The table gives the values of main that are different from the values of main on 3.11.18:

| Interpreter | Modules with a different record | Repository values | Standard library values |
|---|---|---|---|
| 3.12.3 | 2 (`constants`) | 2 previews | 1 preview |
| 3.12.13 | 0 | 0 | 0 |
| 3.13.18 | 81 (`api`) | 193 fingerprints | 672 fingerprints |
| 3.14.6 | 81 (`api`) | 193 fingerprints | 672 fingerprints |

Results with the change:

- Acceptance (a) passes. Each of the five interpreters gives the same `components` section and the same values for the 610 files. 0 values differ.
- Acceptance (b) passes. The median times were 3.083 s for main and 3.126 s for the change: 1.014 times.
  Runs of main: 3.1918, 2.8778, 3.1557, 3.0443, 3.0825 s. Runs of the change: 3.0470, 3.0020, 3.1513, 3.1262, 3.1340 s.
  A control run of main against main before the change gave 0.976 times.
  A first run of the change gave 0.997 times (main 3.174 s, change 3.166 s). After that run, two functions were divided to keep the cognitive complexity at 15 or less. The run above is of the final code, and its other results are the same as in the first run.
- (c) The values that change one time for a user (main on an interpreter against the change on the same interpreter):

| Interpreter | Repository: digests, fingerprints, previews, signatures | Standard library: digests, fingerprints, previews, signatures |
|---|---|---|
| 3.11.18 | 178, 1,179, 476, 44 | 610, 4,014, 196, 79 |
| 3.12.3 | 178, 1,179, 476, 44 | 610, 4,014, 196, 79 |
| 3.12.13 | 178, 1,179, 476, 44 | 610, 4,014, 196, 79 |
| 3.13.18 | 178, 1,026, 476, 44 | 610, 3,361, 196, 79 |
| 3.14.6 | 178, 1,026, 476, 44 | 610, 3,361, 196, 79 |

Each syntax digest changes, because the syntax text does not write empty lists. Thus each recorded source review of a Python module is stale one time after the upgrade.
A preview or a signature changes when the source text is different from the `ast.unparse` text, for example a string in double quotes.
The format of the facts file is now 14, so `extract --check` marks a format 13 file stale.

Run from the repository root:

```sh
uv run python bench/jev/stored_syntax.py drive MAIN CHANGE TARGET LISTING OUT
```


## Flow selection measurements

The measurement plan specified these necessary results before browser measurements on 2026-10-05.
`Structure` must show zero flow lines after component selection.
Other layers must show only flows connected to the selected component.
Only a selected flow has the selection line width.

Without a preview, flow selection and each sequence step must show one flow line and one flow label.
The selected label must have zero overlaps with component text or other flow labels.
The map viewport must contain the full selected endpoint cards.

The inspector must give access to each connected flow, with its direction and evidence state.
A preview must cause zero changes to inspector contents or camera position.

The Node test script gives results for browser procedures and map selection.
Browser measurements give the positions and dimensions of map items for desktop and phone views.
These checks do not measure screen-reader speech or user comprehension.

The first test subset gave 46 satisfactory results and six failures.
Three tests used the previous rendered map and gave failures.
Three corrected style assertions agreed with the preview condition.
A subsequent subset gave ten satisfactory results and did not include one test of the previous map.

The first full test suite gave 547 satisfactory results, one `skipped` result, one `failed` result, and four errors.
The tests with failures used the removed wheel controls.
The corrected tests kept all requirements for evidence state, source references, dash patterns, and keyboard focus.
The repaired subset gave seven satisfactory results.
The next full test suite gave 552 satisfactory results and one `skipped` result.

The first browser measurements found zero label overlaps, zero endpoint cards with clipping, and zero horizontal page overflows in 92 sequence step views.
The measurements also found an error during a sequence change.
A layer change could open the previous component inspector before the sequence cleared its selection.
The corrected sequence code clears selection before the layer change.
In a regression test, the sequence closes the previous inspector and End restores the previous selection and camera.

The last browser measurements examined all 46 steps in all 11 sequences at 1280 by 720 and 390 by 844 pixels.
All 92 views showed one flow line and its label.
There were zero overlaps with component text or other flow labels.
There were zero endpoint cards with clipping and zero horizontal page overflows.

Selection of `Check` showed zero flows in `Structure` and six connected flows in `Data flow` on desktop and phone.
`All` showed all 76 flow lines with no labels until selection or preview.
A desktop keyboard preview caused zero changes to the inspector contents or camera.

The last full test suite gave 553 satisfactory results and one `skipped` result.
The pre-commit checks, mypy, map check, and `systemap judgement --strict` gave satisfactory results.
The map check recorded component assignments for all 53 source modules.
The `systemap judgement --strict` command recorded seven decisions with recorded answers and no necessary decision.
No test or map command sent a Jev request.

The commit check found cognitive complexity of 18 in the new flow group test.
The limit for new functions is 15.
The correction moved the group assertions to a different function and kept each assertion.

The static design check gave three warnings: map canvas padding, type hierarchy, and the Paper palette.
The map canvas has map controls, and the palette is a previous color selection.
These warnings do not measure flow visibility or browser text overlaps.
The three appearance images use 1280 by 720 pixels.
The updated tour shows 12 frames in 30 seconds.

## Card width measurements (2026-10-06)

The measurement plan specified these necessary results before the card width measurements.
All text must stay between the horizontal card margins of 10 units.
The vertical card bounds must contain all text.
The cards must contain the full descriptions and keep their previous dimensions.
The minimum `font-size` must be 11px.

The browser baseline found one text overflow in 40 card text lines.
The `Describe` description had a width of 145.795 units.
The description had an overflow of 5.795 units at the card border.

The correction uses ArialMT version `5.01.2x` and the [Liberation Sans 2.1.5 release](https://github.com/liberationfonts/liberation-fonts/releases/tag/2.1.5).
The font measurements found equal advances for all 95 printable ASCII characters.
The description style uses `font-weight:400`, `font-kerning:none`, and `font-variant-ligatures:none`.
The width table includes measured overhangs for the two sides of each glyph.
The origin correction is the smallest multiple of 0.1 units that is not less than the measured left overhang.
The `Describe` description uses two lines: `The diagram` and `measurements`.

The CoreText measurements found zero text overflows in 41 lines.
The browser measurements examined all 20 cards and 41 text lines in three schemes at 1600 by 900 and 390 by 844 pixels.
The six views supplied 246 line measurements.
There were zero margin failures and zero vertical failures.

The first full test suite after the correction gave 564 satisfactory results, five `failed` results, and one `skipped` result.
All five failures occurred at the `Sidebar` description in the placement fixture.
Its width was 130.25439453125 units, more than the limit of 130 units.
The corrected fixture uses `The add-in interface`, with a width of 97.83447265625 units.
All 15 placement tests then gave satisfactory results.

Six GitHub CI jobs gave failures because the PNG screenshots used 1280 by 720 pixels.
The screenshot tests specified dimensions of 1600 by 900 pixels.
The corrected PNG screenshots use 1600 by 900 pixels.
The tour keeps its 12 frames and 30-second time.
All five screenshot tests then gave satisfactory results.

The width table contains measurements for only the 95 printable ASCII characters in the two specified fonts.
Measurements for other fonts and glyphs are necessary.
For a description character with no measurement, `card_text` gives no description lines.
It gives one diagnostic for each different character: `card {cid}: description width is not measured for character {char!r}`.
The previous dimension diagnostics keep their identifiers for measured descriptions.

All 21 tests in the first card subset gave satisfactory results.
A source review by a different agent then found that Unicode spaces gave no character diagnostic.
The source code removed these characters before it measured the description width.
The correction uses the full description for the character diagnostic.
New test inputs include Unicode spaces `U+00A0` and `U+2003`.
Other test inputs include ASCII separator controls.

The ASCII separator controls `\t`, `\n`, and `\r` keep their previous word separation.
The code replaces these controls with ASCII spaces before it calculates widths.
The controls `\v` and `\f` give character diagnostics.

The last full test suite gave 578 satisfactory results and one disabled test in 95.14 seconds.
All 29 card text tests gave satisfactory results.
The last source review found no remaining defects.

The map check and `systemap judgement --strict` gave satisfactory results.
All 53 source modules have component assignments in a map with 20 components and 76 flows.
The map check found zero flow paths through components or regions that contain no endpoint of the flow.
The minimum `font-size` is 11px.
The `systemap judgement --strict` command recorded seven decisions and no necessary decision.
Mypy found no errors in 53 source files.

The previous pre-commit checks gave satisfactory results.
The last pre-commit checks gave satisfactory results after the document changes.

## Theme contrast measurements (2026-10-06)

Acceptance: each text color must give a contrast ratio of at least 4.5:1 on each page surface.
The probe also measures the actor description on its calculated fill.
The probe measures 64 color pairs for each palette.

| Theme | Minimum ratio | Text | Surface |
|---|---:|---|---|
| Dark | 5.8425:1 | Error text | Raised surface |
| Light | 5.0752:1 | Tools layer | Raised surface |
| Clay | 5.3692:1 | Actor description | Actor fill |

The initial probe passed for all three palettes.
These measurements do not show border visibility or user comprehension.

The first test subset gave 47 passes and five failures.
Two failures used an incorrect theme list or the previous generated page.
Three failures used the previous focus stroke width.
The corrections update the assertions and the generated page.

The second test subset gave 49 passes and three failures.
The failures used the previous flow preview width.
After correction, the test subset gave 58 passes.

The first preview command failed with `ModuleNotFoundError: No module named 'scripts'`.
The same command with the repository in `PYTHONPATH` started the preview server.

The first map check reported seven stale records after later source and test changes.
The refresh updates these records before the final map check.

The first full test suite gave 582 passes, two failures, and one skipped test.
One assertion used the removed `WARM_GROUND` symbol.
The other failure found duplicate glossary rows through a skill symlink.
The corrections use the Dark background and one copy of each glossary row.

At a 390-pixel viewport, the document width was 390 pixels.
The theme, layer, zoom, and view controls had a height of 44 pixels.

The final test suite gave 584 passes and one skipped test.
The pre-commit checks passed. The mypy check found no errors in 53 source files.
The map check found no layout errors and mapped all 53 source modules.
Judgement reported 14 items for maintainer decisions.
The source reviews for six Page flows remain pending after the source change.

The image command wrote all three theme images and 12 tour frames.
The tour GIF was 1.33 MiB at a width of 1200 pixels.

## Isometric page measurements (2026-10-06)

Acceptance: the page projection must keep all 20 components and 76 flows.
Component captions must not overlap or extend beyond the map area.
Both transformed text axes must agree with the original axes within 1e-12.
The camera must contain selected plates, endpoints, and flow paths.

The initial candidate kept all 20 components and 76 flows.
Browser measurements found zero caption overlaps and zero clipped captions.
At a 390-pixel viewport, the document width was 390 pixels.
All 20 captions stayed separate and inside the map area.
The theme and layer controls had a height of 44 pixels.

The first test subset gave 34 passes and five failures.
Four camera assertions used the previous coordinate plane.
One nested-map assertion used the previous SVG attribute order.
The corrected camera harness applies the projection to the four rectangle corners.
The second subset gave 38 passes and one failure.
The remaining assertion used the previous header markup.
The correction uses the new project name element.

The projection tests gave two passes.
The first full test suite gave 586 passes and one skipped test.
The first pre-commit command formatted one file and reported that change as a failure.
The first Ruff command found 13 long source lines.
A separate Ruff command found a missing `strict` argument for `zip()` in a new test.
The corrections divide the long lines and specify `strict=False`.
Complexipy measured a maximum cognitive complexity of six in the changed style module.
The acceptance limit was 15.

Source reads failed for `schematic_nodes.py`, `schematic_shapes.py`, and `page_camera.py`.
These files do not exist.
The source inspection used the actual card, style, and script modules after file discovery.
The GitHub browser tool could not read the package directory.
The Hairline design page and the previously retrieved source CSS supplied the reference.

The browser showed an unwanted focus outline around the projected component group.
The correction removes that outline and keeps the accent stroke for keyboard focus.

The final test suite gave 586 passes and one skipped test.
The final pre-commit checks passed.
Mypy found no errors in 53 source files.
The map check mapped all 53 source modules and found no layout errors.
The map check examines the authored plane.
Browser measurements examine the page with its isometric projection.

Sequence navigation changed the selected step from one to two.
Text view kept the selected sequence and step.
The first browser selection failed because the control name was `Next step`, not `Next`.
The corrected selection used the control name from the accessibility tree.

The image command wrote three theme images and 12 tour frames.
All three theme images were 1600 by 900 pixels.
The tour GIF was 1200 by 1140 pixels, with 12 frames and 919435 bytes.
The first image probe failed because `PIL` was absent.
The same probe with Pillow supplied through `uv --with pillow` gave the image dimensions and frame count.

The dictionary command with `--help` failed because it treated the option as a file path.
The source file and skill instructions supplied the supported command form.
The format check found two unformatted number literals in the new projection test.
Ruff formatted them. The projection tests then gave two passes.
The tour image read failed at the temporary root because the image was in the `frames` directory.
The image read from that directory succeeded.

The last render and projection subset gave eight passes after the accessible label correction.
A later pre-commit command reported file changes during two hooks.
A map refresh operated at the same time.
The repeated pre-commit command after the refresh passed.

Judgement reported 22 items for maintainer decisions.
Source changes made 13 flow reviews pending for the Page and Schematic components.
The source claims and recorded review decisions keep their previous contents.
The language examination corrected the new paragraphs and ordinary words.
The document checker also reported errors in existing design text and technical identities.
This result does not give language acceptance for the complete design document.

## Map workspace acceptance (2026-10-06)

The page must show Components and Sequences controls in its initial viewport.
The page must use Flat as its initial map view.
Flat and Isometric must preserve every component, flow, selected item, and sequence step.
The transition must end at the specified matrix and stop immediately with reduced motion.
Visible component text must have a minimum font size of 12 CSS pixels.
Visible component names must not overlap at desktop and phone widths.
At 390 pixels, the document must have no horizontal overflow.
The theme control must contain Dark, Light, and Clay.
Reference must give access to source rules and review records.

The first workspace probe replaced the page heading with the project title.
Components and Sequences use one navigation panel.
At a 1280-pixel viewport, the document width was 1280 pixels.
The projected plate widths were between 79.6396 and 84.5658 pixels.
This width measurement requires a different text layout for the isometric view.

The requested `~/.claude/WRITING.md` file was absent.
Source reads also failed for `map/components.py` and `schematic_draw.py`.
File discovery found the model in `map/model.py` and card output in `schematic.py`.

The first workspace subset gave 26 passes and 15 failures.
Theme tests still required the removed native selector. The correction tests the three Theme buttons.
The first complete suite gave 563 passes, 15 failures, eight errors, and one skipped test.
The navigation tests still required the removed header links and project-title span.
The updated navigation subset gave 56 passes.

A phone list remained open after Close list.
The event handler also matched the body element and reopened the list for each click.
The correction restricts the handler to navigation buttons.
The phone sequence probe then showed the controls and current step above the map.

The initial region overview had an external label outside the viewport and one overlapping label pair.
The label placement correction gave zero overlapping pairs and zero labels outside the viewport.
At 390 pixels, the document width was 390 pixels.

One edit command failed with an unterminated string literal before it changed files.
A subsequent patch applied the specified edits.
A source read failed for `schematic_view.py`. The camera implementation is in `schematic_script.py`.

The first projection control test failed its camera acceptance value.
The DOM test harness kept a stale viewBox object after projection changes.
The harness now supplies a live viewBox object, as the browser does.
The repeated projection test gave three passes.
It confirms exact state, exact matrices, intermediate animation frames, immediate reduced motion, and restored camera coordinates.
The coordinate acceptance value was 1e-6 units.

The first workspace pre-commit command corrected one import and found two long CSS lines.
The source correction divides those CSS lines.
The desktop browser probe at 1280 pixels showed all 20 component names without overlap.
The document width was 1280 pixels.
Two font probes failed because the browser read interface does not expose parseFloat or getScreenCTM.
The subsequent probe read font sizes, viewport bounds, camera scale, and the viewBox from the DOM.

The full suite after the control corrections gave 587 passes and one skipped test.
Mypy found no errors in 54 source files.
The computed-style font probe gave 11.99998 CSS pixels after the viewport scale.
The font control specifies 12 CSS pixels. The computed-style text contains rounded values.
A broader text probe found two overlaps between region headings and component names.
The heading correction moves a region heading above text that intersects it.
Six long JavaScript source lines failed Ruff. The correction divides those lines.

The desktop Flat and Isometric probes then found zero overlaps between visible text elements.
The phone isometric sequence probe initially showed region summaries instead of the selected step participants.
The correction gives the selected components and sequence participants their own text space at small scales.
The phone probe then showed the Agent, CLI, their functions, and the commands flow.
The document width stayed at 390 pixels. The sequence list closed after selection.
The control and projection subset gave 46 passes after this correction.
A later Ruff command found two long JavaScript lines. The source correction divides them.

A later font correction reads the displayed camera scale during camera animation.
Its first test gave 21 passes, 14 failures, and 11 errors because the initial view had no transform attribute.
The correction permits that initial condition. The repeated subset gave 46 passes.
The image command made three theme images, a sequence image, and a 12-frame tour.
A subsequent image command used four independent Chrome profiles for the same capture procedure.
All captures completed. The images include the new heading and sequence controls.
The language examination found that upper and act are not approved for the new caption.
The caption now refers to plate height and sequence roles.
The glossary defines acting components and measurement components from their schema fields.

## Generated map information acceptance (2026-10-07)

The map information must use the current model and stored source records.
The information must show module counts, entry points, and flow evidence without repository-specific values.
A selected component must show its function and source counts below the diagram.
A selected flow must show its artifact, direction, and evidence state.
An active sequence must show its acting and measurement components.
Region summaries must show component and flow counts.
Maps without authored regions must retain access to every component at small scales.
At 390 pixels, the document must have no horizontal overflow.
Visible text must retain the previous 12-pixel and zero-overlap acceptance values.

The final subset command failed because `tests/test_view.py` does not exist.
File discovery found `tests/test_view_state.py`.
The corrected subset gave 46 passes. The complete pre-commit command passed.
The phone external group probe showed all four external components within the viewport.
The document width and scroll width were both 390 pixels.

The first test without regions removed the container assignment as well as the region assignment.
Its routing command failed for `Ledger -> Parser`.
The corrected fixture retains a container for every component.
A subsequent test called the absent `Model.validate_layout` method and failed before rendering.
The correction uses `Model.layout_problems`.
Both repository fixtures then passed their data and control tests.

The phone sequence probe found labels outside the viewport after the projection change.
The correction frames the step participants throughout the projection transition.
It also keeps their text within the viewport and hides unrelated diagram boundaries at small scales.
The repeated probe found zero overlapping text pairs and zero clipped text elements.
The document width and scroll width were both 390 pixels.
The diagram occupied 464 pixels of the 844-pixel phone viewport.
Previous and Next stay above the diagram. The step sentence follows the diagram on phones.
The isometric legend names acting and measurement components from the current step.

The complete suite gave 589 passes and one skipped test in 77.92 seconds.
The subsequent data, projection, and relationship subset gave 13 passes.
The explicit pre-commit command for the new files passed.
The required `~/.claude/WRITING.md` file remains absent.
The language examination uses the available official ASD-STE100 reference and project glossary.

The first phone export contained cropped controls because the Chrome window exceeded the requested image width.
The export now gives the document a width of 390 pixels.
The browser probe uses the native 390-pixel viewport without that export style.
The complete PNG images have their final IEND records.
Dark contains 142428 bytes. Light contains 129515 bytes. Clay contains 143574 bytes.
The sequence image contains 216790 bytes. The phone image contains 46299 bytes.
The tour contains 1018503 bytes and 12 frames at 1200 pixels wide.

The final desktop layout reserves space for map information in the first viewport.
At 1280 by 900 pixels, the diagram height was 605.4609375 pixels.
The map information ended at 844.03125 pixels.
The first font probe failed because the initial camera had no transform attribute.
The repeated probe permits that initial condition.
It found all 20 component names, zero text overlaps, and no horizontal overflow.
The computed-style font value was 11.999992057567534 pixels after scale conversion.
The font control specifies 12 pixels. Computed-style values contain rounded text.
The Isometric probe also found all 20 names and zero text overlaps.

The inspection test now requires component information during an active sequence.
The source correction prevents the current sequence flow from replacing the inspected component information.
The data, projection, camera, and relationship subset gave 16 passes before that correction.
The drawable area, projection, data, and image subset gave 19 passes after that correction.
The language examination corrected paragraph length and ordinary words in the new design text.
The remaining word-list results refer to glossary terms and interface labels.

The complete staged pre-commit command passed every applicable hook.
A subsequent complete test suite gave 588 passes, one failure, and one skipped test.
The reduced-motion test counted three camera events instead of two.
Map information used a camera event to request text placement after a layout change.
The correction uses the existing layout event and keeps camera events for camera changes.
The page now shows the diagram before a projection change from Text view.
Text placement ignores a hidden diagram.

The theme audit found that a configured Clay palette replaced the device theme on a first visit.
The correction uses Dark or Light from the device preference before a saved selection exists.
The CSS default also uses Dark. Its media rule supplies Light without JavaScript.
The figure palette keeps its configured value.

The corrected keyboard, projection, theme, and information subset gave 45 passes.
The final complete suite gave 590 passes and one skipped test in 74.49 seconds.
The complete staged pre-commit command passed every applicable hook.
Mypy found no issues in 54 source files.
The refresh command updated the recorded map and figures.
The map check found coverage of 54 out of 54 modules, with no flow path or layout errors.
The judgement command reported 22 maintainer decisions and seven pending recorded answers.
The three skill directories had identical contents.
The browser showed the Isometric selection after a change from Text view.
The design text now states that reduced motion stops camera animation, not camera changes.

## Theme colour measurements (2026-10-11)

Acceptance: each pair of colors that can show on one view has CIEDE2000 25 or more with normal
vision and 12 or more with protanopia, deuteranopia and tritanopia (Brettel simulation). Text has
4.5:1 or more on each surface. Kind colors have 4.5:1 or more on the map. The limits were written
in each script before the run.

| Theme | data, control, context, tools | data, control, two custom kinds | five kinds |
|---|---|---|---|
| Ink | Pass, worst 12.9 deutan | Pass, worst 12.1 tritan | Fail, worst 17.9 normal |
| Paper | Pass, worst 25.1 normal | Fail, worst 23.6 normal | Fail, worst 7.2 protan |

In Ink, five kinds passed only with a context color of OKLCH chroma 0.16. The theme does not use it.
The first joint search failed the required sets. A second search ranked a failing color first.
The third search gave the values above.
Paper data has 4.24:1 on the raised surface. It shows there only as a line.

## Flow label size on the map page (2026-10-11)

Acceptance: a larger flow label size is acceptable only if the render of the self-map gives no
new label collisions and the count of labels away from their line does not increase.
The design boards show flow labels at 12px with the map at 88 percent: 13.6 SVG units.
The script renders the page with the label size, the label width for each character, and the
label height multiplied by one scale. A browser counts the collisions and the labels away from their line.

| Scale | Label size (units) | Label collisions | Labels away from their line (of 76) |
|---|---|---|---|
| 1.00 | 11.0 | 0 | 11 |
| 1.05 | 11.55 | 0 | 12 |
| 1.10 | 12.1 | 5 | 11 |
| 1.15 | 12.65 | 5 | 9 |
| 1.24 | 13.64 | 5 | 9 |

All larger sizes failed. The flow label size stays at 11 units.
At 1.10 and more, the collisions include 'settings' on CLI, 'uncovered entry points' on Judgement
and SecondOpinion, 'public surfaces' on ChangeDetector, and 'svg, detail' on Page.

## Card type size on the map page (2026-10-11)

Acceptance: a map uses a larger card type size only if the name and the description of all
cards fit in their cards at that size. The check budget at the base size does not change.
The boards show a 13px name and a 12px description with the map at 88 percent:
14.75 and 13.6 SVG units. `card_sizes` tries eight steps from that size down to the base size.
For the self-map, all 20 cards fit at the board size, and the page uses 14.75 and 13.6 units.

## Map page size (2026-10-11)

Acceptance: the sample page of `test_page_is_small_and_self_contained` is smaller than 300 KiB (307,200 bytes).
The new page has three views, the guide, the phone layout and the motion scripts.
The first build gave 352,977 bytes for the sample page. The test failed.
Two changes made the page smaller without a change to its behavior:

- The build removes comment lines, indentation and empty lines from each page script.
  The page scripts have no template literals, so no string continues on a second line.
- A page without a revision comparison gets a short Changes script that only sets the title.

| Page | Before | After |
|---|---|---|
| Sample page, no comparison | 352,977 | 301,050 |
| Self-map page, no comparison (`docs/map/index.html`) | 667,938 | 622,810 |
| Self-map page with a comparison, before the final model changes | 908,575 | 867,510 |

The sample page passes with 6,150 bytes of space. A small addition to the page scripts can exceed the limit again.
All 14 board states rendered in Chromium after the change with no page error.

## CI failures on the map page change (2026-10-11)

Acceptance: every CI job passes on the pull request head.

- Run 96 failed 12 tests on Windows. The tests read and wrote the page with the platform encoding
  (cp1252). The new page contains characters that cp1252 cannot decode, for example the arrows
  in the keyboard sheet (byte 0x90 of U+2190). The tests now read and write files, and decode Node
  output, as UTF-8. The source code already wrote UTF-8.
- Run 96 also failed the strict judgement, delta and install jobs. Seven answers had old evidence
  digests, and Schematic, Page and Figures had changed source with no new source review.
  The claims were examined again, one description was corrected, and the digests were recorded.
- Run 97 passed all jobs except `test (macos-latest, 3.11)`. That job stopped before the tests:
  the download of `tree-sitter-typescript` 0.23.2 timed out three times. No test ran.
## Card depth and pan speed (2026-10-11)

Acceptance: the card depth and glow effects may add at most 20 percent to the mean frame time
of a 120-frame pan and zoom in the All layer with a selected card.
A Playwright script sets a new camera transform in each animation frame. It measures the frame
interval in headless Chromium, which draws with software rendering. Each page ran twice, with the
effects and with a style rule `*{filter:none!important}`. The first 5 frames are not counted.

| Design | Run | With effects (mean / p95 ms) | Without filters (mean / p95 ms) |
|---|---|---|---|
| A blur shadow on every card | 1 | 34.64 / 66.7 | 30.58 / 50.0 |
| A blur shadow on every card | 2 | 43.19 / 83.4 | 32.46 / 50.1 |
| A shade shape under each card, a blur only on the selection | 1 | 28.26 / 50.0 | 26.81 / 50.0 |
| A shade shape under each card, a blur only on the selection | 2 | 28.55 / 50.0 | 30.00 / 50.0 |

The blur on every card failed the acceptance value in run 2 (33 percent). The shade shape passed.
The page uses the shade shape. Software rendering is slower than a GPU, so the absolute times
are not the times of a browser on a desktop computer.

## Which prompts have no measurement? (2026-10-11)

No new run was made. This section records the limits of the figures above for the shipped commands.

The shipped prompts are not the measured prompts.
The ASD-STE100 work changed the owner, sentence, flow, governs, triage, and move questions,
and the pair question of `suggest --jev`.
It also changed the text of the `none of these` and `not moved: deleted` options.
The tests keep the measured text to replay the recorded answers:
`HISTORICAL_QUESTIONS` in `tests/test_audit.py` and `HISTORICAL_BECAME_Q` in `tests/test_jev_moves.py`.
The `plan` question was not sent in a measurement. `plan_eval.py` uses the recorded triage answers.
All measured repositories are Python repositories. No result was measured on TypeScript.
A measurement is necessary before a figure in this README applies to the shipped prompts or to TypeScript.
The hints of `judgement` and `delta` give no figures. They say what each Jev feature does and how to stop the hint.

Test 8 measured delta followed by Jev picks at P>=0.8 as moves.
In the shipped `delta`, a pick is a `jev move` suggestion. It does not change the delta lines or the exit code.
The 16 correct picks of 17 thus measure the suggestions, not a change to the decisions.

The `possible mis-fold` word rule has two recorded values on 195 development cases.
`results/report.txt` gives 32%. The table in "Why was package ownership evidence rejected?" gives 61/195 (31%).
The two values come from different recorded runs.

The next section gives the method and the acceptance rule for a measurement of the shipped prompts.

## Do the shipped Jev prompts keep the measured results? (2026-10-11)

The method, the data, and the acceptance rule were written before the run.
The run was on 2026-10-11. All 674 answers came from the model `jev-1.13.0`, with 0 errors.

### Method

The test sends two question sets on the same rows and the same current maps.
Thus a difference between the two sets comes from the questions, not from the maps.

- The old set uses the measured questions in `build.py`, `build_flows.py`, and `build_meaning.py`.
  Its rows are the rows of these scripts, with no change.
- The shipped set has the same row ids, items, and labels.
  Its state and questions come from the shipped code: `audit.make_plan`, `audit.plan_governs`, and the triage values in `jev_cli`.
  `build_shipped.py` imports these builders. It does not copy question text.

`build_shipped.py` writes `data/holdout/<kind>_old.jsonl` and `data/holdout/<kind>_shipped.jsonl`.
The new names stop `run.py` from using the recorded answers in `results/holdout/<kind>.jsonl.gz`.
Those answers came from earlier maps. They stay unchanged.

Before it writes a kind, `build_shipped.py` does a check on each shipped question.
Each name in backticks must be in the state.
Each option in `needs` must be an option.
The shipped answer check, `jev.checked`, must accept a correct answer.
All shipped questions in the table below passed these checks.

A one-time check, not kept in the repository, ran `cmd_audit` and `cmd_triage` with an injected `send`.
The `send` function kept each request body and then refused the request. No request left the computer.
Each shipped row with the state of the shipped code was one of the requests of `cmd_audit`.
For a test report, `triage_ask` in `build_shipped.py` gave the same request as `cmd_triage`.

`score.py --arms` scores the two sets with the same functions.
It uses only the rows with an answer in the two sets, in the same order.
Thus the neighbour card of each mis-fold row is the same in the two sets.
It prints the two results line by line, and the acceptance result of each figure.
It also prints the number of answers that the shipped answer check refuses, and the model of each answer.
`run.py` now keeps the model name of each answer.

### Repositories

- systemap: this checkout at commit `6e4c6b1`. Its source tree is the same as at `5e5aac5`.
- httpie: a new first map of commit `2105caa49bae87c5809c274e407619a0de2639d1` (tag 3.2.4), in `bench/scratch/cli-first-map-20261011T201433Z`.
- scorecard: `../scorecard` is not on this computer. The set does not include it.
  `common.py` now writes a line for a holdout repository that is not available, and leaves it out.
  Before this change, `common.load` stopped with an error for that repository.

The httpie map had two runs of `bench/run.sh`:

1. `--ref 2105caa49bae87c5809c274e407619a0de2639d1` stopped before the session started. It did not write a line in `bench/results.jsonl`.
   The output was `fatal: Remote branch 2105caa49bae87c5809c274e407619a0de2639d1 not found in upstream origin`.
   A shallow clone with `--branch` accepts a branch or a tag, not a commit.
2. `--ref 3.2.4`, `--max-turns 120`, `--from /home/user/systemap` finished.
   The tag 3.2.4 is the same commit. The line in `bench/results.jsonl` gives this commit.

| Run | Turns | Minutes | Dollars | Model | systemap | Check | Judgement | Modules |
|---|---|---|---|---|---|---|---|---|
| 2026-09-19 (recorded) | 46 | 4.8 | 3.43 | claude-opus-5[1m] | 1.1.0 from the tag | clean | clean | 78 |
| 2026-10-11 (run 2) | 50 | 4.7 | 1.14 | claude-sonnet-5-5 | 1.2.0 from this checkout | clean | clean | 78 |

The default `--from` installs the tag v1.2.0. This branch is 66 commits after that tag, and the skill changed.
To make a current map, run 2 installed systemap from this checkout.
`bench/run.sh` does not set a model. The default model of the agent on this computer is different from the recorded run.
Thus the new httpie map is not the map of the recorded holdout results.
`systemap init` wrote `name = "repo"`, the name of the checkout directory, in the httpie configuration.
Before the Jev run, the coordinator changed it to `name = "httpie"` and made the shipped rows again.
The old rows did not change (a byte comparison). Thus the two sets send the same system name.

### Question counts

Each row is one request with one question. The input size is the number of JSON characters of the state and the questions (`jev.Ask.chars`).
The token counts come from the run.

| Kind | Old set | Shipped set | systemap | httpie | Median input characters (old, shipped) |
|---|---|---|---|---|---|
| owner (mis-fold and owner) | 80 | 80 | 40 | 40 | 4,620, 4,583 |
| sentence | 64 | 64 | 32 | 32 | 2,189, 2,180 |
| flowverify | 64 | 64 | 32 | 32 | 1,360, 1,372 |
| governs | 129 | 129 | 129 | 0 | 718, 700 |
| issues | not made | not made | | | |

The labels give these numbers of items:
owner 80 modules, and 79 of them have a neighbour card for the mis-fold figure.
Sentence 32 own and 32 sibling sentences. Flowverify 32 own and 32 different claims.
Governs 43 listed pairs and 86 other pairs.
With 32 items, one item is 3.1 points. With 79 items, one item is 1.3 points.

The issues rows were not made on this computer.
`gh pr list -R httpie/cli` stopped with `HTTP 403: GitHub GraphQL is not available from Claude Code sessions`.
The GitHub REST API also refused access to httpie/cli.
The issues rows need a computer where `gh` can read httpie/cli, and the httpie map in `bench/scratch`.

### Differences between the two sets

The shipped code sends some state in a different form. The shipped set uses the shipped form.

- owner and issues: the shipped state `system` is the configured name. After the change above, it is `systemap` and `httpie`, as in the old rows.
- flowverify: the shipped `code` lines come from `systemap.audit_code`, which also reads whole-module imports.
  18 of 64 rows (9 flows) have different lines. On these rows, the result includes the effect of the lines and of the question.
- governs: the shipped audit does not ask about a pair that `governs` lists.
  The 43 listed pairs have the same question form. `plan_governs` made them from a copy of the map without the `governs` lists.
  The httpie map has no invariants. Thus governs has rows from systemap only.
- sentence and flowverify: the shipped audit asks only about the sentence of the component and the claim of the flow.
  The sibling and different-claim rows use the shipped state with the sentence or the claim of the old row.
- mis-fold: the shipped audit refuses an answer without P(claimed component).
  `score.py` uses 0 for a missing probability, as in the earlier scores. The output gives the number of refused answers.
- owner: the shipped `jev owner` question goes only to modules without a component.
  The test uses modules with a component, because their labels are known. The earlier measurement did the same.
- issues: `systemap triage` cuts the report at 2,000 characters.
  The old reports have a title and at most 1,500 characters of text, so a cut occurs only with a long title.
- The holdout set has no rows for the move question of `delta`, the pair question of `suggest --jev`, or the plan question.
  This test does not include them.

### Acceptance rule

The rule applies to each kind at the threshold of the shipped code.
Each figure of the shipped set must be within 10 points of the same figure of the old set, on the same rows.
This is the rule of the holdout section.
For mis-fold, the false alarm rate of the shipped set must also be at most 2 points higher than the old set.

| Kind | Threshold | Figures |
|---|---|---|
| mis-fold, planted in a neighbour card | P<0.05 | caught, flagged (false alarm) |
| owner | confidence >= 0.9 | answered, right |
| sentence | P<0.2 | caught, flagged |
| flowverify | P<0.2 | caught, flagged |
| governs | P>=0.8 | found, suggested |
| issues | the first option | top-1 |

If a figure fails, the recorded figure does not apply to the shipped prompt of that kind.

### Commands

Run these commands in this checkout, because the httpie map is in `bench/scratch`.
Only `run.py` calls Jev. It must have `TYPESAFE_API_KEY`.
After the first Jev call, do not make the data again. The answers must agree with the rows.

    # Only on a computer where gh can read httpie/cli. No Jev call.
    JEV_SET=holdout uv run --project bench/jev python bench/jev/build_shipped.py issues
    # The Jev calls: 674 requests, and two for each issues row.
    JEV_SET=holdout uv run --project bench/jev python bench/jev/run.py owner_old owner_shipped sentence_old sentence_shipped flowverify_old flowverify_shipped governs_old governs_shipped
    JEV_SET=holdout uv run --project bench/jev python bench/jev/run.py issues_old issues_shipped
    # The scores of the two sets. No Jev call.
    JEV_SET=holdout uv run --project bench/jev python bench/jev/score.py --arms owner sentence flowverify governs issues > bench/jev/results/holdout/prompts-report.txt

The data for owner, sentence, flowverify, and governs is in `data/holdout/`. This command made it:

    JEV_SET=holdout uv run --project bench/jev python bench/jev/build_shipped.py owner sentence flowverify governs

### Results

`results/holdout/prompts-report.txt` has the full output. Issues were not measured.

| Figure | Old set | Shipped set | Points | Result |
|---|---|---|---|---|
| mis-fold, planted next door (P<0.05): caught | 82% | 82% | 0.0 | pass |
| mis-fold, planted next door (P<0.05): flagged | 1% | 4% | +2.5 | fail (limit +2) |
| owner (confidence >= 0.9): answered | 52% | 50% | -2.5 | pass |
| owner (confidence >= 0.9): right | 100% | 100% | 0.0 | pass |
| sentence (P<0.2): caught | 78% | 72% | -6.2 | pass |
| sentence (P<0.2): flagged | 0% | 0% | 0.0 | pass |
| flowverify (P<0.2): caught | 62% | 59% | -3.1 | pass |
| flowverify (P<0.2): flagged | 12% | 9% | -3.1 | pass |
| governs (P>=0.8): found | 16% | 7% | -9.3 | pass |
| governs (P>=0.8): suggested | 0% | 0% | 0.0 | pass |

Nine figures pass and one figure fails.
The mis-fold false alarm rate failed: 1 of 80 correct modules in the old set and 3 of 80 in the shipped set.
The difference is two modules. This set cannot show if the cause is the question or chance.
A larger set is necessary before the recorded mis-fold false alarm rate applies to the shipped prompt.
The mis-fold catch rate and the AUC did not change (AUC 0.980 and 0.977 next door, 0.990 and 0.989 at random).

Governs passed the rule, but the shipped question is weaker.
Its AUC went from 0.814 to 0.725, and the share of true pairs found at P>=0.8 went from 16% to 7%.
The governs rows come from systemap only (43 true pairs), and governs was already the weakest question.

The old-set figures are lower than the recorded holdout figures (for example, mis-fold caught next door 82% here and 93% recorded).
The maps are different: the httpie map is new and from a different model, scorecard is not included, and systemap has more modules.
Thus this run compares the two question sets. It does not repeat the recorded holdout measurement.

## TypeScript extraction time with a large node_modules directory (2026-10-11)

Acceptance: with 100,000 files in `node_modules`, `extract.build` takes at most 0.5 s more
than without `node_modules`. The fixture is the correctness shop project with 100,000 files
in 400 packages in `node_modules`. Half of the files are `.ts` files and none are empty.
Each line is three runs of `extract.build` in one Python process. Other processes can run on
the same computer, so the times are approximate. The profile is one more run under `cProfile`.

| Code | node_modules files | `extract.build` (s) | `collect_tests` (s) | `input_files` (s) |
|---|---|---|---|---|
| Before the change (017c6fa) | 100,000 | 3.100, 2.974, 2.992 | 3.866 | 2.281 |
| After the change | 100,000 | 0.053, 0.041, 0.052 | 0.007 | 0.011 (2 calls) |
| Before the change (017c6fa) | 0 | 0.080, 0.044, 0.052 | | |
| After the change | 0 | 0.056, 0.044, 0.046 | | |

`systemap extract --check` took 4.25 s before the change and 0.35 s after it (one run each,
`time`, with the 100,000 files). The change passed the acceptance value. The walks no longer
enter `node_modules`, and the tsconfig input walk starts at the fixed directory of each
`include` pattern. The fixture has 11 modules before the change and 10 after it, because a
file in `__tests__` is now a test file.

## Flow kind colors without blue or purple (2026-10-11)

The maintainer asked for no blue and no purple in the page.
The excluded band is OKLCH hue 180 to 350 degrees for a color with chroma 0.02 or more.
The band 195 to 335 lets through named cyan, aqua, teal (194.8) and turquoise (185.1),
and medium violet red (349.7), so the band is wider.

Acceptance (written before the runs): every pair of colors that can show on one view has
CIEDE2000 25 or more with normal vision and 12 or more with protanopia, deuteranopia and
tritanopia (Brettel). Each kind color has a contrast of 4.5:1 or more on the map and card, and
3:1 or more on the page, panel and raised colors. No kind hue is in the band. The Ink and Paper
hues of a kind differ by 20 degrees or less. Required view sets: data, control, context and
tools (set A) and data, control and custom 1 (set S) in both themes, data, control, custom 1
and custom 2 (set B) in Ink, and change, neutral line and selection (set CH).

A search in OKLCH found the values. The first Paper control value, `#855762`, has hue 4, which
is near pale violet red, and can look mauve. A second search kept the other values and changed
only Paper control to hue 20 to 43. It found 8 values that pass sets A and S. The page uses
`#A05B5A` (hue 21).

| Kind | Ink | Paper | Ink hue | Paper hue |
|---|---|---|---|---|
| data | `#2CB59A` | `#014438` | 176 | 176 |
| control | `#B97874` | `#A05B5A` | 23 | 21 |
| context | `#D1EC9F` | `#497B15` | 124 | 133 |
| tools | `#8A8708` | `#544002` | 108 | 88 |
| custom 1 | `#8A8B22` | `#493901` | 110 | 91 |
| custom 2 | `#DCE8B8` | `#3D7C23` | 119 | 138 |
| custom 3 | `#C6ED9F` | `#5C5C01` | 130 | 110 |
| custom 4 | `#7C9128` | `#71640B` | 120 | 100 |

| Theme | Set | Lowest pair | Value (limit) | Result |
|---|---|---|---|---|
| Ink | A | context / selection, deutan | 12.3 (12) | pass |
| Ink | B | data / custom 2, normal | 25.6 (25) | pass |
| Ink | S | custom 1 / neutral line, normal | 25.6 (25) | pass |
| Ink | CH | change / neutral line, protan | 12.1 (12) | pass |
| Ink | data, control, custom 3 | data / custom 3, normal | 24.5 (25) | fail |
| Paper | A | control / neutral line, normal | 25.4 (25) | pass |
| Paper | S | control / neutral line, normal | 25.4 (25) | pass |
| Paper | CH | change / neutral line, normal | 32.2 (25) | pass |
| Paper | B | control / custom 2, deutan | 10.5 (12) | fail |
| Paper | data, control, custom 4 | control / custom 4, tritan | 12.0 (12) | fail |

The lowest kind contrast on the map or card is 4.58:1 (Paper control on the map).
Five kinds on one view fail in both themes. Custom 1 is near tools (CIEDE2000 2.4 in Ink and 3.0
in Paper) and custom 2 is near context (6.4 and 3.1). Without blue, Ink has four color positions
that pass together, so the custom kinds repeat two standard kinds. The custom 3 and custom 4 hues
differ by 20.2 and 20.3 degrees between the themes, above the 20 degree limit.

Compared with the earlier palette: Ink still shows four kinds on one view. Paper still shows data,
control and one custom kind, and not a second custom kind. The first search value `#855762` passed
Paper set B. The page does not use it, because it can look mauve.

## Map page size with the new Map view (2026-10-11)

Acceptance: the sample page of `test_page_is_small_and_self_contained` stays smaller than 300 KiB (307,200 bytes).
Before this change, the sample page had 257 bytes of space. The new Map view needs more space.
The build now removes the comments, line breaks and indentation from the page styles, as it does for the page scripts.
A line break that does not follow a semicolon, a brace or a comma becomes one space.
In Chromium, the computed style of each of the 1,463 elements of the self-map page is the same with and without this step.
The comparison used Ink and Paper at 1440 pixels, and Ink at 800 and 390 pixels.

| Page | Bytes |
|---|---|
| Sample page, base (6e4c6b1) | 306,943 |
| Sample page, with compact styles (327dba0) | 302,873 |
| Sample page, with the new Map view | 306,145 |
| Self-map page, no comparison, base | 645,992 |
| Self-map page, no comparison, with the new Map view | 643,606 |

The sample page passes with 1,055 bytes of space. A small addition to the page can exceed the limit again.

## Map view pointer highlight and pan speed (2026-10-11)

Acceptance: the new Map view may add at most 20 percent to the mean frame time of the base page (6e4c6b1), in each state and in each run.
The new Map view has three changes that can occur during a pan: the pointer highlight gives low contrast to the cards that do not connect to the card under the pointer,
the card border has a transition, and the panel opens with the page.
The method is the method of "Card depth and pan speed": a new camera transform in each animation frame for 120 frames,
in the All layer of the self-map page at 1440 by 900 pixels in Ink. The first 5 frames are not counted.
There are two states: a selected card, and the pointer on the Page card with no selection.
The new page ran with the panel open, which is the default, and with the panel closed.

| Page | Run | Selected card (mean / p95 ms) | Pointer on a card (mean / p95 ms) |
|---|---|---|---|
| Base | 1 | 21.88 / 33.4 | 25.80 / 50.0 |
| Base | 2 | 20.29 / 33.4 | 25.22 / 50.0 |
| New, panel open | 1 | 23.19 / 33.4 | 24.20 / 50.0 |
| New, panel open | 2 | 23.19 / 33.4 | 24.06 / 33.4 |
| New, panel closed | 1 | 22.46 / 33.4 | 24.06 / 50.0 |
| New, panel closed | 2 | 20.58 / 33.4 | 22.75 / 50.0 |

The new page passed. The largest increase is 14.3 percent: the selected card with the panel open in run 2.
The differences between runs of one page are as large as the differences between the pages.
A drag of the map does not start the pointer highlight. The new effects use no filter.

## Paper theme surfaces and highlighter (2026-10-11)

The maintainer said that the Paper theme looked bad. Before the change, screenshots of all views in Ink and Paper
at 1440 by 900 and 390 by 844 pixels and these values of the base (9defc3d) showed the causes:

| Item | Paper on the base | Ink |
|---|---|---|
| OKLCH chroma of bg, surface, raised, map, card | 0.0098 to 0.0170, hue 86 to 91 | 0.0043 to 0.0088 |
| OKLCH hue of the highlighter `hl` | 92 (`#FFD33D`), the hue of the surfaces | no highlighter |
| Panel against map | panel darker than map (L 0.949 and 0.965) | map darker than panel |
| Map surface | dark grain at 6 percent, a brown dark edge | light grain, dark edge |
| Selection | ink ring, yellow glow, highlighter 11 px at 90 percent under an ink line | amber ring and glow |
| `ink_3` text on `hl` (a selected flow row in the panel) | 4.16:1 | not applicable |
| Paper data, tools and custom 1 kind colors | OKLCH L 0.35 to 0.38 | L 0.61 to 0.70 |

Acceptance (written before the runs):

- Each text token has 4.5:1 or more on bg, surface, raised, map and card, and where it shows on `hl` or `hl_soft`.
- `card_line`, `region` and `flow` have 3:1 or more on the map.
- The kind colors pass the limits of "Flow kind colors without blue or purple" on the new surfaces:
  the required sets A, S and CH, 4.5:1 on the map and card, 3:1 on bg, surface and raised, and no hue in the band.
- Each Paper kind color has 3:1 or more on the highlighter under a selected or current line.
- Ink does not change. The sample page stays smaller than 307,200 bytes.

The new Paper surfaces have an OKLCH chroma of 0.0028 to 0.0063 at hue 75 to 85.
The map is the toned sheet. The header, the row and the panel are lighter. A card is the lightest surface.
Paper has no grain, no dark edge and no glow. The card shade is ink at 8 percent.
A segmented control has the map color as its track, so the white selected segment shows on the white row.

| Token | Before | After |
|---|---|---|
| `bg` | `#ECE8DE` | `#F1EFEC` |
| `surface` | `#F1EEE6` | `#FCFAF7` |
| `raised` | `#E6E1D5` | `#EDEAE6` |
| `map` | `#F6F3EC` | `#F4F2EF` |
| `grid` | `#E6E1D6` | `#E6E3DF` |
| `card` | `#FFFEFB` | `#FFFEFC` |
| `card_line`, derived layers | `#8C877D` | `#8F8B85` |
| `region` | `#8F8A80` | `#8F8B85` |
| `line` | `#E0DBD0` | `#E4E2DF` |
| `line_2`, `ghost` line, containers | `#D3CDC0` | `#D4D1CD` |
| `ink_2`, `steel`, `good` | `#4B4740` | `#524F4A` |
| `ink_3`, `delta.tests` | `#686359` | `#6D6963` |
| `flow` (neutral line) | `#8F8C84` | `#8E8C85` |
| `on_accent` | `#F6F3EC` | `#FCFAF7` |
| `hl`, `hl_line` | `#FFD33D` | `#FFEBA0` |
| `hl_soft`, `accent_soft` | `#FFF1BF` | `#FFF5D6` |

The kind colors measurement is a copy of the script of the earlier measurement with the new Paper surfaces.

| Run | Change | Result |
|---|---|---|
| 1 | neutral line `#8D8A86` | Fail: sets A and S, control / neutral line, normal 23.8 (25) |
| 2 | neutral line `#8E8C85`, found by a search for 3:1 on the map and the set limits | Pass: A worst control / context, deutan 12.3; S worst control / neutral line, normal 25.7; CH 32.4 |
| 3 | highlighter `#FFEBA0` | The same sets. Lowest kind on the highlighter: control 4.26:1 |

With the highlighter `#FFE380` of run 2, `ink_3` had 4.30:1 on it. That failed the text limit, so run 3 uses a lighter yellow.
The lowest values after the change: text 4.55:1 (`ink_3` on raised), a kind color 4.54:1 (control on the map),
`flow` 3.01:1, `card_line` and `region` 3.03:1 on the map. The kind colors do not change.
Set B and the custom 3 and custom 4 hue differences (20.2 and 20.3 degrees) still fail, as before.
Paper data, tools and custom 1 stay dark. The earlier measurement found no passing set with Paper data at L 0.40 or more.
The Ink token tables of the page are the same before and after the change.

| Page | Before | After |
|---|---|---|
| Sample page (`test_page_is_small_and_self_contained`) | 306,145 | 305,750 |
| Self-map page, no comparison, scratch build | 644,811 | 644,416 |

These measurements do not show user comprehension.

## Map page size with the new header and the Find dialog (2026-10-11)

Acceptance: the sample page of `test_page_is_small_and_self_contained` stays smaller than 300 KiB (307,200 bytes).
This change removes Reference, the Text view, the More menu and the component index of the Find field.
It adds the header icons, the full-screen control and the Find dialog.
The self-map rows use the model and the facts of the shared checkout for both pages, so the two rows compare only the page code.

| Page | Bytes |
|---|---|
| Sample page, base (9defc3d) | 306,145 |
| Sample page, with the new header and the Find dialog | 301,610 |
| Self-map page, no comparison, base (9defc3d) | 653,205 |
| Self-map page, no comparison, with the new header and the Find dialog | 640,512 |

The sample page passes with 5,590 bytes of space.

## Sequences view: sequence button, line colors and phone step (2026-10-11)

Acceptance:

- Phone step: on screens of 390 x 844, 375 x 667, and 430 x 932 pixels, Previous and Next are on the screen
  without a scroll for each step of the self map. The space under them is 16 px, or the bottom safe area when that area is larger.
- Line colors: in Ink and Paper, with normal vision and with protanopia and deuteranopia simulations,
  the current step line is the line that is easiest to see. A line keeps the color of its flow kind.
- Page size: the sample page of `test_page_is_small_and_self_contained` stays smaller than 300 KiB (307,200 bytes).

### Phone step

Before the change, the map frame of a phone step had a fixed height of 340 px, and the step did not fill the screen.
The method: Chromium from Playwright, the self-map page from a scratch build, the Sequences view in Ink.
A script goes to each of the 46 steps of the 11 sequences. It reads the bounds of the map frame and of the row with Previous and Next.
The space is the distance from the bottom of that row to the bottom of the screen.

| Screen | Space before | Map frame before | Space after | Map frame after |
|---|---|---|---|---|
| 390 x 844 | 3 to 105 px | 340 px | 16 px | 327 to 429 px |
| 430 x 932 | 105 to 193 px | 340 px | 16 px | 429 to 517 px |
| 375 x 667 | Previous and Next below the screen for 46 of 46 steps, up to 178 px | 340 px | 2 to 16 px | 160 to 252 px |

The first change set a minimum of 180 px for the map frame. With it, 2 of the 46 steps put Previous and Next 18 px below
the 375 x 667 screen. That failed the acceptance value. A minimum of 160 px gives the values in the table.
For the longest step on 375 x 667, the space under the buttons is 2 px, and the page scrolls 14 px to show the bottom padding.
The page has no `viewport-fit=cover` in its viewport tag. Thus the bottom safe area is 0 in a browser now,
and the space is 16 px. With `viewport-fit=cover`, the safe area applies when it is larger than 16 px.

### Line colors

The method: screenshots of steps 1 and 4 of the sequence "Read the change history" at 1440 x 900 pixels.
Step 1 is a control flow, and step 4 is a data flow. A script applies the coloraide Brettel filter for protanopia
and deuteranopia, severity 1, in linear sRGB, to each color of a 500 x 360 pixel part of the map.
The examination of the images is visual. It is not a contrast measurement.

| Run | Values | Result |
|---|---|---|
| 1 | Ink. Under the current line: the `hl` token, 11 px, 0.9 opacity (16 percent amber). Current line 2.6 px. | Fail: the wider line under the current line is almost not visible |
| 2 | Ink. Under the line: accent at 0.3, 0.35, and 0.4 opacity, 10 to 12 px. Current line 2.6, 2.8, and 3.0 px. | Pass for each variant, in all three images. The values 0.3, 11 px, and 2.6 px are the smallest |
| 3 | After the merge of the Paper change: 12 px in both themes. Ink: accent at 0.3. Paper: `hl_line` `#FFEBA0` at full opacity | Pass in Ink and Paper, steps 1 and 4, in all three images |

The earlier steps have the rest width, 1.6 px, at full opacity. The later steps have the rest width at 40 percent opacity.

### Page size

| Page | Bytes |
|---|---|
| Sample page, base (9defc3d) | 306,145 |
| Sample page, base with the line rule | 304,154 |
| Sample page, base with the line rule and the sequence button | 306,815 |
| Sample page, codex/map-workspace with the Paper change (8e95034) | 305,750 |
| Sample page, this branch after the merge of 8e95034 | 306,599 |
| Self-map page, scratch build, 8e95034 | 652,810 |
| Self-map page, scratch build, this branch after the merge | 652,563 |
| Sample page, codex/map-workspace with the header and the Find dialog (6f6eb27) | 301,215 |
| Sample page, this branch after the merge of 6f6eb27, without the Sequences Full screen button | 301,615 |
| Self-map page, scratch build, 6f6eb27 | 637,789 |
| Self-map page, scratch build, this branch after the merge of 6f6eb27 | 637,093 |

After the merge of 6f6eb27, Previous and Next stay on the 375 x 667 screen for each of the 46 steps.
The sequence button needs about 2,300 bytes of script. The line rule removes the sequence arrowheads, the glow rules and the key
under the step list. The panel styles merge repeated declarations. After the merge of 8e95034, the sample page
passed with 601 bytes of space. After the merge of 6f6eb27, it passes with 5,585 bytes of space.

## Map page type (2026-10-11)

Acceptance: no text on the page is less than 11px, and running text is 12px or more.
Card descriptions and card names do not get wider than the measured widths.
The sample page of `test_page_is_small_and_self_contained` stays smaller than 300 KiB (307,200 bytes).

Method: Chromium 141.0.7390.37 (Playwright) at 1440 by 900 and 390 by 844 pixels, in Ink and Paper.
The audit read the computed style of each visible text element and the font that Chromium used
(DevTools protocol, `CSS.getPlatformFontsForNode`). The states were the Map view, a selected component,
a sequence step, Find, the keyboard keys, Text view, Reference, and the phone layout.
In this container, `system-ui` gives Inter, the monospace font is DejaVu Sans Mono, and Arial gives Liberation Sans 2.1.
fontTools 4.66.1 measured the font files. The font files came from the npm registry.

Results of the audit on the base page (9defc3d):

- At Fit, the zoom was 75 percent with the panel open. Flow labels, region labels, and container labels
  showed at 8.2 CSS pixels. Card names showed at 11 and card descriptions at 10.1. This change does not correct these sizes.
  A label box is 6.1 units for each character. At 11 units, Inter Medium is wider than the box for 2 of 70 labels,
  and Liberation Sans for 0. At 12 units, the counts are 10 and 2. Thus a larger label needs a new label width rule.
- The legend ACTS tag was 9px, and the other tags and the phone region labels were 10px.
- The Find match line and the flow ends in a group panel were 11px running text.
- The Read button was 14px, and the other header controls were 13px. The page body was 14px, and DESIGN.md gave 13px.
- The layer names in the guide steps used the monospace font.
- On the phone, a sequence step showed the 11-unit map text at 5.9 CSS pixels. This change does not correct it.

Width measurements:

- Arimo 400 and Liberation Sans have the same advances as the Arial table for all 95 characters, and no larger overhangs.
- For the card descriptions of the self-map and the sample, the total width relative to Arial is
  1.069 for Inter 4, 1.040 for Geist, 1.003 for IBM Plex Sans, 0.933 for Source Sans 3, and 1.133 for DejaVu Sans.
  With the Inter, Geist, or Source Sans 3 widths, one card gets a different number of lines. With DejaVu Sans, five cards do.
- DejaVu Sans Mono has 1233 of 2048 units (0.60205 em) for each character. The name advance was 0.602 em
  and is now 0.6021 em. JetBrains Mono, Geist Mono, IBM Plex Mono, and Liberation Mono have 0.600 em.

Embedded font sizes (WOFF2 bytes / base64 bytes). The subsets keep the kern and tnum features of a sans font.

| Font | Subset | WOFF2 | base64 |
|---|---|---|---|
| Inter 4 | Latin, weight 400 to 600 | 21,448 | 28,600 |
| Inter 4 | ASCII and 5 symbols, weight 400 to 600 | 13,316 | 17,756 |
| Inter 4 | ASCII and 5 symbols, weight 400 | 7,688 | 10,252 |
| IBM Plex Sans | Latin, weight 400 to 600 | 22,452 | 29,936 |
| IBM Plex Sans | ASCII and 5 symbols, weight 400 to 600 | 12,372 | 16,496 |
| Geist | Latin, weight 400 to 600 | 16,972 | 22,632 |
| Geist | ASCII and 5 symbols, weight 400 to 600 | 10,856 | 14,476 |
| Source Sans 3 | Latin, weight 400 to 600 | 17,784 | 23,712 |
| Source Sans 3 | ASCII and 5 symbols, weight 400 to 600 | 10,752 | 14,336 |
| JetBrains Mono | Name characters, weight 600 | 3,336 | 4,448 |
| JetBrains Mono | ASCII and 5 symbols, weight 400 to 600 | 8,044 | 10,728 |
| Geist Mono | Name characters, weight 600 | 3,512 | 4,684 |
| IBM Plex Mono | Name characters, weight 600 | 3,312 | 4,416 |

All seven fonts have the SIL Open Font License 1.1. IBM Plex has the Reserved Font Name "Plex",
and Source Sans 3 has "Source". A subset of these two fonts must have a different name.
Inter, JetBrains Mono, and Geist have no Reserved Font Name.

The page is 1,055 bytes under the limit, so the page uses only the fonts of the computer.
The change removes 28 bytes from each of the four sans font declarations and the `.hint` rule,
and adds `text-wrap-style` to the heading and paragraph rules.

| Page | Before | After |
|---|---|---|
| Sample page, no comparison | 306,145 | 306,048 |
| Self-map page, no comparison, with the same model | 653,205 | 653,108 |

A prepared option, which is not applied, embeds the Inter subset with the ASCII characters and 5 symbols,
weight 400 to 600, with the copyright and license URL records (17,916 base64 bytes).
With it, the sample page has 324,177 bytes, 16,977 bytes over the limit.
For each character, its description width table uses the larger advance of Inter and Arial.
This table is wider than the Arial table for 78 of 95 characters.
With this table, five placement tests failed, because the Config description of the workspace fixture
(49 characters) did not fit on two lines.

The new tests in `tests/test_typography.py` gave 6 failures and 1 pass on the base and 7 passes after the change.
The full test suite gave 767 passes and 1 skipped test.

## Map page size and time with the map changes in the Changes view (2026-10-12)

Acceptance: the sample page of `test_page_is_small_and_self_contained` stays smaller than 300 KiB (307,200 bytes).
The change adds the `#changes` link script to the page shell, and the map changes style rules and section to the Changes view.
The map changes section and the rules of a selected component are only in a page with a revision comparison.

| Page | Bytes |
|---|---|
| Sample page, base (bf3a3f8) | 301,986 |
| Sample page, with the `#changes` link | 302,425 |
| Sample page, with the map changes styles | 302,691 |
| Sample page, with the rules of a selected component | 302,692 |
| Self-map page, no comparison, base code | 636,231 |
| Self-map page, no comparison, new code | 636,937 |
| Self-map page, comparison with 9defc3d, base code | 915,195 |
| Self-map page, comparison with 9defc3d, new code | 917,834 |

The self-map rows use the model and the facts of the worktree for the base code and the new code,
so each pair compares only the page code. The self-map page contains the pages of its nested maps.
The sample page passes with 4,508 bytes of space.

The map comparison loads the committed model at the merge base for each render with `--base`.
For this repository against 9defc3d, two runs gave 0.19 s and 0.20 s for the map comparison,
and 1.09 s and 1.16 s for the source comparison that the page had before this change.

## Map page font (2026-10-12)

The maintainer decided to embed the font. This change puts a subset of Inter in the map page.

Acceptance:

- The page stays one file with no external requests. The font is a data URI in an `@font-face` rule.
- Map text with a measured width keeps its font, unless Inter fits the width rule for each character of the subset.
  Thus no card description wraps differently, and no placement result changes.
- At 1440, 1024, 800, and 390 pixels, no text in an HTML control gets more lines or becomes clipped.
- The sample page limit increases by the measured cost of the font and not more than 4 KiB of additional space.
  The limit is a whole number of KiB.

Method: Chromium 141.0.7390.37 (Playwright), Ink and Paper, 1440 by 900 and 390 by 844 pixels for the screenshots.
fontTools 4.66.1 with brotli 1.2.0 made and measured the fonts.
In this container, `system-ui` gives Inter 4.000 from the Debian package fonts-inter 4.0+ds-1.
SF Pro and Segoe UI are not available here. A measurement with these fonts is necessary.

### Source font

`scripts/inter_subset.py` downloads the npm package inter-ui 4.1.1 and compares its SHA-512 value with the recorded value.
It uses `package/variable/InterVariable.woff2`, "Version 4.001;git-9221beed3".
The earlier option used `inter-latin-opsz-normal.woff2` of @fontsource-variable/inter 5.3.0, "Version 4.001;git-66647c0bb".
The two files have the same ASCII advances at the weights 400, 500, 600, and 700.
They have the same `hhea` and `OS/2` typo metrics. Only `usWinAscent` and `usWinDescent` are different (2269 and 660 against 1984 and 494).
The fontsource file has no U+2190, U+2192, U+21C4, U+22EF, or U+2318.
Thus the subset of the earlier option had only the ASCII characters and U+00B7 (96 codes), not 5 symbols.

The page shows U+00B7, U+2192, and U+2212 in sans text. It shows U+2190, U+2191, U+2193, and U+2318 only in keyboard keys,
which use the monospace font. Inter has no U+21C4. The system sans font shows it.

The script did not give the same file two times at first: fontTools writes the current time in the `head` table.
The script now keeps the time of the source font. Three runs then gave the same SHA-256 value.

### Subset sizes

All rows use the optical size 14 and the name records 0, 1, 2, 5, 13, and 14, except the last row.
The name records 5 and 13 (version and license description) add 208 WOFF2 bytes.

| Characters | Weights | Features | WOFF2 bytes | base64 bytes |
|---|---|---|---|---|
| ASCII and 7 symbols | 400 to 700 | kern, tnum | 15,028 | 20,040 |
| ASCII and 7 symbols | 400 to 700 | kern | 14,292 | 19,056 |
| ASCII, U+00B7, U+2192, U+2212 (the page) | 400 to 700 | kern | 13,596 | 18,128 |
| ASCII, U+00B7, U+2192, U+2212 | 400 to 650 | kern | 13,312 | 17,752 |
| ASCII, U+00B7, U+2192, U+2212 | 400 to 600 | kern | 13,076 | 17,436 |
| ASCII and U+00B7, name records 0, 1, 2, and 14 | 400 to 600 | kern, tnum | 13,532 | 18,044 |

No page rule uses tabular figures, so the subset does not keep `tnum`.
The page uses the weights 400, 500, 600, and 650 in sans text. The weight axis goes to 700 for bold text.

### Width rules of the map

The values are the advances of Inter 4.001 at the optical size 14, for each of the 98 characters of the subset.

| Map text | Width rule | Inter | Characters wider than the rule | Largest |
|---|---|---|---|---|
| Flow label | 6.1 units for each character at 11 units | 500 | 65 of 98 | W, 11.03 |
| Flow label under a selection | 6.1 units at 11 units | 600 | 65 of 98 | W, 11.22 |
| Container description | 5.6 units at 11 units | 400 | 67 of 98 | W, 10.84 |
| Card description | the Arial table | 400 | 78 of 95 ASCII characters | |

The sum of the ASCII advances of Inter 400 is 1.066 times the sum of the Arial table.
Card names, region labels, and container labels use the monospace font. The monospace font does not change.
Thus flow labels and container descriptions keep the system sans font, and card descriptions keep Arial.
On the page, a rule sets `--fs` to the system sans font on these SVG text elements.

`CSS.getPlatformFontsForNode` gave these fonts on the self-map page after the change:

| Text | Font |
|---|---|
| Project name, view buttons, layer segments, Find, question, panel title, legend, sequence button | Inter Variable (embedded) |
| Step labels of a sequence on the map | Inter Variable (embedded) |
| Flow labels and container descriptions | Inter Medium and Inter (the system font in this container) |
| Card names, container labels, region labels, step numbers | DejaVu Sans Mono |
| Card descriptions | Liberation Sans |

At `DOMContentLoaded`, `document.fonts.status` was `loaded` and `document.fonts.check('13px "systemap Inter"')` was true.

### Fit of the controls

An audit read each visible element with its own text in 10 states at 1440, 1024, 800, and 390 pixels:
the Map view, the All layer, a selected component, a selected flow, Find, the keyboard keys, the source panel of the commit,
the sequence list, a sequence step, and the first-visit guide.
Before and after the change, the audit found the same 2,467 elements.
No element got more lines. No element became clipped.
The 278 clipped boxes before and after are the same: screen reader text and rows with an ellipsis.
These rows are in Find, in the sequence list, and in the group list.
The canvas text widths of the view buttons, the layer segments, and Find were the same before and after.
In this container the base page also used Inter widths, because `system-ui` gives Inter 4.000.

The layout boxes of the text were the same before and after, at device scales of 1 and 2.
At a device scale of 1, the glyphs in the screenshots were on the same pixel rows.
At a device scale of 2, the 13px text of the panel was 2 device pixels lower. The 19px title and the Clear button did not move.
The installed font has CFF outlines with hint values. The subset has TrueType outlines and no hint tables.
The difference is probably in how the renderer aligns hinted glyphs. A comparison with SF Pro on a macOS screen is necessary.

### Page size

| Page | Before (f70c3e8) | After |
|---|---|---|
| Sample page, no comparison | 301,519 | 319,971 |
| Self-map page, no comparison, scratch build | 637,718 | 656,170 |

The font costs 18,452 bytes on each page: 18,256 bytes for the `@font-face` rule, 68 bytes for the font name in the four
`--fs` values, and 128 bytes for the rule of the map text with a measured width.
The limit of `test_page_is_small_and_self_contained` was 300 KiB (307,200 bytes). It is now 322 KiB (329,728 bytes).
The limit increases by 22,528 bytes: the font cost and 4,076 bytes of additional space.
The sample page passes with 9,757 bytes of space.

The new tests in `tests/test_typography.py` gave 3 failures and 15 passes on the base with only `page_font.py`
and the license file added, and 18 passes after the change.
The full test suite gave 790 passes and 1 skipped test.

After the merge with the map changes in the Changes view, the sample page is 321,144 bytes.
It passes with 8,584 bytes of space.

## Map text at Fit (2026-10-11)

"Map page type" found that at Fit the map text was smaller than the page type rule:
running text 12px or more, and labels 11px or more. The maintainer agreed to a change.
The acceptance values were written before the change:

- At Fit on a 1440 x 900 screen with the panel open, the self map shows card names at 12 px or more,
  card descriptions at 11 px or more, and flow labels, region labels and container labels at 11 px or more.
- At the same size, the tags, the step numbers and the step note of a Sequences step show at 11 px or more.
- On a 390 x 844 phone, the map frame of each sequence step shows card names at 12 px or more
  and card descriptions at 11 px or more. The acting component of the step is on the screen.
- In each state of the tables, these counts do not increase: labels on labels, labels on cards,
  labels on lines other than their own line, card text outside its card, and map text under the
  title, the legend, the readout or the zoom controls.
- The self map and the sample map keep their `systemap check` result and their layout geometry:
  the card boxes, the label boxes, the flow paths and the collisions that the render reports.
- The sample page of `test_page_is_small_and_self_contained` stays smaller than 300 KiB (307,200 bytes).
- Fit, the zoom value (100 percent), zoom in and zoom out keep their functions. Each motion obeys Reduce motion.

Method: Chromium 141.0.7390.37 (Playwright), device scale 1, Ink, Reduce motion on, the first-visit guide closed.
The pages are scratch builds of the self map and of the sample map of the tests.
For each visible SVG text element, the size on the screen is its CSS font size multiplied by the scale of its screen transform.
A table cell gives the smallest size of the role in CSS pixels. A dash shows that the state has no text of that role.
The overlap counts use the screen bounding boxes of the text elements, the card boxes and the line segments, with a 1 px tolerance.
A tag on its own card is not an overlap.

Before the change (f70c3e8):

| Map | State | Zoom (percent) | Card name | Card description | Flow label | Region label | Container label | Tag | Step number and words | Step note |
|---|---|---|---|---|---|---|---|---|---|---|
| Self map | 1440 x 900, panel open | 75 | 11.0 | 10.1 | 8.2 | 8.2 | 8.2 | - | - | - |
| Self map | 1440 x 900, panel closed | 75 | 11.0 | 10.1 | 8.2 | 8.2 | 8.2 | - | - | - |
| Self map | 1440 x 900, Sequences step 1 | 75 | 11.0 | 10.1 | - | 8.2 | 8.2 | 8.5 | 9.3 | 9.3 |
| Self map | 1024 x 768, panel open | 60 | 8.8 | 8.1 | 6.6 | 6.6 | 6.6 | - | - | - |
| Self map | 1024 x 768, panel closed | 61 | 8.9 | 8.2 | 6.7 | 6.7 | 6.7 | - | - | - |
| Self map | 800 x 600 | 43 | 6.3 | 5.8 | 4.7 | 4.7 | 4.7 | - | - | - |
| Self map | 390 x 844, phone full map | 31 | 4.6 | 4.2 | 3.4 | 3.4 | 3.4 | - | - | - |
| Self map | 390 x 844, phone step (smallest / median of 46 steps) | 35 / 60 | 5.1 / 8.8 | 4.7 / 8.2 | - | 3.8 / 6.6 | 3.8 / 5.9 | 4.0 / 6.8 | 4.3 / 7.5 | - |
| Sample map | 1440 x 900, panel open | 109 | 16.1 | 14.9 | 12.0 | 12.0 | 12.0 | - | - | - |
| Sample map | 1440 x 900, panel closed | 151 | 22.3 | 20.6 | 16.6 | 16.6 | 16.6 | - | - | - |
| Sample map | 1440 x 900, Sequences step 1 | 109 | 16.1 | 14.9 | - | 12.0 | 12.0 | 12.4 | 13.7 | 13.7 |
| Sample map | 1024 x 768, panel open | 72 | 10.6 | 9.8 | 7.9 | 7.9 | 7.9 | - | - | - |
| Sample map | 1024 x 768, panel closed | 108 | 15.9 | 14.6 | 11.8 | 11.8 | 11.8 | - | - | - |
| Sample map | 800 x 600 | 84 | 12.4 | 11.4 | 9.2 | 9.2 | 9.2 | - | - | - |
| Sample map | 390 x 844, phone full map | 37 | 5.5 | 5.1 | 4.1 | 4.1 | 4.1 | - | - | - |
| Sample map | 390 x 844, phone step (smallest / median of 4 steps) | 72 / 93 | 10.6 / 13.8 | 9.7 / 12.7 | - | 9.7 / 10.3 | 9.7 / 10.3 | 8.2 / 10.6 | 8.9 / 10.7 | - |

Overlap counts before the change, for each layer of the self map. Each cell gives
labels on other lines / map text or cards under the page controls. The other counts were 0.

| Self map layer | 1440 x 900, panel open | 1024 x 768, panel open | 800 x 600 |
|---|---|---|---|
| System context | 15 / 0 | 15 / 3 | 15 / 4 |
| Structure | 0 / 0 | 0 / 0 | 0 / 0 |
| Data flow | 0 / 0 | 0 / 3 | 0 / 2 |
| Control flow | 10 / 0 | 10 / 3 | 10 / 2 |
| Map review | 3 / 0 | 3 / 3 | 3 / 2 |
| All | 0 / 0 | 0 / 4 | 0 / 4 |

At 1024 x 768 and 800 x 600, the legend covers a part of the Describe card at the bottom of the map. The sample map has no overlaps.
On the phone, the 46 steps of the self map have 23 overlaps between tags and step numbers.
These overlaps are in the Sequences marks and do not change with the zoom.

`systemap check` on the self map before the change: "map layout: has no errors (20 components,
76 orthogonal labeled edges, no text size less than 11px)". The layout digest of the render
(card boxes, label boxes, paths, collisions, notes and headers) was `c234e180810b1631` for the self map
and `37a8ed23f412ee50` for the sample map.

### Options

The measurements of each option use the self map at 1440 x 900 with the panel open, where the base zoom is 75 percent.
Card names need 81.4 percent for 12 px, card descriptions 80.9 percent for 11 px, and 11-unit labels 100 percent for 11 px.

| Option | Measurement | Result |
|---|---|---|
| (a) Labels that become larger below 100 percent, with collision handling | A test script in Chromium, with the text boxes. Labels scaled about their centre, no move: at a scale of 1.32, 7 of 13 System context labels, 3 of 14 Control flow labels and 6 of 7 Map review labels touch a card, a label or a new line. With a move along the own line, 2 of 13, 0 of 14 and 2 of 7 at 1.2, and 3, 0 and 3 at 1.32 | Used. The card text cannot become larger: the cards have a fixed size |
| (b) A smaller page frame | A test script that adds CSS in Chromium. The map is limited by its height at 1440 x 900: the zoom is 75 percent with the panel open and with the panel closed. A narrower panel does not help. The title block on two compact lines gave 78.6 percent, on one line 79.8 percent, with an 8 px margin and the legend gap of the framing | Used, with the one-line title block and smaller gaps: 82.1 percent |
| (c) Fit of the cards and regions only | The cards and regions are 776 units high, and the containers 860 units. In the 706 px high frame of the final page, the zoom would be 91 percent (calculated, not measured) | Not used: the container labels go off the screen at Fit |
| (d) Larger label size in the layout | "Flow label size on the map page": at a scale of 1.10, 5 label collisions | Not used: it changes the check result |
| (e) A phone step frame at a zoom at which the card text is 11 px or more | The zoom is 81.4 percent or more. The acting card is on the screen in 46 of 46 steps. Both ends of the line are on the screen in fewer steps (see below) | Used |

Fit now fits the drawn bounds of the map (`data-fit`), not the viewBox with its 26-unit margin.
It keeps the map 8 px from the frame and above one line of the legend. With a measured legend top, the zoom of the
self map changed from layer to layer at 1024 x 768 and 800 x 600, because the legend has two lines on a narrow window
for some layers. Thus Fit uses one line of the legend. The title block on one line had the same problem when the
question went onto a second line: a window of 1259 px or less now shows only the question.

### After the change

| Map | State | Zoom (percent) | Card name | Card description | Flow label | Region label | Container label | Tag | Step number and words | Step note |
|---|---|---|---|---|---|---|---|---|---|---|
| Self map | 1440 x 900, panel open | 82 | 12.1 | 11.2 | 11.0 | 11.0 | 10.7 | - | - | - |
| Self map | 1440 x 900, panel closed | 82 | 12.1 | 11.2 | 11.0 | 11.0 | 10.7 | - | - | - |
| Self map | 1440 x 900, Sequences step 1 | 82 | 12.1 | 11.2 | - | 11.0 | 10.7 | 11.2 | 11.2 | 11.2 |
| Self map | 1024 x 768, panel open | 62 | 9.2 | 8.4 | 8.4 | 8.4 | 7.9 | - | - | - |
| Self map | 1024 x 768, panel closed | 67 | 9.8 | 9.1 | 9.1 | 9.1 | 8.5 | - | - | - |
| Self map | 800 x 600 | 48 | 7.0 | 6.5 | 6.5 | 6.5 | 6.0 | - | - | - |
| Self map | 390 x 844, phone full map | 32 | 4.7 | 4.3 | 4.3 | 4.3 | 4.0 | - | - | - |
| Self map | 390 x 844, phone step (smallest / median of 46 steps) | 81 / 81 | 12.0 / 12.0 | 11.1 / 11.1 | - | 8.9 / 11.1 | 10.3 / 10.3 | 11.1 / 11.1 | 11.1 / 11.1 | - |
| Sample map | 1440 x 900, panel open | 118 | 17.4 | 16.0 | 13.0 | 13.0 | 13.0 | - | - | - |
| Sample map | 1440 x 900, panel closed | 150 | 22.1 | 20.4 | 16.5 | 16.5 | 16.5 | - | - | - |
| Sample map | 1440 x 900, Sequences step 1 | 118 | 17.4 | 16.0 | - | 13.0 | 13.0 | 16.0 | 16.0 | 16.0 |
| Sample map | 1024 x 768, panel open | 77 | 11.3 | 10.5 | 10.5 | 8.5 | 10.5 | - | - | - |
| Sample map | 1024 x 768, panel closed | 116 | 17.1 | 15.8 | 12.8 | 12.8 | 12.8 | - | - | - |
| Sample map | 800 x 600 | 90 | 13.3 | 12.3 | 11.1 | 9.9 | 11.1 | - | - | - |
| Sample map | 390 x 844, phone full map | 39 | 5.8 | 5.3 | 5.3 | 4.3 | 5.3 | - | - | - |
| Sample map | 390 x 844, phone step (smallest / median of 4 steps) | 81 / 93 | 12.0 / 13.8 | 11.1 / 12.7 | - | 9.7 / 10.4 | 11.1 / 11.1 | 11.1 / 12.7 | 11.1 / 12.3 | - |

Result for each acceptance value:

- 1440 x 900 with the panel open: card names 12.1 px, card descriptions 11.2 px, flow labels and region labels 11.0 px. Pass.
  The container label OUTSIDE THE PACKAGE is 10.7 px: its box is 190 units wide, and the label stops 6 units before its right edge.
  This value fails the acceptance value of 11 px. A wider label needs a wider container, which is a layout change.
- Sequences step at 1440 x 900: tags, step numbers and the step note at 11.2 px. Pass.
- Phone step: card names 12.0 px and card descriptions 11.1 px in each of the 46 steps. The acting card is on the screen in 46 of 46 steps. Pass.
  The cost: the source card of the step line is on the screen in 39 of 46 steps (before: 46), and the target card in 25 of 46 (before: 46).
  The step note under the map gives both ends. A region label that has no room next to a step number keeps 11 units: 8.9 px.
- Overlaps: no count increased, in any state of the tables or in the 6 phone region frames. The probe counts an item only
  when more than 1 px of it is in the map frame. Each cell gives labels on other lines / map text or cards under the
  page controls. The other counts were 0 before and after on the desktop.

| Self map layer | 1440 x 900, panel open | 1024 x 768, panel open | 800 x 600 |
|---|---|---|---|
| System context | 13 / 0 (before 15 / 0) | 13 / 0 (before 15 / 3) | 13 / 2 (before 15 / 4) |
| Structure | 0 / 0 (before 0 / 0) | 0 / 0 (before 0 / 0) | 0 / 0 (before 0 / 0) |
| Data flow | 0 / 0 (before 0 / 0) | 0 / 0 (before 0 / 3) | 0 / 0 (before 0 / 2) |
| Control flow | 9 / 0 (before 10 / 0) | 9 / 0 (before 10 / 3) | 9 / 0 (before 10 / 2) |
| Map review | 2 / 0 (before 3 / 0) | 2 / 0 (before 3 / 3) | 2 / 0 (before 3 / 2) |
| All | 0 / 0 (before 0 / 0) | 0 / 3 (before 0 / 4) | 0 / 2 (before 0 / 4) |

  The labels on other lines decreased because a label that has no free place at its larger size is now in the list.
  At Fit on 1440 x 900, the readout gives these labels in the list: System context 4 (before: 2), Control flow 2 (before: 2),
  and Map review 4 (before: 2). Thus 2 labels of System context and 2 of the 9 labels of Map review show only for a pointer,
  keyboard focus or selection at Fit. At 100 percent and more, the labels have their layout size, and only the labels beside their lines are in the list.
  On the phone, the overlaps between tags, step numbers and region labels went from 23 to 0, because the step numbers now keep off the region and container labels.
  The sample map has no overlaps before and after.
- `systemap check` gives the same layout line: "map layout: has no errors (20 components, 76 orthogonal labeled edges,
  no text size less than 11px)". The layout digests are the same: `c234e180810b1631` and `37a8ed23f412ee50`.
  In a scratch worktree, `systemap refresh` and then `systemap check` gave "coverage: 84 of 84 modules mapped" and the same layout line.
  The other check lines are stale source records, which the maintainer renews after the merge.
- Page size: the sample page is 307,114 bytes (before: 301,519), 86 bytes under the limit. The self-map page is 643,467 bytes (before: 637,718).
  The label script is 4,561 bytes of the 5,595. The change removes an unused camera function (`fracOf`) and a second legend
  calculation in the sequence script. A further addition to the page can exceed the limit.
- The zoom controls: in Chromium, Fit, the zoom value (100 percent), zoom in and zoom out (1.25), the wheel, a selection frame,
  Escape back to Fit, full screen and the panel button all gave the expected zoom and pressed state. A view at Fit stays at Fit
  when the panel opens or closes. The zoom value now shows the new zoom when the frame changes size. Before, the sample page
  at 1024 x 768 showed 108% at a zoom of 72 percent after the panel opened.
  The first-visit guide moves the map after the panel opens, so the map stays in the frame.
  The Changes view opens at Fit (77 percent on the self map with a comparison). No page error occurred.
  The label sizes have no motion. The camera keeps its 300 ms motion and obeys Reduce motion.

Frame times during a zoom (no acceptance value was written before this run; the earlier sections use 20 percent):
120 frames, one new zoom in each frame from 40 to 140 percent and back, 1440 x 900, Ink, headless Chromium. The first 5 frames are not counted.
The first runs of an earlier version, which painted the map at each label scale, gave increases up to 25.8 percent in one of eight runs.
The final version paints only when the list of labels changes:

| Layer | Run | Before (mean / p95 ms) | After (mean / p95 ms) |
|---|---|---|---|
| Control flow | 1 | 20.61 / 33.4 | 21.78 / 33.4 |
| Control flow | 2 | 17.98 / 33.3 | 19.88 / 33.4 |
| Control flow | 3 | 19.44 / 33.4 | 21.49 / 33.4 |
| Control flow | 4 | 19.00 / 33.3 | 20.61 / 33.4 |
| All | 1 | 20.76 / 33.4 | 22.66 / 33.4 |
| All | 2 | 20.17 / 33.4 | 21.64 / 33.4 |
| All | 3 | 20.17 / 33.4 | 22.51 / 33.4 |
| All | 4 | 22.08 / 33.4 | 21.05 / 33.4 |

The largest increase of the mean is 11.6 percent. The differences between runs of one page are almost as large.

The new tests in `tests/test_map_text.py` gave 6 failures and 1 pass on the base (acd31f5) and 7 passes after the change.
The test that passes on the base examines that the layout widths do not change.

## Map page size after the font, map changes and label merges (2026-10-12)

The sample page of `test_page_is_small_and_self_contained` is 326,739 bytes after the three merges.
The limit is 329,728 bytes, so the page passes with 2,989 bytes of space.
The label script and the Fit changes added 5,595 bytes.

## Live map: render time, change.svg and file scan (2026-10-12)

`systemap live` renders the map of the working tree again after each change. These measurements decide how often it can do that.
The scripts are in the session scratch directory of the work, `/tmp/claude-0/-home-user-systemap/6b590864-2df7-5a7b-8dc8-f2bf55c85a45/scratchpad/live/`.
They ran on this repository (86 modules at 7b29986, 87 with `page_live`), 4 processors, CPython 3.11.17.

### One render before the change (measured by the coordinator, copied)

`measure_render.py`, at 7b29986, one Python process, median of 3 after one run to warm up:

| Step | Time |
|---|---|
| `extract.build` | 3.21 s |
| Page build without a comparison | 1.38 s |
| Page build with a comparison with main | 2.52 s |
| Extraction and the compared page | 5.73 s |

The acceptance value, written before the run, was 3.0 s or less for extraction and the compared page. The result FAILED.
Thus `systemap live` renders after the files stop changing, or once for each agent turn (`--no-watch` and `POST /refresh`).
It does not render while the files continue to change.
With the installed command, `delta --base origin/main` took about 6.0 s and `check` about 9.7 s. `uv run` adds about 5 s.

### The working-tree comparison agrees with the committed comparison

`measure_parity.py`. Acceptance value, written before the run: for each of 6 bases, the `direct` set of the working-tree
comparison is the same as the `direct` set of the committed comparison (`systemap render --base` gives that comparison to the page).
The script computes the committed comparison of B and HEAD. Then `git reset --mixed B` puts the same change in the working tree
as edits that are not in a commit and untracked files, and the script computes the working-tree comparison.

The first run used HEAD~60 as the last base. The scratch clone is shallow (52 first-parent commits), so Git could not resolve HEAD~60
and the run stopped after HEAD~25. The second run used HEAD~50:

| Base | Files | Changed components | `direct` | `modules` | `adjacent` | Committed | Working tree (without extraction) |
|---|---|---|---|---|---|---|---|
| HEAD~1 (f70c3e8) | 130 | 13 | same | same | same | 0.91 s | 0.80 s |
| HEAD~2 (6e4c6b1) | 165 | 14 | same | same | same | 1.22 s | 1.00 s |
| HEAD~5 (0a1e6da) | 230 | 16 | same | same | same | 1.91 s | 1.71 s |
| HEAD~10 (83aabb8) | 261 | 16 | same | same | same | 2.00 s | 1.53 s |
| HEAD~25 (28b68a1) | 337 | 16 | same | same | same | 1.78 s | 1.34 s |
| HEAD~50 (5ea982b) | 335 | 16 | same | same | same | 1.81 s | 1.36 s |

Result: 6 of 6 the same. The acceptance value passed.

### One render of `systemap live`, by step

`measure_live.py`, one Python process, median of 3 after one run to warm up (the scan: median of 10).
Acceptance values, written before the run: change.svg adds 1.0 s or less to a render.
One scan of the watched files takes 50 ms or less (5% or less of one processor at one scan each second).

| Step | Base HEAD (no change) | Base HEAD~1 (13 changed components) |
|---|---|---|
| Configuration and model load | 0.00 s | 0.01 s |
| `extract.build` | 2.74 s | 2.96 s |
| Pages (comparison and `page.build`) | 2.53 s | 3.37 s |
| `change.compute` in the working tree, alone | 0.02 s | 0.80 s |
| change.svg (`figure.make`) | 1.24 s (system figure, 97,234 characters) | 2.16 s (change figure, 108,545 characters) |
| Map update lines (`delta.compute_tree`, cached base facts) | 0.05 s | 0.04 s |
| `render_tree`, one call | 7.00 s | 8.09 s |
| List of the watched files | 1.6 ms (170 paths) | 1.7 ms (170 paths) |
| List and scan | 2.2 ms (168 files) | 2.3 ms (168 files) |

change.svg: the acceptance value FAILED. The figure adds 1.24 s without a change and 2.16 s with a change.
`figure.make` computes the comparison again (0.80 s for HEAD~1), and the schematic of the figure takes the rest.
The page already has the comparison, but `figure.make` has no parameter for it.
A new parameter would increase its cognitive complexity (22 now, the limit is 15), so this change does not add one.
The scan: the acceptance value passed, with 2.3 ms or less.

### One edit cycle of the command

`cycle.py` started `uv run systemap live --port 0 --json` in a scratch clone at 37a50b5, without `--no-watch`.
It added a function to `src/systemap/serve.py`, waited for the next `rendered` line, read `GET /status`, removed the function,
waited for one more `rendered` line, and sent SIGTERM. No acceptance value was written before this run.

| Version | Seconds | Map updates | Changed components | change.svg bytes |
|---|---|---|---|---|
| 1 | 10.22 | 0 | none | 97,257 |
| 2 | 7.13 | 1 | CLI | 103,400 |
| 3 | 6.64 | 0 | none | 97,257 |

The first version also extracts the facts of the merge base into the cache. From the edit to the `rendered` line took 9.1 s:
the scan waits for one scan without a change, then the render takes about 7 s.
The exit code was 0, the temporary directory was removed, and `git status --porcelain` was empty before and after.
An earlier run, with an earlier version of the code, `--no-watch` and `POST /refresh`, took 6.9 s from the edit to the `rendered` line.

The new tests (`tests/test_live_change.py`, `tests/test_live.py`, `tests/test_live_view.py`) gave 3 collection errors on the base (7b29986):
`change.WORKING_TREE` and `page_live` do not exist there. After the change, all of them pass (32 tests).
These errors show only that the interface is new. The parity measurement above compares the behavior.

## Component review state and source records outside the flow endpoints (2026-10-12)

This work gives each component one review state: `missing` (no `source_review`), `stale`
(`source_review` is not the current digest), or `current`. It also makes a rule for flow source
records: at least one source record must be in a module of the source component or the target component.
Two census scripts measured the maps before the decisions. They are not in the repository:
`review_census.py` counts the review states and the flows with source records outside their endpoints.
`strict_compare.py` gives the `judgement --strict` result with the code of 7b29986 and with the changed code.

Acceptance (written before the census):

1. A map that passes `judgement --strict` with the code of 7b29986 fails it with the changed code only
   if a review is stale. If a map that passes now has a component without `source_review`, then a
   `missing` review is a count line, not a finding.
2. If no reviewed flow on these maps has source records outside its endpoints, the rule can change
   the evidence state and add a judgement finding without a migration of an existing map.

The census used the stored facts of each map. The fixture has no stored facts, so the census made its facts in memory.

| Map | Source components | current | stale | missing | `judgement --strict` at 7b29986 | Flows | With source records | Records outside the endpoints |
|---|---|---|---|---|---|---|---|---|
| Self-map at 7b29986 | 16 | 16 | 0 | 0 | pass, 6 answered | 76 | 61 | 0 |
| `bench/scratch/cli-first-map-20261011T201433Z` (httpie) | 17 | 0 | 0 | 17 | pass, 73 answered | 34 | 0 | 0 |
| `tests/fixtures/typescript-app` | 1 | 0 | 0 | 1 | fail, 6 open | 0 | 0 | 0 |

No flow in these maps has source records and an actor end.

Decisions:

- A `missing` review is a count line, `source reviews: N current, N stale, N missing`, and not a finding.
  The httpie map passes `judgement --strict` with 17 of 17 reviews missing.
  As a finding, a missing review would add 17 open lines and make that map fail.
- A `stale` review is a `stale source review` finding.
- A flow with source records outside its endpoints is not `observed`, and judgement prints a `no endpoint source` finding.
  The census found 0 such flows, so neither change has an effect on these maps.
  The state change keeps the page from showing "current source review" for records that do not show the flow.
  The finding gives the correct reason and action. The `flow review` and `declared flow` lines give a different reason.

Result with the changed code (`strict_compare.py`):
the self-map at 7b29986 passes with 6 answered and `source reviews: 16 current, 0 stale, 0 missing`.
The httpie map passes with 73 answered and `source reviews: 0 current, 0 stale, 17 missing`.
The fixture fails with the same 6 open lines as before.
Acceptance 1 and acceptance 2 are met.

The self-map after the source changes of this work (facts made again with `systemap refresh`, not committed):

- `systemap check` passes.
- `systemap judgement --strict` fails with 60 open lines:
  8 `stale source review` lines (CLI, Config, ChangeDetector, Model, Schematic, Page, Judgement, Describe),
  0 `no endpoint source` lines, 45 `flow review` lines, 1 `declared flow` line, and 6 `single module` lines with pending answers.
- `systemap delta --base 7b29986` gives `source review` lines for the same 8 components.

The 45 `flow review` lines, the `declared flow` line, and the 6 pending answers come from the new source hashes of the changed modules.
Each source change has this effect. The maintainer renews the digests and the answers after the source review.

A probe (`stale_probe.py`, not in the repository) wrote the two-card test map with one stale `source_review` value.
Acceptance (written before the run): exit code 0 with the code of 7b29986, and exit code 1 with one
`stale source review` line with the changed code.
`judgement --strict` gave exit code 0 with the code of 7b29986 and exit code 1 with the changed code. Acceptance met.

The sample page of `test_page_is_small_and_self_contained` is 326,741 bytes with the code of 7b29986 and
326,810 bytes with the changed reader text. The limit is 329,728 bytes.

## Claude Code version for the plugin job (2026-10-12)

Acceptance value, written before the run: the lowest Claude Code version that does all steps of the
CI plugin job with the hooks module of the live map. The steps are `claude plugin validate .`, the two
`scripts/check_plugin_manifest.py` checks, the marketplace install with the plugin enabled, and
`claude plugin test .` with 15 passed tests. Each lower version must fail.
The script `ci_versions.py` installed each version with npm into a scratch directory and used an empty
configuration directory. It was not added to the repository.

| Versions | `plugin test` command | Manifest checks | Install | Plugin tests |
|---|---|---|---|---|
| 2.1.278, 2.1.280 | No | Fail: `$ is passed to "update", imported from "claude-code"` | Pass | Cannot run |
| 2.1.281 to 2.1.285 | No | Pass | Pass | Cannot run |
| 2.1.286 to 2.1.288, link to `http://127.0.0.1` | Yes | Pass | Pass | 9 pass, 6 fail |
| 2.1.286 to 2.1.296, link to `http://localhost` | Yes | Pass | Pass | 15 pass |

Result: 2.1.286. The CI plugin job installs it and runs `claude plugin test .`.
Versions 2.1.286 to 2.1.288 refuse a `Link` to `http://127.0.0.1:PORT/` with
`Link href must be https: (or http://localhost)`. Then they draw no line above the prompt.
Thus the `Open map` link uses `localhost`. Version 2.1.296 takes both addresses.
A second run of 2.1.286 without the session variables of this computer also passed all steps.

## A model reader that runs no code (2026-10-12)

systemap 2.0.0 ran `map/model.py` as Python code. The new reader (`src/systemap/model_load.py`)
parses the model file and makes the values from literal syntax only.
`SYSTEMAP_TRUST_MODEL_CODE=1` in the environment of the command selects the 2.0.0 loader.
All runs used Python 3.11.17 on Linux. Other processes can run on the same computer, so the times are approximate.

### Parser limits (model_parse_limits.py)

Acceptance (written before the run): each input parses or gives SyntaxError, RecursionError,
MemoryError, or ValueError, and the process does not stop. The peak memory for a 1 MB file
with the most syntax nodes for its size is less than 400 MB.

| Input | Result |
|---|---|
| 300 nested parentheses | SyntaxError: too many nested parentheses |
| 300 nested lists | SyntaxError: too many nested parentheses |
| 100,000 minus signs before a number | MemoryError, at once |
| 100,000 additions | RecursionError during the syntax tree construction (0.05 s) |
| An attribute chain of 100,000 names | RecursionError during the syntax tree construction (0.03 s) |
| A chain of 50,000 calls | RecursionError during the syntax tree construction (0.05 s) |
| 100,000 `not` operators | MemoryError, at once |
| A flat list, 1,000,006 bytes | 500,006 nodes, peak 485 MB, 2.80 s |
| A flat list, 524,294 bytes | 262,150 nodes, peak 262 MB, 1.49 s |
| A flat list, 262,150 bytes | 131,078 nodes, peak 137 MB, 0.31 s |

No input stopped the process. The 1 MB file failed the memory acceptance value.
The reader therefore reads at most 512 KiB for one model and the files that it imports.
It refuses a larger file before it parses it. The reader gives the parser errors as refusals.
Its own check also refuses values that are nested more than 32 levels.
The three self-map files contain 72,442 bytes after this change.

### Load time (model_load_time.py)

Acceptance (written before the run): the safe reader takes at most twice the time of the
2.0.0 code loader for the self-map. Each line is one process with 30 loads after one load
that is not counted. The values are the medians in milliseconds.

| Files | Code loader (ms) | Safe reader (ms) | Ratio |
|---|---|---|---|
| 2.0.0 self-map (7b29986), bytecode cache | 3.3, 3.4, 4.2 | refused | |
| New self-map, bytecode cache | 2.5, 2.5, 2.3 | 8.0, 7.2, 6.7 | 3.16, 2.91, 2.88 |
| New self-map, no bytecode cache (`PYTHONDONTWRITEBYTECODE=1`) | 7.0, 4.2, 4.3 | 7.5, 6.7, 6.5 | 1.07, 1.60, 1.50 |

The safe reader failed the acceptance value when Python keeps the bytecode of
`map/flows.py` and `map/journeys.py` in `map/__pycache__`. Then the code loader compiles
only `map/model.py`. The reader passed the acceptance value without the bytecode cache.
Against the 2.0.0 self-map with the code loader (the state before this change), the
ratios of the medians across the runs are between 1.5 and 2.4.

A profile of a first version gave these means of 30 runs for the three files:
the complete read 9.47 ms, `ast.parse` 4.35 ms, a count of the syntax nodes with `ast.walk`
1.89 ms, and the values 0.79 ms. `compile` of the same three files takes 3.72 ms.
The check now counts the values that it examines, and the `ast.walk` count is removed.
The remaining time of the current reader, about 1.5 ms, is the check and the file reads
(calculated from the table, not measured separately).
`ast.parse` alone is near twice the time of the code loader with the bytecode cache,
so a check with no cost would also be near the acceptance value. A measurement is
necessary before a decision about a cache of the parsed files.
The difference is 4 to 5 ms for each load. `systemap check` loads the model one time.

### Model files that the reader accepts (model_census.py)

Acceptance (written before the run): 0 refusals for the self-map, the TypeScript test
fixture, the model that `systemap init` writes, and the worked example of the skill.

| File | Result in the worktree of this change |
|---|---|
| The `systemap init` template | accepted |
| `map/model.py`, with `map/flows.py` and `map/journeys.py` | accepted |
| `tests/fixtures/typescript-app/map/model.py` | accepted |
| The worked example in `references/example.md` (three skill directories) | accepted |
| The example in `docs/reference.md` | accepted |
| `bench/scratch/cli-first-map-20261011T201433Z/repo/map/model.py` | accepted |
| The skill example in that bench repository (skill 2.0.0) | refused: line 46, an index (`x=COL["c1"]`) |

The change passed the acceptance value. Before this change, the reader refused
`map/model.py` (line 15, `from dataclasses import replace`, then `_reviewed` and a
dictionary comprehension) and the skill example (line 46, an index into `COL`).
The bench model has `Steps = tuple[Step, ...]` from the 2.0.0 `init` template.
The reader accepts this form as a type alias, so the `init` models of 0.11.0 to 2.0.0 load
with no change. The census of the model texts that the tests write is in the test suite:
the two-card fixture (`x=COL["c1"]`), four delta and comparison fixtures
(`plain={c.id: ... for c in COMPONENTS}`) and the placement fixture (a Python module with
`from typing import Any` and a calculated grid) were refused. They now use literal values.

Of the 69 commits that changed the self-map, the reader accepts 4: this change and three
commits of 2026-08-26 and 2026-08-27. The other 65 have `from dataclasses import replace` (56)
or a comprehension (9). `render --base` with one of these commits shows the refusal in the
Changes view, unless `SYSTEMAP_TRUST_MODEL_CODE=1` is set.

### Adversarial tests

`tests/test_model_load.py` has 43 tests. With the 2.0.0 loader (the code of de8358e), 37 failed
and 6 passed. In 22 of the failures, the model file wrote its marker file: `os.system`,
`__import__`, `exec`, `eval`, `getattr`, `__builtins__`, a lambda, a function, a class,
a decorator, a comprehension, an f-string, `systemap.config` and other systemap modules
(three tests), a call of `open`, a sibling file through a symbolic link to outside the
directory, a committed model in the revision comparison, and the four values of
`SYSTEMAP_TRUST_MODEL_CODE` other than `1`. The other 15 failures were refusals that did not
occur or messages without the line. The 6 tests that passed examine files that both loaders
accept, and the annotation test: the 2.0.0 loader also did not evaluate annotations, because
`compile` received `from __future__ import annotations` from `config.py`.
With the safe reader, all 43 tests pass.

## Can a different code context make the flow question stable on the holdout maps? (2026-10-13)

The `jev flow` question gives the probability that the code agrees with a flow sentence.
The code is the context that `audit_code.code_between` selects.
This context is the source lines that use a name imported from the other component, at most 30 lines.
It does not include adjacent lines, or instance calls such as `ledger.record(parts)`.

In the recorded results, the question caught 53 of 80 incorrect claims (66%) on development, and flagged 2 of 80 correct claims.
On holdout, it caught 26 of 48 (54%) and flagged 2 of 48 (4.2%).
The catch rate changed by more than 10 points. Thus `jev flow` is not in `DEFAULT_KINDS`.
This experiment compares four context selectors on the same rows.
`flow_context.py` has the method and the acceptance value in its docstring.

### Method

The rows are the recorded rows of `data/flowverify.jsonl` (5 development maps, 160 rows) and `data/holdout/flowverify.jsonl` (3 holdout maps, 96 rows).
Each map gives 16 flows.
Each flow gives one row with its own claim, and one row with the claim of a different flow from the same source component.
Each arm uses the same ids, claims, and labels.
Each arm sends the shipped question (`audit.VERIFY_Q`) and the shipped `ends` (`audit.card_brief`). Only the `code` text is different.

The source of each map must be the source of its cached facts.
The `flow_context.py build` command compares the hash of each source file with the facts. It stops if a hash is different.

The holdout systemap source is an archive of commit `5704068`, the commit of its facts.
Its map contains a comprehension. Thus the command must have `SYSTEMAP_TRUST_MODEL_CODE=1`.
The scorecard source is `../scorecard` at commit `ae1f309`. `JEV_ROOT_SCORECARD` gives its location.

With these sources, `build_flows.code_between` made the recorded code of all 256 rows again.
The table gives the code text of each arm:

| arm | code text | limit |
|---|---|---|
| `base` | the shipped `code_between` | 30 lines |
| `around` | the shipped lines, then 1 and then 2 adjacent lines before and after each line | 60 lines |
| `calls` | the shipped lines, then the lines that use a name bound to an imported name (`x = Ledger(...)` or `x: Ledger`, then `x.record(...)`), then the `def`, `class`, or `function` line before each of these lines | 60 lines |
| `targets` | the lines of `calls`, then the facts signature of each imported function, class, or method in these lines, then the first sentence of each target module docstring | 60 lines and 12 target lines |

Each line has 160 characters at most.
The median code length on development is 606 characters for `base`, 1,755 for `around`, 1,202 for `calls`, and 1,407 for `targets`.

### Acceptance value

The acceptance value was written before the first Jev call:

- The development set gives the threshold of each arm. The holdout set does not.
  The candidate thresholds are 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, and 0.5.
  The threshold is the largest candidate that flags at most 2.5% of the correct development claims.
  The recorded development figure is 2 of 80 (2.5%).
- At that threshold, the development catch rate must be 50% or more.
- At that threshold, the difference between the holdout catch rate and the development catch rate must be 10 points or less.
- At that threshold, the arm can flag at most 4.2% of the correct holdout claims.
  The recorded holdout figure "4%" is 2 of 48 (4.2%).
- If more than one arm satisfies the value, the arm with the highest development catch rate replaces `code_between`.
  If two arms have the same rate, the arm with the shorter median code wins.
- If an arm satisfies the value, `jev flow` can go into `DEFAULT_KINDS`. If no arm satisfies it, `src/` does not change.

The `calls` and `targets` arms use text patterns for Python and TypeScript syntax: `def`, `function`, `self.`, `this.`, and `const`.
Shared code must not contain language syntax. Thus only `base` and `around` can change `src/` in this work.
If only `calls` or `targets` satisfies the value, `src/` does not change.
Then a call-site fact from each language adapter is necessary.

All the repositories in the two sets are Python repositories.
Thus the result does not show the behavior on TypeScript.

### Commands

    uv run --project bench/jev python bench/jev/flow_context.py build
    uv run --project bench/jev python bench/jev/run.py flowctx_base flowctx_around flowctx_calls flowctx_targets
    SYSTEMAP_TRUST_MODEL_CODE=1 JEV_SET=holdout JEV_ROOT_SCORECARD=../scorecard uv run --project bench/jev python bench/jev/flow_context.py build
    JEV_SET=holdout uv run --project bench/jev python bench/jev/run.py flowctx_base flowctx_around flowctx_calls flowctx_targets
    uv run --project bench/jev python bench/jev/flow_context.py score > bench/jev/results/flowctx-report.txt

### Results

The Jev requests were sent on 2026-10-13. Each arm operated one time on development, and then one time on holdout.
No selector changed between the development requests and the holdout requests.
All 1,024 answers came from the model `jev-1.13.0`, with 0 errors.
`results/flowctx-report.txt` has the full output.

Two arms satisfy the acceptance value: `calls` and `targets`. `base` and `around` do not.
The table gives the figures at the threshold that the development set selected.
"Caught" is the fraction of incorrect claims with P(holds) below the threshold.
"Flagged" is the fraction of correct claims below the threshold.

| arm | threshold | dev caught | dev flagged | holdout caught | holdout flagged | points | result |
|---|---|---|---|---|---|---|---|
| `base` | 0.15 | 39/80 (48.8%) | 1/80 (1.2%) | 19/48 (39.6%) | 1/48 (2.1%) | -9.2 | fail: dev caught below 50% |
| `around` | 0.15 | 34/80 (42.5%) | 1/80 (1.2%) | 14/48 (29.2%) | 1/48 (2.1%) | -13.3 | fail: dev caught below 50%, difference more than 10 points |
| `calls` | 0.2 | 48/80 (60.0%) | 2/80 (2.5%) | 26/48 (54.2%) | 0/48 (0.0%) | -5.8 | pass |
| `targets` | 0.2 | 47/80 (58.8%) | 2/80 (2.5%) | 28/48 (58.3%) | 0/48 (0.0%) | -0.5 | pass |

The AUC on development and holdout was 0.878 and 0.882 for `base`, and 0.880 and 0.909 for `around`.
It was 0.898 and 0.931 for `calls`, and 0.899 and 0.932 for `targets`.

In this measurement, `base` at the shipped threshold 0.2 caught 53/80 (66%) and flagged 4/80 (5.0%) on development.
On holdout, it caught 29/48 (60.4%) and flagged 2/48 (4.2%).
The recorded measurement flagged 2/80 on development with the same `code` text, but with the earlier question and an earlier model.
Thus the development rule selected 0.15 for `base`, and `base` did not satisfy the value.

The cost was 1,024 Jev requests: 1,094,728 input tokens and 20,480 output tokens.
The median input was 698 tokens for `base`, 1,119 for `around`, 848 for `calls`, and 932 for `targets` on development.
The median latency was 0.21 to 0.23 seconds for each arm.

### Decision

`calls` has the highest development catch rate of the two arms that satisfy the value.
But `calls` uses text patterns for Python and TypeScript syntax, and shared code must not contain these patterns.
Thus `src/` did not change, and `jev flow` stays out of `DEFAULT_KINDS`.

To use the result, a language adapter must write a call-site fact for each module.
The fact must give the lines that use a local name bound to an imported name.
It must also give the line of the function that contains each use.
Each adapter must give the same output: `extract.py` for Python, and the TypeScript adapter.
Then `audit_code` can select the `calls` lines from the fact.

A new measurement with the fact is necessary before `jev flow` goes into `DEFAULT_KINDS`.
All the measured repositories are Python repositories. A TypeScript measurement is also necessary.

The `targets` lines from the facts signatures did not increase the development catch rate (47/80 compared with 48/80 for `calls`).
The `around` lines decreased the catch rate on the two sets.
With 48 holdout claims, one claim is 2.1 points. Thus the difference between `calls` and `targets` on holdout is 2 claims.

## Can OpenAI Decisions use the measured audit rules? (2026-10-13)

OpenAI Decisions is a second decision provider: `POST https://api.openai.com/v1/decisions`, model `gpt-6-luna`, public beta.
A threshold of Jev does not apply to a different model.
Thus `decision.thresholds("openai")` stays an error until this experiment gives a value for each question kind.
This experiment sends the Jev bench rows to OpenAI, selects each threshold on development, and compares it with holdout.
`provider_eval.py` has the method and the acceptance value in its docstring.

### Method

The rows are the recorded rows of `data/` (development, five maps) and `data/holdout/` (holdout, three maps).
The kinds are owner (also mis-fold), sentence, flowverify, governs, and issues (triage and plan).
Each row goes to OpenAI one time, as one request.

The request body comes from `systemap.openai_provider.request_body`.
The `input` is the JSON text of the row state.
A Jev `noul` question becomes a `predicate` question. A Jev `choice` question becomes a `choice` question, with the criteria as `choices`.
The question text is the text of the row. Thus the two providers get the same rows and the same question text.

`provider_eval.py curve` scores the recorded Jev answers and the OpenAI answers with the functions of `score.py` and `plan_eval.py`.
Each kind uses only the rows that the two providers answered.
A row with an OpenAI refusal is not in the figures of the two providers. The output gives the count of these rows.

The holdout systemap map must be the map of its cached facts.
`JEV_ROOT_SYSTEMAP` gives an archive of commit `5704068`, the commit of the facts. This map must have `SYSTEMAP_TRUST_MODEL_CODE=1`.
`JEV_ROOT_SCORECARD` gives `../scorecard`, because a worktree has a different parent directory.
With these roots, `score.py` gave the recorded Jev holdout figures again (for example, mis-fold next door 93% caught and 1% flagged, triage top-1 31/39).

The same-pair question of `suggest --jev` and the move question of `delta --jev` have no holdout rows.
Thus the experiment cannot give a holdout result for these two kinds, and it does not send their rows.

### Acceptance value

The acceptance value was written before the first request of the bench rows.
One earlier request with a test input of two questions examined the response form. It did not use bench rows.

- The development set gives the threshold of each kind. The holdout set does not.
- The budget of each kind is the Jev development figure at the shipped Jev threshold, on the same rows.
- Mis-fold: the threshold is the largest candidate where the fraction of correct modules flagged is at most the Jev budget at P<0.05. A module is planted in a neighbour card, as in `score.py`.
- Sentence and flow: the threshold is the largest candidate where the fraction of correct rows flagged is at most the Jev budget at P<0.2.
- Governs: the threshold is the smallest candidate where the fraction of incorrect pairs suggested is at most the Jev budget at P>=0.8.
- Owner: the threshold is the smallest candidate where the fraction of correct answers is at least the Jev budget at confidence >= 0.9.
- Plan: the threshold is the largest cut of `plan_eval.CUTS` that satisfies the plan bar on development: coverage 0.70 or more, and 2.0 more components or less.
- Triage has no threshold. Its figure is the top-1 rate.
- The candidates for a "below" threshold are 0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, and 0.5. The candidates for an "at" threshold are 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, and 1.0.
- If no candidate satisfies the rule, the kind fails. If the selected threshold flags, suggests, or answers no development row, the kind fails.
- At the selected threshold, each figure on holdout must be within 10 points of the same figure on development. This is the rule that the Jev thresholds obeyed.
- A kind that fails is not available for OpenAI. `decision.thresholds("openai")` gives no value for it, and the command gives this result.

The Jev rule for mis-fold, owner, sentence, flow, and governs is not recorded as a formula.
The recorded data is the operating figure at each shipped threshold (`decision.JEV`).
Thus this experiment uses the Jev false alarm figure (or the owner figure of correct answers) as the budget for OpenAI.

### Commands

The key comes from the keychain only for the command. No command writes the key.

    OPENAI_API_KEY="$(security find-generic-password -a "$USER" -s openai-api-key-systemap -w)" uv run --project bench/jev python bench/jev/run.py --provider openai owner sentence flowverify governs issues
    OPENAI_API_KEY="$(security find-generic-password -a "$USER" -s openai-api-key-systemap -w)" JEV_SET=holdout uv run --project bench/jev python bench/jev/run.py --provider openai owner sentence flowverify governs issues
    uv run --project bench/jev python bench/jev/provider_eval.py curve
    SYSTEMAP_TRUST_MODEL_CODE=1 JEV_SET=holdout JEV_ROOT_SCORECARD=../scorecard JEV_ROOT_SYSTEMAP=<archive of 5704068> uv run --project bench/jev python bench/jev/provider_eval.py curve
    uv run --project bench/jev python bench/jev/provider_eval.py verdict > bench/jev/results/openai/report.txt

### Results

The OpenAI requests were sent on 2026-10-13. The development rows went one time, and then the holdout rows went one time.
No rule, row, or request form changed between the two runs.
There were 1,636 requests: 1,131 on development and 505 on holdout. There were 0 errors and 0 refusals.

All answers came from the model `gpt-6-luna`.
All 1,636 answers satisfied the answer check of `openai_provider.answer_of`.
`results/openai/report.txt` has the selection output. `results/openai/curves.txt` has the figures of the two providers at each candidate.

Four of the seven measured kinds satisfy the acceptance value: owner, sentence, flow, and governs.
Mis-fold, plan, and triage do not satisfy it.
The table gives the OpenAI figures at the threshold that the development set selected.

| kind | threshold | figure | development | holdout | points | result |
|---|---|---|---|---|---|---|
| mis-fold (next door) | P<0.02 | caught | 160/195 (82.1%) | 59/96 (61.5%) | -20.6 | fail |
| | | flagged | 6/195 (3.1%) | 1/96 (1.0%) | -2.0 | pass |
| owner | confidence >= 0.99 | answered | 19/200 (9.5%) | 5/106 (4.7%) | -4.8 | pass |
| | | right | 19/19 (100%) | 5/5 (100%) | 0.0 | pass |
| sentence | P<0.3 | caught | 64/79 (81.0%) | 33/44 (75.0%) | -6.0 | pass |
| | | flagged | 1/79 (1.3%) | 0/44 (0.0%) | -1.3 | pass |
| flow | P<0.05 | caught | 37/80 (46.2%) | 27/48 (56.2%) | +10.0 | pass |
| | | flagged | 2/80 (2.5%) | 4/48 (8.3%) | +5.8 | pass |
| governs | P>=0.99 | found | 35/177 (19.8%) | 10/58 (17.2%) | -2.5 | pass |
| | | suggested | 4/354 (1.1%) | 7/116 (6.0%) | +4.9 | pass |
| plan | cut 0.5 | covered | 0.73 | 0.39 | -33.8 | fail |
| triage | none | top-1 | 66/80 (82.5%) | 27/39 (69.2%) | -13.3 | fail |

The flow difference is 10.0 points, the limit of the rule. One more holdout claim caught would make the flow kind fail.
With 48 holdout claims, one claim is 2.1 points.
The sentence rows contain two ids two times in each set. The scorer uses one row for each id: 158 development rows and 88 holdout rows.

### Comparison with Jev on the same rows

The table gives the two providers on the same rows. The Jev columns use the shipped Jev threshold. The OpenAI columns use the selected OpenAI threshold.

| kind | Jev development | Jev holdout | OpenAI development | OpenAI holdout |
|---|---|---|---|---|
| mis-fold: caught, flagged | 94.4%, 4.1% (P<0.05) | 90.6%, 1.0% | 82.1%, 3.1% (P<0.02) | 61.5%, 1.0% |
| owner: answered, right | 55.5%, 98.2% (0.9) | 60.4%, 100% | 9.5%, 100% (0.99) | 4.7%, 100% |
| sentence: caught, flagged | 67.1%, 1.3% (P<0.2) | 61.4%, 2.3% | 81.0%, 1.3% (P<0.3) | 75.0%, 0.0% |
| flow: caught, flagged | 66.2%, 2.5% (P<0.2) | 54.2%, 4.2% | 46.2%, 2.5% (P<0.05) | 56.2%, 8.3% |
| governs: found, suggested | 30.5%, 1.4% (P>=0.8) | 37.9%, 0.9% | 19.8%, 1.1% (P>=0.99) | 17.2%, 6.0% |
| plan: covered | 0.86 (cut 0.05) | 0.71 | 0.73 (cut 0.5) | 0.39 |
| triage: top-1 | 80.0% | 79.5% | 82.5% | 69.2% |

The AUC of the predicate kinds, on development and holdout:

| kind | Jev | OpenAI |
|---|---|---|
| sentence | 0.972, 0.972 | 0.966, 0.969 |
| flow | 0.903, 0.899 | 0.855, 0.863 |
| governs | 0.901, 0.856 | 0.849, 0.758 |

OpenAI gave many answers at exactly 0 or 1. For example, 173 of the 531 development governs answers were 0 or 1.
At the Jev threshold P>=0.8, OpenAI suggested 11.9% of the incorrect governs pairs on development, compared with 1.4% for Jev.

### Cost

| set | requests | input tokens | dollars |
|---|---|---|---|
| development | 1,131 | 874,135 | 0.087 |
| holdout | 505 | 337,758 | 0.034 |
| total | 1,636 | 1,211,893 | 0.121 |

OpenAI gave 0 output tokens, and the price has no output charge.
On the scored rows (one row for each id), Jev used 1,154,587 input tokens on development and 455,449 on holdout.
OpenAI used 872,766 and 336,870 on the same rows. The two models count tokens differently. Thus the counts do not compare the size of the input.
The median OpenAI time was 0.13 to 0.14 seconds for each request.

### Decision

`decision.OPENAI` gives values for owner (0.99), sentence (0.3), flow (0.05), and governs (0.99).
Mis-fold, plan, triage, the pair question, and the move question have no value. A command does not send these questions to OpenAI, and it gives the cause.
`jev flow` stays out of the default kinds for the two providers.

The OpenAI owner threshold gives one component for 9.5% of modules, compared with 55.5% for Jev.
The OpenAI governs threshold found fewer governed components than Jev, and it suggested more incorrect pairs on holdout (6.0% compared with 0.9%).
Thus OpenAI is an alternative provider, not a replacement for Jev.
All measured repositories are Python repositories. A TypeScript measurement is necessary before these values apply to TypeScript.

## Does the flow context from the call-site fact satisfy the flow acceptance value? (2026-10-13)

The flow context experiment above found two arms that satisfy the acceptance value: `calls` and `targets`.
These arms used text patterns for Python and TypeScript syntax. Thus they did not go into `src/`.

This work adds the `call_sites` fact to each language adapter.
The Python adapter reads the fact with `ast`. The TypeScript adapter reads it with tree-sitter.
`audit_code.code_between` selects the flow context from this fact only.
This experiment measures that selector on the same rows.
`call_site_context.py` has the method and the acceptance value in its docstring.

### Method

The rows are the same 160 development rows and 96 holdout rows as the flow context experiment.
Each row sends the shipped question (`audit.VERIFY_Q`) and the shipped `ends`. Only the `code` text is new.

The cached facts have format 2. They do not have the `call_sites` fact.
Thus `build` writes the fact with the Python adapter from the source of the cached facts.
`build` stops if a source file is not the file that the cached facts give.

The cached facts of format 2 give the first name part as `package`. The current `audit.modules_by_card` reads `package` as the folder package.
Thus `build` writes the folder package into each cached record. Then it compares the module claims with the claims of the flow context experiment.

The claims are the same for all 8 maps.
Before this correction, 22 of the 32 Mealie rows had an empty context. No Jev request was sent before the correction.

The context has the lines of `targets`, but the fact gives the lines:

1. The import lines and the lines that use an imported name.
2. The lines that read a property of a local name that gets its value or type from an imported name.
3. The line of the named function or method that contains each of these lines.
4. At most 12 lines from the facts: the signature of each imported function, class, or method that a selected line uses, and the first sentence of each target module description.

The context has at most 60 source lines. Each line has 160 characters at most.

If the context of a row is empty, the shipped audit sends no question for the flow.
The command does not send such a row. The score counts it as not caught and not flagged.

### Acceptance value

The acceptance value was written before the first Jev request. It is the value that `calls` and `targets` satisfied:

- The development set gives the threshold. The holdout set does not.
  The candidate thresholds are 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, and 0.5.
  The threshold is the largest candidate that flags at most 2 of 80 correct development claims.
- At that threshold, the development catch rate must be 50% or more.
- At that threshold, the difference between the holdout catch rate and the development catch rate must be 10 points or less.
- At that threshold, the selector can flag at most 2 of 48 correct holdout claims.
- If the selector satisfies the value, `audit_code.code_between` uses the fact. If it does not, `audit_code.py` does not change.
- The result does not put `jev flow` into `DEFAULT_KINDS`, because no TypeScript row set is available.

All the repositories in the two sets are Python repositories.
Thus the result does not show the behavior on TypeScript.

### Commands

    uv run --project bench/jev python bench/jev/call_site_context.py build
    uv run --project bench/jev python bench/jev/run.py flowctx_facts
    SYSTEMAP_TRUST_MODEL_CODE=1 JEV_SET=holdout JEV_ROOT_SCORECARD=../scorecard uv run --project bench/jev python bench/jev/call_site_context.py build
    JEV_SET=holdout uv run --project bench/jev python bench/jev/run.py flowctx_facts
    uv run --project bench/jev python bench/jev/call_site_context.py score > bench/jev/results/flowctx-facts-report.txt

### Results

The Jev requests were sent on 2026-10-13. The selector operated one time on development, and then one time on holdout.
The selector did not change between the development requests and the holdout requests.
All 256 answers came from the model `jev-1.13.0`, with 0 errors.
No row had an empty context.
`results/flowctx-facts-report.txt` has the full output.

The selector satisfies the acceptance value.
The table gives the figures at the threshold that the development set selected, 0.2.
The `calls` and `targets` rows give the results of the flow context experiment.

| selector | threshold | dev caught | dev flagged | holdout caught | holdout flagged | points | result |
|---|---|---|---|---|---|---|---|
| `call_sites` fact | 0.2 | 48/80 (60.0%) | 2/80 (2.5%) | 25/48 (52.1%) | 1/48 (2.1%) | -7.9 | pass |
| `calls` (text patterns) | 0.2 | 48/80 (60.0%) | 2/80 (2.5%) | 26/48 (54.2%) | 0/48 (0.0%) | -5.8 | pass |
| `targets` (text patterns) | 0.2 | 47/80 (58.8%) | 2/80 (2.5%) | 28/48 (58.3%) | 0/48 (0.0%) | -0.5 | pass |

The AUC was 0.904 on development and 0.936 on holdout.
The median code length was 1,165 characters on development and 1,374 characters on holdout.

The cost was 256 Jev requests: 279,288 input tokens and 5,120 output tokens.
The median input was 871 tokens on development and 978 tokens on holdout. The median time was 0.21 seconds.

### Decision

`audit_code.code_between` uses the `call_sites` fact. The threshold 0.2 in `decision.JEV` does not change.
`jev flow` stays out of `DEFAULT_KINDS`, because no TypeScript row set is available.

A TypeScript row set must have a map with flows and flow sentences for each repository, as the Python rows have.
The bench data has no map of Hono, Ky, or Zod, and no checkout of these repositories. Thus no TypeScript rows were made.

The `decision.OPENAI` flow value (0.05) was measured with the earlier context. A new OpenAI measurement with this context is necessary.

## Does OpenAI satisfy the flow acceptance value with the context from the call-site fact? (2026-10-13)

The `decision.OPENAI` flow value (0.05) came from the earlier flow context: the lines that use an imported name.
At this time, `audit_code.code_between` selects the context from the `call_sites` fact. Thus the earlier value does not apply.

Before the first OpenAI request of this experiment, `decision.OPENAI.flow_below` became None.
Thus OpenAI did not answer the flow question until this experiment gave a value.
`openai_flow_context.py` has the method and the acceptance value in its docstring.

### Method

The rows are the rows of the call-site context experiment above: 160 development rows and 96 holdout rows.
Each row has the same id, claim, label, question, and `code` text that Jev answered.
`call_site_context.py build` makes the rows again from the cached facts and the source.
`run.py --provider openai flowctx_facts` sends each row to OpenAI one time, as one request.
The request body comes from `systemap.openai_provider.request_body`, as in the earlier OpenAI experiment.

`openai_flow_context.py score` uses the functions of `provider_eval.py`. Thus the selection rule is the flow rule of the earlier OpenAI experiment.
Each figure uses only the rows that the two providers answered.
A row with an empty context gets no request. It counts as not caught and not flagged for the two providers.

### Acceptance value

The acceptance value was written before the first OpenAI request of these rows. It is the flow rule in `provider_eval.py`:

- The development set gives the threshold. The holdout set does not.
- The budget is the fraction of correct development claims that Jev flags at the shipped Jev threshold, P<0.2, on the same rows.
  The recorded Jev figure is 2 of 80 (2.5%).
- The threshold is the largest candidate where OpenAI flags a fraction of the correct development claims that is at most the budget.
  The candidates are 0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, and 0.5.
- If no candidate satisfies the rule, the flow question type does not satisfy the value.
  If the selected threshold catches no incorrect development claim, the flow question type does not satisfy the value.
- At the selected threshold, the holdout catch rate must be 10 points or less from the development catch rate.
  The holdout flag rate must also be 10 points or less from the development flag rate.
- If the flow question type satisfies the value, `decision.OPENAI.flow_below` gets the selected threshold.
  If it does not satisfy the value, `decision.OPENAI.flow_below` stays None, and OpenAI does not answer the flow question.

All the repositories in the two sets are Python repositories.
Thus the result does not show the behavior on TypeScript.

### Commands

The key comes from the keychain only for the command. No command writes the key.

    uv run --project bench/jev python bench/jev/call_site_context.py build
    SYSTEMAP_TRUST_MODEL_CODE=1 JEV_SET=holdout JEV_ROOT_SCORECARD=../scorecard uv run --project bench/jev python bench/jev/call_site_context.py build
    OPENAI_API_KEY="$(security find-generic-password -a "$USER" -s openai-api-key-systemap -w)" uv run --project bench/jev python bench/jev/run.py --provider openai flowctx_facts
    OPENAI_API_KEY="$(security find-generic-password -a "$USER" -s openai-api-key-systemap -w)" JEV_SET=holdout uv run --project bench/jev python bench/jev/run.py --provider openai flowctx_facts
    uv run --project bench/jev python bench/jev/openai_flow_context.py score > bench/jev/results/openai/flowctx-facts-report.txt

### Results

The OpenAI requests were sent on 2026-10-13. The development rows went one time, and then the holdout rows went one time.
No rule, row, or request form changed between the two request sets.
Before the requests, `call_site_context.py build` made the rows again. The rows of the two sets were the same as the rows that Jev answered.

There were 256 requests: 160 on development and 96 on holdout. There were 0 errors and 0 refusals.
All answers came from the model `gpt-6-luna`. No row had an empty context.
`results/openai/flowctx-facts-report.txt` has the full output.

The flow question type satisfies the acceptance value at P<0.02.
The table gives the OpenAI figures at that threshold, and the Jev figures at the shipped Jev threshold P<0.2.
The scorer calculated the Jev figures again from the recorded Jev answers. They agree with the call-site context experiment.

| provider | threshold | figure | development | holdout | points | result |
|---|---|---|---|---|---|---|
| OpenAI | P<0.02 | caught | 27/80 (33.8%) | 18/48 (37.5%) | +3.7 | satisfied |
| | | flagged | 2/80 (2.5%) | 3/48 (6.2%) | +3.8 | satisfied |
| Jev | P<0.2 | caught | 48/80 (60.0%) | 25/48 (52.1%) | -7.9 | |
| | | flagged | 2/80 (2.5%) | 1/48 (2.1%) | -0.4 | |

At P<0.05, OpenAI flagged 4 of 80 correct development claims (5.0%). This figure is more than the budget of 2 of 80.
Thus the rule selected P<0.02.

The AUC of OpenAI was 0.881 on development and 0.862 on holdout.
The AUC of Jev on the same rows was 0.904 and 0.936.

At P<0.05 with the earlier context, OpenAI caught 37 of 80 (46.2%) on development and flagged 2 of 80 (2.5%).
At P<0.05 with the context from the call-site fact, it caught 32 of 80 (40.0%) and flagged 4 of 80 (5.0%).

### Cost

| set | requests | input tokens | dollars |
|---|---|---|---|
| development | 160 | 125,383 | 0.013 |
| holdout | 96 | 88,559 | 0.009 |
| total | 256 | 213,942 | 0.021 |

OpenAI gave 0 output tokens. The price is $0.10 for each 1M input tokens, with no output charge.
The median input was 664 tokens on development and 743 tokens on holdout. The median time was 0.14 seconds for each request.

### Decision

`decision.OPENAI.flow_below` is 0.02.
`jev flow` stays out of `DEFAULT_KINDS` for the two providers, because no TypeScript row set is available.
At its threshold, OpenAI catches 33.8% of incorrect claims on development. At its threshold, Jev catches 60.0%.
Thus Jev stays the better provider for the flow question.

## Which bench scripts did not import on 2026-10-13, and what changed?

Each bench script must import with no error. On the `integrate/wave-3` branch, four scripts did not import, because `src/` removed or moved a name:

| script | error | change |
|---|---|---|
| `flow_context.py` | `audit_code._bindings` does not exist, and `audit_code.code_between` has a different signature | `import_context.py` keeps the earlier selector. `flow_context.py` also writes the folder package into each cached record, as `call_site_context.py` does. |
| `draft.py` | `extract.is_empty_marker` does not exist | The script imports `source_facts.is_empty_marker`. |
| `moves.py` | `extract.is_empty_marker` does not exist | The script imports `source_facts.is_empty_marker`. |
| `paths.py` | `extract.entry_label` does not exist | The script imports `source_facts.entry_label`. |

`flow_context.py build` made the rows of the four arms again on the two sets.
The 8 row files were the same as the files that Jev answered in the flow context experiment.
`flow_context.py score` gave the same output as `results/flowctx-report.txt`.
Thus the script stays, and `call_site_context.py` does not replace it. The two scripts measure different selectors.

`source_facts.is_empty_marker` reads the `empty_marker` fact. The cached facts of format 2 do not have this fact.
Thus, for these facts, the function finds no empty package marker. The earlier `extract.is_empty_marker` found the markers from the file name and the record.

`common.py` and `call_site_context.py` used the new function before this change. After this change, `draft.py` also uses it with the facts of each first map.
A new `draft.py` result can be different from the recorded result. The script was not operated again.

`drift_head.py` operates when Python imports it. The `repo-maintenance-*` folders in `bench/scratch` are necessary.
Without these folders, the import stops with `StopIteration`. With these folders, the import completed.

## Does TypeScript source discovery stay fast with a large node_modules folder? (2026-10-13)

`bench/typescript_discovery.py` makes two fixtures with 40 modules in the package root `packages/web`.
One fixture also has 40,000 files in `packages/web/node_modules`.
The acceptance value was written before the change: the median `extract.build` time with node_modules must be at most 1.2 times the time without node_modules.
Each value is the median of 5 runs on one macOS computer with Python 3.11.10.

| revision | build without node_modules (s) | build with node_modules (s) | ratio | `source_paths` with node_modules (s) |
|---|---|---|---|---|
| `origin/main` (d4b1514), first run | 0.0269 | 0.317 | 11.784 | 0.2842 |
| `origin/main` (d4b1514), second run | 0.0345 | 0.4325 | 12.536 | not recorded |
| `origin/main` (d4b1514), third run | 0.0343 | 0.3859 | 11.251 | not recorded |
| `fix/ts-projects`, first run | 0.0365 | 0.0372 | 1.019 | 0.0004 |
| `fix/ts-projects`, second run | 0.0369 | 0.0372 | 1.008 | not recorded |

On `origin/main`, `TypeScriptLanguage.source_paths` did one `rglob` walk for each source suffix, and each walk went into node_modules.
The change uses `source_files`, which does not go into the `SOURCE_SKIP` folders.
The result satisfies the acceptance value.

## Does the Git tree reader keep a large blob out of memory? (2026-10-13)

Codex result change-14: `delta_git.write_tree` read all blobs of a commit into one byte string, and then copied each blob.
The change reads each blob in parts of 1 MiB and writes the parts to the file.
A thread sends the blob requests. Thus the reader does not stop for each request.

Fixtures: `small` has 20 modules. `blob` has the same 20 modules and one file of 256 MiB of random bytes in `assets/`.
`many` has 2000 modules. Each value is the median of 3 runs of `delta_git.facts_at` in a new process.
"Memory increase" is the increase of the peak resident memory during the call.

Acceptance (written before the change): for `blob`, the memory increase is at most 64 MiB above the increase for `small`.
For each fixture, the median time after the change is at most 1.2 times the median time before the change.

Command: `uv run python bench/jev/tree_reader_memory.py`. The base and the change operated two times each, in alternate order.
The table also gives two earlier runs of the base.

| fixture | base time (ms), 4 runs | change time (ms), 4 runs | time ratio of the medians | base memory increase | change memory increase |
|---|---|---|---|---|---|
| `small` | 25, 25, 26, 28 | 25, 25, 27, 43 | 1.02 | 0.5 MiB | 0.4 to 0.5 MiB |
| `blob` | 189, 239, 242, 246 | 108, 109, 124, 191 | 0.48 | 888 to 898 MiB | 2.5 to 4.5 MiB |
| `many` | 1562, 1571, 1774, 2028 | 1551, 1694, 1808, 1819 | 1.05 | 10.6 to 11.1 MiB | 10.0 to 10.3 MiB |

For `blob` minus `small`, the change gives 2.0 to 4.1 MiB. The base gave 887 to 898 MiB.
The result satisfies the two acceptance values.
A first version of the change sent one request and read one blob at a time. For `many`, its times were 2044 and 2306 ms.
That version did not satisfy the time value. Thus the change uses a thread for the requests.

The tree reader continues to write each blob of the commit, also the blobs that the extraction does not read.
Codex proposed a selection of the necessary files. The selection is not in the change, because the language adapters do not give a list of the extraction inputs before the extraction.

## Does a render with nested maps compare the source one time? (2026-10-13)

Codex result change-20: `change.for_page` compared all changed source files again for each map.
The change makes the source comparison one time with `change.source_change` and gives it to each map.
The change also reads the blobs of each side with one Git process. Before the change, each file had one `git show` process.

Fixture: 200 modules and 200 test files. The head commit adds one function to each module and one test to each test file.
The script uses `change.for_page` for K maps with the same model. Each value is the median of 3 runs in a new process.

Acceptance (written before the change): the median time for K = 5 is at most 1.5 times the median time for K = 1.
The peak resident memory increase for K = 5 is at most 1.2 times the value before the change.

Command: `uv run python bench/jev/change_reuse.py`.

| run | K = 1 time | K = 5 time | ratio | K = 5 memory increase |
|---|---|---|---|---|
| base | 3795 ms | 18649 ms | 4.91 | 3.6 MiB |
| change, first run | 332 ms | 394 ms | 1.19 | 2.3 MiB |
| change, second run | 263 ms | 262 ms | 1.00 | 2.3 MiB |

The full test suite operated at the same time as the first run of the change.
The result satisfies the two acceptance values.
The test `test_a_render_with_nested_maps_parses_each_changed_file_once_for_each_side` counts the surface parses of `systemap render --base` with three maps.

## Does the label script read the mark boxes on each pan frame? (2026-10-13)

Follow-up followup-labels-time: commit 57f8180 (Codex result schematic-5) put the boxes of the sequence marks in the label key.
Thus each relabel call read the box of each mark, also when no mark changed.

The repair keeps the boxes in drawing units.
A MutationObserver on the marks, on the page root and on the body removes the kept boxes. A font load also removes them.
Without MutationObserver, each call reads the boxes, as before the repair.

Acceptance (written before the measurement): the median time of one relabel call with a sequence is at most 1.2 times the time before 57f8180.
The pan case is the acceptance case.

The script makes the self-map page three times, each with a different start of the relabel function.
The three functions are `before` (57f8180^), `read` (57f8180), and `current`.
Headless Chrome opens each page at 1600 by 900 pixels.
In the pan case, a change to the transform of the map view occurs before each call. The script subtracts the time of the transform changes.
In the static case, the calls occur with no change between them.
Each value is the median of 11 samples of 2000 calls.

Command: `uv run python bench/jev/relabel_time.py`.

| State | Case | Marks | before (us) | read (us) | current (us) | current / before |
|---|---|---|---|---|---|---|
| whole route | pan | 6 | 5.45 | 9.80 | 5.25 | 0.96 |
| whole route | static | 6 | 1.90 | 6.10 | 2.00 | 1.05 |
| step 1 | pan | 6 | 5.45 | 9.65 | 5.20 | 0.95 |
| step 1 | static | 6 | 1.95 | 6.15 | 2.00 | 1.03 |

The `read` function did not satisfy the acceptance value: 1.80 times `before` in the pan case, and 3.2 times in the static case.
The `current` function satisfies the acceptance value.
Four earlier measurements with 5 samples gave `before` pan values from 5.35 to 13.30 us. Thus the script now uses 11 samples.
The table gives the first measurement with 11 samples. Other processes operated on the computer during the measurements.
The second measurement gave 1.19 (whole route) and 0.88 (step 1) for `current / before` in the pan case. The third gave 0.96 and 0.95.
Thus the margin to the acceptance value is small when the computer has a high load.
Headless Chrome draws with software rendering. The absolute times are not the times of a browser on a desktop computer.

The test `test_a_pan_does_not_read_the_mark_boxes_again` counts the box reads under the Node page driver.
The driver now has a MutationObserver.

## Does TypeScript language detection stay fast with a large node_modules folder? (2026-10-13)

Result `followup-detect`: `TypeScriptRepository.detect` and `discover_typescript_roots` used `rglob`.
Thus they read each folder in node_modules, and only then removed its files.
The change uses `source_files`, which does not enter the `SOURCE_SKIP` folders.

`bench/typescript_detect.py` makes two fixtures, each with and without 40,000 files in node_modules.
In `config_only`, the root has tsconfig.json and no TypeScript source outside node_modules.
In `workspace`, the package root `packages/web` has 40 modules in `src` and the node_modules folder.
The acceptance value was written before the change: for each call, the median time with node_modules must be at most 1.2 times the median time without node_modules.

Each value is the median of 11 samples on one macOS computer with Python 3.11.10.
One sample is the mean time of one call in a loop of at least 20 ms.
The first version of the script timed one call in each sample. After the change, its ratios were from 0.69 to 1.49 between runs, because one call takes approximately 30 microseconds.
Thus the loop replaced the single call. The acceptance value did not change.

| revision | call | without node_modules (ms) | with node_modules (ms) | ratio |
|---|---|---|---|---|
| base (06468a2), first run | `discover_typescript_roots(config_only)` | 0.060 | 234.7 | 3911.65 |
| base (06468a2), first run | `detect(config_only)` | 0.073 | 233.2 | 3214.40 |
| base (06468a2), first run | `detect(config_only, [config_only])` | 0.048 | 130.6 | 2708.61 |
| base (06468a2), first run | `detect(workspace, [packages/web])` | 0.052 | 134.6 | 2600.73 |
| base (06468a2), second run | the four calls, in the same order | 0.060, 0.074, 0.049, 0.052 | 233.3, 230.7, 130.2, 133.9 | 3868.60, 3124.35, 2671.27, 2582.20 |
| change, first run | the four calls, in the same order | 0.0277, 0.0410, 0.0238, 0.0405 | 0.0285, 0.0421, 0.0245, 0.0412 | 1.029, 1.025, 1.029, 1.017 |
| change, second run | the four calls, in the same order | 0.0279, 0.0417, 0.0241, 0.0416 | 0.0285, 0.0424, 0.0246, 0.0417 | 1.022, 1.016, 1.020, 1.005 |
| change, third run | the four calls, in the same order | 0.0281, 0.0414, 0.0241, 0.0414 | 0.0286, 0.0424, 0.0246, 0.0416 | 1.020, 1.023, 1.021, 1.005 |

The results of the calls did not change. The result satisfies the acceptance value.
The test `tests/test_typescript_detect_skip.py` records each folder that the calls open, and it finds no folder in node_modules, .git, or .venv.

## Does the live watcher stay fast when the adapter gives its configuration files? (2026-10-13)

Result `followup-extends`: the language adapter now gives the configuration files that it reads (`config_paths`).
The TypeScript adapter follows `extends` and `references`, so the watcher reads each tsconfig file at each scan.
The adapter also walks the source folders for its configuration names. Thus the source folders get two walks.

Acceptance (written before the change): on this repository, the median time of `live_watch.watched` after the change is at most 2 times the median before the change.
Each value is the median of 31 calls on one macOS computer.

| revision | watched files | median (ms) |
|---|---|---|
| base (06468a2) | 277 | 1.44 |
| change, first run | 279 | 1.74 |
| change, second run | 279 | 1.75 |

The ratio is 1.21. The result satisfies the acceptance value.
The change added two source modules between the two measurements. On the same tree, the base and the change give the same 279 paths.

## Does the Python file list stay fast with a large node_modules folder? (2026-10-13)

Result `followup-python-paths`: `python_repo.python_paths` used `rglob`.
Thus it read each folder in node_modules, .venv, and the other skipped folders, and only then removed their files.
The change uses `os.walk` and does not go into the `PYTHON_SKIP` folders. The TypeScript detection uses the same method.

`bench/python_paths.py` makes two fixtures, each with and without 40,000 files in node_modules.
In `package`, the package root `src/app` has 40 modules and the node_modules folder. Half of the files in node_modules are `.py` files.
In `no_source`, the folder has Python files only in node_modules.
The acceptance value was written before the change: for each call, the median time with node_modules must be at most 1.2 times the median time without node_modules.

Each value is the median of 11 samples on one macOS computer with Python 3.11.10.
One sample is the mean time of one call in a loop of 20 ms or more.

| revision | call | without node_modules (ms) | with node_modules (ms) | ratio |
|---|---|---|---|---|
| base (b168c9c), first run | `list(python_paths(package/src/app))` | 0.2294 | 101.8 | 443.78 |
| base (b168c9c), first run | `detect(package, [package/src/app])` | 0.0283 | 0.0289 | 1.02 |
| base (b168c9c), first run | `detect(no_source, [no_source])` | 0.0227 | 101.7 | 4472.93 |
| base (b168c9c), second run | the three calls, in the same order | 0.2282, 0.0281, 0.0228 | 100.1, 0.0287, 97.93 | 438.81, 1.019, 4286.85 |
| change, first run | the three calls, in the same order | 0.1583, 0.0308, 0.0139 | 0.1571, 0.0337, 0.0147 | 0.992, 1.094, 1.058 |
| change, second run | the three calls, in the same order | 0.2065, 0.0342, 0.0150 | 0.1597, 0.0323, 0.0143 | 0.773, 0.946, 0.953 |
| change, third run | the three calls, in the same order | 0.1706, 0.0303, 0.0148 | 0.1632, 0.0318, 0.0143 | 0.957, 1.047, 0.967 |

For `detect(package, [package/src/app])`, the base also did not read node_modules, because the call stops at the first Python file.
The results of the calls did not change. The result satisfies the acceptance value.
On this repository, the base and the change give the same 138 Python files for the package root `src/systemap`.
The test `tests/test_python_paths_skip.py` records each folder that the calls open, and it finds no folder with a `PYTHON_SKIP` name.

### The test file list (2026-10-13)

`python_tests.test_files` also used `rglob("test_*.py")` in each test folder, and only then removed the paths in skipped folders.
The change uses `python_paths(test_dir, "test_*.py")`. It sorts the result, thus the order of the list does not change.
The acceptance value was written before the change: the same ratio of 1.2 or less, for the new call `test_files(tests, ("tests",), ())`.
In the new fixture `tests`, the folder `tests` has 40 test modules and the node_modules folder. Half of the files in node_modules are `test_*.py` files.
The script now has four calls. The fourth value in each cell is the `test_files` call. The base is 8868b3e, the commit of the `python_paths` change.

| revision | without node_modules (ms) | with node_modules (ms) | ratio |
|---|---|---|---|
| base (8868b3e), first run | 0.1434, 0.0292, 0.0165, 0.3015 | 0.1412, 0.0295, 0.0130, 113.8 | 0.985, 1.010, 0.787, 377.36 |
| base (8868b3e), second run | 0.1432, 0.0283, 0.0123, 0.2115 | 0.1398, 0.0269, 0.0124, 109.9 | 0.976, 0.950, 1.002, 519.63 |
| change, first run | 0.1395, 0.0269, 0.0121, 0.1373 | 0.1373, 0.0272, 0.0126, 0.1384 | 0.984, 1.012, 1.038, 1.008 |
| change, second run | 0.1390, 0.0264, 0.0120, 0.1385 | 0.1391, 0.0272, 0.0124, 0.1401 | 1.000, 1.029, 1.033, 1.012 |
| change, third run | 0.1463, 0.0279, 0.0119, 0.1387 | 0.1413, 0.0280, 0.0125, 0.1389 | 0.966, 1.001, 1.045, 1.001 |

The results of the calls did not change. The result satisfies the acceptance value.
On this repository, the base and the change give the same 136 test files in the same order.
The other `glob` calls in the Python adapter do not go into a skipped folder by default.
`_loose_files` uses `glob("*.py")` in each folder of `config.walk`, and `config.walk` does not go into the skipped folders.
`workspace_members` uses the `[tool.uv.workspace] members` patterns of the user. The change keeps the selection of uv for these patterns.

## Assurance levels on the page (2026-10-18)

Issue 102 adds the assurance level and the freshness of each component, flow, invariant, and import rule to the map page.
The sample page of `tests/test_render.py` has a size limit.

Acceptance, written before the measurement: the limit increases only by the measured cost of the levels.
The limit stays a whole number of KiB, as in "Map page font".

Method: `page.build` for the sample system with `{"has_change": False}`, at origin/main 4d2b030 and on the branch.
The page records only `level`, `freshness`, and `basis`. The page has the text of each level and basis one time.

| revision | sample page (bytes) | limit (bytes) | space |
|---|---|---|---|
| base (4d2b030) | 329,623 | 329,728 (322 KiB) | 105 |
| first form, with the full text in each record | 333,251 | 329,728 (322 KiB) | -3,523 (fail) |
| change, with the text one time | 331,990 | 332,800 (325 KiB) | 810 |

The base had 105 bytes of space. Thus the levels could not pass the earlier limit.
The levels cost 2,367 bytes. The new limit, 325 KiB, is the next whole KiB above the measured page (324.2 KiB).
The maintainer must accept or refuse this new limit.

## The pull request summary for reviewers (2026-10-18)

Issue 99 adds the architecture summary to `systemap delta --comment FILE`.
The workflow from `init` writes the summary as one pull request comment.

### The length of the summary

`bench/pr_summary_length.py` writes the summary for five changes and counts the lines, the words, and the characters after the marker line.
Acceptance, written before the measurement: a change without an architectural effect gives one line.
Each summary has a maximum of 26 lines. The row limit of 5 rows and one count row in each part gives this maximum.

| summary | lines | words | characters |
|---|---|---|---|
| systemap, base HEAD (b6c6322) | 1 | 11 | 68 |
| systemap, base 4d2b030 | 12 | 106 | 767 |
| systemap, base b611ede~1 | 19 | 156 | 1115 |
| systemap, base 0ef6399 | 19 | 156 | 1115 |
| two-card fixture, base HEAD~1 | 11 | 109 | 669 |

The head of each systemap row is b6c6322 with the model on disk. The result satisfies the acceptance value.
The bases b611ede~1 and 0ef6399 give the same summary, because the map and the contract did not change between them.
Two summaries used the row limit. In each, 12 changed invariants gave 5 rows and one count row, and 10 changed map items also gave 5 rows and one count row.
This repository has no import rules. Thus its rows give `Rules: none`.

### The reviewer test (not done)

The issue gives a test with persons. With the summary, reviewers must tell the architectural effect of a pull request faster and more accurately.
This test is not done. A coding agent cannot do it. Thus there is no result.

The plan, written before the test:

- Persons: 6 or more reviewers who know Python and do not know the test repository.
- Tasks: 8 pull requests of one repository with a map. 4 change a boundary: a new flow, a removed flow, an import against a rule, or a changed contract rule. 4 change no boundary.
- Each reviewer does 4 tasks with the summary and 4 without it. The assignment of the two sets changes from one reviewer to the next.
- Each reviewer writes the architectural effect in one or two sentences. A second person scores each answer as correct or incorrect against a key that was written before the test.
- Measurement: the time from the start of the task to the answer, and the score.

Acceptance value: with the summary, the median time is at most 0.7 times the median time without it.
Also, the share of correct answers with the summary is equal to or more than the share without it.
If the test does not satisfy the two values, record the result here and change or remove the summary.
The maintainer must accept or change the value 0.7. No measurement gives it. The issue gives a target of about 30 seconds for each pull request.

## The route search of the group lines on a large map (2026-10-26)

Findings perf-1 and uiperf-3: at commit d90d08e, the map page did the route search of the flow-group lines for all layers in one idle callback.
On a page with 72 components, that callback blocked the browser for more than 10 s.
If the search goes later, the freeze occurs at the first click on a layer.

The change moves the route search to `page_group_lines.py`.
The search keeps the shapes for each pair of places and uses only the items near each segment.
The work for each layer goes in small parts in the idle time of the browser.
If the reader selects a layer before its lines are ready, the search continues for 120 ms at most.
If the lines are not ready after this time, the map shows the layer without group lines.
The idle work then does that layer first and draws its lines.

Acceptance, written before the measurement: at 1x CPU on the page with 72 components, the longest task of the load is less than 500 ms.
The first click on each layer button takes less than 500 ms.
The page of this repository is not slower than before.
The group lines and badges are byte-identical to the lines and badges of d90d08e.

Method: three map pages, made with the worktree code and with d90d08e.
`repo` is this repository. `f36` and `f72` are generated systems with 36 and 72 components.
Headless Chromium opens each page at 1440 by 900 pixels.
The load ends when the page has no long task for 1.5 s.
A click time is the time from the click to two animation frames.
The scripts are in the scratch folder `p1-groups`: `measure.js`, `bench.js`, `count.js`, `steps.js`, `deferred.js` and `verify_all.sh`.

### Load and layer clicks (ms)

Each cell gives the values of three runs. "Load" is the longest task of the load. "Click" is the longest first click on a layer button.

| page | d90d08e load | d90d08e click | change load | change click |
|---|---|---|---|---|
| repo | 101, 124, 161 | 129, 153, 128 | 175, 151, 207 | 154, 160, 217 |
| f36 | 1103, 1207, 1130 | 62, 67, 90 | 209, 239, 223 | 82, 85, 87 |
| f72 | 11610, 10079, 10587 | 230, 212, 187 | 217, 634, 578 | 279, 288, 271 |

In the first measurement, two f72 load values were more than 500 ms: 634 and 578.
A second measurement of f72 with five runs gave the load values 255, 236, 224, 216 and 455 ms, and the click values 242, 232, 257, 264 and 208 ms.
With the idle work turned off, the f72 load has long tasks to 211 ms and 302 ms in two runs. These tasks are not a part of the route search.
The longest single part of the idle work on f72 was 11.9 ms and 14.6 ms in two runs, in 672 parts.
Thus the acceptance value for the load is satisfied in the second measurement, but not in two runs of the first measurement.
The longest load task of f72 has a variance that is not from the route search. A measurement on a computer with no other load is necessary.

If the reader clicks a layer at once after the load, the f72 click took 294 to 309 ms. The click values of the other measurements are less than 500 ms.
On the repo page, the change values are up to 64 ms higher than the d90d08e values.
In all repo runs, the longest click is on the judge layer. That layer has no group lines, thus the route search does not operate on it.
A measurement with more runs is necessary to show if this difference is real. Other processes operated on the computer during the measurements.

### The route search alone

`bench.js` times the full search of each layer in a new page. The values are the minimum and the median of the runs, in ms.

| page, layer | d90d08e min | d90d08e median | change min | change median |
|---|---|---|---|---|
| f72, data | 3483 | 3703 | 802 | 862 |
| f72, control | 2889 | 2969 | 356 | 398 |
| f72, all | 4164 | 4205 | 315 | 359 |

`count.js` counts the calls of `cost()`:

| page, layer | groups | d90d08e | change |
|---|---|---|---|
| repo, data | 13 | 10,535 | 1,389 |
| repo, all | 15 | 10,543 | 1,397 |
| f72, data | 144 | 1,236,270 | 76,823 |
| f72, control | 141 | 1,160,896 | 67,563 |
| f72, all | 184 | 1,582,529 | 92,228 |

The test `tests/test_group_line_work.py` counts the calls of `cost()` under the Node page driver, with a bound of 12,000 calls.

### The lines are the same

`verify_all.sh` writes the points of each group line and badge, and the drawn path of each line, for each layer of the three pages.
The data of the change is byte-identical to the data of d90d08e for repo, f36 and f72.
A click on a layer before its lines are ready gives the same lines as d90d08e, after the idle work.
The three SVG figures of this repository are byte-identical. On each page, the only changed lines are lines of the group script.

### Page size

The new script is longer. The compact group script changes from 27,893 bytes to 31,358 bytes.
The sample page of `tests/test_render.py` changes from 331,990 bytes to 335,455 bytes, an increase of 3,465 bytes.
The earlier limit of 325 KiB (332,800 bytes) had 810 bytes of space. Thus the change cannot pass the earlier limit.
The new limit, 328 KiB (335,872 bytes), is the next whole KiB above the measured page (327.6 KiB).
The maintainer must accept or refuse this new limit.

## Map movement, layer switch and load (2026-10-26)

Findings uiperf-1, perf-2, perf-6, uiperf-2 and perf-5: each frame of a wheel zoom or a camera tween wrote the drawing transform.
Each write caused a layout of all of the map. Findings uiperf-4 and perf-4: a layer switch read a line length after each mask write.
Finding uiperf-5: at load, the page scripts started transitions on about 1,600 lines and labels.

The change has these parts:

- During a wheel, pinch, drag or camera tween, a CSS transform on the HTML element around the map (`.stage`) shows the view.
  At the end of the movement, the script writes the drawing transform one time. Then the labels change one time.
  A wheel movement ends 120 ms after the last wheel event. The script keeps the scale and the screen matrix during the movement.
- The zoom readout changes at the end of a movement. A change to the readout during a movement caused a layout of all of the map text.
- `drawLines` reads all lengths and boxes before the first write. It keeps the length and the box of each path for its path data.
- The class `booting` stops all transitions in the map until the second frame after load.
- `apply` does not write a transform that is equal to the current transform.
- The script examines the parent of the wrapper again when the parent changes. The present mode moves the wrapper to a parent that does not clip it.
  In that parent, the script does not move the wrapper. `tests/test_map_movement.py` examines this.

The acceptance values were written before the measurement. At 4x CPU on f72, the median frame interval during wheel input and during a camera tween is less than 33 ms.
At 1x CPU on f72, a layer switch takes less than 150 ms. The longest task of the load is lower than before.
After each interaction, the view transform, the label transforms and the classes are equal to the values before the change.

Method: `repo`, `f36` and `f72` of "The route search of the group lines on a large map", made with 65e5464 and with the change.
Headless Chromium opens each page at 1440 by 900 pixels. Each cell gives the values of two runs.
The scripts are in the scratch folder `p3-pageview`: `p3.js`, `dump.js`, `cmpdump.py`, `cmpout.sh`, `repaint.js` and `tprobe.js`.
"Wheel" is the median rAF interval during 60 wheel events at 8 ms intervals.
"Tween" is the median rAF interval from the start of each of four camera tweens to 300 ms after the start.
"Layer" is the time from the click on a layer button to the next frame, as the median and the maximum of 10 clicks.

### Frame intervals and layer switch (ms)

| page | CPU | 65e5464 wheel | change wheel | 65e5464 tween | change tween | 65e5464 layer median, max | change layer median, max |
|---|---|---|---|---|---|---|---|
| f72 | 1x | 16.7, 16.7 | 16.7, 16.7 | 16.7, 16.7 | 16.7, 16.7 | 118 and 159, 121 and 174 | 99 and 142, 91 and 163 |
| f72 | 4x | 100, 83.3 | 100, 83.3 | 100, 66.6 | 16.7, 16.7 | 652 and 990, 569 and 756 | 607 and 757, 503 and 1110 |
| f36 | 4x | 33.3, 50 | 33.4, 50 | 33.3, 50 | 16.7, 16.7 | 237 and 376, 277 and 346 | 195 and 272, 185 and 289 |
| repo | 4x | 33.3, 33.3 | 33.3, 33.3 | 33.3, 33.3 | 16.7, 16.7 | 152 and 238, 125 and 193 | 137 and 182, 96 and 134 |

The layout count during the four tweens on f72 at 4x fell from 38 and 46 to 10 and 10.
During the 60 wheel events on f72 at 4x, it fell from 46 and 53 to 23 and 25.

The acceptance value for the tween is satisfied. The acceptance value for the wheel is not satisfied: the median stays at 83 to 100 ms on f72 at 4x.
A Chrome trace of the wheel input shows one layout in each frame, with 1,270 of 3,475 layout objects dirty.
The f72 map has 644 text elements, thus these objects are the map text. A tween with no input has no such layouts.
A tween with mouse moves over the map has them. Thus the cause is the input with a scale change on the wrapper.
`pointer-events: none` on the map or on the wrapper did not remove the layouts. A wheel step in the next animation frame did not remove them.
An investigation of the Chrome layout of SVG text under a scaled wrapper is necessary.

Thus the change fixes the camera tween (perf-2, perf-6, uiperf-2 and perf-5). For the wheel, uiperf-1 is improved, but it is not fixed. It stays an open item.
A review run of `p3.js` on f72 at 4x CPU used pages that it made again from 65e5464 and from the change.
During the wheel, the median rAF interval fell from 99.9 ms to 66.7 ms, and the 90th percentile fell from 133.4 ms to 100 ms. The layout count fell from 49 to 26.
During the tweens, the median fell from 83.3 ms to 16.7 ms, and the layout count fell from 38 to 10.
The changelog line for this change must use the word "improved" for the wheel. It can use the word "fixed" only for the camera tween.

At 1x on f72, the median of the layer switch satisfies the acceptance value. The maximum of one run (163 ms) does not satisfy it.
The longest task of a switch at 1x on f72 is 65 to 127 ms. Most of the click time is the style and the layout of the map after the class changes on about 900 lines and labels.
The first visit to a layer also includes the route search of the group lines.

### Load (ms)

"Longest" is the longest task of the load. "Sum" is the sum of all long tasks of the load.

| page | CPU | 65e5464 longest | change longest | 65e5464 sum | change sum |
|---|---|---|---|---|---|
| f72 | 1x | 638, 667 | 223, 158 | 1436, 1224 | 401, 271 |
| f72 | 4x | 812, 961 | 896, 663 | 3372, 3394 | 2713, 2283 |
| f36 | 1x | 215, 145 | 124, 72 | 578, 381 | 124, 131 |
| repo | 1x | 88, 106 | 0, 75 | 200, 223 | 0, 75 |

A separate run of three loads on f72 at 1x compared the change with and without the class `booting`.
Without the class, the longest task was 547 to 844 ms. With the class, it was 171 to 259 ms.
The count of SVG elements with an opacity other than 1 after the load stays 900 on f72. These elements are the hidden lines and labels of the other layers.
The load reads (12 `getBoundingClientRect`, 29 `getScreenCTM` and 475 `getBBox` calls on f72) did not change.

### The final state is the same

`dump.js` does 17 or 18 interactions on each page.
These are wheel in and out, ctrl+wheel, drag, a two-finger pinch, two tweens, a selection, a clear, each layer, and a wheel with a selection.
After each interaction, it records the view transform, the label transforms, the classes, the masks and the zoom readout. It also takes two screenshots of the map frame.
For repo, f36 and f72, all records are equal. The screenshots after a full repaint of the map are byte-identical.
The screenshots at the end of each gesture are byte-identical, except the load screenshot of each page and the tween to Fit on f72.
These screenshots differ in 2 to 168 pixels by 1 or 2 of 255 in one color channel. After a full repaint, they are byte-identical. Thus the difference is from the paint history.

The three SVG figures of this repository and `map.json` of the three pages are byte-identical.
Outside the script and style elements, the three pages are byte-identical.

### Page size

The sample page of `tests/test_render.py` changes from 335,455 bytes to 337,959 bytes, an increase of 2,504 bytes.
The earlier limit of 328 KiB (335,872 bytes) had 417 bytes of space. Thus the change cannot pass the earlier limit.
The new limit, 331 KiB (338,944 bytes), is the next whole KiB above the measured page (330.0 KiB).

## The step numbers of a long sequence (2026-10-26)

Finding g1page-1: at commit 65e5464, the place of each step number on the map was a scan of all line points and all marks on the map.
The work increased with the square of the route length, and the sequence script had no step limit.

The change puts the line points and the marks in a grid of 32-unit cells (`GRID_JS` in `page_sequence_script.py`).
A score reads only the items near the box. The score adds the same values in the same order as before.
A sequence with more than 40 steps has numbers on 40 steps only: the first 40 steps of the whole route, or the 40 steps near the current step.
The legend gives these steps. For such a sequence, a number examines about 40 places on its line.

Acceptance, written before the change: at 1x CPU on the page with 72 components and 450 flows, a click on a route of 200 steps takes less than 300 ms.
The marks of each sequence of this repository are byte-identical to the marks of 65e5464.

Method: headless Chromium at 1600 by 900 pixels. A synthetic sequence of N steps uses N different flows.
The time is the synchronous time of `P.journey.route`, `P.journey.start` and one `P.journey.stepBy(1)`.
The scripts are in the scratch folder `p3-pageseq`: `seqperf.js`, `marks.js`, `cmpmarks.py` and `incl.js`.

### Click times (ms)

Each cell gives route / start / step. The change has three runs.

| N | 65e5464 | change, run 1 | change, run 2 | change, run 3 |
|---|---|---|---|---|
| 6 | 134 / 220 / 130 | 85 / 85 / 82 | 95 / 99 / 73 | 82 / 58 / 74 |
| 50 | 2614 / 1483 / 1637 | 75 / 85 / 107 | 86 / 102 / 122 | 66 / 78 / 91 |
| 100 | 6615 / 6521 / 7096 | 120 / 102 / 108 | 125 / 76 / 128 | 83 / 81 / 102 |
| 200 | 27261 / 26186 / 28309 | 187 / 111 / 105 | 128 / 93 / 135 | 117 / 87 / 168 |
| 1000 | not measured | 361 / 228 / 290 | 367 / 198 / 199 | 286 / 185 / 235 |

With the grid only, 200 steps took 828 / 579 / 517 ms.
With the grid and fewer places, but with all numbers, 200 steps took 199 to 504 ms in six runs. Thus the number limit is necessary.
With the grid only, 40 steps took 112 / 96 / 102 ms. This is the limit of 40 steps.

### The marks are the same

`marks.js` writes the lines and marks of the whole route and of each step of each sequence.
For the 15 sequences of this repository (78 views), the data of the change is byte-identical to the data of 65e5464.
On the page with 450 flows, the views of the four sequences of the page and of synthetic sequences of 6 and 25 steps are byte-identical.
The views of a synthetic sequence of 50 steps are different, because of the number limit.
The map.json file and the three SVG figures of this repository are byte-identical. On the page, the only changed lines are lines of the sequence script.

### Page size

The sample page of `tests/test_render.py` changes from 335,455 bytes to 337,306 bytes, an increase of 1,851 bytes.
The earlier limit of 328 KiB (335,872 bytes) had 417 bytes of space. Thus the change cannot pass the earlier limit.
The new limit, 330 KiB (337,920 bytes), is the next whole KiB above the measured page (329.4 KiB).
The maintainer must accept or refuse this new limit.

After the merge with the change of "Map movement, layer switch and load", the sample page is 339,850 bytes (331.9 KiB).
Thus the merged limit is 332 KiB (339,968 bytes).
After the next merge with the change of "Map page bytes and the security policy", the sample page is 337,662 bytes (329.7 KiB).
Thus the merged limit is 330 KiB (337,920 bytes).

## All step numbers of a long sequence (2026-10-27)

Scope seqcap: the number limit of the earlier section removed the step numbers of a sequence with more than 40 steps.
The lines of these steps had no number on the map.
The maintainer selected option C: remove the number limit and keep the grid.

The change removes `LONG`, `numbered()` and `ctx.long` from `page_sequences.py`, and the legend note from `page_sequence_script.py`.
Each step number examines all places on its line again. The grid (`GRID_JS`) stays.

Acceptance, written before the measurement:

- The marks of synthetic sequences of 30, 41, 60, 100 and 200 steps are byte-identical to the marks of d7d7a8b.
- The marks of each sequence of this repository and of the page with 450 flows are byte-identical to the marks of d7d7a8b.
- At 1x CPU, on the page with 72 components and 450 flows, a sequence of 200 steps has a click time that is not more than one tenth of the d7d7a8b time. The slowest of route, start and step must obey this limit in each of 3 runs.

Method: the method of the earlier section, on the same host in the same session. The load average was 1.1 to 2.5 on 4 cores.
The scripts are in the scratch folder `fu-seqcap`: `render.sh`, `marks.sh`, `dump.js`, `marks.js`, `cmp.py`, `time.sh`, `seqtime.js`, `summ.py` and `pagebytes.py`.
The time limit of the session stopped the third run at 4x. This run was done again alone after the other runs.

### Click times (ms)

Each cell gives the range of 3 runs for route / start / step.

| N | d7d7a8b, 1x | change, 1x | change, 4x |
|---|---|---|---|
| 30 | 1044-1290 / 1018-1396 / 873-1023 | 215-246 / 156-267 / 153-192 | 1018-1235 / 903-1297 / 789-1051 |
| 41 | not measured | 144-222 / 149-169 / 173-210 | 696-977 / 867-960 / 957-1397 |
| 60 | 2362-2795 / 2480-2687 / 2487-2930 | 217-247 / 207-251 / 262-329 | 1037-1387 / 1086-1227 / 1159-1440 |
| 100 | 7313-7860 / 6787-7779 / 7349-8728 | 378-671 / 376-394 / 364-467 | 1960-2617 / 1825-2617 / 1809-2555 |
| 200 | 28411-31591 / 27727-32184 / 29502-35031 | 849-1029 / 769-1105 / 769-1064 | 5369-5764 / 4366-5576 / 4237-5355 |

At 200 steps and 1x, the slowest operation of the change took 1105, 901 and 849 ms.
The fastest d7d7a8b operation in the same runs took 27727, 28411 and 29155 ms. The acceptance passes.
With the number limit, the scope seqcap measurement gave 146 to 374 ms for 200 steps at 1x. Thus the change makes a long sequence slower than the number limit did.

### A long sequence on one flow (failure)

The review of this change measured the case of audit finding g1page-1: a route of 3000 steps on one flow.
Acceptance, written before the measurement: with the change, route, start and step each take not more than 1000 ms at 1x on the page with 450 flows, in each of 3 runs.

Method: `same.js` in the scratch folder `fu-seqcap-review`, started by `same.sh` in the scratch folder `fu-seqcap-v`.
The runs of ddf8236 and of the change alternate on the same host in the same session. The load average was 1.7 to 2.1 on 4 cores.

| Page | Run | Route / start / step (ms) | Numbers, route / step |
|---|---|---|---|
| ddf8236 | 1 | 395 / 496 / 489 | 40 / 39 |
| ddf8236 | 2 | 451 / 465 / 308 | 40 / 39 |
| ddf8236 | 3 | 469 / 577 / 323 | 40 / 39 |
| Change | 1 | 4458 / 5074 / 5018 | 3000 / 2999 |
| Change | 2 | 5090 / 5475 / 4719 | 3000 / 2999 |
| Change | 3 | 4906 / 4125 / 5605 | 3000 / 2999 |

The acceptance fails. With the change, each click takes 4.1 to 5.6 s. At ddf8236, each click takes 0.3 to 0.6 s.
The review got 4.5 to 8.7 s for the change and 0.36 to 0.9 s for ddf8236 in a different session.
No page error occurred. The d7d7a8b time for this route is not measured.
The change keeps option C for this case. The number of steps in a sequence has no limit.
If the maintainer must have a limit, a step limit in `journeys._steps` is an option. This option needs a new measurement.

The Node harness of the tests also draws all 3000 numbers for this route on the sample page. It took 11.5 s in one run.
Thus this change adds no test for this route: the test would add 11.5 s to each test run.

### The marks are the same

`dump.js` writes the marks of the whole route and of step N/2 + 1 for each synthetic sequence.
For N = 30, 41, 60, 100 and 200, the marks of the change are byte-identical to d7d7a8b in the two views.
The change draws N numbers on the whole route and N - 1 numbers in the step view, as d7d7a8b does.
`marks.js` writes the lines and marks of the whole route and of each step of each sequence.
For the 15 sequences of this repository (78 views) and the 4 sequences of the page with 450 flows (28 views), the data is byte-identical to d7d7a8b.

### Page size

The sample page of `tests/test_render.py` changes from 337,662 bytes to 337,127 bytes, a decrease of 535 bytes.
The limit of 330 KiB stays the same.

## The syntax tree cache above its limit (2026-10-27)

Scope treecache: `python_tree.py` keeps the syntax trees of an extraction in a cache with the limit `KEPT` (1,048,576 nodes).
Before the change, a new tree above the limit removed only the oldest trees. Each extraction step reads the modules in the same sequence, so a large repository removed each tree before the next step used it again.
The maintainer selected option 2: when a new tree goes above the limit, the cache removes all trees and then keeps at most one tree until the end of the extraction.

Acceptance, written before the measurement:

- This repository, `extract`: the parse count is the same on the two versions. The peak RSS and the time of the change are in the range of ddf8236 plus the noise between runs.
- The fixture big5, `extract`: the time of the change is not more than the time with `KEPT=0` (42 to 45 s in an earlier measurement). The peak RSS of the change is not more than the peak RSS of ddf8236 in the same session.
- The files after `extract` are byte-identical between ddf8236 and the change.

Method: the versions are Git archives of ddf8236 and b678013. The code of b678013 is the same as the code of the merged change. Each run uses a new copy of the input.
The peak RSS is `ru_maxrss` from `os.wait4`. The times are wall times. The host has 4 cores. The runs of the two versions alternate.
The scripts are in the scratch folder `fu-treecache`: `rss.py`, `probe.py`, `identity.py`, `run.sh` and `run2.sh`.

| Input | Version | Time (s) | Peak RSS (MB) | Parses |
|---|---|---|---|---|
| This repository | ddf8236 | 5.89-6.94 | 132.9-133.1 | 178 |
| This repository | Change | 5.72-6.52 | 132.9-133.0 | 178 |
| big5, run 1 | ddf8236 | 65.93-67.70 | 435.7-436.8 | 4247 |
| big5, run 1 | Change | 49.20-50.99 | 404.5-405.4 | 4254 |
| big5, run 2 | ddf8236 with `KEPT=0` | 44.33-46.89 | 173.5-174.1 | not measured |
| big5, run 2 | Change | 45.50-47.52 | 404.5-406.4 | not measured |

Each range is 3 runs. At ddf8236 this repository has 178 modules. The acceptance gave 177 modules, but the two versions both make 178 parses.

Results:

- This repository: the acceptance passes.
- big5 peak RSS: the acceptance passes. The change uses about 31 MB less than ddf8236.
- big5 time: the acceptance fails. The change is 16 to 20 s faster than ddf8236. But in each pair of run 2, the change is 0.63, 0.74 and 1.17 s slower than `KEPT=0`.
  The time of ddf8236 in this session was also more than in the earlier measurement (65.9 to 69.3 s against 59 to 63 s).
  A possible cause is that the first step fills the cache to about 1M nodes before the first removal. `KEPT=0` does not fill the cache. This cause is not measured separately.
- Output identity: the acceptance passes. The files after `extract` are byte-identical on this repository, big5, big6, diamond20, f36, f72 and ns20. On tsconfig80 the two versions both give exit code 2 and write no facts file.

The change stays, because it is faster than ddf8236 and keeps the output the same. A lower limit or no cache can remove the remaining difference. These options need a new measurement.

## Map page bytes and the security policy (2026-10-26)

This change is for four findings of the audit at commit 65e5464:

- uiperf-6: the page with `--base` contained the map script two times: one copy for the system map and one copy for the change map.
- perf-8: each module record of the page data contained `names` and `public_names` with the same names. The page data had a space after each comma and colon.
- xss-1: the map page, the figures and the two servers gave no Content-Security-Policy.
- regex-5: a theme value with `/*` removed the page CSS until the next `*/`, with no error.

The change:

- The page has one map script. The script contains the map code one time, in a function. It calls the function for the system map and for the change map.
- The script contains the detail of the system map one time. The change map gets that detail with a set of changes: new fields of records and new values of keys. If the changes do not give the same detail, the script contains the full detail of the change map.
- The module records do not contain `names`. The page script makes the names from `public_names`. The page data uses compact JSON separators.
- The page scripts have no line feed after a line that ends with `;`, `{` or `,`, if the line has no `//` and no `/*`.
- Each page has a policy meta element (`page_csp.py`). The policy contains the SHA-256 digest of each inline script and style element. It gives `'none'` to `default-src`, `object-src`, `base-uri` and `form-action`. It permits `data:` images and fonts, and frames from the same origin. It permits style attributes, because the map uses them. It permits no network source.
- `systemap live` adds the digest of its script and `connect-src 'self'` to the policy of each page.
- The page server and the live server send the policy of an HTML page in the Content-Security-Policy header. An SVG file gets a fixed policy without scripts.
- A theme value that contains `/*` or `*/` gives a ValueError. Through the configuration, it gives a ConfigError.

Acceptance, written before the measurement:

- uiperf-6: the size of the `--base` page minus the size of the page without `--base` is less than 50% of the same difference before the change.
- perf-8: the page of this repository gets at least 15 KB smaller.
- The three SVG figures, an interactive figure and `map.json` are byte-identical.
- The interaction snapshots of a Playwright smoke test are identical before and after: select, layer change, sequence, Changes view, and a child map.
- The pages have 0 CSP violations: this repository page, the `--base` page, the nested pages of `tests/test_nested.py` from a file and from the page server, the figures, and the live page.
- regex-5: `#888 /*` in `ink_2` gives an error. Before the change, it removed characters of the page CSS.

Method: the scripts are in the scratch folder `p3-pagebytes`.
`render.py` renders the page, the page with `--base HEAD~10`, the three configured figures and an interactive figure into a temporary folder.
For the change, `render.py` reads the facts of the base run and uses the model file of 65e5464. Thus the comparison does not include the new source module.
`smoke.js`, `smoke2.sh`, `figure.js` and `live.js` operate headless Chromium. They record each `securitypolicyviolation` event.
At the end, `smoke.js` adds an inline script to the page. With the policy, that script must not run.

### Page bytes

| page | 65e5464 (bytes) | change (bytes) | difference |
|---|---|---|---|
| this repository | 931,784 | 889,244 | -42,540 (-4.6%) |
| `--base HEAD~10` | 1,323,157 | 1,114,431 | -208,726 (-15.8%) |
| `--base` minus the page without `--base` | 391,373 | 225,187 | -166,186 (-42.5%) |
| sample page of `tests/test_render.py` | 335,455 | 333,356 | -2,099 |

The parts of the change on the `--base` page:

| part | 65e5464 (bytes) | change (bytes) | difference |
|---|---|---|---|
| map scripts (code and detail) | 331,787 | 166,855 | -164,932 |
| page data | 466,610 | 424,033 | -42,577 |
| other scripts | 166,426 | 163,883 | -2,543 |
| policy meta element | 0 | 1,344 | +1,344 |

On the page of this repository, the page data changes from 395,122 bytes to 354,362 bytes (-40,760).
The change map gets 1,706 bytes of changes in place of a second detail. The detail of the system map is 121,288 bytes.

The acceptance value of uiperf-6 is not satisfied: the difference is 57.5% of the earlier difference, not less than 50%.
The duplicate map script is removed. The remaining 225 KB are the change map SVG, its styles and the comparison data. These parts are not copies.
The acceptance value of perf-8 is satisfied.

The sample page has a size limit. The policy meta element adds 1,182 bytes. The line feed removal and the compact JSON remove more bytes.
The limit goes down from 328 KiB to 326 KiB, the next whole KiB above the measured page (325.5 KiB).

### Outputs and interaction

The three SVG figures, the interactive figure and `map.json` are byte-identical (`cmp`).
The interaction snapshots are identical for this repository page (16 steps), the `--base` page (17 steps) and the nested top page (15 steps).

### Security policy

| page | CSP violations | page errors | added script ran |
|---|---|---|---|
| this repository, file | 0 | 0 | no |
| `--base`, file | 0 | 0 | no |
| nested top page and child page, file | 0 | 0 | no |
| nested top page, page server, child map open in the frame | 0 | 0 | no |
| this repository and `--base`, page server | 0 | 0 | no |
| three figures, file and page server | 0 | 0 | not tested |
| live page, before and after `POST /refresh` | 0 | 0 | no |
| live `change.svg` | 0 | 0 | not tested |

On 65e5464, the added script ran on the file pages of this repository, the `--base` page and the nested top page.
The live page loaded again after `POST /refresh` and kept the selected component and the layer. Thus the event connection operates with the policy.
A figure SVG file cannot contain a policy meta element. A file that a person opens from the disk thus has no policy. The figures contain no script.
The interactive figure goes into a different document. The policy of that document applies to it.

### Theme values

Before the change, `#888 /*` in `ink_2` removed 5,707 characters of the page CSS, with no error.
`#888 */` and `/* x */ #888` gave no error.
After the change, each of the three values gives "The theme value ink_2 contains ...".

A review found that a quote mark or a backslash also changed the page CSS with no error.
The page CSS is on one line. Thus, `#888 '` in `ink_2` started a CSS string that continued for 1,108 characters to the next `'`.
In Chromium, the stylesheet went from 228 rules to 227 rules. The lost rule was the dark theme rule `:root[data-theme="dark"]`.
Before this second change, `#888 '` and `#888 \` in `ink_2`, `Inter',sans-serif` and `Inter",sans-serif` in `font_ui`, and `x\` in `font_mono` gave no error.
After the change, each of these five values gives "The theme value ... contains ...".
`'Inter',sans-serif`, `"Inter",sans-serif` and `#888` give no error before and after. A font stack can contain quote marks in pairs.

### Refused requests

The page server sends the policy only for a request that it accepts.
Before this change, a request with `Host: evil.example:PORT` got status 403 with a policy header of 1,153 characters. The server read the page file to make that header.
After the change, the same request gets status 403 with no policy header.
The figures and the interactive figure are byte-identical before and after this change. The page and `map.json` change only in the source facts of the changed files and tests.

## The A* route search of a strict search (2026-10-26)

Finding scale-5: after the P3 change, `route_all` took 2.65 s on s72 (450 flows) and 10.9 s on s144 (900 flows).
The search of each flow was a Dijkstra search. The time grows with the square of the number of flows.

The change adds `route_astar.py`. A strict search now uses an A* search with a cut bound.
A path from a node to a target crosses each row interval and each column interval between them.
The bound adds the lowest cost of an allowed segment in each such interval.
If all allowed segments of an interval are used, that cost is five times the length.
The router counts the unused segments of each interval for each set of crossed regions.
The non-strict search (the fallback) does not change.

The result of the Dijkstra search is a function of the exact float distances.
The A* search keeps the same tie rules for the end port and for the step before each state.
Its bound is lower than the true cost by at least 0.001. Thus it calculates the exact distance of each state on a path of lowest cost.
A state is not necessary if the other state of its node is lower by 40.001 or more.
A first version used 40 without the 0.001. On 13 of 400 random layouts it gave a different route, because two float sums in a different sequence were different in the last bit.

Other parts of the change:
- The router finds the regions of all grid segments one time, with bisect. The comparisons are those of `_crosses`.
- The router keeps the regions of each port stub.
- The step lists of each state are made one time for each router.

Acceptance, written before the measurement: `route_all` on s144 takes less than 4 s, the growth exponent from s72 to s144 is less than 2, and the routes are byte-identical to those of 154e395 for this repository, s36, s72, s144 and perf/huge.

Method: the inputs of `route_all` for each map are written one time to a file with the placement of 154e395.
Then `rt.py` times `route_all` and writes the routes. The base runs and the change runs take turns.
The scripts are in the scratch folder `post-router`: `dump.py`, `rt.py`, `run.sh`, `final.sh`, `fuzz.py`, `kinds_check.py` and `figs_cmp.py`.
The computer has 4 cores. Other processes operated during the measurements.

### route_all (s)

Each cell gives the values of three runs.

| map | flows | 154e395 | change |
|---|---|---|---|
| repo | 80 | 0.41, 0.39, 0.38 | 0.14, 0.22, 0.15 |
| s36 | 200 | 0.54, 0.54, 0.58 | 0.25, 0.28, 0.26 |
| s72 | 450 | 2.43, 2.39, 2.41 | 1.10, 1.07, 0.95 |
| s144 | 900 | 9.19, 9.28, 9.00 | 4.25, 4.18, 4.19 |
| perf/huge | 450 | 2.29, 2.23, 2.29 | 1.03, 1.03, 1.02 |

The growth exponent log2(t144 / t72) is 1.93 to 2.16 for the change (1.89 to 1.96 for 154e395).

### States taken from the heap

| map | 154e395 | change |
|---|---|---|
| repo | 258723 | 56701 |
| s36 | 412877 | 155251 |
| s72 | 1738062 | 690991 |
| s144 | 6720106 | 3102114 |

### Identity

- The routes files are byte-identical to the files of 154e395 for repo, s36, s72, s144 and perf/huge, in all runs.
- The pages and the configured figures of repo, s36 and s72 are byte-identical to those of 154e395.
- On 2900 random layouts (50177 flows in the last 2500), the A* search and the Dijkstra search give equal routes.
- The regions of each grid segment are equal to the result of `Router._segment` on the five maps.

### Result

The acceptance value for s144 is not satisfied: 4.18 to 4.25 s. The growth exponent is not less than 2.
The change halves the time, but the time still grows with the square of the number of flows.
The s144 map is a strip of 2 region columns. Each flow crosses a band of rows, and the path length grows with the number of flows.
Thus also a perfect bound gives a quadratic growth. A measurement showed that a perfect bound keeps 4.3% of the states of the Dijkstra search on s72. The cut bound keeps about 40%.
Many states are on paths that cost only a little more than the best path, for example in a parallel lane.
These bounds did not decrease the time in a measurement:
- A reverse search from each target card, kept between flows: the kept fields became too low after other routes used lanes, and new fields cost as much as the Dijkstra search.
- A row DP bound with lane changes: it keeps 32% of the states, but its own cost is near the cost that it removes.
- A zone bound with columns grouped at region edges: 35% of the states.

## TypeScript module descriptions, issue #91 (2026-10-14)

`bench/typescript_descriptions.py` compares three rules on all tracked TypeScript source files, including tests but excluding declaration files.
The earlier rule is from systemap revision `077155e`.
The tag rule accepts only documentation blocks with `@module` or `@packageDocumentation`.
The revised rule excludes untagged comments directly before variable declarations, unless a blank line separates them.
Other headers retain their descriptions. An explicit module tag also keeps a header without a blank line.

Before measurement, the acceptance value required the tag rule to remove symbol comments and retain every manually identified module description.
The tag rule failed: it removed every existing description, including clear descriptions of files.
Thus the change uses the narrower variable-comment rule.

| repository | revision | source files | earlier descriptions | tag rule | revised rule |
|---|---|---:|---:|---:|---:|
| ky | `0d59458a0a58e1c3d7c6db0ab17ed5c7cd671e47` | 87 | 7 | 0 | 6 |
| vite | `c2c9ef4dcd05b3e4d88844ea3a13dc23819ca2a5` | 576 | 44 | 0 | 41 |

Ky uses the revision from PR #12. Issue #91 does not record the earlier vite trial revision.
This measurement pins the current vite revision instead.
The [recorded results](results/typescript-descriptions-91.json) contain each earlier description, its tag-rule result, and its revised result.

Manual examination of the four removed descriptions found comments attached to variables:

- ky `source/core/retry-timing.ts`: the timestamp threshold constant.
- vite `packages/vite/src/shared/constants.ts`: the import prefix constant.
- vite `packages/vite/src/module-runner/constants.ts`: the export constants.
- vite `packages/plugin-legacy/src/snippets.ts`: the source URL of a constant containing a browser fix.

The revised rule keeps file descriptions such as vite's benchmark header, module-runner export header, and formatter header.
This syntax rule cannot determine the purpose of every comment. Comments before imports can still describe an individual symbol.
An author can mark an ambiguous file comment with a module tag.

Reproduce with checkouts at the revisions above:

```sh
uv run python bench/typescript_descriptions.py /path/to/ky /path/to/vite
```

For declaration imports, TypeScript 5.9.3 `resolveModuleName` with `moduleResolution: bundler` confirmed all nine parameterized import cases in `tests/test_typescript_declarations.py`.
The cases include `./types.d`, JavaScript extension substitution, directory indexes, and a path alias.
Regression tests also cover source priority, declaration priority before a directory index, and alias fallback order.

## M6: two writers at the same time (2026-11-04)

Scope: step 1 of [the nested parts design](../../docs/design/nested-parts.md).
The script is [`lock_race.py`](lock_race.py). Its docstring has the acceptance values, which were written before the run.
Each run uses a new copy of the nested fixture of `tests/test_nested.py`, after `place` and `extract`.
The two processes of a run start at the same time. The host has 4 cores.

Acceptance, written before the run:

- Part A: 100 runs of two `decisions submit` processes, with one `supported` verdict for a judgement line of the map Gateway and one for a line of the map Style. 0 lost answer rows and 0 lost store records. Each process that does not exit 0 gives the lock error.
- Part B: 100 runs of two writers of different nested model files. 100 percent of the runs exit 0 in the two processes, and each file has its new digest.
- Part C: two writers of the same model file. This part is for information only. It has no acceptance value.

Difference from the design: `place --map` is not available before step 2 of the design. Thus parts B and C use `review CARD --map MAP`, which writes only the model file of that map.

Command: `uv run python bench/jev/lock_race.py 100`

| Part | Runs | Result |
|---|---|---|
| A | 100 | 82 processes stopped with the lock error. 0 stopped with a different error. 0 lost answer rows. 0 lost store records. |
| B | 100 | 100 runs with exit 0 in the two processes. 0 lock errors. 0 lost digests. |
| C | 100 | 33 runs with exit 0 in the two processes. 67 runs with a lock error. 0 lost digests. |

Results:

- Part A passes. In 82 runs the two processes operated at the same time, and the second process stopped. In the other 18 runs, the two processes did not operate at the same time, and the two submits recorded their verdicts.
- Part B passes.
- Part C: a trial run with 3 runs, before the run above, gave 2 lost digests. At that time, `review` held the model lock only during the write, not from the read to the write. The second writer then wrote a text that did not have the digest of the first writer. After that result, `review` holds the lock of each model file of the map from the read to the write, and the trial with 5 runs and the run above gave 0 lost digests.
- A trial run with 5 runs of all three parts, before the run above, gave 5 lock errors in part A, 5 runs with exit 0 in part B, and 4 lock errors in part C, with 0 lost rows, records, and digests.
- Not measured: the time of a submit with the lock. A lock that a stopped process left was tested in `tests/test_lock.py`, not in this script.

### M6 again after the review corrections (2026-11-04)

The review of step 1 changed the lock code. The lock of one process now has one guard for the make and the removal of the lock file, also for two threads. `decisions submit` takes the model file locks of all its reviews before its first write. A `review --dry-run` takes no lock. `refresh` and `extract` hold the model file locks when they move a contract or record earlier flow reviews.
The acceptance values and the script did not change.

Command: `uv run python bench/jev/lock_race.py 100` (88 seconds on the same host)

| Part | Runs | Result |
|---|---|---|
| A | 100 | 91 processes stopped with the lock error. 0 stopped with a different error. 0 lost answer rows. 0 lost store records. |
| B | 100 | 100 runs with exit 0 in the two processes. 0 lock errors. 0 lost digests. |
| C | 100 | 44 runs with exit 0 in the two processes. 56 runs with a lock error. 0 lost digests. |

Parts A and B pass. Part C has no acceptance value. It gave 0 lost digests.

## M1, M2, M10, and M19: a tree on three levels and `--map` (2026-11-04)

Scope: step 2 of [the nested parts design](../../docs/design/nested-parts.md).
The script is [`nested_scope.py`](nested_scope.py). Its docstring has the acceptance values, which were written before the run.
The fixture is [`tests/three_levels.py`](../../tests/three_levels.py). It has nested maps on levels 1, 2, and 3. Each map on level 2 imports a module of the top card Base.
Each command is a new process. The times are wall times. The host has 4 cores. The code is the working tree of step 2 on 8fef34a.

Command: `uv run python bench/jev/nested_scope.py` (23 seconds)

### M10: the fixture on three levels

Acceptance, written before the run: on the fixture with 11 maps, `place`, `extract`, `refresh`, `check`, `judgement`, and `delta --base HEAD` exit 0.

| Command | Exit code |
|---|---|
| `place` | 0 |
| `extract` | 0 |
| `refresh --quiet` | 0 |
| `check` | 0 |
| `judgement` | 0 |
| `delta --base HEAD` | 0 |

M10 passes. `delta` compared the commit with the same working tree. A delta with a source change on three levels was not measured.

### M2 on a generated tree, not on big5

The design gives M2 on the 50-map tree of the fixture big5. big5 is not on this host. Thus M2 of the design was not run.
The script ran the acceptance of M2 on a different tree: the fixture with 7 maps on level 1 and 3 maps on level 2 below each of them, 50 maps in all.
This tree has 122 modules with the empty package markers, not about 4,250. Its result does not replace the M2 of the design.

Acceptance, written before the run: the median time of `check --map P0/Q0` is at most 0.5 times the median time of the full-tree `check`. A syntax error in the model file of the sibling map P1 does not change the exit code of `check --map P0/Q0`.

| Command | Exit codes | Times of 5 runs (s) | Median (s) |
|---|---|---|---|
| `check` | 0 | 2.28, 2.20, 2.29, 2.30, 2.25 | 2.28 |
| `check --map P0/Q0` | 0 | 0.27, 0.27, 0.32, 0.26, 0.26 | 0.27 |

The ratio of the medians is 0.12. After the syntax error in `map/p1.py`, `check --map P0/Q0` exits 0, and the full-tree `check` exits 2.
The acceptance passes on this tree. The time on big5 is not known. A measurement on big5 is necessary.

### M2 again, after the review of step 2

The review found that `check --map` did not examine the facts. Thus it gave exit 0 with stale facts or with no facts file.
After the correction, `check --map` compares the saved facts with fresh facts, as the full `check` does. It does not examine the pages.
The acceptance is the same as above. Command: `uv run python bench/jev/nested_scope.py` (23 seconds). The full test suite operated on the same host at the same time.

| Command | Exit codes | Times of 5 runs (s) | Median (s) |
|---|---|---|---|
| `check` | 0 | 2.06, 2.09, 2.14, 2.06, 2.05 | 2.06 |
| `check --map P0/Q0` | 0 | 0.37, 0.33, 0.39, 0.38, 0.34 | 0.37 |

The ratio of the medians is 0.18. After the syntax error in `map/p1.py`, `check --map P0/Q0` exits 0, and the full-tree `check` exits 2.
The acceptance passes on this tree. M10 also passes again: the six commands exit 0. The time on big5 is not known. A measurement on big5 is necessary.

### M1 and M19: not run

- M1 needs the fixture big5 (about 4,250 modules) divided into 10, 25, and 50 nested maps. big5 is not on this host. M1 was not run.
- M19 needs a fixture with more than 10,000 source files (issue #92). No such fixture is on this host. M19 was not run.

## M3 and M4: the part plan and the size of one nested model (2026-11-04)

Scope: step 3 of [the nested parts design](../../docs/design/nested-parts.md).
The script is [`parts_plan.py`](parts_plan.py). Its docstring has the acceptance values, which were written before the run.
The host has 4 cores. The code is the working tree of step 3 on 70b8c0b.

Command: `uv run python bench/jev/parts_plan.py` (about 10 seconds)

### M3 on a generated tree, not on big5

The design gives M3 on the fixture big5 (about 4,250 modules). big5 is not on this host. Thus M3 of the design was not run.
The script ran the acceptance of M3 on a different tree: the fixture of [`tests/three_levels.py`](../../tests/three_levels.py) with 7 maps on level 1 and 3 maps on level 2 below each of them, 50 maps in all.
The plan of the top map has 7 nested parts. This tree has 122 modules with the empty package markers, not about 4,250. Its result does not replace the M3 of the design.

Acceptance, written before the run: the median time of `systemap parts --json` is at most 10 s. Its peak RSS is at most 50 MB above the peak RSS of a process that only loads the tree and reads the facts. Its output is at most 50 MB.

| Measurement | Result |
|---|---|
| Exit codes of 5 runs | 0 |
| Times of 5 runs (s) | 0.40, 0.37, 0.41, 0.34, 0.38 |
| Median time (s) | 0.38 |
| Peak RSS of `parts --json` | 35.1 MB |
| Peak RSS of the load and the facts read | 25.4 MB |
| Peak RSS above the load and the facts read | 9.7 MB |
| Output | 14,476 bytes |

The acceptance passes on this tree. The time and the memory on big5 are not known. A measurement on big5 is necessary.

### M4: one nested model with 40 components

Acceptance, written before the run: a nested model with 40 components, flows, sequences, and positions is at most 256 KB (262,144 bytes) and 50,000 values.

The script made the model from the means of the self-map at the same commit. The self-map has 21 components, 80 flows, and 16 sequences. Its model files have 95,277 bytes and 2,320 values without the contract file.

| Mean of the self-map | Value |
|---|---|
| Characters of `does` (internal components) | 898.7 |
| Characters of `interface` | 101.4 |
| Claims for each internal component | 11.5 |
| Flows for each component | 3.8 |
| Source records for each flow | 1.9 |
| Characters of a relation sentence | 111.2 |
| Sequences for each component | 0.8 |
| Steps for each sequence | 4.3 |
| Characters of a step sentence | 120.4 |
| Entry points for each sequence | 1.8 |

| Generated model | Result |
|---|---|
| Components, flows, sequences | 40, 152, 30 |
| Size | 214,060 bytes (209.0 KB) |
| Values (the count of `model_load`) | 4,137 |

M4 passes. The size is 82 percent of the acceptance value, and the size limit is nearer than the value limit. A map with longer `does` text than the self-map can be above 256 KB. The size of a real nested map of 40 components was not measured.

### M3 and M4 again, after the review of step 3 (2026-11-04)

The review of step 3 changed `parts_plan.py`: the plan calculates the crossing imports one time for each parent map, not one time for each nested part. `facts_digest` and `contract_digest` also changed.
The script now stops with exit code 1 if `place`, `extract`, `refresh`, or a measured process fails. The acceptance values did not change.
The code is the working tree of the review on 7a48d35. The command and the tree are the same as above.

| Measurement | Result |
|---|---|
| Exit codes of 5 runs | 0 |
| Times of 5 runs (s) | 0.32, 0.32, 0.37, 0.33, 0.34 |
| Median time (s) | 0.33 |
| Peak RSS of `parts --json` | 35.9 MB |
| Peak RSS of the load and the facts read | 25.4 MB |
| Peak RSS above the load and the facts read | 10.5 MB |
| Output | 14,476 bytes |

M3 passes on this tree. M4 gives the same values as above: 214,060 bytes and 4,137 values, and passes. The time and the memory on big5 are not known. A measurement on big5 is necessary.

## M5: a round trip of the self-map through nested parts (2026-11-04)

Scope: step 4 of [the nested parts design](../../docs/design/nested-parts.md): the judgement kinds `boundary flow` and `boundary import`.
The script is [`join_round_trip.py`](join_round_trip.py). Its docstring has the acceptance values and the division, which were written before the run.
The host has 4 cores. The code is the working tree of step 4 on 26bd8e0.

Acceptance, written before the run: after the division of the self-map into nested parts that copy its cards and flows, `systemap judgement` gives 0 `boundary flow` lines and 0 `boundary import` lines. `systemap check` gives the same exit code as before the division, and `systemap rules` gives the same text.

The division: each of the 5 regions of the self-map becomes one card on the top map, and that card opens a nested map with the components of the region. The 5 actors stay on the top map. Of the 80 flows of the self-map, 11 connect two components of one region and go into one nested map. The other 69 flows go to the top map as flows between the part cards and the actors, on 28 ordered pairs, and into the nested maps as flows with an actor.
Differences from the design, written before the run: the sequences, the layer overrides, the verb overrides, the flow reviews, and the source reviews are not copied.

Command: `uv run python bench/jev/join_round_trip.py` (about 2 minutes)

| Measurement | Before the division | After the division |
|---|---|---|
| Maps | 1 | 6 |
| `boundary flow` lines | 0 | 0 |
| `boundary import` lines | 0 | 0 |
| `check` exit code | 0 | 1 |
| `rules` text | `import rules: The model has no import rules.` | the same text |
| Coverage | 185 of 185 modules | 185 of 185 modules |

M5 fails. The boundary lines and the `rules` text agree with the acceptance. The `check` exit code does not agree.

- `check` gave 4 layout problems on the top map, and no problem in the 5 nested maps. Two labels of the 69 top flows overlap other labels or a region header: `diagram measurements` (`KeepPart -> Agent`) and `cards, sentences` (`MeanPart -> KeepPart`). The 69 top flows connect 28 ordered pairs, a mean of 2.5 flows for each pair. The `stale` problems of the pages followed, because `refresh` stops after a check error.
- The 0 `boundary import` lines do not show that each import has a flow between its two original components. The self-map has the open line `crossing import: Placer imports Config` and the answered line `crossing import: Skill imports Config`. After the division, Placer and Config are in the same nested map, and the open line has the prefix of that map. Skill and Config are in different nested maps. A different flow between the two regions connects Skill with the actor of the part of Config. Thus the nested map gives no `boundary import` line for the import of Skill, and the answer of the self-map no longer applies to a line.
- Lines for information only, after the division: 63 `flow review`, 10 `entry point`, 4 `single module`, 4 `no endpoint source`, 3 `thin layer`, and 1 `crossing import`. The division does not copy the reviews or the sequences, as the docstring says.

A division with fewer top flows, for example one flow for each pair of part cards, was not measured. A measurement is necessary before the design can say that a division of the self-map passes `check`.

### M5 again, after a change of the script structure

The complexity check refused two functions of the script with a cognitive complexity of 17. The functions now call helper functions. The division and the acceptance did not change.
The run gave the same values as above: 6 maps, 0 `boundary flow` lines, 0 `boundary import` lines, `check` exit code 0 before and 1 after with the same 4 layout problems, and the same `rules` text. M5 fails again for the same cause.

### M5 again, after the review of step 4

The review changed the code that finds the boundary lines one time for each judgement run, the evidence of the boundary lines, the `detail` field of a `boundary import` row, and the direction of `parent_flow` for a `boundary import` row. The rule that gives the lines did not change. The script, the division, and the acceptance did not change. The code is the working tree of the review on 9063986.

Command: `uv run python bench/jev/join_round_trip.py` (40 s)

| Measurement | Before the division | After the division |
|---|---|---|
| Maps | 1 | 6 |
| `boundary flow` lines | 0 | 0 |
| `boundary import` lines | 0 | 0 |
| `check` exit code | 0 | 1 |
| `rules` text | `import rules: The model has no import rules.` | the same text |
| Coverage | 185 of 185 modules | 185 of 185 modules |

M5 fails again for the same cause: the same 4 layout problems on the top map. Open lines by kind before the division: 1 `crossing import`, 19 `flow review`, and 1 `stale source review`. After the division: 63 `flow review`, 10 `entry point`, 4 `single module`, 4 `no endpoint source`, 3 `thin layer`, and 1 `crossing import`.

## C1: the size of the canvas data (2026-11-05)

Scope: step 1 of [the nested canvas design](../../docs/design/nested-canvas.md): the module `canvas_data.py`.
The script is [`canvas_data_size.py`](canvas_data_size.py). Its docstring has the acceptance value, which was written before run 1.

Acceptance: the canvas data of the M11 tree (50 maps, 40 cards in each map) is at most 2 MB (2,097,152 bytes) raw, as the UTF-8 bytes of `canvas_data.text`.
The gzip size at level 6 and the time have no acceptance value.

The M11 tree is the fixture of `nested_tree_pages.py` on the branch `claude/nested-step-8` (c820839). That script is not on this branch. Thus the new script has a copy of its fixture writer with no change.
The fixture is generated. It is not big5, and no real repository has this form.
The script runs `place` and `extract`, not `refresh`. The data is built without the open lines of the judgement.
Each time is one call of `canvas_data.build` and `canvas_data.text`. The caches of the router, the evidence, and the claims are empty before each call. The host has 4 cores. The code is the working tree of step 1 on accc234.

Command: `uv run python bench/jev/canvas_data_size.py`

| Run | Tree | Maps | Raw bytes | gzip -6 bytes | Times (s) | Median (s) | Result |
|---|---|---|---|---|---|---|---|
| 1 | M11 tree | 50 | 731,326 | 30,236 | 22.00, 23.18, 22.37 | 22.37 | pass |
| 1 | this repository | 1 | 40,420 | 10,902 | 0.42, 0.46, 0.41 | 0.42 | |
| 2 | M11 tree | 50 | 731,326 | 30,236 | 21.93, 22.38, 21.80 | 21.93 | pass |
| 2 | this repository | 1 | 40,408 | 10,918 | 0.36, 0.36, 0.35 | 0.36 | |

C1 passes. The raw data of the 50 maps is 731,326 bytes, 35 percent of the acceptance value.

- In run 1, `place` took 5.0 s and `extract` took 2.9 s on the M11 tree. Both exited 0. In run 2, both exited 0. Their times in run 2 were not recorded.
- In run 1, the time of each build also included the load of the 50 model files (`nest.load`). The tests of the new module operated on the same host near the end of run 1. Run 2 is after the code review. It times only the build and the text.
- Between the two runs, the facts of this repository were extracted again, and the `does` text of the component Page changed. Thus the bytes of this repository are different. The M11 bytes are the same.
- The time on the M11 tree is about 0.44 s for each map. The cause of this time was not examined. The build calculates the flow paths of each map with the router, and the page render calculates the same paths. A profile is necessary before step 2 can give a load time (C3).
- This run does not answer the open question of the design about a map with more than 400 cards. A measurement on such a tree is necessary.

### Runs 3 to 5: after the claim index of PR #152

The code is 2363822 on `claude/nested-canvas`. This commit has the claim index and the judgement evidence index of PR #152.
The script and its acceptance value did not change. The command is the same. The 3 runs operated one after the other.
Other agents operated Chromium on the same host at the same time. Thus the times are not exact.

| Run | Tree | Maps | Raw bytes | gzip -6 bytes | Times (s) | Median (s) | Result |
|---|---|---|---|---|---|---|---|
| 3 | M11 tree | 50 | 732,502 | 30,256 | 1.91, 2.01, 2.09 | 2.01 | pass |
| 3 | this repository | 1 | 41,259 | 11,144 | 0.38, 0.39, 0.36 | 0.38 | |
| 4 | M11 tree | 50 | 732,502 | 30,256 | 1.91, 1.99, 1.93 | 1.93 | pass |
| 4 | this repository | 1 | 41,259 | 11,144 | 0.32, 0.29, 0.31 | 0.31 | |
| 5 | M11 tree | 50 | 732,502 | 30,256 | 1.87, 1.90, 1.99 | 1.90 | pass |
| 5 | this repository | 1 | 41,259 | 11,144 | 0.35, 0.37, 0.34 | 0.35 | |

C1 passes again. The raw data of the 50 maps is 732,502 bytes, 35 percent of the acceptance value.

- One build on the M11 tree now takes 1.87 to 2.09 s. In runs 1 and 2, it took 21.80 to 23.18 s (about 22 s). The median is about 11 times less.
- `place` took 4.6 s, 4.5 s, and 4.3 s, and `extract` took 1.1 s, 1.2 s, and 1.0 s. All exited 0.
- The raw bytes of the M11 tree increased by 1,176, and the gzip bytes by 20. PR #152 did not cause this change. Commit 7afa36f added the key `fp` to each port of a nested flow. `fp` is the line from the actor card to the map frame. The M11 tree has 49 such ports, and each `fp` key and value has 24 bytes.
- A one-time script built the M11 data with the code of 90d4ad3 (step 1), 7afa36f, f396423, and 2363822. The data of 90d4ad3 has 731,326 bytes. The other three have 732,502 bytes and identical text. Without the `fp` keys, the data of 2363822 is equal to the data of 90d4ad3.
- The bytes of this repository are different from run 2, because the map of this repository changed after run 2. The cause of each changed byte was not examined.
- The build time is not in C3. C3 measures the time in the browser only.

## C2 and C3: frame time and load time of the canvas page (2026-11-05)

Scope: step 2 of [the nested canvas design](../../docs/design/nested-canvas.md): the canvas page (`canvas_page.py`, `page_canvas.py`, `page_canvas_scene.py`, `page_canvas_draw.py`) behind `[render] canvas = true`.
The script is [`canvas_frames.py`](canvas_frames.py) with its browser part [`canvas_frames.js`](canvas_frames.js). Its docstring has the acceptance values, which were written before run 1.

Acceptance:
- C2: the p95 frame interval of each scenario with 4 times CPU throttling is at most 33 ms. The browser starts a frame at a 60 Hz tick, so an interval is a multiple of 16.67 ms. The limit is 33.33 ms (two ticks) plus 5 percent for the timer error: 35.0 ms.
- C2 at normal CPU speed: p95 at most 16.7 ms plus 5 percent: 17.5 ms.
- C3: from the start of the navigation to an interactive map (the first frame is drawn and the input handlers are attached), for 50 maps, at normal CPU speed: at most 1,500 ms. The time with 4 times throttling has no acceptance value.

Each scenario draws 180 frames, and the camera changes at each frame. Thus each frame is drawn at half resolution.
The host is headless Chromium 153 (Playwright 1.63.0) on a 4-core Xeon at 2.1 GHz with no GPU. Chromium paints in software. Thus the values are worse than on a usual laptop or phone. That difference is not measured.
The viewport is 1440 x 900 with a device pixel ratio of 1. A screen with a ratio of 2 has 4 times the pixels. That is not measured.
`M11 tree` is the real canvas data of the M11 tree (`canvas_data.build` after `place` and `extract`). `M11 shape`, `400 cards` and `1,500 cards` are generated data in the same format.

Command: `uv run python bench/jev/canvas_frames.py`

Run 1 (the first renderer):

| Data | Scenario | CPU | Median (ms) | p95 (ms) | Max (ms) | Result |
|---|---|---|---|---|---|---|
| M11 tree | C3 load | 4x | 237 ms | | | information |
| M11 shape | C3 load | 4x | 302 ms | | | information |
| M11 tree | pan-fit | 4x | 16.7 | 16.8 | 50.1 | pass |
| M11 tree | all-open | 4x | 16.7 | 16.8 | 83.3 | pass |
| M11 tree | dive | 4x | 33.4 | 550.0 | 1433.3 | fail |
| 400 cards | pan-fit | 4x | 16.7 | 16.8 | 33.3 | pass |
| 400 cards | dive | 4x | 16.7 | 33.4 | 83.2 | pass |
| 1,500 cards | pan-fit | 4x | 16.7 | 16.8 | 33.4 | pass |
| M11 shape | pan-fit | 4x | 16.7 | 16.8 | 33.3 | pass |
| M11 shape | all-open | 4x | 16.7 | 16.8 | 66.7 | pass |
| M11 shape | dive | 4x | 33.4 | 616.6 | 1399.9 | fail |
| M11 tree | C3 load | 1x | 77 ms | | | pass |
| M11 shape | C3 load | 1x | 75 ms | | | pass |
| M11 tree | pan-fit | 1x | 16.7 | 16.8 | 16.8 | pass |
| M11 tree | all-open | 1x | 16.7 | 16.8 | 16.8 | pass |
| M11 tree | dive | 1x | 16.7 | 100.0 | 150.1 | fail |
| 400 cards | pan-fit | 1x | 16.7 | 16.8 | 16.8 | pass |
| 400 cards | dive | 1x | 16.7 | 16.8 | 16.8 | pass |
| 1,500 cards | pan-fit | 1x | 16.7 | 16.8 | 16.8 | pass |
| M11 shape | pan-fit | 1x | 16.7 | 16.8 | 16.8 | pass |
| M11 shape | all-open | 1x | 16.7 | 16.7 | 16.8 | pass |
| M11 shape | dive | 1x | 16.7 | 116.7 | 333.4 | fail |

Run 1 fails C2 for the dive of the two trees, at 4x and at 1x.

The cause. A CPU profile (CDP `Profiler`, 4x throttling, 121 frames of the dive of the M11 tree, each frame timed in the page) gave 95.1 percent idle time and no frame with more than 30 ms of script time. Thus the script was not the cause. The time was in the paint of the canvas. Deep in a map, the boxes and the routes of the maps above it are millions of pixels long, and the dashed region borders and dashed routes are painted dash by dash in software.
The correction: the renderer cuts each box and each route point to the canvas, with a margin of 8 pixels, before it paints them (`CUT` in `page_canvas_draw.py`).
After the correction, two runs of the driver alone (`node bench/jev/canvas_frames.js PAGE dive RATE`) on the M11 tree gave p95 16.8 ms at 4x (median 16.7, max 33.3) and p95 16.8 ms at 1x (max 16.8).

Run 2 (after the correction and the corrections of the code review):

| Data | Scenario | CPU | Median (ms) | p95 (ms) | Max (ms) | Result |
|---|---|---|---|---|---|---|
| M11 tree | C3 load | 4x | 264 ms | | | information |
| M11 shape | C3 load | 4x | 223 ms | | | information |
| M11 tree | pan-fit | 4x | 16.7 | 16.8 | 33.4 | pass |
| M11 tree | all-open | 4x | 16.7 | 16.7 | 50.0 | pass |
| M11 tree | dive | 4x | 16.7 | 16.8 | 50.0 | pass |
| 400 cards | pan-fit | 4x | 16.7 | 16.8 | 33.4 | pass |
| 400 cards | dive | 4x | 16.7 | 33.3 | 50.0 | pass |
| 1,500 cards | pan-fit | 4x | 16.7 | 16.8 | 33.3 | pass |
| M11 shape | pan-fit | 4x | 16.7 | 16.8 | 33.3 | pass |
| M11 shape | all-open | 4x | 16.7 | 16.8 | 50.0 | pass |
| M11 shape | dive | 4x | 16.7 | 16.8 | 33.3 | pass |
| M11 tree | C3 load | 1x | 76 ms | | | pass |
| M11 shape | C3 load | 1x | 67 ms | | | pass |
| M11 tree | pan-fit | 1x | 16.7 | 16.8 | 16.8 | pass |
| M11 tree | all-open | 1x | 16.7 | 16.7 | 16.8 | pass |
| M11 tree | dive | 1x | 16.7 | 16.8 | 16.8 | pass |
| 400 cards | pan-fit | 1x | 16.7 | 16.7 | 16.8 | pass |
| 400 cards | dive | 1x | 16.7 | 16.8 | 16.8 | pass |
| 1,500 cards | pan-fit | 1x | 16.7 | 16.8 | 16.8 | pass |
| M11 shape | pan-fit | 1x | 16.7 | 16.7 | 16.8 | pass |
| M11 shape | all-open | 1x | 16.7 | 16.7 | 16.8 | pass |
| M11 shape | dive | 1x | 16.7 | 16.8 | 16.8 | pass |

C2 and C3 pass in run 2.
- The dive of the 400-card map at 4x has p95 33.3 ms: two ticks. It is in the limit of 35.0 ms, but it is more than 33 ms if 33 ms is a strict value.
- C3 is 76 ms for the real M11 tree at 1x, and 264 ms at 4x. This time is in the browser only. It does not include `canvas_data.build`, which took about 21 s for the M11 tree on this branch (C1).
- The CI job `canvas-browser` runs `tests/test_canvas_frames.py` with the generated data (M11 shape, 400 cards, 1,500 cards) at 4x and C3 at 1x, with the same limits. On this host, the test passed (8 tests in 31 s).

Run 3 (a second run by a different person, at commit afdaecb, which also fits the plates of the flow labels to their text). The full test suite ran on the same host at the same time. Thus the CPU had more load than in run 2, and the times are not the times of an idle host.

| Data | Scenario | CPU | Median (ms) | p95 (ms) | Max (ms) | Result |
|---|---|---|---|---|---|---|
| M11 tree | C3 load | 4x | 585 ms | | | information |
| M11 shape | C3 load | 4x | 660 ms | | | information |
| M11 tree | pan-fit | 4x | 16.7 | 16.8 | 33.4 | pass |
| M11 tree | all-open | 4x | 16.7 | 16.8 | 33.4 | pass |
| M11 tree | dive | 4x | 16.7 | 33.3 | 33.5 | pass |
| 400 cards | pan-fit | 4x | 16.7 | 16.7 | 33.4 | pass |
| 400 cards | dive | 4x | 16.7 | 33.4 | 50.0 | pass |
| 1,500 cards | pan-fit | 4x | 16.7 | 16.8 | 50.1 | pass |
| M11 shape | pan-fit | 4x | 16.7 | 16.7 | 50.0 | pass |
| M11 shape | all-open | 4x | 16.7 | 16.8 | 50.0 | pass |
| M11 shape | dive | 4x | 16.7 | 16.8 | 50.0 | pass |
| M11 tree | C3 load | 1x | 93 ms | | | pass |
| M11 shape | C3 load | 1x | 91 ms | | | pass |
| M11 tree | pan-fit | 1x | 16.7 | 16.8 | 16.8 | pass |
| M11 tree | all-open | 1x | 16.7 | 16.7 | 16.8 | pass |
| M11 tree | dive | 1x | 16.7 | 16.8 | 16.8 | pass |
| 400 cards | pan-fit | 1x | 16.7 | 16.7 | 16.8 | pass |
| 400 cards | dive | 1x | 16.7 | 16.8 | 16.8 | pass |
| 1,500 cards | pan-fit | 1x | 16.7 | 16.8 | 16.8 | pass |
| M11 shape | pan-fit | 1x | 16.7 | 16.8 | 16.8 | pass |
| M11 shape | all-open | 1x | 16.7 | 16.8 | 16.8 | pass |
| M11 shape | dive | 1x | 16.7 | 16.8 | 16.8 | pass |

C2 and C3 pass in run 3. Two more scenarios have p95 of 33.3 or 33.4 ms (two ticks) at 4x: the dive of the M11 tree and the dive of the 400-card map. Both are in the limit of 35.0 ms. Both are more than 33 ms if 33 ms is a strict value. C3 at 1x is 93 ms for the M11 tree.

Run 4 (at commit 7afa36f, which draws the boundary flows with right angles and keeps the portals off the cards). Before the run, no test suite and no other measurement operated on the host for 30 s. During the run, a different person took screenshots of the canvas page in a different browser for some of the time. Thus the CPU had more load than an idle host for some of the time.

| Data | Scenario | CPU | Median (ms) | p95 (ms) | Max (ms) | Result |
|---|---|---|---|---|---|---|
| M11 tree | C3 load | 4x | 260 ms | | | information |
| M11 shape | C3 load | 4x | 259 ms | | | information |
| M11 tree | pan-fit | 4x | 16.7 | 16.8 | 16.8 | pass |
| M11 tree | all-open | 4x | 16.7 | 16.8 | 33.3 | pass |
| M11 tree | dive | 4x | 16.7 | 16.8 | 50.0 | pass |
| 400 cards | pan-fit | 4x | 16.7 | 16.8 | 33.3 | pass |
| 400 cards | dive | 4x | 16.7 | 33.4 | 50.1 | pass |
| 1,500 cards | pan-fit | 4x | 16.7 | 16.7 | 16.8 | pass |
| M11 shape | pan-fit | 4x | 16.7 | 16.7 | 16.8 | pass |
| M11 shape | all-open | 4x | 16.7 | 16.7 | 66.6 | pass |
| M11 shape | dive | 4x | 16.7 | 16.8 | 50.0 | pass |
| M11 tree | C3 load | 1x | 69 ms | | | pass |
| M11 shape | C3 load | 1x | 67 ms | | | pass |
| M11 tree | pan-fit | 1x | 16.7 | 16.7 | 16.8 | pass |
| M11 tree | all-open | 1x | 16.7 | 16.8 | 16.8 | pass |
| M11 tree | dive | 1x | 16.7 | 16.8 | 16.8 | pass |
| 400 cards | pan-fit | 1x | 16.7 | 16.8 | 16.8 | pass |
| 400 cards | dive | 1x | 16.7 | 16.8 | 16.8 | pass |
| 1,500 cards | pan-fit | 1x | 16.7 | 16.7 | 16.8 | pass |
| M11 shape | pan-fit | 1x | 16.7 | 16.7 | 16.8 | pass |
| M11 shape | all-open | 1x | 16.7 | 16.8 | 16.8 | pass |
| M11 shape | dive | 1x | 16.7 | 16.7 | 16.8 | pass |

C2 and C3 pass in run 4. No p95 increased by one tick (16.7 ms) or more against run 2 or run 3.
- The dive of the 400-card map at 4x has p95 33.4 ms (two ticks), as in run 2 (33.3 ms) and run 3 (33.4 ms). It is in the limit of 35.0 ms. It is more than 33 ms if 33 ms is a strict value.
- The dive of the M11 tree at 4x has p95 16.8 ms, as in run 2. In run 3 it was 33.3 ms.
- C3 at 1x is 69 ms for the M11 tree.
- An earlier run at the same commit started when a different measurement had started on the same host. Thus it is not run 4. It also gave a pass for all scenarios, with the same p95 values in the same ticks. Its p95 for the dive of the 400-card map at 4x was 33.3 ms, and its C3 at 1x was 89 ms for the M11 tree.

Run 5 (on the source of the commit after 7afa36f that records this run. That commit changes the boundary flows: each path goes around the open card and stays out of the cards, the texts and the portals of the screen. Each frame tests the paths against the screen boxes that it draws). Before the run, no test suite and no other measurement operated on the host for 20 s. During the run, no other measurement and no screenshot operated on the host.

| Data | Scenario | CPU | Median (ms) | p95 (ms) | Max (ms) | Result |
|---|---|---|---|---|---|---|
| M11 tree | C3 load | 4x | 241 ms | | | information |
| M11 shape | C3 load | 4x | 252 ms | | | information |
| M11 tree | pan-fit | 4x | 16.7 | 16.8 | 33.3 | pass |
| M11 tree | all-open | 4x | 16.7 | 16.7 | 50.0 | pass |
| M11 tree | dive | 4x | 16.7 | 16.8 | 33.2 | pass |
| 400 cards | pan-fit | 4x | 16.7 | 16.7 | 16.8 | pass |
| 400 cards | dive | 4x | 16.7 | 33.3 | 50.0 | pass |
| 1,500 cards | pan-fit | 4x | 16.7 | 16.7 | 16.8 | pass |
| M11 shape | pan-fit | 4x | 16.7 | 16.7 | 33.3 | pass |
| M11 shape | all-open | 4x | 16.7 | 16.7 | 83.4 | pass |
| M11 shape | dive | 4x | 16.7 | 16.7 | 33.2 | pass |
| M11 tree | C3 load | 1x | 80 ms | | | pass |
| M11 shape | C3 load | 1x | 68 ms | | | pass |
| M11 tree | pan-fit | 1x | 16.7 | 16.8 | 16.8 | pass |
| M11 tree | all-open | 1x | 16.7 | 16.7 | 16.8 | pass |
| M11 tree | dive | 1x | 16.7 | 16.7 | 16.8 | pass |
| 400 cards | pan-fit | 1x | 16.7 | 16.8 | 16.8 | pass |
| 400 cards | dive | 1x | 16.7 | 16.7 | 16.8 | pass |
| 1,500 cards | pan-fit | 1x | 16.7 | 16.8 | 33.3 | pass |
| M11 shape | pan-fit | 1x | 16.7 | 16.7 | 16.8 | pass |
| M11 shape | all-open | 1x | 16.7 | 16.7 | 16.8 | pass |
| M11 shape | dive | 1x | 16.7 | 16.8 | 16.8 | pass |

C2 and C3 pass in run 5. No p95 increased by one tick (16.7 ms) or more against run 4.
- The dive of the 400-card map at 4x has p95 33.3 ms (two ticks), as in runs 2, 3 and 4. It is in the limit of 35.0 ms. It is more than 33 ms if 33 ms is a strict value.
- The dive of the M11 tree at 4x has p95 16.8 ms, as in run 4.
- C3 at 1x is 80 ms for the M11 tree. In run 4 it was 69 ms.

Run 6 (on the source of the commit after f396423 that records this run. That commit puts the cut of a screen box to the screen edge in one function, for the rings and the boundary flows. The drawing does not change). Before the run, no test suite and no other measurement operated on the host for 20 s. During the run, no other measurement and no screenshot operated on the host.

| Data | Scenario | CPU | Median (ms) | p95 (ms) | Max (ms) | Result |
|---|---|---|---|---|---|---|
| M11 tree | C3 load | 4x | 277 ms | | | information |
| M11 shape | C3 load | 4x | 285 ms | | | information |
| M11 tree | pan-fit | 4x | 16.7 | 16.8 | 16.8 | pass |
| M11 tree | all-open | 4x | 16.7 | 16.8 | 49.8 | pass |
| M11 tree | dive | 4x | 16.7 | 16.8 | 33.3 | pass |
| 400 cards | pan-fit | 4x | 16.7 | 16.8 | 33.2 | pass |
| 400 cards | dive | 4x | 16.7 | 33.3 | 50.0 | pass |
| 1,500 cards | pan-fit | 4x | 16.7 | 16.7 | 33.3 | pass |
| M11 shape | pan-fit | 4x | 16.7 | 16.7 | 49.9 | pass |
| M11 shape | all-open | 4x | 16.7 | 16.8 | 49.9 | pass |
| M11 shape | dive | 4x | 16.7 | 16.8 | 33.4 | pass |
| M11 tree | C3 load | 1x | 79 ms | | | pass |
| M11 shape | C3 load | 1x | 68 ms | | | pass |
| M11 tree | pan-fit | 1x | 16.7 | 16.7 | 33.4 | pass |
| M11 tree | all-open | 1x | 16.7 | 16.7 | 16.8 | pass |
| M11 tree | dive | 1x | 16.7 | 16.8 | 16.8 | pass |
| 400 cards | pan-fit | 1x | 16.7 | 16.8 | 16.8 | pass |
| 400 cards | dive | 1x | 16.7 | 16.7 | 16.8 | pass |
| 1,500 cards | pan-fit | 1x | 16.7 | 16.8 | 16.8 | pass |
| M11 shape | pan-fit | 1x | 16.7 | 16.8 | 16.8 | pass |
| M11 shape | all-open | 1x | 16.7 | 16.7 | 16.8 | pass |
| M11 shape | dive | 1x | 16.7 | 16.8 | 16.8 | pass |

C2 and C3 pass in run 6. No p95 increased by one tick (16.7 ms) or more against run 5.
- The dive of the 400-card map at 4x has p95 33.3 ms (two ticks), as in runs 2 to 5. It is in the limit of 35.0 ms. It is more than 33 ms if 33 ms is a strict value.
- C3 at 1x is 79 ms for the M11 tree.

The fit on a phone screen (after run 6). On a screen of 390 x 844 pixels, the fit of a map kept a band of 12 percent of the screen width at each side for the portals. But on that screen each portal is in the top or the bottom row, thus the bands were empty. The frame of the open map was 296 of 390 pixels wide (76 percent), and the help line was cut at the right. The correction: the side bands are 0 when the widest portal is wider than 12 percent of the screen width, and the help line wraps between its parts. The bottom row of the portals moves up by one line for each added line. At 1440 x 900 nothing changes.
The A/B script `ab_draw.js` (not in the repository) timed `systemapCanvas.view` (one draw at half resolution) at the fit of `P0/A0/B0` of the M11 shape, 300 times, at 390 x 844. Acceptance, written before the run: in each of 3 interleaved pairs, the median after the change is at most the median before plus 5 percent plus 0.1 ms. Other browsers operated on the host at the same time. The browser gives times in steps of 0.1 ms. The two pages have different fits, thus they draw different areas.

| Pair | Before (ms) | After (ms) | Result |
|---|---|---|---|
| 1 | 0.3 | 0.3 | pass |
| 2 | 0.4 | 0.4 | pass |
| 3 | 0.3 | 0.4 | pass |

This measures the script time only, not the paint of the canvas. C2 was not measured again for this change.

### The deep zoom: A/B runs (2026-11-05)

A measurement-only study found the cause of the two-tick frames in the dive of the 400-card map. Text is the largest cost. The slow frames are at a camera scale of about 0.3 to 3, where 300 to 600 cards show their name and their text. The change has four parts:

1. While the camera moves, a large open map with no nested map and no port is drawn from images of the full map (`mapImage`, now in `page_canvas_image.py`). There is one image for each half step of zoom, at the moving resolution, with at most 2 million pixels. A map keeps 4 images. The page makes each image in slices of 25 cards, until 8 ms after the start of a moving frame. Between two steps, the frame draws the two images with an opacity that follows the zoom.
2. The wrapped lines of a card are kept for each count of columns, not for each font size.
3. After the font loads, the page sets each font and measures the words of the cards, in its idle time.
4. While the camera moves, a card with a name below 10 px shows only its name (`MOVE_TEXT`). This is a visible change.

The study proposed a fallback to the image of the step next to the current step. A screenshot of frame 25 of the dive showed marks in place of the cards with text. Thus part 1 blends the two images around the scale and has no such fallback.

The script is `ab.py` in the scratch directory of the work, with the real driver `canvas_frames.js`. Its docstring has the acceptance values, which were written before run 1:
- Goal: the dive of the 400-card map at 4x has p95 at most 17.5 ms (one tick plus 5 percent) in each run.
- No regression: B is a regression in a scenario if its p95 is more than the p95 of A in the same run by one tick or more, in 2 or more runs.
- C3: the median of B is at most 1.10 times the median of A, for the M11 tree and the M11 shape, at 1x and 4x.

A is the page at commit 2363822. In each run, A and B alternate for each scenario, and the first of the two changes from run to run. Each scenario has 180 frames. Other agents operated Chromium on the same host. The load average was 0.3 to 1.9.

Parts 1 to 3 (B), 3 runs. The goal fails.

| Data | Scenario | CPU | p95 A (ms) | p95 B (ms) | Max A (ms) | Max B (ms) |
|---|---|---|---|---|---|---|
| 400 cards | dive | 4x | 33.3, 33.3, 33.3 | 33.3, 33.3, 16.8 | 50, 33.4, 50 | 50, 50, 33.3 |
| M11 tree | dive | 4x | 16.8, 16.7, 16.8 | 16.7, 16.8, 16.7 | 33.4, 33.4, 33.3 | 33.3, 33.3, 33.3 |
| M11 tree | pan-fit | 4x | 16.8, 16.7, 16.8 | 16.7, 16.8, 16.8 | 33.4, 33.3, 16.8 | 16.8, 33.3, 16.8 |
| M11 tree | all-open | 4x | 16.8, 16.8, 16.8 | 16.8, 16.8, 16.8 | 66.6, 50, 50 | 50, 49.9, 49.9 |
| 400 cards | pan-fit | 4x | 16.8, 16.8, 16.8 | 16.8, 16.7, 16.8 | 16.8, 16.8, 16.8 | 33.4, 33.4, 16.8 |
| 1,500 cards | pan-fit | 4x | 16.8, 16.8, 16.7 | 16.7, 16.7, 16.7 | 16.8, 16.8, 16.8 | 16.8, 16.8, 33.3 |
| M11 shape | pan-fit | 4x | 16.8, 16.8, 16.7 | 16.8, 16.8, 16.8 | 33.2, 33.3, 33.3 | 33.3, 16.8, 33.4 |
| M11 shape | all-open | 4x | 16.8, 16.7, 16.8 | 16.8, 16.7, 16.7 | 83.2, 33.4, 49.9 | 50, 33.4, 33.3 |
| M11 shape | dive | 4x | 16.7, 16.7, 16.8 | 16.8, 16.7, 16.8 | 16.8, 33.3, 16.8 | 16.8, 16.8, 33.4 |

C3 for parts 1 to 3 (ms, 3 runs): M11 tree 1x A 67, 80, 69 and B 66, 76, 69 (median ratio 1.00); M11 tree 4x A 218, 250, 243 and B 230, 243, 248 (1.00); M11 shape 1x A 70, 71, 70 and B 69, 71, 74 (1.02); M11 shape 4x A 217, 265, 249 and B 267, 218, 236 (0.95).

A trace of the dive with parts 1 to 3 (one run, not the bench) showed the cause: the images cover the scale 0.29 to 0.5 or to 0.7. The step above 0.7 needs an image of more than 2 million pixels. Thus the frames from 0.5 to 0.9 have the normal drawing, and some of them take two ticks.

Parts 1 to 4 (B), 5 runs (3 runs and then 2 runs). The goal passes in 5 of 5 runs. No scenario has a regression.

| Data | Scenario | CPU | p95 A (ms) | p95 B (ms) | Max A (ms) | Max B (ms) |
|---|---|---|---|---|---|---|
| 400 cards | dive | 4x | 33.3, 33.3, 33.3, 33.3, 33.3 | 16.8, 16.8, 16.8, 16.8, 16.8 | 83.3, 50, 50, 50, 50 | 33.4, 33.3, 33.4, 33.3, 33.4 |
| M11 tree | dive | 4x | 16.8, 16.8, 16.7, 16.8, 16.8 | 16.7, 16.8, 16.8, 16.7, 16.7 | 33.4, 33.4, 33.3, 33.3, 33.4 | 33.3, 33.2, 16.8, 50, 16.8 |
| M11 tree | pan-fit | 4x | 16.7, 16.8, 16.8, 16.8, 16.8 | 16.7, 16.8, 16.7, 16.8, 16.7 | 33.3, 50, 33.3, 33.3, 33.3 | 33.4, 66.7, 16.8, 33.4, 16.8 |
| M11 tree | all-open | 4x | 16.8, 16.8, 16.8, 16.8, 16.7 | 16.8, 16.7, 16.8, 16.8, 16.7 | 49.9, 50, 50, 66.6, 50 | 33.4, 50, 33.4, 66.7, 33.4 |
| 400 cards | pan-fit | 4x | 16.7, 16.8, 16.8, 16.8, 16.7 | 16.8, 16.8, 16.7, 16.8, 16.7 | 33.3, 16.8, 16.8, 33.2, 16.8 | 33.3, 33.3, 33.4, 33.3, 33.2 |
| 1,500 cards | pan-fit | 4x | 16.8, 16.8, 16.7, 16.7, 16.8 | 16.8, 16.8, 16.7, 16.7, 16.7 | 16.8, 16.8, 16.8, 16.8, 33.2 | 33.3, 33.3, 33.3, 16.8, 33.3 |
| M11 shape | pan-fit | 4x | 16.8, 16.7, 16.8, 16.8, 16.7 | 16.7, 16.8, 16.8, 16.8, 16.8 | 33.3, 16.8, 16.8, 33.3, 16.8 | 33.3, 16.8, 33.3, 33.2, 16.8 |
| M11 shape | all-open | 4x | 16.7, 16.8, 16.8, 16.8, 16.7 | 16.8, 16.8, 16.8, 16.8, 16.7 | 50, 50, 50, 49.9, 49.9 | 49.9, 50, 33.3, 33.3, 33.3 |
| M11 shape | dive | 4x | 16.8, 16.7, 16.8, 16.7, 16.8 | 16.8, 16.7, 16.8, 16.7, 16.8 | 33.3, 33.3, 33.3, 33.4, 33.3 | 16.8, 33.3, 33.3, 16.8, 16.8 |

C3 for parts 1 to 4 (ms, 5 runs): M11 tree 1x A 72, 62, 74, 68, 68 and B 73, 73, 59, 66, 70; M11 tree 4x A 248, 272, 246, 245, 236 and B 269, 260, 231, 242, 249; M11 shape 1x A 76, 67, 83, 68, 66 and B 75, 68, 87, 71, 68; M11 shape 4x A 251, 237, 232, 280, 253 and B 248, 202, 282, 239, 227. The median ratio B/A of each batch is 0.87 to 1.05. Thus C3 passes the acceptance value of 1.10.

The maximum interval of B in the 400-card pan-fit is 33.3 ms in 5 of 5 runs, and 16.8 ms in 3 of 5 runs of A. The p95 does not change. A possible cause: at the fit of the map, a pan frame also makes slices of the images.

Variant D: parts 1 to 4, but only a frame of a zoom makes slices, and a pan makes none. Three runs of all scenarios (A and D) gave p95 16.8, 16.8 and 33.3 ms for the 400-card dive. Thus the goal failed in 1 of 3 runs. The load average was 2.0 at the end of these runs. No other scenario had a regression. C3 of the M11 shape at 4x had a median ratio of 1.23 (A 244, 227, 232 ms; D 291, 285, 236 ms), which fails the value of 1.10. D does not change the code of the load. Thus this result is possibly noise, but it was not measured again.

Then A, B (parts 1 to 4) and D were interleaved in the same session:

| Runs | Scenario | p95 A (ms) | p95 B (ms) | p95 D (ms) | Max A (ms) | Max B (ms) | Max D (ms) |
|---|---|---|---|---|---|---|---|
| 3 | 400 cards dive | 33.3, 33.3, 33.3 | 16.8, 16.8, 16.7 | 16.8, 16.8, 16.8 | 50, 66.6, 33.4 | 33.3, 33.4, 33.4 | 33.4, 33.4, 33.4 |
| 3 | 400 cards pan-fit | 16.7, 16.7, 16.8 | 16.8, 16.8, 16.8 | 16.7, 16.7, 16.8 | 16.8, 33.3, 33.3 | 33.3, 33.3, 33.3 | 33.4, 33.3, 16.8 |
| 3 | 1,500 cards pan-fit | 16.7, 16.7, 16.7 | 16.7, 16.8, 16.8 | 16.8, 16.7, 16.7 | 16.8, 33.4, 16.8 | 16.8, 33.3, 33.3 | 33.2, 16.8, 16.8 |
| 6 | 400 cards dive | 33.3, 33.4, 33.3, 33.4, 33.3, 33.3 | 16.8, 16.8, 16.7, 16.8, 16.8, 16.8 | 16.8 in 6 of 6 | 50, 66.6, 33.4, 50.1, 50, 66.7 | 33.4 in 6 of 6 | 33.3 or 33.4 in 6 of 6 |

In all runs of the 400-card dive, B (parts 1 to 4) has p95 of one tick in 14 of 14 runs, and A has p95 of two ticks in 14 of 14 runs. D has p95 of one tick in 11 of 12 runs. The pan maximum of D is not better than the pan maximum of B in these runs. Thus D is rejected, and the code is B.

The final code is B with shorter comments and lines, and the same behavior. Three more interleaved runs of it (A and B) gave:

| Data | Scenario | CPU | p95 A (ms) | p95 B (ms) | Max A (ms) | Max B (ms) |
|---|---|---|---|---|---|---|
| 400 cards | dive | 4x | 33.3, 33.3, 33.2 | 16.7, 16.8, 16.8 | 66.7, 50, 66.7 | 33.3, 33.3, 33.3 |
| 400 cards | pan-fit | 4x | 16.8, 16.7, 16.8 | 16.7, 16.8, 16.8 | 33.3, 16.8, 16.8 | 16.8, 16.8, 33.3 |
| M11 tree | dive | 4x | 16.8, 16.8, 16.8 | 16.8, 16.7, 16.8 | 66.7, 33.3, 49.9 | 16.8, 33.3, 100 |
| M11 tree | pan-fit | 4x | 16.8, 16.8, 16.7 | 16.7, 16.7, 16.8 | 33.3, 33.3, 16.8 | 16.8, 33.3, 33.4 |

C3 of the final code (ms): M11 tree 1x A 69, 84, 70 and B 68, 66, 70 (median ratio 0.97); M11 tree 4x A 260, 257, 240 and B 267, 315, 228 (1.04); M11 shape 1x A 77, 87, 81 and B 67, 70, 70 (0.86); M11 shape 4x A 282, 262, 252 and B 229, 265, 246 (0.94). The load average went from 1.0 to 2.4 during these runs.

Result: the goal passes. The dive of the 400-card map at 4x has p95 of one tick in 17 of 17 runs of parts 1 to 4, and of two ticks in 17 of 17 runs of A. No scenario has a regression of its p95, and C3 is in its acceptance value in each batch of parts 1 to 4.

The pixels. A second script (`probe.js`) gives the moving frame of A and B at the same camera, after a wait of 2 s, at 720 x 450 device pixels. The value is the mean of the largest channel difference of each pixel (0 to 255), and the part of the pixels with a difference of more than 64:

| Frame of the dive | Scale | Parts 1 to 3 | Parts 1 to 4 |
|---|---|---|---|
| 14 | 0.30 | 9.28, 0.3 percent | not measured |
| 20 | 0.37 | 4.77, 0.3 percent | 4.55, 0.3 percent |
| 26 | 0.47 | 8.56, 0.3 percent | 9.06, 0.5 percent |
| 32 | 0.62 | not measured | 7.76, 2.5 percent |
| 45 | 1.19 | not measured | 2.98, 1.3 percent |

In the image frames, the cards are a little grey, because the blend of the lower image has more of the mark color. The text of a card in an image can show more characters than in the normal drawing, because the image has a different scale. At frame 45, part 4 removes the text under the name of each card (shown by the screenshot). These are the visible effects while the camera moves. The frame at full resolution after the camera stops does not change.

Not measured: a device with a GPU (part 1 reads one pixel of each image slice with `getImageData`), a device pixel ratio of 2, normal CPU speed, and parts 1 to 3 without part 4 in more runs.

### Runs 7 to 9: after the images, the fades and the phone fit (2026-11-05)

Runs 7, 8 and 9 are on the source of commit d6994df. Since run 6, that commit adds three changes to the page: the images of a large map while the camera moves (parts 1 to 4 of the deep zoom above), the fades of the boundary flows (F1 to F3 below), and the fit on a phone screen. The script `run_frames.py` (in the scratch directory of the work, not in the repository) operated `bench/jev/canvas_frames.py` without changes. Its docstring has the acceptance values, which were written before run 7:
- Each scenario passes its limit of `canvas_frames.py` in each run.
- The dive of the 400-card map at 4x has p95 at most 16.8 ms in each run.
- No p95 increases by one tick (16.7 ms) or more against the same scenario in run 5 or in run 6.

The host. Before each run, a polling loop with `ps` (one sample each 2 s) waited until no Chromium, node or pytest process operated for 30 s. Each run took 85 s. During the runs, the agent of a different task operated Chromium on the host:
- Run 7: no sample during the run. An error in the script lost it. 30 s before the run, the other agent operated `node info.js` with Chromium.
- Run 8: the other agent operated `node dive.js` with Chromium from 8 s after the start to the end of the run.
- Run 9: the other agent operated `node move.js` with Chromium for approximately 20 s of the run, from 27 s after the start.
- The load average (1 minute) was 0.2 to 1.4 during the samples.

Thus the host was not quiet in runs 8 and 9, and possibly not in run 7. The task specified 2 runs. Run 9 is an added run, because run 8 was not on a quiet host. A busy host can make a frame interval longer. It cannot make it shorter.

For C3, the value is the load time. For a scenario, the value is the p95 frame interval in ms.

| Data | Scenario | CPU | Run 7 | Run 8 | Run 9 | Max of runs 7, 8, 9 (ms) | Runs 5, 6 | Result |
|---|---|---|---|---|---|---|---|---|
| M11 tree | C3 load | 4x | 294 ms | 224 ms | 294 ms | | 241 ms, 277 ms | information |
| M11 shape | C3 load | 4x | 246 ms | 229 ms | 254 ms | | 252 ms, 285 ms | information |
| M11 tree | pan-fit | 4x | 16.8 | 16.8 | 16.8 | 33.3, 33.4, 33.3 | 16.8, 16.8 | pass |
| M11 tree | all-open | 4x | 16.8 | 16.8 | 16.8 | 33.3, 49.9, 49.9 | 16.7, 16.8 | pass |
| M11 tree | dive | 4x | 16.7 | 16.7 | 16.7 | 16.8, 16.8, 16.8 | 16.8, 16.8 | pass |
| 400 cards | pan-fit | 4x | 16.8 | 16.7 | 16.7 | 16.8, 33.4, 16.8 | 16.7, 16.8 | pass |
| 400 cards | dive | 4x | 16.7 | 16.8 | 16.8 | 33.3, 33.4, 33.3 | 33.3, 33.3 | pass |
| 1,500 cards | pan-fit | 4x | 16.8 | 16.7 | 16.8 | 33.3, 16.8, 33.4 | 16.7, 16.7 | pass |
| M11 shape | pan-fit | 4x | 16.7 | 16.7 | 16.7 | 16.8, 16.8, 33.3 | 16.7, 16.7 | pass |
| M11 shape | all-open | 4x | 16.8 | 16.8 | 16.8 | 33.3, 83.3, 33.2 | 16.7, 16.8 | pass |
| M11 shape | dive | 4x | 16.7 | 16.8 | 16.7 | 16.8, 16.8, 33.4 | 16.7, 16.8 | pass |
| M11 tree | C3 load | 1x | 77 ms | 71 ms | 64 ms | | 80 ms, 79 ms | pass |
| M11 shape | C3 load | 1x | 68 ms | 72 ms | 70 ms | | 68 ms, 68 ms | pass |
| M11 tree | pan-fit | 1x | 16.8 | 16.8 | 16.8 | 16.8, 16.8, 16.8 | 16.8, 16.7 | pass |
| M11 tree | all-open | 1x | 16.7 | 16.7 | 16.7 | 16.8, 16.8, 16.8 | 16.7, 16.7 | pass |
| M11 tree | dive | 1x | 16.7 | 16.7 | 16.7 | 16.8, 16.8, 16.8 | 16.7, 16.8 | pass |
| 400 cards | pan-fit | 1x | 16.7 | 16.7 | 16.7 | 16.8, 16.8, 16.8 | 16.8, 16.8 | pass |
| 400 cards | dive | 1x | 16.7 | 16.8 | 16.8 | 16.8, 16.8, 99.9 | 16.7, 16.7 | pass |
| 1,500 cards | pan-fit | 1x | 16.7 | 16.7 | 16.8 | 16.8, 16.8, 16.8 | 16.8, 16.8 | pass |
| M11 shape | pan-fit | 1x | 16.8 | 16.8 | 16.7 | 16.8, 16.8, 16.8 | 16.7, 16.8 | pass |
| M11 shape | all-open | 1x | 16.8 | 16.7 | 16.7 | 16.8, 33.3, 16.8 | 16.7, 16.7 | pass |
| M11 shape | dive | 1x | 16.7 | 16.7 | 16.8 | 16.8, 16.8, 16.8 | 16.8, 16.8 | pass |

C2 and C3 pass in runs 7, 8 and 9. The three acceptance values pass:
- The dive of the 400-card map at 4x has p95 16.7, 16.8 and 16.8 ms (one tick). In runs 2 to 6 it was 33.3 ms (two ticks). This agrees with the A/B runs of the deep zoom.
- No p95 increased by one tick or more against run 5 or run 6. The largest p95 of a scenario is 16.8 ms.
- C3 at 1x is 64 to 77 ms for the M11 tree. In runs 5 and 6 it was 80 and 79 ms.

### A/B after the review fixes (2026-11-05)

A is commit d6994df. B is the same source with the fixes of the review of that commit. These fixes change the renderer:
- An image of a large map while the camera moves has 1.41 times the moving resolution. Before, the frame showed the lower image up to 1.41 times larger than its pixels, and the names were not clear.
- The image cache removes each image whose key is not current, also after a change of the device pixel ratio. The key of a marks image has the device pixel ratio.
- Only the map that asked last keeps its images. The marks images of all maps have at most 16 million pixels together.
- After a change of the screen size, a camera at the fit of the open map fits that map again.
- Changes that make the code simpler, with no change of behavior (`/simplify`), and a cache of the help lines.

The script `run_ab.py` (in the scratch directory of the work, not in the repository) operated `bench/jev/canvas_frames.py` of each copy without changes. Its docstring has the acceptance values, which were written before the first run:
- B: each scenario passes its limit of `canvas_frames.py` in each of the 3 runs.
- B against A: for each scenario, the median of the 3 p95 values of B is not more than the median of A plus one tick (16.6 ms or more counts as one tick).
- The dive of the 400-card map at 4x passes its limit in each run of B, because the images now have 2 times the pixels.

The order was A1, B1, A2, B2, A3, B3 in one session. The first start failed before a measurement: the copies had only `src` and `bench`, and the script needs the map of the repository. The second start used full copies. Before each run, a polling loop with `ps` waited until no Chromium, node or pytest process operated for 30 s. The samples during the runs show only the processes of the run. The load average (1 minute) was 0.5 to 1.6 during the runs.

For C3, the value is the load time. For a scenario, the value is the p95 frame interval in ms.

| Data | Scenario | CPU | A: runs 1, 2, 3 | B: runs 1, 2, 3 | Median B minus median A | Result of B |
|---|---|---|---|---|---|---|
| M11 tree | C3 load | 4x | 266, 240, 240 ms | 230, 246, 288 ms | +6 ms | information |
| M11 shape | C3 load | 4x | 245, 268, 293 ms | 218, 226, 220 ms | -48 ms | information |
| M11 tree | pan-fit | 4x | 16.8, 16.8, 16.7 | 16.8, 16.7, 16.8 | 0 | pass |
| M11 tree | all-open | 4x | 16.8, 16.8, 16.8 | 16.8, 16.8, 16.8 | 0 | pass |
| M11 tree | dive | 4x | 16.8, 16.8, 16.7 | 16.7, 16.7, 16.7 | -0.1 | pass |
| 400 cards | pan-fit | 4x | 16.7, 16.8, 16.7 | 16.7, 16.8, 16.8 | +0.1 | pass |
| 400 cards | dive | 4x | 16.8, 16.8, 16.8 | 16.8, 16.8, 16.8 | 0 | pass |
| 1,500 cards | pan-fit | 4x | 16.8, 16.7, 16.8 | 16.8, 16.8, 16.7 | 0 | pass |
| M11 shape | pan-fit | 4x | 16.7, 16.7, 16.7 | 16.7, 16.7, 16.8 | 0 | pass |
| M11 shape | all-open | 4x | 16.7, 16.8, 16.7 | 16.7, 16.8, 16.8 | +0.1 | pass |
| M11 shape | dive | 4x | 16.7, 16.8, 16.8 | 16.7, 16.8, 16.8 | 0 | pass |
| M11 tree | C3 load | 1x | 85, 66, 66 ms | 66, 67, 69 ms | +1 ms | pass |
| M11 shape | C3 load | 1x | 68, 73, 69 ms | 71, 66, 70 ms | +1 ms | pass |
| M11 tree | pan-fit | 1x | 16.8, 16.7, 16.7 | 16.7, 16.8, 16.7 | 0 | pass |
| M11 tree | all-open | 1x | 16.7, 16.7, 16.7 | 16.8, 16.8, 16.7 | +0.1 | pass |
| M11 tree | dive | 1x | 16.7, 16.8, 16.8 | 16.7, 16.7, 16.8 | -0.1 | pass |
| 400 cards | pan-fit | 1x | 16.7, 16.7, 16.7 | 16.7, 16.8, 16.7 | 0 | pass |
| 400 cards | dive | 1x | 16.7, 16.8, 16.7 | 16.8, 16.7, 16.8 | +0.1 | pass |
| 1,500 cards | pan-fit | 1x | 16.7, 16.7, 16.8 | 16.8, 16.8, 16.8 | +0.1 | pass |
| M11 shape | pan-fit | 1x | 16.7, 16.7, 16.7 | 16.7, 16.8, 16.7 | 0 | pass |
| M11 shape | all-open | 1x | 16.7, 16.7, 16.8 | 16.7, 16.7, 16.8 | 0 | pass |
| M11 shape | dive | 1x | 16.7, 16.8, 16.8 | 16.8, 16.7, 16.8 | 0 | pass |

The three acceptance values pass. All p95 values of A and B are one tick.

Two probes of the same fixes, information only. No acceptance value was written before these probes, so they give no pass or fail:
- The names in the images, with `move.js` and `ink.py` of the visual check of d6994df (the same method). The 400-card map, 1440 x 900, a pan of 40 frames, then the still frame 300 ms later. A name is gone when its ink in the moving frame is less than 0.35 times its ink in the still frame. At 2 times the fit, light: A 50 of 210 gone (median ratio 0.52), B 11 of 210 (0.85). Dark: A 14 of 210, B 5 of 210. At 2.5 times the fit, light: A 65 of 144 (0.36). In B the images at this zoom have more than 2 million pixels, so the frame uses the usual drawing: 0 of 288 (1.06). 390 x 844 at 8 times the fit, light: A 11 of 21 (0.35). B uses the usual drawing: 0 of 42 (1.01).
- The image cache after a change of the device pixel ratio from 1 to 2 (`dpr.js` of the code review, with a count of the canvases that the page makes). The 400-card map at 1.6 and 2 times the fit, a pan of 120 frames, then two pans at the ratio 2. At 1.6 times the fit, the count of canvases in all after each pan was 5, 123 and 243 for A (about one new canvas in each frame at the ratio 2), and 4, 5 and 5 for B. In B at the ratio 2, the higher image is more than 2 million pixels, so the frames use the usual drawing.

### A/B after the phone fit (2026-11-06)

A is commit 4905fcf. B is the same source with the changes for the fit on a phone screen:
- The fit of a map has a margin of 4 % of the screen at each side, not 6 %. The measured cameras (`fit`, `openBox`, `deepFit`) use this margin. Thus B draws the maps of the measurements a little larger.
- The help line has one line on a plate. The bands of the fit do not change with the help line.
- The parts of the path become narrower when the path is wider than the screen.
- In a map with a nested map or a port, the name of a container or a region stays at the left screen edge, in its box.

The script `run_ab.py` (in the scratch directory of the work, not in the repository) operated `bench/jev/canvas_frames.py` of each copy without changes. Its docstring has the acceptance values, which were written before the first run:
- B: each scenario passes its limit of `canvas_frames.py` in each of the 3 runs.
- B against A: for each scenario, the median of the 3 p95 values of B is not more than the median of A plus one tick (16.6 ms or more counts as one tick).
- The dive of the 400-card map at 4x has a p95 of at most 16.8 ms (one tick) in each run of B.

The order was A1, B1, A2, B2, A3, B3 in one session, from 10:52 to 11:01. Other agents operated Chromium on the host at the same time. Thus the script did not wait for a quiet host. During run A1, a screenshot script of this work also operated Chromium. The load average (1 minute) was 0.56 to 1.77 during the runs.

For C3, the value is the load time. For a scenario, the value is the p95 frame interval in ms.

| Data | Scenario | CPU | A: runs 1, 2, 3 | B: runs 1, 2, 3 | Median B minus median A | Result of B |
|---|---|---|---|---|---|---|
| M11 tree | C3 load | 4x | 253, 224, 259 ms | 211, 259, 261 ms | +6 ms | information |
| M11 shape | C3 load | 4x | 267, 286, 275 ms | 270, 251, 235 ms | -24 ms | information |
| M11 tree | pan-fit | 4x | 16.7, 16.8, 16.8 | 16.7, 16.8, 16.8 | 0 | pass |
| M11 tree | all-open | 4x | 16.8, 16.8, 16.8 | 16.7, 16.8, 16.8 | 0 | pass |
| M11 tree | dive | 4x | 16.8, 16.8, 16.8 | 16.8, 16.8, 16.8 | 0 | pass |
| 400 cards | pan-fit | 4x | 16.8, 16.8, 16.8 | 16.8, 16.8, 16.8 | 0 | pass |
| 400 cards | dive | 4x | 16.8, 16.8, 16.8 | 16.8, 16.8, 16.7 | 0 | pass |
| 1,500 cards | pan-fit | 4x | 16.8, 16.8, 16.8 | 16.8, 16.7, 16.8 | 0 | pass |
| M11 shape | pan-fit | 4x | 16.8, 16.8, 16.8 | 16.7, 16.8, 16.7 | -0.1 | pass |
| M11 shape | all-open | 4x | 16.8, 16.8, 16.8 | 16.8, 16.8, 16.7 | 0 | pass |
| M11 shape | dive | 4x | 16.8, 16.8, 16.8 | 16.8, 16.8, 16.8 | 0 | pass |
| M11 tree | C3 load | 1x | 65, 69, 73 ms | 68, 71, 67 ms | -1 ms | pass |
| M11 shape | C3 load | 1x | 79, 66, 77 ms | 74, 70, 71 ms | -6 ms | pass |
| M11 tree | pan-fit | 1x | 16.8, 16.7, 16.8 | 16.7, 16.8, 16.8 | 0 | pass |
| M11 tree | all-open | 1x | 16.7, 16.7, 16.7 | 16.8, 16.8, 16.7 | +0.1 | pass |
| M11 tree | dive | 1x | 16.7, 16.8, 16.8 | 16.7, 16.7, 16.8 | -0.1 | pass |
| 400 cards | pan-fit | 1x | 16.7, 16.7, 16.8 | 16.8, 16.8, 16.7 | +0.1 | pass |
| 400 cards | dive | 1x | 16.7, 16.8, 16.8 | 16.8, 16.8, 16.7 | 0 | pass |
| 1,500 cards | pan-fit | 1x | 16.7, 16.7, 16.7 | 16.7, 16.8, 16.7 | 0 | pass |
| M11 shape | pan-fit | 1x | 16.8, 16.7, 16.8 | 16.8, 16.7, 16.8 | 0 | pass |
| M11 shape | all-open | 1x | 16.8, 16.7, 16.8 | 16.8, 16.8, 16.8 | 0 | pass |
| M11 shape | dive | 1x | 16.8, 16.7, 16.8 | 16.7, 16.7, 16.7 | -0.1 | pass |

The three acceptance values pass. All p95 values of A and B are one tick.

The fit on the screens of the review, information only (`fit.js` of the work, the M11 tree of `m11_tree` in `canvas_frames.py`, the top map and the first map on levels 1 to 3). At 390 x 844, the frame of the open map filled 88 % of the screen width in A and 92 % in B. At 844 x 390, it filled 88 % in A and 92 % in B. At 1440 x 900, it filled 100 % of the free width (the width less the bands of the side portals) in A and in B. In A at 390 x 844, the help line had two lines. Its second line was over the cards of the map below the open map, and the name of the region "1 WORK" was cut at the left screen edge. In B, the browser test `test_the_fit_uses_the_screen` examines these screens and the turn from 390 x 844 to 844 x 390.

## F1 to F3: the fade of the boundary flows (2026-11-05)

Scope: the boundary flows of the canvas page (`page_canvas_fade.py`, `page_canvas_draw.py`, `page_canvas.py`). Before this change, a boundary flow was drawn only in a frame where a clear path existed. Thus a line appeared at one time and went at one time. The maintainer rule is "Each change follows the zoom continuously. Nothing appears at one time."

The change:
- Each path of a line has a value from 0 to 1 that the frames keep. A value changes by 1 in 200 ms or more, and by 0.2 or less in one frame.
- A path that goes into a card, a text or a portal is still not drawn. Thus the value must be near 0 before a box gets to the path. For each box and each segment, the distance now and in the frame before give the frames until they touch. The value is never more than 0.1 times that count of frames.
- A line that changes to a different path fades out on the earlier path and fades in on the new path. A line of a map above that a deeper map replaces fades out.
- The last segments to a portal move from the near corner to the middle of the portal edge. Before, they jumped from one form to the other.
- A portal with a `show` of less than 0.5 does not stop a path. It only makes the line fade.

The scripts were in the scratchpad of the agent and are not in the repository: `fade_dive.py` with `fade_dive.js`, `frame_cost.js`, and two shell loops for the A/B runs. The acceptance values were in the docstring of `fade_dive.py` before the first run:
- F1: in a dive of 200 frames, the drawn alpha of each boundary flow path changes by at most 0.25 between two frames. A path that is not drawn has the alpha 0. Pass or fail.
- F0, information only: the earlier renderer gives no alpha. A drawn flow counts as alpha 1.
- F2, information only: p95 frame interval of the C2 scenarios at 4 times throttling, A/B interleaved, 3 runs each.
- F3, information only: the median and p95 time of one draw in a zoom from 0.8 to 1.25 times the fit of P0 and of P0/A0, at 4 times throttling, A/B interleaved, 3 runs each.

The data is the M11 shape tree (`nested_tree` of `canvas_frames.py`). The viewport is 1440 x 900, without reduced motion, with one animation frame for each camera step. Other agents used Chromium on the host at the same time. Thus the times are noisy, and only the A/B difference in the same session has a meaning.

F1, the browser test (`tests/canvas_driver.js --fade`, acceptance 11 of `tests/test_canvas_browser.py`). Each move has 200 frames. The scale moves in log space and the move is slow at its two ends:

| Move | Line frames (A, B) | Earlier renderer: largest change | New renderer: largest change | Result |
|---|---|---|---|---|
| top fit into P0/A0 | 6, 5 | 1 | 0.087 | pass |
| P0/A0 out to the top fit | 6, 6 | 1 | 0.133 | pass |
| P0 into P0/A0 | 42, 41 | 1 | 0.169 | pass |
| zoom 0.5 to 3 times the fit of P0/A0 | 42, 42 | 1 | 0.116 | pass |

No drawn path went into a card that is not open, in the two renderers.

F1, more moves of `fade_dive.js` with the last version of the change (in and out are the two directions of the same camera path). These moves fail:

| Move | Direction | Largest change | Frames over 0.25 |
|---|---|---|---|
| top fit to P0 fit | out | 0.407 | 2 |
| P0 fit to P0/A0 fit | out | 0.277 | 2 |
| zoom 0.5 to 3 times the fit of P0/A0 | out | 0.475 | 2 |
| zoom 0.5 to 3 times the fit of P0 | out | 0.475 | 3 |

The same moves in the direction "in" pass (largest change 0.116 to 0.169). The dive between the top fit and the fit of P0/A0 passes in the two directions (0.088 and 0.133), and so does the dive between the top fit and the deepest map (0.083 and 0.165). The causes of the failures, from a frame-by-frame record:
- A card comes onto the screen 30 to 50 pixels from the line, and the next frame it touches the line. A box that is not on the screen is not in the obstacle list, thus the fade cannot start before it.
- A portal starts to move at one time, when the portal above it fades (`kept` in `apart`). It moves 8 to 12 pixels in each frame. A first-order speed does not see the start of the move.
- The end of the last segment moves to the middle of the portal edge at the speed of the camera. The speed then predicts a contact with the portal above that does not occur. The line fades and then comes back.

F2 (C2 scenarios at 4 times throttling, p95 frame interval in ms, A = before, B = after):

| Scenario | Run 1 A | Run 1 B | Run 2 A | Run 2 B | Run 3 A | Run 3 B |
|---|---|---|---|---|---|---|
| dive | 16.8 | 16.7 | 16.8 | 16.8 | 16.8 | 16.8 |
| all-open | 16.8 | 16.7 | 16.8 | 16.8 | 16.8 | 16.8 |

F3 (time of one draw in ms, 4 times throttling, 96 of 180 frames have boundary flows):

| Map | Run | A median | B median | A p95 | B p95 |
|---|---|---|---|---|---|
| P0 | 1 | 2.8 | 2.9 | 5.6 | 5.3 |
| P0 | 2 | 2.7 | 2.8 | 5.0 | 6.5 |
| P0 | 3 | 2.7 | 3.3 | 5.1 | 6.0 |
| P0/A0 | 1 | 3.2 | 3.6 | 9.6 | 8.0 |
| P0/A0 | 2 | 3.4 | 3.5 | 6.9 | 7.3 |
| P0/A0 | 3 | 3.2 | 3.5 | 5.3 | 8.6 |

The median draw time is 0.1 to 0.6 ms more with the fade. The p95 values change in the two directions, so the noise is larger than the difference. The C2 limits do not change.

## S1 to S4: the fades of the speed changes (2026-11-06)

Scope: decision 1 of the maintainer on 2026-11-06. Keep the two speed changes of a moving frame: the images of a large map, and the rule MOVE_TEXT. Add fades, so that nothing appears at one time. The rule of the maintainer is "Each change follows the zoom continuously. Nothing appears at one time." The limit of 35 ms for the p95 at 4 times throttling stays. The dive of the 400-card map at 4 times throttling must stay at one tick (p95 at most 16.8 ms).

Before this change, four changes occurred in one frame:
- 150 ms after the camera stops, the text that MOVE_TEXT hid came back.
- At the same time, the full drawing replaced the images of a large map.
- While the camera moved, the images replaced the usual drawing in the frame after they became complete.
- While the camera moved, the usual drawing replaced the images when the zoom went out of the range of the images.

The change (`page_canvas_image.py`, `page_canvas_draw.py`, `page_canvas.py`):
- HIDE is a value from 0 to 1. The text that MOVE_TEXT hides has the alpha 1 - HIDE. HIDE goes to 1 while the camera moves and to 0 after it stops.
- The image layer of a large map has a value from 0 to 1. In the layer, each image has a weight. The weight goes to 1 - t for the lower image and to t for the higher image of the step. When only one image of the step is complete, that image gets all of the layer. Thus an image that becomes complete fades in.
- Each value and each weight changes by 1 in 160 ms or more, and by 0.2 or less in one frame.
- Above the highest step with an image, the image of that step stays for a quarter step more of zoom, and the layer goes to 0 over that part of the zoom.
- While the zoom goes in, the images also fade in over the marks image of a map, in the last quarter step of zoom before the marks end.
- Each moving frame is drawn on a second canvas over the page canvas. While the camera moves, the page canvas has the opacity 0. When the camera stops, the page draws the full drawing at full resolution one time on the page canvas, under the last moving frame. Then the second canvas fades out. Each frame of that fade only changes the opacity of the second canvas.
- `fadeLater` asks for the next frame only when the camera did not change in the last 50 ms. Before, a fade that started in the frame of a camera change (`view` or a flight) got a second draw in each animation frame until it ended.

The scripts are in the scratch directory of the work, not in the repository: `run_ab.py` for the A/B, `pixels.js` and `still.js` for the pixels, and `explore*.js` with `variant.py` for a record of each frame. The driver of the A/B is `bench/jev/canvas_frames.js` of B. Its modes `dive-stop` and `pan-stop` are new. They only operate the camera with `systemapCanvas.view`, thus they also operate the page of A. A is the page of commit 4905fcf.

The acceptance values of `run_ab.py` were in its docstring before the first run:
1. The dive of the 400-card map at 4x: the p95 of B is at most 16.8 ms in each of the 3 runs.
2. Each scenario of B (with the moving part of `dive-stop` and `pan-stop`) has a p95 of at most 35.0 ms at 4x in each run.
3. In `dive-stop` and `pan-stop` of each data at 4x, the largest interval between two animation frames in the 700 ms after the move is at most 35.0 ms in each run of B. The values of A are information.
4. No regression: for each scenario, the median of the 3 p95 values of B is less than the median of A plus one tick (16.6 ms).
5. Information only: C3 of the M11 shape at 1x.

The acceptance value of the browser test comes from the task: in a dive, a pan and a dive out of the 400-card map, each followed by a stop of 700 ms, no alpha of a layer changes by more than 0.25 between two frames. It is acceptance 13 of `tests/test_canvas_browser.py`.

Other agents operated Chromium on the host during all runs. `run_ab.py` recorded 1 to 16 Chromium processes and a load average of 0.9 to 3.2. Thus only the A/B difference in the same session has a meaning, and in the last runs A also failed the limit of one tick.

### S1: the alpha of each layer in each frame

The page records each frame that the screen shows (`systemapCanvas.record`). The layers are HIDE, the image layer of each map, and the part of each image in the result. In the final code, the largest change between two frames is 0.2 in each of the three moves, at 1x. The image layer is at 1 in 59 frames of the dive in, 111 frames of the pan and 43 frames of the dive out. It is between 0 and 1 in 19 frames of each move. After each stop, 9 or 10 frames fade, and the last frame has the full resolution, the full text and no image. The test passes. The renderer of A gives no record. In its code, each of the four changes is a step of 1 in one frame.

### S2: the pixels of a stop (information)

`pixels.js`: the 400-card map at the part 0.2 of the dive, a pan of 90 frames, and then 60 animation frames with no camera change. After each frame, the script draws the page canvas and the second canvas, with its opacity, into a canvas of 720 x 450 pixels. The value is the mean of the largest channel difference of each pixel against the frame before (0 to 255), and the part of the pixels with a difference of more than 32. No acceptance value was written before this probe.

| Page | Frames that change | Largest mean difference | Largest part over 32 |
|---|---|---|---|
| A | 1 | 9.67 | 6.15 percent |
| B, final | 9 | 1.73 | 0.21 percent |

`still.js` gives the screenshot 1.2 s after the same pan. The PNG files of A and B are identical.

### S3: the attempts before the final code

Attempt 1. The first version faded the text and the images at full resolution after the stop. It used the earlier `fadeLater`. The run stopped after 4 scenarios of run 1, because the stop was too slow:

| Data | Scenario | p95 A (ms) | p95 B (ms) | Stop max A (ms) | Stop max B (ms) |
|---|---|---|---|---|---|
| 400 cards | dive | 16.8 | 33.3 | | |
| 400 cards | pan-fit | 16.8 | 16.8 | | |
| 400 cards | dive-stop | 16.7 | 16.8 | 50 | 166.6 |
| 400 cards | pan-stop | 33.4 | 33.4 | 49.9 | 166.6 |

A record of each frame gave three causes:
- A fade that started in the frame of a camera change got two draws in each animation frame (`fadeLater`).
- A frame of the fade after a stop drew the full drawing at full resolution and the images over it. At 4x, the interval of such a frame was 80 to 99 ms.
- When an image became complete above the marks range, the fade in drew the usual drawing and the images for 5 or 6 frames. In one record, 5 of these frames had an interval of 25 to 30 ms.

Attempt 2. The fixed `fadeLater`, the weights of the images, the fade in over the marks image, and the fades after a stop at half resolution. The run stopped after run 1. In `pan-stop` of the 400-card map, the largest stop interval of B was 216.6 ms (A 50.1 ms). In `pan-stop` of the 1,500-card map, it was 49.9 ms (A 16.7 ms). A possible cause: the frames under a full image layer did not keep the marks image current, thus the first frame after the stop made it again. The code was changed for this cause, but this cause was not measured alone.

Attempt 3. The quarter step above the highest image step, the marks image kept current, and the fade after a stop with a copy of the last moving frame into a second canvas. Three full runs:

| Data | Scenario | p95 A (ms) | p95 B (ms) | Stop max A (ms) | Stop max B (ms) |
|---|---|---|---|---|---|
| 400 cards | dive | 16.8, 16.8, 16.8 | 33.2, 16.8, 33.2 | | |
| 400 cards | pan-fit | 16.8, 16.7, 16.8 | 16.7, 16.8, 16.8 | | |
| 400 cards | dive-stop | 16.8, 16.8, 16.7 | 33.4, 16.8, 16.8 | 33.3, 66.6, 50.0 | 83.3, 100.1, 100.0 |
| 400 cards | pan-stop | 33.4, 33.4, 33.4 | 33.4, 49.9, 33.4 | 116.7, 50.0, 66.6 | 100.0, 66.7, 66.6 |
| 1,500 cards | pan-fit | 16.8, 16.8, 16.7 | 16.8, 16.7, 16.8 | | |
| 1,500 cards | pan-stop | 33.4, 16.8, 33.3 | 33.3, 33.3, 33.4 | 33.3, 33.3, 33.3 | 66.6, 66.7, 50.0 |
| M11 shape | pan-fit | 16.7, 16.8, 16.7 | 16.8, 16.8, 16.8 | | |
| M11 shape | all-open | 16.8, 16.8, 16.7 | 16.7, 16.8, 16.8 | | |
| M11 shape | dive | 16.8, 16.7, 16.7 | 16.7, 16.8, 16.8 | | |
| M11 shape | dive-stop | 16.8, 16.7, 16.8 | 33.4, 16.8, 16.7 | 33.3, 16.8, 33.3 | 66.7, 50.0, 233.4 |
| M11 shape | pan-stop | 16.8, 16.8, 16.7 | 16.8, 16.8, 16.8 | 33.3, 33.3, 33.4 | 50.0, 66.6, 66.7 |

Result of attempt 3: fail. Acceptance 1 failed in 2 of 3 runs, acceptance 2 failed for the 400-card `pan-stop` (49.9 ms), and acceptance 3 failed in all stop scenarios. In each stop scenario, B had one long frame more than A. A record of the parts of that frame (`times.js`) gave 0.1 to 5.3 ms for the copy of the moving frame and 4.0 to 36.2 ms for the copy of the full drawing. Thus the final code copies no canvas.

An exploration with the moving frames on the second canvas and the page canvas visible under it gave 21 to 30 frames over 20 ms in the 400-card dive (A 4 to 10). With the opacity 0 on the page canvas while the camera moves, it gave 6 to 10 (A 3 to 9). These counts are from single runs of a scratch copy of the driver (`count.js`), not from `run_ab.py`.

Attempt 4. The moving frames on the second canvas, and the opacity 0 on the page canvas while the camera moves. No frame copies a canvas. Three full runs:

| Data | Scenario | p95 A (ms) | p95 B (ms) | Stop max A (ms) | Stop max B (ms) |
|---|---|---|---|---|---|
| 400 cards | dive | 16.8, 16.8, 33.3 | 16.8, 16.8, 16.8 | | |
| 400 cards | pan-fit | 16.8, 16.7, 16.8 | 16.8, 16.8, 16.8 | | |
| 400 cards | dive-stop | 16.8, 16.8, 16.8 | 16.8, 16.8, 16.8 | 66.7, 83.5, 66.8 | 49.9, 50.0, 50.0 |
| 400 cards | pan-stop | 33.3, 33.4, 33.4 | 33.4, 33.4, 33.4 | 50.0, 50.0, 50.0 | 50.1, 66.7, 16.8 |
| 1,500 cards | pan-fit | 16.7, 16.7, 16.7 | 16.7, 16.7, 16.8 | | |
| 1,500 cards | pan-stop | 16.8, 16.8, 16.8 | 33.4, 33.3, 33.4 | 50.1, 33.3, 33.3 | 133.4, 66.6, 33.3 |
| M11 shape | pan-fit | 16.8, 16.8, 16.8 | 16.7, 16.8, 16.8 | | |
| M11 shape | all-open | 16.8, 16.8, 16.7 | 16.8, 16.7, 16.8 | | |
| M11 shape | dive | 16.7, 16.8, 16.7 | 16.8, 16.8, 16.7 | | |
| M11 shape | dive-stop | 16.7, 16.8, 16.7 | 16.8, 33.3, 16.8 | 83.2, 116.7, 16.8 | 33.4, 16.7, 16.8 |
| M11 shape | pan-stop | 16.7, 16.8, 16.8 | 16.8, 16.8, 16.8 | 16.8, 100.0, 16.8 | 16.8, 16.8, 16.8 |

C3 of the M11 shape at 1x: A 69, 90, 72 ms; B 92, 96, 82 ms.

Result of attempt 4: acceptance 1 and 2 pass. Acceptance 3 fails for the stops of the two grid maps. In these stops, A also has an interval of more than 35 ms in 7 of 9 runs. `run_ab.py` gave no failure of acceptance 4, but the written value fails for one scenario: in the moving part of `pan-stop` of the 1,500-card map, the median p95 is 33.4 ms for B and 16.8 ms for A. The difference is 16.6 ms, one tick. The script compared floating point numbers, and 16.8 + 16.6 is a little more than 33.4. A record of each frame of that pan showed the images in a fade over the marks image, while the page made the images in slices. The map was in the last quarter step before the end of the marks. Thus the final code fades the images in over the marks only while the zoom goes in.

### S4: the final code

The final code is attempt 4 with one more change: the images fade in over the marks image only while the zoom goes in. Attempt 5 is three full runs of `run_ab.py` on this code:

| Data | Scenario | p95 A (ms) | p95 B (ms) | Stop max A (ms) | Stop max B (ms) |
|---|---|---|---|---|---|
| 400 cards | dive | 33.3, 33.2, 33.3 | 33.2, 16.8, 33.3 | | |
| 400 cards | pan-fit | 16.7, 16.8, 16.8 | 16.8, 16.8, 16.8 | | |
| 400 cards | dive-stop | 16.7, 16.8, 16.8 | 33.3, 16.8, 16.7 | 66.7, 83.3, 49.9 | 50.0, 50.0, 50.0 |
| 400 cards | pan-stop | 33.4, 33.4, 33.4 | 33.3, 33.4, 49.9 | 50.1, 83.3, 49.9 | 50.1, 33.3, 16.7 |
| 1,500 cards | pan-fit | 16.8, 16.7, 16.8 | 16.8, 16.7, 16.8 | | |
| 1,500 cards | pan-stop | 33.3, 33.3, 16.8 | 16.8, 33.3, 33.3 | 33.4, 16.7, 33.3 | 16.7, 16.8, 16.8 |
| M11 shape | pan-fit | 16.7, 16.8, 16.8 | 16.7, 16.8, 16.8 | | |
| M11 shape | all-open | 16.8, 16.8, 16.8 | 16.8, 16.8, 16.7 | | |
| M11 shape | dive | 16.8, 16.8, 16.8 | 16.8, 16.7, 16.7 | | |
| M11 shape | dive-stop | 16.8, 16.8, 16.8 | 16.8, 16.7, 16.7 | 33.3, 33.3, 33.3 | 16.8, 16.8, 16.8 |
| M11 shape | pan-stop | 33.3, 16.7, 16.8 | 16.7, 16.7, 16.8 | 16.8, 33.3, 16.8 | 16.8, 16.8, 16.8 |

C3 of the M11 shape at 1x: A 105, 76, 79 ms; B 74, 73, 78 ms. `run_ab.py` recorded 1 to 15 Chromium processes and a load average of 2.1 to 3.2.

Then `run_dive.py` (its docstring has its acceptance value, written before its first run) gave 5 interleaved runs of the 400-card dive at 4x only. The acceptance value is a p95 of B of at most 16.8 ms in each run:

| Run | Chromium processes | Load average | p95 A (ms) | p95 B (ms) |
|---|---|---|---|---|
| 1 | 1 | 2.72 | 16.8 | 33.3 |
| 2 | 3 | 2.58 | 16.8 | 33.3 |
| 3 | 9 | 2.34 | 33.3 | 33.3 |
| 4 | 3 | 2.28 | 16.8 | 16.8 |
| 5 | 7 | 2.31 | 16.8 | 16.8 |

Results of the final code:
- Acceptance 1 fails. The dive of the 400-card map at 4x has a p95 of two ticks in 2 of 3 runs of attempt 5 and in 3 of 5 runs of `run_dive.py`. A has two ticks in 3 of 3 and in 1 of 5 of the same runs. In attempt 4, before the last change, B had one tick in 3 of 3 runs and A two ticks in 1 of 3. The last change changes the end of the dive out: in the marks, the images now fade out over the marks image. The cause of the difference between attempts 4 and 5 (the last change or the load of the host) was not measured. With the host of these runs, the requirement of one tick is not shown. A measurement on a quiet host is necessary.
- Acceptance 2 fails one time: the moving part of the 400-card `pan-stop` has a p95 of 49.9 ms in run 3 (A 33.4 ms). In attempt 4 the same part had 33.4 ms in 3 of 3 runs. The C2 scenarios of `canvas_frames.py` stay in the limit of 35 ms in all runs.
- Acceptance 3 fails for the stops of the 400-card map: the largest interval after the stop is 50 ms in 4 of 6 runs. The first frame of the stop draws the full drawing at full resolution, as A does. A has 49.9 to 83.3 ms in 6 of 6 of these runs. In each stop of attempt 5, the largest interval of B is in the same tick as that of A in the same run, or in a lower tick. Thus the fade after the stop adds no long frame. The full drawing at full resolution takes more than two ticks also without the fade.
- Acceptance 4 passes. In each scenario, the median of B is not more than the median of A.

Not measured: a device with a GPU, a device pixel ratio of 2, the M11 tree (only the M11 shape), and the dive on a quiet host.

## F4: the boundary flows under the cards (2026-11-06)

Scope: the boundary flows of the canvas page (`page_canvas_fade.py`, `page_canvas_draw.py`, `page_canvas_image.py`, `page_canvas.py`). The maintainer decided on 2026-11-06: "Draw boundary lines under the cards. A card that moves onto a line covers it while the line fades. A line is never drawn over a card." Before this change, a line was hidden when a box was in its path. Thus its alpha changed by up to 0.78 (1440 x 900) and 1.0 (390 x 844) in one frame in moves that zoom out (F1 to F3 above).

The change:
- The frame draws the boundary flows into a layer canvas. Then it removes the part of the layer under each box of the obstacle list (cards, texts, flow label plates, portals, the path and the help line), with the opacity of the box. Then it puts the layer on the screen before the portals. Thus a line is under the cards, their texts and the portals, as the routes of a map are.
- A line uses a clear path when one is possible, as before. A path that a box blocks is not hidden at one time. The line changes to a different clear path, or to no path, and the earlier path fades out by time, by 0.2 or less in each frame.
- These parts are removed: the caps of a value from the speed of the boxes (`boxCap`, `pathCap`, `limitsOf`, `nearCap`), the places of the portals in the frame before, and the cases that hid a line at one time (a blocked path, a change of the weight of a portal, a change of the count of points).
- A line whose portal goes because the chain changed fades out from the place of that portal in the last frame (`fadeLeft`). Before, it went at one time with its portal.
- A frame with no portal and no line value does not use the layer.

The scripts are in the scratchpad of the agent and are not in the repository: `fade_check.py`, `run_ab.py`, `ab_table.py` and `load_ab.py`. Each docstring has the acceptance values, which were written before the first run of that script. Other agents used Chromium on the host at the same time.

### F4: the alpha of the lines and the pixels over the cards

The browser test (`tests/canvas_driver.js --fade`, acceptance 11 of `tests/test_canvas_browser.py`) now has more moves. On a screen of 1440 x 900, it has the four moves of F1. On a screen of 1440 x 900 and on a screen of 390 x 844, it has five moves that zoom out: from the fit of P0, P0/A0 and P0/A0/B0 to the fit of the map above, and from 3 to 0.5 times the fit of P0 and of P0/A0. Each move has 200 frames, on the M11 shape tree, without reduced motion.

Acceptance values of `fade_check.py`:
- In each move, the alpha of each drawn path changes by 0.25 or less between two frames. A path that is not drawn has the alpha 0.
- In each frame, no pixel of the layer of the lines has an alpha more than 0 in a card that is not open, 2 pixels or more in from the edge of its box. The page puts the layer on the screen with no other change. Thus such a pixel is a line pixel over a card.
- The moves on each screen draw boundary flows in 30 frames or more.

Each cell gives the largest change of an alpha, the count of frames with a line pixel over a card, the count of drawn paths, and the count of drawn paths that go into a card that is not open (the card covers them).

| Screen | Move | Run 1 | Run 2 | Run 3 |
|---|---|---|---|---|
| 1440 x 900 | top to P0/A0, zoom 1 to 1 | 0.084 / 0 / 6 / 0 | 0.086 / 0 / 6 / 0 | 0.103 / 0 / 8 / 1 |
| 1440 x 900 | P0/A0 to top, zoom 1 to 1 | 0.089 / 0 / 13 / 8 | 0.088 / 0 / 13 / 8 | 0.086 / 0 / 13 / 8 |
| 1440 x 900 | P0 to P0/A0, zoom 1 to 1 | 0.090 / 0 / 57 / 2 | 0.109 / 0 / 57 / 2 | 0.093 / 0 / 57 / 2 |
| 1440 x 900 | P0/A0 to P0/A0, zoom 0.5 to 3 | 0.086 / 0 / 71 / 11 | 0.091 / 0 / 71 / 11 | 0.087 / 0 / 70 / 11 |
| 1440 x 900 | P0 to top, zoom 1 to 1 | 0.092 / 0 / 44 / 18 | 0.104 / 0 / 43 / 17 | 0.098 / 0 / 43 / 17 |
| 1440 x 900 | P0/A0 to P0, zoom 1 to 1 | 0.093 / 0 / 59 / 13 | 0.104 / 0 / 60 / 14 | 0.092 / 0 / 60 / 14 |
| 1440 x 900 | P0/A0/B0 to P0/A0, zoom 1 to 1 | 0.237 / 0 / 60 / 9 | 0.238 / 0 / 61 / 9 | 0.239 / 0 / 60 / 9 |
| 1440 x 900 | P0 to P0, zoom 3 to 0.5 | 0.085 / 0 / 71 / 22 | 0.105 / 0 / 71 / 22 | 0.085 / 0 / 71 / 22 |
| 1440 x 900 | P0/A0 to P0/A0, zoom 3 to 0.5 | 0.085 / 0 / 54 / 11 | 0.099 / 0 / 55 / 12 | 0.094 / 0 / 54 / 11 |
| 390 x 844 | P0 to top, zoom 1 to 1 | 0.091 / 0 / 23 / 8 | 0.087 / 0 / 23 / 8 | 0.104 / 0 / 23 / 8 |
| 390 x 844 | P0/A0 to P0, zoom 1 to 1 | 0.084 / 0 / 16 / 0 | 0.089 / 0 / 16 / 0 | 0.085 / 0 / 16 / 0 |
| 390 x 844 | P0/A0/B0 to P0/A0, zoom 1 to 1 | 0.085 / 0 / 28 / 8 | 0.092 / 0 / 28 / 8 | 0.092 / 0 / 29 / 9 |
| 390 x 844 | P0 to P0, zoom 3 to 0.5 | 0.086 / 0 / 107 / 0 | 0.091 / 0 / 107 / 0 | 0.094 / 0 / 107 / 0 |
| 390 x 844 | P0/A0 to P0/A0, zoom 3 to 0.5 | 0.092 / 0 / 69 / 6 | 0.100 / 0 / 69 / 6 | 0.108 / 0 / 69 / 6 |

The three acceptance values pass in the three runs. The moves draw 435 to 437 paths at 1440 x 900, and 243 to 244 paths at 390 x 844.

The largest change, 0.237 to 0.239, is in the move from P0/A0/B0 to P0/A0 at 1440 x 900. The actor card of the line goes off the screen, thus the line fades out by 0.2 in a frame. At the same time, the neighbour B1 comes onto the screen, and its portal fades with the camera. The alpha of a line is the product of these two values. Thus the margin to 0.25 is small. A change of the fade time or of the portal fade can make this move fail.

During the work, one error was found with this check: the layer kept the opacity of the last line when it removed the boxes. Then the boxes removed only a part of the line, and 10 to 14 frames of two moves had a line pixel over a card. The check above is after the fix.

### C2 and C3: A/B

A is commit 4905fcf. B is the change above, before the last item of the list (the layer is not used in a frame with no portal). The order was A1, B1, A2, B2, A3, B3 in one session, and each copy operated its own `bench/jev/canvas_frames.py` without changes. Before each run, the script waited up to 120 s for 20 s with no Chromium process. Before runs A1 to A3 and B1 and B2, it found 20 s with no Chromium process. Before B3, it did not find 20 s in 120 s, but no Chromium process was there at the start. Each run took 90 s. The load average (1 minute) was 0.5 to 2.0 during the runs.

Acceptance values of `run_ab.py`:
- B: each scenario passes its limit of `canvas_frames.py` in each of the 3 runs.
- B against A: for each scenario, the median of the 3 p95 values of B is not more than the median of A plus one tick (16.6 ms or more counts as one tick).
- The dive of the 400-card map at 4x has p95 at most 16.8 ms in each run of B.

For C3, the value is the load time. For a scenario, the value is the p95 frame interval in ms.

| Data | Scenario | CPU | A: runs 1, 2, 3 | B: runs 1, 2, 3 | Median B minus median A | Result of B |
|---|---|---|---|---|---|---|
| M11 tree | C3 load | 4x | 244, 238, 259 ms | 281, 277, 272 ms | +33 ms | information |
| M11 shape | C3 load | 4x | 272, 269, 229 ms | 324, 314, 289 ms | +45 ms | information |
| M11 tree | pan-fit | 4x | 16.8, 16.8, 16.7 | 16.8, 16.8, 16.8 | 0 | pass |
| M11 tree | all-open | 4x | 16.7, 16.8, 16.8 | 16.8, 16.8, 16.8 | 0 | pass |
| M11 tree | dive | 4x | 16.8, 16.8, 16.7 | 16.8, 16.8, 16.8 | 0 | pass |
| 400 cards | pan-fit | 4x | 16.8, 16.7, 16.7 | 16.8, 16.8, 16.8 | +0.1 | pass |
| 400 cards | dive | 4x | 16.8, 33.3, 16.7 | 16.8, 16.8, 16.8 | 0 | pass |
| 1,500 cards | pan-fit | 4x | 16.7, 16.8, 16.8 | 16.8, 16.8, 16.7 | 0 | pass |
| M11 shape | pan-fit | 4x | 16.8, 16.8, 16.8 | 16.8, 16.8, 16.8 | 0 | pass |
| M11 shape | all-open | 4x | 16.7, 16.8, 16.7 | 16.8, 16.7, 16.8 | +0.1 | pass |
| M11 shape | dive | 4x | 16.8, 16.8, 16.7 | 16.8, 16.8, 16.7 | 0 | pass |
| M11 tree | C3 load | 1x | 73, 78, 68 ms | 72, 80, 73 ms | 0 ms | pass |
| M11 shape | C3 load | 1x | 90, 72, 78 ms | 75, 76, 89 ms | -2 ms | pass |
| M11 tree | pan-fit | 1x | 16.7, 16.8, 16.7 | 16.7, 16.8, 16.8 | +0.1 | pass |
| M11 tree | all-open | 1x | 16.7, 16.8, 16.8 | 16.7, 16.7, 16.8 | -0.1 | pass |
| M11 tree | dive | 1x | 16.8, 16.8, 16.7 | 16.8, 16.7, 16.8 | 0 | pass |
| 400 cards | pan-fit | 1x | 16.7, 16.7, 16.7 | 16.7, 16.8, 16.8 | +0.1 | pass |
| 400 cards | dive | 1x | 16.8, 16.8, 16.7 | 16.7, 16.7, 16.7 | -0.1 | pass |
| 1,500 cards | pan-fit | 1x | 16.7, 16.7, 16.8 | 16.8, 16.7, 16.8 | +0.1 | pass |
| M11 shape | pan-fit | 1x | 16.7, 16.8, 16.7 | 16.8, 16.8, 16.8 | +0.1 | pass |
| M11 shape | all-open | 1x | 16.7, 16.8, 16.7 | 16.7, 16.8, 16.7 | 0 | pass |
| M11 shape | dive | 1x | 16.8, 16.7, 16.8 | 16.7, 16.7, 16.7 | -0.1 | pass |

The three acceptance values pass. All p95 values of B are one tick. The dive of the 400-card map at 4x has p95 16.8 ms in each run of B. In run A2, it had 33.3 ms.

C3 at 4x was more in B than in A in each of the 3 runs (information only). The script `load_ab.py` then measured C3 of the M11 shape page in 5 more runs in the order A, B, B2. B2 is the final change, with the layer not used in a frame with no portal. Its acceptance value, written before its first run: C3 of B2 at 1x is at most 1,500 ms in each run. It passes.

| Copy | C3 at 4x: runs 1 to 5 (ms) | Median | C3 at 1x: runs 1 to 5 (ms) | Median |
|---|---|---|---|---|
| A | 586, 246, 307, 233, 254 | 254 | 81, 84, 73, 66, 77 | 77 |
| B | 289, 264, 275, 265, 284 | 275 | 73, 69, 74, 81, 76 | 74 |
| B2 | 306, 244, 297, 262, 278 | 278 | 73, 74, 67, 74, 68 | 73 |

At 4x, the median of B and B2 is 21 to 24 ms more than A. The values of each copy overlap, thus the cause is not known. The first frame of the page has no portal, and B2 does not use the layer in that frame. A measurement with a CPU profile is necessary to find the cause. At 1x there is no difference.

One more run of `canvas_frames.py` with B2, information only: each scenario passed its limit, and each p95 was 16.7 or 16.8 ms. The dive of the 400-card map at 4x had p95 16.8 ms. C3 was 259 ms (M11 tree) and 261 ms (M11 shape) at 4x, and 65 ms and 77 ms at 1x.

## F5: the fade of the portals (2026-11-06)

Scope: the portals of the canvas page (`page_canvas_fade.py`, `page_canvas_draw.py`, `page_canvas.py`). Before this change, a portal appeared and went at one time when the chain changed. In the frame where it appeared, it showed at full opacity, also over a card. The maintainer decided on 2026-11-06 to keep the speed changes and to add fades, so that nothing appears at one time.

The change:
- The `show` of each portal changes by 1 in 400 ms or more (`PORTAL_MS`). The time between two frames counts as 17 ms or less (`PORTAL_DT`), thus the `show` changes by 0.0425 or less in one frame. When the frames come more slowly, the fade takes more time. A new portal starts at 0. The portal is drawn only with this `show`.
- A portal that the chain removes stays at its side or in its row, with no boundary flow, and fades out.
- Each portal has a `room` from 0 to 1 that changes at the same rate. Two portals on an edge keep the smaller `room` of the two as the part of their gap (`kept`). Before, the part was `smoothstep(0, 0.3, show)`.
- A portal can push each portal after it on its edge, not only the next one. A portal moves by the largest of these pushes, not by their sum. Before, a portal with a small `show` between two portals let them come together, and when it went, they jumped apart.
- The line code did not change. The boundary flows use the `show` of a portal as before, for the alpha of a line and for the weight of the portal box. This `show` is now the faded value. F1 (acceptance 11) still passes.
- The measurements below are of this change on commit 4905fcf, before it was joined with the change of F4 (the lines under the cards). After the join, `boxCap` is not there, and the browser tests of the two changes (acceptance 11 and 14) pass together.

The scripts are in the scratchpad of the agent and are not in the repository: `run_portals.py` (F5) and `run_frames.py` (F6), with `build.py`, `trace.js` and `shots.js`. The browser test is acceptance 14 of `tests/test_canvas_browser.py` (`tests/canvas_driver.js --portals`). A is commit 4905fcf with one change for the measurement only: `hits()` also gives the map and the `show` of each portal. B is the change. The data is the M11 shape tree. The viewport is 1440 x 900 and 390 x 844, without reduced motion, with one animation frame for each camera step. Other agents used Chromium on the host at the same time. The order of A and B changed in each run.

Acceptance values, in the docstring of `run_portals.py` before the recorded runs:
- F5: during a slow dive into P0/A0 and a slow zoom out from it (300 frames each), no portal alpha changes by more than 0.25 between two frames, and the middle of no portal moves by more than 16 px between two frames. A portal that is not drawn has the alpha 0. Pass or fail for B, for each run, move and screen.
- F6: with 4 times CPU throttling, the p95 frame interval of the M11 shape scenarios is at most 35.0 ms, and the p95 of the 400 cards dive is at most 16.8 ms (one tick). Pass or fail for B.

Revision 1 of the F5 acceptance used the moves of acceptance 11 (from fit to fit, 200 frames). In these moves, the middle of the screen goes across sibling cards, and the chain changed 12 to 14 times in one move. A portal follows its card along the screen edge, and the cards moved more than 16 px in one frame. In the first run of revision 1, A moved a portal by 56.6 px in one frame (alpha change 1). Thus revision 1 did not test a smooth camera. Revision 2 keeps the middle of the screen on the middle of the fit of P0/A0, and the scale moves in log space and slowly at the two ends. The chain changes 2 times in each move. Revision 2 was written before the runs below.

F5, the last version of B (largest change of a portal alpha between two frames, and largest move of a portal middle between two frames in px):

| Run | Screen | Move | A alpha | A move | B alpha | B move | B result |
|---|---|---|---|---|---|---|---|
| 1 | 1440 x 900 | dive | 1.000 | 22.1 | 0.043 | 9.6 | pass |
| 1 | 1440 x 900 | zoom out | 1.000 | 22.1 | 0.043 | 9.6 | pass |
| 1 | 390 x 844 | dive | 1.000 | 20.9 | 0.043 | 11.0 | pass |
| 1 | 390 x 844 | zoom out | 1.000 | 20.9 | 0.042 | 11.0 | pass |
| 2 | 1440 x 900 | dive | 1.000 | 22.1 | 0.043 | 9.6 | pass |
| 2 | 1440 x 900 | zoom out | 1.000 | 22.1 | 0.043 | 9.6 | pass |
| 2 | 390 x 844 | dive | 1.000 | 20.9 | 0.042 | 11.0 | pass |
| 2 | 390 x 844 | zoom out | 1.000 | 20.9 | 0.043 | 11.0 | pass |
| 3 | 1440 x 900 | dive | 1.000 | 22.1 | 0.043 | 9.6 | pass |
| 3 | 1440 x 900 | zoom out | 1.000 | 22.1 | 0.043 | 9.6 | pass |
| 3 | 390 x 844 | dive | 1.000 | 20.9 | 0.042 | 11.0 | pass |
| 3 | 390 x 844 | zoom out | 1.000 | 20.9 | 0.043 | 10.9 | pass |

Three earlier A/B runs of B without `PORTAL_DT` also passed in each move: B alpha 0.043 to 0.056, B move 9.6 to 12.2 px. A gave the same values as above.

A fails the alpha value in each move: a portal goes from 0 to 1 in one frame when the chain changes. In A, the move of 20.9 to 22.1 px occurs when a new portal pushes a different portal by a full gap in one frame.

Steps that failed before the last version of B (revision 2 moves, one run each, not recorded as a result). In each of them, a portal got the pushes of all portals before it, one after the other:
- A fade of `show` in 200 ms, and a `kept` equal to the smaller `show`: a portal moved by 23.1 px in one frame (390 x 844). A portal that fades in between two portals must move by a gap of up to 156 px in a short time.
- A fade in 400 ms, and the same `kept`: the moves passed (12.5 px or less). But then two portals with a constant `show` of less than 1 cover a part of each other while the camera does not move. At the fit of P0/A0 on 390 x 844, the portal A1 has a `show` of 0.77.
- A fade in 400 ms, and a `kept` that is full at a `show` of 0.5: 22.8 px.
- `room` in place of `show` for `kept`: 22.4 px.

One failure of the last version but one: acceptance 14 failed one time on 390 x 844 in a run of all the canvas tests, while other agents used Chromium on the host. The same test passed when it ran alone. The value was not recorded. When frames come more slowly, a time-based fade changes more in each frame, and the pushes are larger. The correction is `PORTAL_DT`: a frame counts as 17 ms or less for the portal fade.

F6, the last version of B (p95 frame interval in ms, 4 times throttling):

| Scenario | Run 1 A | Run 1 B | Run 2 A | Run 2 B | Run 3 A | Run 3 B | B result |
|---|---|---|---|---|---|---|---|
| M11 shape pan-fit | 16.7 | 16.7 | 16.7 | 16.8 | 16.7 | 16.7 | pass |
| M11 shape all-open | 16.8 | 16.8 | 16.7 | 16.8 | 16.8 | 16.8 | pass |
| M11 shape dive | 16.8 | 16.8 | 16.7 | 16.8 | 16.8 | 16.7 | pass |
| 400 cards dive | 16.8 | 16.8 | 16.8 | 16.8 | 16.8 | 16.8 | pass |

The median is 16.7 ms in each row. The fade adds no measurable frame time. Three earlier A/B runs of B without `PORTAL_DT` gave p95 values from 16.7 to 16.8 ms for A and B in each row.

A screenshot check (`shots.js`, 390 x 844, the dive near the first chain change, one camera step for each screenshot): in A, the portal P7 has the alpha 1.00 in the first step where it is drawn. In B, with the last version, it has 0.01, 0.05, 0.06, 0.11 and 0.12 in the first five steps. While a portal fades, the page can draw more frames between two steps.

## C2 and C3 of commit 0b547b7: runs on a quiet host (2026-11-06)

Scope: commit 0b547b7. This commit joins the still fade (S1 to S4), the lines under the cards (F4), the portal fade (F5) and the phone fit. Its commit message says that the limit of one tick for the 400-card dive at 4x is not shown on a busy host, and that a measurement on a quiet host is necessary. These runs are that measurement. The source did not change. Each run operated `uv run python bench/jev/canvas_frames.py` of the commit without changes. There is no A/B in these runs.

The scripts are in the scratchpad of the agent and are not in the repository: `run2.py` (runs 1 and 2) and `more.py` (runs 3 to 7). The acceptance values were in the docstring of `run2.py` before the first run:
- Each scenario passes its limit of `canvas_frames.py` in each run.
- The dive of the 400-card map at 4x has a p95 of at most 16.8 ms (one tick) in each run.
- No p95 is one tick (16.6 ms) or more above the latest runs above (the A/B after the phone fit, and the C2 and C3 A/B of F4). All p95 values of B in those runs are 16.7 or 16.8 ms. Thus a p95 of 33.2 ms or more fails.

Before each run, a polling loop with `ps` waited until no Chromium, node or pytest process of a different agent had operated for 30 s. During each run, a sampler recorded the processes each 2 s. It kept the processes of the run apart from the processes of other agents. The first start of `run2.py` found a process at each poll and made no run: the loop examined the full command line, and a shell of the host has the word "node" in its command line. The loop now examines the name of the program (`ps` comm).

The polling loop did not stop other agents. They started Chromium during runs 1, 2, 3, 5 and 6. Thus `more.py` added a rule, written before its first run: a run is on a quiet host only when no sample during the run shows a Chromium, node or pytest process of a different agent (a zombie process does not count). It made runs until it had 2 such runs. Runs 4 and 7 are on a quiet host.

| Run | Start | Samples with a process of a different agent | Load average (1 minute) |
|---|---|---|---|
| 1 | 11:41:52 | 29 of 43 (a browser script of a different agent) | 0.26 to 2.37 |
| 2 | 11:44:20 | 22 of 44 (the same script) | 0.74 to 1.37 |
| 3 | 11:47:25 | 35 of 45 (the same script) | 0.42 to 2.35 |
| 4 | 12:03:16 | 0 of 44 | 0.16 to 1.49 |
| 5 | 12:05:15 | 3 of 45 (two probe scripts, from 12:05:19 to 12:05:39) | 0.64 to 1.33 |
| 6 | 12:07:15 | 8 of 45 (a probe script, from 12:08:04 to 12:08:18) | 0.53 to 1.34 |
| 7 | 12:09:41 | 0 of 44 | 0.49 to 1.24 |

For C3, the value is the load time. For a scenario, the value is the p95 frame interval in ms. Runs 4 and 7 are on a quiet host. The result is for all 7 runs.

| Data | Scenario | CPU | Runs 1 to 3 and 5, 6 | Run 4 (quiet) | Run 7 (quiet) | Result |
|---|---|---|---|---|---|---|
| M11 tree | C3 load | 4x | 261, 268, 290, 302, 306 ms | 228 ms | 288 ms | information |
| M11 shape | C3 load | 4x | 298, 267, 236, 277, 364 ms | 236 ms | 268 ms | information |
| M11 tree | pan-fit | 4x | 16.8, 16.7, 16.7, 16.8, 16.8 | 16.8 | 16.7 | pass |
| M11 tree | all-open | 4x | 16.8, 16.8, 16.7, 16.8, 33.2 | 16.8 | 16.8 | pass, two ticks in run 6 |
| M11 tree | dive | 4x | 16.8, 16.8, 16.8, 16.8, 33.3 | 16.7 | 33.3 | pass, two ticks in runs 6 and 7 |
| 400 cards | pan-fit | 4x | 16.8, 16.8, 16.8, 16.7, 16.8 | 16.8 | 16.7 | pass |
| 400 cards | dive | 4x | 33.3, 16.8, 16.8, 33.4, 33.3 | 33.3 | 33.2 | pass, two ticks in runs 1 and 4 to 7 |
| 1,500 cards | pan-fit | 4x | 16.8, 16.7, 16.8, 16.8, 16.8 | 16.8 | 16.8 | pass |
| M11 shape | pan-fit | 4x | 16.8, 16.8, 16.7, 16.7, 16.8 | 16.7 | 16.8 | pass |
| M11 shape | all-open | 4x | 16.7, 16.8, 16.8, 16.8, 16.8 | 16.8 | 16.8 | pass |
| M11 shape | dive | 4x | 16.8, 16.8, 16.8, 16.8, 16.8 | 16.8 | 16.8 | pass |
| M11 tree | C3 load | 1x | 82, 68, 73, 67, 104 ms | 69 ms | 70 ms | pass |
| M11 shape | C3 load | 1x | 79, 79, 95, 74, 109 ms | 82 ms | 81 ms | pass |
| M11 tree | pan-fit | 1x | 16.8, 16.8, 16.8, 16.7, 16.8 | 16.7 | 16.8 | pass |
| M11 tree | all-open | 1x | 16.8, 16.8, 16.7, 16.8, 16.7 | 16.7 | 16.7 | pass |
| M11 tree | dive | 1x | 16.7, 16.8, 16.7, 16.8, 16.7 | 16.8 | 16.8 | pass |
| 400 cards | pan-fit | 1x | 16.7, 16.7, 16.8, 16.8, 16.7 | 16.8 | 16.8 | pass |
| 400 cards | dive | 1x | 16.8, 16.7, 16.8, 16.7, 16.7 | 16.8 | 16.8 | pass |
| 1,500 cards | pan-fit | 1x | 16.7, 16.7, 16.8, 16.7, 16.8 | 16.8 | 16.8 | pass |
| M11 shape | pan-fit | 1x | 16.8, 16.8, 16.8, 16.7, 16.7 | 16.8 | 16.8 | pass |
| M11 shape | all-open | 1x | 16.7, 16.8, 16.8, 16.7, 16.8 | 16.7 | 16.7 | pass |
| M11 shape | dive | 1x | 16.7, 16.7, 16.8, 16.7, 16.7 | 16.8 | 16.7 | pass |

Results:
- Acceptance value 1 passes. Each scenario passes its limit of `canvas_frames.py` in each of the 7 runs. The largest p95 at 4x is 33.4 ms (limit 35.0 ms), and the largest C3 at 1x is 109 ms (limit 1,500 ms).
- Acceptance value 2 fails. The dive of the 400-card map at 4x has a p95 of two ticks (33.2 to 33.4 ms) in 5 of 7 runs, and in each of the 2 runs on a quiet host. Thus the quiet host does not give one tick for this commit, and the two ticks are not only an effect of a busy host.
- Acceptance value 3 fails. Against the latest runs, the p95 of three scenarios at 4x rose by one tick: the 400-card dive (runs 1 and 4 to 7), the M11 tree dive (runs 6 and 7), and the M11 tree all-open (run 6). In the C2 and C3 A/B of F4, B had 16.8 ms in 3 of 3 runs for each of these scenarios. Those runs were of F4 alone, not of the joined commit.
- The p95 values at 1x are all one tick.

Not measured: which of the four joined changes makes the 400-card dive at 4x two ticks. An A/B on a quiet host of commit 0b547b7 against commits with one change removed is necessary. S4 (attempt 4 against attempt 5) gives a possible cause: the fade of the images over the marks image at the end of the dive out. That cause is not measured.

## R1 to R3: the fixes after the third review of commit 0b547b7 (2026-11-06)

Scope: the canvas page (`page_canvas*.py`), after the review of commit 0b547b7. The changes:
- The layer of the boundary flows has the size of the canvas of the frame. Before, it had the size of the page canvas also while the camera moved. The page then put it at 2 times its screen position on the second canvas, which has half the resolution. Thus a line could go over a card while the camera moved. Each canvas now has its own layer. `tests/canvas_driver.js --fade` now finds a layer that does not have the size of the canvas of the frame. On the page of commit 0b547b7, it found 392 such frames in the 9 moves at 1440 x 900.
- A line that fades out after a change of the chain keeps its end on the portal of the same neighbour in the frame.
- The image layer of a large map fades by 1 in 80 ms or more (before: 160 ms). Above the highest image step, the image stays for an eighth of a step of zoom (before: a quarter of a step).
- The text of a card fades with the zoom (`page_canvas_text.py`). This includes the names at 7 px, the flow labels at 8 px, the names of the boxes, each new line or row, the fact row, the lists, and a change of the count of columns. The description has 4 lines or less.

### R1: where the 400-card dive at 4x got two ticks

`dive.js` records each frame of the dive of `canvas_frames.js` (the same camera path, 180 frames, 4x). No acceptance value was written before these probes. They are information only. On commit 0b547b7, the frames with an interval of more than 20 ms were in four parts of the dive:
- The first 20 frames, where the page makes the images. One slice of an image took up to 19 ms. The first slice of an image fills its canvas, and it took 5.6, 9.5 and 14.4 ms for the three images.
- The fade above the highest image step: 7 frames in each direction, with the usual drawing and the image. A frame with the two drawings took 17.6 ms (median) with the raster forced (`cost.js`), against 12.0 ms without the image.
- Frames of the usual drawing at a scale of 1.5 to 2.0.
- In 6 runs of 0b547b7, 8 to 13 frames had more than 20 ms. In 6 runs of commit 4905fcf, 2 to 8 frames had more than 20 ms, and none of them were in the fade above the highest image step.

With the change, the fade above the highest image step has 4 or 5 frames in each direction. In 5 runs of a first version of the change (a copy of the page with the two values changed), the p95 was 16.8 ms in 4 runs. In 5 runs of 0b547b7 in the same session, it was 33.3 or 33.4 ms in each run. Later runs of the same probes on the same host gave 33 ms for both pages in most runs, with no Chromium process of a different agent. Thus the probes show where the cost is, but they do not show the result. R2 is the measurement.

### R2: C2 and C3, A/B

A is commit 0b547b7. B is the change above. The order was A1, B1, A2, B2, A3, B3, A4, B4 in one session. Each copy operated its own `bench/jev/canvas_frames.py` without changes. The script `run_ab.py` is in the scratchpad of the agent and is not in the repository. Before each run, it waited until no Chromium, node or pytest process (by the name of the program) had operated for 30 s. It found that before each run. During each run, it recorded these processes each 2 s. No sample of the 8 runs showed a process of a different agent. The load average (1 minute) was 0.47 to 1.66.

The acceptance values were in the docstring of `run_ab.py` before the first run:
1. Each scenario of B passes its limit of `canvas_frames.py` in each run.
2. The dive of the 400-card map at 4x: the p95 of B is at most 16.8 ms in each run.
3. B against A: for each scenario, the median of the p95 values of B is less than the median of A plus one tick (16.6 ms). The script compares with a margin of 0.5 ms for the float values: a difference of 16.1 ms or more fails.
4. Information only: C3 at 4x.

For C3, the value is the load time. For a scenario, the value is the p95 frame interval in ms.

| Data | Scenario | CPU | A: runs 1 to 4 | B: runs 1 to 4 | Median B minus median A | Result of B |
|---|---|---|---|---|---|---|
| M11 tree | C3 load | 4x | 239, 288, 332, 348 ms | 259, 287, 234, 394 ms | -37 ms | information |
| M11 shape | C3 load | 4x | 225, 311, 278, 275 ms | 257, 252, 238, 248 ms | -26.5 ms | information |
| M11 tree | pan-fit | 4x | 16.8, 16.8, 16.8, 16.8 | 16.8, 16.8, 16.8, 16.8 | 0 | pass |
| M11 tree | all-open | 4x | 16.8, 16.8, 16.8, 16.8 | 16.8, 16.8, 16.7, 16.8 | 0 | pass |
| M11 tree | dive | 4x | 16.8, 16.8, 16.8, 16.8 | 16.8, 16.8, 16.8, 16.8 | 0 | pass |
| 400 cards | pan-fit | 4x | 16.7, 16.7, 16.8, 16.7 | 16.8, 16.8, 16.8, 16.8 | +0.1 | pass |
| 400 cards | dive | 4x | 33.3, 33.3, 33.2, 33.3 | 16.8, 16.7, 16.8, 16.8 | -16.5 | pass |
| 1,500 cards | pan-fit | 4x | 16.8, 16.8, 16.7, 16.7 | 16.8, 16.7, 16.7, 16.8 | 0 | pass |
| M11 shape | pan-fit | 4x | 16.8, 16.8, 16.8, 16.8 | 16.7, 16.7, 16.8, 16.8 | -0.1 | pass |
| M11 shape | all-open | 4x | 16.7, 16.7, 16.8, 16.8 | 16.8, 16.8, 16.8, 16.8 | +0.1 | pass |
| M11 shape | dive | 4x | 16.7, 16.7, 16.8, 16.8 | 16.7, 16.8, 16.8, 16.7 | 0 | pass |
| M11 tree | C3 load | 1x | 82, 73, 79, 69 ms | 71, 89, 72, 69 ms | -4.5 ms | pass |
| M11 shape | C3 load | 1x | 76, 77, 75, 72 ms | 68, 67, 74, 68 ms | -7.5 ms | pass |
| M11 tree | pan-fit | 1x | 16.8, 16.8, 16.8, 16.8 | 16.8, 16.8, 16.8, 16.7 | 0 | pass |
| M11 tree | all-open | 1x | 16.8, 16.8, 16.7, 16.8 | 16.7, 16.8, 16.7, 16.7 | -0.1 | pass |
| M11 tree | dive | 1x | 16.8, 16.8, 16.7, 16.8 | 16.8, 16.8, 16.7, 16.8 | 0 | pass |
| 400 cards | pan-fit | 1x | 16.7, 16.7, 16.8, 16.8 | 16.7, 16.8, 16.8, 16.7 | 0 | pass |
| 400 cards | dive | 1x | 16.7, 16.8, 16.7, 16.8 | 16.7, 16.7, 16.7, 16.8 | -0.1 | pass |
| 1,500 cards | pan-fit | 1x | 16.8, 16.7, 16.8, 16.8 | 16.8, 16.7, 16.8, 16.8 | 0 | pass |
| M11 shape | pan-fit | 1x | 16.7, 16.8, 16.8, 16.8 | 16.8, 16.8, 16.8, 16.7 | 0 | pass |
| M11 shape | all-open | 1x | 16.7, 16.7, 16.7, 16.7 | 16.8, 16.7, 16.7, 16.7 | 0 | pass |
| M11 shape | dive | 1x | 16.7, 16.7, 16.7, 16.7 | 16.7, 16.8, 16.8, 16.8 | +0.1 | pass |

Results:
- The three acceptance values pass.
- The dive of the 400-card map at 4x has a p95 of one tick in each run of B (16.7 to 16.8 ms), and of two ticks in each run of A (33.2 to 33.3 ms). The other p95 values of A and B are one tick.
- C3 at 4x and at 1x is not more in B than in A. The values overlap.

Not measured: a device with a GPU, a device pixel ratio of 2, and the cost of the text fades of R3 alone.

### R3: the motion of the text

The motion probe of the review (`motion.js` of the motion verifier, with one change: it keeps all the text events) was operated again on the final code. It has a dive, a stop, a zoom out, a zoom of 40 frames and a pan, on the M11 tree, the 400-card map and the map of this repository. It was operated at 1440 x 900, 390 x 844 and 844 x 390, in light and dark. Its acceptance values were in its header before its first run by the reviewer. The text count is approximate: a text that goes under a portal, the path or the help line, or that comes in at the screen edge, also counts.

| Page | Screen | Scheme | Largest alpha step | Line pixels over a box | Pixel jumps at a stop | Text events (0b547b7) | Text events | Fit (width, height) |
|---|---|---|---|---|---|---|---|---|
| M11 tree | 1440 x 900 | light | 0.200 | 0 | 5 | 1516 | 291 | each level 1.00 |
| M11 tree | 1440 x 900 | dark | 0.200 | 0 | 0 | 1514 | 291 | each level 1.00 |
| M11 tree | 390 x 844 | light | 0.200 | 0 | 0 | 372 | 80 | each level 0.92 |
| M11 tree | 390 x 844 | dark | 0.200 | 0 | 0 | 372 | 80 | each level 0.92 |
| M11 tree | 844 x 390 | light | 0.200 | 0 | 0 | 643 | 365 | each level 0.92 |
| M11 tree | 844 x 390 | dark | 0.200 | 0 | 0 | 643 | 365 | each level 0.92 |
| 400 cards | 1440 x 900 | light | 0.200 | 0 | 0 | 288 | 70 | top 1.00, 0.61 |
| 400 cards | 1440 x 900 | dark | 0.200 | 0 | 0 | 288 | 70 | top 1.00, 0.61 |
| 400 cards | 390 x 844 | light | 0.208 | 0 | 0 | 22 | 22 | top 0.92, 0.20 |
| 400 cards | 390 x 844 | dark | 0.214 | 0 | 0 | 22 | 22 | top 0.92, 0.20 |
| 400 cards | 844 x 390 | light | 0.200 | 0 | 0 | 8 | 9 | top 0.68, 1.00 |
| 400 cards | 844 x 390 | dark | 0.200 | 0 | 0 | 8 | 9 | top 0.68, 1.00 |
| systemap | 1440 x 900 | light | 0.200 | 0 | 0 | 1541 | 169 | top 0.73, 1.00 |
| systemap | 1440 x 900 | dark | 0.200 | 0 | 0 | 1541 | 169 | top 0.73, 1.00 |
| systemap | 390 x 844 | light | 0.200 | 0 | 0 | 225 | 56 | top 0.92, 0.44 |
| systemap | 390 x 844 | dark | 0.200 | 0 | 0 | 225 | 56 | top 0.92, 0.44 |
| systemap | 844 x 390 | light | 0.200 | 0 | 0 | 541 | 130 | top 0.30, 1.00 |
| systemap | 844 x 390 | dark | 0.200 | 0 | 0 | 531 | 130 | top 0.30, 1.00 |

For a line, the probe found 0 frames with a line pixel over a box or a card. At each fit, no portal covers a card of the open map, and no text is cut at the screen edge. The fit values are the same as in the review of 0b547b7. The largest alpha step between two frames is 0.2, or 0.208 to 0.214 on the 400-card map at 390 x 844 (limit 0.25).

At a stop, the M11 tree at 1440 x 900 light has 5 frames in which more than 50 pixels change by more than 64 (limit of the probe). The largest change is 92. In each of these frames, a change of the count of columns fades (`colFade`): the earlier lines fade out by 0.2 and the new lines fade in by 0.2 at the same place. A copy of the page without this fade gave 0 such frames in the same probe. Thus these frames are a fade by time, and no text appears at one time in them.

The text events of the M11 tree at 1440 x 900 dark with a size of 9 px or less and an alpha of 0.45 or more: 750 on commit 0b547b7, and 116 with the change. Most of the events that stay are near the portals at the screen edge, or in the zoom of 40 frames. In that zoom, a fade that follows the zoom changes by more than 0.25 in one frame.

## G1 and G2: the portals keep off the boxes of the maps (2026-11-06)

Scope: the canvas page (`page_canvas.py`, `page_canvas_draw.py`, `page_canvas_fade.py`) after commit 8c1a2d8. At the fit of P0/Q1 of the M11 tree at 1440 x 900, the portals Q0 and Q2 in the bottom row covered the flow label "record" of the map P0. The camera fit keeps the cards of the open map out of the bands of the portals, but not the boxes of the maps around it. The change:
- The frame finds the portals after it draws the maps. Thus the first values of OBST (`NMAP`) are the boxes of the maps of the frame: the cards, the flow label plates and the texts.
- After `apart`, each portal moves off these boxes (`dodge`): along its edge, or 34 px or less into the screen, to the open place nearest to its move in the last frame. The boxes of its neighbour do not count. When no place is open, it stays at its place.
- This move changes by 0.2 px for each millisecond (3.4 px in one frame) or less. It waits when the camera moves the place of the portal by 16 px or more in one frame, and it adds no more than 16 px less that move. With reduced motion, it occurs at one time.
- `systemapCanvas.obstacles()` gives these boxes. `tests/canvas_driver.js --clear` and acceptance 10 of `tests/test_canvas_browser.py` use them. `nested_tree(cols)` of `canvas_frames.py` can make the M11 shape with fewer columns. The measurements use the default of 14 columns.

The scripts `run_g.py`, `run_ab.py` and `run_ab2.py` are in the scratchpad of the agent and are not in the repository. Each has its acceptance values in its docstring, written before its first run. A is commit 8c1a2d8. For G1 and G2, A has one change for the measurement only: the page records `NMAP` and gives `obstacles()`. For C2 and C3, A is commit 8c1a2d8 with no change. Other agents used Chromium on the host at the same time. The order of A and B changed in each run.

### G1: the portals at the fit of each map

`tests/canvas_driver.js --clear`: the fit of each of the 50 maps at 1440 x 900, 390 x 844 and 844 x 390, with reduced motion. A problem is a portal box that covers a box of the maps with an opacity of 0.05 or more by more than 0.5 px. Acceptance: 0 problems for B on each page in each run, and 1 problem or more for A on the M11 tree. The M11 tree is the real canvas data of the tree (the cache of the reference views). `cols4` is the M11 shape with 4 columns of cards.

| Page | Fits | Portals | A: problems, runs 1 to 3 | B: problems, runs 1 to 3 |
|---|---|---|---|---|
| M11 tree | 150 | 714 | 19, 19, 19 | 0, 0, 0 |
| M11 shape | 150 | 546 | 0, 0, 0 | 0, 0, 0 |
| `cols4` | 150 | 498 | 48, 48, 48 | 0, 0, 0 |

In A, the problems of the M11 tree are at 1440 x 900 (Q0 over the label "record" at the fit of P0/Q1, and the same in the maps Q1 and Q2 of P0 to P6) and at 390 x 844. Pass. A first version of B that moved the portals before `apart` had 4 problems at 390 x 844 on the M11 tree: three portals did not fit in the free parts of the bottom row. That version was not kept.

### G2: the motion of the portals

`tests/canvas_driver.js --portals` (acceptance 14): a slow dive of 300 frames and the zoom out back, without reduced motion. `jump` is the largest move of the middle of a portal between two frames, in px. Revision 1 of the acceptance: `jump` of B at most 16 px, and the alpha step at most 0.25. Revision 1 failed: in the move into `cols4` P0/A1/B0 at 1440 x 900, `jump` of B was 17.20 to 18.26 px in the 3 runs (B then had no limit for the sum of the two moves). In the same move, `jump` of A was 16.79 px. Thus there the camera alone moves a portal by more than 16 px in one frame. B then got the limit of 16 px less the move of the place. Revision 2, written before its runs: `jump` of B at most the larger of 16 px and `jump` of A of the same run plus 0.5 px, and the alpha step at most 0.25. Revision 2, 3 runs:

| Page and map | Screen | Move | A: `jump`, runs 1 to 3 | B: `jump`, runs 1 to 3 |
|---|---|---|---|---|
| M11 tree P0/Q1 | 1440 x 900 | dive | 9.17, 9.17, 9.17 | 9.98, 9.90, 9.94 |
| M11 tree P0/Q1 | 1440 x 900 | zoom out | 9.17, 9.17, 9.17 | 12.53, 12.53, 12.53 |
| M11 tree P0/Q1 | 390 x 844 | dive | 8.26, 8.26, 8.26 | 8.26, 8.26, 8.26 |
| M11 tree P0/Q1 | 390 x 844 | zoom out | 8.26, 8.26, 8.26 | 8.26, 8.21, 8.17 |
| M11 tree P5/Q2 | 1440 x 900 | dive | 8.20, 8.20, 8.20 | 10.54, 10.50, 10.54 |
| M11 tree P5/Q2 | 1440 x 900 | zoom out | 8.20, 8.20, 8.20 | 11.56, 11.54, 11.56 |
| M11 tree P5/Q2 | 390 x 844 | dive | 4.13, 4.13, 4.13 | 7.44, 7.44, 7.44 |
| M11 tree P5/Q2 | 390 x 844 | zoom out | 4.13, 4.13, 4.11 | 4.13, 4.13, 4.13 |
| M11 shape P0/A0 | 1440 x 900 | dive | 9.57, 9.57, 9.57 | 11.18, 11.20, 11.22 |
| M11 shape P0/A0 | 1440 x 900 | zoom out | 9.57, 9.57, 9.57 | 12.89, 12.91, 12.91 |
| M11 shape P0/A0 | 390 x 844 | dive | 11.00, 11.00, 10.93 | 13.69, 13.69, 13.61 |
| M11 shape P0/A0 | 390 x 844 | zoom out | 11.00, 11.00, 11.00 | 14.23, 14.23, 14.23 |
| `cols4` P0/A0 | 1440 x 900 | dive | 11.55, 11.55, 11.55 | 14.49, 14.51, 14.53 |
| `cols4` P0/A0 | 1440 x 900 | zoom out | 11.55, 11.55, 11.55 | 14.87, 14.87, 14.85 |
| `cols4` P0/A0 | 390 x 844 | dive | 11.00, 10.93, 10.87 | 11.32, 11.19, 11.12 |
| `cols4` P0/A0 | 390 x 844 | zoom out | 10.93, 10.93, 11.00 | 11.00, 11.00, 11.53 |
| `cols4` P0/A1/B0 | 1440 x 900 | dive | 16.79, 16.79, 16.79 | 16.79, 16.79, 16.79 |
| `cols4` P0/A1/B0 | 1440 x 900 | zoom out | 16.79, 16.79, 16.79 | 16.79, 16.79, 16.79 |
| `cols4` P0/A1/B0 | 390 x 844 | dive | 13.59, 13.59, 13.59 | 13.51, 13.59, 13.59 |
| `cols4` P0/A1/B0 | 390 x 844 | zoom out | 13.59, 13.51, 13.59 | 13.51, 13.59, 13.43 |

The largest alpha step was 0.0425 for A and B in each move. Revision 2 passes. Explorations before `run_g.py` had no acceptance values. With 0.5 px for each millisecond, `jump` of B on the M11 shape at 390 x 844 was 18.5 px. In the same version, a portal that faded out after a move into the screen went to the top row: a `jump` of 727 px. Its row now comes from its place before that move. With 0.25 px for each millisecond, `jump` of B in `cols4` P0/A0 at 1440 x 900 was 15.75 px. The move of 16.79 px in `cols4` P0/A1/B0 comes from the camera, not from this change.

### C2 and C3: A/B

`run_ab.py`: each scenario of `canvas_frames.py` (`run`, the same driver and frames) for A and B, 3 runs. Acceptance: (1) each scenario of B passes its limit in each run, (2) the 400-card dive at 4x of B is at most 16.8 ms in each run, (3) for each scenario, the median of B is less than the median of A plus one tick, (4) C3 at 4x is information. The values are p95 in ms, or the load time for C3. The load average (1 minute) before the runs was 0.54 to 0.62.

| Data | Scenario | CPU | A: runs 1 to 3 | B: runs 1 to 3 | Median B minus median A | Result of B |
|---|---|---|---|---|---|---|
| M11 tree | C3 load | 4x | 270.5, 270.9, 254.6 ms | 267.3, 301.2, 343.8 ms | +30.7 ms | information |
| M11 shape | C3 load | 4x | 293.5, 239.2, 285.9 ms | 285.7, 281.8, 271.3 ms | -4.1 ms | information |
| M11 tree | pan-fit | 4x | 16.8, 16.7, 16.8 | 16.7, 16.7, 16.8 | -0.1 | pass |
| M11 tree | all-open | 4x | 16.7, 16.8, 16.8 | 16.8, 16.8, 16.7 | 0 | pass |
| M11 tree | dive | 4x | 16.8, 16.8, 16.8 | 16.8, 16.8, 33.3 | 0 | pass |
| 400 cards | pan-fit | 4x | 16.8, 16.7, 16.7 | 16.8, 16.8, 16.8 | +0.1 | pass |
| 400 cards | dive | 4x | 16.8, 33.3, 16.8 | 16.8, 33.3, 16.8 | 0 | fail |
| 1,500 cards | pan-fit | 4x | 16.8, 16.8, 16.8 | 16.7, 16.8, 16.8 | 0 | pass |
| M11 shape | pan-fit | 4x | 16.8, 16.8, 16.8 | 16.8, 16.7, 16.8 | 0 | pass |
| M11 shape | all-open | 4x | 16.8, 16.8, 16.8 | 16.7, 16.8, 16.8 | 0 | pass |
| M11 shape | dive | 4x | 16.8, 16.8, 16.8 | 16.8, 16.8, 16.8 | 0 | pass |
| M11 tree | C3 load | 1x | 72.6, 72.6, 76.0 ms | 67.6, 91.0, 72.8 ms | +0.2 ms | pass |
| M11 shape | C3 load | 1x | 70.1, 89.5, 74.4 ms | 74.9, 70.4, 69.7 ms | -4.0 ms | pass |
| M11 tree | pan-fit | 1x | 16.8, 16.7, 16.7 | 16.7, 16.7, 16.7 | 0 | pass |
| M11 tree | all-open | 1x | 16.8, 16.7, 16.8 | 16.7, 16.7, 16.7 | -0.1 | pass |
| M11 tree | dive | 1x | 16.8, 16.7, 16.8 | 16.7, 16.8, 16.8 | 0 | pass |
| 400 cards | pan-fit | 1x | 16.7, 16.8, 16.8 | 16.7, 16.8, 16.7 | -0.1 | pass |
| 400 cards | dive | 1x | 16.8, 16.8, 16.7 | 16.8, 16.8, 16.8 | 0 | pass |
| 1,500 cards | pan-fit | 1x | 16.8, 16.7, 16.8 | 16.8, 16.7, 16.7 | -0.1 | pass |
| M11 shape | pan-fit | 1x | 16.8, 16.7, 16.7 | 16.7, 16.7, 16.8 | 0 | pass |
| M11 shape | all-open | 1x | 16.7, 16.7, 16.7 | 16.7, 16.8, 16.7 | 0 | pass |
| M11 shape | dive | 1x | 16.7, 16.8, 16.8 | 16.7, 16.8, 16.7 | -0.1 | pass |

`run_ab2.py` then operated the two dives at 4x again in 5 runs, with the same pages. Acceptance: the 400-card dive of B at most 16.8 ms in each run, and the M11 tree dive of B at most 35.0 ms in each run.

| Scenario | A: runs 1 to 5 | B: runs 1 to 5 | Result of B |
|---|---|---|---|
| 400 cards dive 4x | 33.3, 16.8, 16.8, 16.8, 33.3 | 16.8, 33.3, 16.8, 16.8, 33.3 | fail |
| M11 tree dive 4x | 16.8, 16.8, 16.8, 16.8, 16.8 | 16.8, 16.8, 16.8, 16.7, 16.8 | pass |

Results:
- Acceptance 2 of `run_ab.py` and acceptance 1 of `run_ab2.py` fail. In the 8 runs, the 400-card dive at 4x had a p95 of two ticks (33.3 ms) in 3 runs of A and in 3 runs of B. On the 400-card page, the change does no new work: the map has no portal, thus `dodge` gets an empty list. The only change on that page is the order of the work in the frame. A on this host also failed the limit of one tick, thus these runs do not show a difference between A and B. A measurement on a quiet host is necessary to show the limit of one tick for B.
- All other scenarios pass their limits. The medians of B are not more than the medians of A plus one tick.
- The M11 tree dive at 4x of B had 33.3 ms in run 3 of `run_ab.py`, and 16.7 to 16.8 ms in the 5 runs of `run_ab2.py`.

Not measured: a device with a GPU, a device pixel ratio of 2, and the cost of `dodge` alone in a frame.

## H1 to H3: the portals at rest (2026-11-06)

Scope: the portals of the canvas page (`page_canvas_draw.py`, `page_canvas_fade.py`). On commit 8c1a2d8, at 390 x 844, the hash #P0/Q1 of the M11 tree showed the portal "Q0 in P0" at a low alpha behind the portal A0, 2.5 s after the load, while the camera did not move.

The cause: `portalsOf` gave the target `show` of a portal from the camera, with `smooth(0, 160, off)`. `off` is the distance of the card of the neighbour out of the screen, less a margin of 30 px. `portalFades` moves the `show` to this target by time. Thus, when the camera stopped with the card of a neighbour 0 to 160 px past the margin, the portal stayed partly shown. At the fit of P0/Q1 at 390 x 844, Q0 had an `off` of 30.7 px and a `show` of 0.096. The scale of a portal is `0.85 + 0.15 * show`, thus the small portal Q0 was near A0. The fade of `portalFades`, the stacking of `apart` and `stack`, and the fade-out of a removed portal were not the cause: each `room` was 1 at rest, and no two portal boxes overlapped.

The change: a neighbour has a portal only when no part of its card is on the screen (`onScreen`). The target `show` is then 1. Else the neighbour has no portal, and its portal of the last frame fades out by time, as before. The fade by time (F5) did not change.

### H1: the alpha of the portals at rest

`probe.js` (in the scratchpad of the agent) opens the page with the hash #P0/Q1 and waits 2.5 s. Then it sets the camera to the fit of each of the 50 maps (`view(fit(id))`) and waits 1 s. The screens are 390 x 844, 844 x 390 and 1440 x 900, without reduced motion. For each of the 153 views, it records each portal with an alpha that is not 0 or 1, and each two portal boxes with an alpha above 0 that overlap. The acceptance value comes from the task: no such portal and no such overlap in each view. The value was not written in a docstring before the first run.

| Page | Data | Views | Views with a problem | Problems |
|---|---|---|---|---|
| A (8c1a2d8) | M11 tree | 153 | 29 | alpha only: Q0 0.096 and P1 0.864 at 390 x 844, Q1 0.914 at 844 x 390, Q1 0.221 at 1440 x 900 |
| B | M11 tree | 153 | 0 | none |
| A (`pages.py`) | M11 shape | 153 | 49 | alpha, for example P1, A1 and B1 at 0.864 at 390 x 844 |

The A page of the M11 tree is the page of the task (commit 8c1a2d8). The A page of the M11 shape comes from `pages.py` (see H2). In the M11 tree, no view of A had two portal boxes that overlap. For the M11 shape, the record has only the first 40 problem lines of A, and they are all alpha problems. The browser test is acceptance 16 of `tests/test_canvas_browser.py` (`tests/canvas_driver.js --rest`). It uses the M11 shape, the hash #P0/A0 and the fits of the top map and of one map on each level, on the three screens (15 views). Before the test was in the repository, `rest.py` operated the driver on the A page and the B page. The acceptance values were in its docstring before the first run: B has no problem, and A has one or more problems. Result: the M11 shape gave 4 views with a problem for A and 0 for B. The M11 tree gave 3 views with a problem for A and 0 for B. Pass.

The screenshots of `shot.js` with B: at 390 x 844 (#P0/Q1), the bottom row has the four portals Q0, A0, P1 and T0 at the full alpha, with a gap between each two.

### H2: C2 at 4x, A/B

`ab.py` (in the scratchpad of the agent). B is the change. A comes from the same build (`pages.py`), with the earlier lines of the portal target in `portalsOf`. Thus A operates the code of commit 8c1a2d8. Its text also has the new comments and the function `onScreen`, which A does not use. The driver is `bench/jev/canvas_frames.js` without changes, at 4 times CPU throttling. There were 3 runs, A then B in runs 1 and 3, B then A in run 2. Other agents used Chromium on the host at the same time: before each pair, 4 to 12 chrome processes operated.

The acceptance values were in the docstring of `ab.py` before the first run:
1. Each C2 scenario of B has a p95 of at most 35.0 ms in each run.
2. The 400-card dive: the p95 of B is at most 16.8 ms in each run.
3. For each scenario, the median of B less the median of A is less than 16.1 ms.

| Data | Scenario | A p95, runs 1 to 3 (ms) | B p95, runs 1 to 3 (ms) | Median B less median A | Result of B |
|---|---|---|---|---|---|
| M11 tree | pan-fit | 16.7, 16.8, 16.7 | 16.8, 16.7, 16.7 | 0 | pass |
| M11 tree | all-open | 16.7, 16.8, 16.8 | 16.8, 16.7, 33.3 | 0 | pass |
| M11 tree | dive | 33.3, 33.3, 33.3 | 16.8, 16.8, 33.4 | -16.5 | pass |
| M11 shape | pan-fit | 16.8, 16.7, 16.7 | 16.7, 16.8, 16.8 | +0.1 | pass |
| M11 shape | all-open | 16.8, 16.8, 16.8 | 16.8, 16.8, 16.8 | 0 | pass |
| M11 shape | dive | 16.8, 16.8, 16.8 | 16.8, 16.8, 16.8 | 0 | pass |
| 400 cards | dive | 33.3, 33.3, 16.8 | 33.3, 16.8, 16.8 | -16.5 | fail |

Acceptance values 1 and 3 pass. Acceptance value 2 fails: in run 1, the 400-card dive of B had a p95 of 33.3 ms. A had the same value in runs 1 and 2. The 400-card map has no card that opens a map. Thus the chain is empty, `portalsOf` makes no portal, and the changed lines do not operate in these frames.

### H3: the 400-card dive at 4x, A/B

`ab400.py` (in the scratchpad of the agent), after H2. The acceptance values were in its docstring before the first run: the p95 of B is at most 16.8 ms in each of 6 interleaved runs, and the p95 of A is information. Before each pair, 6 to 10 chrome processes operated.

| Run | A p95 (ms) | B p95 (ms) |
|---|---|---|
| 1 | 33.3 | 33.3 |
| 2 | 16.8 | 16.8 |
| 3 | 16.8 | 16.8 |
| 4 | 16.8 | 33.3 |
| 5 | 33.3 | 16.8 |
| 6 | 33.3 | 33.3 |

Result: fail. B had 33.3 ms in 3 of 6 runs, and A had 33.3 ms in 3 of 6 runs. The two pages operate the same code for this map. Thus these runs do not show a difference between A and B. They show that the 400-card dive at 4x on this host, with the Chromium processes of other agents, does not stay at one tick. A measurement on a quiet host is necessary to show the rule of 16.8 ms for this change.

## C2 and C3 of commit d55580c: two runs (2026-11-06)

Scope: `bench/jev/canvas_frames.py` without changes, on commit d55580c (the changes of G1, G2 and H1 to H3). There is no A page. The script `run_quiet.py` is in the scratchpad of the agent and is not in the repository. Before each run, it waited until no chrome, chromium, node or pytest process (by the name of the program) had operated for 30 s, with a poll each 1 s. During each run, it recorded these processes each 2 s, but not the processes of the run.

The acceptance values were in the docstring of `run_quiet.py` before the first run:
1. Each scenario passes its limit of `canvas_frames.py` in each run.
2. The 400-card dive at 4x has a p95 of at most 16.8 ms in each run.
3. No p95 of a scenario is one tick (16.1 ms or more) above the largest p95 of the same scenario in runs B1 to B4 of R2.
4. Information only: C3 at 4x.

The host was not quiet during the runs. Each run started after 30 s with no such process. Then, a different agent started `motion.js` with Chromium (7 to 16 processes) 18 s after the start of run 1 and 4 s after the start of run 2. These processes operated until the end of each run. The load average (1 minute) was 0.64 to 1.95 in run 1 and 0.34 to 1.82 in run 2.

| Data | Scenario | CPU | R2 B: largest p95 | Run 1 | Run 2 | Result |
|---|---|---|---|---|---|---|
| M11 tree | C3 load | 4x | 394 ms | 264 ms | 253 ms | information |
| M11 shape | C3 load | 4x | 257 ms | 269 ms | 234 ms | information |
| M11 tree | pan-fit | 4x | 16.8 | 16.8 | 16.7 | pass |
| M11 tree | all-open | 4x | 16.8 | 16.8 | 16.8 | pass |
| M11 tree | dive | 4x | 16.8 | 33.2 | 16.7 | fail (acceptance 3) |
| 400 cards | pan-fit | 4x | 16.8 | 16.8 | 16.7 | pass |
| 400 cards | dive | 4x | 16.8 | 33.4 | 16.8 | fail (acceptance 2 and 3) |
| 1,500 cards | pan-fit | 4x | 16.8 | 16.7 | 16.8 | pass |
| M11 shape | pan-fit | 4x | 16.8 | 16.7 | 16.8 | pass |
| M11 shape | all-open | 4x | 16.8 | 16.8 | 16.8 | pass |
| M11 shape | dive | 4x | 16.8 | 16.8 | 16.8 | pass |
| M11 tree | C3 load | 1x | 89 ms | 85 ms | 84 ms | pass |
| M11 shape | C3 load | 1x | 74 ms | 67 ms | 76 ms | pass |
| M11 tree | pan-fit | 1x | 16.8 | 16.8 | 16.8 | pass |
| M11 tree | all-open | 1x | 16.8 | 16.7 | 16.7 | pass |
| M11 tree | dive | 1x | 16.8 | 16.8 | 16.8 | pass |
| 400 cards | pan-fit | 1x | 16.8 | 16.7 | 16.8 | pass |
| 400 cards | dive | 1x | 16.8 | 16.7 | 16.7 | pass |
| 1,500 cards | pan-fit | 1x | 16.8 | 16.7 | 16.8 | pass |
| M11 shape | pan-fit | 1x | 16.8 | 16.7 | 16.7 | pass |
| M11 shape | all-open | 1x | 16.8 | 16.8 | 16.7 | pass |
| M11 shape | dive | 1x | 16.8 | 16.8 | 16.8 | pass |

For C3, the R2 B column gives the largest load time of R2 B.

Results:
- Acceptance 1 passes: each scenario passes its limit of `canvas_frames.py` in the two runs.
- Acceptance 2 fails: in run 1, the 400-card dive at 4x had a p95 of 33.4 ms. In run 2, it had 16.8 ms.
- Acceptance 3 fails: in run 1, the M11 tree dive at 4x had 33.2 ms and the 400-card dive at 4x had 33.4 ms. Each is one tick above R2 B. In run 2, each p95 is one tick.
- In the two runs, the Chromium of a different agent operated. Thus these runs do not show that the change causes the two ticks of run 1. H3 found two ticks in the 400-card dive at 4x also for A, with Chromium of other agents. A measurement on a quiet host for all of the run is necessary.

Not measured: a device with a GPU and a device pixel ratio of 2.

## J1 to J3: the fixes after the fourth review of commit d55580c (2026-11-06)

Scope: the portals of the canvas page (`page_canvas_draw.py`, `page_canvas_fade.py`), after the review of commit d55580c. The review found these problems:
- `portalsOf` called the point test `onScreen(p)`, not the new box test. The two functions had the same name in one script, and the second one replaced the first one. Thus a neighbour whose card was partly on the screen could get a portal. The box test is now `boxOnScreen`.
- The move of `dodge` (`dx`, `dy`) stayed from frame to frame as a move from the place of the portal. It waited while the place moved by 16 px or more in one frame. Thus, after a flight, a change of the hash, a change of the screen size or a jump of the camera, the move of an earlier view came back at a different place. A portal at the full alpha was then partly or fully off the screen, and it slid back for up to 1.75 s after the camera stopped. While it slid, it went over other portals.

The changes:
- When the place moves by 16 px or more in one frame, the move changes by that distance or less in that frame. Thus the move does not stay from an earlier view.
- While the place does not move, the step is a quarter of the distance to the target, and 3.4 px or more. Thus the move slows down near its target, and a long move ends soon after the camera stops. While the place moves by 4 px or more in one frame, the step is 3.4 px or less, as before. The sum of the step and the move of the place stays less than 16 px.
- While the move goes step by step, a portal does not go over a different portal. A portal that it covers at the start does not stop it.
- The portal stays in the range of its edge. When `apart` puts the place out of that range, the range goes to the place.
- Cleanups with no change of behavior: one value for "no move yet" (`undefined`), `bottomRow()` and `rowRange(t)`, no `show` target in `portalsOf`, one `Math.min(dt, PORTAL_DT)` in `fadeFrame`, `levels()` in the driver, and the `--clear` assertions in their own test.

The probes and the scripts are in the scratchpad of the agent and are not in the repository. No acceptance value was written before the probes of J1. They are information only. A is the page of the review (commit d55580c), from the folder of the review. B is the change.

### J1: the probes of the review

| Probe | Page and screen | A (from the review) | B |
|---|---|---|---|
| `hashfly.js`: #P2/A2/B0, then the hash #P3 | `cols4`, 844 x 390 | /P7 at x = -103 with alpha 1.00, then a slide to x = 119 until 2.50 s | /P7 at x = 128 at 1.00 s and at 119 from 1.25 s. No point off the screen. |
| `hashfly.js`: #P0/A0, then 390 x 844 | `cols4`, 844 x 390 | /P7 at x = -1 and -7 with alpha 1.00, a slide of 284 px, /P7 over /P1 | At rest from 0.75 s. No portal over a different portal. |
| `rest.js`: the fit of each map, 1.5 s, then 1 s with no camera change | `cols4`, M11 tree, M11 shape, three screens | 8 views with motion on `cols4` | 0 views with motion on each page |
| `pan.js`: from each fit, a pan of 6 px in each frame, 4 directions | `cols4`, 1440 x 900 and 390 x 844 | 88 (map, direction) pairs with a portal off the screen | 0 pairs |

In the first version of B, the limit of the edge range was applied after the step. Then a portal with a target out of the range moved by a step in each frame, and the limit moved it back. `rest.js` found 12 views on the M11 tree that drew 60 frames in each second with no move. The version above applies the limit to the target and to the start before the step. In the second version of B, the step was 3.4 px or less also while the place did not move. Then `rest.js` found 10 views on `cols4` at 844 x 390 that still moved 1.5 s after the fit, by 35 to 50 px in 1 s. With the step of a quarter of the distance, `trace.js` shows the fit of `cols4` P0/A0/B0 at 844 x 390 at rest 0.78 s after the camera change. The fade in of the portals takes 0.4 s of that time. The first run of the browser tests with the step found a move of 16.000000000000004 px in acceptance 14. The step now keeps a margin of 0.05 px.

`pan.js` with B found a move of 98.9 px of /P7 in one frame, at the fit of P3 at 1440 x 900 with a pan to the left. There the neighbour goes from the left side band to the bottom row, and `apart` puts it after the portal in the corner. Commit 8c1a2d8 and commit d55580c give the same move in the same pan. `dodge` does not cause it. It is not changed here.

### J2: C2 and C3, A/B, on a quiet host

`run_ab.py`. A is commit 8c1a2d8 (no `dodge`). B is the change. Each copy operated its own `bench/jev/canvas_frames.py` without changes. The order was A1, B1, B2, A2, A3, B3. Before each run, the script waited until no chrome, chromium, node or pytest process (by the name of the program) had operated for 30 s. During each run, it recorded these processes each 2 s, but not the processes of the run. A run with a different process in a sample is "not quiet", and the script makes it again.

The acceptance values were in the docstring of `run_ab.py` before the first run:
1. Each scenario of B passes its limit of `canvas_frames.py` in each quiet run.
2. The 400-card dive at 4x: the p95 of B is at most 16.8 ms in each quiet run.
3. For each scenario, the median of B less the median of A is less than 16.1 ms.
4. Information only: C3 at 4x.

A first attempt stopped after run A1. Its samples had only zombie processes (state Z, with no command line) with the name chrome-headless, from the browsers of the run itself after they closed. Revision 1 of the quiet gate, before the next run A1: a zombie process does not count. The acceptance values did not change. A command of the agent (`systemap refresh`, `check` and `judgement`, about 10 s) also operated at the start of that first A1. The first attempt is not in the table.

All 6 runs were quiet: no sample had a different process. The load average (1 minute) was 0.37 to 1.52.

| Data | Scenario | CPU | A: runs 1 to 3 | B: runs 1 to 3 | Median B minus median A | Result of B |
|---|---|---|---|---|---|---|
| M11 tree | C3 load | 4x | 294, 255, 279 ms | 266, 268, 305 ms | -11 ms | information |
| M11 shape | C3 load | 4x | 273, 262, 235 ms | 272, 330, 290 ms | +28 ms | information |
| M11 tree | pan-fit | 4x | 16.7, 16.7, 16.7 | 16.7, 16.8, 16.8 | +0.1 | pass |
| M11 tree | all-open | 4x | 16.8, 16.8, 16.8 | 16.8, 16.7, 16.8 | 0 | pass |
| M11 tree | dive | 4x | 16.8, 16.7, 16.8 | 16.8, 16.8, 16.8 | 0 | pass |
| 400 cards | pan-fit | 4x | 16.8, 16.8, 16.8 | 16.8, 16.8, 16.7 | 0 | pass |
| 400 cards | dive | 4x | 33.3, 33.3, 16.8 | 33.3, 33.3, 16.8 | 0 | pass of the limit, fail of acceptance 2 |
| 1,500 cards | pan-fit | 4x | 16.7, 16.8, 16.8 | 16.8, 16.8, 16.7 | 0 | pass |
| M11 shape | pan-fit | 4x | 16.7, 16.8, 16.8 | 16.8, 16.8, 16.7 | 0 | pass |
| M11 shape | all-open | 4x | 16.8, 16.8, 16.7 | 16.7, 16.8, 16.7 | -0.1 | pass |
| M11 shape | dive | 4x | 16.8, 16.8, 16.8 | 16.8, 16.8, 16.8 | 0 | pass |
| M11 tree | C3 load | 1x | 78, 71, 76 ms | 90, 84, 70 ms | +8 ms | pass |
| M11 shape | C3 load | 1x | 72, 66, 65 ms | 71, 70, 67 ms | +4 ms | pass |
| M11 tree | pan-fit | 1x | 16.7, 16.8, 16.7 | 16.7, 16.8, 16.7 | 0 | pass |
| M11 tree | all-open | 1x | 16.8, 16.8, 16.7 | 16.8, 16.8, 16.7 | 0 | pass |
| M11 tree | dive | 1x | 16.8, 16.8, 16.8 | 16.7, 16.8, 16.8 | 0 | pass |
| 400 cards | pan-fit | 1x | 16.8, 16.8, 16.7 | 16.8, 16.7, 16.7 | -0.1 | pass |
| 400 cards | dive | 1x | 16.8, 16.8, 16.7 | 16.8, 16.8, 16.7 | 0 | pass |
| 1,500 cards | pan-fit | 1x | 16.8, 16.8, 16.7 | 16.7, 16.7, 16.7 | -0.1 | pass |
| M11 shape | pan-fit | 1x | 16.7, 16.7, 16.8 | 16.8, 16.8, 16.8 | +0.1 | pass |
| M11 shape | all-open | 1x | 16.8, 16.8, 16.7 | 16.7, 16.8, 16.8 | 0 | pass |
| M11 shape | dive | 1x | 16.8, 16.8, 16.7 | 16.7, 16.8, 16.8 | 0 | pass |

Results:
- Acceptance 1 passes.
- Acceptance 2 fails: the 400-card dive at 4x of B had a p95 of 33.3 ms in runs 1 and 2. A had the same values in runs 1 and 2, on the same quiet host. The 400-card map has no card that opens a map. Thus the chain is empty, there is no portal, and `dodge` does not operate in these frames. The cause is not in this change. It is also in commit 8c1a2d8. R2 found 16.8 ms in 4 of 4 runs for that code. A measurement of the frames of this dive (as R1) is necessary to find the cause.
- Acceptance 3 passes: the largest difference of the medians is +0.1 ms.

### J3: the views

The motion probe and the screenshots of the review (`motion.js` of verify3, without changes), on the pages of B: the M11 tree, the 400-card map and the self-map with `[render] canvas = true`, at 1440 x 900, 390 x 844 and 844 x 390, light and dark (18 runs).
- The largest alpha step between two frames: text 0.2, lines 0.2, portals 0.043, images 0.217. Acceptance: 0.25 or less. Pass.
- 0 line pixels over cards, 0 page errors, 0 jumps.
- The item "in stops, fewer than 50 composite pixels change by more than 64" fails on the M11 tree at 1440 x 900 in light (6 frames, largest change 92), as in the review (1 to 7 frames). There, a wrapped second line of a description fades while the camera does not move. This is not a criterion of the review and it is not changed here.
- The screenshots of the fit of each level show the same layout as the review. At the fit of P0 at 1440 x 900, the portals P1 and T0 are across the right edge of the open card P0, as in the review. The open card is the frame around the view, and a portal does not keep off its body, only off its texts. At the fit of P0/Q1 at 1440 x 900, the portals P1 and T0 are in the bottom right corner, clear of the Q1 card.

Not measured: a device with a GPU and a device pixel ratio of 2.

## Claimed modules and judgement evidence on a tree of 50 maps (2026-11-05)

`bench/jev/claim_speed.py` gives the acceptance values in its docstring. They were written before the first run:

- With the change, `systemap check` and `systemap judgement` give the same output bytes as without it.
- With the change, each command takes at most 0.5 times the seconds without it.

The tree is the M11 tree of the nested parts design: 50 maps, 40 cards in each map, and about 1,900 modules (`bench/jev/canvas_data_size.py` on the nested canvas branch writes it). `place` and `extract` ran one time before the measurement. The host is a 4-core Xeon at 2.1 GHz. Each value is one run. "Before" is main at c6c0662. "After" is the branch `claude/claim-index`.

### Run 1: the claim index only

A profile of the canvas data build found that `model.claimed` compared each `implemented_by` pattern with each module: 20 million comparisons, 92 of 95 profiled seconds. The new module `claim_index` gives the same modules in the same order from an index of the modules.

| Command | Before | After | Ratio | Same output | Result |
|---|---|---|---|---|---|
| `check` | 69.1 s | 19.5 s | 0.28 | yes | PASS |
| `judgement` | 571.9 s | 492.5 s | 0.86 | yes | FAIL |

`judgement` failed. A profile of `judgement` (1,656 s with the profiler) found the cause in `judgement_evidence.names`. It made one regular expression for each judgement line and each module name: 7.8 million compilations, 1,593 s of the profile. The cache of the `re` module keeps 512 patterns, so almost each call compiled its pattern again.

### Run 2: the claim index and the word set of each line

`names` now finds a name of word characters, dots and hyphens in the set of words of the line (`judgement_evidence.words`, kept for 4,096 lines). A different name still uses the pattern. 500 random cases compare the new procedure with the pattern.

| Command | Before | After | Ratio | Same output | Result |
|---|---|---|---|---|---|
| `check` | 69.1 s | 20.3 s | 0.29 | yes | PASS |
| `judgement` | 571.9 s | 9.1 s | 0.016 | yes | PASS |

Information only, with no acceptance value: `refresh` took 72 s before and 48 s after (ratio 0.67). The two runs had different start states: the "before" tree had pages from an earlier refresh, and the "after" tree had none. An earlier value of 1,844 s for `refresh` of this tree came from the code of `claude/nested-step-8`, which wrote one page for each of the 50 maps. The claim index does not explain that value.

### Run 3: after the code review

The review changes: `check_coverage` and the missing-claim check use `claimed` and the index, not `covers` for each module; the kept indexes are in least-recently-used order; `line_modules` makes the word set of a line one time; `package_fact` has one implementation. Each command ran on the same tree with the code of main and of the branch. An earlier `refresh` had written the pages of this tree, so `check` reports no stale pages here and exits 0 in the two runs.

| Command | Before | After | Ratio | Same output | Result |
|---|---|---|---|---|---|
| `check` | 69.6 s | 19.0 s | 0.27 | yes | PASS |
| `judgement` | 571.9 s (run 1) | 7.8 s | 0.014 | yes | PASS |

The `check_coverage` change did not make `check` measurably faster (19.5 s, 20.3 s and 19.0 s in the three runs). The rest of the 19 s of `check` is not examined yet.

### Run 4: after the `/simplify` review

The review changes:
- One finder of module names in a line (`judgement_evidence.named_modules`) is used by `line_modules` and by `decisions._subject`. It compiles the pattern of a name with other characters (for example a path) one time for each module collection.
- `extraction.mapping_drift`, `schematic_cards._claimed_files` and `change` (the owner of each module) use the claim index, not a scan of each module.
- The tests clear the kept indexes before each test.

| Command | Before | After | Ratio | Same output | Result |
|---|---|---|---|---|---|
| `check` | 69.6 s | 9.8 s | 0.14 | yes | PASS |
| `judgement` | 571.9 s (run 1) | 6.0 s | 0.011 | yes | PASS |

Most of the 19 s of `check` in run 3 was `schematic_cards._claimed_files`, which scanned each module for each module claim of each card.
