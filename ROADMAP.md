# The road to 1.0

systemap 0.7 works end to end on one repository it did not write. That is a
beta. This document says what "a fully working product" means, names every
gap between here and there, and gives each gap a mechanism, an acceptance
number stated before the work starts, and the measurement that decides it.
Where a number below is a target, it says so; the README will carry the
measured value, whichever way it falls.

Two things are out of scope by decision, not by neglect. systemap reads
Python and only Python; the README says so and no other language is
planned. And the map is documentation: it is not fed to a coding agent as
context for its next change.

## What 1.0 means

1. One command installs it from PyPI on macOS, Linux and Windows, and the
   workflow `init` writes passes in a consumer's CI.
2. A first map of any Python repository up to 400 modules completes
   unattended, check clean, inside a stated cost.
3. The map stays true through ordinary changes at a stated cost per pull
   request, without redrawing it.
4. Every edge says whether the code backs it.
5. It has been run, unattended, on repositories we did not write, by the
   documented path, and finished.
6. The page works in both colour schemes, from the keyboard, and at the
   sizes it claims.

## The gaps, each with its plan

### 1. Layout is hand-placed: the cost driver and the scale limit

What is wrong: the agent places every card by hand and learns the corridor
rule by trial. In the second headless run about a third of the turns went
on layout before the first check. Hand placement also stops working near
sixty cards.

Mechanism: `systemap place`. A deterministic first placement, stdlib only:
regions on a 2xN grid with the corridors the layout reference already
specifies; cards in a region ordered by a few barycentre sweeps over their
edges so the parts that talk sit together; positions written into the
model as the starting values. A component with no `x`, `y` is placed by
the tool; a component with them is pinned and left alone. `init` and the
skill's draft step run `place` so the first check starts from a drawable
map. `describe` reports which cards are placed and which are pinned. The
check does not change: it still decides.

Acceptance, stated now:
- On the anonymised 144-module fixture with every position stripped,
  `place` produces a map whose check is clean with zero manual moves, in
  under ten seconds. Landed in 0.8.0 and measured: the geometry check
  (placement, routes, labels, type size, wheels) is clean with no manual
  move, and `place` takes about a millisecond; the test asserts the
  ten-second bound. On the self-map, `place` cut the bends from 113 to
  92 and the total edge length from 25609 to 18900 units against the
  hand layout, so the self-map now carries its positions.
- On a fresh headless run of the same repository, the number of
  `systemap check` and `systemap refresh` invocations across the run falls
  to at most half of run 3's. Baseline, read from run 3's session log on
  2026-08-26: 22 invocations in 101 turns. Target: at most 11.
  Measured on run 4 (2026-08-26, systemap 0.8.0, the same repository):
  21. Missed. Two more measures, read from both session logs with one
  parser, say why the mechanism did not move the number:
  - calls (place, check or refresh) to the first clean layout: run 3 =
    2, run 4 = 3; layout refusals before it: 1 and 1.
  - work between the first write of map/model.py and the first clean
    layout: run 3 = 6 tool uses over 8 assistant turns; run 4 = 5 over
    7.
  - whole run: run 3 = 168 assistant turns, 17.30 dollars; run 4 = 232
    turns, 25.49 dollars; the same model (claude-opus-5[1m]) and
    repository.

  Reading: by run 3 the layout reference (0.6) had already made hand
  placement cheap on this repository, so `place` had little left to
  remove there; its value is on a first draft with no positions and on
  relayout, which 0.8.0 could not do (after the first place every card
  had a position, so a card added later found no free slot and the only
  fix was a hand edit). Run 4 cost more than run 3, with the extra turns
  spent on the facts views and on relayout by hand; 0.10.1 changes both
  (`place --all`, the rendered facts views). The target above is kept
  as written and stands missed; the acceptance for `place` is restated
  as a claim it can meet:
- On a first draft with no positions, `place --all` reaches a clean
  layout with at most one refusal. Measured on the next headless run.
  The cost target in gap 4 stands and is now the number to watch.

Measurement: count check invocations in the session's stream-json log;
count the place, check and refresh calls before the first clean layout
and the refusals among them.

The restated claim (a first draft with no positions reaches a clean layout
with at most one layout refusal after `place`), measured on 2026-08-26
from the four first-map benchmark logs on systemap 0.9.0, which had
`place` without the region-order search:

| repository | refusals between the first place and the first clean layout |
|---|---|
| rich | 1 |
| poetry | 1 |
| paperless-ngx | 2 |
| kstrl | 4 |

Met on two of four. The refusals were label collisions, which is what the
region-order search in 0.11.1 scores against; the claim is re-measured on
the next first-map runs on 0.11.1 or later.

### 2. Flows are declared, not observed

What is wrong: the check verifies entries and interfaces against the code.
It does not verify that an edge exists. The agent's "edges inferred rather
than read" list is the only record, and it lives in a chat.

Mechanism: every flow gets an evidence state from the facts. `observed`
when an import joins the two components' modules in either direction;
`declared` when nothing in the facts does. Edges touching an actor are
outside the code and are marked `external`. Declared edges draw dashed,
the panel says "declared: no import behind it", and judgement prints one
line per declared edge so the agent either finds the evidence, names the
mechanism (a subprocess, a file, a queue) in the sentence, or removes it.
A `[flows] observed_by = [...]` config key lets a repository name the
non-import mechanisms it uses, so a queue edge is not nagged forever.

Acceptance: on the run-3 map, the set of `declared` edges equals the five
edges the session itself listed as inferred, plus or minus the ones that
touch an actor; a fixture test asserts the three states. Landed in 0.8.0:
the fixture test asserts the three states and observed-by-mechanism; on
the self-map two edges were declared before answering, one now names
its mechanism (the facts file) and one is answered. The run-3 comparison
needs that map's session log and is not measured here.

### 3. There is no maintenance path

What is wrong: the loop is built for the first draft. After a pull request
moves a module, `extract --check` fails and the skill's only answer is the
whole loop again, at first-draft cost.

Mechanism: `systemap delta --base REF`. From the facts at two commits: the
modules added, removed and moved, the cards they belong to, new crossing
imports with no flow, interface and entry names that vanished, and the
change map figure the change detector already draws. The skill gains a
"the code changed" path: run `delta`, act only on its lines, `refresh`,
`check && judgement --strict`. The workflow `init` writes gains a
`pull_request` job that posts the delta and the change map as one comment
(permissions `pull-requests: write` on that job only; zizmor clean).

Acceptance, stated now as targets: three real merged pull requests from a
mapped repository's history (small, medium, large by files changed),
replayed on top of its map by a headless session in the maintenance path.
Small and medium: at most 15 turns and at most 2 dollars each. Large:
measured and reported, no target. If the measured numbers are higher, the
README carries the measured numbers.

Measurement: the benchmark harness in gap 4.

Landed in 0.9.0: `systemap delta --base REF [--head REF] [--format
markdown]`, reading the facts at both commits out of git; the skill's
"When the code changed" section and references/maintenance.md; the
workflow's pull_request job that posts the delta as one comment, with
`pull-requests: write` on that job alone and zizmor clean. Since then,
0.10.0 made `delta` walk every map of a tree. Still not measured, as of
0.10.1: no pull request has been replayed in the maintenance path by a
headless session; the three replayed pull requests need a mapped
repository's history and a harness run, and docs/benchmarks.md has no
maintenance row until then.

Measured on 2026-08-26 (systemap 0.11.0, claude-opus-5[1m]), three real merged
pull requests replayed as reverts on the kstrl benchmark map, by the harness,
each finishing on its own with check clean and judgement --strict at exit 0:

| replay | files | turns | minutes | dollars |
|---|---|---|---|---|
| small (PR 237) | 8 | 51 | 6.4 | 2.31 |
| medium (PR 213) | 17 | 63 | 11.3 | 4.39 |
| large (PR 184) | 20 | 46 | 5.8 | 2.50 |

Against the target (small and medium at most 15 turns and 2 dollars): missed
on turns by three to four times, missed on dollars by 0.31 and 2.39. The
turn target did not account for the maintenance path's own steps (delta,
refresh, check and judgement together, answers), which is where most turns
went; the dollar number is the one the README quotes. The target line
above stays as written.

### 4. Cost is measured twice, on one repository, by hand

What is wrong: two runs, one repository, numbers read off a log. Nothing
about a refresh, nothing about a larger tree, and the model is unnamed.

Mechanism: `bench/run.sh`, the headless recipe as a script: clone or
worktree, install the pinned version, `init`, the sentence, stream-json
to a file, and a summary line with the model, turns, minutes and dollars
from the result event. `docs/benchmarks.md` is generated from the summary
lines and committed, one row per repository per mode (first map,
maintenance small, medium, large). The skill states a turn budget per
step so a run that overruns says which step ate it.

Acceptance: before 1.0, the table has at least four repositories (the
self-map, a 100-module tree, a 150-module tree, a 300-plus-module tree) in
first-map mode and at least one in every maintenance mode. Targets for
1.0, stated now: first map at most 0.15 dollars per module; maintenance
at most 2 dollars on a medium pull request. The README quotes the table,
not the targets.

Landed in 0.9.0: bench/run.sh (the recipe as a script, the summary line
from the session's result event, the first tool call verified from the
log), bench/summary.py, bench/table.py and docs/benchmarks.md, and the
turn budgets in the skill. Measured, as of 0.10.1: the table has one
row, a first map of a private 144-module service by systemap 0.8.0,
from its session log: 25.49 dollars, 0.177 dollars per module, against
the 0.15 target. Missed; the target stands, and the table carries the
measured value.

Measured, as of 0.11.1, in docs/benchmarks.md: four more first-map rows,
each run by bench/run.sh on systemap 0.9.0, against the 0.15 target:
https://github.com/0xfauzi/kstrl, 111 modules, 17.61 dollars, 0.159 per
module; https://github.com/Textualize/rich, 103 modules, 14.37 dollars,
0.14; https://github.com/paperless-ngx/paperless-ngx, 341 modules, 24.24
dollars, 0.071; https://github.com/python-poetry/poetry, 192 modules,
20.82 dollars, 0.108. Three of the four under the target; one at 0.159.
The target stands, unedited; the table carries the measured values, the
0.177 row included. The 100-module and 300-plus-module trees of the
acceptance line are in the table; the self-map row is not. Still
unmeasured in the committed table: every maintenance mode.

### 5. Past sixty cards the single map stops working

What is wrong: one canvas, hand-placed or not, cannot hold a 300-module
repository legibly, and the check's rules assume one canvas.

Mechanism: nested maps. A component may carry `map = "map/sub/name.py"`,
a model of its own whose modules are exactly the parent's
`implemented_by`. The parent card shows a "has a map" mark and links to
the sub-page; the sub-page links back. Coverage: the parent claims the
modules once; the sub-map must claim exactly those and no others, and the
check runs on every map. `describe` and `suggest` say when a map is past
forty cards and which cards are candidates to open.

Acceptance: a 300-plus-module repository mapped as one top map of at most
forty cards plus at least two sub-maps, every check clean, and the
benchmark row for it inside the first-map cost target.

Landed in 0.10.0: `Component.map`, the tree of maps every command walks
(`systemap.nest`), the nesting rule of the check (exact claims, actors
that are cards above), one page per map with the links up and down, the
"has a map" mark and the `opens:` panel line, `figure --map`, the
prefixed check, judgement, describe and place lines, `delta` on every
map, `suggest`'s past-forty line, and the skill's guidance on when to
open a map inside a card. Not measured, as of 0.10.1: no 300-plus-module repository
has been mapped this way yet; the fixture in tests/test_nested.py is
ten modules, the one headless run since (run 4, 144 modules, 40 cards)
opened no map inside a card, and the acceptance line waits on gap 6's
external runs.

Measured on 2026-08-26 (systemap 0.11.0, claude-opus-5[1m]): a 460-module
public repository (mealie), by the harness, finished on its own in 167
turns, 32.9 minutes and 23.76 dollars (0.052 per module, inside the
first-map target); check clean on every map, judgement --strict at exit 0
with 105 answered. The top map has 37 cards (at most forty: met) and the
session opened one sub-map (ImportWorkflow, 10 cards, clean). The
acceptance line asked for at least two sub-maps: one was drawn, so that
clause is missed and the line stays as written. What the run shows is that
the mechanism holds on a real 460-module tree; whether an agent opens a
second map is its judgement of the code, which the tool suggests but does
not force.

### 6. It has been run on one repository, ours

What was wrong: n equals one, and we wrote it.

Mechanism: the benchmark harness on three public Python repositories we
did not write, chosen for shape rather than fame: a command-line tool, a
web service, a library; 100 to 400 modules; permissive licence; active.
Each run by the documented path only. Every friction item filed as an
issue on this repository; anything that recurs across two repositories is
fixed before 1.0. The three maps are published as examples (model and
page only, linking to the source repository and its licence).

Acceptance: all three finish unattended with check clean and
`judgement --strict` at exit 0; at most five friction items per run and
none of them a defect (a defect is wrong output, a valid input refused, or
a crash; a wording complaint is not).

Measured, as of 0.11.1: four repositories, three not ours
(https://github.com/Textualize/rich, a library, 103 modules;
https://github.com/paperless-ngx/paperless-ngx, a web service, 341;
https://github.com/python-poetry/poetry, a command-line tool, 192) and
https://github.com/0xfauzi/kstrl (ours, 111), each run by bench/run.sh
on systemap 0.9.0 with the documented sentence and nothing else. All
four finished unattended with check clean and `judgement --strict` at
exit 0 (docs/benchmarks.md). Zero systemap crashes and zero usage errors
in the four session logs.

Not measured: the friction-item count. The harness runs the pure user
sentence, and a friction log is a test instrument, not user behaviour;
asking the agent to keep one would change the run being measured, so
the acceptance line's "at most five friction items" has no number. The
substitute signal is the helper scripts the agent wrote around the
tool: three on one repository, four on another, none on the other two.
The helper both of those repositories shared tried region orders and
picked the one with the fewest bends and shortest routes, because
`place` laid the regions in model order and never compared two; 0.11.1
builds that search into `place`. The other helpers are not yet read for
the same signal; that is the next item here. Not done: the three maps
are not published as examples.

### 7. It is not yet distributed, and the page's claims are half verified

What was wrong: not on PyPI, so a consumer's CI cannot pass; the plugin
install was proven once, by hand, on this machine; the light scheme was
measured for contrast but never looked at; nothing had run on Windows;
the page had no keyboard path.

Landed in 0.11.0, each with its measurement:
- CI matrix: Linux, macOS and Windows with Python 3.11 and 3.13; the
  suite, the types and the linter pass on all six; a job per platform
  installs the built wheel with pip into an empty virtual environment
  and runs `init`, `extract`, `refresh`, `check`, `judgement --strict`
  and `render --check` on a copy of the self-map beside the checkout.
  Windows broke line endings (every writer now writes LF) and path
  separators (every printed or recorded path is posix); `git archive`
  in `delta` and the loopback server in `serve` ran unchanged.
- The plugin job adds the checkout as a marketplace, installs the
  plugin from it with the CLI and lists it; no login is needed for the
  three commands, so the job is strict.
- The light scheme rendered and looked at (the page, two readings, a
  drawer with a spoke read, a journey step, the index and invariants);
  nothing read badly; `docs/screenshots/light.png` beside `dark.png`.
- Keyboard: arrows switch readings or step a journey, Tab moves across
  the cards in reading order, Enter opens the wheel, Escape closes it
  and hands the focus back, `prefers-reduced-motion` honoured;
  `tests/test_keyboard.py` drives the page's script under Node with the
  readings table.
- README: Python-only in the first paragraph; the cost table by
  reference; a thirty-second tour of the page.

Deferred, on purpose:
- Publishing to PyPI: the maintainer publishes 1.0 by hand with
  `scripts/publish.sh` when every acceptance line in this document is
  met; until then the workflow `init` writes pins the release tag.
- Submitting the plugin to the official marketplace: after 1.0, not
  before.

Acceptance, restated: `uv tool install systemap` from PyPI on all three
operating systems is the one line still open, and it opens with the
publish; the four-command path from the built wheel passes on all three
in CI; the marketplace install job passes; both scheme screenshots
exist; the keyboard test passes.

## Order

Gaps 1 and 2 first, together, because they change the model and the
check, and every benchmark after them would otherwise be measured twice.
Then 3 and 4 together, because the maintenance path is what the benchmark
mostly measures. Then 5 with 6, because nested maps need a large
repository and the external runs supply one. Gap 7 runs alongside from
the first PyPI release and closes last.

Versions: 0.8 (gaps 1, 2; first PyPI release), 0.9 (gaps 3, 4), 0.10
(gaps 5, 6), 0.11 (gap 7 but the publishing), 1.0 (gap 7 closed, every
acceptance line above met, README numbers measured).

## What this document does not promise

Every number above is a target or a threshold set before the work, so
that the work can fail it, except the ones marked measured: gap 1's
check-and-refresh count (21 against a target of 11) and gap 4's first-map
cost (0.177 dollars per module against 0.15), both missed on run 4 and
both left standing, and gap 4's four 0.9.0 rows (three under 0.15, one
at 0.159). When a measured value misses its target, the choice is to
change the mechanism or to publish the measured value, never to move
the target quietly.
