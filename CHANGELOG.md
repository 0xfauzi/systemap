# Changelog

## 0.11.0

ROADMAP gap 7, everything but the publishing: the package proven on three
operating systems, the plugin install proven by the CLI in the workflow,
the light scheme rendered and looked at, the page from the keyboard with a
test that drives its script, the README with the cost table by reference
and a thirty-second tour. Not in this release: the PyPI publish (the
maintainer publishes 1.0 by hand with `scripts/publish.sh`) and the
submission to the official marketplace (after 1.0, not before).

- CI on Linux, macOS and Windows with Python 3.11 and 3.13: the suite,
  `mypy --strict`, `ruff check` and `ruff format --check` on each; and a
  job per platform that builds the wheel, installs it with pip into an
  empty virtual environment, copies this repository's own map beside the
  checkout (no `.git`, no source tree on the path, no uv at run time) and
  runs `init`, `extract`, `refresh`, `check`, `judgement --strict`,
  `render --check` and `describe` there. `check` comes after `refresh`
  because the check refuses a page that is not rendered, and the
  committed page names the commit it was rendered at, which a copy
  without `.git` cannot reproduce.
- What Windows broke, fixed: every file systemap writes now ends its
  lines with LF on every platform (`newline="\n"` on every writer:
  the page, the facts, the figures, the model `place` edits, the skill,
  what `init` scaffolds), so a page rendered on one machine is byte for
  byte what another renders and `render --check` compares as written;
  every path printed or recorded uses forward slashes (`Config.rel`, the
  `file` of each module record in the facts, the skill directory `init`
  names); `.gitattributes` checks every text file out with LF. Two tests
  were platform-bound: the plugin skill-tree comparison keyed its paths
  by the platform separator (now posix), and the `bench/run.sh` test is
  skipped on Windows with the reason (the `bash` on a Windows PATH is
  the WSL launcher, not a shell that runs it). `git archive` in `delta`
  and the loopback server in `serve` needed no change: the suite runs
  them on Windows.
- The plugin job adds the checkout as a marketplace (`claude plugin
  marketplace add ./`), installs `systemap@systemap` from it and lists
  it, into a configuration directory of its own; the list must show the
  plugin enabled. None of the three needs a login (measured with an
  empty `CLAUDE_CONFIG_DIR` on the pinned CLI, locally and on the
  runner), so the job fails when any of them does.
- The light scheme, rendered and looked at: the page, the All and the
  Control flow readings, a card's drawer with a spoke read, a journey
  step, and the index and invariants under the map, each photographed
  by headless Chrome. Nothing read badly; no token moved.
  `docs/screenshots/light.png` sits beside `dark.png`, both at 1600 by
  900, and the README shows them. `scripts/screenshots.py` writes both.
- Keyboard: the cards are written in reading order (row by row, left to
  right), so Tab moves across the map the way the eye does; Enter or
  Space on a focused card opens its wheel; Escape closes it, returns the
  view and hands the focus back to the card; the left and right arrows
  switch readings, wrapping through All, or step the journey while one
  is on; the journey select keeps its own arrows; the focus ring is the
  accent of the scheme on the card, the spoke and every control; the
  index buttons scroll without smoothing under `prefers-reduced-motion`,
  which already turned every transition and the framing animation off.
  The page's hint and key paragraph say so.
- A test drives the page's script: `tests/page_driver.js` loads a
  rendered page into a DOM of its own (a tag parser, a selector matcher,
  events that bubble, focus, animation frames on a fake clock; no
  library), runs the page's scripts as written, presses the keys and
  reports; `tests/test_keyboard.py` asserts the arrows walk the readings
  table the page carries, the Tab order, Enter, Escape, the journey and
  that reduced motion frames without an animation frame, on the sample
  page and on the committed self-map page. It runs under Node where
  Node is on the PATH (every runner the workflow uses) and skips with
  the reason where it is not.
- README: the first paragraph says Python and only Python; the Cost
  section is the table by reference (the table is the number) and
  copies no row; a thirty-second tour, `docs/screenshots/tour.gif`,
  twelve states of the page (each reading, All, a card and its wheel, a
  spoke read, a journey stepped, a card on the Control flow reading) at
  two and a half seconds each, produced from headless screenshots
  stitched by ffmpeg, 1.1 MB. Every state could be driven headlessly.

## 0.10.1

What the fourth headless run found: the first run with `place`, on the
same repository as runs 1 to 3 (systemap 0.8.0; finished on its own,
check clean, `judgement --strict` 0). Ten friction items, each with a
decision, and the measurement gap 1 of ROADMAP.md was waiting on.

- ROADMAP gap 1, measured and missed: the check-and-refresh count on
  run 4 was 21 against a target of 11 (run 3: 22). The roadmap records
  the count, the calls to the first clean layout (2 and 3, one refusal
  each), the work between the first model write and that layout (6 tool
  uses over 8 turns, then 5 over 7) and the whole-run cost (168 turns
  and 17.30 dollars, then 232 and 25.49), under the original target,
  kept and marked missed, with the reading: hand placement was already
  cheap on that repository by run 3, and `place` could not lay a map
  out again. The acceptance for `place` is restated as a claim it can
  meet: on a first draft with no positions, `place --all` reaches a
  clean layout with at most one refusal, measured on the next run. Gaps
  3, 4 and 5 say what landed and what is still unmeasured; gap 4 states
  the one benchmark row, 0.177 dollars per module against 0.15.
- `place --all` and `Component.pinned`. After the first `place` every
  card had a position, so a card added later found no free slot and the
  only fix was a hand edit of the file. Now `pinned: bool = False` on a
  card means a person chose its position; `systemap place` places the
  cards without a position and keeps the rest, as before; `systemap
  place --all` lays every card out again and keeps only the pinned
  ones (with none pinned, the boxes and the canvas too); the "no free
  slots" refusal names `place --all`; `describe` counts pinned by the
  flag (`positions: 1 pinned, 17 placed`); the skill's loop says to run
  `place --all` after adding or removing a card, and layout.md says
  when to pin. `Component.positioned` is the property that `pinned`
  was; `Placement.kept` is the tuple that `Placement.pinned` was.
- The facts views no longer leak the JSON they replace. `facts --module
  NAME` renders the record (docstring, public names with their kinds,
  re-exports marked with their module, imports, imported by, external,
  the test count) and never a test's name; `--modules` carries the
  first sentence of each module's docstring before the counts;
  `--docstrings` prints module and first sentence alone; `--names NAME`
  prints the public names with kinds; `--entry-points` prints each
  target beside the point, the thing that collapses `python -m pkg`
  and `main()` into one journey. SKILL.md says which view gives what.
- Evidence: two cards that share a module (a tool claimed by symbol
  inside its agent's module, the shape layers.md recommends) can never
  have an import between them, so the flow was permanently declared.
  Now the shared module is the evidence: the flow is observed, the panel
  says `observed: shared module`, and layers.md says so.
- `init` against a strict repository's own gates. The starter's import
  line carries `# type: ignore[import-not-found, unused-ignore]` with a
  comment saying why (mypy strict refused the import in a repository
  that does not depend on systemap, the recommended shape; the second
  code keeps the ignore quiet where systemap happens to be installed);
  the package ships `py.typed`, so an installed systemap is typed; and
  `init` prints one note naming mypy and deptry with the exact pyproject
  lines deptry needs (`[tool.deptry.per_rule_ignores]`, `DEP001 =
  ["systemap"]`, `DEP003 = ["systemap"]`). pitfalls.md says to run
  every CI command the repository runs, not only pre-commit.
- `judgement` output fit for one tool call. Crossing-import lines are
  one per ordered pair of cards with a module count (`crossing import:
  Page imports Model in 16 modules and no flow joins them`) instead of
  one per import; `--verbose` lists the imports under each line;
  `--kind KIND` prints one kind at a time (the head and `--strict` still
  count every open line). `delta` matches an answer against the grouped
  line. An `item` answer that quotes an old crossing-import line goes
  stale: answer the pair (`crossing`, `crossing_into`, `crossing_from`)
  or quote the new line. second-pass.md shows one row per answer form,
  seven for seven, and names the new line and both flags.
- pitfalls.md: a scratch script goes outside the repository (for
  example /tmp), never in the repository root.
- Tests: the anonymised fixture gains a pinned tool card that claims a
  symbol inside its agent's module and the tool flow between them, so
  `place --all`, the pinned flag and the shared-module evidence are
  measured on it; every decision above has a test.

## 0.10.0

Gap 5 of ROADMAP.md: past sixty cards the single map stopped working,
and the check's rules assumed one canvas.

Nested maps:

- `Component.map`: a path, relative to the model file, naming a second
  model module that exports `MODEL` and `MEANING` like any model. The
  map inside a card draws that card alone: its cards claim exactly the
  modules the card claims, no more and no fewer, each once (symbol
  claims allowed, empty package markers left out as the coverage rule
  leaves them out); its actors are cards of the map it is inside, the
  ones around the card, so its edges to the outside have somewhere to
  land. The card claims the modules once for coverage. An actor cannot
  open a map; a map that opens a file above it, or one that does not
  exist, is refused with exit 2. A map inside a map is `Gateway/Routes`.
- `systemap.nest` loads the tree (the top map, then each sub-map depth
  first in the parent's card order) and every command that reads the
  model walks it.
- `check`: every rule on every map, and a nesting rule between them
  that names each module the sub-map claims and the card does not,
  each it leaves unclaimed, each it claims twice, and each actor that
  is not a card above; coverage runs on the top map alone. A sub-map's
  lines carry its id in front (`Gateway: map layout: clean ...`), the
  fix line names the sub-map's file, and the stale group covers every
  page.
- `refresh` and `render` write one page per map: the top at
  `index.html`, the map inside a card at `<card>/index.html` under the
  output directory. A card that opens a map stands on a second card
  (the mark, on the page and in every figure, with a legend row) and
  its panel reads `opens: Gateway (5 cards)` with a link; the header
  lists the maps inside. A sub-map's page names the card it is inside,
  links back to the map above, and lists its own readings and journeys.
- `figure --map ID` draws the map inside a card, and a `[[figures]]`
  entry takes `map`. `place` writes positions into every map's file.
  `describe` prefixes a sub-map's lines with its id.
- `judgement` runs on every map with the prefix on a sub-map's lines;
  an `item` answer quotes the line as printed and a bulk form covers
  every map. An entry point, or a model sdk import, is asked about once,
  on the deepest map whose card claims its module, against the journeys
  of every map.
- `delta` compares each sub-map over the modules its card claims at
  each commit, so a moved or removed module names the card on every map
  it is drawn on and that map's file, and a new module inside a card
  that no sub-card claims says the map inside claims exactly what the
  card claims.
- `suggest` reads the tree when a model has cards: when a map is past
  forty cards it says so and names the cards with the most modules as
  the candidates to open; a card past ten modules is named on any map.
- The skill: `schema.md` documents `map`, `layout.md` says when to open
  a map inside a card and how, `pitfalls.md` gains the poster of sixty
  cards, `second-pass.md` says the pass runs on every map; the loop is
  unchanged.
- Tests: a fixture of one top map with two maps inside it, covering the
  exact-claim rule, the actor rule, coverage counted once, the pages
  and their links, `figure --map`, `place` on a sub-map, the judgement
  and describe prefixes, `delta` naming the card and the map, and the
  suggest line. systemap's own map is not nested: 18 cards is below the
  threshold.

## 0.9.0

Gaps 3 and 4 of ROADMAP.md, closed together because the maintenance
path is what the benchmark mostly measures: there was no maintenance
path, and cost was measured twice, on one repository, by hand.

`systemap delta --base REF [--head REF]`:

- The facts at two commits, both read out of git (`git archive` into a
  temporary directory, then the extractor as usual), never from the
  working copy; the base is the merge base of the two refs, so a base
  branch that moved on is not a change. Compared in the map's terms
  against the model on disk: modules moved (same content, else the same
  public names), added and removed, with the card each belongs to; a new
  module no card claims (coverage lost); entry and interface names the
  card's modules defined at the base and no longer do, judged by the
  check's own interface rule; imports that cross a card boundary at the
  head and did not at the base, with no flow and no answer under
  `[judgement]`; flows an import backed at the base and nothing backs
  now.
- One line per thing, each naming its fix, in two groups: `needs a
  person` and `changed, nothing to do`. Exit 0 when nothing needs a
  person, 1 when something does, and the last line names what to run. A
  card told to rename or drop a module is not also asked about its
  names, and a card that names a module's new path is taken to have
  claimed the old one at the base, so a pending rename is one line. When
  more than about a third of the cards are named the report says so.
- `--format markdown` prints the report as a pull-request comment: a
  marker line the workflow finds the comment by, the two groups, and the
  committed whole-map figure at the head commit as an image, by the blob
  URL with `?raw=true` (the form GitHub's writing guide gives for an
  image from the repository in a comment; a `data:` URI is stripped).
  The change map itself depends on the base and is not a committed
  file, so the comment names the command that draws it.
- An unknown ref is refused with exit 2 and the fix named.

The maintenance path:

- SKILL.md gains "When the code changed" and `references/maintenance.md`:
  `delta --base <the base branch>`, act only on its lines, `refresh`,
  `check && judgement --strict`; never redraw a map to absorb a small
  change; when `delta` names more than about a third of the cards, say
  so and run the full loop instead. The sentence for an agent: "The code
  changed. Update the map with systemap: follow the systemap skill's
  maintenance path, with base <ref>." A budget of 15 turns.
- The skill states a turn budget per step: extract 2, draft 10, place
  and check 15, judgement 10, second pass 20; budgets an overrun names in
  the hand-back, not limits. SKILL.md's ceiling moves from 200 to 230
  lines for the new section.
- The workflow `init` writes gains a `delta` job on pull requests: it
  runs `delta --base <base sha> --head <head sha> --format markdown` with
  both shas passed through the environment, posts the report as one
  comment or updates the one it posted before (found by the marker, with
  `gh api`), and fails while a line needs a person. `contents: read` at
  the top, `pull-requests: write` on that job alone with the reason
  beside it, every action pinned to a commit, zizmor clean; a fork's
  read-only token turns the post into a warning. This repository's own
  workflow carries the same job.

The benchmark harness:

- `bench/run.sh <repo-url-or-path> <first-map|maintenance> [--ref REF]
  [--base REF] [--from SPEC] [--model NAME] [--max-turns N]`: a worktree
  for a path or a clone for a URL under `bench/scratch/`, systemap
  installed into a tool directory of the run's own from the release tag
  of this checkout's version (`--from` overrides it), `systemap init`,
  the documented sentence (the maintenance sentence with `--base`), the
  agent headless with the acceptEdits permission mode and the tool list
  the recipe used (Skill, Read, Edit, Write, Glob, Grep, TodoWrite, and
  Bash for systemap, uv, uvx, python3, git, ls, cat, grep, rg, find,
  head, tail, sed, wc and mkdir), the session streamed as JSON to a log.
  Then `check`, `judgement --strict`, the module count, and one summary
  line appended to `bench/results.jsonl` by `bench/summary.py`: the
  model the session names, its turns, minutes and dollars from the
  result event, finished or cut off, and whether the first tool call was
  the systemap skill, which the recipe requires. Nothing is estimated: a
  value the log lacks is null.
- `bench/table.py` renders `bench/results.jsonl` into
  `docs/benchmarks.md`, one row per repository per mode with the model
  and the systemap version named and the dollars per module for a first
  map; a test keeps the committed file equal to the render. The table is
  empty: no repository has been measured by the harness yet, and the
  README's Cost section says the table is the number.
- Tests: the parser on a synthetic stream-json fixture, the table, the
  script's usage and the recipe it spells out, the workflow text, and
  `delta` on a synthetic two-commit repository covering every line kind.

Also:

- The check's interface rule is one function, `interface_problem`,
  reported by the check and compared at two commits by `delta`.
- The self-map claims the delta module under ChangeDetector, draws the
  interface-rule edge from Check, retells the refactor journey as the
  maintenance path, and answers the one new crossing import.

## 0.8.0

The first two gaps of ROADMAP.md, closed together because both change
the model and the check: layout was hand-placed, and flows were declared
rather than observed.

`systemap place`:

- A first position for every card without one, deterministic and from
  the standard library alone. Regions go on a two-column grid inside
  their container, in the model's order, with the corridors
  references/layout.md specifies (48 units between region columns, 36
  between rows); cards go on the grid inside their region (columns 190
  apart, rows 92 apart, three deep before a second column), ordered by
  a few barycentre sweeps over the flows so the parts that talk sit
  together; a region's box follows its card count, a container's its
  regions, and an actor stands in a column beside them, level with what
  it talks to.
- `x` and `y` are optional in the schema. A card with both is pinned and
  never moved; while any card is pinned the boxes and the canvas stay as
  written and the unpinned cards take the free slots inside their own
  boxes; a model with no pinned card is laid out whole. The check
  refuses a card with no position until `place` has written one, and
  nothing else about the check changes.
- The positions are written into the model module in place: only the
  `x=` and `y=` values, the `box=` tuples and the canvas move, and the
  rest of the file is kept byte for byte; `--print` prints them instead.
  The file is read back and compared after the write.
- On the anonymised 144-module fixture with every position stripped,
  `place` gives a map whose geometry check is clean with no manual move,
  in about a millisecond; the test asserts under ten seconds. A second
  run changes nothing, a pinned card stays where it was, and the
  self-map with its positions stripped is clean after `place`.
- `init`'s starter has no positions and no position tables; the skill's
  draft step is: write the components and the flows, run `place`, then
  check. `describe` reports how many cards are pinned and how many it
  placed for the look. layout.md is shortened to what the agent still
  decides: the region a card is in, the order of the regions, when to
  pin a card, and how to read `describe`.

Evidence on every flow:

- Every flow has an evidence state computed from the facts at render
  and at check time, never authored: `observed` when an import joins
  the two components' modules in either direction, `external` when
  either end is an actor, `declared` otherwise. A declared edge draws
  dashed on the page, in every figure and on the wheel; the panel says
  `declared: no import behind it` (or `observed: an import joins
  them`, `external: outside the code`); the legend explains the dash.
- `systemap judgement` prints one line per declared edge: `declared
  flow: A -> B (artifact): no import joins them; find the evidence,
  name the mechanism in the sentence, or remove it`. The bulk answer
  forms cover the new kind (`kind = "declared flow"`), and
  second-pass.md walks it after the crossing imports.
- `[flows] observed_by = ["subprocess", "queue", ...]` lists the
  mechanisms other than an import that join the repository's parts; a
  flow whose sentence or artifact names one (a whole word, case blind)
  is observed by it, drawn solid, and the panel says `observed by:
  queue`.
- On the self-map, two edges were declared before answering: the facts
  file joins the extractor and the schematic (`observed_by = ["facts
  file"]`, named in the sentence), and the change map reaches the page
  through the CLI (answered in the configuration).

Also:

- The workflow `init` writes pins `uvx --from
  "git+https://github.com/0xfauzi/systemap@v<version>"`, since nothing
  is on PyPI yet; the pin moves to PyPI at 1.0.
- The self-map gains a Placer card and claims the evidence module under
  Model; invariant 5 now reads "written once by systemap place or by
  hand".
- The fixture's five plain words and one container sub that were over
  the 0.7.0 card-text budget are shortened, and its two low containers
  lifted clear of their headers, so the fixture passes the geometry
  check as hand-placed too.

## 0.7.0

What a third headless run found mapping a real repository with the skill:
twenty-one items, written from inside a finished map (the run reached a
clean check and an answered judgement on its own). Each fixed here with a
test. The anonymised fixture gains an interface sweep and a re-export case.

Things the schema reference said that were not true:

- `interface`, `entry` and `note` now reach the reader. The detail panel
  prints the interface as the card's signature, the entry as `entry: name
  (module)` and the note as a caveat line; a card with a note carries a
  dot in its top corner, on the map and in every figure. schema.md says
  where each appears.
- `interface` is checked. Its leading identifier (the token before `(`,
  `.`, `->` or whitespace; both parts of `Class.method`) must be a name
  one of the component's modules defines, a re-export included; the line
  is refused with the closest defined name. Sixteen of a real map's
  twenty-one interface lines were wrong after a check that never read
  them. `interface` stays optional.
- `refresh` says what current means: `already current: the page matches
  the model's rendered fields and the facts`.

Things the check called clean that were not:

- Card text has a budget and nothing is elided. A name fits about 20
  characters (a component, agent or tool card wraps a longer CamelCase
  name over two lines), a plain word about 26 per line on the lines the
  card has; the check refuses what does not fit, stating the budget
  (`actor cards fit about 26 characters on one line; this one has 34`).
  The ellipsis is gone from the drawing.
- Two invariants with one number are refused, both rules quoted.
- An `__init__` with no public names and no imports is an empty package
  marker: listed once in the extract summary, left out of the coverage
  rule on its own, and an ignore that names only markers is refused as
  not needed. Nine such files once needed nine ignore entries. The
  subtree form `module = "pkg.sub.*"` is documented. The coverage line
  reads `144 of 144 modules mapped, 5 of them ignored with a reason, 9
  of them empty package markers`.

The facts:

- `systemap facts` reads the file back one view at a time: `--modules`
  (one line per module: name, public names, imports, tests), `--module
  NAME`, `--entry-points`, `--external`, `--imports NAME`. The skill's
  step 1 reads the facts through it, never the JSON (451 KB on a
  144-module tree), and pitfalls.md says so.
- A package `__init__` records the names it imports from the package's
  own modules under `names`, with `reexport_of` and the kind the defining
  module gives them; `entry` and `interface` accept them. The facts
  format is 2, and `extract --check` reports an older file as stale.
- The extract summary uses the documented field names (`functions`,
  `classes`, `errors`, `tests`) and schema.md maps each word.

Judgement and layout:

- `crossing_into = "Card"` answers every crossing import into a card,
  `crossing_from = "Card"` every one out of it, and `crossing` accepts two
  or more ids (every pair among them). Each has an example.
- The loop's check step is `systemap check && systemap judgement
  --strict`, every round: a layout fix that drops an edge reopens the
  lines the edge answered, and the judgement in the same round sees it.
- `describe` and the label diagnosis name a gutter by its neighbours and
  coordinates: `between the row of Orchestrator, Telemetry and the row of
  RosterClient (y 160 to 226)`.
- layout.md: the pitch is a starting value; a dense region may raise its
  row pitch, and regions in one grid row need not share a height. The
  diagnosis names the region: `raise the row pitch of region X`.
- The skill states a target (three to ten modules per component, N/10 to
  N/3 cards for N modules; the judgement lines push from both sides) and
  `systemap suggest` prints a first grouping from the package structure
  and the import graph, headed as a starting point to argue with, never
  the answer.

Agentic:

- `Component.calls_model` marks a single-shot call site. Context and tool
  flows accept an agent or a `calls_model` component at the agent end;
  the Context and Tools readings light every such flow; the Agents
  reading stays agents only; the `model sdk` line is answered by the
  flag, listed beside the four outcomes in second-pass.md.
- `entry` is optional for `store` and `context` kinds; the panel reads
  `entry: none (a namespace)`.

Words:

- One flow per ordered pair, stated under Flow in schema.md and in the
  check's message for a duplicate pair: pick the artifact that matters,
  or draw the other direction as its own flow.
- The starter's pragma is `# ruff: noqa: E501` only; every schema name is
  imported and used, so neither F401 nor RUF100 fires; `# fmt: off` and
  `# fmt: on` fence the position tables, with the reason beside them.
- The second pass's document reread is one pass over what the repository
  points a newcomer at (README, AGENTS.md, CLAUDE.md, a docs index or the
  first level of docs/), stopping when the rules found govern parts not
  in the tree.
- SKILL.md step 4 lists every answer form on its own line with its
  constraint, and a table of the seven line kinds, one sentence each,
  what a mis-fold is and what to do.
- SKILL.md says to run extract when `systemap.toml` exists but the facts
  file does not; schema.md documents `state` (`built` is the only value
  the page shows) and defines the wheel where the check counts them.

The self-map: interface lines that pass the new check, a note on the
Scaffold card, the FactsExtractor holding `facts` and the Judgement
holding `suggest`, plain words that fit their cards.

## 0.6.0

What a second fresh agent found mapping a real repository from the one
sentence `init` prints: ten items, none of them among the first run's
twenty-two, plus three from the repository's own pre-commit hooks. Each
fixed here with a test.

Layout, which took a third of the session's turns:

- `references/layout.md`, named from the skill's draft step: an edge may
  not cross a region it does not belong to, so regions never tile a
  container; a 2xN grid of regions works for every pair because the
  corridors form a cross, more than two full-width bands does not; 48
  units between region columns, 36 between rows; the parts that talk most
  in adjacent regions; one empty card column for the long routes.
- The starter model `init` writes is a 2x2 grid of regions with the
  corridors in place, ruff-formatted at 88 and 100 columns, importing
  every schema name including `Layer`. A test fills its four corners and
  routes every pair cleanly.
- A label collision says which fix applies, from the router's own seat
  counts: `gutter between rows 2 and 3 holds 3 of 3 seats: move a card or
  widen the row pitch`, or `label is 41 units wider than its seat: shorten
  the artifact`. The skill's rule of thumb: an artifact label is a noun
  phrase of one to three words, never a sentence. The second gutter seat
  moved from 51 to 53 units so two seats a side are two seats.
- `systemap describe`: what a look at the picture would tell an agent
  that cannot look. Cards per region; bends and length per edge, worst
  first, with the gutter each label sits in; seats used of seats available
  per gutter; cards and edges per reading. The skill's render step runs it
  and opens the page only if it can.

Judgement:

- `ignored:` lines are not questions and are not printed; the coverage
  reason is the answer.
- Bulk answer forms in `[judgement] answered`, each one table with one
  reason: `crossing = ["A", "B"]` answers every crossing-import line for
  the pair in either direction, `kind = "single module"` every line of
  that kind, `module_sdk = "google.adk"` every model sdk line for that
  import. `item` and `items` stay. An answer that matches no line is
  reported as stale under the form it was written in.
  `references/second-pass.md` shows every form with an example.
- The model sdk line has a fourth outcome: a part that calls a model once
  and is deliberately not an agent, by the repository's own rule; when the
  repository defines what counts as an agent, that definition wins over the
  SDK prompt. The built-in list matches import prefixes, so `[facts]
  model_sdks` removes a built-in name with a leading `-` (`"-google.adk"`);
  removing a name that is not listed is refused.
- `systemap judgement --strict` exits 1 while any line is unanswered, for
  CI; the workflow `init` writes runs it after `check`.

Symbol claims:

- `implemented_by` may name a symbol, `"pkg.mod:name"`, for a part that
  lives inside another card's module (a tool defined beside the agent
  that invokes it). A symbol claim counts for no module in the coverage
  rule and conflicts with no claim; the entry rule refuses a symbol of a
  module the facts do not have, of a name the module does not define, or
  of a module nobody claims. `references/layers.md` shows the case.

Words:

- The skill: both `systemap` and `uv run systemap` resolve when the tool
  is installed; use whichever `systemap --version` answers to.
- The extract summary labels its numbers: facts for the change detector,
  which never appear on the map.
- A `NameError` or `ImportError` while loading the model is one line with
  the fix (`map/model.py failed to import: ...; add the missing name to
  the import from systemap`), exit 2, never a traceback.
- `check` prints coverage as `140 of 144 modules mapped, 4 ignored with a
  reason`, so the extract's total and the check's total agree.
- `figure --out` is relative to `out_dir`, like a `[[figures]]` out; an
  absolute path stays absolute.
- The model module is compiled and run directly, not through the import
  loader whose bytecode cache handed back the previous model after an
  edit of the same size within the same second.

The repository's hooks:

- The facts file is compact: no indentation, keys sorted, one module
  record per line, and no per-symbol docstrings. Measured with the old
  and the new writer on the same trees: this repository, 17 modules,
  87 KB before and 59 KB after; a 111-module tree, 428 KB before and
  304 KB after. The session's 144-module tree (635 KB) was not available
  to measure; at the ratio measured it would land near 450 KB, under the
  500 KB hook, so the symbol table was not split.
- The workflow `init` writes pins every action to a commit with the
  version beside it, declares `permissions: contents: read`, and sets
  `persist-credentials: false` on the checkout; zizmor reports nothing on
  it, and a test asserts all three.
- `references/pitfalls.md`: run the repository's formatter on
  `map/model.py` before the check; keep scratch scripts out of the
  repository root.

The self-map gains a `Describe` card and answers its judgement with the
bulk forms.

## 0.5.0

What a fresh agent found mapping a real repository with only the README:
twenty-two defects, each fixed here with a test.

Judgement:

- `possible mis-fold` compared the component id with the module's last
  path segment and fired 112 times on 27 cards. It now compares every
  word of the dotted path with the component's id, `does`, plain word and
  `interface`, and fires only in a component of several modules when the
  module's package holds none of the others and is not one of them. On
  the anonymised fixture of that map (`tests/fixture_workspace.py`: two
  packages, 144 modules, 27 cards, four agents): 112 before, 0 after.
- The list has memory. `[judgement] answered` in `systemap.toml` holds
  each answered line (`item`, or `items` for one reason over several)
  with its reason; an answered line is suppressed and counted in the
  header, an answer whose line is gone is reported as stale, an answer
  without a reason is a configuration error. The skill's step 4 and
  "what to hand back" point at it: the answers are the hand-back, and
  they live in the repository.
- A new line, `model sdk: module X imports <sdk> and its component P is
  not an agent`, over a built-in list of model SDKs and agent frameworks
  extended by `[facts] model_sdks`: the mechanical prompt for the agentic
  layers.
- The `note: ... sits on a shorter segment` line on a clean check is
  gone; it was not a rule.

Facts:

- Each module record carries `external` (third-party imports, as the
  dotted names written) and `names` (every public module-level name with
  its kind: function, class, error, constant, object). A component's
  `entry` may be any public name, so `app` or `root_agent` is accepted.
- `tests_dir` takes a directory or a list; unset, every directory named
  `tests` or `test` under the root is read. The facts record
  `tests_dirs`; when no test imports a module the extract summary says
  so in one line and names the directories searched.
- Package roots are discovered under every `[tool.uv.workspace]` member;
  the error when none is found lists every directory holding an
  `__init__.py` up to four deep.
- `name` defaults to `[project] name`, then the git repository's
  directory (the main checkout, even from a worktree), then the
  directory's name.
- `extract.FIELDS` declares every field the extractor writes;
  `references/schema.md` is rendered from it and a test compares both
  the reference and what `build` writes with the table.

Check:

- `wheel of X: label Y leaves the drawing` is deleted: the wheel sizes
  itself to its labels. The wheel rule keeps the centre and the labels
  off each other.
- A label collision names both labels by artifact and edge, and a
  collision inside the 2-unit gap no longer reports an empty list.
- Container and region header text joins the labels rule: a `sub` wraps
  to a second line inside its box and is refused past that; a label
  wider than its box and a header touching a card are refused too.
- `refresh` checks what it wrote and exits 1 when the check fails.
- `--root` is accepted after the subcommand as well as before it.

init:

- Configures `figures/structure.svg` and `figures/system.svg` (bare
  drawings) instead of `system.html`.
- The starter model has no components; the check says "the model has no
  components yet; see the skill" as its one line; the starter toml
  carries no ignore.
- Reports the skill directory once: "wrote .claude/skills/systemap/
  (SKILL.md and 6 references)".
- The workflow runs `uvx --from "systemap==<the version that wrote it>"
  systemap ...`, so the project needs no dependency on systemap; it
  needs the package on PyPI, which it is not yet, and the README says so.
- The starter model opens with `# ruff: noqa: E501` and one comment
  saying why; every rendered file ends with a newline.

Skill and README:

- The draft reads the repository's own words: its README, AGENTS.md,
  CLAUDE.md, docs/.
- `systemap serve [--port 8765]` serves the output directory over HTTP
  on the loopback address and prints the URL; the page's script does not
  run from a `file://` address, and the skill says to use it.
- The second pass answers a long list in bulk, walks the model sdk
  lines, and looks at `figures/structure.svg` then `figures/system.svg`.

Agentic rendering:

- The Context reading is about the context cards and Tools about the
  tools, as Agents is about the agents. A figure of one reading gives
  its subject cards the reading's colour as their stroke and dims every
  card no edge of the reading touches, as the page does; the page
  colours the subject strokes the same way.

The self-map is regenerated with the new facts fields, the top row moved
clear of the region header the new rule caught, and its sixteen
remaining judgement lines answered in `systemap.toml`.

## 0.4.1

A figure of one reading, so a document can show one question's answer
instead of every arrow at once.

- `systemap figure --layer ID` draws one reading: a kind layer's flows,
  or for a derived layer the edges the page shows for it (`structure`:
  none; `system`: those crossing the boundary, painted in the reading's
  hue), with every other edge left out entirely, every card present, the
  line legend reduced to that layer, and the layer's question as the
  drawing's title and caption. An id the page does not have exits 2
  naming the readings it does.
- `[[figures]]` gains an optional `layer` key; `refresh` writes and
  `check` compares a layer figure like any other.
- Which edges a reading shows is decided once, in `systemap.model.reading`
  (`edge_in_layer`, `subject_of_layer`), and the page's script reads that
  table out of the detail JSON (`_meta.readings`, and `derived` per layer)
  instead of deciding again in the browser, so the figure and the page
  cannot disagree. Every SVG the generator draws now carries a `<title>`.
- The self-map ships `figures/structure.svg` and `figures/control.svg`
  beside `figures/system.svg`, and the README leads with the Structure
  figure and then the Control flow reading; the whole map, every layer at
  once, is no longer embedded there.

## 0.4.0

The map draws what exists today, reads in standard layers, and is built in
passes: the second pass is the point.

Breaking removals:

- `Component.tracker` is gone, and with it the `planned` and `partial`
  build states, the ghost rendering, the Today / End state toggle on the
  page and the end-state checkbox on figures, the planned legend entry,
  and the tracker chips and issue links in the panel. `build_state`
  returns only `built`. A component whose module or entry is not in the
  facts is a check failure under the `entry` rule ("X names module Y
  which is not in the facts", "X names entry Z which none of its modules
  defines", "X names no module"); the `tracker` rule is gone.
- The `issue_url` configuration key is gone and is refused as unknown.
- `Meaning.layers` no longer declares the standard readings. The ids
  `structure`, `system`, `data`, `control`, `agents`, `context`, `tools`
  and `all` are reserved; a custom layer taking one fails the meaning
  check. `layers`, `layer_of_kind` and `relations` are optional.
- A flow whose kind is neither standard nor declared in `flow_kinds`
  fails the placement check with the kinds named.
- `theme.resolve`, `schematic.layer_rows`, `check.run` and
  `schematic.render` changed signatures: the theme is resolved over every
  layer the page shows (`systemap.all_layers(model, meaning)`),
  `layer_rows` takes the model, and the `issue_url` arguments are gone.
- The theme constants are renamed for the new palette (`GRAPHITE`,
  `INK`, `AMBER`, `STEEL`, `PAPER`, `INK_ON_PAPER`; `TEAL`, `PANEL`,
  `SLATE`, `MUTED` are gone) and the scheme's `layers` table names every
  standard layer; a `[theme.layers]` override still applies per id.

Added:

- Layers. Two readings are derived from the model with no authoring:
  Structure (every component in its place, no edges) and System context
  (the actors and every edge that crosses the boundary, internal edges
  dimmed). Two flow kinds are standard and need no declaring: `data`
  (Data flow) and `control` (Control flow), with verbs of their own. Page
  order: Structure, System context, Data flow, Control flow, the model's
  own layers, All; the page opens on Structure.
- Agentic systems. `Component.kind` gains `agent`, `tool` and `context`;
  two more standard flow kinds, `context` (into an agent's window) and
  `tool` (an agent invoking a tool); three readings that appear only when
  the model has an agent: Agents, Context, Tools. The check refuses a
  context or tool flow whose agent end is not an agent. The cards carry a
  mark from the theme's `marks` table (ring, notch, dotted), never a
  colour, and the legend names them.
- Entry points in the facts (`entry_points`): console scripts, `__main__`
  modules, `main` functions, argparse subcommands with a literal name, the
  public functions of the package root. The facts drift check compares
  them.
- `systemap judgement` gains two second-pass prompts: "entry point X has
  no journey" and "crossing import: module A (component P) imports module
  B (component Q) and no flow joins P and Q"; the thin-layer line covers
  the standard kind layers.
- The look: cool graphite, one muted amber, low-chroma layer hues; a light
  scheme measured to clear 4.5:1 for every text hue (the given accent
  `#a8722a` measures 3.68:1 and is flagged in the commit that set it).
- The skill is a directory: `SKILL.md` (129 lines: when to use, the loop,
  what goes in the model, the commands, what to hand back, the rules, the
  index of references) and `references/` (`schema.md`, `example.md`,
  `layers.md`, `journeys-and-invariants.md`, `second-pass.md`,
  `pitfalls.md`). `systemap skill` and `systemap init` install the whole
  directory and remove a reference the package no longer ships; the
  plugin copy mirrors it and a test compares the trees.
- The self-map uses the standard kinds, a journey per entry point, and
  invariants that cite the README, a guard clause and a test; every
  judgement line is answered in its commit.

## 0.3.0

systemap is a tool for coding agents: the agent draws the map, the checker
refuses an incomplete or stale one, the person reviews the judgement.

- Identity: a logo mark and a hero image under `assets/`, and the default
  theme is the same palette (ink ground, panel surfaces, paper text, amber
  for the clicked component, teal for what it reaches). A light scheme is
  derived from it and picked with `scheme = "light"` under `[theme]`;
  every token name is unchanged, so existing overrides still apply.
- The skill is the primary document. It ships in the package as
  `systemap/skill/SKILL.md`, and `systemap init` installs it by default
  (`systemap skill` reinstalls it; `--print` writes it to stdout). It now
  carries the full model schema, a worked example of every part, the
  command to run at each step, and the what-to-hand-back section; a test
  runs the real check on the example. `init` takes `--no-ci` to skip the
  workflow and ends with the sentence to give the agent.
- `systemap judgement`: the list a maintainer must confirm, printed from
  the model and the facts: components with a single module, modules whose
  name shares no word with the component that claims them, flows without a
  sentence, layers that light fewer than two components, every ignored
  module with its reason. A report, not a gate: exit 0 always.
- Check rules: `entry` (a component whose modules exist names an entry one
  of them defines), `tracker` (a planned component names the item that
  will build it), `stale` (the facts against a fresh extraction, the page
  against a fresh render, every configured figure against the generator,
  in one command). Each failure prints its fix under its rule.
  `refresh` no longer says "already current" while the check fails.
- Figures: an `out` ending in `.svg` writes the bare drawing on its ground,
  for embedding as an image.
- systemap maps itself: `map/model.py`, `docs/map/` with the page and the
  README figure, `docs/index.html` and `docs/.nojekyll` for GitHub Pages,
  and the workflow `init` writes running on the repository.
- README rewritten around the agent: the hero, why an agent and not a
  script, the quick start, the check rules as a table, the model in one
  screen, commands and configuration.
- The repository is a Claude Code plugin and its own marketplace:
  `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, and the
  skill at `skills/systemap/SKILL.md` (a copy of the package file, kept
  byte-identical by a test; the manifest's version is tested against the
  package's). Install with `/plugin marketplace add 0xfauzi/systemap` then
  `/plugin install systemap@systemap`. The skill's front matter carries
  `license` and `compatibility`, and its description names the phrases
  that should trigger it. The workflow validates both manifests and the
  skill in strict mode.

## 0.2.0

- Breaking: the package's noun is "map". The defaults are now
  `model = "map/model.py"` and `out_dir = "docs/map"` (the facts file stays
  `map.json`), `systemap init` writes `map/model.py` and `docs/map/`, and
  the README, the scaffold and the workflow say "map". A project that
  relied on the old defaults sets `model` and `out_dir` in its
  configuration to keep its paths.
- Coverage: `systemap check` refuses an incomplete map. Every module in the
  facts must be claimed by exactly one component's `implemented_by`; the
  check prints each unmapped and each doubly claimed module and exits 1,
  or `coverage: N/N modules mapped` on success. An optional `[coverage]`
  table lists `ignore = [{ module = "pkg.mod", reason = "..." }]`; an
  ignore without a reason is a configuration error (exit 2), and an ignore
  naming a module the facts do not have is reported. A check with no facts
  fails closed.
- `implemented_by` entries may name a package with a `.*` suffix to claim
  the package and everything beneath it. The build state, the drift check,
  the change map and the coverage rule all read the same convention.
- `systemap skill [--dir PATH]` writes `SKILL.md` (default
  `.claude/skills/systemap/`): the agent skill that drafts the model, in
  order, and hands the maintainer its list of judgement calls to confirm.
  The README says where the judgement comes from: extract is mechanical,
  the model is agent-drafted and person-reviewed, the check refuses an
  incomplete map.
- The shipped example project is removed; the test suite carries its own
  sample system. The package's built-in example will be systemap mapping
  itself, in a later release.

## 0.1.0

First release. The engine is ported from an earlier in-repository tool
with the project literals replaced by configuration; the original map
rendered byte-identically inside the SVG view group.

- Schema: frozen dataclasses for `Container`, `Region`, `Component`,
  `Flow`, `Invariant`, `Journey`, `Step`, `Layer`, `Model` and `Meaning`;
  `build_state` derives built, partial or planned from the facts;
  `Model.layout_problems` and `meaning_problems` check the model.
- Configuration: `systemap.toml` or `[tool.systemap]` in `pyproject.toml`;
  package roots are discovered when not configured; unknown keys are
  refused.
- Engine: facts extraction with `ast`, orthogonal routing through the card
  grid, label seating, the SVG scene with its interaction script, the page,
  the change map, figures for lessons, and the mechanical layout check.
- Theme: a neutral dark default; every token overridable; layer colours
  named per layer id or taken from a palette in order.
- CLI: `init`, `extract`, `render`, `check`, `figure`, `refresh`; exit
  codes 0 (current), 1 (stale or failed), 2 (configuration error).
- Example: a full model of one project under `examples/`.
