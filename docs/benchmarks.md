# Benchmarks

`bench/table.py` writes this document from `bench/results.jsonl`.
Do not edit the generated document. Change the generator instead.
Each repository and mode has one row for its latest run.

`bench/run.sh` executes the documented headless procedure.
The session's result event gives the model, turns, minutes, and dollars.
After the session, the harness executes `systemap check` and
`systemap judgement --strict`. Their results use the `check` and `judgement`
columns. The `run` column shows whether the session completed without
intervention or stopped at its limit. The `skill first` column shows whether
the first tool call used the systemap skill. The procedure specifies this first
call.

The experiment recorded two acceptance limits before implementation:

- A first map must cost no more than 0.15 dollars per module.
- Maintenance on a medium pull request must use no more than 15 turns and
 2 dollars.

Four of the six first maps cost less than 0.15 dollars per module.
The other two cost 0.159 and 0.177.
The maintenance runs cost 2.31, 4.39, and 2.50 dollars.
They used 51, 63, and 46 turns.
All three exceeded both maintenance limits.

The 15-turn limit used an incorrect two-step assumption.
The maintenance procedure executes delta, refresh, check, and judgement.
The experiment did not change either limit after the results.

The maintenance runs used the reverse comparison direction.
Each run reverted a merged pull request but kept the map unchanged.
Thus, the map contained claims for removed code structure.
The report used the identifiers `entry vanished`, `interface vanished`, and
`evidence lost`.

The workflow from `init` uses the forward direction, from the pull-request base
to its head. That comparison can print `new crossing import`.
The test suite includes both directions.
The table's turns and dollars are from the reverse runs.


| repository | mode | modules | systemap | model | turns | minutes | dollars | dollars per module | check | judgement | run | skill first | date |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a 144-module service (private) | first-map | 144 | 0.8.0 | claude-opus-5[1m] | 155 | 31.9 | 25.49 | 0.177 | clean | clean | finished | yes | 2026-08-26 |
| https://github.com/0xfauzi/kstrl | first-map | 111 | 0.9.0 | claude-opus-5[1m] | 112 | 34.1 | 17.61 | 0.159 | clean | clean | finished | yes | 2026-08-26 |
| https://github.com/0xfauzi/kstrl | maintenance, small (PR 237, 8 files) | 111 | 0.11.0 | claude-opus-5[1m] | 51 | 6.4 | 2.31 | - | clean | clean | finished | yes | 2026-08-26 |
| https://github.com/0xfauzi/kstrl | maintenance, medium (PR 213, 17 files) | 111 | 0.11.0 | claude-opus-5[1m] | 63 | 11.3 | 4.39 | - | clean | clean | finished | yes | 2026-08-26 |
| https://github.com/0xfauzi/kstrl | maintenance, large (PR 184, 20 files) | 111 | 0.11.0 | claude-opus-5[1m] | 46 | 5.8 | 2.5 | - | clean | clean | finished | yes | 2026-08-26 |
| https://github.com/Textualize/rich | first-map | 103 | 0.9.0 | claude-opus-5[1m] | 118 | 26.7 | 14.37 | 0.14 | clean | clean | finished | yes | 2026-08-26 |
| https://github.com/httpie/cli | first-map | 78 | 1.1.0 | claude-opus-5[1m] | 46 | 4.8 | 3.43 | 0.044 | clean | clean | finished | yes | 2026-09-19 |
| https://github.com/httpie/cli | first-map-jev | 78 | 1.1.0 | claude-opus-5[1m] | 54 | 5.5 | 3.61 | 0.046 | clean | clean | finished | yes | 2026-09-19 |
| https://github.com/mealie-recipes/mealie | first-map | 460 | 0.11.0 | claude-opus-5[1m] | 167 | 32.9 | 23.76 | 0.052 | clean | clean | finished | yes | 2026-08-26 |
| https://github.com/paperless-ngx/paperless-ngx | first-map | 341 | 0.9.0 | claude-opus-5[1m] | 151 | 36 | 24.24 | 0.071 | clean | clean | finished | yes | 2026-08-26 |
| https://github.com/python-poetry/poetry | first-map | 192 | 0.9.0 | claude-opus-5[1m] | 174 | 35.9 | 20.82 | 0.108 | clean | clean | finished | yes | 2026-08-26 |
