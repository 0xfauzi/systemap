"""The output lines and the project root of a command.

Each command module writes its lines with `say` and `warn`, and finds the project root
with `root`. The functions are in this module, and not in `systemap.cli`, so that a
command module of a different component does not import the command line.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from systemap import config, terminal_text


def say(*lines: str) -> None:
    """Write the lines to stdout. A control character in a line shows as an escape."""
    for line in lines:
        print(terminal_text.lines(line))


def warn(*lines: str) -> None:
    """Write the lines to stderr. A control character in a line shows as an escape."""
    for line in lines:
        print(terminal_text.lines(line), file=sys.stderr)


def root(args: argparse.Namespace) -> Path:
    if args.root:
        return Path(args.root).resolve()
    found = config.find_root(Path.cwd().resolve())
    return found or Path.cwd().resolve()
