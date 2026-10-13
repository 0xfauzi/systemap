"""The source fact readers give the facts that each language adapter writes with the same
meaning.

The shared modules read module records and entry points through these functions. A
function here does not examine a language name, a file suffix, or source syntax. A fact
that an older extraction did not write is not known. The readers then give the safe
value, and they do not give a pass.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from systemap.model import source_parsed

# The imported-name value that means "the full module".
WHOLE_MODULE = "*"


def standard_label(point: Mapping[str, str]) -> str:
    """Give the display name of an entry point from its kind.

    An adapter uses this text for the kinds in this function. A kind that is not in this
    function gives the name and the module."""
    kind, name, module = point["kind"], point["name"], point["module"]
    target = point.get("target", "")
    labels = {
        "console_script": f"{name} (console script)",
        "main_module": name,
        "main_function": f"main() in {module}",
        "subcommand": (
            f"{target} {name} (subcommand)" if target else f"{name} (subcommand in {module})"
        ),
        "route": f"{name} (route)",
        "command": f"{name} (command)",
        "task": f"{name}() (background task in {module})",
        "plugin": f"{name} (plugin hook)",
    }
    return labels.get(kind, f"{name}() in {module}")


def entry_label(point: Mapping[str, str]) -> str:
    """Give the display name that the adapter wrote for the entry point.

    Facts from an older extraction have no label. Then the standard label of the kind
    is the display name, as the older extraction gave it. Finding lines that contain
    the label then stay the same."""
    return str(point.get("label") or standard_label(point))


def entry_identity(point: Mapping[str, str]) -> str:
    """Get an entry-point identity that is separate from its display name."""
    return json.dumps(
        [point["kind"], point["module"], point.get("target", ""), point["name"]],
        separators=(",", ":"),
        ensure_ascii=False,
    )


def is_empty_marker(record: Mapping[str, Any]) -> bool:
    """Find a module that only marks a package and holds no code.

    The adapter writes `empty_marker`. Coverage excludes these markers, and the
    extraction summary lists them. A record without the fact is not a marker."""
    return record.get("empty_marker") is True


def empty_markers(facts: Mapping[str, Any]) -> list[str]:
    """List each empty package marker by module name."""
    return sorted(m for m, r in facts.get("components", {}).items() if is_empty_marker(r))


def package_of(module: str, components: Mapping[str, Any]) -> str:
    """Give the package that the adapter wrote for the module.

    Without a record or a `package` fact, the package is not known. Then the module
    itself is the result, so the module shares a package only with itself."""
    record = components.get(module)
    package = record.get("package") if isinstance(record, Mapping) else None
    return package if isinstance(package, str) and package else module


def module_file(module: str, components: Mapping[str, Any]) -> str:
    """Give the root-relative source file of the module, or an empty string."""
    record = components.get(module)
    file = record.get("file") if isinstance(record, Mapping) else None
    return file if isinstance(file, str) else ""


def unknown_fact_lines(facts: dict[str, Any]) -> list[str]:
    """Give the facts that the extractor could not fully read or connect."""
    out: list[str] = []
    for module, record in sorted(facts.get("components", {}).items()):
        file = record.get("file", module)
        if issue := record.get("parse_error"):
            location = f"{file}:{issue['line']}" if issue.get("line") else file
            # `answer_migrations` reads the earlier form of this line, which named Python.
            out.append(
                f"unknown surface: module {module} ({location}): {issue['reason']} "
                f"(parser version {issue['parser']})"
            )
        for issue in record.get("unknown", []):
            line = issue.get("line", 0)
            location = f"{file}:{line}" if line else file
            out.append(f"unknown surface: module {module} ({location}): {issue['reason']}")
    for issue in facts.get("entry_point_issues", []):
        out.append(
            f"unknown surface: {issue['kind']} {issue['name']} -> {issue['target']}: "
            f"{issue['reason']}"
        )
    for issue in facts.get("test_file_issues", []):
        problem = issue["problem"]
        out.append(
            f"unknown surface: test file {issue['file']}:{problem.get('line', 0)}: "
            f"{problem['reason']}"
        )
    for issue in facts.get("config_issues", []):
        # `answer_migrations` reads the earlier form of this line, which named npm.
        out.append(
            f"unknown surface: {issue['file']} extends {issue['reference']!r}: "
            "the configuration package could not be read"
        )
    return out


def inventory_issue_lines(facts: dict[str, Any]) -> list[str]:
    """List files with an unresolved source inventory."""
    out: list[str] = []
    for module, record in sorted(facts.get("components", {}).items()):
        if not source_parsed(record):
            out.append(f"source inventory unresolved: {module} ({record['file']})")
    for issue in facts.get("test_file_issues", []):
        out.append(f"source inventory unresolved: test file {issue['file']}")
    return out
