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

## Which accuracy gaps can be fixed without Jev? (2026-09-26)

The [full review](ACCURACY_REVIEW.md)
records the findings, source locations, priorities, proposed changes, and
acceptance checks. No production implementation changed during this review.

`accuracy_review.py` reproduces 33 targeted gaps and passes four controls.
Its acceptance criteria are in its docstring. These deliberately selected
cases test specific contracts; the fraction passing is not a map accuracy
estimate. All 376 existing tests passed.

The challenge suite grew during the review: the first run reproduced 24 gaps
with four passing controls; additional binding, snapshot, and nested-entry
cases brought that to 31 gaps; test identity added one; nested rename
handling added one. Repeated runs after formatting kept the same outcomes.
The final JSON retains all 37 cases. The census was rerun after factoring
its readers and adding source hashes; its counts did not change.

`accuracy_census.py` reads 1,381 Python files across the eight mapped
repositories. Under Python 3.11, 15 of Mealie's 460 files silently disappear
because they use Python 3.12 syntax. The same extraction under Python 3.12
reads all 460 and restores import evidence for five flows. This improves
parsed-file coverage from 96.74% to 100%, not semantic map accuracy.

`accuracy_moves.py` compares the current move rules with unique exact-content
matching on 33 saved commits and 86 Git-labelled renames. The preset bar was
fewer disagreements without losing correctly paired renames:

| method | correct pairs | Git disagreements | reference renames not correctly paired |
|---|---:|---:|---:|
| current rules | 65 | 4 | 21 |
| unique exact content | 13 | 0 | 73 |

The candidate loses 52 correct pairs, so it failed and is not shipped.
These are comparisons with Git's similarity-based labels, not independently
adjudicated semantic truth. The replay samples rename-containing commits.
The first run under Python 3.11 failed with a missing Mealie module and
produced no score. The recorded run explicitly uses Python 3.12.

Results are `results/no-jev-accuracy-review.json`,
`results/no-jev-accuracy-census.json.gz`,
`results/no-jev-accuracy-census-py312.json.gz`, and
`results/no-jev-accuracy-moves.json`. The review gives the commands.

## Implementation verification (2026-09-27)

The targeted counterexamples now pass 37/37 Python and 32/32 TypeScript
contracts. On the pinned Hono, Ky and Zod revisions, systemap retained all
1,171 compiler-resolved dependencies whose targets belong to its extracted
inventory, with zero missing and zero wrong targets. These checks do not
measure whole-map semantic accuracy. The implementation also passed 450
repository tests and every pre-commit hook.

The ownership pilot below still misses its preset false-challenge bar and
has no independently adjudicated end-to-end labels. It is not evidence for
changing the default ownership policy. New exact entry coverage and flow
review rules leave existing maps pending review until their claims are
confirmed against current source.

## Can package neighbours make the Jev-free mis-fold rule more accurate? (2026-09-26)

`heuristic_owner.py` tested one addition: flag a module when at least two
other modules in its package belong to another card and none belong to its
current card. It uses the existing owner samples and places each sampled
module in a neighbouring wrong card. The bar in the script's docstring was
at least 50% of planted errors caught and at most 3% of unchanged owners
flagged, on both development and holdout maps.

| map set | rule | planted errors caught | unchanged owners flagged |
|---|---|---:|---:|
| development | current | 61/195 | 2/195 |
| development | with package evidence | 116/195 | 21/195 |
| holdout | current | 32/96 | 1/96 |
| holdout | with package evidence | 52/96 | 23/96 |

The addition missed the false-alarm bar on both sets, so it is not shipped.
Two cards can legitimately split one package by purpose. These labels are
finished maps rather than independent checks of every module's purpose, so
they measure agreement with those maps and detection of planted mistakes.
For a Jev-free map, the skill now asks the agent to review every assignment
against the code instead of treating unflagged modules as verified.

## How well did an agent judge sampled card assignments without Jev? (2026-09-26)

The subsequent accuracy review found mixed snapshots in five systemap cases:
their source differs from the cached facts supplied alongside it. It also
found a fixed condition order: four planted cases, then four unchanged
cases, in every repository batch. The counts below remain the recorded
pilot results; these limitations need correction before an end-to-end
accuracy claim. See F23 in the full review.

In this pilot, code review found 24 more of the 32 planted mismatches than
the word rule: 32 rather than 8. It challenged one more of the 32 unchanged
assignments: 2 rather than 1. The run tests one code-reading judgement per
module, not the full mapping procedure.

`review_accuracy.py` sampled eight modules from each of the five development
and three holdout maps. Four kept their card; four were placed in another card
in the same region. One module appeared once. The reviewer was Claude Opus
5.5 with no tools or Jev: it saw the full source file, module facts, and the
descriptions of nearby cards, but no card's module list or reference owner.
The script selected files of at most 25,000 characters with a neighbouring
card, so these figures do not cover larger files or isolated cards.

The bar in the script's docstring was to catch at least 60% of planted wrong
assignments, challenge at most 5% of unchanged assignments, and beat the word
rule's planted-error recall on both sets. "Reference card chosen" counts
planted cases where the reviewer named the module's card in the finished map
as the better one. The results were:

| set | planted caught | reference card chosen | unchanged challenged | word rule caught | word rule challenged |
|---|---:|---:|---:|---:|---:|
| development | 20/20 | 19/20 | 1/20 | 5/20 | 1/20 |
| holdout | 12/12 | 12/12 | 1/12 | 3/12 | 0/12 |
| combined | 32/32 | 31/32 | 2/32 | 8/32 | 1/32 |

On planted mismatches, code review caught 100% versus the word rule's 25%,
an improvement of 75 percentage points. It named the reference card in 31
of 32 planted cases; the word rule does not name a replacement card. On
unchanged assignments, code review challenged 6.25% versus 3.125%, an
increase of 3.125 points. It therefore missed the preset 5% challenge bar.
Its binary decisions agreed with the finished maps on 62 of 64 cases
(96.9%), versus 39 of 64 (60.9%) for the word rule: 23 more agreements,
or 36 percentage points. This is agreement on a balanced synthetic sample,
not the error rate of a real map.

The two challenges name plausible placement errors: `poetry.config.source`
defines a source entry for `pyproject.toml`, while ProjectLoader explicitly
owns the project's sources; `praxis.reports.commitment_rollup` assembles the
weekly masthead payload, while Digest owns that presentation. One replacement
differs from the reference for `kstrl.tui.home_data`: the reviewer chose RunViews,
while the finished map puts the home board's data under Dashboard. These
are unresolved semantic labels, so the finished map cannot establish whether
the two challenges are false alarms or corrections. A maintainer must label
them before a stronger accuracy claim is possible.

The first kstrl call returned fenced JSON, which the scorer rejected and did
not count. The same prompt was retried, and the parser was changed to accept
the code fence without changing any judgement. The scored answers and their
prompt hashes are in `results/review-accuracy.json` and
`results/holdout/review-accuracy.json`. The eight scored calls reported $1.88;
the failed and diagnostic calls were not included in that cost.

## How can the next ownership review use one source snapshot?

`review_accuracy_v2.py` prepares a source review without calling an agent.
`freeze` copies every tracked or unignored file present in one working tree,
including uncommitted source and map files. A tracked file deleted before the
freeze remains absent. A deletion or other mutation during freezing stops the
run. Ignored source files still stop the freeze if extraction discovers them. Internal symlinks retain their targets;
external or missing targets stop the freeze. It extracts facts from that copy,
compares them with extraction from the original tree, and records SHA-256
hashes for the files, facts, extractor source, and manifest. `verify` refuses
changed, missing, or extra files and facts that refer to a different source.
It also requires the Python and systemap source versions used at freeze time.
Regenerate a snapshot after either changes; the stored facts are not
reinterpreted under new extraction code.
Invalid UTF-8 in a sampled source file stops case construction explicitly.
The freeze also compares discovered source paths with extracted records and
refuses parse errors or unresolved test files. Mealie contains Python 3.12
syntax, so freeze that repository with a compatible Python 3.12 interpreter.

```sh
uv run --project bench/jev python bench/jev/review_accuracy_v2.py freeze REPO SNAPSHOT
uv run --project bench/jev python bench/jev/review_accuracy_v2.py verify SNAPSHOT
uv run --project bench/jev python bench/jev/review_accuracy_v2.py build SNAPSHOT --out CASE_SET --seed RECORDED_SEED
```

`build` selects each nonempty module at most once for its top-map card.
`--count N` limits
the selection when a smaller packet is needed. It records the seed, excluded
empty package markers, unclaimed module count, and nested-map count. Nested
card ownership is not yet scored. An unclaimed module gets
"none of these" as its candidate, so a reviewer can label its missing owner.
Candidate assignments and case order are randomized. `label-cases.json` goes
to the independent adjudicator. It contains full source and all card
descriptions, including "none of these", but omits the candidate, reference
owner, and planted condition. `review-cases.json` goes to the answerer. It
adds the candidate while omitting the reference owner and planted condition.
Both packets carry a SHA-256 digest of `cases.json`, which holds all fields.
The adjudicator should not receive the review packet, map, or recorded pilot
answers.

An independent reviewer records one label per case in `labels.json`. The
file has `format: 1`, `case_set_sha256` (SHA-256 of canonical `cases.json`),
and a `labels` array. Each label has the case `id`, `snapshot_id`,
`source_sha256`, reviewer name, `blind_to_predictions: true`, a `status`,
and `acceptable_cards`. This is a required provenance declaration, not proof
of independence. Status is `adjudicated` for one acceptable card,
`ambiguous` for at least two, `new_card` for no existing acceptable card,
or `unresolved`. A settled label needs source evidence of the form
`{"file":"...","symbol":"...","reason":"..."}`. A new-card label
also needs `proposed_card`, a description of that card's job. The validator
checks that references resolve in the frozen source. It cannot establish
that a reviewer was independent or that a cited symbol supports the label.

The isolated reviewer writes `answers.json` with the same `format` and
`case_set_sha256`. Each answer has `id`, `snapshot_id`, `candidate`,
`decision` (`fits`, `wrong`, or `abstain`), and `better_card` (a listed card,
"none of these", or null). `score` refuses missing answers or labels. It
reports true errors detected, incorrect confident claims, abstentions,
ambiguous labels, and unresolved labels separately by repository.

```sh
uv run --project bench/jev python bench/jev/review_accuracy_v2.py score CASE_SET/cases.json labels.json answers.json
```

A full mapping run uses a separate input directory created by
`prepare-workflow`. The frozen reference tree remains available to the scorer,
but the mapping agent receives only the prepared input tree. Its whitelist
contains every extracted component source and source in the configured test
directories or matching configured test patterns. Map directories and rendered
output directories cannot enter the whitelist, even if configured as source.
Facts, reference maps, documentation, and case packets are not copied.

`source-config.json` describes the language, source roots, test settings, and
selected Python package metadata. It omits map claims and recorded judgement
answers from the original configuration. For TypeScript, supply each needed
`package.json` or `tsconfig*.json` explicitly with `--config PATH`. Relative
paths are preserved. The command rejects configurations under reference map or
rendered output directories. Review the selected configuration files before
exposing them to the agent. Other configuration names are refused.

```sh
uv run --project bench/jev python bench/jev/review_accuracy_v2.py prepare-workflow SNAPSHOT WORKFLOW_INPUT --config tsconfig.json --config package.json
```

The command prints the SHA-256 digest of the input manifest. The manifest lists
every admitted file and binds those bytes to the frozen snapshot. Run the agent
in a separate working copy of `WORKFLOW_INPUT/tree`; retain the prepared input
unchanged for validation. Restrict the external run's filesystem access to its
working copy. The validator proves which input bytes were supplied; it cannot
prove that an external agent never read another directory or service.

Save the exact instructions beside `run.json`. Record `workflow_input`, the
prepared directory's path relative to `run.json`, and `workflow_input_sha256`,
the digest printed by preparation. Record the relative `instructions_file`
path and SHA-256 digest, plus `snapshot_id`,
agent identity, a `cards` object from card ID to job, and an `owners` object with
every extracted nonempty module as a key. Use null for an omitted owner.
Include `flows`, `journeys`, `invariants`, and `unresolved_claims` arrays.
`validate-workflow` checks the input whitelist, every input file hash, and the
complete reported inventory. Changed, added, missing, or unbound input is refused. A separate reviewer then
aligns each workflow card with a reference card before ownership is scored.
This prevents a renamed card from being treated as a different job solely
because its ID changed. The reviewer writes `alignment.json` with `format: 1`,
the run's `snapshot_id`, `run_sha256` (SHA-256 of canonical `run.json`), and
one `alignments` row per workflow card. Each row has `card`, `status`,
`reference_card`, `reviewer`, `blind_to_scores: true`, and `evidence`. An
`existing` status names one reference card. A `new` or `ambiguous` status has
null `reference_card`. The reviewer must inspect the card's job and source;
matching IDs alone do not establish equivalent jobs. The validator checks
the declared provenance and run binding, not the semantic judgement.

`score-workflow` compares aligned owners with independently adjudicated case
labels. It counts corrections of reference-map errors, wrong confident owners,
and omissions. When a module needs a new card, an owner aligned to an existing
rejected card is counted wrong. An owner aligned as new stays unscored until
the new card is reviewed for that module. Ambiguous card alignments also stay
unscored. Flow, journey, and invariant claims need separate labels.

```sh
uv run --project bench/jev python bench/jev/review_accuracy_v2.py validate-workflow SNAPSHOT run.json
uv run --project bench/jev python bench/jev/review_accuracy_v2.py score-workflow SNAPSHOT CASE_SET/cases.json labels.json run.json alignment.json
```

The recorded pilot remains unchanged and missed its preset false-challenge
bar. The v2 harness has no semantic result yet. An independent source review,
actual paired workflow runs on frozen trees, and a fresh holdout are still
needed. The prior holdout maps have been examined. Before a new run, record
its acceptance rule and sample plan. Do not transfer the isolated pilot's
60% and 5% thresholds to a different task without a new justification.

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

## Which repositories are held out, and why?

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

## What did tests 7 and 8 measure?

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

## Does Jev make the first map cheaper? (turns.py, draft.py)

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

## What can the structure decide about a journey? (2026-09-20)

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
chain: a walk fans out into a sub-call and returns to the card that
started it, and that reads perfectly while its edges do not join. Continuity
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

## What does the map's graph add to the imports? (2026-09-20)

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

## How well does a plan project onto the map? (2026-09-20)

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
thresholds held to), and the holdout is one repository, so what this
supports is that the projection is better on some systems than others. It names two
cards; a maintainer can check two cards.

## What does a year of the system look like in today's cards? (2026-09-20)

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

Both finish well inside the time allowed, because the facts at a commit
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

rich barely changed in a year: one window moved, and it was the unicode width
tables being regenerated. Printing almost nothing for a year in which almost
nothing happened is the right answer.

## Can Jev say what changed for the people using it? (2026-09-20)

The plan was a section in `delta`'s pull-request comment: for each journey
step through a card the change touched, whether the step's sentence still
holds, and an agent's rewrite of the ones that do not. It is not built, and
now there is a measurement rather than an argument.

**The set.** Fifteen journey steps from the bench maps, taken from the real
situation the feature is for: a map drawn on 2026-08-23/26, and the code at
each repository's origin on 2026-09-20. A step qualified when the files
behind the two cards its edge joins had moved by at least twenty lines; the
largest few per repository were kept, at most four each. kstrl, paperless,
mealie and poetry contributed; rich and httpie contributed nothing, because
nothing behind their steps changed. `bench/jev/label_set.py` builds it into
`data/label-drift-cases.json`.

**The labels.** Written by reading the code at both commits, not by reading
the diff excerpt: fifteen of fifteen sentences still hold. Each label carries
the reason in the file. Examples: paperless deleted a 610-line query
translation module, and "Tantivy returns ranked hits with the matching text
highlighted" is still exactly what the backend does; mealie removed 194 lines
from the recipe repository, and they were `find_suggested_recipes`, while the
group and household stamping the step names is untouched; kstrl added 3,584
lines to its verifier, and `run_mechanical_verification` still says "All
checks run even if earlier ones fail".

That is the first finding, and it is about journeys rather than about Jev: a
step sentence is written at the level of roles ("the controller hands the
address to the scraper"), and a month of real change underneath does not
reach that level. The labels are the author's, not a maintainer's, so the
figure is 15 of 15 as read by a model that looked at the code.

**What Jev said.** Asked the same question about the same fifteen, with the
step, both cards, the commit subjects, the file list and the capped diff:

    uv run --project bench/jev python bench/jev/drift_steps.py

| where delta would draw the line | steps it would report | how many would be wrong |
|---|---|---|
| below 0.5 | 2 of 15 | 2 |
| below 0.6 | 6 of 15 | 6 |
| below 0.7 | 12 of 15 | 12 |
| below 0.8 | 15 of 15 | 15 |

Jev's answers run from 0.43 to 0.75. No answer is confident either way, and
because every case is a negative, every alarm at every threshold is a false
one. There is no threshold that buys a reader anything here: the cautious end
reports two wrong lines per fifteen steps, and the generous end reports
twelve.

**So it is not built.** A pull-request comment that says "this is what
changed for the people using it" would, on this month's evidence, have printed
four false lines to four maintainers and not one correct one. Two caveats, because both
would have to be answered before anyone tries again: the diff Jev sees is
capped, and a fuller or better-selected diff might sharpen it; and a set with
no positives in it measures false alarms only, so nothing here says whether
real drift would be caught. What it does say is that real drift is rare
enough that the question may not be worth asking per pull request.

## What do the measurements suggest next? (2026-09-20)

Three things in this directory came back with numbers that point at work worth
doing. Each is written here with the bar it has to clear, before anyone starts,
so the decision is the same shape as the ones above.

### 1. The cards one flow from a change, chosen for precision

The ripple run failed a bar about recall, but it measured something else on the
way. Over the same 366 pull requests, medians:

| rule | cards named | share of the map | precision |
|---|---|---|---|
| one hop either way over the flows | 5 | 0.14 | 0.17 |
| every module the imports reach | 20 | 0.57 | 0.05 |

The map's edges name a quarter as many cards and are three times as likely to
name one the change actually touched. That is a poor prediction and a good
short list, which is a different feature: `delta` would print "these cards sit
next to what you changed", as context beside the lines it already prints, never
as a claim about what else broke.

**The bar, before the work:** on the same 366 pull requests, the list must name
at most 6 cards at the median, and must contain at least one card the pull
request really touched in 50% of them or more. Below either, nothing ships, and
the rule joins the two above it. Cost: the dataset exists; a run and a reading.

**Measured (2026-09-20, `bench/jev/near.py`): passed, and built.** The rule as
measured seeds from the card holding the file with the most changed lines: 5
cards at the median, a hit in 70%. `delta` reads the facts at two commits and
not the diff, so it cannot count lines; it seeds from the card holding the most
changed modules instead, and that was measured too, over the 359 pull requests
where it applies:

| what would be printed | cards (median) | ninetieth | holds a touched card |
|---|---|---|---|
| one hop from the seed card | 6 | 14 | 0.72 |
| one hop from every changed card | 14 | 21 | not scored: every touched card is a seed |
| every module that card imports | 20 | 32 | 0.77 |

The union of every changed card's neighbours is the obvious shape and it is the
one not built: fourteen cards at the median is not a short list. The imports
find five points more at three times the length, which is the same result the
ripple run got, and the reason this ships as context rather than as a claim
about what else broke.

Fourteen cards at the ninetieth percentile is still too long, and the cause is
a card joined by flows to most of the map: the cards one flow from it are
almost the whole map, which tells a reader nothing. `delta`
prints nothing when the seed is joined to more than a third of the cards, which
is the threshold the skill already uses for running the full loop rather than
acting line by line. That prints nothing for 18% of the pull requests; the rest hold 5
cards at the median and 8 at the ninetieth, and the hit falls 3 points to 0.69.

### 2. Where the system is growing

`history` proved its windows trace to real work (five of the five largest named
the commit that caused them). The same walk, summed over a year rather than
read per window, answers a question a maintainer asks out loud. On mealie:

    ImportWorkflow +17   SchemaMigrations +7   QueryFilter +4   Translations +3

and not one card shrank in twelve months. A card that grows every quarter and
never loses a module is either the part everything else is built on, or the
part modules land in when nobody decided where they belong. The map is the
only thing that can tell a reader which.

**The bar, before the work:** on four repositories, the three fastest-growing
cards must each trace to at least one commit a person can name as a feature,
on at least three of the four. `systemap history --by-card` is an aggregation
of numbers `trend.walk` already computes, so the cost is small.

**Measured (2026-09-20, `bench/jev/by_card.py`): failed, and not built.** Two
of the four repositories passed, where the bar asked for three.

| repo | the three fastest-growing cards | traces to |
|---|---|---|
| mealie | ImportWorkflow +17, SchemaMigrations +7, QueryFilter +4 | all three: "feat: Unified AI recipe page", "feat: Announcements", "feat: Query relative dates" |
| paperless | AppConfig +11, SearchIndex +7, FileParsers +5 | all three: "support ollama embeddings", "Replace Whoosh with tantivy search backend", "Initial document parser plugin framework" |
| poetry | HttpAccess +1, and no other card grew at all | one perf commit, and nothing to rank |
| rich | Measure +23, and no other card grew | one commit titled "f string path", which names nothing |

Where a system grew, the aggregate named the work that grew it, exactly as the
windows did. Where it did not grow, there was nothing to name: poetry gained
one module in a year of the map's view, and rich's twenty-three are generated
unicode tables added in a commit whose subject is three words that name
nothing.

A rule that reported only cards past some size would pass, and that rule was
not the one written down before the run, so it is not the one being judged.
The finding this leaves is smaller and worth keeping: on the two repositories
that did grow, every one of the three cards traced to named work, which is what
`history`'s windows already print. The aggregate restates what the windows say
and adds no answer of its own.

The instrument was changed once during the run, before any judging: it first
showed the newest commits touching each card's new files, which over a year
lists the fixes made to a file rather than the commit that added it.
`--diff-filter=A` asks for
the commit that added each file instead. Both readings are in the git history
of `by_card.py`.

### 3. A journey per crowd, not per way in

Finding the ways a framework registers took paperless-ngx from 0 to 203 and
mealie to 195, against four written journeys each. `judgement` already groups
them: one line per card once a card takes four or more of a kind. `systemap
journeys` does not: it writes one walk per way in, three to a run, which would
take sixty runs to cover paperless.

**The bar, before the work:** for the crowded cards of mealie and paperless,
a generated walk per group must pass the map's own check (every step tracing a
flow the model draws) in 70% of attempts or more, and the ways in with no walk
must fall from about two hundred to under fifteen lines. This one costs agent
runs, so it is the most expensive of the three and the last to start.

**Measured (2026-09-20, `bench/jev/group_journeys.py`): passed, and built.**
Eight of nine crowds over mealie, paperless-ngx and poetry came back as a walk
the map can hold, which is 89% against a bar of 70%. On the two repositories
the bar names, four of five. The one refusal was a step tracing MediaFiles ->
Assets, a flow mealie's map does not draw, which is the check doing its job:
it was printed as a line to fix and nothing was written.

| repo | ways in in crowds | crowds | walks the map can hold |
|---|---|---|---|
| mealie | 195 | 2 | 1 |
| paperless | 86 | 3 | 3 |
| poetry | 27 | 4 | 4 |

The second half of the bar was already true before the work and the bar was
wrong to ask for it: `judgement` has grouped crowds since the entry-point work,
so mealie's 195 open ways in print as 2 lines and paperless's 98 as 15. What
was not true is that a walk could be written per line. `systemap journeys`
wrote one per way in, three to a run, so covering mealie meant sixty-five runs.
It now writes one per crowd: two runs for mealie, three for paperless.

A crowd's walk records the card in `starts` rather than one of the hundred
routes, because a walk standing for all of them cannot name one without
claiming to be about that one, and `judgement` reads a card there as covering
every way in that card claims.

An earlier run of this script scored 19 of 19, and that number is not the one
above. It asked about single ways in as well as crowds, and it carried its own
copy of the question rather than the one `journeys` sends. Both were corrected:
the script now calls `journeys.gather`, `journeys.context` and
`journeys.read_answer`, so what is measured is the code that runs.

What this does not measure is whether a walk is true of the code. Every one of
the eight is a journey the map can hold, and holding is a low bar: read as
sequences, they fan out rather than joining up (of seven consecutive pairs, two
to four start where the one before ended), and two answered with nine steps
where the question asked for four to eight. Nothing checks either, because the
continuity rules that were tried flagged thirty steps and a hand review found
none of them real (`src/systemap/graph.py` records that). A generated walk is
written `drafted=True` and prints as a `drafted journey` line until a person
reads it, which is the standard the per-way-in walks already ship under.

### Not on this list

`plan --check` in the pull-request workflow, because the claim worth testing
(work that lands outside its plan predicts a later fix) needs fix pull requests,
and the whole corpus of five repositories holds six of them. It cannot be
measured, so it is not scheduled.

## Does Python syntax evidence survive a supported interpreter change?

On 2026-10-02, the portability experiment compared the same 45 systemap
source modules under Python 3.11 and 3.13. The acceptance rule was recorded
before execution: zero canonical syntax hash mismatches between interpreters,
zero changes to existing Python 3.11 hashes, unchanged hashes after comments
or formatting edits, and a changed hash after a function body edit on each
interpreter.

The original syntax hashes differed for all 45 modules. The canonical hashes
differed for zero modules, and zero existing Python 3.11 hashes changed.
Formatting and comment edits produced zero mismatches on either interpreter.
Each interpreter detected the body edit. The experiment checks syntax hash
portability for this source set and these transformations. It does not establish
that every future Python grammar change preserves the representation.
`syntax_portability.py` records the acceptance rule and prints hashes and
control results for comparison across repeated runs. From the repository root:

```sh
uv run --python 3.11 python bench/jev/syntax_portability.py > /tmp/syntax-311.json
uv run --python 3.13 python bench/jev/syntax_portability.py > /tmp/syntax-313.json
```
