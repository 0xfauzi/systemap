# Changelog

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
