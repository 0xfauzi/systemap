"""The TypeScript re-export target reader replaces each re-export specifier with its module.

A re-export from an npm package keeps the package name and has no unknown record. A `*`
re-export from an npm package gives no public name. Each other re-export without a
module gives one unknown record for each statement and target. The record has the line of
the statement and the public names that the statement gives. A target that is a
declaration file has its own cause, because such a file is never a module.

An indirect re-export, `import type { X } from './x'` and then `export type { X }`, gives
the same record as `export type { X } from './x'`: the line of the export statement and
its names. A name without a module has the kind `unknown` here. The re-export resolver
(`reexports`) gives a type-only name of kind `unknown` the kind `type`.

Two `export * from` statements give the same public name `*`. Thus each target without
a module is kept in a set, and each statement of such a target gives its own record. A
public name with a control character is not in a record (`control_names`).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from systemap import unknown_causes
from systemap.terminal_text import has_control
from systemap.typescript_reexports import export_specifiers, reexports
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
    missing = _Missing({}, set())
    kept: list[dict[str, Any]] = []
    for entry in surface["names"]:
        source = entry.get("reexport_of")
        if source and not _resolved(entry, source, targets):
            star = entry.pop("star", None)
            entry["kind"] = "unknown"
            if targets.package(source):
                if star:
                    continue
            elif not has_control(entry["name"]):
                missing.names[entry["name"]] = source
                missing.targets.add(source)
        kept.append(entry)
    surface["names"] = kept
    surface["unknown"].extend(_problems(raw, path, missing, targets.declaration))


@dataclass(frozen=True)
class _Missing:
    """The targets without a module: `names` gives the target of each public name, and
    `targets` holds each target. Two statements can give the same name, such as `*`."""

    names: dict[str, str]
    targets: set[str]


def _resolved(entry: dict[str, Any], source: str, targets: Targets) -> bool:
    found = targets.module(source)
    if found:
        entry["reexport_of"] = found
    return bool(found)


def _problems(
    raw: str, path: str, missing: _Missing, declaration: Callable[[str], str]
) -> list[dict[str, Any]]:
    """This function gives one unknown record for each statement and missing target.

    A target that no top-level statement names gives a record without a line (0).
    """
    targets = missing.targets
    if not targets:
        return []
    out: list[dict[str, Any]] = []
    found: set[str] = set()
    for line, source, names, text in _statements(raw, path, missing.names):
        if source in targets:
            found.add(source)
            out.append(_problem(line, source, names, text, declaration(source)))
    out += [_problem(0, source, [], "", declaration(source)) for source in sorted(targets - found)]
    return out


def _statements(
    raw: str, path: str, imported: dict[str, str]
) -> Iterable[tuple[int, str, list[str], str]]:
    """This function gives the line, the target, the public names, and the text of each
    top-level export statement for each of its targets.

    An `export ... from` statement names its target. A statement without `from` gives the
    target of each imported public name from `imported`.
    """
    root = syntax_tree(raw, path)
    source = raw.encode("utf-8")
    for node in root.named_children:
        if node.type != "export_statement":
            continue
        text = _one_line((node.text or b"").decode("utf-8"))[:EXCERPT]
        target = string_value(node.child_by_field_name("source"))
        if target:
            yield node.start_point.row + 1, target, _shown_names(reexports(node, source)), text
            continue
        groups: dict[str, list[str]] = {}
        for _local, public, _type_only in export_specifiers(node):
            if public in imported:
                groups.setdefault(imported[public], []).append(public)
        for found, names in groups.items():
            yield node.start_point.row + 1, found, names, text


def _shown_names(entries: list[dict[str, Any]]) -> list[str]:
    """Give the public names of the records without a name with a control character."""
    return [entry["name"] for entry in entries if not has_control(entry["name"])]


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
