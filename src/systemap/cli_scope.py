"""The `--map ID` option: a command examines one map of the tree.

With `--map ID`, `nest.load` reads only the model files of that map, of its ancestors,
and of its descendants. Thus an error in the file of a different map does not stop the
command. The command reports only the selected map. `.` selects the top map.

A run with `--map` is not the result of the full tree. It does not examine the pages,
and it does not examine the global entry coverage. Only a run without `--map` gives the
result for completion. `refresh`, `extract`, and `decisions submit` write the shared
files of all maps. Thus they refuse `--map`.
"""

from __future__ import annotations

import argparse
import dataclasses
from typing import Any

from systemap import check, judgement, judgement_json, nest
from systemap.config import Config

# The commands that accept `--map` with the scoped load. `review` has its own option, and
# `decisions` adds the option to its `pending` and `status` actions (`add_option`).
SCOPED = ("check", "judgement", "rules", "place", "describe", "journeys")
# The commands that refuse `--map`, because they write the shared files of all maps.
REFUSED = ("refresh", "extract")

HELP = (
    "Examine only the map with this ID, for example Gateway or Gateway/Routes. Use . for "
    "the top map. The command reads only the model files of this map, of its parent maps, "
    "and of its nested maps. Only a run without --map gives the result for completion."
)
ENTRY_NOTE = "entry coverage: not examined in a run with --map"
PAGES_NOTE = "pages: not examined in a run with --map"


def add_options(sub: Any) -> None:
    """Add `--map` to each command of `SCOPED`, and the refusal to each of `REFUSED`."""
    for name in SCOPED:
        add_option(sub.choices[name])
    for name in REFUSED:
        refuse_option(sub.choices[name], f"systemap {name}")


def add_option(parser: argparse.ArgumentParser) -> None:
    """Add `--map ID` to a command. The value goes to `args.only` (`nest.load`)."""
    parser.add_argument("--map", dest="only", default=None, metavar="ID", help=HELP)


def refuse_option(parser: argparse.ArgumentParser, command: str) -> None:
    """Add a `--map` option that stops the command with exit code 2 and the reason."""

    def refused(_value: str) -> str:
        raise argparse.ArgumentTypeError(
            f"{command} writes the shared files of all maps. Thus it examines the full "
            "tree. Do the command again without --map."
        )

    parser.add_argument("--map", dest="refused_map", type=refused, help=argparse.SUPPRESS)


def load(cfg: Config, args: argparse.Namespace) -> nest.Tree:
    """Load the tree, or only the scope of `--map` if the command has the option."""
    return nest.load(cfg, getattr(args, "only", None))


def label(tree: nest.Tree) -> str:
    """Give the name of the selected map for a person."""
    return tree.selected or f"{nest.TOP_ID} (the top map)"


def notes(tree: nest.Tree, *examined: str) -> list[str]:
    """Give the lines that tell a person the scope of a run with `--map`.

    `examined` gives the lines about the checks that the run did not do. A run without
    `--map` gives no lines."""
    if not tree.partial:
        return []
    return [
        f"map: This run examines only the map {label(tree)}. Only a run without --map "
        "gives the result for completion.",
        *examined,
    ]


def stale(cfg: Config, tree: nest.Tree) -> list[str]:
    """Compare the outputs with fresh output. A run with `--map` does not examine them,
    because the pages show all maps."""
    return [] if tree.partial else check.stale(cfg, tree)


def in_scope(tree: nest.Tree, line: str) -> bool:
    """Tell if a judgement line or an answer item is a line of the selected map.

    A line of a nested map starts with its map prefix. A line of the top map has no map
    prefix (`judgement.unprefixed`)."""
    chosen = tree.get(tree.selected or "")
    return line.startswith(chosen.prefix) if chosen.id else judgement.unprefixed(line) == line


def judged(found: judgement_json.Judged, tree: nest.Tree, cfg: Config) -> judgement_json.Judged:
    """Remove the stale answers that are not about the selected map.

    In a run with `--map`, an answer for a different map matches no line. That answer is
    not stale. A family answer can apply to each map. Thus a run with `--map` cannot tell
    if it is stale, and it gives no family answer as stale."""
    if not tree.partial:
        return found
    family = {answer.label for answer in cfg.judgement_answered if not answer.items}
    kept = [x for x in found.result.stale if x not in family and in_scope(tree, x)]
    return dataclasses.replace(found, result=dataclasses.replace(found.result, stale=kept))


def payload(obj: dict[str, Any], tree: nest.Tree) -> dict[str, Any]:
    """Add the scope of a run with `--map` to the JSON object of a command."""
    if tree.partial:
        obj["scope"] = {"map": tree.selected, "entry_coverage": "not examined"}
    return obj


def records(found: dict[str, dict[str, Any]], tree: nest.Tree) -> dict[str, dict[str, Any]]:
    """Keep the store records of the selected map, or all records of the full tree."""
    if not tree.partial:
        return found
    return {key: row for key, row in found.items() if row.get("map", "") == tree.selected}
