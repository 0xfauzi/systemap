"""The live render makes the pages and the figure of one version of the working tree.

`systemap live` calls the render after each change. The render writes no file. A
`LiveRenderer` keeps a fact cache (`fact_cache`) between two renders. Thus the
extraction parses only the changed files. The routes of the figures stay in the route
cache (`route.routed`). The result is the same as the result of `render_tree` without a
cache.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from systemap import (
    change,
    config,
    delta,
    explain,
    extraction,
    fact_cache,
    figure,
    history,
    nest,
    out_paths,
    page,
)
from systemap.config import Config, ConfigError
from systemap.model import problems as model_problems

# The figure beside the page: the change figure, or the system figure without a change.
FIGURE = "change.svg"


@dataclass(frozen=True)
class Rendered:
    """The pages, the figure and the map update lines of one version.

    `files` maps a path in the served directory to its text. `lines` are the map update
    lines, each with its text and its action. `components` are the changed components
    of the top map. `models` are the model files of the map tree.
    """

    files: dict[str, str] = dataclasses.field(default_factory=dict)
    updates: int = 0
    lines: tuple[dict[str, str], ...] = ()
    components: tuple[str, ...] = ()
    comparison_base: str = ""
    models: tuple[Path, ...] = ()
    seconds: float = 0.0
    svg: str = ""
    svg_bytes: int = 0


def render_tree(root: Path, base: str, cache: fact_cache.FactCache | None = None) -> Rendered:
    """Render the pages and the figure of the working tree. Write no file.

    The facts come from the source files and the models from the model files. With a
    base, the Changes view and the map update lines compare the working tree with the
    merge base of the base and HEAD. `systemap delta` uses the same comparison of the
    facts for all maps. With a cache, the extraction uses the kept facts of each file
    with the same text.
    """
    cfg = config.load(root)
    tree = nest.load(cfg)
    _no_problems(tree)
    facts = extraction.build(cfg, cache)
    # One source comparison for all maps: it does not use the model of a map.
    source = change.source_change(cfg, base, facts, change.WORKING_TREE, cache) if base else None
    compared = {m.id: _compare(cfg, m, base, facts, source) for m in tree.maps}
    files = {
        out_paths.checked(cfg, m.page_path(cfg)).relative_to(cfg.out_path).as_posix(): page.build(
            cfg,
            m.model,
            m.meaning,
            m.theme,
            facts,
            compared[m.id],
            nesting=page.nesting_of(cfg, tree, m, facts),
        )
        for m in tree.maps
    }
    top = compared[tree.top.id]
    files[FIGURE] = _figure(cfg, tree, facts, (base, source), top)
    lines = _updates(cfg, tree, facts, base, top.get("comparison_base", ""))
    return Rendered(
        files=files,
        updates=len(lines),
        lines=lines,
        components=tuple(sorted(top.get("direct", ()))),
        comparison_base=top.get("comparison_base", ""),
        models=tuple(m.path for m in tree.maps),
    )


def _no_problems(tree: nest.Tree) -> None:
    """Give the model contradictions as one error, as `systemap render` gives them."""
    found = {m.rel: model_problems(m.model, m.meaning) for m in tree.maps}
    lines = [f"{m.prefix}{line}" for m in tree.maps for line in found[m.rel]]
    if lines:
        files = ", ".join(rel for rel, problems in found.items() if problems)
        raise ConfigError("\n".join([*lines, f"Correct {files}. Then use systemap check."]))


def _compare(
    cfg: Config,
    m: nest.Map,
    base: str,
    facts: dict[str, Any],
    source: change.SourceChange | None,
) -> dict[str, Any]:
    if not base:
        return {"has_change": False}
    return change.for_page(cfg, m, base, facts, change.WORKING_TREE, source)


def _figure(
    cfg: Config,
    tree: nest.Tree,
    facts: dict[str, Any],
    compared: tuple[str, change.SourceChange | None],
    ch: dict[str, Any],
) -> str:
    """Give the change figure as SVG, or the system figure if the comparison has no change.

    The figure uses the source comparison of the pages."""
    base, source = compared
    m = tree.top
    svg, _collisions = figure.make(
        cfg,
        m.model,
        m.meaning,
        m.theme,
        facts,
        mode="change" if ch.get("has_change") else "system",
        base=base,
        head=change.WORKING_TREE,
        bare=True,
        opens=nest.opens(tree, m, links=False),
        source=source,
    )
    return svg


def _updates(
    cfg: Config, tree: nest.Tree, facts: dict[str, Any], base: str, merge_base: str
) -> tuple[dict[str, str], ...]:
    """Give the delta lines that need an action, for the working tree and the merge base."""
    if not merge_base:
        return ()
    found = delta.compute_tree(
        cfg,
        tree,
        history.facts_at(cfg, merge_base),
        facts,
        base_ref=base,
        head_ref=change.WORKING_TREE,
    )
    return tuple({"text": line.text, "action": _action(line.kind)} for line in found.open)


def _action(kind: str) -> str:
    lesson = explain.lesson(kind)
    return lesson.do if lesson else ""


class LiveRenderer:
    """Render the working tree again and again with one fact cache.

    The live map renders one version at a time. Thus one cache is sufficient."""

    def __init__(self, root: Path, base: str) -> None:
        self.root = root
        self.base = base
        self.cache = fact_cache.FactCache()

    def __call__(self) -> Rendered:
        return render_tree(self.root, self.base, self.cache)
