"""The TypeScript entry reader finds the package entry points of the source modules.

It reads `bin` and `exports` in the top-level package.json file and in the package.json
file of each package directory that contains source modules. Each compiled target maps
to a source module through the tsconfig project of its package.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from systemap.typescript_config import (
    TypeScriptConfig,
    package_json,
    root_candidates,
    source_targets,
)
from systemap.typescript_projects import path_choices

if TYPE_CHECKING:
    from systemap.typescript import TypeScriptContext

BUILD_DIRS = {"build", "dist", "distribution", "lib"}
BUILD_FORMATS = {"cjs", "esm", "types"}
TARGET_SUFFIXES = (".js", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts")
BIN_REASON = "The parser could not resolve the package.json bin target to a TypeScript module."


@dataclass(frozen=True)
class Package:
    """This record gives one package.json file and the compiler settings of its directory."""

    directory: Path
    data: dict[str, Any]
    compiler: TypeScriptConfig
    source_roots: tuple[Path, ...]
    # The text before each target in an issue. It is empty for the top-level package.
    label: str = ""


def entry_points(
    repo: Path,
    prefixes: set[str],
    components: dict[str, Any],
    context: TypeScriptContext,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """This function gives the package entry points and the targets that do not resolve."""
    points: list[dict[str, str]] = []
    issues: list[dict[str, str]] = []
    root_modules = {f"{prefix}.index" for prefix in prefixes}
    for package in _packages(repo, context):
        root_modules.update(_package_entries(package, context, points, issues))
    points.extend(_public_functions(root_modules, components))
    return _unique_points(points), issues


def _packages(repo: Path, context: TypeScriptContext) -> Iterator[Package]:
    yield Package(repo, package_json(repo), context.compiler, context.source_roots)
    projects = context.projects
    if projects is None:
        return
    directories = {projects.package_directory(path) for path in context.modules_by_path}
    for directory in sorted(found for found in directories if found is not None):
        compiler = projects.config_for_directory(directory)
        yield Package(
            directory,
            package_json(directory),
            compiler,
            # The imported files count, as in the top-level context: tsc 5 takes the
            # common folder of all program files as the output root.
            root_candidates(compiler, projects.lazy_program_files(compiler)),
            directory.relative_to(context.repo.resolve()).as_posix() + "/",
        )


def _package_entries(
    package: Package,
    context: TypeScriptContext,
    points: list[dict[str, str]],
    issues: list[dict[str, str]],
) -> set[str]:
    for name, target in _bin_targets(package.data, package.directory):
        module = _entry_module(target, package, context)
        if module:
            points.append({"kind": "console_script", "name": name, "module": module, "target": ""})
        else:
            shown = package.label + target.removeprefix("./") if package.label else target
            issues.append(_entry_issue("package_bin", name, shown, BIN_REASON))
    modules, export_issues = _package_exports(package, context)
    issues.extend(export_issues)
    return modules


def _package_exports(
    package: Package, context: TypeScriptContext
) -> tuple[set[str], list[dict[str, str]]]:
    name = str(package.data.get("name", package.directory.name))
    modules: set[str] = set()
    unmapped: list[str] = []
    for target in _export_targets(package.data.get("exports")):
        if "*" in target:
            unmapped.append(target)
            continue
        if target.endswith(".d.ts") or not target.endswith(TARGET_SUFFIXES):
            continue
        module = _entry_module(target, package, context)
        if module:
            modules.add(module)
        else:
            unmapped.append(target)
    if not unmapped:
        return modules, []
    sample = package.label + unmapped[0]
    if len(unmapped) > 1:
        sample += f" (+{len(unmapped) - 1} more)"
    reason = f"{len(unmapped)} package.json export targets have no resolved TypeScript modules."
    return modules, [_entry_issue("package_export", name, sample, reason)]


def _entry_module(target: str, package: Package, context: TypeScriptContext) -> str | None:
    if not target.endswith(TARGET_SUFFIXES):
        return None
    sources = source_targets(target, package.directory, package.compiler, package.source_roots)
    direct = _matching_entry_modules(sources, context)
    if len(direct) == 1:
        return next(iter(direct))
    if direct or _in_out_dir(target, package):
        # Two roots each name a module: which one tsc used is not knowable
        # from here, and a wrong answer costs more than none. A target in the
        # configured outDir has only the tsc mapping.
        return None
    fallback = _matching_entry_modules(_built_source_candidates(target, package.directory), context)
    return next(iter(fallback)) if len(fallback) == 1 else None


def _in_out_dir(target: str, package: Package) -> bool:
    out_dir = package.compiler.out_dir
    return out_dir is not None and (package.directory / target).resolve().is_relative_to(out_dir)


def _matching_entry_modules(candidates: Iterable[Path], context: TypeScriptContext) -> set[str]:
    return {
        context.modules_by_path[choice.resolve()]
        for source in candidates
        for choice in path_choices(source)
        if choice.resolve() in context.modules_by_path
    }


def _built_source_candidates(target: str, directory: Path) -> Iterator[Path]:
    parts = PurePosixPath(target.removeprefix("./")).parts
    if len(parts) < 2 or parts[0] not in BUILD_DIRS:
        return
    tails = [parts[1:]]
    if len(parts) > 2 and parts[1] in BUILD_FORMATS:
        tails.append(parts[2:])
    for root in ("src", "source"):
        for tail in tails:
            yield directory / root / Path(*tail)


def _export_targets(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value.removeprefix("./")
    elif isinstance(value, dict):
        for nested in value.values():
            yield from _export_targets(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _export_targets(nested)


def _bin_targets(package: dict[str, Any], directory: Path) -> list[tuple[str, str]]:
    bins = package.get("bin", {})
    if isinstance(bins, str):
        return [(str(package.get("name", directory.name)), bins)]
    if not isinstance(bins, dict):
        return []
    return [(str(name), target) for name, target in sorted(bins.items()) if isinstance(target, str)]


def _entry_issue(kind: str, name: str, target: str, reason: str) -> dict[str, str]:
    return {"kind": kind, "name": name, "target": target, "reason": reason}


def _public_functions(modules: set[str], components: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"kind": "public_function", "name": function["name"], "module": module, "target": ""}
        for module in sorted(modules)
        for function in components.get(module, {}).get("names", [])
        if function.get("kind") == "function"
    ]


def _unique_points(points: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, str]] = []
    for point in points:
        key = point["kind"], point["name"], point["module"]
        if key not in seen:
            seen.add(key)
            out.append(point)
    return out
