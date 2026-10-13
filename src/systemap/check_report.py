"""Format the check result of one map as report lines for a person.

Each cause that makes the check fail gives a group: a heading, one line for each problem,
and a fix line. A test examines each field of `check.Result` that makes the check fail,
and makes sure that the report prints its lines. A model error has a group for its kind.
The group "map layout" contains only problems of positions, routes, labels, and text.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

from systemap import explain, unknown_causes
from systemap.schematic import TEXT_PX

if TYPE_CHECKING:
    from systemap.check import Coverage, Result
    from systemap.model import Model

# The prefixes that `model.problems` writes. A model problem stops the render of the map.
MEANING = "meaning: "
IMPORT_RULE = "import rule: "
PLACEMENT = "placement: "
MODEL_PREFIXES = (MEANING, IMPORT_RULE, PLACEMENT)

INVENTORY_FIX = (
    "  fix: Make sure that systemap can read and parse each file in the list. Then use "
    "systemap check."
)
STALE_FIX = "  fix: Use systemap refresh. Then commit the output directory."
STALE_AFTER_REFRESH_FIX = (
    "  fix: Make sure that each output in the configuration has a different path. If the "
    "paths are different, report this problem to the systemap project."
)


def plural(n: int, noun: str) -> str:
    return f"{n} {noun}{'s' if n != 1 else ''}"


def coverage_line(cov: Coverage) -> str:
    """This function formats the coverage counts, including ignored modules and empty
    package markers.
    """
    line = f"coverage: {cov.mapped} of {cov.total} modules mapped"
    if cov.ignored:
        line += f", {cov.ignored} ignored with a reason"
    if cov.markers:
        noun = "an empty package marker" if cov.markers == 1 else "empty package markers"
        line += f", {cov.markers} {noun}"
    return line


def report(
    model: Model,
    result: Result,
    model_file: str = "the model",
    prefix: str = "",
    teach: bool = True,
) -> list[str]:
    """This function gives the CLI report for one map.

    The report includes diagnostic groups and necessary actions. The optional prefix
    identifies a nested map. The `teach` option adds an explanation for each diagnostic
    group.
    """
    lines = _report(model, result, model_file)
    return [prefix + line for line in (_taught(lines) if teach else lines)]


def _taught(lines: list[str]) -> list[str]:
    """This function adds an explanation to each diagnostic group with errors."""
    out: list[str] = []
    for k, line in enumerate(lines):
        out.append(line)
        failed = k + 1 < len(lines) and lines[k + 1].startswith(" ")
        if failed:
            out += explain.rows(line.split(":")[0])
    return out


def report_stale(lines: list[str], teach: bool = True, after_refresh: bool = False) -> list[str]:
    """This function gives one stale-output report for the full map tree.

    After a refresh, a second refresh writes the same outputs. Thus the report then does
    not tell the person to use refresh again."""
    if not lines:
        return []
    kind = "stale after refresh" if after_refresh else "stale"
    return [
        f"{kind}: {plural(len(lines), 'problem')}",
        *(explain.rows(kind) if teach else []),
        *(f"  {line}" for line in lines),
        STALE_AFTER_REFRESH_FIX if after_refresh else STALE_FIX,
    ]


def _report(model: Model, result: Result, model_file: str) -> list[str]:
    through, across = result.through, result.across
    out = [
        (
            f"map routes: {through} flow path{('s' if through != 1 else '')} across components "
            f"other than their endpoints, {across} across regions other than their endpoint "
            f"regions."
        )
    ]
    out += _coverage(result.coverage, model_file)
    out += inventory_report(result.inventory_issues)
    out += _group(
        "nesting",
        result.nesting,
        f"In {model_file}, give each module of the parent component one claim. "
        f"Use other parent components as actors.",
    )
    out += _group(
        "entry",
        result.entry,
        "The map shows code in the facts. "
        f"In {model_file}, use modules from the facts. Set entry to a public "
        f"name that one of these modules defines.",
    )
    out += _group(
        "interface",
        result.interface,
        f"In {model_file}, start interface with a public name from the "
        f"component modules, or leave it empty. Use Class.method for a method.",
    )
    out += unknown_surface_report(result.unknown_surface, result.unknown_causes)
    out += _model_groups(result.problems, model_file)
    out += _layout(model, result.problems, model_file)
    out += report_stale(result.stale)
    return out


def _group(kind: str, lines: Sequence[str], fix: str, noun: str = "problem") -> list[str]:
    if not lines:
        return []
    head = f"{kind}: {plural(len(lines), noun)}"
    return [head, *(f"  {line}" for line in lines), f"  fix: {fix}"]


def _coverage(cov: Coverage, model_file: str) -> list[str]:
    if not cov.counted:
        return []
    if not cov.checked:
        return ["coverage: No facts are available for the check. Use systemap extract."]
    out = [coverage_line(cov), *(f"  {line}" for line in cov.problems)]
    if cov.problems:
        out.append(
            f"  fix: Give each module a component in {model_file}, or give a reason to "
            f"ignore it in [coverage] in the configuration. Remove each ignore entry "
            f"that a line identifies as not necessary or missing from the facts."
        )
    return out


def inventory_report(lines: Sequence[str]) -> list[str]:
    """Give the modules that the extractor could not read or parse. They reject the map."""
    if not lines:
        return []
    kind = "source inventory unresolved"
    return [
        f"{kind}: {plural(len(lines), 'problem')}",
        *(f"  {line.removeprefix(f'{kind}: ')}" for line in lines),
        INVENTORY_FIX,
    ]


def _model_groups(problems: Sequence[str], model_file: str) -> list[str]:
    """Give the meaning errors and the import rule errors of the model, each in a group."""
    fix = f"Change {model_file}. Then use systemap check."
    meaning = [line.removeprefix(MEANING) for line in problems if line.startswith(MEANING)]
    rules = [line.removeprefix(IMPORT_RULE) for line in problems if line.startswith(IMPORT_RULE)]
    return _group("map meaning", meaning, fix) + _group("import rule fields", rules, fix)


def _layout(model: Model, problems: Sequence[str], model_file: str) -> list[str]:
    """Give the problems of positions, routes, labels, and text.

    A model error stops the check before it renders the map. Then the check did not
    examine routes, labels, or text, and the report does not say that the layout has no
    errors."""
    layout = [line for line in problems if not line.startswith((MEANING, IMPORT_RULE))]
    if layout:
        return _group("map layout", layout, f"Change {model_file}. Then use systemap check.")
    if any(line.startswith(MODEL_PREFIXES) for line in problems):
        return [
            "map layout: The check did not render the map, because the model has errors. "
            "Correct the errors. Then use systemap check."
        ]
    n = len(model.components)
    return [
        f"map layout: has no errors ({n} components, {len(model.flows)} orthogonal "
        f"flow paths with labels, no text size less than {TEXT_PX:g}px)"
    ]


def unknown_surface_report(findings: Sequence[str], causes: Iterable[str] = ()) -> list[str]:
    """Give the not-known records, and one fix line for each cause that occurs.

    These records do not reject the map. Without a cause, the fix line of
    `unknown_causes.NOT_KNOWN` occurs."""
    if not findings:
        return []
    found = list(causes) or [unknown_causes.NOT_KNOWN]
    return [
        f"unknown surface: {plural(len(findings), 'finding')}",
        *(f"  {line.removeprefix('unknown surface: ')}" for line in findings),
        *unknown_causes.fix_lines(found),
    ]
