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
