"""The scope of a run with `--map ID`: the load of one map of the tree, and its notices.

With `--map ID`, `nest.load` reads only the model files of that map, of its ancestors,
and of its descendants. The command reports only the selected map. `.` selects the top
map. A run with `--map` is not the result of the full tree.

These functions read only the map tree and the arguments of a command. They are in this
module, and not in `systemap.cli_scope`, so that a command module of a different
component does not import the command line.
"""

from __future__ import annotations

import argparse
from typing import Any

from systemap import nest
from systemap.config import Config
from systemap.terminal_text import show

HELP = (
    "Examine only the map with this ID, for example Gateway or Gateway/Routes. Use . for "
    "the top map. The command reads only the model files of this map, of its parent maps, "
    "and of its nested maps. Only a run without --map gives the result for completion."
)


ENTRY_NOTE = "entry coverage: not examined in a run with --map"


PAGES_NOTE = "pages: not examined in a run with --map"


SEQUENCES_NOTE = (
    "sequence coverage: a run with --map examines only the sequences of this map, of its "
    "parent maps, and of its nested maps"
)


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


def show_notes(tree: nest.Tree, *examined: str) -> None:
    """Write the lines of `notes`, if the run has `--map`."""
    for line in notes(tree, *examined):
        show(line)


def payload(obj: dict[str, Any], tree: nest.Tree, **not_examined: str) -> dict[str, Any]:
    """Add the scope of a run with `--map` to the JSON object of a command.

    `not_examined` gives the checks that the run did not do, for example
    `entry_coverage="not examined"`."""
    if tree.partial:
        obj["scope"] = {"map": tree.selected, **not_examined}
    return obj


def records(found: dict[str, dict[str, Any]], tree: nest.Tree) -> dict[str, dict[str, Any]]:
    """Keep the store records of the selected map, or all records of the full tree."""
    if not tree.partial:
        return found
    return {key: row for key, row in found.items() if row.get("map", "") == tree.selected}
