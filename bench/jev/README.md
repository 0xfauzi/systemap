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
| mis-fold, planted next door (P<0.05) | 95% caught, 4% flagged | 93%, 1% (n=106) | asked |
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

The development set contained 80 issues from Rich, Poetry, kstrl, Mealie, and Paperless.
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
| mealie | 25 | 29.3s | 0.3s | 24 of 24 |
| rich | 8 | 5.8s | 0.0s | 1 of 7 |

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
