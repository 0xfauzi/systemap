# Jev experiments

What TypeSafe's Jev model can and cannot judge about a systemap map, measured
against the five first maps in `bench/scratch` and against git and GitHub
history. `systemap audit` and `systemap route` exist because of the numbers
here, and their thresholds come from `score.py`'s curves.

    uv run --project bench/jev python bench/jev/build.py      # labelled rows -> data/ (no API calls; build_flows.py, build_meaning.py hold the rest)
    uv run --project bench/jev python bench/jev/run.py        # every row once -> results/*.jsonl.gz
    uv run --project bench/jev python bench/jev/score.py      # metrics, with today's heuristic beside each
    uv run --project bench/jev python bench/jev/moves.py build|score

`run.py` needs `TYPESAFE_API_KEY`, skips rows already answered and never
replaces a failed call with a guess. `data/` is rebuilt from `bench/scratch`
(gitignored, written by `bench/run.sh`) and is not committed; `results/` is,
gzipped, with `results/report.txt` the scorer's output at the time.

Each experiment, its label source and what it measures:

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

## The holdout set

`JEV_SET=holdout` builds, runs and scores on maps no threshold was chosen
on: systemap's own map, scorecard (`../scorecard`), and the newest finished
`bench/run.sh https://github.com/httpie/cli first-map` run. Data and
results go to `holdout/` under `data/` and `results/`, and the scorer prints
each experiment at the threshold `systemap audit` ships with:

    JEV_SET=holdout uv run --project bench/jev python bench/jev/build.py owner sentence flowverify governs issues
    JEV_SET=holdout uv run --project bench/jev python bench/jev/run.py owner sentence flowverify governs issues
    JEV_SET=holdout uv run --project bench/jev python bench/jev/score.py owner sentence flowverify governs issues

The bar, set before the run: within 10 points of the development figure, or
the kind is not asked by default. `results/holdout/report.txt` has the output:

| kind, at the shipped threshold | development | holdout | verdict |
|---|---|---|---|
| mis-fold, planted next door (P<0.05) | 95% caught, 4% flagged | 93%, 1% (n=106) | asked |
| owner (confidence >= 0.9) | 56% answered, 98% right | 60%, 100% | asked |
| sentence (P<0.2) | 67% caught, 1% flagged | 61%, 2% (44 wrong) | asked |
| flow (P<0.2) | 66% caught, 2% flagged | 54%, 4% (48 wrong) | only with `--kind "jev flow"` |
| governs (P>=0.8) | 31% found, 1% suggested | 38%, 1% (58 governed) | asked |
| issues, top-1 (`triage`) | 80% | 79% (39 httpie issues) | shipped |

Test 9's follow-up ran as `bench/run.sh <repo> first-map-jev`, the first map
told to group with `suggest --jev`: on httpie 3.2.4 it took 54 turns, $3.61
and 5.5 minutes against 46, $3.43 and 4.8 for the plain first map, one run
each (`bench/results.jsonl`). No saving was measured, so `suggest --jev`
stays opt-in and out of the recipe.

## Tests 7 and 8 on agent labels

The maintainer chose not to hand-label. Each set was labelled once by a
Claude subagent reading the full commits in git, blind to Jev's answers
(`results/labels/agent-*.json`, with a reason per item; scores in
`results/labels/report.txt`).

- Test 8, moves (20 successors, 12 unrelated): a factual question, checkable
  in git, so the agent's labels are taken as the truth. Delta then Jev at
  P>=0.8 finds 82 renames against delta's 66; Jev's 17 additions are 16 right
  (94%). Pass: +8 at 90% or better. **Passed.**
- Test 7, drift (12 stale, 48 hold): a judgement, where a model labelling a
  model's answers measures agreement rather than truth. AUC 0.957; at
  P(holds)<0.4, 75% of stale sentences caught and 0.4 false alarms per 10
  cards. It would pass the bar, but **it is not a measurement**: drift
  detection stays unbuilt until about 15 human labels confirm the agent's.

## Jev in the first map (turns.py, draft.py)

Could Jev assign modules to cards during the first map, with the agent
writing only the cards? Two measurements on the six first maps in
bench/scratch, before building anything (`results/draft/`):

- `turns.py`: where the tool calls go. The first write of the model
  already claimed every module in all six runs (no `unmapped:` line at the
  first check), and later edits touching `implemented_by` were 1% of the
  calls. Reading and planning were 31%, reading after the draft 32%, the
  check and judgement loop 25%. Assigning modules is not where a first map
  spends its turns.
- `draft.py`: the owner question asked over each run's first loadable
  draft's cards, for every module, scored against the finished map. 1% of
  modules changed card between the draft and the finished map, so the
  agent's draft agrees with the finished map on 99%; Jev agrees on 87%, and
  on 98% of the 63% it is confident about. The finished map is the agent's
  own, so this is agreement, not truth; of the 22 confident disagreements,
  most are cards the agent split in the draft and merged later, and a few
  read like real mis-folds (mealie's `auth_cache` under HttpApi).

Verdict: nothing to save in assigning modules, and no evidence Jev would
assign them better than the agent's draft, so it was not built and the
first-map benchmark was not run. `audit`'s mis-fold line already asks the
question that finds the few real mis-folds.

## Journeys: what the structure can and cannot decide (2026-09-20)

Two questions about journeys were measured on the seven maps (the six in
`bench/scratch` and systemap's own) before anything shipped.

**Finding the ways in.** `systemap.ways_in` reads routes, commands, tasks
and plugin hooks out of the syntax tree. Ways in found, before and after:

| map | before | after | what the new ones are |
|---|---|---|---|
| paperless-ngx | 0 | 98 | 59 Django routes, 22 Celery tasks, 17 management commands |
| poetry | 3 | 44 | 41 cleo commands |
| mealie | 8 | 203 | 195 FastAPI routes |
| kstrl | 7 | 38 | 31 click commands |
| rich | 6 | 6 | none; its `@group()` is not a command |
| httpie, systemap | 5, 19 | 5, 19 | neither uses a framework this reads |

A hand-checked sample of 30 of the new records was 29 real and 1 wrong
(rich's `@group()`, which is why a command decorator must now be called on
something). The bar was 90%.

**Judging whether a journey holds together: nothing shipped.** Three rules
were written for "does step k carry on from step k-1", and each was measured
on the same seven maps:

| rule | steps flagged | real, by hand review |
|---|---|---|
| the edges join | 30 | 0 |
| the actors acted the step before | 46 | not reviewed; worse by inspection |
| the actors appeared anywhere earlier | 27 | not reviewed; the same shapes |

The bar was 80% real. A journey is written as a sequence of scenes, not one
chain: a walk fans out into a sub-call and returns to the card that has been
driving it, and that reads perfectly while its edges do not join. Continuity
is not something the structure can decide, so no `journey gap` line exists.
What did ship is `journey start`: a journey names the way in it starts at,
and the line says when the facts have no such way in. That one is exact.

**Proposing the walk from the imports: not shipped (paths.py, propose.py).**
Before `systemap journeys` asked an agent to read the code, the walk was
proposed from the facts alone: follow the imports out of the way in, map each
module to the card that claims it, and keep the card-to-card hops the map
draws a flow for. The bar, set before the run: the proposed cards had to
overlap the cards of a hand-written journey by a median of 0.60.

    uv run --project bench/jev python bench/jev/paths.py

| maps | journeys matched to a way in | median overlap |
|---|---|---|
| systemap and the six first maps | 16 | 0.28 |

Far below the bar, and the reason is structural: the module behind a console
script imports the whole system, so the proposal names almost every card and
the journey names four. Reading the entry function's own imports instead of
the module's did not help, because a command line dispatches through a table.
The proposal is not shipped. `bench/jev/propose.py` keeps the code and
`paths.py` scores it. `systemap journeys` asks the agent to read the code
from the way in, and checks every step it answers with against the map.

## Ripple: what the map's graph adds to the imports (2026-09-20)

`systemap ripple` would answer "you changed these cards, which others does
this reach". It is not built, because the walk did not beat what systemap can
already say from imports alone.

**The truth had to change first.** The plan was to pair a pull request with
the pull request that fixed it within thirty days. Over 2,406 merged pull
requests across rich, poetry, mealie, paperless-ngx and httpie, a rule strict
enough to exclude release rollups (the later one says fixes, reverts,
regression or broken by, names at most three pull requests, and both touch
Python) found **6 such pairs**. A ten point difference cannot be seen in six
cases, so the truth used is co-change: from the card holding the file a pull
request changed most, which other cards of that same pull request does the
rule find? 366 pull requests over six maps qualified.

    uv run --project bench/jev python bench/jev/ripple.py

| rule | recall | precision | cards named | share of the map |
|---|---|---|---|---|
| the cards the flows leave to, one hop | 0.00 | 0.00 | 2 | 0.06 |
| the same, three hops | 0.50 | 0.07 | 13 | 0.37 |
| the cards a flow joins either way, one hop | 0.50 | 0.17 | 5 | 0.14 |
| the same, two hops | 1.00 | 0.09 | 19 | 0.54 |
| one hop either way, plus the journeys through the card | 0.67 | 0.11 | 10 | 0.29 |
| every module the imports reach, as cards | 1.00 | 0.05 | 20 | 0.57 |

Medians, on maps holding 35 cards at the median.

The bar, stated before the run: recall within 10 points of the import
closure, at no more than half its size. **Nothing passed.** Two hops either
way matches the imports' recall but is 95% of their size; one hop is a
quarter of the size but half the recall; adding the journeys through the card
reaches 0.67 at half the size, still 33 points behind.

What the table also shows is that the baseline wins its recall by naming 20
of 35 cards: 57% of the map, at 0.05 precision. The one-hop walk is three
times more precise at a quarter of the size. That is an argument about what
the right question is, not a pass, and the bar was set before the run, so
ripple does not ship. Anything built here later needs a question a reader
would act on and a bar set before it is measured.

## A plan projected onto the map (2026-09-20)

`systemap plan` asks one question: given this task in the maintainer's own
words, which card will the work most likely have to change? The truth is the
issue set built for triage: a real bug report, and the cards the pull request
that fixed it touched (`data/issues.jsonl`, `label.owners`). The input is the
report alone, written before anyone did the work, which is what a plan is.

The bar, set before the run: cover 70% of the cards the fix touched, with at
most 2 extra cards per issue. Jev's answer is a weight on every card, so the
whole curve is scored offline from the answers already recorded for triage.

    uv run --project bench/jev python bench/jev/plan_eval.py
    JEV_SET=holdout uv run --project bench/jev python bench/jev/plan_eval.py

| cut | covered (dev) | extra | covered (holdout) | extra |
|---|---|---|---|---|
| 0.50 | 0.69 | 0.16 | 0.46 | 0.13 |
| 0.30 | 0.79 | 0.26 | 0.58 | 0.33 |
| 0.20 | 0.82 | 0.42 | 0.63 | 0.36 |
| 0.10 | 0.86 | 0.69 | 0.66 | 0.59 |
| **0.05** | **0.86** | **1.15** | **0.71** | **0.90** |
| 0.02 | 0.88 | 1.91 | 0.74 | 1.31 |

80 issues on the development set (rich, poetry, kstrl, mealie, paperless),
39 on the holdout (httpie). The cut that passes the bar on both is 0.05, and
that is the one `systemap plan` ships with: it names 2.1 cards per task on
either set. The gap between the two sets is wider here than elsewhere in this
directory (15 points at the shipped cut against the 10 points the audit
thresholds held to), and the holdout is one repository, so the honest reading
is that the projection is better on some systems than others. It names two
cards; a maintainer can check two cards.

## A year of the system, read in today's cards (2026-09-20)

`systemap history` samples the tree back through time and says what moved.
Two bars, set before it was built: 26 samples over a year of mealie must
take at most five minutes with the facts cached, and of the five largest
windows at least three must name a change a person can find in that window's
commits.

    uv run --project bench/jev python bench/jev/history_eval.py --repo mealie

| repository | samples | cold | warm | windows that moved |
|---|---|---|---|---|
| mealie | 25 | 29.3s | 0.3s | 24 of 24 |
| rich | 8 | 5.8s | 0.0s | 1 of 7 |

Both pass the time bar with room to spare, because the facts at a commit
never change and are cached under `.systemap/facts/`.

The five largest mealie windows, and the commit each led back to:

| what the trend said | the work behind it |
|---|---|
| ImportWorkflow +17 modules, 5 new crossing imports | feat: Unified AI recipe page (#8043) |
| ways in +7, AiService -> Repositories | feat: In-app AI Provider Configuration (#7650) |
| IngredientParser +1, four crossings into Translations | feat: Unit standardization / conversion (#7121) |
| QueryFilter +4 | feat: Query relative dates (#6984) |
| Translations +3 | feat: Customize Ingredient Plural Handling (#7057) |

Five of five, against a bar of three. What made this checkable was naming
the commits that wrote the modules which appeared, rather than the commits
of the window: a fortnight of mealie is mostly dependency bumps, and a trend
read against those looks like noise whether it is real or not. `systemap
history` prints those same commits under each window for the same reason.

rich's year is quiet: one window moved, and it was the unicode width tables
being regenerated. A quiet year printing almost nothing is the right answer.

## What changed for the people using it: not built (2026-09-20)

The plan was a section in `delta`'s pull-request comment: for each journey
step through a card the change touched, whether the step's sentence still
holds, and an agent's rewrite of the ones that do not. It is not built, and
the reason is that its gate cannot be met honestly.

The drift question was measured once already (test 7, `drift.jsonl`): asked
whether a card's `does` still described it after a diff, Jev scored AUC 0.957
against labels written by a coding agent. That is agreement between two
models, not truth, and the maintainer declined to label the set by hand.

The proxy the plan allowed was a planted test: swap a step's sentence with
another step's and see whether the answer flips. Measured or not, it answers
a different question. It would show that Jev can tell a step's own sentence
from a foreign one given the code, which is close to the `jev sentence`
check that already ships. It would not show that Jev notices when a real
change makes a true sentence false, which is the whole claim of the feature.

So nothing ships. A section that tells a reader "this is what changed for
your users" has to be right more often than not, and there is currently no
measurement that says whether it would be. About fifteen hand-labelled
examples, drawn from real pull requests, would settle it.
