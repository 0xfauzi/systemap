"""Give the one action that ends the report of `systemap check` or `systemap refresh`.

The action is for the check error with the highest priority. An action never tells the
person to use the same command again when a second use gives the same result. For
example, a refresh does not change an output that it wrote with a different path.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from systemap.config import CONFIG_FILE, Config

if TYPE_CHECKING:
    from systemap import check, nest

STALE_AFTER_REFRESH = (
    "A second refresh writes the same outputs. Do the step in the fix line of the stale "
    "after refresh group."
)


def fix_line(tree: nest.Tree, cfg: Config, results: Mapping[str, check.Result]) -> str:
    """Give the action for the check error with the highest priority.

    Model errors come first, then facts, combined checks, and outputs. The top map comes
    before nested maps. Only stale outputs give "run: systemap refresh". A scoped tree has
    results only for the selected map. Its coverage counts only if it is the top map.
    """
    for m in tree.reported:
        if results[m.id].problems:
            return f"Correct {m.rel}. Then use systemap check."
    coverage = _top_fix(cfg, results.get(tree.top.id))
    if coverage:
        return coverage
    for m in tree.reported:
        result = results[m.id]
        if result.entry or result.interface or result.nesting:
            return f"Correct {m.rel}. Then use systemap check."
    return "run: systemap refresh"


def _top_fix(cfg: Config, top: check.Result | None) -> str:
    """Give the action for the facts or the coverage of the top map, or no action.

    A scoped tree without the top map gives no action."""
    if top is None:
        return ""
    if not top.coverage.checked:
        return "run: systemap extract"
    return _coverage_fix(cfg, top)


def _coverage_fix(cfg: Config, top: check.Result) -> str:
    """Give the action for facts without modules or for coverage errors, or no action.

    Facts without modules and a model with source components need new package roots."""
    if top.coverage.total == 0 and top.entry:
        return (
            f"Set [package_roots] in {cfg.source or CONFIG_FILE} to the directories that "
            f"contain the source files. Then use systemap check."
        )
    if top.coverage.problems:
        return (
            f"Give each module a component in {cfg.model}, or give a reason to ignore it "
            f"in [coverage]. Then use systemap check."
        )
    return ""
