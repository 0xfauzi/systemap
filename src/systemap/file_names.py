"""The file name rules find a file name that is not valid as a source path.

A POSIX file name is a sequence of bytes. Python gives each byte that is not UTF-8 as a
surrogate character (the `surrogateescape` error handler). The facts file is UTF-8 text,
so it cannot contain such a name. Thus a walk does not give such a name to the
extraction as a source path. A source walk gives the file to a `refused` list. The
extraction then records the file with the cause `encoding` and does not read it.

A file name that contains a control character or a line separator gets the same rule,
with the cause `name`. Such a name can change the terminal output, and a newline in a
module identifier can divide one finding line into two lines (`terminal_text`).
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from pathlib import Path

from systemap.terminal_text import has_control, printable

REASON = "the file name is not valid UTF-8"
CONTROL_REASON = "the file name contains a control character"


class NameNotText(UnicodeError):
    """A file name that is not valid UTF-8 text. The message is the reason."""


class NameNotSafe(NameNotText):
    """A file name that contains a control character. The message is the reason."""


def _text(name: str) -> bool:
    """Find a name that the UTF-8 encoding can encode with no error."""
    try:
        name.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def valid(name: str) -> bool:
    """Find a name that the UTF-8 encoding can encode with no error, and that contains no
    control character."""
    return _text(name) and not has_control(name)


def checked(name: str) -> str:
    """Give the name if it is valid. A name that is not UTF-8 gives NameNotText. A name
    with a control character gives NameNotSafe."""
    if not _text(name):
        raise NameNotText(REASON)
    if has_control(name):
        raise NameNotSafe(CONTROL_REASON)
    return name


def shown(name: str) -> str:
    """Give the name as valid text. A valid name does not change.

    A byte that is not UTF-8 shows as `\\xNN`. A different surrogate character shows as
    `\\uNNNN`. A control character shows as `terminal_text.printable` gives it."""
    try:
        data = name.encode("utf-8", "surrogateescape")
    except UnicodeEncodeError:
        return printable(name.encode("utf-8", "backslashreplace").decode("utf-8"))
    return printable(data.decode("utf-8", "backslashreplace"))


def folders(names: Iterable[str]) -> list[str]:
    """Give the valid names in the same order. A walk does not go into the other folders."""
    return [name for name in names if valid(name)]


def selected(
    paths: Iterable[Path],
    names: list[Path],
    keep: Callable[[Path], bool],
    refused: list[Path] | None,
) -> list[Path]:
    """Give the paths that `keep` selects.

    `names` holds the files that the walk of `paths` did not give, because their paths
    are not valid UTF-8. The function reads `names` after the walk. If `refused` is a
    list, the function adds each file in `names` that `keep` selects to it."""
    found = [path for path in paths if keep(path)]
    if refused is not None:
        refused.extend(path for path in names if keep(path))
    return found


def files(top: Path, here: str, names: Iterable[str], refused: list[Path] | None) -> list[str]:
    """Give the names of the files in `here` whose path below `top` is valid, in order.

    If `refused` is a list, the function adds the path of each other file to it. A file
    in a folder with a name that is not valid also goes to `refused`."""
    names = list(names)
    kept = [name for name in names if valid(name)] if valid(os.path.relpath(here, top)) else []
    if refused is not None and len(kept) != len(names):
        good = set(kept)
        refused.extend(Path(here, name) for name in names if name not in good)
    return kept
