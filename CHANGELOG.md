# Changelog

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
