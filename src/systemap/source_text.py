"""The source text rules read source files and compare extraction inputs.

The same committed source must give the same facts on each computer. The extractor reads
text as each source language reads it. A digest of text does not change with the newline
form of a checkout. The language adapters select the source paths.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from systemap import repo_files

# These provenance values can be different on two computers for the same commit: the
# interpreter version, the parser packages, and the compiler settings that installed npm
# packages supply. A difference in these values is a change only if the facts change.
# The other drift comparisons find a change of the facts.
LOCAL_INPUTS = ("parser", "compiler")


def decode(data: bytes) -> str:
    """This function gives the source text of the bytes of one source file.

    The text is UTF-8, with or without a byte order mark, as Python and TypeScript read
    it. The function removes the mark. It changes CRLF and CR newlines to LF, as universal
    newlines do. Bytes that are not UTF-8 give UnicodeError.

    The extraction and the change detection use this function. Thus the two get the same
    text from the same bytes, in a file or in a Git blob.
    """
    text = data.decode("utf-8-sig")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read(repo: Path, path: Path) -> str:
    """This function gives the source text of a regular file in the repository.

    `decode` gives the text. A file that `repo_files` refuses gives OSError. Bytes that
    are not UTF-8 give UnicodeError.
    """
    return decode(repo_files.read_bytes(repo, repo_files.relative(repo, path)))


def read_problems(path: Path, repo: Path) -> tuple[str, list[str]]:
    """This function gives the source text and its read problems.

    `decode` gives the text. Text that is not UTF-8 gives empty text and one problem. A
    file that `repo_files` refuses also gives empty text and one problem. A different
    OSError goes to the caller.
    """
    try:
        return read(repo, path), []
    except (UnicodeError, repo_files.RepoPathError) as exc:
        return "", [f"source could not be read: {repo_files.reason(exc)}"]


def text_digest(data: bytes) -> str:
    """This function hashes text bytes with CRLF and CR newlines changed to LF.

    LF text keeps the digest of its bytes, so the digests that LF checkouts recorded do
    not change.
    """
    return hashlib.sha256(data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()


def inputs_changed(stored: object, fresh: object) -> bool:
    """This function compares two provenance records without the values of one computer."""
    return _shared(stored) != _shared(fresh)


def _shared(provenance: object) -> object:
    if not isinstance(provenance, dict):
        return provenance
    return {key: value for key, value in provenance.items() if key not in LOCAL_INPUTS}
