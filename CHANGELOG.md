# Changelog

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
