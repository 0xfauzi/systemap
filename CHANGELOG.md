# Changelog

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
