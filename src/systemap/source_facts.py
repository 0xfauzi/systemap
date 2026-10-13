"""The source fact readers give the facts that each language adapter writes with the same
meaning.

The shared modules read module records and entry points through these functions. A
function here does not examine a language name, a file suffix, or source syntax. A fact
that an older extraction did not write is not known. The readers then give the safe
value, and they do not give a pass.
"""

from __future__ import annotations

import json
from collections.abc import Collection, Iterable, Mapping
from typing import Any, NamedTuple

from systemap import unknown_causes
from systemap.model import source_parsed

# The imported-name value that means "the full module".
WHOLE_MODULE = "*"


class Located(NamedTuple):
    """The root-relative file, the source line (0 if not known), and the unknown record of
    an `unknown surface` line."""

    file: str
    line: int
    record: Mapping[str, Any]


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


def entry_symbol(point: Mapping[str, str]) -> str:
    """Give the name in the module that the entry point starts, or an empty string.

    The language adapter writes this name in `symbol`. An empty string tells that the
    entry point starts no single name, for example the full module. Facts from an older
    extraction have no `symbol`. Then the name is not known, and the result is empty, so
    that the entry point matches no symbol claim."""
    symbol = point.get("symbol")
    return symbol if isinstance(symbol, str) else ""


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


def unknown_fact_lines(
    facts: dict[str, Any], skip: Collection[str] = (), repository: bool = True
) -> list[str]:
    """Give the facts that the extractor could not fully read or connect.

    A module line is not given for a module in `skip`. The judgement gives a module line
    in the map that owns the module. The lines about entry points, test files, and
    configuration files apply to the full repository. Only `repository` gives them.
    """
    return [line for line, _cause in unknown_fact_causes(facts, skip, repository)]


def unknown_fact_causes(
    facts: dict[str, Any], skip: Collection[str] = (), repository: bool = True
) -> list[tuple[str, str]]:
    """Give each line of `unknown_fact_lines` with the cause that the adapter wrote.

    A record without a cause has the cause `unknown_causes.NOT_KNOWN`. A line is the
    identity of a finding. Thus it contains no line number, source excerpt, or parser
    version (`located_records` gives them). Two records with the same line give one line,
    with the cause of the first record.
    """
    modules = [
        (text, unknown_causes.of(found.record)) for text, found in _module_issues(facts, skip)
    ]
    lines = modules + _unknown_repository_lines(facts) if repository else modules
    first: dict[str, str] = {}
    for line, cause in lines:
        first.setdefault(line, cause)
    return list(first.items())


def _module_issues(facts: dict[str, Any], skip: Collection[str]) -> list[tuple[str, Located]]:
    """Give the line and the source location of each unknown record of a module.

    `answer_migrations` reads the earlier forms of these lines: with the line number in
    the location, with a source excerpt, and with the parser version."""
    out: list[tuple[str, Located]] = []
    for module, record in sorted(facts.get("components", {}).items()):
        if module in skip:
            continue
        file = record.get("file", module)
        issues = [record["parse_error"]] if record.get("parse_error") else []
        for issue in [*issues, *record.get("unknown", [])]:
            line = f"unknown surface: module {module} ({file}): {issue['reason']}"
            out.append((line, Located(file, int(issue.get("line") or 0), issue)))
    return out


def _test_file_issues(facts: dict[str, Any]) -> list[tuple[str, Located]]:
    """Give the line and the source location of each test file that could not be read."""
    out: list[tuple[str, Located]] = []
    for issue in facts.get("test_file_issues", []):
        problem = issue["problem"]
        line = f"unknown surface: test file {issue['file']}: {problem['reason']}"
        out.append((line, Located(issue["file"], int(problem.get("line") or 0), problem)))
    return out


def _unknown_repository_lines(facts: dict[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for issue in facts.get("entry_point_issues", []):
        line = (
            f"unknown surface: {issue['kind']} {issue['name']} -> {issue['target']}: "
            f"{issue['reason']}"
        )
        out.append((line, unknown_causes.of(issue)))
    out += [(line, unknown_causes.of(found.record)) for line, found in _test_file_issues(facts)]
    for issue in facts.get("config_issues", []):
        # `answer_migrations` reads the earlier form of this line, which named npm.
        line = (
            f"unknown surface: {issue['file']} extends {issue['reference']!r}: "
            "the configuration package could not be read"
        )
        out.append((line, unknown_causes.of(issue)))
    return out


def located_records(facts: dict[str, Any]) -> dict[str, list[Located]]:
    """Give the source location and the record of each record of an `unknown surface`
    line of a module or a test file.

    The location is not part of the line: a new line above a statement changes the line
    number, but not the finding. Two records with the same line give one line with two
    locations. `judgement_evidence.located_state` gives the evidence of the statements.
    """
    out: dict[str, list[Located]] = {}
    for line, found in [*_module_issues(facts, ()), *_test_file_issues(facts)]:
        out.setdefault(line, []).append(found)
    return out


def source_fields(found: Located) -> dict[str, Any]:
    """Give the file, the line, the source excerpt, and the parser version of one record.

    A value that the record does not give is None. These values change while the finding
    stays the same. Thus they are not in the line. `judgement --json` gives these fields.
    """
    excerpt = found.record.get("source")
    parser = found.record.get("parser")
    return {
        "file": found.file,
        "line": found.line or None,
        "excerpt": excerpt if found.line and isinstance(excerpt, str) and excerpt else None,
        "parser": parser if isinstance(parser, str) and parser else None,
    }


def source_rows(sources: Iterable[Mapping[str, Any]]) -> list[str]:
    """Give the text rows below an `unknown surface` line for the fields of its records:
    `at:`, `excerpt:`, and `parser version:`. `judgement`, `check`, and `refresh` use
    this one function."""
    rows: list[str] = []
    for source in sources:
        rows += [f"at: {source['file']}:{source['line']}"] if source["line"] else []
        rows += [f"excerpt: {source['excerpt']!r}"] if source["excerpt"] else []
        rows += [f"parser version: {source['parser']}"] if source["parser"] else []
    return rows


def unknown_rows(facts: dict[str, Any]) -> dict[str, list[str]]:
    """Give the source rows of each `unknown surface` line that has rows."""
    found = {
        line: source_rows(source_fields(item) for item in records)
        for line, records in located_records(facts).items()
    }
    return {line: rows for line, rows in found.items() if rows}


def inventory_issue_lines(facts: dict[str, Any]) -> list[str]:
    """List the modules that the extractor could not read or parse."""
    return [line for line, _cause in inventory_issue_causes(facts)]


def inventory_issue_causes(facts: dict[str, Any]) -> list[tuple[str, str]]:
    """Give each module that the extractor could not read or parse, with its cause.

    These records are not known. They do not reject the map. Each result that reads the
    module stays not known: the component has no current source review digest, and an
    import rule that reads the module is `unknown`. A test file that the extractor could
    not read or parse does not give a line here. `unknown_fact_lines` gives it.
    """
    out: list[tuple[str, str]] = []
    for module, record in sorted(facts.get("components", {}).items()):
        if not source_parsed(record):
            state = record.get("completeness")
            cause = unknown_causes.of(state) if isinstance(state, Mapping) else NOT_KNOWN
            out.append((f"source inventory unresolved: {module} ({record['file']})", cause))
    return out


NOT_KNOWN = unknown_causes.NOT_KNOWN
