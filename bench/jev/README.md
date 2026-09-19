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
