"""Command failures give one message, one correction, and one exit code.

Each known error type has a correction sentence for the person who runs the command.
The correction names the input that gives the error: a command option, systemap.toml or
the model module, a tsconfig file, or a Git ref. Exit code 1 means that the command could
not make its output. Exit code 2 means a configuration, model, option, or revision error.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

from systemap import change, delta, delta_link, figure, place
from systemap.config import ArgumentError, ConfigError

STALE, BAD_CONFIG = 1, 2

CONFIG_FIX = "Correct systemap.toml or the model module. Then run the command again."
TSCONFIG_FIX = "Correct the tsconfig file in the message. Then run the command again."
OPTION_FIX = "Correct the command option. Then run the command again."
# The module that reads tsconfig.json files. Its errors are about those files.
TSCONFIG_READER = "systemap.typescript_config"

# The first type that agrees with the error gives the correction and the exit code.
# A subclass comes before its base class.
FAILURES: tuple[tuple[type[Exception], str, int], ...] = (
    (ArgumentError, OPTION_FIX, BAD_CONFIG),
    (delta_link.LinkError, OPTION_FIX, BAD_CONFIG),
    (ConfigError, CONFIG_FIX, BAD_CONFIG),
    (figure.FigureError, "", STALE),
    (place.PlaceError, "", STALE),
    (
        delta.DeltaError,
        "Give delta a Git ref that Git can resolve. Then run the command again.",
        BAD_CONFIG,
    ),
    (
        change.ChangeError,
        "If the revision is remote, use git fetch. Then use refs that Git can resolve.",
        BAD_CONFIG,
    ),
)
KNOWN = tuple(kind for kind, _fix, _code in FAILURES)


def run(command: Callable[[argparse.Namespace], int], args: argparse.Namespace) -> int:
    """Run one command. For a known error, write the message and its correction to stderr."""
    try:
        return int(command(args))
    except KNOWN as exc:
        return report(exc)


def report(exc: Exception) -> int:
    """Write the error message and its correction. Give the exit code."""
    _kind, fix, code = next(entry for entry in FAILURES if isinstance(exc, entry[0]))
    if fix == CONFIG_FIX and from_tsconfig(exc):
        fix = TSCONFIG_FIX
    print(f"systemap: {exc}", file=sys.stderr)
    if fix:
        print(fix, file=sys.stderr)
    return code


def from_tsconfig(exc: BaseException) -> bool:
    """Find if the cause of a configuration error comes from the tsconfig reader."""
    cause = exc.__cause__
    trace = cause.__traceback__ if cause is not None else None
    while trace is not None:
        if trace.tb_frame.f_globals.get("__name__") == TSCONFIG_READER:
            return True
        trace = trace.tb_next
    return False
