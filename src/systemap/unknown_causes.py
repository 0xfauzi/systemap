"""Give the cause of an unknown record, and the correction for each cause.

A language adapter writes `cause` in each unknown record: a module `parse_error`, each
item of a module `unknown` list, the `problem` of each `test_file_issues` record, each
`entry_point_issues` record, and each `config_issues` record. A cause has the same
meaning for each language. Shared code reads `cause` and does not examine the reason
text. A record without `cause`, for example from an older facts format, has the cause
NOT_KNOWN. NOT_KNOWN gets its own correction, not the correction of a different cause.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from systemap import file_names, repo_files

# The file could not be read, or the repository rules refused it.
READ = "read"
# The file is not UTF-8 text, or the file name is not valid UTF-8.
ENCODING = "encoding"
# The file is larger than the size limit of a source file.
SIZE = "size"
# The parser could not parse the source.
SYNTAX = "syntax"
# The syntax tree of the file has more levels than the reader can read.
DEPTH = "depth"
# The parser read the syntax, but it has no record for this declaration or export form.
DECLARATION = "declaration"
# A reference has a target that is not a module in the facts.
TARGET = "target"
# A reference names a declaration file. Such a file gives only types and has no module.
DECLARATION_FILE = "declaration file"
# A reference names a script file in the repository that the extractor does not read as
# source code, for example a JavaScript file in a TypeScript repository.
SCRIPT_FILE = "script file"
# A configuration file extends a configuration package that could not be read.
PACKAGE = "package"
# The framework binding of a registration is not known.
BINDING = "binding"
# The names that a re-export gives are not known.
REEXPORT = "reexport"
# A file name, an export name, or an entry point name contains a control character.
NAME = "name"
# The record has no cause.
NOT_KNOWN = "not known"

CAUSES = (
    READ,
    ENCODING,
    SIZE,
    SYNTAX,
    DEPTH,
    DECLARATION,
    TARGET,
    DECLARATION_FILE,
    SCRIPT_FILE,
    PACKAGE,
    BINDING,
    REEXPORT,
    NAME,
    NOT_KNOWN,
)

# The correction for each cause. The check prints one line for each cause that occurs.
FIX = {
    READ: (
        "If systemap could not read a file, make sure that the file is in the repository "
        "and that systemap can read it."
    ),
    ENCODING: (
        "If a file is not UTF-8 text, write the file as UTF-8 text. If a file name is not "
        "valid UTF-8, change the name to a valid UTF-8 name."
    ),
    SIZE: (
        "If a file is larger than the source size limit, systemap does not read it. "
        "If the file is generated, record an answer for the line in [judgement] answered. "
        "If not, divide the file into smaller modules."
    ),
    SYNTAX: (
        "If the parser could not parse a file, examine the source at the line. If the "
        "source is not correct, correct the source. If the source is correct, the parser "
        "cannot read this syntax. Then record an answer for the line in [judgement] answered."
    ),
    DEPTH: (
        "If the source syntax of a file has too many levels, some facts of the file are "
        "not known. Examine the source. If the file is generated, record an answer for "
        "the line in [judgement] answered. If not, divide its expressions into smaller "
        "expressions."
    ),
    DECLARATION: (
        "If the parser has no record for a declaration form, examine the source at the "
        "line. Then record an answer for the line in [judgement] answered."
    ),
    TARGET: (
        "If a target has no module in the facts, examine the target file. If it is "
        "source code, add its directory to [package_roots]. If not, record an answer."
    ),
    DECLARATION_FILE: (
        "If a target is a declaration file, the names of the line come from that file and "
        "have no module. Examine the declaration file. Then record an answer for the line "
        "in [judgement] answered."
    ),
    SCRIPT_FILE: (
        "If a target is a script file with no source module, the extractor does not read "
        "it. Examine the file. Then record an answer for the line in [judgement] answered."
    ),
    PACKAGE: (
        "If a configuration package could not be read, install the dependencies of the "
        "repository. Then use systemap refresh."
    ),
    BINDING: (
        "If a framework binding is not known, examine the registration source. Then "
        "record an answer for the line in [judgement] answered."
    ),
    REEXPORT: (
        "If the names of a re-export are not known, examine the modules that it reads. "
        "Then record an answer for the line in [judgement] answered."
    ),
    NAME: (
        "If a name contains a control character, the facts do not use the name. Change "
        "the file name, the export name, or the entry point name. Then use systemap refresh."
    ),
    NOT_KNOWN: (
        "If a line has no cause, the facts have an older format. Use systemap refresh. "
        "Then examine the line again."
    ),
}


def of(record: Mapping[str, Any]) -> str:
    """Give the cause that the adapter wrote, or NOT_KNOWN."""
    cause = record.get("cause")
    return cause if isinstance(cause, str) and cause in FIX else NOT_KNOWN


# The read problems with a cause that is not READ.
_READ_CAUSES: tuple[tuple[type[BaseException], str], ...] = (
    (repo_files.TooLarge, SIZE),
    (file_names.NameNotSafe, NAME),
    (UnicodeError, ENCODING),
)


# The errors that a parse or a walk gives when a file has too many levels. Python gives
# RecursionError above its recursion limit. A parser can also give MemoryError.
DEPTH_ERRORS = (RecursionError, MemoryError)
# The fixed reason of a DEPTH problem. A finding line must not contain a changing value.
DEPTH_REASON = "The source syntax has too many levels."


def read_cause(exc: BaseException) -> str:
    """Give the cause of a read problem: ENCODING for text that is not UTF-8, SIZE for a
    file that is larger than the source size limit, NAME for a file name with a control
    character, or READ."""
    return next((cause for kind, cause in _READ_CAUSES if isinstance(exc, kind)), READ)


def read_problem(exc: BaseException) -> tuple[str, str]:
    """Give the reason and the cause of a read problem."""
    return f"source could not be read: {repo_files.reason(exc)}", read_cause(exc)


def fix_lines(causes: Iterable[str]) -> list[str]:
    """Give one fix line for each cause, in the order of CAUSES."""
    found = set(causes)
    return [f"  fix: {FIX[cause]}" for cause in CAUSES if cause in found]
