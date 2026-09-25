"""Read TypeScript and TSX into systemap's language-neutral facts."""

from __future__ import annotations

import fnmatch
import hashlib
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from systemap.config import ConfigError
from systemap.typescript_config import (
    TypeScriptConfig,
    alias_targets,
    load_typescript_config,
    package_json,
    source_target,
)
from systemap.typescript_surface import _root as parse_root
from systemap.typescript_surface import parse_problem, parse_surface, test_names

SOURCE_SUFFIXES = (".ts", ".tsx")
TEST_SUFFIXES = (".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")
TEST_FILES = ("test.ts", "test.tsx")
SKIP_PARTS = {".git", ".venv", "node_modules", "build", "dist"}
WHOLE_MODULE = "*"
CONSTANTS_KEPT = 14
TESTS_KEPT = 25


@dataclass
class TypeScriptContext:
    """Indexes built once so each import does constant work."""

    repo: Path
    modules_by_path: dict[Path, str]
    compiler: TypeScriptConfig
    tests_dirs: tuple[str, ...]
    test_patterns: tuple[str, ...]
    test_issues: list[dict[str, Any]] = field(default_factory=list)


def _test_path(
    path: Path, repo: Path, tests_dirs: tuple[str, ...], patterns: tuple[str, ...]
) -> bool:
    if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
        return False
    if any(part in SKIP_PARTS for part in path.parts):
        return False
    return _test_file(path.relative_to(repo).as_posix(), tests_dirs, patterns)


def _test_file_guards(
    path: Path,
    repo: Path,
    paths: dict[str, Path],
    context: TypeScriptContext,
) -> dict[str, list[dict[str, Any]]]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    root = parse_root(raw, path.as_posix())
    if root is None:
        context.test_issues.append(
            {
                "file": path.relative_to(repo).as_posix(),
                "problem": parse_problem(raw, path.as_posix()),
            }
        )
        return {}
    targets = {
        target
        for specifier, _names in _imports(root)
        if (target := _target_from_path(specifier, path, paths, context))
    }
    names = test_names(raw, path.as_posix())[:TESTS_KEPT]
    stem = path.name.split(".", 1)[0].removeprefix("test_")
    guards: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for target in targets:
        primary = stem == target.rsplit(".", 1)[-1]
        guards[target] = [{"name": name, "primary": primary} for name in names]
    return dict(guards)


def _module_name(name: str) -> str:
    return name.removeprefix("@").replace("/", ".").replace("-", "_")


def _without_script_suffix(specifier: str) -> str:
    for suffix in (".d.ts", ".tsx", ".ts", ".jsx", ".js", ".mjs", ".cjs"):
        if specifier.endswith(suffix):
            return specifier[: -len(suffix)]
    return specifier


def _test_file(path: str, tests_dirs: tuple[str, ...], patterns: tuple[str, ...]) -> bool:
    relative = PurePosixPath(path).as_posix()
    if PurePosixPath(path).suffix not in SOURCE_SUFFIXES or relative.endswith(".d.ts"):
        return False
    if any(relative.startswith(f"{folder.rstrip('/')}/") for folder in tests_dirs if folder):
        return True
    name = PurePosixPath(path).name
    if name.startswith("test_") or name in TEST_FILES or name.endswith(TEST_SUFFIXES):
        return True
    return any(
        fnmatch.fnmatchcase(relative, pattern)
        or fnmatch.fnmatchcase(relative, pattern.replace("**/", ""))
        for pattern in patterns
    )


def _path_choices(target: Path) -> list[Path]:
    if target.suffix in SOURCE_SUFFIXES:
        return [target]
    stem = target.with_suffix("") if target.suffix else target
    return [stem.with_suffix(suffix) for suffix in SOURCE_SUFFIXES] + [
        (stem / "index").with_suffix(suffix) for suffix in SOURCE_SUFFIXES
    ]


def _target_from_path(
    specifier: str,
    importer: Path,
    paths: dict[str, Path],
    context: TypeScriptContext,
) -> str | None:
    if specifier.startswith("."):
        targets = [importer.parent / _without_script_suffix(specifier)]
    else:
        normalized = _module_name(_without_script_suffix(specifier))
        named = next((name for name in (normalized, f"{normalized}.index") if name in paths), None)
        if named:
            return named
        targets = alias_targets(specifier, context.compiler, context.repo)
    return next(
        (
            context.modules_by_path[choice.resolve()]
            for target in targets
            for choice in _path_choices(target)
            if choice.resolve() in context.modules_by_path
        ),
        None,
    )


def _module_candidate(specifier: str, module: str) -> str:
    specifier = _without_script_suffix(specifier)
    if not specifier.startswith("."):
        return _module_name(specifier)
    parts = module.split(".")[:-1]
    for part in PurePosixPath(specifier).parts:
        if part == "..":
            if parts:
                parts.pop()
        elif part != ".":
            parts.append(part.replace("-", "_"))
    return ".".join(parts)


def _known_module(candidate: str, known: set[str]) -> str | None:
    return next((choice for choice in (candidate, f"{candidate}.index") if choice in known), None)


def _resolve(
    specifier: str,
    module: str,
    known: set[str],
    paths: dict[str, Path],
    context: TypeScriptContext,
) -> str | None:
    importer = paths.get(module)
    if importer is not None:
        target = _target_from_path(specifier, importer, paths, context)
        if target:
            return target
    return _known_module(_module_candidate(specifier, module), known)


def _imported_names(node: Any) -> set[str]:
    clause = next((child for child in node.named_children if child.type == "import_clause"), None)
    if clause is None:
        return {WHOLE_MODULE}
    if any(child.type == "namespace_import" for child in _walk(clause)):
        return {WHOLE_MODULE}
    out: set[str] = set()
    if any(child.type == "identifier" for child in clause.named_children):
        out.add("default")
    for specifier in (child for child in _walk(clause) if child.type == "import_specifier"):
        original = next(
            (child for child in specifier.named_children if child.type == "identifier"), None
        )
        if original is not None:
            out.add(_text(original))
    return out


def _exported_names(node: Any) -> set[str]:
    clause = next((child for child in node.named_children if child.type == "export_clause"), None)
    if clause is None:
        return {WHOLE_MODULE}
    out: set[str] = set()
    for specifier in (child for child in clause.named_children if child.type == "export_specifier"):
        original = next(
            (
                child
                for child in specifier.named_children
                if child.type in ("identifier", "type_identifier")
            ),
            None,
        )
        if original is not None:
            out.add(_text(original))
    return out or {WHOLE_MODULE}


def _walk(node: Any) -> Iterator[Any]:
    yield node
    for child in node.named_children:
        yield from _walk(child)


def _text(node: Any | None) -> str:
    return (node.text or b"").decode("utf-8") if node is not None else ""


def _source(node: Any) -> str:
    source = node.child_by_field_name("source")
    if source is None or source.type != "string":
        return ""
    fragment = next(
        (child for child in source.named_children if child.type == "string_fragment"), None
    )
    return (fragment.text or b"").decode("utf-8") if fragment is not None else ""


def _imports(root: Any) -> Iterator[tuple[str, set[str]]]:
    for node in root.named_children:
        specifier = _source(node)
        if not specifier:
            continue
        if node.type == "import_statement":
            yield specifier, _imported_names(node)
        elif node.type == "export_statement":
            yield specifier, _exported_names(node)


def _problem(line: int, reason: str, source: str) -> dict[str, Any]:
    return {"line": line, "reason": reason, "source": source[:120]}


class TypeScriptLanguage:
    """TypeScript syntax normalized to the facts Python already consumes."""

    name = "typescript"

    def source_paths(
        self,
        root: Path,
        repo: Path,
        tests_dirs: tuple[str, ...],
        test_patterns: tuple[str, ...],
    ) -> Iterable[Path]:
        return (
            path
            for suffix in SOURCE_SUFFIXES
            for path in root.rglob(f"*{suffix}")
            if not any(part in SKIP_PARTS for part in path.parts)
            and not _test_file(path.relative_to(repo).as_posix(), tests_dirs, test_patterns)
        )

    def context(
        self,
        repo: Path,
        paths: dict[str, Path],
        tests_dirs: tuple[str, ...],
        test_patterns: tuple[str, ...],
    ) -> TypeScriptContext:
        try:
            compiler = load_typescript_config(repo)
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
        return TypeScriptContext(
            repo=repo,
            modules_by_path={path.resolve(): module for module, path in paths.items()},
            compiler=compiler,
            tests_dirs=tests_dirs,
            test_patterns=test_patterns,
        )

    def module_of(self, path: Path, root: Path, name: str) -> str:
        parts = path.relative_to(root).with_suffix("").parts
        return ".".join((name, *(part.replace("-", "_") for part in parts)))

    def module_for_path(self, repo: Path, path: str, roots: list[tuple[Path, str]]) -> str | None:
        absolute = repo / path
        if absolute.suffix not in SOURCE_SUFFIXES or absolute.name.endswith(".d.ts"):
            return None
        for root, name in roots:
            if absolute.is_relative_to(root):
                return self.module_of(absolute, root, name)
        return None

    def collect_module(
        self,
        path: Path,
        repo: Path,
        module: str,
        prefixes: frozenset[str],
        known: set[str],
        paths: dict[str, Path],
        context: TypeScriptContext,
    ) -> dict[str, Any] | None:
        del prefixes
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            return None
        surface = parse_surface(raw, path.as_posix())
        if surface is None:
            surface = {
                "docstring": "",
                "functions": [],
                "classes": [],
                "errors": [],
                "constants": [],
                "names": [],
                "unknown": [parse_problem(raw, path.as_posix())],
            }
        for entry in surface["names"]:
            source = entry.get("reexport_of")
            if not source:
                continue
            target = _resolve(source, module, known, paths, context)
            if target:
                entry["reexport_of"] = target
            else:
                entry["kind"] = "unknown"
                entry.pop("star", None)
                surface["unknown"].append(
                    _problem(
                        1,
                        f"the re-export target {source!r} is outside the extracted modules",
                        source,
                    )
                )
        return {
            "file": path.relative_to(repo).as_posix(),
            "loc": len(raw.splitlines()),
            "sha": hashlib.sha1(raw.encode(), usedforsecurity=False).hexdigest()[:12],
            **surface,
            "constants": surface["constants"][:CONSTANTS_KEPT],
        }

    def internal_uses(
        self,
        raw: str,
        prefixes: set[str],
        known: set[str],
        module: str = "",
        is_package: bool = False,
        repo: Path | None = None,
        paths: dict[str, Path] | None = None,
        context: TypeScriptContext | None = None,
    ) -> dict[str, set[str]]:
        del prefixes, is_package, repo
        source_path = (paths or {}).get(module)
        root = parse_root(raw, source_path.as_posix() if source_path else "")
        if root is None or context is None:
            return {}
        uses: dict[str, set[str]] = defaultdict(set)
        for specifier, names in _imports(root):
            target = _resolve(specifier, module, known, paths or {}, context)
            if target:
                uses[target].update(names)
        return dict(uses)

    def external_imports(
        self,
        raw: str,
        prefixes: set[str],
        module: str = "",
        repo: Path | None = None,
        paths: dict[str, Path] | None = None,
        context: TypeScriptContext | None = None,
    ) -> list[str]:
        source_path = (paths or {}).get(module)
        root = parse_root(raw, source_path.as_posix() if source_path else "")
        if root is None or context is None:
            return []
        out = {
            specifier
            for specifier, _names in _imports(root)
            if not specifier.startswith(".")
            and _resolve(specifier, module, set(paths or {}), paths or {}, context) is None
            and not any(
                _module_name(specifier) == prefix
                or _module_name(specifier).startswith(prefix + ".")
                for prefix in prefixes
            )
        }
        return sorted(out)

    def collect_tests(
        self,
        repo: Path,
        tests_dirs: tuple[str, ...],
        prefixes: set[str],
        paths: dict[str, Path],
        context: TypeScriptContext,
    ) -> dict[str, list[dict[str, Any]]]:
        del prefixes
        files = sorted(
            path
            for path in repo.rglob("*")
            if _test_path(path, repo, tests_dirs, context.test_patterns)
        )
        guards: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for path in files:
            for module, entries in _test_file_guards(path, repo, paths, context).items():
                guards[module].extend(entries)
        return guards

    def entry_points(
        self,
        repo: Path,
        prefixes: set[str],
        components: dict[str, Any],
        sources: dict[str, str],
        context: TypeScriptContext,
    ) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        del sources
        package = package_json(repo)
        points: list[dict[str, str]] = []
        issues: list[dict[str, str]] = []
        for name, target in _bin_targets(package, repo):
            self._add_entry_target(points, issues, name, target, repo, context)
        root_modules = {f"{prefix}.index" for prefix in prefixes}
        export_modules, export_issues = self._package_exports(package, repo, context)
        root_modules.update(export_modules)
        issues.extend(export_issues)
        points.extend(_public_functions(root_modules, components))
        return _unique_points(points), issues

    def _add_entry_target(
        self,
        points: list[dict[str, str]],
        issues: list[dict[str, str]],
        name: str,
        target: str,
        repo: Path,
        context: TypeScriptContext,
    ) -> None:
        module = self._entry_module(target, repo, context)
        if module:
            points.append({"kind": "console_script", "name": name, "module": module, "target": ""})
        else:
            issues.append(
                {
                    "kind": "package_bin",
                    "name": name,
                    "target": target,
                    "reason": "package.json bin target could not be mapped to a TypeScript module",
                }
            )

    def _package_exports(
        self, package: dict[str, Any], repo: Path, context: TypeScriptContext
    ) -> tuple[set[str], list[dict[str, str]]]:
        name = str(package.get("name", repo.name))
        modules: set[str] = set()
        issues: list[dict[str, str]] = []
        for target in _export_targets(package.get("exports")):
            if "*" in target:
                issues.append(
                    _entry_issue(
                        "package_export",
                        name,
                        target,
                        "wildcard package export cannot be mapped without choosing a subpath",
                    )
                )
                continue
            if target.endswith(".d.ts") or not target.endswith(
                (".js", ".mjs", ".cjs", ".ts", ".tsx")
            ):
                continue
            module = self._entry_module(target, repo, context)
            if module:
                modules.add(module)
            else:
                issues.append(
                    _entry_issue(
                        "package_export",
                        name,
                        target,
                        "package.json export target could not be mapped to a TypeScript module",
                    )
                )
        return modules, issues

    def _entry_module(self, target: str, repo: Path, context: TypeScriptContext) -> str | None:
        if not target.endswith((".js", ".mjs", ".cjs", ".ts", ".tsx")):
            return None
        source = source_target(target, repo, context.compiler)
        return next(
            (
                context.modules_by_path[choice.resolve()]
                for choice in _path_choices(source)
                if choice.resolve() in context.modules_by_path
            ),
            None,
        )

    def parse_surface(self, raw: str, path: str = "") -> dict[str, Any] | None:
        return parse_surface(raw, path)

    def test_names(self, raw: str, path: str = "") -> list[str]:
        return test_names(raw, path)

    def is_test_file(
        self, path: str, tests_dirs: tuple[str, ...], test_patterns: tuple[str, ...] = ()
    ) -> bool:
        return _test_file(path, tests_dirs, test_patterns)


def _export_targets(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value.removeprefix("./")
    elif isinstance(value, dict):
        for nested in value.values():
            yield from _export_targets(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _export_targets(nested)


def _bin_targets(package: dict[str, Any], repo: Path) -> list[tuple[str, str]]:
    bins = package.get("bin", {})
    if isinstance(bins, str):
        return [(str(package.get("name", repo.name)), bins)]
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


TYPESCRIPT = TypeScriptLanguage()
