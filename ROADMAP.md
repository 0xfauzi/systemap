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

Measurement: count check invocations in the session's stream-json log.

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
`pull-requests: write` on that job alone and zizmor clean. Not measured:
the three replayed pull requests need a mapped repository's history and
a harness run, and the table in docs/benchmarks.md is empty until then.

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
turn budgets in the skill. No repository has been measured by the harness
yet; the table says so.

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

### 6. It has been run on one repository, ours

What is wrong: n equals one, and we wrote it.

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

### 7. It is not yet distributed, and the page's claims are half verified

What is wrong: not on PyPI, so a consumer's CI cannot pass; the plugin
install was proven once, by hand, on this machine; the light scheme was
measured for contrast but never looked at; nothing has run on Windows;
the page has no keyboard path.

Mechanism, in order:
- Publish 0.8 to PyPI as soon as gaps 1 and 2 land, so consumers' CI can
  run while the rest is built; 1.0 when every acceptance line in this
  document is met.
- CI matrix: macOS, Linux, Windows; the tests pass on all three, and a
  job installs the built wheel and runs `init`, `extract`, `check` on the
  self-map from a clean directory.
- A CI job that adds the repository as a marketplace and installs the
  plugin with the CLI, then lists it, so the install proof is mechanical.
- The light scheme rendered and looked at, with its screenshot kept
  beside the dark one in `docs/`.
- Keyboard: readings switch with the arrow keys, cards take focus with
  Tab, Enter opens the wheel, Escape closes it; `prefers-reduced-motion`
  honoured. A test drives the page's script with the readings table.
- README: the Python-only statement in the first paragraph; the measured
  cost table; a thirty-second recording of the page.
- Submit the plugin to the official marketplace after 1.0, not before.

Acceptance: `uv tool install systemap` and the four-command path work on
all three operating systems in CI; the marketplace install job passes;
both scheme screenshots exist; the keyboard test passes.

## Order

Gaps 1 and 2 first, together, because they change the model and the
check, and every benchmark after them would otherwise be measured twice.
Then 3 and 4 together, because the maintenance path is what the benchmark
mostly measures. Then 5 with 6, because nested maps need a large
repository and the external runs supply one. Gap 7 runs alongside from
the first PyPI release and closes last.

Versions: 0.8 (gaps 1, 2; first PyPI release), 0.9 (gaps 3, 4), 0.10
(gaps 5, 6), 1.0 (gap 7 closed, every acceptance line above met, README
numbers measured).

## What this document does not promise

No number above is a measurement yet; each is a target or a threshold set
before the work, so that the work can fail it. When a measured value
misses its target, the choice is to change the mechanism or to publish the
measured value, never to move the target quietly.
