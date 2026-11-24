"""The `--map ID` option: a command examines one map of the tree.

With `--map ID`, `nest.load` reads only the model files of that map, of its ancestors,
and of its descendants. Thus an error in the file of a different map does not stop the
command. The command reports only the selected map. `.` selects the top map.

A run with `--map` is not the result of the full tree. It examines the facts, but it
does not examine the pages, and it does not examine the global entry coverage. Only a
run without `--map` gives the result for completion. `refresh`, `extract`, and
`decisions submit` write the shared files of all maps. Thus they refuse `--map`.
"""

from __future__ import annotations

import argparse
import dataclasses
from collections.abc import Callable
from typing import Any

from systemap import (
    check,
    claims_cli,
    extraction,
    judgement,
    judgement_evidence,
    judgement_json,
    nest,
    parts_cli,
    parts_plan,
)
from systemap.config import Config
from systemap.map_scope import ENTRY_NOTE as ENTRY_NOTE
from systemap.map_scope import HELP as HELP
from systemap.map_scope import PAGES_NOTE as PAGES_NOTE
from systemap.map_scope import SEQUENCES_NOTE as SEQUENCES_NOTE
from systemap.map_scope import add_option as add_option
from systemap.map_scope import label as label
from systemap.map_scope import load as load
from systemap.map_scope import notes as notes
from systemap.map_scope import payload as payload
from systemap.map_scope import records as records
from systemap.map_scope import refuse_option as refuse_option
from systemap.map_scope import show_notes as show_notes

# The commands that accept `--map` with the scoped load. `review` has its own option, and
# `decisions` adds the option to its `pending` and `status` actions (`add_option`).
SCOPED = ("check", "judgement", "rules", "place", "describe", "journeys", "claims")
# The commands that refuse `--map`, because they write the shared files of all maps.
REFUSED = ("refresh", "extract")


PARTS_HELP = (
    "Select the map with this ID, for example Gateway or Gateway/Routes. Without --stub "
    "and --results, give the record of this nested part from the plan of its parent map."
)


def add_parsers(sub: Any, add_root: Callable[[argparse.ArgumentParser], None]) -> None:
    """Add the commands `systemap parts` and `systemap claims`. Then add `--map` to the
    commands (`add_options`)."""
    parts_cli.add_parser(sub, add_root, PARTS_HELP)
    claims_cli.add_parser(sub, add_root)
    add_options(sub)


def add_options(sub: Any) -> None:
    """Add `--map` to each command of `SCOPED`, and the refusal to each of `REFUSED`."""
    for name in SCOPED:
        add_option(sub.choices[name])
    for name in REFUSED:
        refuse_option(sub.choices[name], f"systemap {name}")


def check_notes(cfg: Config, tree: nest.Tree) -> list[str]:
    """Give the scope lines of `check --map`, and a warning for each stale part plan of the
    selected map. A plan that does not exist gives no line, and a warning does not change
    the exit code."""
    return [*notes(tree, PAGES_NOTE), *parts_plan.stale_warnings(cfg, tree)]


def stale(cfg: Config, tree: nest.Tree) -> list[str]:
    """Compare the facts and the outputs with fresh output. A run with `--map` examines
    only the facts, because the pages show all maps."""
    return extraction.saved_drift(cfg)[0] if tree.partial else check.stale(cfg, tree)


def in_scope(tree: nest.Tree, line: str) -> bool:
    """Tell if a judgement line or an answer item is a line of the selected map.

    The map of a line is the loaded map with the longest prefix (`map_of`). A line of the
    top map also has no map prefix, because the tree has no sibling maps."""
    found = judgement_evidence.map_of(tree, line)
    if found.id != (tree.selected or ""):
        return False
    return bool(found.id) or judgement.unprefixed(line) == line


def _entry_line(line: str) -> bool:
    """Tell if a judgement line is an entry point line. A run with `--map` gives none."""
    return judgement.unprefixed(line).startswith(judgement.KIND_PREFIX["entry point"])


def judged(found: judgement_json.Judged, tree: nest.Tree, cfg: Config) -> judgement_json.Judged:
    """Remove the stale answers that a run with `--map` cannot examine.

    In a run with `--map`, an answer for a different map matches no line. An answer for
    an entry point line also matches no line, because the run gives no entry point lines.
    Such answers are not stale. A family answer can apply to each map. Thus a run with
    `--map` cannot tell if it is stale, and it gives no family answer as stale.

    The run also removes the import crossings and the `module use` lines of the other
    loaded maps. Thus `Judged.blocking` reads only the import crossings of the selected
    map."""
    if not tree.partial:
        return found
    family = {answer.label for answer in cfg.judgement_answered if not answer.items}
    kept = [
        x
        for x in found.result.stale
        if x not in family and in_scope(tree, x) and not _entry_line(x)
    ]
    return dataclasses.replace(
        found,
        result=dataclasses.replace(found.result, stale=kept),
        crossings={k: v for k, v in found.crossings.items() if in_scope(tree, k)},
        uses={k: v for k, v in found.uses.items() if in_scope(tree, k)},
        hidden=[line for line in found.hidden if in_scope(tree, line)],
    )
