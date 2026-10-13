"""The TypeScript re-export target reader replaces each re-export specifier with its module.

A re-export from an npm package keeps the package name and has no unknown record. A `*`
re-export from an npm package gives no public name. Each other re-export without a
module gives one unknown record for each statement. The record has the line of the
statement and the public names that the statement gives. A target that is a declaration
file has its own cause, because such a file is never a module.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from systemap import unknown_causes
from systemap.typescript_reexports import reexports
from systemap.typescript_syntax import _one_line, string_value, syntax_tree

# The text limit of the source excerpt in an unknown record.
EXCERPT = 120


@dataclass(frozen=True)
class Targets:
    """This record gives the three resolution functions of one importing module.

    `module` gives the module of a specifier, or None. `package` tells if a specifier
    names an npm package. `declaration` gives the declaration file that a specifier
    names, or an empty string.
    """

    module: Callable[[str], str | None]
    package: Callable[[str], bool]
    declaration: Callable[[str], str]


def resolve_reexports(surface: dict[str, Any], raw: str, path: str, targets: Targets) -> None:
    """This function replaces each re-export specifier with its module, and adds the
    unknown records of the specifiers without a module."""
    missing: set[str] = set()
    kept: list[dict[str, Any]] = []
    for entry in surface["names"]:
        source = entry.get("reexport_of")
        if source and not _resolved(entry, source, targets):
            star = entry.pop("star", None)
            entry["kind"] = "unknown"
            if targets.package(source):
                if star:
                    continue
            else:
                missing.add(source)
        kept.append(entry)
    surface["names"] = kept
    surface["unknown"].extend(_problems(raw, path, missing, targets.declaration))


def _resolved(entry: dict[str, Any], source: str, targets: Targets) -> bool:
    found = targets.module(source)
    if found:
        entry["reexport_of"] = found
    return bool(found)


def _problems(
    raw: str, path: str, missing: set[str], declaration: Callable[[str], str]
) -> list[dict[str, Any]]:
    """This function gives one unknown record for each statement with a missing target.

    A target that no top-level statement names gives a record without a line (0).
    """
    if not missing:
        return []
    out: list[dict[str, Any]] = []
    found: set[str] = set()
    for line, source, names, text in _statements(raw, path):
        if source in missing:
            found.add(source)
            out.append(_problem(line, source, names, text, declaration(source)))
    out += [_problem(0, source, [], "", declaration(source)) for source in sorted(missing - found)]
    return out


def _statements(raw: str, path: str) -> Iterable[tuple[int, str, list[str], str]]:
    """This function gives the line, the target, the public names, and the text of each
    top-level `export ... from` statement."""
    root = syntax_tree(raw, path)
    source = raw.encode("utf-8")
    for node in root.named_children:
        if node.type != "export_statement":
            continue
        target = string_value(node.child_by_field_name("source"))
        if target:
            names = [entry["name"] for entry in reexports(node, source)]
            text = (node.text or b"").decode("utf-8")
            yield node.start_point.row + 1, target, names, _one_line(text)[:EXCERPT]


def _problem(line: int, source: str, names: list[str], text: str, file: str) -> dict[str, Any]:
    if file:
        reason = (
            f"the re-export target {source!r} is the declaration file {file}. A declaration "
            "file gives only types and has no module record."
        )
        cause = unknown_causes.DECLARATION_FILE
    else:
        reason = f"the re-export target {source!r} is outside the extracted module set."
        cause = unknown_causes.TARGET
    if names:
        reason += f" Names: {', '.join(names)}."
    return {"line": line, "reason": reason, "source": text or source, "cause": cause}
