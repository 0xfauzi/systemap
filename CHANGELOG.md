# Changelog

## 0.1.0

First release. The engine is ported from kstrl's atlas tooling with the
project literals replaced by configuration; the kstrl map renders
byte-identically inside the SVG view group.

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
- Example: kstrl's full model under `examples/kstrl/`.
