"""The change detection reads the text of each changed file on each side of a comparison.

A side can have the file, not have the file, or have a file that systemap cannot read.
A file that the side does not have gives empty text: its public names are added or
removed. A file that systemap cannot read gives a problem. Then the changes of the file
are not known. The change detection does not use empty text for such a file.

`source_text.decode` gives the text from the bytes, as for the extraction. Thus a byte
order mark and the newline form do not change the result.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable
from pathlib import Path

from systemap import delta_git, repo_files, source_text

PROBLEM = "source could not be read: {}"


@dataclasses.dataclass(frozen=True)
class Text:
    """The text of one file on one side of a comparison.

    `raw` is empty if the side does not have the file. `problem` is not empty if the side
    has the file but systemap cannot read its text.
    """

    raw: str = ""
    problem: str = ""


def decoded(data: bytes | None) -> Text:
    """This function gives the text of the bytes of a file, or the read problem.

    None is an entry that is not a regular file, for example a symbolic link in Git.
    """
    if data is None:
        return Text(problem=PROBLEM.format("the Git entry is not a regular file"))
    try:
        return Text(source_text.decode(data))
    except UnicodeError as exc:
        return Text(problem=PROBLEM.format(repo_files.reason(exc)))


def at(repo: Path, revision: str, paths: Iterable[str]) -> dict[str, Text]:
    """This function gives the committed text of each path at a revision.

    One Git process reads all the blobs. A path that the revision does not have gives
    empty text.
    """
    wanted = list(paths)
    found = delta_git.blobs_at(repo, revision, wanted)
    return {path: decoded(found[path]) if path in found else Text() for path in wanted}


def on_disk(root: Path, path: str) -> Text:
    """This function gives the text of a file in the working tree.

    A missing file gives empty text. `repo_files` refuses a link to a file that is not in
    the repository. That refusal and each other read error give a problem.
    """
    try:
        data = repo_files.read_bytes(root, path)
    except (FileNotFoundError, NotADirectoryError):
        return Text()
    except OSError as exc:
        return Text(problem=PROBLEM.format(repo_files.reason(exc)))
    return decoded(data)
